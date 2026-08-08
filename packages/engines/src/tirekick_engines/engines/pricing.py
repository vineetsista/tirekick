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

#: How far past the ends of the comps' own mileage range the fitted line may be
#: carried, as a fraction of the range it was fitted over.
#:
#: WHY A QUARTER, AND NOT SOME OTHER NUMBER
#:
#: A least-squares line through three to six listings is evidence about the
#: stretch of road those listings cover and nothing else. Past the last one it is
#: an assumption wearing the same units. At a quarter of the span, four fifths of
#: the mileage under the answer was actually observed - 100,000 miles of listings
#: carry the line to 125,000 miles of reasoning - so at most one mile in five is
#: invented. That is the most invented distance worth putting behind a dollar
#: figure someone repeats to a seller.
#:
#: It composes with MIN_MILEAGE_SPREAD rather than fighting it: a fit needs
#: 10,000 miles of spread before it exists at all, so the allowance is never
#: tighter than 2,500 miles and this never refuses a car that merely sits a
#: little outside the pack. It is also symmetric. A low-mileage subject
#: extrapolated upward inflates the range and makes an overpriced car look fair,
#: which is quieter than the $0 range and no less wrong.
MAX_EXTRAPOLATION_FRACTION = 0.25

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


def _extrapolation_distance(comps: list[Comp], subject_mileage: int) -> tuple[int, int, int]:
    """(nearest, furthest, how far outside) for the comps' mileage range.

    Zero when the subject sits between them, which is the case the fit was built
    for and the only case it is evidence about.
    """
    low = min(c.mileage for c in comps)
    high = max(c.mileage for c in comps)
    if subject_mileage < low:
        return low, high, low - subject_mileage
    if subject_mileage > high:
        return low, high, subject_mileage - high
    return low, high, 0


def _extrapolation_refusal(comps: list[Comp], subject_mileage: int) -> str | None:
    """Why this car cannot be priced off these listings, when it cannot.

    THE REPORT THIS PREVENTS
    ------------------------
    Comps at 50k/$20,000, 100k/$15,000 and 150k/$10,000 - a clean -$0.10 per mile
    fit with nothing wrong with it - and a 260,000-mile car, which is an ordinary
    used car and not an edge case. The slope was applied over 110,000 miles that
    no listing covered, every normalized price came out below zero,
    `max(0.0, ...)` turned that into $0, and the buyer was told their $6,000 car
    was "above the $0-$0 range these comparable listings support", with a
    negotiation line to say out loud. Nothing in the arithmetic noticed, because
    `fit_mileage_slope` guards the spread *between* the comps and nothing guarded
    the distance *from* them.

    The refusal is worded like the fit's other refusals on purpose. This engine
    already knows how to decline (D-032); it should not learn a second dialect
    for it.
    """
    low, high, distance = _extrapolation_distance(comps, subject_mileage)
    span = high - low
    allowance = span * MAX_EXTRAPOLATION_FRACTION
    if distance <= allowance:
        return None

    side = "below" if subject_mileage < low else "above"
    return (
        f"The listings you provided run from {low:,} to {high:,} miles, and this "
        f"car is stated at {subject_mileage:,} - {distance:,} miles {side} any of "
        f"them, further than the {MAX_EXTRAPOLATION_FRACTION:.0%} of their own "
        f"{span:,}-mile span TIREKICK will carry a fitted line past the listings "
        f"it came from. Carried that far the adjustment stops being a measurement "
        f"of these listings and becomes an assumption about a stretch of road none "
        f"of them covers; carried far enough it prices cars below zero. Find "
        f"listings nearer this car's mileage and the range will mean something."
    )


def _below_zero_refusal(normalized: list[float]) -> str | None:
    """The second guard, for what the first one lets through.

    A steep enough slope reaches below zero inside the extrapolation allowance -
    listings $19,000 apart over 50,000 miles do it in 25,000 more. Whatever the
    distance, a normalized price below zero is not a cheap car, it is arithmetic
    that has stopped describing anything, and the old code met it with
    `max(0.0, ...)`: the number was corrected and the fact was not reported.

    A ceiling of exactly zero is caught here too, and not because the fit did it.
    Three listings pasted in at $0 - a paste error, or free-car listings - give a
    range of $0-$0 with no adjustment involved at all, and everything downstream
    treats that as a priced car.
    """
    if min(normalized) >= 0 and max(normalized) > 0:
        return None
    return (
        "Priced against this car, at least one of these listings comes out at or "
        "below zero dollars, and zero is not a price. Whatever relationship these "
        "particular listings hold between price and mileage, it does not survive "
        "being carried to this car, so there is no range to report - a $0 floor "
        "here would be this engine hiding a broken calculation behind a round "
        "number."
    )


