"""Model access, with fixture mode as the default (DECISIONS.md D-009).

Fixture mode serves cached responses from disk. It is the default in code, not
just in CI config, so a missing API key produces a deterministic run rather than a
crash - and CI stays green on a fork with no secrets (LAW 7).

Live mode is opt-in via TIREKICK_MODE=live. The vision and audio prompts that live
mode will send land in P2 and P3; until then, live mode says so plainly instead of
pretending.

Every response passes through the CostMeter, including cached ones (at zero), so
the cost block is never silently absent.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cogs import CostMeter
from .models import RunMode


class FixtureMissing(RuntimeError):
    """A cached response was requested and does not exist."""


def resolve_mode(explicit: str | None = None) -> RunMode:
    raw = (explicit or os.environ.get("TIREKICK_MODE") or "fixture").strip().lower()
    if raw not in ("fixture", "live"):
        raise ValueError(f"TIREKICK_MODE must be 'fixture' or 'live', got {raw!r}")
    return raw  # type: ignore[return-value]


@dataclass
class ModelClient:
    """Returns structured engine output, from cache or from the API."""

    mode: RunMode
    cache_dir: Path
    meter: CostMeter

    def call(
        self,
        *,
        engine: str,
        task: str,
        subject: str,
        prompt: str,
        images: int = 0,
    ) -> dict[str, Any]:
        """Run one structured model task.

        `subject` identifies what is being analyzed (an asset id, a VIN) and,
        with engine and task, forms the cache key. Keys are readable filenames on
        purpose - a cached response should be reviewable in a diff.
        """
        key = f"{engine}.{task}.{subject}"
        if self.mode == "fixture":
            return self._from_cache(key, images=images)
        return self._from_api(key=key, prompt=prompt, images=images)

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

    def _from_api(self, *, key: str, prompt: str, images: int) -> dict[str, Any]:
        del prompt, images  # consumed by the P2/P3 implementations
        raise NotImplementedError(
            f"Live mode has no implementation for {key!r} yet. The vision engine "
            f"lands in P2 and the audio engine in P3; until then the only honest "
            f"run is TIREKICK_MODE=fixture. See phase_reports/."
        )
