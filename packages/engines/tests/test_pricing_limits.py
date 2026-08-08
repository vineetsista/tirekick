"""What the pricing engine does when it should not answer.

The arithmetic was covered in P0. This file is about the cases where doing the
arithmetic correctly would still produce a wrong answer: too few listings, the
wrong car, a market that has moved, and listings that disagree with each other.

The failure being guarded against is not a crash. It is a confident dollar range,
formatted identically whether it came from twenty relevant listings or from two
for a different model.
"""

from __future__ import annotations

import pytest

from tirekick_engines.engines import pricing
from tirekick_engines.models import (
    BoundingBox,
    Comp,
    CostBand,
    DecodedVehicle,
    Finding,
    ImageRegionEvidence,
)

ACCORD = DecodedVehicle(year=2013, make="HONDA", model="Accord")


def _finding_costing(low: float, high: float) -> Finding:
    """A finding carrying a sourced repair band, which is the only kind that
    produces a deduction (D-024)."""
    return Finding(
        id="wreck",
        type="rust_corrosion",
        system="exterior",
        title="Structural corrosion through the rocker",
        detail="Corrosion has opened the rocker panel along its length.",
        severity="critical",
        confidence=0.8,
        confidence_basis="well-lit, unobstructed region",
        evidence=[
            ImageRegionEvidence(
                asset_id="photo_01",
                box=BoundingBox(x=0.1, y=0.1, w=0.2, h=0.2),
                caption="rocker panel",
            )
        ],
        estimated_cost_usd=CostBand(low=low, high=high),
        engine="vision",
    )


def comp(
    id_: str = "c1",
    price: float = 9000,
    mileage: int = 100_000,
    year: int = 2013,
    make: str | None = "Honda",
    model: str | None = "Accord",
    listed_on: str = "",
) -> Comp:
    return Comp(
        id=id_,
        source_note="pasted by the buyer",
        asking_price_usd=price,
        mileage=mileage,
        year=year,
        make=make,
        model=model,
        listed_on=listed_on,
    )


def three_good() -> list[Comp]:
    return [
        comp("c1", 9400, 112_000),
        comp("c2", 8100, 134_000),
        comp("c3", 10200, 98_000),
    ]


def check(comps: list[Comp], **kwargs):  # type: ignore[no-untyped-def]
    return pricing.build_price_check(
        asking_price_usd=kwargs.pop("asking", 8900),
        comps=comps,
        subject_mileage=kwargs.pop("mileage", 128_540),
        findings=[],
        decoded=kwargs.pop("decoded", ACCORD),
        as_of=kwargs.pop("as_of", "2026-07-27T00:00:00Z"),
    )


# --------------------------------------------------------------------------- #
# too few                                                                      #
# --------------------------------------------------------------------------- #


def test_two_listings_produce_no_verdict() -> None:
    """Two listings are an anecdote, and a range built from two numbers looks
    exactly like a range built from twenty."""
    result = check(three_good()[:2])
    assert result is not None
    assert result.verdict == "cannot_determine"
    assert result.fair_range_usd.low == 0.0
    assert result.fair_range_usd.high == 0.0
    assert "not going to price this car on that" in result.verdict_statement


def test_the_listings_are_still_shown_when_there_is_no_verdict() -> None:
    """They are the buyer's own research. Declining to price them is not a
    reason to hide them."""
    result = check(three_good()[:2])
    assert result is not None
    assert len(result.comps) == 2


def test_no_comps_at_all_produces_no_price_section() -> None:
    """LAW 1. Not a hedged section - no section."""
    assert check([]) is None


def test_no_asking_price_produces_no_price_section() -> None:
    assert check(three_good(), asking=None) is None


# --------------------------------------------------------------------------- #
# the wrong car                                                                #
# --------------------------------------------------------------------------- #


def test_a_listing_for_another_model_is_excluded_and_the_reason_is_rendered() -> None:
    comps = [*three_good(), comp("c4", 9000, 100_000, model="Civic")]
    result = check(comps)
    assert result is not None

    excluded = {e.comp_id: e.reason for e in result.excluded}
    assert "c4" in excluded
    assert "Civic" in excluded["c4"]
    # Shown, not silently dropped - a hidden exclusion is a comp the buyer
    # believes was counted.
    assert any(c.id == "c4" for c in result.comps)
    assert "left out of the range" in result.normalization_notes


