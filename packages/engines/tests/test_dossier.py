"""The dossier's own judgments, tested against synthetic reports rather than the fixture.

Every one of these branches existed before this file and was pinned only by the
golden byte-compare of `demo-01` - which exercises exactly one of the five
headline sentences, one shape of systems table, and one negotiation script. A
regression in the other four was invisible to nine gates.

The reports below are built by hand so each case is the smallest thing that can
distinguish the branch. Where a case corresponds to a defect this suite was
written for, the docstring says which.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from tirekick_engines import dossier, registry
from tirekick_engines.cogs import CostMeter
from tirekick_engines.dossier import build_report
from tirekick_engines.models import (
    Asset,
    BoundingBox,
    CostBand,
    DecodedVehicle,
    DraftFinding,
    ImageRegionEvidence,
    Recall,
    VehicleRecord,
)

FIXED_TIME = "2026-01-01T00:00:00Z"


def photo(asset_id: str = "photo_01", view: str = "exterior_front") -> Asset:
    return Asset(
        id=asset_id,
        kind="photo",
        path=f"{asset_id}.jpg",
        bytes=1024,
        sha256="0" * 64,
        view_class=view,  # type: ignore[arg-type]
        width=1600,
        height=1200,
        synthetic=True,
    )


def draft(
    *,
    finding_id: str = "f1",
    finding_type: str = "exterior_damage",
    system: str = "exterior",
    severity: str = "major",
    confidence: float = 0.8,
    cost: CostBand | None = None,
    asset_id: str = "photo_01",
) -> DraftFinding:
    return DraftFinding(
        id=finding_id,
        type=finding_type,  # type: ignore[arg-type]
        system=system,  # type: ignore[arg-type]
        title=f"{finding_type} on the {system}",
        detail="A synthetic finding, written to exercise one branch of the dossier.",
        severity=severity,  # type: ignore[arg-type]
        confidence=confidence,
        confidence_basis="Constructed by a test, so the basis is the test.",
        evidence=[
            ImageRegionEvidence(
                asset_id=asset_id,
                box=BoundingBox(x=0.1, y=0.1, w=0.2, h=0.2),
                caption="The region this synthetic finding cites.",
            )
        ],
        estimated_cost_usd=cost,
        engine="vision",
    )


def vehicle_with(recalls: list[Recall]) -> VehicleRecord:
    return VehicleRecord(
        vin="1HGCR2F37DA000000",
        vin_masked="1HGCR2F37D******",
        vin_valid=True,
        vin_statement=(
            "The VIN decodes to a model, not to this car's history. "
            "Confirm the title with your state motor vehicle agency."
        ),
        decoded=DecodedVehicle(year=2013, make="Honda", model="Accord"),
        recalls=recalls,
        recall_scope=(
            "Recalls are published per model year, not per VIN. A dealer can "
            "check this car by VIN for free."
        ),
        complaint_summary=None,
        sources=[],
    )


def recall(campaign: str, component: str) -> Recall:
    return Recall(
        campaign_number=campaign,
        component=component,
        summary=f"A synthetic campaign against {component}.",
        consequence="Stated by the campaign, reproduced here for the test.",
        remedy="Dealer will remedy free of charge.",
        report_received_date="2024-01-01",
    )


def build(
    *,
    drafts: list[DraftFinding],
    vehicle: VehicleRecord | None = None,
    assets: list[Asset] | None = None,
):  # type: ignore[no-untyped-def]
    report, _log = build_report(
        inspection_id="insp_test",
        report_id="rpt_test",
        mode="fixture",
        assets=assets if assets is not None else [photo()],
        drafts=drafts,
        vehicle=vehicle,
        audio=None,
        walkaround=None,
        asking_price_usd=None,
        comps=[],
        subject_mileage=None,
        meter=CostMeter(mode="fixture"),
        examined_systems=set(),
        generated_at=FIXED_TIME,
    )
    return report


# --------------------------------------------------------------- the headline --


def test_the_critical_branch_says_critical() -> None:
    report = build(drafts=[draft(severity="critical")])
    assert report.verdict.headline.startswith("1 critical finding(s) visible")


def test_the_major_branch_talks_about_money() -> None:
    report = build(drafts=[draft(severity="major")])
    assert "likely to cost money" in report.verdict.headline


def test_an_info_reading_is_not_reported_as_a_minor_finding() -> None:
    """An odometer value is a reading, not a fault.

    The branch counted every vehicle-level finding as minor, so a report whose
    only finding was an info-severity odometer reading led with "1 minor
    finding(s) visible" - an adverse sentence about a neutral number, in the
    line that opens both the paid report and the free teaser.
    """
    report = build(
        drafts=[draft(finding_type="odometer_reading", system="documentation", severity="info")]
    )
    assert "minor finding" not in report.verdict.headline
    assert report.verdict.headline.startswith("Nothing adverse was visible")
    assert "1 reading(s) were recorded" in report.verdict.headline


def test_minor_findings_are_counted_without_the_info_ones() -> None:
    report = build(
        drafts=[
            draft(finding_id="f1", severity="minor"),
            draft(
                finding_id="f2",
                finding_type="odometer_reading",
                system="documentation",
                severity="info",
            ),
        ]
    )
    assert report.verdict.headline.startswith("1 minor finding(s) visible")


def test_an_empty_handed_report_says_so_plainly() -> None:
    report = build(drafts=[])
    assert report.verdict.headline == "Nothing adverse was visible in the media provided."


def test_a_locked_system_recall_still_reaches_the_headline() -> None:
    """The airbag case.

    A campaign against a locked system is converted to a mechanic referral by
    the safety clamp, so counting recalls among the surviving findings meant the
    single most common recall category in the fleet could not appear in the
    headline at all. A car whose only campaign was an airbag recall reported
    "Nothing adverse was visible in the media provided." and nothing else.
    """
    report = build(
        drafts=[
            draft(
                finding_id="recall_1",
                finding_type="open_recall",
                system="restraints",
                severity="major",
                confidence=1.0,
            )
        ],
        vehicle=vehicle_with([recall("24V001000", "AIR BAGS:FRONTAL")]),
    )
    assert not report.findings, "the clamp should have taken the campaign out of findings"
    assert any(r.system == "restraints" for r in report.mechanic_referrals)
    assert "1 recall campaign(s) are on record" in report.verdict.headline


def test_the_recall_count_matches_the_federal_record_it_came_from() -> None:
    vehicle = vehicle_with(
        [
            recall("24V001000", "AIR BAGS:FRONTAL"),
            recall("23V858000", "FUEL SYSTEM, GASOLINE"),
            recall("25V422000", "POWER TRAIN:AUTOMATIC TRANSMISSION"),
        ]
    )
    report = build(drafts=[], vehicle=vehicle)
    assert "3 recall campaign(s) are on record" in report.verdict.headline
    assert len(report.vehicle.recalls) == 3  # type: ignore[union-attr]


# ---------------------------------------------------------- the systems table --


def test_a_recall_does_not_put_a_system_row_into_attention() -> None:
    """D-021, applied to the table rather than only to the score.

    A recall campaign carries confidence 1.0 - confidence that the campaign
    exists. Grouped into the systems table it rendered the transmission row as
    "attention, 1.0" on a car nothing had observed a transmission fault on, and
    the teaser turned that into "Something was found here."
    """
    report = build(
        drafts=[
            draft(
                finding_id="recall_1",
                finding_type="open_recall",
                system="transmission",
                severity="major",
                confidence=1.0,
            )
        ]
    )
    row = next(r for r in report.systems if r.system == "transmission")
    assert row.status == "cannot_determine"
    assert row.finding_ids == []
    assert row.confidence is None
    # The campaign is still in the report, in the section that is about the model.
    assert any(f.type == "open_recall" for f in report.findings)


def test_a_vehicle_level_finding_still_drives_its_row() -> None:
    report = build(drafts=[draft(system="engine", severity="minor", confidence=0.62)])
    row = next(r for r in report.systems if r.system == "engine")
    assert row.status == "attention"
    assert row.confidence == 0.62
    assert row.finding_ids == ["f1"]


def test_a_recall_does_not_outrank_the_observation_in_a_row_statement() -> None:
    """The engine row led with a recall title over the fluid leak on this car."""
    report = build(
        drafts=[
            draft(finding_id="obs", system="engine", severity="minor", confidence=0.6),
            draft(
                finding_id="recall_1",
                finding_type="open_recall",
                system="engine",
                severity="major",
                confidence=1.0,
            ),
        ]
    )
    row = next(r for r in report.systems if r.system == "engine")
    assert row.statement == "exterior_damage on the engine"
    assert row.finding_ids == ["obs"]


# ----------------------------------------------------- the negotiation script --


def test_the_script_never_puts_a_shop_quote_in_the_buyers_mouth() -> None:
    """No shop was called. The band is this analysis's own estimate.

    The script used to write "a shop quoted that kind of work at roughly $600 to
    $900" - a provenance that does not exist, scripted for a buyer to assert to
    a seller's face.
    """
    report = build(drafts=[draft(cost=CostBand(low=600, high=900))])
    said = " ".join(beat.say for beat in report.negotiation_script)
    assert "shop quoted" not in said
    assert "its own estimate, not a quote" in said
    assert "$600 to $900" in said


# ------------------------------------------------------------- LAW 4's switch --


def test_a_measured_and_failing_type_does_not_reach_the_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LAW 4 had a switch that governed nothing.

    `enabled_for_paid` was read by the gate table and the accuracy statement -
    by the things that *describe* the gate - and by nothing in the report path.
    A type measured at 0.40 against a 0.85 threshold printed "NO / below gate"
    on the console and shipped in the paid dossier unchanged.
    """
    failing = replace(registry.FINDING_TYPES["exterior_damage"], measured_precision=0.40, n=200)
    monkeypatch.setitem(registry.FINDING_TYPES, "exterior_damage", failing)

    report = build(
        drafts=[
            draft(finding_id="withheld", finding_type="exterior_damage"),
            draft(finding_id="kept", finding_type="fluid_leak_indicator", system="engine"),
        ]
    )
    ids = {f.id for f in report.findings}
    assert "withheld" not in ids
    assert "kept" in ids


