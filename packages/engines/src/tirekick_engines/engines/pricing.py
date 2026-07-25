"""Pricing engine - v1.

Scope, deliberately narrow: the buyer pastes in 3-6 comparable listings (LAW 3 -
never harvested), and this engine normalizes them and produces a range. Automated
comps are a locked later phase.

The honesty problem this engine has to solve: a mileage adjustment needs a
dollars-per-mile figure, and the obvious move is to hardcode one. A hardcoded
constant is a number we made up, applied to someone's six-thousand-dollar
decision. So instead the slope is **fitted from the buyer's own comps**, and when
the comps cannot support a fit - too few, or no spread in mileage, or a fit that
comes out the wrong way round - the engine does not adjust and says so. An
unadjusted range with a stated reason beats an adjusted range built on an invented
constant.

Deductions come only from findings that carry a sourced cost band. A finding with
no cost band produces no deduction, however alarming it is.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import Comp, Finding, PriceCheck, PriceDeduction, PriceRange

#: Minimum comps before a mileage fit is attempted at all.
MIN_COMPS_FOR_FIT = 3

#: Minimum spread in miles across comps for a fit to mean anything.
MIN_MILEAGE_SPREAD = 10_000


@dataclass(frozen=True)
class MileageFit:
    #: USD per mile. Negative when the fit behaves the way used cars do.
    slope: float | None
    reason: str

    @property
    def usable(self) -> bool:
        return self.slope is not None


def fit_mileage_slope(comps: list[Comp]) -> MileageFit:
    """Least-squares price-on-mileage slope, or a stated reason there isn't one."""
    if len(comps) < MIN_COMPS_FOR_FIT:
        return MileageFit(
            None,
            f"Only {len(comps)} comparable listing(s) provided; at least "
            f"{MIN_COMPS_FOR_FIT} are needed before mileage can be adjusted for. "
            f"Prices below are as-listed, unadjusted.",
        )

    mileages = [float(c.mileage) for c in comps]
    prices = [float(c.asking_price_usd) for c in comps]
    spread = max(mileages) - min(mileages)
    if spread < MIN_MILEAGE_SPREAD:
        return MileageFit(
            None,
            f"The comparable listings span only {spread:,.0f} miles, too narrow to "
            f"estimate a per-mile adjustment from. Prices below are as-listed, "
            f"unadjusted.",
        )

    n = len(comps)
    mean_m = sum(mileages) / n
    mean_p = sum(prices) / n
    numerator = sum((m - mean_m) * (p - mean_p) for m, p in zip(mileages, prices, strict=True))
    denominator = sum((m - mean_m) ** 2 for m in mileages)
    if denominator == 0:
        return MileageFit(None, "Comparable listings have no mileage variation to fit.")

    slope = numerator / denominator
    if slope >= 0:
        return MileageFit(
            None,
            f"In these comparable listings, price rises with mileage "
            f"(${slope:+.3f}/mile), which means something other than mileage is "
            f"driving the spread - trim, condition, or how they were chosen. No "
            f"mileage adjustment has been applied.",
        )

    return MileageFit(
        slope,
        f"Mileage adjustment of ${slope:.3f} per mile, fitted from the "
        f"{n} comparable listings provided rather than from any assumed "
        f"depreciation rate.",
    )


def _normalized_prices(
    comps: list[Comp], subject_mileage: int | None, fit: MileageFit
) -> list[float]:
    if fit.slope is None or subject_mileage is None:
        return [float(c.asking_price_usd) for c in comps]
    return [
        float(c.asking_price_usd) + fit.slope * (subject_mileage - c.mileage) for c in comps
    ]


def build_price_check(
    *,
    asking_price_usd: float | None,
    comps: list[Comp],
    subject_mileage: int | None,
    findings: list[Finding],
) -> PriceCheck | None:
    """Returns None when there is nothing honest to say.

    LAW 1: no price verdict is ever produced without comps to show behind it, so
    an empty comp list yields no price section at all rather than a hedged one.
    """
    if asking_price_usd is None or not comps:
        return None

    fit = fit_mileage_slope(comps)
    normalized = _normalized_prices(comps, subject_mileage, fit)
    low, high = min(normalized), max(normalized)

    deductions = [
        PriceDeduction(
            finding_id=f.id,
            label=f.title,
            low_usd=f.estimated_cost_usd.low,
            high_usd=f.estimated_cost_usd.high,
            basis=(
                f"Repair cost band attached to this finding. Confidence in the "
                f"finding itself is {f.confidence:.2f}."
            ),
        )
        for f in findings
        if f.estimated_cost_usd is not None
    ]

    deduct_low = sum(d.low_usd for d in deductions)
    deduct_high = sum(d.high_usd for d in deductions)

    # Comps describe a car without this car's findings; the deductions move the
    # range down. High deductions pair with the low end of the range.
    adjusted_low = max(0.0, low - deduct_high)
    adjusted_high = max(0.0, high - deduct_low)
    if adjusted_low > adjusted_high:
        adjusted_low, adjusted_high = adjusted_high, adjusted_low

    if asking_price_usd < adjusted_low:
        verdict = "below_range"
        verdict_statement = (
            f"The asking price of ${asking_price_usd:,.0f} is below the "
            f"${adjusted_low:,.0f}-${adjusted_high:,.0f} range these comparable "
            f"listings support after the deductions above. A price below the "
            f"range is not automatically a good deal - ask why it is priced there."
        )
    elif asking_price_usd > adjusted_high:
        verdict = "above_range"
        verdict_statement = (
            f"The asking price of ${asking_price_usd:,.0f} is above the "
            f"${adjusted_low:,.0f}-${adjusted_high:,.0f} range these comparable "
            f"listings support after the deductions above. The gap is "
            f"${asking_price_usd - adjusted_high:,.0f}."
        )
    else:
        verdict = "in_range"
        verdict_statement = (
            f"The asking price of ${asking_price_usd:,.0f} falls within the "
            f"${adjusted_low:,.0f}-${adjusted_high:,.0f} range these comparable "
            f"listings support after the deductions above."
        )

    notes = [
        fit.reason,
        f"Range built from {len(comps)} listing(s) you provided. It reflects those "
        f"listings and nothing else - not a market index, not an appraisal.",
        "Asking prices, not sale prices. What a car is listed at and what it sells "
        "for are different numbers, and the second one is not public.",
    ]
    if subject_mileage is not None:
        notes.append(
            f"Subject mileage of {subject_mileage:,} is as stated by the seller "
            f"and has not been verified."
        )

    return PriceCheck(
        asking_price_usd=asking_price_usd,
        comps=comps,
        normalization_notes=" ".join(notes),
        fair_range_usd=PriceRange(low=round(adjusted_low, 2), high=round(adjusted_high, 2)),
        deductions=deductions,
        verdict=verdict,  # type: ignore[arg-type]
        verdict_statement=verdict_statement,
    )