def test_a_listing_for_another_make_is_excluded() -> None:
    comps = [*three_good(), comp("c4", 9000, 100_000, make="Toyota", model="Accord")]
    result = check(comps)
    assert result is not None
    assert any(e.comp_id == "c4" and "Toyota" in e.reason for e in result.excluded)


def test_a_listing_too_many_years_away_is_excluded() -> None:
    comps = [*three_good(), comp("c4", 9000, 100_000, year=2008)]
    result = check(comps)
    assert result is not None
    assert any(e.comp_id == "c4" and "2008" in e.reason for e in result.excluded)


def test_a_nearby_model_year_is_kept() -> None:
    """Two years spans most facelifts. Excluding them would leave nothing."""
    comps = [*three_good(), comp("c4", 9600, 105_000, year=2015)]
    result = check(comps)
    assert result is not None
    assert not result.excluded


def test_an_abbreviated_model_name_is_not_a_mismatch() -> None:
    """Same reasoning as the VIN check in data.py - crying wolf on every truck
    listing trains buyers to ignore the one time it matters."""
    silverado = DecodedVehicle(year=2015, make="CHEVROLET", model="Silverado")
    comps = [
        comp("c1", 24000, 90_000, year=2015, make="Chevrolet", model="Silverado 1500"),
        comp("c2", 22000, 110_000, year=2015, make="Chevrolet", model="Silverado 1500"),
        comp("c3", 26000, 70_000, year=2015, make="Chevrolet", model="Silverado 1500"),
    ]
    result = check(comps, decoded=silverado, asking=23000, mileage=95_000)
    assert result is not None
    assert not result.excluded


def test_every_listing_for_the_wrong_car_means_no_verdict() -> None:
    comps = [comp(f"c{i}", 9000, 100_000, model="Civic") for i in range(1, 5)]
    result = check(comps)
    assert result is not None
    assert result.verdict == "cannot_determine"
    assert "None of the 4 listing(s)" in result.verdict_statement
    assert len(result.excluded) == 4


def test_relevance_is_not_checked_when_the_vin_did_not_decode() -> None:
    """No decode means no basis to exclude on. Excluding on a guess would be
    worse than not excluding."""
    comps = [*three_good(), comp("c4", 9000, 100_000, model="Civic")]
    result = check(comps, decoded=None)
    assert result is not None
    assert not result.excluded


# --------------------------------------------------------------------------- #
# a market that moved                                                          #
# --------------------------------------------------------------------------- #


def test_stale_listings_are_flagged_and_still_counted() -> None:
    comps = [
        comp("c1", 9400, 112_000, listed_on="2026-01-02"),
        comp("c2", 8100, 134_000, listed_on="2026-07-20"),
        comp("c3", 10200, 98_000, listed_on="2026-07-22"),
    ]
    result = check(comps)
    assert result is not None
    assert result.verdict != "cannot_determine"
    assert "more than 90 days old" in result.normalization_notes


def test_undated_listings_say_so_rather_than_assuming_they_are_fresh() -> None:
    result = check(three_good())
    assert result is not None
    assert "carry no dates" in result.normalization_notes


def test_recent_listings_produce_no_staleness_note() -> None:
    comps = [
        comp("c1", 9400, 112_000, listed_on="2026-07-20"),
        comp("c2", 8100, 134_000, listed_on="2026-07-21"),
        comp("c3", 10200, 98_000, listed_on="2026-07-22"),
    ]
    result = check(comps)
    assert result is not None
    assert "days old" not in result.normalization_notes


# --------------------------------------------------------------------------- #
# listings that disagree                                                       #
# --------------------------------------------------------------------------- #


def test_a_wide_spread_is_called_out_as_a_problem_with_the_comps() -> None:
    """A range that wide is telling you the listings are not comparable, not
    that the car is worth anything inside it.

    Note the prices deliberately do NOT track mileage here. When a wide spread
    IS explained by mileage the fit absorbs it and the note correctly stays
    quiet - which is the behaviour the sibling test below pins.
    """
    comps = [
        comp("c1", 6000, 120_000),
        comp("c2", 14000, 125_000),
        comp("c3", 9000, 130_000),
    ]
    result = check(comps)
    assert result is not None
    assert "disagree with each other" in result.normalization_notes


def test_a_spread_that_mileage_explains_is_not_called_a_disagreement() -> None:
    """$6k to $14k looks alarming until you notice the cheap one has done
    150,000 more miles. The fit absorbs it and the range comes out tight."""
    comps = [
        comp("c1", 6000, 250_000),
        comp("c2", 9000, 150_000),
        comp("c3", 14000, 50_000),
    ]
    result = check(comps)
    assert result is not None
    assert "disagree with each other" not in result.normalization_notes
    assert result.fair_range_usd.high - result.fair_range_usd.low < 2000


