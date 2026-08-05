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

# USD per million tokens, per model. Update deliberately; a stale number here
# understates COGS. Source: Anthropic public pricing. Verify before quoting these
# anywhere external.
#
# Keyed by model because the price and the model choice are one decision, not two.
# A single global pair silently reprices the moment TIREKICK_MODEL changes, which
# is exactly when the number matters most.
# Checked against Anthropic's published per-MTok list prices on 2026-08-04.
# A price table nobody re-checks is a cost projection that drifts away from the
# bill: opus-5 sat here at $15/$75 for three phases, three times its actual
# rate, and the note printed the wrong figure with no caveat because a wrong
# number that IS in the table looks authoritative.
#
# Both the alias and the dated id are keyed where both exist. TIREKICK_MODEL is
# documented with the alias, and keying only the dated id silently priced the
# spelling we tell people to use at the fallback rate.
MODEL_PRICES: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.00, 50.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
}

#: Used when the configured model is not in the table. Deliberately the most
#: expensive row rather than an average: an unknown model that turns out to be
#: cheap makes us look conservative, and one that turns out to be dear does not
#: silently blow the unit economics.
FALLBACK_PRICE = (15.00, 75.00)


def prices_for(model: str) -> tuple[float, float]:
    return MODEL_PRICES.get(model, FALLBACK_PRICE)


#: Storage assumption for the per-report line, USD per GB-month.
PRICE_PER_GB_MONTH = 0.023


@dataclass
class CostMeter:
    """Accumulates real usage across a single inspection."""

    mode: RunMode
    #: The model these prices are for. Recorded so a cost figure names the model
    #: that produced it rather than floating free of it.
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    images_analyzed: int = 0
    audio_seconds_processed: float = 0.0
    video_seconds_processed: float = 0.0
    storage_bytes: int = 0
    federal_lookups: int = 0
    #: Image tokens computed from the dimensions we actually sent. Kept beside the
    #: API's reported usage rather than instead of it, so the projection in
    #: UNIT_ECONOMICS can be checked against the invoice instead of trusted.
    projected_image_tokens: int = 0
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

    def record_federal_lookup(self, label: str) -> None:
        """vPIC and NHTSA are free to query. Counted anyway.

        A lookup that costs no money still costs a rate limit, a dependency, and
        the seconds a buyer spends waiting. Reporting only the line items that
        carry a dollar sign would make the cost block a billing summary rather
        than an honest account of what producing a report takes (LAW 5).
        """
        self.federal_lookups += 1
        self._calls.append(f"{label}: federal lookup, no charge")

    def record_projected_image_tokens(self, tokens: int) -> None:
        self.projected_image_tokens += tokens

    def record_audio(self, seconds: float) -> None:
        self.audio_seconds_processed += seconds

    def record_video_seconds(self, seconds: float) -> None:
        self.video_seconds_processed += seconds

    def record_storage(self, byte_count: int) -> None:
        self.storage_bytes += byte_count

    @property
    def usd_total(self) -> float:
        if self.mode == "fixture":
            # Cached responses. No inference was billed, so the honest total is zero.
            return 0.0
        price_in, price_out = prices_for(self.model)
        tokens = (
            self.input_tokens / 1_000_000 * price_in
            + self.output_tokens / 1_000_000 * price_out
        )
        storage = self.storage_bytes / 1_000_000_000 * PRICE_PER_GB_MONTH
        return round(tokens + storage, 6)

    def note(self) -> str:
        if self.mode == "fixture":
            return (
                "Fixture mode: responses served from cache, no API calls billed. "
                "$0.00 is the true cost of this run and not a placeholder."
            )
        price_in, price_out = prices_for(self.model)
        caveat = (
            ""
            if self.model in MODEL_PRICES
            else " This model is not in the price table, so it is charged here at "
            "the most expensive rate we know of - the figure is an upper bound, "
            "not a quote."
        )
        # `_calls` is every line item, federal lookups included; calling the
        # total "model calls" inflated the figure the unit economics are read
        # off by however many free lookups the run happened to make.
        model_calls = len(self._calls) - self.federal_lookups
        return (
            f"Live mode on {self.model or 'an unnamed model'}: {model_calls} "
            f"model calls, {self.input_tokens} input and {self.output_tokens} output "
            f"tokens at ${price_in}/${price_out} per Mtok.{caveat}"
        )

    def to_model(self) -> Cost:
        from .prompts import fingerprint

        return Cost(
            mode=self.mode,
            model=self.model,
            prompt_fingerprint=fingerprint(),
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            images_analyzed=self.images_analyzed,
            audio_seconds_processed=round(self.audio_seconds_processed, 3),
            video_seconds_processed=round(self.video_seconds_processed, 3),
            storage_bytes=self.storage_bytes,
            federal_lookups=self.federal_lookups,
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
            f"    video seconds       {self.video_seconds_processed:.1f}  (decoded locally)",
            f"    storage             {self.storage_bytes / 1_000_000:.1f} MB",
            f"    federal lookups     {self.federal_lookups}  (vPIC/NHTSA, no charge)",
            f"    model               {self.model or '-'}",
            f"    TOTAL               ${self.usd_total:.4f}",
            f"    {self.note()}",
        ]
        return "\n".join(lines)
