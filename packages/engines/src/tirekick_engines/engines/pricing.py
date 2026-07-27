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
from datetime import date

from ..models import (
    Comp,
    DecodedVehicle,
    ExcludedComp,
    Finding,
    PriceCheck,
    PriceDeduction,
    PriceRange,
)

#: Minimum comps before a mileage fit is attempted at all.
MIN_COMPS_FOR_FIT = 3

#: Minimum spread in miles across comps for a fit to mean anything.
MIN_MILEAGE_SPREAD = 10_000

#: Fewest usable comps before a verdict is offered at all.
#:
#: Two listings are an anecdote. The engine will still show them - they are the
#: buyer's own research and worth rendering - but it returns `cannot_determine`
#: rather than a range, because a range built from two numbers looks exactly like
#: a range built from twenty.
MIN_COMPS_FOR_VERDICT = 3

#: How far a comp's model year may sit from the subject's before it stops being a
#: comparison. Two years spans most facelifts without excluding a whole generation.
MAX_YEAR_GAP = 2

#: A listing older than this describes a different market. Used-car prices moved
#: 20-40% inside single years recently, so this is not a formality.
STALE_COMP_DAYS = 90


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


def _relevance_problem(comp: Comp, decoded: DecodedVehicle | None) -> str | None:
    """Why this listing is not a comparison for this car, if it is not.

    Checked because nothing else would notice. A buyer who pastes three listings
    for the wrong model gets arithmetic performed on them either way, and the
    output is a confident range for a car that is not theirs.
    """
    if decoded is None:
        return None

    if decoded.year and abs(comp.year - decoded.year) > MAX_YEAR_GAP:
        return (
            f"listed as a {comp.year}; this vehicle is a {decoded.year}, and "
            f"more than {MAX_YEAR_GAP} model years apart is a different car"
        )

    if comp.make and decoded.make and comp.make.strip().upper() != decoded.make.upper():
        return f"listed as a {comp.make}; this vehicle is a {decoded.make}"

    if comp.model and decoded.model:
        claimed = comp.model.strip().upper()
        actual = decoded.model.upper()
        # Loose, for the same reason as the VIN mismatch check in data.py:
        # "Silverado 1500" against "Silverado" is not a disagreement.
        if claimed not in actual and actual not in claimed:
            return f"listed as a {comp.model}; this vehicle is a {decoded.model}"

    return None


def _staleness_note(comps: list[Comp], as_of: str) -> str | None:
    """Flag old listings without excluding them.

    Excluded would be too strong - an old comp is still a data point, and the
    buyer chose it. But a range built from spring listings priced against an
    autumn market is wrong in a way no amount of arithmetic reveals.
    """
    dated = [c for c in comps if c.listed_on]
    if not dated or not as_of:
        return (
            "The listings you provided carry no dates, so how current they are "
            "could not be checked. Used-car prices have moved by tens of percent "
            "inside a single year."
        )
    try:
        today = date.fromisoformat(as_of[:10])
        ages = [(today - date.fromisoformat(c.listed_on[:10])).days for c in dated]
    except ValueError:
        return None

    # A listing dated after the report is a typo or a paste error, and it would
    # otherwise sail through the staleness check as "very fresh".
    future = [age for age in ages if age < 0]
    if future:
        return (
            f"{len(future)} of {len(dated)} dated listing(s) carry a date after "
            f"this report was generated, which is not possible. Check the dates - "
            f"they were not used to judge how current the listings are."
        )

    stale = [age for age in ages if age > STALE_COMP_DAYS]
    if not stale:
        return None
    return (
        f"{len(stale)} of {len(dated)} dated listing(s) are more than "
        f"{STALE_COMP_DAYS} days old. They are still counted - they are your "
        f"research - but they describe an older market than the one you are "
        f"buying in."
    )


