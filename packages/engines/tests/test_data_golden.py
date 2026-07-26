"""Golden tests over five real VINs. The P1 gate.

Every assertion here runs against a committed snapshot of what NHTSA returned, so
the suite needs no network and no key (LAW 7). Refresh the snapshot deliberately
with scripts/refresh_federal_cache.py and read the diff - recall counts really do
change, and a silent change would quietly redefine what these tests mean.

What is being tested is fidelity, not intelligence: does the record we render say
what the federal source said, and does it stop where the federal source stops.
The second half is the one that matters. NHTSA publishes recalls per model and
never per VIN, and the failure this file exists to prevent is a report that
presents a model-level campaign as a defect found on one particular car.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tirekick_engines.cogs import CostMeter
from tirekick_engines.engines import data as data_engine
from tirekick_engines.models import LOCKED_SYSTEMS
from tirekick_engines.safety import apply_safety_law
from tirekick_engines.sources import DEFAULT_CACHE_DIR, FederalSources

REPO_ROOT = Path(__file__).resolve().parents[3]

#: What the federal cache held when it was last refreshed. Checked as exact
#: values so a refresh cannot change the meaning of a test without showing up.
EXPECTED = {
    "1HGCM82673A000000": {
        "year": 2003,
        "make": "HONDA",
        "model": "Accord",
        "trim": "EX-V6",
        "recalls": 24,
        "complaints": 2013,
    },
    "1FTFW1ET6DFC00000": {
        "year": 2013,
        "make": "FORD",
        "model": "F-150",
        "trim": None,
        "recalls": 3,
        "complaints": 8388,
    },
    "4S4BSANC9G3000000": {
        "year": 2016,
        "make": "SUBARU",
        "model": "Outback",
        "trim": "Limited + MR + ES + NAVI",
        "recalls": 4,
        "complaints": 639,
    },
    "3GCUKRECXFG000000": {
        "year": 2015,
        "make": "CHEVROLET",
        "model": "Silverado",
        "trim": "LT",
        "recalls": 7,
        "complaints": 1174,
    },
    "KM8J3CA43JU000000": {
        "year": 2018,
        "make": "HYUNDAI",
        "model": "Tucson",
        "trim": "SE Pop, SE Plus, Eco, Sport, Value, Ultimate Base/Ultimate",
        "recalls": 1,
        "complaints": 383,
    },
}

GOLDEN_VINS = sorted(EXPECTED)


@pytest.fixture(scope="module")
def sources() -> FederalSources:
    return FederalSources(
        mode="fixture", cache_dir=DEFAULT_CACHE_DIR, meter=CostMeter(mode="fixture")
    )


def _record(sources: FederalSources, vin: str):  # type: ignore[no-untyped-def]
    record = data_engine.lookup(vin, sources)
    assert record is not None, f"no cached federal record for {vin}"
    return record


def test_the_golden_set_is_what_the_manifest_says_it_is() -> None:
    """The VIN list, the tests, and the refresh script cannot drift apart."""
    manifest = json.loads((DEFAULT_CACHE_DIR / "GOLDEN_VINS.json").read_text(encoding="utf-8"))
    assert sorted(entry["vin"] for entry in manifest["vins"]) == GOLDEN_VINS
    assert len(GOLDEN_VINS) == 5


@pytest.mark.parametrize("vin", GOLDEN_VINS)
def test_decode_matches_the_federal_record(sources: FederalSources, vin: str) -> None:
    record = _record(sources, vin)
    expected = EXPECTED[vin]

    assert record.vin_valid is True
    assert record.decode_error is None
    assert record.decoded.year == expected["year"]
    assert record.decoded.make == expected["make"]
    assert record.decoded.model == expected["model"]
    assert record.decoded.trim == expected["trim"]


@pytest.mark.parametrize("vin", GOLDEN_VINS)
def test_recall_and_complaint_counts_match_the_snapshot(
    sources: FederalSources, vin: str
) -> None:
    record = _record(sources, vin)
    expected = EXPECTED[vin]

    assert len(record.recalls) == expected["recalls"]
    assert record.complaint_summary is not None
    assert record.complaint_summary.total == expected["complaints"]


@pytest.mark.parametrize("vin", GOLDEN_VINS)
def test_every_recall_carries_a_resolvable_citation(sources: FederalSources, vin: str) -> None:
    """LAW 1. A database claim needs a citation exactly as much as a visual one."""
    record = _record(sources, vin)
    for draft in data_engine.recall_findings(record):
        assert len(draft.evidence) >= 1
        evidence = draft.evidence[0]
        assert evidence.kind == "data_record"
        assert evidence.record_id
        assert evidence.retrieved_at
        assert "NHTSA" in evidence.source


@pytest.mark.parametrize("vin", GOLDEN_VINS)
def test_no_recall_is_presented_as_outstanding_on_this_vehicle(
    sources: FederalSources, vin: str
) -> None:
    """The central honesty test of the data engine.

    NHTSA publishes no per-VIN remedy status, so no wording anywhere in a recall
    finding may imply we know one. The scope sentence must carry the caveat, and
    the finding text must say we cannot tell.
    """
    record = _record(sources, vin)
    assert "not a list of what is outstanding" in record.recall_scope
    assert "by model, not by VIN" in record.recall_scope

    for draft in data_engine.recall_findings(record):
        assert "cannot tell whether it was ever carried out" in draft.detail
        assert "does not publish per-VIN repair status" in draft.detail
        # The seller question asks; it never assumes.
        assert draft.seller_question is not None
        assert "Has it been done" in draft.seller_question


@pytest.mark.parametrize("vin", GOLDEN_VINS)
def test_recalls_on_locked_systems_never_survive_as_findings(
    sources: FederalSources, vin: str
) -> None:
    """LAW 2, applied to federal records rather than to model output.

    The 2003 Accord is in this set because it carries Takata airbag campaigns:
    real recalls, naming a locked system, that must leave the pipeline as
    mechanic referrals and never as graded findings.
    """
    record = _record(sources, vin)
    result = apply_safety_law(data_engine.recall_findings(record))

    assert all(f.system not in LOCKED_SYSTEMS for f in result.findings)
    for referral in result.referrals:
        assert referral.system in LOCKED_SYSTEMS
        # A referral carries no verdict: no severity, no confidence, no grade.
        assert not hasattr(referral, "severity")
        assert not hasattr(referral, "confidence")


def test_the_takata_campaigns_actually_reach_the_referral_path() -> None:
    """Guards the test above from passing vacuously.

    If the 2003 Accord ever stops producing locked-system recalls, the clamp
    assertions are still green while testing nothing at all.
    """
    sources = FederalSources(
        mode="fixture", cache_dir=DEFAULT_CACHE_DIR, meter=CostMeter(mode="fixture")
    )
    record = _record(sources, "1HGCM82673A000000")
    result = apply_safety_law(data_engine.recall_findings(record))

    assert result.referrals, "expected airbag recalls to become mechanic referrals"
    assert any(r.system == "restraints" for r in result.referrals)
    assert any("AIR BAG" in ev.caption for r in result.referrals for ev in r.evidence)


@pytest.mark.parametrize("vin", GOLDEN_VINS)
def test_complaint_summaries_describe_the_model_and_say_so(
    sources: FederalSources, vin: str
) -> None:
    record = _record(sources, vin)
    assert record.complaint_summary is not None
    scope = record.complaint_summary.scope
    assert "describe the model" in scope or "cover all of them" in scope

    for draft in data_engine.complaint_findings(record):
        assert draft.severity == "info"
        assert "not an observation about this car" in draft.detail


def test_a_truck_that_nhtsa_indexes_under_several_names_is_aggregated_and_says_so() -> None:
    """The F-150 case.

    vPIC decodes the model as 'F-150'. The complaints endpoint rejects that name
    outright and indexes the same truck under three cab configurations. Before
    this was handled, the complaint lookup failed and the report would have shown
    zero complaints - which reads as good news and was actually a failed query.
    """
    sources = FederalSources(
        mode="fixture", cache_dir=DEFAULT_CACHE_DIR, meter=CostMeter(mode="fixture")
    )
    record = _record(sources, "1FTFW1ET6DFC00000")

    assert record.complaint_summary is not None
    assert record.complaint_summary.total > 0
    scope = record.complaint_summary.scope
    assert "more than one name" in scope
    assert "F-150 SUPERCAB" in scope
    assert "the VIN does not say which one" in scope


def test_a_truck_with_a_series_resolves_to_exactly_one_name() -> None:
    """The Silverado case - vPIC gives series 1500, so no aggregation is needed.

    Blending a half-ton's complaints with a one-ton's would be the lazy answer.
    """
    sources = FederalSources(
        mode="fixture", cache_dir=DEFAULT_CACHE_DIR, meter=CostMeter(mode="fixture")
    )
    record = _record(sources, "3GCUKRECXFG000000")

    assert record.decoded.series == "1500"
    assert record.complaint_summary is not None
    assert "more than one name" not in record.complaint_summary.scope


def test_complaint_cache_retains_counts_and_no_narratives() -> None:
    """D-015. Third-party complaint narratives never enter the repository."""
    for path in DEFAULT_CACHE_DIR.glob("nhtsa.complaints.*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))["payload"]
        assert set(payload) <= {
            "total",
            "top_components",
            "with_crash",
            "with_fire",
            "injuries_reported",
            "deaths_reported",
            "_reduction_note",
        }, f"{path.name} stores more than counts"
        # The SHA of the full response survives, so the reduction stays traceable.
        envelope = json.loads(path.read_text(encoding="utf-8"))
        assert len(envelope["_body_sha256"]) == 64


def test_an_unusable_vin_produces_no_lookup_and_no_invented_record() -> None:
    sources = FederalSources(
        mode="fixture", cache_dir=DEFAULT_CACHE_DIR, meter=CostMeter(mode="fixture")
    )
    record = data_engine.lookup("1HGCR2F31DA000000", sources)  # bad check digit

    assert record is not None
    assert record.vin_valid is False
    assert record.decoded.year is None
    assert record.recalls == []
    assert record.sources == []
    assert "check digit" in record.vin_statement
    # Nothing to cite, so - LAW 1 - nothing is reported as a finding.
    assert data_engine.recall_findings(record) == []
    assert data_engine.decode_findings(record) == []


def test_a_listing_that_disagrees_with_the_vin_is_flagged(
    sources: FederalSources,
) -> None:
    record = _record(sources, "1HGCR2F37DA000000")
    drafts = data_engine.decode_findings(
        record, listing_year=2015, listing_make="Toyota", listing_model="Camry"
    )
    assert len(drafts) == 1
    assert drafts[0].type == "vin_decode"
    assert drafts[0].severity == "major"
    assert "2015" in drafts[0].detail and "2013" in drafts[0].detail


def test_a_listing_that_agrees_with_the_vin_is_silent(sources: FederalSources) -> None:
    record = _record(sources, "1HGCR2F37DA000000")
    assert (
        data_engine.decode_findings(
            record, listing_year=2013, listing_make="Honda", listing_model="Accord"
        )
        == []
    )


def test_a_model_name_the_listing_abbreviates_is_not_a_mismatch(
    sources: FederalSources,
) -> None:
    """'Silverado 1500' against a decoded 'Silverado' is not a disagreement.

    Crying wolf on every truck listing would train buyers to ignore the one time
    it matters.
    """
    record = _record(sources, "3GCUKRECXFG000000")
    assert (
        data_engine.decode_findings(
            record,
            listing_year=2015,
            listing_make="Chevrolet",
            listing_model="Silverado 1500",
        )
        == []
    )
