"""Model access, with fixture mode as the default (DECISIONS.md D-009).

Fixture mode serves cached responses from disk. It is the default in code, not
just in CI config, so a missing API key produces a deterministic run rather than a
crash - and CI stays green on a fork with no secrets (LAW 7).

Live mode is opt-in via TIREKICK_MODE=live and needs both `anthropic` (the `live`
extra) and an API key. The import is deliberately inside the function that uses
it: CI installs the dev extra only, and a module-level import would make the
fixture path depend on a package it never calls.

Two things about the live path are worth knowing before reading it.

Structured output is forced through a tool, not requested in prose. The model is
given one tool whose input schema is the shape we need and is required to call it.
A prompt that politely asks for JSON gets JSON most of the time, and the residue
is a parse error at the worst moment; a forced tool call gets a schema-validated
object every time.

Every response records which prompt produced it. A cached response and the prompt
that generated it drift apart silently otherwise, and then a fixture that looks
like evidence of current behaviour is evidence of behaviour we replaced.
"""

from __future__ import annotations

import base64
import io
import json
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cogs import CostMeter
from .models import RunMode

#: Default model for vision work.
#:
#: A report runs a stage-1 classification plus targeted stage-2 passes over every
#: photo - eighteen image calls on the demo fixture - so the per-image model
#: choice is the whole of COGS. Sonnet is the default because the tasks here are
#: detection and transcription against an explicit schema rather than open-ended
#: reasoning. Whether that is the right call is an empirical question, and P3's
#: eval is where it gets answered on the labeled set rather than asserted here.
#: Override with TIREKICK_MODEL. See DECISIONS.md D-023.
DEFAULT_MODEL = "claude-sonnet-5"

#: Anthropic's long-edge limit before an image is downscaled server-side. Doing it
#: ourselves means the tokens we are billed for are the tokens we counted.
MAX_IMAGE_EDGE = 1568

MAX_ATTEMPTS = 3
RETRY_BACKOFF_SEC = (1.0, 4.0)


class FixtureMissing(RuntimeError):
    """A cached response was requested and does not exist."""


class LiveModeUnavailable(RuntimeError):
    """Live mode was requested but cannot run."""


def resolve_mode(explicit: str | None = None) -> RunMode:
    raw = (explicit or os.environ.get("TIREKICK_MODE") or "fixture").strip().lower()
    if raw not in ("fixture", "live"):
        raise ValueError(f"TIREKICK_MODE must be 'fixture' or 'live', got {raw!r}")
    return raw  # type: ignore[return-value]


def resolve_model(explicit: str | None = None) -> str:
    return (explicit or os.environ.get("TIREKICK_MODEL") or DEFAULT_MODEL).strip()


def encode_image(path: Path, *, max_edge: int = MAX_IMAGE_EDGE) -> tuple[str, str, int, int]:
    """Return (base64 data, media type, width, height), downscaled if oversized.

    Downscaling here rather than letting the API do it keeps the cost meter
    honest: image tokens are a function of dimensions, and we can only report a
    number we computed from the bytes we actually sent.
    """
    from PIL import Image

    with Image.open(path) as image:
        image = image.convert("RGB")
        if max(image.size) > max_edge:
            ratio = max_edge / max(image.size)
            image = image.resize(
                (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
                Image.Resampling.LANCZOS,
            )
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=88)
        return (
            base64.standard_b64encode(buffer.getvalue()).decode("ascii"),
            "image/jpeg",
            image.width,
            image.height,
        )


def image_tokens(width: int, height: int) -> int:
    """Anthropic's published approximation: width * height / 750.

    Used for the projection in docs/UNIT_ECONOMICS.md. A live run replaces it with
    the usage the API actually reports, and the two are compared rather than one
    quietly standing in for the other.
    """
    return round(width * height / 750)