def _spread_note(prices: list[float]) -> str | None:
    """Say when the comps disagree with each other more than they agree.

    The range is the observed spread of a handful of listings, not a confidence
    interval, and with a wide spread that distinction stops being pedantic.
    """
    if len(prices) < 2:
        return None
    low, high = min(prices), max(prices)
    midpoint = (low + high) / 2
    if midpoint <= 0:
        return None
    if (high - low) / midpoint < 0.4:
        return None
    return (
        f"These listings disagree with each other by ${high - low:,.0f} - the "
        f"cheapest is {(1 - low / high) * 100:.0f}% below the dearest. A range "
        f"that wide is telling you the listings are not really comparable, not "
        f"that the car is worth anything in it."
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
    decoded: DecodedVehicle | None = None,
    as_of: str = "",
) -> PriceCheck | None:
    """Returns None when there is nothing honest to say, and `cannot_determine`
    when there is something to show but no verdict to attach to it.

    LAW 1: no price verdict is ever produced without comps to show behind it, so
    an empty comp list yields no price section at all rather than a hedged one.
    """
    if asking_price_usd is None or not comps:
        return None

    # Listings for a different car are dropped, and the drop is rendered. A comp
    # silently excluded is a comp the buyer believes was counted.
    usable: list[Comp] = []
    excluded: list[ExcludedComp] = []
    for comp in comps:
        problem = _relevance_problem(comp, decoded)
        if problem is None:
            usable.append(comp)
        else:
            excluded.append(ExcludedComp(comp_id=comp.id, reason=problem))

    notes: list[str] = []
    stale = _staleness_note(usable or comps, as_of)

    if len(usable) < MIN_COMPS_FOR_VERDICT:
        # Everything is still shown. There is simply no number attached to it.
        if excluded and not usable:
            why = (
                f"None of the {len(comps)} listing(s) you provided is a comparison "
                f"for this vehicle - see the exclusions above."
            )
        elif excluded:
            why = (
                f"{len(usable)} of the {len(comps)} listing(s) you provided compare "
                f"to this vehicle; the rest are for different cars."
            )
        else:
            why = f"{len(usable)} comparable listing(s) is not enough to price against."

        return PriceCheck(
            asking_price_usd=asking_price_usd,
            comps=comps,
            excluded=excluded,
            normalization_notes=" ".join(
                filter(
                    None,
                    [
                        f"A price range needs at least {MIN_COMPS_FOR_VERDICT} "
                        f"comparable listings. Two listings are an anecdote, and a "
                        f"range built from two numbers looks exactly like a range "
                        f"built from twenty.",
                        stale,
                    ],
                )
            ),
            fair_range_usd=PriceRange(low=0.0, high=0.0),
            deductions=[],
            verdict="cannot_determine",
            verdict_statement=(
                f"{why} TIREKICK is not going to price this car on that. Find two "
                f"or three more listings for the same year, make and model, and "
                f"the range will mean something."
            ),
        )

    fit = fit_mileage_slope(usable)
    normalized = _normalized_prices(usable, subject_mileage, fit)
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
        f"Range built from {len(usable)} listing(s) you provided. It reflects those "
        f"listings and nothing else - not a market index, not an appraisal.",
        "Asking prices, not sale prices. What a car is listed at and what it sells "
        "for are different numbers, and the second one is not public.",
    ]
    if excluded:
        notes.append(
            f"{len(excluded)} listing(s) you provided were left out of the range as "
            f"comparisons for a different vehicle. They are listed above with the "
            f"reason."
        )
    spread = _spread_note(normalized)
    if spread:
        notes.append(spread)
    if stale:
        notes.append(stale)
    if subject_mileage is not None:
        notes.append(
            f"Subject mileage of {subject_mileage:,} is as stated by the seller "
            f"and has not been verified."
        )
    if not deductions:
        notes.append(
            "No repair costs were deducted. TIREKICK does not invent cost bands, "
            "and none of the findings on this vehicle carries a sourced one."
        )

    return PriceCheck(
        asking_price_usd=asking_price_usd,
        comps=comps,
        excluded=excluded,
        normalization_notes=" ".join(notes),
        fair_range_usd=PriceRange(low=round(adjusted_low, 2), high=round(adjusted_high, 2)),
        deductions=deductions,
        verdict=verdict,  # type: ignore[arg-type]
        verdict_statement=verdict_statement,
    )