def _deductions_swallow_the_range(
    high: float, deduct_low: float, deduct_high: float
) -> str | None:
    """When the repairs cost more than the whole car, say that instead of $0.

    Found while fixing the mileage extrapolation, by reading the other end of the
    same function. `max(0.0, high - deduct_low)` is the identical silent clamp:
    a $9,500 car with $12,000-$15,000 of sourced repair bands comes out as
    "above the $0-$0 range these comparable listings support. The gap is $6,000."

    There is no honest range to publish here, but there is something well worth
    saying, and it is not a hedge - the numbers already on the page cost more
    than a comparable car does. Zeroing it and printing a verdict said that
    badly; saying nothing would have said it not at all (D-017).
    """
    # No deduction means nothing was swallowed, whatever the range looks like.
    # Without this the guard fires on a range that is already at zero for some
    # other reason and tells the buyer "the repairs found on this car - $0 to
    # $0 - come to more than the car is worth", which is not a sentence anyone
    # should read. `_below_zero_refusal` owns that case.
    if deduct_low <= 0 or high - deduct_low > 0:
        return None
    return (
        f"The repairs found on this car - ${deduct_low:,.0f} to "
        f"${deduct_high:,.0f}, from the cost bands listed above - come to more "
        f"than these listings say the whole car is worth. There is no range left "
        f"to price the asking price against, so TIREKICK is not printing one: the "
        f"arithmetic lands on nothing, and nothing is not a number to negotiate "
        f"from. Take the repair estimates to a shop before you go any further "
        f"with this car."
    )


def _no_verdict(
    *,
    asking_price_usd: float,
    comps: list[Comp],
    excluded: list[ExcludedComp],
    notes: list[str | None],
    statement: str,
    deductions: list[PriceDeduction] | None = None,
) -> PriceCheck:
    """The engine's one way of declining to price.

    Every refusal comes through here so they are indistinguishable to whatever
    renders them: the comps are still shown, because they are the buyer's own
    research and declining to price them is not a reason to hide them, and the
    range is zeroed rather than guessed at. It is a single path so that a new
    refusal cannot accidentally ship a `cannot_determine` verdict beside a
    plausible-looking range.
    """
    return PriceCheck(
        asking_price_usd=asking_price_usd,
        comps=comps,
        excluded=excluded,
        normalization_notes=" ".join(filter(None, notes)),
        fair_range_usd=PriceRange(low=0.0, high=0.0),
        deductions=deductions or [],
        verdict="cannot_determine",
        verdict_statement=statement,
    )


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

        return _no_verdict(
            asking_price_usd=asking_price_usd,
            comps=comps,
            excluded=excluded,
            notes=[
                f"A price range needs at least {MIN_COMPS_FOR_VERDICT} "
                f"comparable listings. Two listings are an anecdote, and a "
                f"range built from two numbers looks exactly like a range "
                f"built from twenty.",
                stale,
            ],
            statement=(
                f"{why} TIREKICK is not going to price this car on that. Find two "
                f"or three more listings for the same year, make and model, and "
                f"the range will mean something."
            ),
        )

    fit = fit_mileage_slope(usable)

    # Only when a slope is about to be applied. With no fit there is no line to
    # carry anywhere - the listings go out as-listed with the fit's own reason
    # attached, and this guard has nothing to say about them.
    if fit.slope is not None and subject_mileage is not None:
        too_far = _extrapolation_refusal(usable, subject_mileage)
        if too_far is not None:
            return _no_verdict(
                asking_price_usd=asking_price_usd,
                comps=comps,
                excluded=excluded,
                notes=[
                    "No range was produced. The listings below are shown "
                    "as-listed and unadjusted; adjusting them to this car's "
                    "mileage would have meant extending a fitted line well past "
                    "the listings that produced it.",
                    stale,
                ],
                statement=too_far,
            )

    normalized = _normalized_prices(usable, subject_mileage, fit)

    below_zero = _below_zero_refusal(normalized)
    if below_zero is not None:
        return _no_verdict(
            asking_price_usd=asking_price_usd,
            comps=comps,
            excluded=excluded,
            notes=[
                "No range was produced. The listings below are shown as-listed "
                "and unadjusted.",
                stale,
            ],
            statement=below_zero,
        )

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

    swallowed = _deductions_swallow_the_range(high, deduct_low, deduct_high)
    if swallowed is not None:
        return _no_verdict(
            asking_price_usd=asking_price_usd,
            comps=comps,
            excluded=excluded,
            notes=[
                "No range was produced: the deductions below run past the bottom "
                "of what these listings support.",
                stale,
            ],
            statement=swallowed,
            deductions=deductions,
        )

    # Comps describe a car without this car's findings; the deductions move the
    # range down. High deductions pair with the low end of the range. The floor
    # can still land on $0 here - a car that is worth nothing once its repairs
    # are paid for is a real outcome, and the ceiling above it is what stops
    # that $0 from being the whole answer.
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

    # A fitted slope is only an adjustment if there is a mileage to adjust TO.
    # Without one, `_normalized_prices` returns the listings as-listed, and
    # printing "Mileage adjustment of $-0.123 per mile, fitted from..." told the
    # buyer arithmetic had been performed on a number they never supplied.
    mileage_note = (
        fit.reason
        if subject_mileage is not None
        else (
            "No mileage adjustment was applied: the seller's stated mileage for "
            "this car was not provided, so there is nothing to adjust the "
            "comparable listings toward. The range below is as-listed."
        )
    )
    notes = [
        mileage_note,
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
