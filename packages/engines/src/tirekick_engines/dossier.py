"""The dossier - joins every engine's output into one report.

Two things happen here that happen nowhere else: the safety clamp is applied
(LAW 2), and the systems table is built. The systems table is where a report most
easily becomes dishonest, because an empty row looks like a clean row. So a system
we have no coverage for is rendered `cannot_determine`, never `no_issues_visible`,
and the distinction is driven by which views actually arrived rather than by
whether an engine happened to say anything.
"""

from __future__ import annotations

from datetime import UTC, datetime

from . import registry
from .cogs import CostMeter
from .coverage import compute_coverage
from .engines import audio as audio_engine
from .engines import data as data_engine
from .engines import pricing as pricing_engine
from .models import (
    REPORT_BANNER,
    Asset,
    AudioTrack,
    Comp,
    Coverage,
    DraftFinding,
    Finding,
    PriceCheck,
    Report,
    ScriptBeat,
    SystemKey,
    SystemRow,
    VehicleRecord,
    Verdict,
    ViewClass,
    WalkaroundTrack,
)
from .safety import ALL_SYSTEMS, apply_safety_law, could_not_assess_lines, is_locked

#: Which views must be present before we are willing to say "no issues visible"
#: about a system. Absent these, the row reads `cannot_determine`.
SYSTEM_VIEW_REQUIREMENTS: dict[str, tuple[ViewClass, ...]] = {
    "exterior": (
        "exterior_front",
        "exterior_rear",
        "exterior_side_left",
        "exterior_side_right",
    ),
    "interior": ("interior_front",),
    "engine": ("engine_bay",),
    "tires": ("tire",),
    "electrical": ("dash",),
    "glass": ("exterior_front",),
    "documentation": ("vin_plate",),
    # No view lets us say anything reassuring about these, so they can only ever
    # be `attention` (if a finding lands) or `cannot_determine`.
    "transmission": (),
    "suspension": (),
    "fluids": (),
}

#: Severity weights for the red-flag score. Set once, here, so the number means the
#: same thing in every report. BRAND.md forbids rendering it without its caveats.
_SEVERITY_WEIGHT = {"info": 0, "minor": 6, "major": 18, "critical": 34}

#: The frozen clock for fixture runs (D-011). Any fixed value would do; this one
#: is obviously not a real generation time, which is the point.
FIXTURE_GENERATED_AT = "2026-01-01T00:00:00Z"


def _default_generated_at(mode: str) -> str:
    """Fixture runs are byte-reproducible; live runs are stamped with the real time.

    A cached run that stamps a live wall clock is not reproducible in the way
    D-009 claims: the golden report churns on every run, and the snapshot test
    guarding it degrades into noise that gets regenerated without being read.
    An explicit --generated-at still overrides this in either mode.
    """
    if mode == "fixture":
        return FIXTURE_GENERATED_AT
    return datetime.now(UTC).isoformat()


#: Findings that describe the model rather than this particular vehicle.
#:
#: They are kept out of the red-flag score. A recall campaign is filed against
#: every car of a model year, is free to remedy at any dealer, and may well have
#: been done on this one years ago - NHTSA does not publish per-VIN status, so we
#: cannot know. Scoring them like observed damage produced a 2013 Accord at
#: 100/100 on the strength of five campaigns and a check-engine lamp, which reads
#: as "this car is a wreck" and is not what the evidence says. They are still
#: reported in full, at their own severity, in their own section. See D-021.
MODEL_LEVEL_TYPES: frozenset[str] = frozenset({"open_recall", "complaint_pattern"})


def _vehicle_level(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.type not in MODEL_LEVEL_TYPES]


def _red_flag_score(findings: list[Finding], coverage: Coverage) -> int:
    """Confidence-weighted severity over findings about this vehicle, capped at 100.

    Deliberately not a grade and deliberately not an average: averaging would let
    a pile of minor findings dilute a critical one. Low coverage does not lower
    the score - a thin report is not a good report - and the coverage block is
    rendered next to it so the two are read together.

    Model-level federal records are excluded; see MODEL_LEVEL_TYPES.
    """
    del coverage  # read alongside the score in the report, not folded into it
    total = sum(_SEVERITY_WEIGHT[f.severity] * f.confidence for f in _vehicle_level(findings))
    return min(100, int(round(total)))