@dataclass
class ModelClient:
    """Returns structured engine output, from cache or from the API."""

    mode: RunMode
    cache_dir: Path
    meter: CostMeter
    model: str = field(default_factory=resolve_model)
    #: Written alongside each live response so a cached fixture names its prompt.
    record_cache: bool = True

    def call(
        self,
        *,
        engine: str,
        task: str,
        subject: str,
        prompt: str,
        system: str | None = None,
        schema: dict[str, Any] | None = None,
        image_paths: Sequence[Path] = (),
        prompt_ref: str = "",
    ) -> dict[str, Any]:
        """Run one structured model task.

        `subject` identifies what is being analyzed (an asset id, a VIN) and,
        with engine and task, forms the cache key. Keys are readable filenames on
        purpose - a cached response should be reviewable in a diff.
        """
        key = f"{engine}.{task}.{subject}"
        if self.mode == "fixture":
            return self._from_cache(key, images=len(image_paths))
        return self._from_api(
            key=key,
            prompt=prompt,
            system=system,
            schema=schema,
            image_paths=image_paths,
            prompt_ref=prompt_ref,
        )

    # ------------------------------------------------------------------ #

    def _from_cache(self, key: str, *, images: int) -> dict[str, Any]:
        path = self.cache_dir / f"{key}.json"
        if not path.is_file():
            raise FixtureMissing(
                f"No cached response at {path}. Fixture mode cannot invent one - "
                f"that would be fabricating a finding (LAW 1). Either add the "
                f"cached response or run with TIREKICK_MODE=live."
            )
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        # Cached calls are billed at zero, but the work they stand in for is still
        # counted: image and call counts are what a live run would have paid for,
        # and a fixture run that reported zero images would hide the shape of the
        # cost rather than reporting it truthfully at zero.
        self.meter.record_model_call(
            label=f"cache:{key}", input_tokens=0, output_tokens=0, images=images
        )
        return payload

    def _from_api(
        self,
        *,
        key: str,
        prompt: str,
        system: str | None,
        schema: dict[str, Any] | None,
        image_paths: Sequence[Path],
        prompt_ref: str,
    ) -> dict[str, Any]:
        if schema is None:
            raise LiveModeUnavailable(
                f"{key!r} was called live with no output schema. Every live call "
                f"forces a schema-validated tool call; there is no free-text path."
            )
        content: list[dict[str, Any]] = []
        counted_image_tokens = 0
        for path in image_paths:
            data, media_type, width, height = encode_image(path)
            counted_image_tokens += image_tokens(width, height)
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": data},
                }
            )
        content.append({"type": "text", "text": prompt})

        tool = {
            "name": "report_observations",
            "description": (
                "Report what is visible in the image, in the required shape. This "
                "is the only way to answer. An empty findings list is a valid and "
                "frequently correct answer."
            ),
            "input_schema": schema,
        }

        message = self._send(
            system=system,
            content=content,
            tool=tool,
        )

        self.meter.record_model_call(
            label=f"live:{key}",
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            images=len(image_paths),
        )
        self.meter.record_projected_image_tokens(counted_image_tokens)

        payload = self._tool_input(message, key=key)
        payload["_prompt_ref"] = prompt_ref
        payload["_model"] = self.model
        if self.record_cache:
            self._write_cache(key, payload)
        return payload

    def _send(
        self, *, system: str | None, content: list[dict[str, Any]], tool: dict[str, Any]
    ) -> Any:
        """One call, retried on transient failures only."""
        import anthropic

        client = self._anthropic()
        last: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                return client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=system or "",
                    tools=[tool],
                    tool_choice={"type": "tool", "name": tool["name"]},
                    messages=[{"role": "user", "content": content}],
                )
            except (anthropic.RateLimitError, anthropic.APIStatusError) as exc:
                status = getattr(exc, "status_code", None)
                # A 4xx that is not rate limiting is our bug - a bad schema, a bad
                # image, a bad key - and retrying it just spends money slower.
                if status is not None and 400 <= status < 500 and status != 429:
                    raise
                last = exc
            except anthropic.APIConnectionError as exc:
                last = exc
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF_SEC[min(attempt, len(RETRY_BACKOFF_SEC) - 1)])
        raise LiveModeUnavailable(f"model call failed after {MAX_ATTEMPTS} attempts: {last}")

    @staticmethod
    def _tool_input(message: Any, *, key: str) -> dict[str, Any]:
        for block in message.content:
            if getattr(block, "type", None) == "tool_use":
                return dict(block.input)
        raise LiveModeUnavailable(
            f"{key!r}: the model returned no tool call despite tool_choice forcing "
            f"one. Nothing is inferred from the prose it returned instead."
        )

    def _anthropic(self) -> Any:
        try:
            import anthropic
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on extras
            raise LiveModeUnavailable(
                "Live mode needs the 'live' extra: pip install -e "
                "'packages/engines[live]'. Fixture mode needs nothing."
            ) from exc
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise LiveModeUnavailable(
                "Live mode needs ANTHROPIC_API_KEY. Fixture mode is the default "
                "and needs no key (D-009)."
            )
        return anthropic.Anthropic()

    def _write_cache(self, key: str, payload: dict[str, Any]) -> None:
        """Persist a live response so the next run is reproducible and free."""
        path = self.cache_dir / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
