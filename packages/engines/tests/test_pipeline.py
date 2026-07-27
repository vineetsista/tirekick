"""The end-to-end fixture run, and the golden report it must keep producing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tirekick_engines.models import LOCKED_SYSTEMS
from tirekick_engines.pipeline import run_inspection

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "fixtures" / "demo-01"
GOLDEN = REPO_ROOT / "fixtures" / "reports" / "demo-01.report.json"

#: Pinned so golden output is byte-stable across runs.
FIXED_TIME = "2026-01-01T00:00:00Z"


@pytest.fixture(scope="module")
def run():  # type: ignore[no-untyped-def]
    return run_inspection(inspection_dir=FIXTURE_DIR, mode="fixture", generated_at=FIXED_TIME)


def test_fixture_run_needs_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """LAW 7. CI has no secrets and must still go green."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = run_inspection(inspection_dir=FIXTURE_DIR, mode="fixture", generated_at=FIXED_TIME)
    assert result.report.findings


def test_golden_report_is_unchanged(run) -> None:  # type: ignore[no-untyped-def]
    """Committed media + committed responses -> byte-identical report.

    When this fails, either the pipeline changed or a fixture did. Both are worth
    stopping for; regenerate deliberately, and read the diff.
    """
    assert GOLDEN.is_file(), "run: pnpm run inspect:fixture"
    expected = GOLDEN.read_text(encoding="utf-8")
    assert run.report.to_json() == expected


def test_fixture_mode_freezes_its_own_clock(run) -> None:  # type: ignore[no-untyped-def]
    """D-011. A fixture run with no --generated-at is still byte-reproducible.

    Without this, every run rewrites generated_at, the golden report churns, and
    the snapshot tests that guard the dossier become noise nobody reads.
    """
    a = run_inspection(inspection_dir=FIXTURE_DIR, mode="fixture")
    b = run_inspection(inspection_dir=FIXTURE_DIR, mode="fixture")
    assert a.report.generated_at == FIXED_TIME
    assert a.report.to_json() == b.report.to_json()
    assert a.report.to_json() == run.report.to_json()


def test_an_explicit_timestamp_still_wins(run) -> None:  # type: ignore[no-untyped-def]
    override = run_inspection(
        inspection_dir=FIXTURE_DIR, mode="fixture", generated_at="2030-06-01T12:00:00Z"
    )
    assert override.report.generated_at == "2030-06-01T12:00:00Z"


def test_report_declares_its_synthetic_media(run) -> None:  # type: ignore[no-untyped-def]
    assert run.report.contains_synthetic_media is True
    assert all(a.synthetic for a in run.report.assets)


def test_no_finding_touches_a_locked_system(run) -> None:  # type: ignore[no-untyped-def]
    """The law, asserted on the real artifact rather than on a constructed one."""
    assert not [f for f in run.report.findings if f.system in LOCKED_SYSTEMS]


def test_the_fabricated_all_clear_never_reaches_the_report(run) -> None:  # type: ignore[no-untyped-def]
    """fixtures ship a deliberate 'brakes are good, 0.96' draft. It must die here."""
    blob = run.report.to_json().lower()
    assert "good condition" not in blob
    assert "vf_bay_03" not in blob
    assert any("dropped 'vf_bay_03'" in line for line in run.clamp_log)


def test_the_adverse_brake_observation_survives_as_a_referral(run) -> None:  # type: ignore[no-untyped-def]
    referral_ids = {r.id for r in run.report.mechanic_referrals}
    assert "ref_vf_bay_02" in referral_ids


def test_the_clamp_reaches_document_findings_too(run) -> None:  # type: ignore[no-untyped-def]
    """LAW 2 is about the system, not about which engine spoke.

    The fixture's paperwork reports structural repair. That has to leave the
    pipeline as a mechanic referral carrying its document excerpt - visible to
    the buyer, and never graded. Recalls naming a locked system take the same
    path; the Takata campaigns in test_data_golden.py cover that on real records.
    """
    referral = next(
        r for r in run.report.mechanic_referrals if r.id == "ref_title_structural_history_01"
    )
    assert referral.system == "structure"
    assert referral.evidence[0].kind == "document_excerpt"
    assert "structural damage" in referral.evidence[0].excerpt