def _headline(score: int, findings: list[Finding], vehicle: VehicleRecord | None) -> str:
    """One sentence about this car, plus a separate count for its model.

    The two are never added together. Conflating "we can see rust on this car"
    with "this model year has recall campaigns on file" is how a report starts
    overstating itself.

    The recall count comes from the federal record, not from the surviving
    findings. A campaign against a locked system - airbags, brakes, steering,
    structure - is converted to a mechanic referral by the safety clamp before
    this function ever sees it, so counting findings meant a car whose only
    campaign was an airbag recall reported "Nothing adverse was visible in the
    media provided." The most common recall category in the fleet was the one
    the headline could not mention.
    """
    observed = _vehicle_level(findings)
    recall_count = len(vehicle.recalls) if vehicle is not None else 0
    tail = (
        f" Separately, {recall_count} recall campaign(s) are on record for this "
        f"model year - free to fix, and worth one phone call to a dealer."
        if recall_count
        else ""
    )

    critical = [f for f in observed if f.severity == "critical"]
    major = [f for f in observed if f.severity == "major"]
    # `info` is a reading, not a fault: an odometer value is not a minor finding
    # and must not be counted as one in the sentence that leads the report.
    minor = [f for f in observed if f.severity == "minor"]
    if critical:
        return f"{len(critical)} critical finding(s) visible in the media provided.{tail}"
    if major:
        return f"{len(major)} finding(s) that are likely to cost money.{tail}"
    if minor:
        return (
            f"{len(minor)} minor finding(s) visible; nothing major in what we "
            f"could see.{tail}"
        )
    if observed:
        return (
            f"Nothing adverse was visible in the media provided. "
            f"{len(observed)} reading(s) were recorded.{tail}"
        )
    if score == 0:
        return f"Nothing adverse was visible in the media provided.{tail}"
    return f"Analysis complete.{tail}"


def _build_systems(
    findings: list[Finding],
    coverage: Coverage,
    has_audio_clip: bool,
    examined_systems: set[str],
) -> list[SystemRow]:
    received = set(coverage.received_views)
    rows: list[SystemRow] = []

    # Only findings about THIS car may set a system's status. A recall campaign
    # is filed against every car of a model year and carries confidence 1.0 -
    # confidence that the campaign exists, not that anything is wrong with the
    # car in front of the buyer. Grouping it here rendered the transmission row
    # as "attention, 1.0" on a vehicle nothing had observed a transmission fault
    # on, which is the conflation D-021 forbids two paragraphs above this one.
    # The campaigns are still reported in full, in the section that is about the
    # model rather than the car.
    by_system: dict[str, list[Finding]] = {}
    for f in _vehicle_level(findings):
        by_system.setdefault(f.system, []).append(f)

    for system in ALL_SYSTEMS:
        if is_locked(system):
            # LAW 2. Identical in every report TIREKICK will ever emit.
            from .models import LOCKED_SYSTEM_STATEMENT

            rows.append(
                SystemRow(
                    system=system,
                    status="locked_mechanic_required",
                    statement=LOCKED_SYSTEM_STATEMENT,
                    finding_ids=[],
                    confidence=None,
                )
            )
            continue

        attached = by_system.get(system, [])
        if attached:
            rows.append(
                SystemRow(
                    system=system,
                    status="attention",
                    statement=_attention_statement(attached),
                    finding_ids=[f.id for f in attached],
                    confidence=round(max(f.confidence for f in attached), 2),
                )
            )
            continue

        required = SYSTEM_VIEW_REQUIREMENTS.get(system, ())
        # Two conditions, both necessary, before we will say "no issues visible":
        # the views arrived, AND an analysis pass that could have found something
        # about this system actually ran. Coverage alone is not enough - a system
        # nothing examined is unassessed, however many photos we received.
        covered = (
            bool(required)
            and all(v in received for v in required)
            and system in examined_systems
        )

        if system == "engine" and has_audio_clip and not covered:
            rows.append(
                SystemRow(
                    system=system,
                    status="cannot_determine",
                    statement=(
                        "An audio clip was provided but engine audio analysis is "
                        "not yet enabled, and no engine bay photo was received."
                    ),
                    finding_ids=[],
                    confidence=None,
                )
            )
            continue

        if covered:
            rows.append(
                SystemRow(
                    system=system,
                    status="no_issues_visible",
                    statement=(
                        "No issues visible in the media provided. This is not a "
                        "clearance - it means nothing adverse was visible in "
                        "these photographs."
                    ),
                    finding_ids=[],
                    confidence=None,
                )
            )
        else:
            rows.append(
                SystemRow(
                    system=system,
                    status="cannot_determine",
                    statement=_cannot_determine_statement(
                        system, required, received, examined_systems
                    ),
                    finding_ids=[],
                    confidence=None,
                )
            )

    return rows


def _attention_statement(findings: list[Finding]) -> str:
    worst = max(findings, key=lambda f: _SEVERITY_WEIGHT[f.severity])
    if len(findings) == 1:
        return worst.title
    return f"{worst.title} (and {len(findings) - 1} more)"


