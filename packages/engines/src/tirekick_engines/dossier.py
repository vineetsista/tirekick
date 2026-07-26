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

from .cogs import CostMeter
from .coverage import compute_coverage
from .engines import audio as audio_engine
from .engines import data as data_engine
from .engines import pricing as pricing_engine
from .models import (
    REPORT_BANNER,
    Asset,
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


def _red_flag_score(findings: list[Finding], coverage: Coverage) -> int:
    """Confidence-weighted severity, capped at 100.

    Deliberately not a grade and deliberately not an average: averaging would let
    a pile of minor findings dilute a critical one. Low coverage does not lower
    the score - a thin report is not a good report - and the coverage block is
    rendered next to it so the two are read together.
    """
    del coverage  # read alongside the score in the report, not folded into it
    total = sum(_SEVERITY_WEIGHT[f.severity] * f.confidence for f in findings)
    return min(100, int(round(total)))


def _headline(score: int, findings: list[Finding]) -> str:
    critical = [f for f in findings if f.severity == "critical"]
    major = [f for f in findings if f.severity == "major"]
    if critical:
        return f"{len(critical)} critical finding(s) visible in the media provided."
    if major:
        return f"{len(major)} finding(s) that are likely to cost money."
    if findings:
        return f"{len(findings)} minor finding(s) visible; nothing major in what we could see."
    if score == 0:
        return "Nothing adverse was visible in the media provided."
    return "Analysis complete."


def _build_systems(
    findings: list[Finding],
    coverage: Coverage,
    has_audio_clip: bool,
    examined_systems: set[str],
) -> list[SystemRow]:
    received = set(coverage.received_views)
    rows: list[SystemRow] = []

    by_system: dict[str, list[Finding]] = {}
    for f in findings:
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
            "Can you show me the dealer paperwork for the open recalls on this VIN?"
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
        beats.append(
            ScriptBeat(
                beat=f"Raise: {f.title}",
                say=(
                    f"The analysis flagged {f.title.lower()}. I'd want that looked "
                    f"at - a shop quoted that kind of work at roughly "
                    f"${f.estimated_cost_usd.low:,.0f} to "
                    f"${f.estimated_cost_usd.high:,.0f}. Can we talk about the price "
                    f"with that in mind?"
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

    # LAW 2 - nothing reaches the report without passing through here.
    safety = apply_safety_law(drafts)
    findings: list[Finding] = safety.findings

    systems = _build_systems(
        findings, coverage, audio_engine.has_audio(assets), examined_systems
    )
    score = _red_flag_score(findings, coverage)

    could_not_assess = could_not_assess_lines()
    if coverage.missing_views:
        could_not_assess.append(
            f"{len(coverage.missing_views)} standard view(s) were not provided: "
            f"{', '.join(v.replace('_', ' ') for v in coverage.missing_views)}."
        )
    if audio_engine.has_audio(assets):
        could_not_assess.append(audio_engine.P0_STATEMENT)

    price = pricing_engine.build_price_check(
        asking_price_usd=asking_price_usd,
        comps=comps,
        subject_mileage=subject_mileage,
        findings=findings,
    )

    for asset in assets:
        meter.record_storage(asset.bytes)

    report = Report(
        report_id=report_id,
        inspection_id=inspection_id,
        generated_at=generated_at or _default_generated_at(mode),
        mode=mode,  # type: ignore[arg-type]
        banner=REPORT_BANNER,
        vehicle=vehicle,
        assets=assets,
        coverage=coverage,
        verdict=Verdict(
            red_flag_score=score,
            headline=_headline(score, findings),
            could_not_assess=could_not_assess,
            summary=(
                f"{coverage.statement} Red-flag score {score}/100, which reflects "
                f"the severity and confidence of what was visible - not the "
                f"condition of the vehicle overall."
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
