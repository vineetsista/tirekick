"""LAW 2 - the safety-critical clamp.

Brakes, restraints, frame/structure, and steering are never cleared remotely.

This is deliberately not a prompt instruction. Prompts are probabilistic; this is
not (DECISIONS.md D-004). Engines may draft whatever they draft. Everything passes
through `apply_safety_law` before it can become a report, and what comes out the
other side cannot contain a verdict on a locked system - regardless of what the
model said, how confident it was, or how obviously fine the car looked.

The one asymmetry (DECISIONS.md D-005): an *observation* near a locked system
survives as a `MechanicReferral`, because warning a buyer is not the same as
clearing them. It loses its severity, its confidence, and its status as a finding.
We can raise an alarm. We cannot sound an all-clear.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import (
    LOCKED_SYSTEM_STATEMENT,
    LOCKED_SYSTEMS,
    DraftFinding,
    Finding,
    MechanicReferral,
    SystemKey,
    SystemRow,
)

ALL_SYSTEMS: tuple[SystemKey, ...] = (
    "exterior",
    "interior",
    "engine",
    "transmission",
    "brakes",
    "suspension",
    "steering",
    "tires",
    "electrical",
    "restraints",
    "structure",
    "fluids",
    "glass",
    "documentation",
)

# Buyer-facing names for the locked systems, used in the "could not assess" block.
LOCKED_SYSTEM_LABELS: dict[str, str] = {
    "brakes": "Brakes",
    "restraints": "Airbags and restraints",
    "structure": "Frame and structural integrity",
    "steering": "Steering",
}

# What a locked-system observation gets converted into. Phrased as a question for a
# mechanic, never as a conclusion about the vehicle.
_REFERRAL_ASK = (
    "Ask an independent mechanic to inspect this on a lift before you buy. "
    "TIREKICK cannot assess it from photos, video, or audio."
)


def is_locked(system: str) -> bool:
    return system in LOCKED_SYSTEMS


@dataclass
class SafetyResult:
    """What survived the clamp, and a record of what did not."""

    findings: list[Finding] = field(default_factory=list)
    referrals: list[MechanicReferral] = field(default_factory=list)
    #: Human-readable log of every clamp action. Printed on every run so that a
    #: suppressed finding is visible to us even though it is invisible to the buyer.
    clamp_log: list[str] = field(default_factory=list)


def _is_adverse(draft: DraftFinding) -> bool:
    """Does this draft warn about something, or does it clear something?

    Only warnings survive as referrals. Anything reassuring is dropped outright -
    that is the entire point of the law. `info` severity is treated as
    non-adverse because an informational note about brakes is, in practice, a
    model telling the buyer they look fine.
    """
    return draft.severity in ("minor", "major", "critical")


def apply_safety_law(drafts: list[DraftFinding]) -> SafetyResult:
    """Split drafts into publishable findings and mechanic referrals.

    Every draft touching a locked system leaves as either a referral (if it warns)
    or nothing at all (if it reassures). None leave as findings.
    """
    result = SafetyResult()

    for draft in drafts:
        if not is_locked(draft.system):
            result.findings.append(Finding(**draft.model_dump()))
            continue

        if not _is_adverse(draft):
            result.clamp_log.append(
                f"LAW 2: dropped {draft.id!r} ({draft.system}, severity="
                f"{draft.severity}, confidence={draft.confidence:.2f}) - a locked "
                f"system is never cleared remotely."
            )
            continue

        result.referrals.append(
            MechanicReferral(
                id=f"ref_{draft.id}",
                system=draft.system,
                # The observation is kept; the judgment is stripped.
                observation=draft.detail,
                ask=_REFERRAL_ASK,
                evidence=draft.evidence,
            )
        )
        result.clamp_log.append(
            f"LAW 2: converted {draft.id!r} ({draft.system}, severity="
            f"{draft.severity}) to a mechanic referral - observation kept, "
            f"severity and confidence stripped."
        )

    return result


def locked_system_rows() -> list[SystemRow]:
    """The four rows that are identical in every report TIREKICK will ever emit."""
    return [
        SystemRow(
            system=system,  # type: ignore[arg-type]
            status="locked_mechanic_required",
            statement=LOCKED_SYSTEM_STATEMENT,
            finding_ids=[],
            confidence=None,
        )
        for system in ("brakes", "restraints", "structure", "steering")
    ]


def could_not_assess_lines() -> list[str]:
    """Leads the verdict block. LIABILITY section 9."""
    return [
        f"{label} - not remotely verifiable, independent mechanic required."
        for label in LOCKED_SYSTEM_LABELS.values()
    ]