def test_a_withheld_type_is_named_rather_than_silently_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A gap the buyer cannot see reads as an absence of problems."""
    failing = replace(registry.FINDING_TYPES["exterior_damage"], measured_precision=0.40, n=200)
    monkeypatch.setitem(registry.FINDING_TYPES, "exterior_damage", failing)

    report = build(drafts=[draft(finding_id="withheld")])
    withheld_lines = [
        line for line in report.verdict.could_not_assess if "Exterior damage" in line
    ]
    assert withheld_lines, report.verdict.could_not_assess
    assert "0.40" in withheld_lines[0]
    assert "n=200" in withheld_lines[0]
    assert "0.85" in withheld_lines[0]


def test_an_unmeasured_type_still_ships_under_the_D032_disclosure() -> None:
    """ "Not measured" and "measured and failed" are different states.

    Filtering on unmeasured would empty every report this product can currently
    produce, while telling the buyer less than the generated accuracy statement
    on the checkout page already does.
    """
    assert registry.FINDING_TYPES["exterior_damage"].measured_precision is None
    report = build(drafts=[draft()])
    assert [f.id for f in report.findings] == ["f1"]
    assert registry.withheld_types() == {}


def test_a_withheld_type_cannot_arrive_as_a_referral_either(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate is applied before the safety clamp, not after.

    A referral built on a measurement we know to be wrong is the same claim in a
    softer voice, and it would land on the one part of the report a buyer is
    told to act on.
    """
    failing = replace(registry.FINDING_TYPES["rust_corrosion"], measured_precision=0.10, n=300)
    monkeypatch.setitem(registry.FINDING_TYPES, "rust_corrosion", failing)

    report = build(
        drafts=[
            draft(
                finding_id="frame",
                finding_type="rust_corrosion",
                system="structure",
                severity="critical",
            )
        ]
    )
    assert report.mechanic_referrals == []
    assert report.findings == []


# ------------------------------------------------------------------- the clock --


def test_the_clock_is_read_once_for_the_whole_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two calls to now() put two different moments in one report.

    Pricing computes staleness against `as_of` and the report is stamped with
    `generated_at`. Both came from their own call to the clock, so a live run
    classified a comparable listing as stale relative to a moment that was not
    the report's own timestamp - and the two figures in one document did not
    agree.
    """
    calls = []
    real = dossier._default_generated_at

    def counted(mode: str) -> str:
        calls.append(mode)
        return real(mode)

    monkeypatch.setattr(dossier, "_default_generated_at", counted)
    # No explicit timestamp: this is the path that reads the clock.
    build_report(
        inspection_id="insp_test",
        report_id="rpt_test",
        mode="fixture",
        assets=[photo()],
        drafts=[],
        vehicle=None,
        audio=None,
        walkaround=None,
        asking_price_usd=None,
        comps=[],
        subject_mileage=None,
        meter=CostMeter(mode="fixture"),
        examined_systems=set(),
    )
    assert calls == ["fixture"], f"the clock was read {len(calls)} times"
