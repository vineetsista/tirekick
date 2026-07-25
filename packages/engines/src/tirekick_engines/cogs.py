"""LAW 5 - COGS visible.

Every run prints what it cost. A fixture run prints $0.00 and says why; hiding a
zero trains us to stop reading the number, which is how the number stops being
true.

Token prices are declared here in one place so that when they change, the change
is a visible diff and not a silently wrong invoice.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Cost, RunMode

# USD per million tokens. Update deliberately; a stale number here understates COGS.
# Source: Anthropic public pricing. Verify before quoting these anywhere external.
PRICE_PER_MTOK_INPUT = 3.00
PRICE_PER_MTOK_OUTPUT = 15.00

#: Storage assumption for the per-report line, USD per GB-month.
PRICE_PER_GB_MONTH = 0.023


@dataclass
class CostMeter:
    """Accumulates real usage across a single inspection."""

    mode: RunMode
    input_tokens: int = 0
    output_tokens: int = 0
    images_analyzed: int = 0
    audio_seconds_processed: float = 0.0
    storage_bytes: int = 0
    _calls: list[str] = field(default_factory=list)

    def record_model_call(
        self,
        *,
        label: str,
        input_tokens: int,
        output_tokens: int,
        images: int = 0,
    ) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.images_analyzed += images
        self._calls.append(f"{label}: in={input_tokens} out={output_tokens} images={images}")

    def record_audio(self, seconds: float) -> None:
        self.audio_seconds_processed += seconds

    def record_storage(self, byte_count: int) -> None:
        self.storage_bytes += byte_count

    @property
    def usd_total(self) -> float:
        if self.mode == "fixture":
            # Cached responses. No inference was billed, so the honest total is zero.
            return 0.0
        tokens = (
            self.input_tokens / 1_000_000 * PRICE_PER_MTOK_INPUT
            + self.output_tokens / 1_000_000 * PRICE_PER_MTOK_OUTPUT
        )
        storage = self.storage_bytes / 1_000_000_000 * PRICE_PER_GB_MONTH
        return round(tokens + storage, 6)

    def note(self) -> str:
        if self.mode == "fixture":
            return (
                "Fixture mode: responses served from cache, no API calls billed. "
                "$0.00 is the true cost of this run and not a placeholder."
            )
        return (
            f"Live mode: {len(self._calls)} model calls, "
            f"{self.input_tokens} input and {self.output_tokens} output tokens at "
            f"${PRICE_PER_MTOK_INPUT}/${PRICE_PER_MTOK_OUTPUT} per Mtok."
        )

    def to_model(self) -> Cost:
        return Cost(
            mode=self.mode,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            images_analyzed=self.images_analyzed,
            audio_seconds_processed=round(self.audio_seconds_processed, 3),
            storage_bytes=self.storage_bytes,
            usd_total=self.usd_total,
            note=self.note(),
        )

    def render(self) -> str:
        """The block printed at the end of every run. LAW 5."""
        lines = [
            "  COST OF THIS REPORT",
            f"    mode                {self.mode}",
            f"    input tokens        {self.input_tokens:,}",
            f"    output tokens       {self.output_tokens:,}",
            f"    images analyzed     {self.images_analyzed}",
            f"    audio seconds       {self.audio_seconds_processed:.1f}",
            f"    storage             {self.storage_bytes / 1_000_000:.1f} MB",
            f"    TOTAL               ${self.usd_total:.4f}",
            f"    {self.note()}",
        ]
        return "\n".join(lines)