def test_a_tight_spread_produces_no_such_note() -> None:
    comps = [
        comp("c1", 9000, 130_000),
        comp("c2", 9400, 118_000),
        comp("c3", 9800, 108_000),
    ]
    result = check(comps)
    assert result is not None
    assert "disagree with each other" not in result.normalization_notes


# --------------------------------------------------------------------------- #
# things that were already true, held in place                                 #
# --------------------------------------------------------------------------- #


def test_no_deductions_says_so_rather_than_staying_silent() -> None:
    """D-024 removed model-invented cost bands, so live reports have none. An
    unexplained absence reads as 'nothing needs fixing'."""
    result = check(three_good())
    assert result is not None
    assert not result.deductions
    assert "does not invent cost bands" in result.normalization_notes


def test_the_mileage_slope_is_still_fitted_not_assumed() -> None:
    result = check(three_good())
    assert result is not None
    assert "fitted from the" in result.normalization_notes
    assert "rather than from any assumed" in result.normalization_notes


def test_asking_prices_are_never_called_sale_prices() -> None:
    result = check(three_good())
    assert result is not None
    assert "Asking prices, not sale prices" in result.normalization_notes


@pytest.mark.parametrize("position", ["below", "inside", "above"])
def test_the_verdict_still_tracks_the_range(position: str) -> None:
    """Computed against the range the engine produced, not against a number
    hardcoded here - mileage normalisation moves the range, and a literal would
    pin the test to today's arithmetic rather than to the behaviour."""
    baseline = check(three_good())
    assert baseline is not None
    low, high = baseline.fair_range_usd.low, baseline.fair_range_usd.high

    asking = {"below": low - 2000, "inside": (low + high) / 2, "above": high + 2000}[position]
    expected = {"below": "below_range", "inside": "in_range", "above": "above_range"}[position]

    result = check(three_good(), asking=asking)
    assert result is not None
    assert result.verdict == expected


# --------------------------------------------------------------------------- #
# a fitted line carried past the listings it was fitted to                      #
# --------------------------------------------------------------------------- #


def _straight_line_comps() -> list[Comp]:
    """A textbook fit: 50k/$20,000, 100k/$15,000, 150k/$10,000. Exactly -$0.10
    per mile, with nothing wrong with it inside the range it covers."""
    return [
        comp("c1", 20_000, 50_000),
        comp("c2", 15_000, 100_000),
        comp("c3", 10_000, 150_000),
    ]


def test_a_high_mileage_car_is_not_priced_by_extrapolation() -> None:
    """The $0-$0 range, reproduced.

    Three clean listings, a clean fit, and an ordinary 260,000-mile car. The
    slope was applied over 110,000 miles of road nobody listed, every normalized
    price came out negative, `max(0.0, ...)` quietly turned them into zero, and
    the report told the buyer their $6,000 car was above the $0-$0 range these
    listings support - then handed them a sentence to say out loud about it.
    """
    result = check(_straight_line_comps(), mileage=260_000, asking=6_000)
    assert result is not None
    assert result.verdict == "cannot_determine"
    assert "$0" not in result.verdict_statement
    assert "260,000" in result.verdict_statement
    assert "50,000 to 150,000 miles" in result.verdict_statement
    assert result.fair_range_usd.high == 0.0


def test_the_extrapolation_limit_is_a_declared_fraction_of_the_comps_own_span() -> None:
    """The line may be carried a quarter of its own span past the data, and not
    one mile further. Both sides of that boundary, so the constant is pinned by
    behaviour rather than by being read back out of the module."""
    span = 100_000  # 50,000 to 150,000
    reach = int(150_000 + span * pricing.MAX_EXTRAPOLATION_FRACTION)

    inside = check(_straight_line_comps(), mileage=reach, asking=7_500)
    assert inside is not None
    assert inside.verdict != "cannot_determine"

    outside = check(_straight_line_comps(), mileage=reach + 1, asking=7_500)
    assert outside is not None
    assert outside.verdict == "cannot_determine"


def test_a_car_far_below_the_listings_is_refused_the_same_way() -> None:
    """The low side hurts differently and just as much: extrapolating upward
    inflates the range and makes an overpriced car look fair."""
    result = check(_straight_line_comps(), mileage=20_000, asking=30_000)
    assert result is not None
    assert result.verdict == "cannot_determine"


