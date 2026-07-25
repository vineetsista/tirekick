"""Data engine - VIN decode, open recalls, complaint patterns.

P0 reads from the fixture cache. P1 replaces `_fetch` with live calls to NHTSA
vPIC and the NHTSA recalls/complaints API through net.get, which allowlists both
(LAW 3). The shape does not change when that happens: every fact carries a
DataRecordEvidence naming its source, its record id, and when it was retrieved,
because a database claim needs a citation exactly as much as a visual one does
(LAW 1).
"""

from __future__ import annotations

from typing import Any

from ..client import FixtureMissing, ModelClient
from ..models import (
    ComplaintSummary,
    ComponentCount,
    DataRecordEvidence,
    DecodedVehicle,
    DraftFinding,
    Recall,
    VehicleRecord,
)

VPIC_DECODE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}"
RECALLS_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"
COMPLAINTS_URL = "https://api.nhtsa.gov/complaints/complaintsByVehicle"


def mask_vin(vin: str) -> str:
    """LIABILITY section 6 - full VINs never appear on a shareable surface."""
    if len(vin) <= 6:
        return "*" * len(vin)
    return vin[:-6] + "******"


def _to_record(vin: str, payload: dict[str, Any]) -> VehicleRecord:
    decoded = payload["decoded"]
    complaints = payload.get("complaint_summary")
    return VehicleRecord(
        vin=vin,
        vin_masked=mask_vin(vin),
        decoded=DecodedVehicle(
            year=decoded.get("year"),
            make=decoded.get("make"),
            model=decoded.get("model"),
            trim=decoded.get("trim"),
            body_class=decoded.get("body_class"),
            engine=decoded.get("engine"),
            drive_type=decoded.get("drive_type"),
            plant_country=decoded.get("plant_country"),
        ),
        recalls=[
            Recall(
                campaign_number=r["campaign_number"],
                component=r["component"],
                summary=r["summary"],
                remedy=r.get("remedy", ""),
                report_received_date=r.get("report_received_date", ""),
            )
            for r in payload.get("recalls", [])
        ],
        complaint_summary=(
            ComplaintSummary(
                total=complaints["total"],
                top_components=[
                    ComponentCount(component=c["component"], count=c["count"])
                    for c in complaints.get("top_components", [])
                ],
            )
            if complaints
            else None
        ),
        source=payload["source"],
        retrieved_at=payload["retrieved_at"],
    )


def lookup(vin: str | None, client: ModelClient) -> VehicleRecord | None:
    if not vin:
        return None
    try:
        payload = client.call(
            engine="data",
            task="vin",
            subject=vin,
            prompt="",  # not a model call; the cache key shape is shared
        )
    except FixtureMissing:
        return None
    return _to_record(vin, payload)


def recall_findings(record: VehicleRecord | None) -> list[DraftFinding]:
    """One finding per open recall, each citing the federal record it came from.

    Severity is `major` for every open recall and is not model-judged: an
    unremedied manufacturer safety recall is a fact with a fixed meaning, and
    ranking them against each other would be us inventing a judgment.
    """
    if record is None:
        return []

    findings: list[DraftFinding] = []
    for recall in record.recalls:
        findings.append(
            DraftFinding(
                id=f"recall_{recall.campaign_number}",
                type="open_recall",
                # Recalls are reported under electrical/documentation-style systems
                # only when they are not locked; a recall naming a locked system is
                # routed to a mechanic referral by safety.apply_safety_law.
                system=_system_for(recall.component),
                title=f"Open recall {recall.campaign_number}: {recall.component}",
                detail=recall.summary,
                severity="major",
                confidence=1.0,
                confidence_basis=(
                    "Reported directly by NHTSA for this VIN. Not a model judgment."
                ),
                evidence=[
                    DataRecordEvidence(
                        source=record.source,
                        record_id=recall.campaign_number,
                        retrieved_at=record.retrieved_at,
                        caption=f"NHTSA recall {recall.campaign_number} - {recall.component}",
                    )
                ],
                seller_question=(
                    f"Has recall {recall.campaign_number} been performed? "
                    f"A dealer will do it free - ask for the paperwork."
                ),
                mechanic_check=None,
                engine="data",
            )
        )
    return findings


#: Maps an NHTSA component string onto our system keys. Deliberately coarse; when
#: it lands on a locked system, the clamp handles it.
_COMPONENT_HINTS: tuple[tuple[str, str], ...] = (
    ("AIR BAG", "restraints"),
    ("SEAT BELT", "restraints"),
    ("BRAKE", "brakes"),
    ("STEERING", "steering"),
    ("STRUCTURE", "structure"),
    ("FRAME", "structure"),
    ("ENGINE", "engine"),
    ("FUEL", "engine"),
    ("ELECTRICAL", "electrical"),
    ("EXTERIOR LIGHTING", "electrical"),
    ("SUSPENSION", "suspension"),
    ("TIRE", "tires"),
    ("POWER TRAIN", "transmission"),
    ("VISIBILITY", "glass"),
)


def _system_for(component: str) -> Any:
    upper = component.upper()
    for hint, system in _COMPONENT_HINTS:
        if hint in upper:
            return system
    return "documentation"
