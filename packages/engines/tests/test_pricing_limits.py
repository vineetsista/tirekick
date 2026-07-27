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
from tirekick_engines.models import Comp, DecodedVehicle

ACCORD = DecodedVehicle(year=2013, make="HONDA", model="Accord")


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