def test_a_subject_inside_the_listings_is_still_adjusted() -> None:
    """The guard is about distance, not about mileage adjustment. If it silences
    the ordinary case it has replaced one wrong answer with another."""
    result = check(_straight_line_comps(), mileage=120_000, asking=13_000)
    assert result is not None
    assert result.verdict == "in_range"
    assert "fitted from the" in result.normalization_notes


def test_the_listings_are_still_shown_when_the_car_is_out_of_range() -> None:
    """LAW 1 again. Declining to price the buyer's research is not a reason to
    hide it, and a silent drop is the failure that costs them the car."""
    result = check(_straight_line_comps(), mileage=260_000, asking=6_000)
    assert result is not None
    assert len(result.comps) == 3
    assert "unadjusted" in result.normalization_notes


def test_a_negative_normalized_price_is_never_rendered_as_zero_dollars() -> None:
    """The second guard, for the case the first one lets through.

    These listings sit 50k apart and $19,000 apart - a slope of -$0.19/mile that
    is steep enough to price the dearest listing below zero only 25,000 miles
    past the last one, which the distance guard permits. A price below zero is
    not a cheap car, it is arithmetic that has stopped describing anything, and
    it must not arrive at the buyer wearing a `$0` and a verdict.
    """
    comps = [
        comp("c1", 20_000, 50_000),
        comp("c2", 12_000, 100_000),
        comp("c3", 1_000, 150_000),
    ]
    result = check(comps, mileage=175_000, asking=6_000)
    assert result is not None
    assert result.verdict == "cannot_determine"
    assert "below zero" in result.verdict_statement


def test_listings_pasted_in_at_zero_dollars_produce_no_range() -> None:
    """Found by mutating the guard above, not by design.

    With the below-zero guard switched off, three $0 listings reached the
    deduction check and came back as "the repairs found on this car - $0 to $0 -
    come to more than these listings say the whole car is worth", which is
    gibberish attached to a real recommendation. $0 listings are a paste error,
    and a paste error is not a valuation.
    """
    comps = [comp("c1", 0, 100_000), comp("c2", 0, 110_000), comp("c3", 0, 120_000)]
    result = check(comps, asking=6_000)
    assert result is not None
    assert result.verdict == "cannot_determine"
    assert "repairs found on this car" not in result.verdict_statement
    assert "at or below zero dollars" in result.verdict_statement


def test_repairs_worth_more_than_the_car_are_not_reported_as_a_zero_range() -> None:
    """The same $0-$0 sentence, reached by a second route, found while fixing the
    first one.

    Bounding the mileage extrapolation does nothing about deductions: a $9,500
    car with $12,000-$15,000 of sourced repair bands hits `max(0.0, ...)` at the
    other end of the function and produces the identical report - "above the
    $0-$0 range these comparable listings support. The gap is $6,000." The number
    is meaningless and the verdict beside it is confident.

    Refusing here is not silence. The refusal carries the finding that matters,
    which is that the repairs cost more than a comparable car does.
    """
    comps = [
        comp("c1", 10_000, 100_000),
        comp("c2", 9_500, 110_000),
        comp("c3", 9_000, 120_000),
    ]
    wreck = _finding_costing(12_000, 15_000)
    result = pricing.build_price_check(
        asking_price_usd=6_000,
        comps=comps,
        subject_mileage=115_000,
        findings=[wreck],
        decoded=None,
        as_of="2026-07-27T00:00:00Z",
    )
    assert result is not None
    assert result.verdict == "cannot_determine"
    assert "$0" not in result.verdict_statement
    assert "more than these listings say the whole car is worth" in result.verdict_statement
    # The deductions are the point of the refusal, so they are still rendered.
    assert [d.finding_id for d in result.deductions] == ["wreck"]


def test_a_listing_dated_after_the_report_is_called_out() -> None:
    """Found by the fixture, not by design.

    Fixture mode freezes its clock at 2026-01-01 (D-011), so comps dated later
    that year were silently treated as fresh - negative age passes any
    "older than 90 days" test. A future-dated listing is a paste error and the
    report should say so rather than scoring it as the most current comp.
    """
    comps = [
        comp("c1", 9400, 112_000, listed_on="2030-01-01"),
        comp("c2", 8100, 134_000, listed_on="2026-07-20"),
        comp("c3", 10200, 98_000, listed_on="2026-07-22"),
    ]
    result = check(comps)
    assert result is not None
    assert "after this report was generated" in result.normalization_notes