def _cannot_determine_statement(
    system: str,
    required: tuple[ViewClass, ...],
    received: set[ViewClass],
    examined_systems: set[str],
) -> str:
    if not required:
        return (
            f"Cannot be determined from photographs, video, or audio. Assessing "
            f"{system} requires a test drive or a lift."
        )
    missing = [v.replace("_", " ") for v in required if v not in received]
    if missing:
        return (
            f"Cannot be determined - the media provided did not include: "
            f"{', '.join(missing)}."
        )
    if system not in examined_systems:
        return (
            f"Cannot be determined - TIREKICK has no analysis pass that assesses "
            f"{system} from photographs. The media may show it; we did not examine it."
        )
    return "Cannot be determined from the media provided."


def _history_limits(assets: list[Asset], record: VehicleRecord | None) -> list[str]:
    """What the history side of the report could not reach.

    The absence of a document is not evidence of anything, so it never becomes a
    finding (LAW 1). It belongs here, in the block that leads the verdict, where a
    thin history reads as thin rather than as clean.
    """
    lines = [
        "Title status - TIREKICK queries no title registry. Any title brand named "
        "in this report was read out of paperwork you uploaded. Confirm the title "
        "with your state motor vehicle agency before you buy."
    ]

    documents = [a for a in assets if a.kind == "document"]
    if not documents:
        lines.append(
            "Vehicle history - no history report or service records were provided, "
            "so there was nothing to read. This is not a clean history; it is no "
            "history."
        )
    unreadable = [a for a in documents if not a.path.lower().endswith((".txt", ".md", ".text"))]
    if unreadable:
        lines.append(
            f"{len(unreadable)} uploaded document(s) could not be read as text and "
            f"were not scanned. Reading scanned or photographed documents is not "
            f"enabled yet."
        )
    if record is not None and not record.vin_valid:
        lines.append(
            "VIN decode - the VIN provided did not pass its check digit, so no "
            "federal record was retrieved. Everything a VIN would have told us is "
            "missing from this report."
        )
    return lines


def _seller_questions(findings: list[Finding], record: VehicleRecord | None) -> list[str]:
    questions = [f.seller_question for f in findings if f.seller_question]
    # Questions that are worth asking about any used car, and that our inputs can
    # never answer for the buyer.
    questions.extend(
        [
            "Do you have service records? Can I see them before I come out?",
            "Has this car been in any accident, reported or not?",
            "Are you the titleholder, and is the title in hand and clear?",
            "Can I take it to my mechanic for a pre-purchase inspection?",
        ]
    )
    if record is not None and record.recalls:
        questions.append(
            "Has any recall work been done on this car? A dealer will check by VIN "
            "and do outstanding recall work free - can you show me the paperwork?"
        )
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    ordered: list[str] = []
    for q in questions:
        if q not in seen:
            seen.add(q)
            ordered.append(q)
    return ordered


def _negotiation_script(
    findings: list[Finding], price: PriceCheck | None, coverage: Coverage
) -> list[ScriptBeat]:
    """A script that never asks the buyer to overstate what we found."""
    beats: list[ScriptBeat] = [
        ScriptBeat(
            beat="Open by naming what you did",
            say=(
                "I ran the photos and the VIN through an AI analysis before coming "
                "out. It flagged a few things I want to look at with you."
            ),
        )
    ]

    costed = [f for f in findings if f.estimated_cost_usd is not None]
    for f in costed[:3]:
        assert f.estimated_cost_usd is not None
        # The band is ours, and the script says so. It used to put "a shop quoted
        # that kind of work at roughly $600 to $900" in the buyer's mouth - a
        # provenance that does not exist, scripted for them to assert to a
        # stranger's face. No shop was called. The number is a rough band this
        # analysis attached, and a seller is entitled to hear it described as
        # what it is.
        beats.append(
            ScriptBeat(
                beat=f"Raise: {f.title}",
                say=(
                    f"The analysis flagged {f.title.lower()}, and put a rough band "
                    f"of ${f.estimated_cost_usd.low:,.0f} to "
                    f"${f.estimated_cost_usd.high:,.0f} on that kind of work - its "
                    f"own estimate, not a quote. I'd want a shop to price it "
                    f"properly. Can we talk about the price with that in mind?"
                ),
            )
        )

    if price is not None and price.verdict == "above_range":
        beats.append(
            ScriptBeat(
                beat="Anchor on the comps",
                say=(
                    f"I looked at comparable listings and they support roughly "
                    f"${price.fair_range_usd.low:,.0f} to "
                    f"${price.fair_range_usd.high:,.0f} for this car in this "
                    f"condition. Here are the listings I looked at. Can you meet me "
                    f"in that range?"
                ),
            )
        )

    beats.append(
        ScriptBeat(
            beat="Protect yourself on what the analysis could not see",
            say=(
                "The analysis was clear that it can't assess brakes, airbags, frame, "
                "or steering from photos. I'd like to take it to my mechanic before "
                "we finalize. If that's not possible, I understand, but then I'd need "
                "the price to reflect the risk I'm taking on."
            ),
        )
    )

    if coverage.score < 0.6:
        beats.append(
            ScriptBeat(
                beat="Ask for what you did not get to see",
                say=(
                    "I only had a few photos to work from. Can you send me shots of "
                    "the areas I'm missing, or walk me around it when I get there?"
                ),
            )
        )

    beats.append(
        ScriptBeat(
            beat="Be willing to leave",
            say=("I appreciate your time. Let me think it over and I'll call you " "tomorrow."),
        )
    )
    return beats