def test_every_finding_cites_evidence_that_resolves(run) -> None:  # type: ignore[no-untyped-def]
    asset_ids = {a.id for a in run.report.assets}
    assert run.report.findings
    for finding in run.report.findings:
        assert finding.evidence, f"{finding.id} has no evidence"
        for ev in finding.evidence:
            asset_id = getattr(ev, "asset_id", None)
            if asset_id is not None:
                assert asset_id in asset_ids


def test_all_four_locked_rows_are_present_and_identical(run) -> None:  # type: ignore[no-untyped-def]
    locked = [r for r in run.report.systems if r.system in LOCKED_SYSTEMS]
    assert len(locked) == 4
    assert {r.status for r in locked} == {"locked_mechanic_required"}


def test_no_system_is_called_clean_without_being_examined(run) -> None:  # type: ignore[no-untyped-def]
    """LIABILITY section 9 - the false-reassurance-by-omission guard.

    A system nothing looked at must read cannot_determine. Glass is the standing
    example: photographs may show it, but no pass assesses it.
    """
    glass = next(r for r in run.report.systems if r.system == "glass")
    assert glass.status == "cannot_determine"


def test_coverage_leads_with_what_is_missing(run) -> None:  # type: ignore[no-untyped-def]
    coverage = run.report.coverage
    assert coverage.missing_views
    assert "Not covered" in coverage.statement
    assert coverage.score < 1.0
    # The verdict block names the gap, not just the coverage block.
    assert any("standard view" in line for line in run.report.verdict.could_not_assess)


def test_verdict_leads_with_the_locked_systems(run) -> None:  # type: ignore[no-untyped-def]
    first_four = run.report.verdict.could_not_assess[:4]
    assert all("independent mechanic required" in line for line in first_four)


def test_cost_is_reported_and_is_honestly_zero(run) -> None:  # type: ignore[no-untyped-def]
    cost = run.report.cost
    assert cost.mode == "fixture"
    assert cost.usd_total == 0.0
    assert "no API calls billed" in cost.note
    # The work is still counted even though it was not billed.
    assert cost.images_analyzed > 0
    assert cost.storage_bytes > 0


def test_price_verdict_shows_its_comps(run) -> None:  # type: ignore[no-untyped-def]
    price = run.report.price
    assert price is not None
    assert len(price.comps) >= 3
    assert price.deductions
    for deduction in price.deductions:
        assert deduction.finding_id in {f.id for f in run.report.findings}


def test_audio_still_makes_no_claims(run) -> None:  # type: ignore[no-untyped-def]
    """P3 gave audio a working detector and it still says nothing. LAW 4.

    This is the test that costs something. There is a spectrogram, three located
    transients, and a measured idle frequency in the report - and zero findings,
    because `audio_anomaly` has never been measured against a labelled set.
    """
    assert not [f for f in run.report.findings if f.engine == "audio"]
    assert run.report.coverage.has_audio is True

    track = run.report.audio
    assert track is not None
    assert track.claims_enabled is False
    assert any(
        "does not make claims about engine condition" in line
        for line in run.report.verdict.could_not_assess
    )


def test_the_audio_section_shows_evidence_without_interpreting_it(run) -> None:  # type: ignore[no-untyped-def]
    """A picture, timestamps, and no diagnosis attached to either."""
    track = run.report.audio
    assert track is not None
    assert track.spectrogram_path.endswith(".png")
    assert track.transients, "the fixture clip has three deliberate impulses"
    # Located, and explicitly not identified.
    assert "not telling you what it heard" in track.transient_statement


def test_implied_rpm_is_reported_only_with_a_cylinder_count(run) -> None:  # type: ignore[no-untyped-def]
    """Guessing the cylinders puts the answer out by a clean factor of two."""
    track = run.report.audio
    assert track is not None
    # demo-01 decodes to a 4-cylinder Accord, so the arithmetic is available.
    assert track.implied_rpm is not None
    assert 700 <= track.implied_rpm <= 1400
    assert "arithmetic on the recording" in track.implied_rpm_basis


def test_report_json_round_trips(run) -> None:  # type: ignore[no-untyped-def]
    """What we write is what the web app parses."""
    from tirekick_engines.models import Report

    reparsed = Report.model_validate(json.loads(run.report.to_json()))
    assert reparsed == run.report
