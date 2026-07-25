"""Pricing engine - the arithmetic, and the refusals."""

from __future__ import annotations

from tirekick_engines.engines.pricing import build_price_check, fit_mileage_slope
from tirekick_engines.models import BoundingBox, Comp, CostBand, Finding, ImageRegionEvidence


def comp(id_: str, price: float, mileage: int) -> Comp:
    return Comp(
        id=id_,
        source_note="pasted by the buyer",
        asking_price_usd=price,
        mileage=mileage,
        year=2013,
        trim="LX",
    )


def finding_with_cost(low: float, high: float) -> Finding:
    return Finding(
        id="f1",
        type="rust_corrosion",
        system="exterior",
        title="Corrosion on rocker panel",
        detail="d",
        severity="major",
        confidence=0.7,
        confidence_basis="b",
        evidence=[
            ImageRegionEvidence(
                asset_id="photo_01",
                box=BoundingBox(x=0.1, y=0.1, w=0.1, h=0.1),
                caption="c",
            )
        ],
        estimated_cost_usd=CostBand(low=low, high=high),
        engine="vision",
    )


def test_slope_is_fitted_from_the_buyers_own_comps() -> None:
    comps = [
        comp("a", 10200, 98500),
        comp("b", 9400, 112300),
        comp("c", 8100, 134800),
        comp("d", 7300, 151000),
    ]
    fit = fit_mileage_slope(comps)
    assert fit.usable
    assert fit.slope is not None and fit.slope < 0
    assert "fitted from the 4 comparable listings" in fit.reason


def test_too_few_comps_means_no_adjustment_and_says_so() -> None:
    fit = fit_mileage_slope([comp("a", 9000, 100000), comp("b", 8000, 130000)])
    assert not fit.usable
    assert "at least 3" in fit.reason
    assert "unadjusted" in fit.reason


def test_narrow_mileage_spread_means_no_adjustment() -> None:
    comps = [comp("a", 9000, 100000), comp("b", 8900, 102000), comp("c", 9100, 101000)]
    fit = fit_mileage_slope(comps)
    assert not fit.usable
    assert "too narrow" in fit.reason


def test_a_backwards_fit_is_refused_rather_than_applied() -> None:
    """Price rising with mileage means something else drives the spread. Say so."""
    comps = [
        comp("a", 7000, 90000),
        comp("b", 9000, 120000),
        comp("c", 11000, 160000),
    ]
    fit = fit_mileage_slope(comps)
    assert not fit.usable
    assert "price rises with mileage" in fit.reason


def test_no_comps_means_no_price_section_at_all() -> None:
    """LAW 1 - never a price verdict without the comps behind it."""
    assert (
        build_price_check(asking_price_usd=9000, comps=[], subject_mileage=120000, findings=[])
        is None
    )


def test_no_asking_price_means_no_price_section() -> None:
    assert (
        build_price_check(
            asking_price_usd=None,
            comps=[comp("a", 9000, 100000)],
            subject_mileage=120000,
            findings=[],
        )
        is None
    )


def test_deductions_come_only_from_findings_with_a_cost_band() -> None:
    costed = finding_with_cost(600, 900)
    uncosted = finding_with_cost(0, 0).model_copy(
        update={"id": "f2", "estimated_cost_usd": None}
    )

    check = build_price_check(
        asking_price_usd=9000,
        comps=[comp("a", 10200, 98500), comp("b", 9400, 112300), comp("c", 8100, 134800)],
        subject_mileage=120000,
        findings=[costed, uncosted],
    )
    assert check is not None
    assert [d.finding_id for d in check.deductions] == ["f1"]


def test_deductions_move_the_range_down() -> None:
    comps = [comp("a", 10200, 98500), comp("b", 9400, 112300), comp("c", 8100, 134800)]
    without = build_price_check(
        asking_price_usd=9000, comps=comps, subject_mileage=120000, findings=[]
    )
    with_deduction = build_price_check(
        asking_price_usd=9000,
        comps=comps,
        subject_mileage=120000,
        findings=[finding_with_cost(600, 900)],
    )
    assert without is not None and with_deduction is not None
    assert with_deduction.fair_range_usd.high < without.fair_range_usd.high
    assert with_deduction.fair_range_usd.low < without.fair_range_usd.low


def test_below_range_is_not_reported_as_a_good_deal() -> None:
    comps = [comp("a", 10200, 98500), comp("b", 9400, 112300), comp("c", 8100, 134800)]
    check = build_price_check(
        asking_price_usd=3000, comps=comps, subject_mileage=120000, findings=[]
    )
    assert check is not None
    assert check.verdict == "below_range"
    assert "not automatically a good deal" in check.verdict_statement


def test_notes_say_these_are_asking_prices() -> None:
    check = build_price_check(
        asking_price_usd=9000,
        comps=[comp("a", 10200, 98500), comp("b", 9400, 112300), comp("c", 8100, 134800)],
        subject_mileage=120000,
        findings=[],
    )
    assert check is not None
    assert "Asking prices, not sale prices" in check.normalization_notes
    assert "has not been verified" in check.normalization_notes
