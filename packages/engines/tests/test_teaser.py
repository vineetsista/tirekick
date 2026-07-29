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


@pytest.fixture(scope="module")
def rest(blob) -> str:  # type: ignore[no-untyped-def]
    """The teaser with the one declared sample removed.

    Exactly one finding crosses the paywall on purpose (D-044), so a guard that
    reads "no paid sentence appears anywhere" can no longer be true as written.
    The guard that replaces it is the same sentence with a hole cut in it whose
    exact shape is `sample`: everything the free payload contains *other than*
    the one disclosure is held to the original standard, unchanged.

    Deleting the key rather than relaxing the assertions is the point. A refactor
    that routes a second finding down the free route has to put it somewhere, and
    everywhere except this one field is still checked on the raw text.
    """
    payload = json.loads(blob)
    payload.pop("sample", None)
    return json.dumps(payload, indent=2)


# --------------------------------------------------------------------------- #
# the paywall                                                                  #
# --------------------------------------------------------------------------- #


def test_no_paid_content_survives_the_projection(report, teaser, rest) -> None:  # type: ignore[no-untyped-def]
    """The teaser is a smaller object, not a hidden one.

    Checked on the text rather than the schema, because the dangerous refactor
    is one that keeps the shape and changes what fills it.
    """
    assert report.findings, "the fixture must have findings or this proves nothing"

    for finding in report.findings:
        assert finding.title not in rest, f"leaked title: {finding.title}"
        assert finding.detail not in rest, f"leaked detail of {finding.id}"
        assert finding.confidence_basis not in rest
        assert finding.id not in rest
        for evidence in finding.evidence:
            caption = getattr(evidence, "caption", None)
            if caption:
                assert caption not in rest


def test_only_the_sampled_finding_crosses_the_paywall(report, teaser, blob) -> None:  # type: ignore[no-untyped-def]
    """The hole in the guard above is exactly one finding wide.

    Checked against the *whole* payload, sample included: every finding except
    the sampled one must be absent from the free bytes entirely.
    """
    assert teaser.sample is not None, "the fixture must produce a sample"
    for finding in report.findings:
        if finding.id == teaser.sample.finding_id:
            continue
        assert finding.title not in blob, f"leaked title: {finding.title}"
        assert finding.detail not in blob, f"leaked detail of {finding.id}"
        assert finding.confidence_basis not in blob
        assert finding.id not in blob
        for evidence in finding.evidence:
            caption = getattr(evidence, "caption", None)
            if caption:
                assert caption not in blob


def test_the_sample_is_one_object_and_not_a_list(blob) -> None:  # type: ignore[no-untyped-def]
    """`sample` is singular in the type system and must stay singular in the JSON.

    A list would be a paywall with a length knob on it, and the knob would be
    turned by whoever next wants the free page to convert better.
    """
    payload = json.loads(blob)
    assert isinstance(payload["sample"], dict)
    assert json.dumps(payload["sample"]).count('"box"') == 1


def test_no_evidence_of_any_kind_reaches_the_teaser(blob, rest) -> None:  # type: ignore[no-untyped-def]
    payload = json.loads(blob)
    for key in ("findings", "mechanicReferrals", "assets", "price", "vehicle", "audio"):
        assert key not in payload, f"{key} must not exist in a teaser at all"
    # Bounding boxes are the single most valuable thing in the paid report. The
    # sample carries exactly one, asserted above; nothing else carries any.
    assert '"box"' not in rest
    assert "image_region" not in rest


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
# the one finding that is given away (D-044)                                   #
# --------------------------------------------------------------------------- #


def test_the_sample_is_a_real_finding_reproduced_faithfully(report, teaser) -> None:  # type: ignore[no-untyped-def]
    """Free does not mean softened.

    The sample is the paid finding verbatim - same severity, same confidence,
    same basis. A teaser that rounded the confidence up or dropped the caveat
    would be advertising a product the paid report does not contain.
    """
    sample = teaser.sample
    assert sample is not None
    origin = next(f for f in report.findings if f.id == sample.finding_id)
    assert sample.title == origin.title
    assert sample.detail == origin.detail
    assert sample.severity == origin.severity
    assert sample.confidence == origin.confidence
    assert sample.confidence_basis == origin.confidence_basis
    assert sample.type == origin.type
    assert sample.system == origin.system