def build_report(
    *,
    inspection_id: str,
    report_id: str,
    mode: str,
    assets: list[Asset],
    drafts: list[DraftFinding],
    vehicle: VehicleRecord | None,
    audio: AudioTrack | None,
    walkaround: WalkaroundTrack | None,
    asking_price_usd: float | None,
    comps: list[Comp],
    subject_mileage: int | None,
    meter: CostMeter,
    examined_systems: set[str],
    generated_at: str | None = None,
) -> tuple[Report, list[str]]:
    """Assemble the report. Returns it alongside the safety clamp log.

    The clamp log is returned rather than swallowed so that every suppressed
    finding is visible to us on the run, even though it is invisible to the buyer.
    """
    coverage = compute_coverage(assets)
    stamped_at = generated_at or _default_generated_at(mode)

    # LAW 4 - a type that was measured and failed does not reach a paid report.
    # Applied before the safety clamp so a withheld type cannot arrive as a
    # referral either: the gate is about whether we can tell the difference
    # between a real defect and a false one, and a referral built on a
    # measurement we know to be wrong is the same claim in a softer voice.
    withheld = registry.withheld_types()
    drafts = [d for d in drafts if d.type not in withheld]

    # LAW 2 - nothing reaches the report without passing through here.
    safety = apply_safety_law(drafts)
    findings: list[Finding] = safety.findings

    systems = _build_systems(
        findings, coverage, audio_engine.has_audio(assets), examined_systems
    )
    score = _red_flag_score(findings, coverage)

    could_not_assess = could_not_assess_lines()
    # A withheld type is a gap in this report, and it is named in the block that
    # leads the verdict rather than left as a silence the buyer reads as absence.
    could_not_assess.extend(withheld.values())
    if coverage.missing_views:
        could_not_assess.append(
            f"{len(coverage.missing_views)} standard view(s) were not provided: "
            f"{', '.join(v.replace('_', ' ') for v in coverage.missing_views)}."
        )
    if audio_engine.has_audio(assets):
        could_not_assess.append(
            audio.claims_statement if audio is not None else audio_engine.P0_STATEMENT
        )
    if audio is not None and not audio.usable:
        could_not_assess.extend(audio.quality_problems)
    could_not_assess.extend(_history_limits(assets, vehicle))
    if walkaround is not None:
        # What was discarded from the video belongs next to the conclusions, not
        # buried in a media section. A report that analysed 5 frames of a 40-frame
        # walkaround has a coverage gap the buyer cannot see otherwise.
        could_not_assess.append(walkaround.statement)

    price = pricing_engine.build_price_check(
        asking_price_usd=asking_price_usd,
        comps=comps,
        subject_mileage=subject_mileage,
        findings=findings,
        decoded=vehicle.decoded if vehicle is not None else None,
        as_of=stamped_at,
    )

    for asset in assets:
        meter.record_storage(asset.bytes)

    report = Report(
        report_id=report_id,
        inspection_id=inspection_id,
        # One clock reading for the whole report. Called twice, a live run gave
        # pricing a staleness cutoff that was not the report's own timestamp.
        generated_at=stamped_at,
        mode=mode,  # type: ignore[arg-type]
        banner=REPORT_BANNER,
        vehicle=vehicle,
        audio=audio,
        walkaround=walkaround,
        assets=assets,
        coverage=coverage,
        verdict=Verdict(
            red_flag_score=score,
            headline=_headline(score, findings, vehicle),
            could_not_assess=could_not_assess,
            summary=(
                f"{coverage.statement} Red-flag score {score}/100, which reflects "
                f"the severity and confidence of what was visible on this vehicle "
                f"- not the condition of the vehicle overall. Recalls and owner "
                f"complaint patterns describe the model rather than this car, so "
                f"they are reported separately and are not counted in the score."
            ),
        ),
        findings=findings,
        systems=systems,
        mechanic_referrals=safety.referrals,
        price=price,
        seller_questions=_seller_questions(findings, vehicle),
        negotiation_script=_negotiation_script(findings, price, coverage),
        cost=meter.to_model(),
        contains_synthetic_media=any(a.synthetic for a in assets),
    )
    return report, safety.clamp_log


__all__ = ["SYSTEM_VIEW_REQUIREMENTS", "SystemKey", "build_report", "data_engine"]
