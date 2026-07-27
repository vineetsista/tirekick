"""The free teaser, and the one test that matters.

`test_no_paid_content_survives_the_projection` reads the teaser JSON looking for
every sentence the paid report contains. If a refactor ever starts passing the
full report down the free route, that test fails on the text rather than on the
shape, which is the failure mode a type checker cannot see.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tirekick_engines.models import LOCKED_SYSTEM_STATEMENT, LOCKED_SYSTEMS
from tirekick_engines.pipeline import run_inspection
from tirekick_engines.registry import FINDING_TYPES
from tirekick_engines.teaser import accuracy_statement, build_teaser

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "fixtures" / "demo-01"
PRICE = 25.0


@pytest.fixture(scope="module")
def report():  # type: ignore[no-untyped-def]
    return run_inspection(
        inspection_dir=FIXTURE_DIR, mode="fixture", generated_at="2026-01-01T00:00:00Z"
    ).report


@pytest.fixture(scope="module")
def teaser(report):  # type: ignore[no-untyped-def]
    return build_teaser(report, price_usd=PRICE)


@pytest.fixture(scope="module")
def blob(teaser) -> str:  # type: ignore[no-untyped-def]
    return teaser.to_json()


# --------------------------------------------------------------------------- #
# the paywall                                                                  #
# --------------------------------------------------------------------------- #


def test_no_paid_content_survives_the_projection(report, blob) -> None:  # type: ignore[no-untyped-def]
    """The teaser is a smaller object, not a hidden one.

    Checked on the text rather than the schema, because the dangerous refactor
    is one that keeps the shape and changes what fills it.
    """
    assert report.findings, "the fixture must have findings or this proves nothing"

    for finding in report.findings:
        assert finding.title not in blob, f"leaked title: {finding.title}"
        assert finding.detail not in blob, f"leaked detail of {finding.id}"
        assert finding.confidence_basis not in blob
        assert finding.id not in blob
        for evidence in finding.evidence:
            caption = getattr(evidence, "caption", None)
            if caption:
                assert caption not in blob


def test_no_evidence_of_any_kind_reaches_the_teaser(blob) -> None:  # type: ignore[no-untyped-def]
    payload = json.loads(blob)
    for key in ("findings", "mechanicReferrals", "assets", "price", "vehicle", "audio"):
        assert key not in payload, f"{key} must not exist in a teaser at all"
    # Bounding boxes are the single most valuable thing in the paid report.
    assert '"box"' not in blob
    assert "image_region" not in blob


def test_the_vin_never_appears_even_masked(report, blob) -> None:  # type: ignore[no-untyped-def]
    assert report.vehicle is not None
    assert report.vehicle.vin not in blob
    assert report.vehicle.vin_masked not in blob
    assert "******" not in blob


def test_mechanic_referral_observations_do_not_leak(report, blob) -> None:  # type: ignore[no-untyped-def]
    assert report.mechanic_referrals
    for referral in report.mechanic_referrals:
        assert referral.observation not in blob


def test_the_teaser_is_substantially_smaller(report, blob) -> None:  # type: ignore[no-untyped-def]
    """A blunt sanity check. If these ever converge, something is being shipped."""
    assert len(blob) < len(report.to_json()) / 4


# --------------------------------------------------------------------------- #
# what stays free, and why                                                     #
# --------------------------------------------------------------------------- #


def test_coverage_is_free_and_complete(report, teaser) -> None:  # type: ignore[no-untyped-def]
    """It says whether this could answer the question - that belongs before the
    payment, not after."""
    assert teaser.coverage == report.coverage
    assert teaser.coverage.missing_views


def test_every_could_not_assess_line_is_free(report, teaser) -> None:  # type: ignore[no-untyped-def]
    """Charging someone to discover we cannot assess their brakes would be
    indefensible."""
    assert teaser.could_not_assess == list(report.verdict.could_not_assess)
    assert any("mechanic required" in line for line in teaser.could_not_assess)


def test_all_four_locked_rows_are_free_and_verbatim(teaser) -> None:  # type: ignore[no-untyped-def]
    locked = [row for row in teaser.systems if row.system in LOCKED_SYSTEMS]
    assert len(locked) == 4
    for row in locked:
        assert row.status == "locked_mechanic_required"
        assert row.statement == LOCKED_SYSTEM_STATEMENT


def test_a_teaser_row_cannot_paraphrase_the_locked_statement() -> None:
    from tirekick_engines.models import TeaserSystemRow

    with pytest.raises(ValueError, match="LAW 2"):
        TeaserSystemRow(
            system="brakes",
            status="locked_mechanic_required",
            statement="Brakes could not be checked.",
        )


def test_the_counts_are_the_hook_and_they_are_true(report, teaser) -> None:  # type: ignore[no-untyped-def]
    assert teaser.finding_count == len(report.findings)
    assert sum(c.count for c in teaser.counts) == len(report.findings)
    assert teaser.mechanic_referral_count == len(report.mechanic_referrals)
    assert teaser.red_flag_score == report.verdict.red_flag_score


def test_the_headline_carries_counts_but_no_specifics(report, teaser) -> None:  # type: ignore[no-untyped-def]
    assert teaser.headline == report.verdict.headline
    for finding in report.findings:
        assert finding.title not in teaser.headline


def test_the_vehicle_summary_is_year_make_model_only(teaser) -> None:  # type: ignore[no-untyped-def]
    assert teaser.vehicle_summary == "2013 HONDA Accord"


# --------------------------------------------------------------------------- #
# the accuracy statement - D-032                                               #
# --------------------------------------------------------------------------- #


def test_the_accuracy_statement_comes_from_the_gate(teaser) -> None:  # type: ignore[no-untyped-def]
    """Generated, not written, so it cannot be softened when it becomes
    commercially inconvenient."""
    enabled = [s for s in FINDING_TYPES.values() if s.enabled_for_paid]
    assert not enabled, "this test describes the current, unmeasured state"

    assert teaser.accuracy_statement == accuracy_statement()
    assert "None of the" in teaser.accuracy_statement
    assert "has cleared its accuracy threshold" in teaser.accuracy_statement


def test_the_statement_changes_when_something_clears_its_gate(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """It is not a hardcoded apology - it tracks the registry."""
    from dataclasses import replace

    import tirekick_engines.teaser as teaser_module

    patched = dict(FINDING_TYPES)
    patched["rust_corrosion"] = replace(
        patched["rust_corrosion"], measured_precision=0.93, n=120
    )
    monkeypatch.setattr(teaser_module, "FINDING_TYPES", patched)

    statement = teaser_module.accuracy_statement()
    assert statement.startswith("1 of 16 finding types have cleared")
    assert "including the misses" in statement


def test_the_price_and_what_it_buys_are_both_stated(teaser) -> None:  # type: ignore[no-untyped-def]
    assert teaser.price_usd == PRICE
    assert len(teaser.unlocks) >= 5
    assert any("box drawn on it" in line for line in teaser.unlocks)


def test_the_synthetic_flag_survives_into_the_teaser(teaser) -> None:  # type: ignore[no-untyped-def]
    assert teaser.contains_synthetic_media is True