def test_the_sample_cites_an_asset_that_exists_at_the_size_recorded(report, teaser) -> None:  # type: ignore[no-untyped-def]
    """A box is only checkable against an image of known size (LAW 1)."""
    sample = teaser.sample
    assert sample is not None
    asset = next(a for a in report.assets if a.id == sample.asset_id)
    assert sample.asset_path == asset.path
    assert sample.asset_width == asset.width
    assert sample.asset_height == asset.height
    assert asset.width and asset.height, "the sampled photo must have dimensions"
    assert sample.asset_synthetic == asset.synthetic
    # The box is a fraction of that image and must land inside it.
    assert 0.0 <= sample.box.x <= 1.0 and 0.0 <= sample.box.y <= 1.0
    assert sample.box.x + sample.box.w <= 1.0 + 1e-9
    assert sample.box.y + sample.box.h <= 1.0 + 1e-9


def test_the_sample_is_never_a_model_level_record(report, teaser) -> None:  # type: ignore[no-untyped-def]
    """A recall campaign is true of every car of that model year.

    Handing one over as *the* sample would advertise this vehicle's report with
    a fact about a car the buyer has never seen.
    """
    from tirekick_engines.dossier import MODEL_LEVEL_TYPES

    assert teaser.sample is not None
    assert teaser.sample.type not in MODEL_LEVEL_TYPES


def test_the_sample_is_never_from_a_locked_system(teaser) -> None:
    """LAW 2, restated at the paywall.

    The safety clamp already converts locked-system findings to referrals, so
    this asserts a property of a pipeline rather than of this function alone -
    which is exactly why it is worth asserting. The free page is the most-read
    surface in the product; a brake claim reaching it would be the worst
    possible place for the clamp to have failed.
    """
    assert teaser.sample is not None
    assert teaser.sample.system not in LOCKED_SYSTEMS


def test_the_sample_is_the_strongest_finding_not_the_weakest(report, teaser) -> None:  # type: ignore[no-untyped-def]
    """Showing the least of what was found in order to hold the best back is a
    sales tactic. The coverage block above it already states the limits."""
    from tirekick_engines.dossier import MODEL_LEVEL_TYPES
    from tirekick_engines.models import ImageRegionEvidence

    sample = teaser.sample
    assert sample is not None
    rank = {"info": 0, "minor": 1, "major": 2, "critical": 3}
    eligible = [
        f
        for f in report.findings
        if f.type not in MODEL_LEVEL_TYPES
        and any(isinstance(e, ImageRegionEvidence) for e in f.evidence)
    ]
    assert eligible
    best = max(eligible, key=lambda f: (rank[f.severity], f.confidence))
    assert (rank[sample.severity], sample.confidence) == (
        rank[best.severity],
        best.confidence,
    )


def test_the_sample_statement_counts_honestly(report, teaser) -> None:  # type: ignore[no-untyped-def]
    """ "One of 9" must be the real 9, or the free page understates the product
    while appearing to describe it."""
    from tirekick_engines.dossier import MODEL_LEVEL_TYPES

    sample = teaser.sample
    assert sample is not None
    total = sum(1 for f in report.findings if f.type not in MODEL_LEVEL_TYPES)
    assert str(total) in sample.statement
    assert "this vehicle" in sample.statement


def test_a_report_with_no_photographic_finding_has_no_sample(report) -> None:  # type: ignore[no-untyped-def]
    """An upload with no vision responses must render an honest empty state
    rather than an empty frame."""
    from tirekick_engines.models import ImageRegionEvidence

    stripped = report.model_copy(
        update={
            "findings": [
                f
                for f in report.findings
                if not any(isinstance(e, ImageRegionEvidence) for e in f.evidence)
            ]
        }
    )
    assert build_teaser(stripped, price_usd=PRICE).sample is None


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
