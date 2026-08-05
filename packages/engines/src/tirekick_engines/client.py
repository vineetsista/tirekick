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
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cache
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


@cache
def _retryable_errors() -> tuple[type[BaseException], ...]:
    """Transport errors worth trying again, resolved without importing at module load.

    This function is the reason CI caught a bug the author's laptop could not.
    An earlier version imported `anthropic` at the top of the send loop, which
    runs even when the client is a test double - so the whole live-path suite
    passed locally, where the `live` extra happens to be installed, and failed in
    CI, where it deliberately is not.

    An empty tuple is a valid `except` clause and catches nothing, which is the
    correct behaviour when the SDK is absent: there is no real transport to have
    a transient failure.
    """
    try:
        import anthropic
    except ImportError:
        return ()
    # RateLimitError subclasses APIStatusError; the 429 is separated by status
    # code in the handler rather than by type.
    return (anthropic.APIStatusError, anthropic.APIConnectionError)


#: Characters permitted in a cache key component.
#:
#: The key becomes a filename, and `subject` is an asset id that arrives from a
#: manifest - user input under LAW 3. An id of `../../../etc/whatever` made
#: `_write_cache` mkdir and write attacker-named JSON anywhere the process
#: could reach, and made fixture mode read from there. Every id the pipeline
#: has ever produced passes this; nothing that escapes a directory does.
_CACHE_KEY_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _cache_key(engine: str, task: str, subject: str) -> str:
    for part in (engine, task, subject):
        if not _CACHE_KEY_OK.match(part) or ".." in part:
            raise ValueError(
                f"unusable cache-key component {part!r}: a cache key becomes a "
                f"filename, so it may not contain separators or traversal"
            )
    return f"{engine}.{task}.{subject}"


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


#: Only resize when the image is meaningfully oversized. Shrinking a 1600px photo
#: to 1568px costs a full-quality resample of two million pixels and saves about
#: 4% of the image tokens - a trade that was costing roughly a second per image
#: before anyone measured it.
RESIZE_TOLERANCE = 1.08


def _target_size(size: tuple[int, int], max_edge: int) -> tuple[int, int] | None:
    """The size to decode to, or None when the image is already small enough."""
    if max(size) <= max_edge * RESIZE_TOLERANCE:
        return None
    ratio = max_edge / max(size)
    return (max(1, round(size[0] * ratio)), max(1, round(size[1] * ratio)))


@cache
def _encoded(path: str, mtime_ns: int, size: int, max_edge: int) -> tuple[str, str, int, int]:
    """Cached encode, keyed on the file's identity rather than its name.

    A single photograph is sent to the classifier and then to up to three
    stage-2 passes, so without this a report re-encodes the same bytes four
    times. Keyed on mtime and size so editing a file invalidates the entry.
    """
    from PIL import Image

    with Image.open(path) as image:
        target = _target_size(image.size, max_edge)
        if target is not None:
            # Ask libjpeg to decode straight to roughly the size we want, in the
            # DCT domain at 1/2, 1/4 or 1/8 scale. Far cheaper than decoding at
            # full resolution and resampling afterwards, and a no-op on formats
            # that do not support it.
            #
            # The target has to be the real box, not a square. Pillow picks its
            # scale with integer division on BOTH axes and takes the minimum, so
            # passing (1568, 1568) for a 4032x3024 photo computes
            # min(4032//1568, 3024//1568) = min(2, 1) = 1 and quietly does
            # nothing at all.
            image.draft("RGB", target)

        image = image.convert("RGB")

        if target is not None and image.size != target:
            image = image.resize(target, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=88)
        return (
            base64.standard_b64encode(buffer.getvalue()).decode("ascii"),
            "image/jpeg",
            image.width,
            image.height,
        )


def encode_image(path: Path, *, max_edge: int = MAX_IMAGE_EDGE) -> tuple[str, str, int, int]:
    """Return (base64 data, media type, width, height), downscaled if oversized.

    Downscaling here rather than letting the API do it keeps the cost meter
    honest: image tokens are a function of dimensions, and we can only report a
    number we computed from the bytes we actually sent.
    """
    stat = path.stat()
    return _encoded(str(path), stat.st_mtime_ns, stat.st_size, max_edge)


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
        key = _cache_key(engine, task, subject)
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
        client = self._anthropic()
        retryable = _retryable_errors()
        last: BaseException | None = None
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
            except retryable as exc:
                status = getattr(exc, "status_code", None)
                # A 4xx that is not rate limiting is our bug - a bad schema, a bad
                # image, a bad key - and retrying it just spends money slower.
                if status is not None and 400 <= status < 500 and status != 429:
                    raise
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
        except ImportError as exc:
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
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
