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

For nine phases it also kept the model's sentence, which meant it could sound an
all-clear after all - a draft tagged `minor` and reading "the pads have plenty of
life left" became a referral whose text was that sentence, verbatim, in front of
the buyer. The clamp was deterministic about *whether* to publish and entirely
credulous about *what*. So a referral built from a generated draft now says only
what this pipeline knows: which locked system, which asset, and that the sentence
is being withheld. The evidence goes out; the prose does not.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import (
    LOCKED_SYSTEM_STATEMENT,
    LOCKED_SYSTEMS,
    AudioSegmentEvidence,
    DataRecordEvidence,
    DocumentExcerptEvidence,
    DraftFinding,
    Evidence,
    Finding,
    ImageRegionEvidence,
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


#: Engines whose prose about a locked system may be printed for the buyer as it
#: was written, because a person in this repository wrote it.
#:
#: Default-deny, and listed by hand rather than derived, because the failure it
#: prevents is a new engine that calls a model and inherits permission to publish
#: what the model says about brakes simply by existing. Anything not named here -
#: `vision`, `audio`, and whatever is added next - is treated as a stranger's
#: sentence and withheld.
#:
#: Membership is not a matter of taste: an engine that loads a prompt is talking
#: to a model, and prompts live one directory per engine under `prompts/`. The
#: test in test_laws.py checks this list against those directories, so adding an
#: engine here that has prompts fails rather than quietly widens the hole.
SELF_AUTHORED_ENGINES: frozenset[str] = frozenset({"data", "pricing"})

#: What replaces a caption that came from a model, on evidence attached to a
#: locked system. The box and the asset id are kept - they are the citation, and
#: they are checkable. The words are not.
_CAPTION_WITHHELD = (
    "Flagged here for your mechanic. The wording that came with it is not published."
)


def is_locked(system: str) -> bool:
    return system in LOCKED_SYSTEMS


def _wrote_its_own_prose(draft: DraftFinding) -> bool:
    return draft.engine in SELF_AUTHORED_ENGINES


def _where_to_look(evidence: Evidence) -> str:
    """Name the medium a flag sits in, in the pipeline's own words.

    Deliberately built from identifiers and numbers rather than from the caption
    beside them: on a model-authored draft the caption is the model's sentence
    too, and it is rendered under the box in the report gallery, which makes it
    exactly as capable of clearing a brake system as the observation is.
    """
    if isinstance(evidence, ImageRegionEvidence):
        return f"a boxed region of {evidence.asset_id}"
    if isinstance(evidence, AudioSegmentEvidence):
        return (
            f"{evidence.asset_id}, between {evidence.start_sec:.1f}s and "
            f"{evidence.end_sec:.1f}s"
        )
    if isinstance(evidence, DocumentExcerptEvidence):
        return f"a line quoted from {evidence.asset_id}"
    if isinstance(evidence, DataRecordEvidence):
        return f"{evidence.source} record {evidence.record_id}"
    raise AssertionError(f"unhandled evidence kind: {type(evidence).__name__}")


def _withheld_observation(draft: DraftFinding) -> str:
    """What the buyer reads instead of the model's sentence about a locked system.

    THE FAILURE THIS PREVENTS, WRITTEN OUT
    --------------------------------------
    A vision model returns system="brakes", severity="minor", and the detail "the
    pads appear to have plenty of life left; nothing here suggests the braking
    system needs work". `_is_adverse` sees "minor", calls it a warning, and the
    clamp copies that sentence into a `MechanicReferral.observation`, which the
    report prints under a heading that says a mechanic is required. The buyer has
    just been given a remote all-clear on the braking system. LAW 2 exists for
    that one sentence and it went out untouched.

    Reading the sentence and deciding whether it reassures is not available to
    us. That is a second probabilistic filter bolted onto a control that is
    deterministic on purpose (D-004), and it fails the same way the model does,
    silently and on the case nobody wrote a phrase for. `copy_rules.BANNED`
    holds nine exact phrasings and catches nothing about pads, rotors, or life
    left. So the sentence is not published. Not filtered, not softened - not
    published, whatever it says.

    The two sentences above used to quote the banned phrasings verbatim, and
    the copy scan caught this file - the scan covers engine modules, and it was
    right to: a phrase is not safe here because the surrounding paragraph
    disapproves of it.

    What is not withheld is the evidence. The photograph ships, the box is drawn
    on it, the asset id is named here, and a mechanic works from those rather
    than from a caption. The buyer loses a sentence and keeps everything that
    sentence was about.
    """
    label = LOCKED_SYSTEM_LABELS[draft.system]
    where = ", and in ".join(_where_to_look(e) for e in draft.evidence)
    return (
        f"{label}: the {draft.engine} engine flagged something in {where}. What it "
        f"said about it is not printed here. A sentence generated about a locked "
        f"system can read as a warning or as an all-clear, TIREKICK cannot reliably "
        f"tell the two apart, and publishing the reassuring kind is the outcome "
        f"this product refuses to risk - so neither kind is published. What it "
        f"flagged is not withheld: it is cited above and shipped with this report. "
        f"Look at it, and show it to the mechanic."
    )


@dataclass
class SafetyResult:
    """What survived the clamp, and a record of what did not."""

    findings: list[Finding] = field(default_factory=list)
    referrals: list[MechanicReferral] = field(default_factory=list)
    #: Human-readable log of every clamp action. Printed on every run so that a
    #: suppressed finding is visible to us even though it is invisible to the buyer.
    clamp_log: list[str] = field(default_factory=list)


def _is_adverse(draft: DraftFinding) -> bool:
    """Is this draft worth sending anyone to a mechanic over?

    `info` is dropped because an informational note about brakes is, in practice,
    a model telling the buyer they look fine, and a referral for it would waste a
    mechanic's time and the buyer's attention on nothing.

    What this function is NOT is LAW 2's defence against an all-clear. It used to
    claim it was - the docstring said "anything reassuring is dropped outright" -
    while reading `severity`, a label chosen by the same model that wrote the
    reassurance. Tag "the pads have plenty of life left" as `minor` and it sailed
    through here and was printed word for word. The all-clear is stopped now by
    not publishing generated prose about a locked system at all; see
    `_withheld_observation`. This is a triage threshold, and nothing more.
    """
    return draft.severity in ("minor", "major", "critical")


def apply_safety_law(drafts: list[DraftFinding]) -> SafetyResult:
    """Split drafts into publishable findings and mechanic referrals.

    Every draft touching a locked system leaves as either a referral or nothing
    at all. None leave as findings.

    It used to say "a referral if it warns, nothing if it reassures", which was
    the same overclaim `_is_adverse` was making one function down: the split is
    on severity, and severity comes from whoever wrote the draft. What actually
    holds the law up is that a referral built from generated text carries none of
    that text - so a draft that reassures becomes a referral saying a mechanic
    should look, which is the wrong outcome for a clean car and the survivable
    one for a wrecked one (D-017).
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

        # Whose sentence this is decides whether it can be printed. Ours can:
        # it was written here, reviewed in a diff, and scanned for banned
        # language. A model's cannot, in either direction (D-004).
        ours = _wrote_its_own_prose(draft)
        result.referrals.append(
            MechanicReferral(
                id=f"ref_{draft.id}",
                system=draft.system,
                observation=draft.detail if ours else _withheld_observation(draft),
                ask=_REFERRAL_ASK,
                evidence=(
                    draft.evidence
                    if ours
                    else [
                        e.model_copy(update={"caption": _CAPTION_WITHHELD})
                        for e in draft.evidence
                    ]
                ),
            )
        )
        result.clamp_log.append(
            f"LAW 2: converted {draft.id!r} ({draft.system}, severity="
            f"{draft.severity}) to a mechanic referral - severity and confidence "
            f"stripped, "
            + (
                "observation kept (written by this pipeline)."
                if ours
                else f"generated prose withheld ({draft.engine} is not a "
                f"self-authoring engine); the detail it wrote was: {draft.detail!r}"
            )
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
