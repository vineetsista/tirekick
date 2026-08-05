"""The free teaser: a projection of the report, not a redaction of it.

The distinction is the whole module. A teaser that ships the full report and
hides the findings behind a paywall in the browser is not a teaser - it is the
paid product with a `display: none` on it, readable by anyone who opens the
network tab. So this builds a genuinely smaller object. What is not in the
returned payload was never serialised, and there is a test that reads the teaser
JSON looking for every finding title in the report and fails if it finds one.

What the teaser keeps is deliberate, and it is roughly the opposite of what a
conversion-optimised teaser would keep.

It keeps **coverage in full** - which views arrived and which did not - because
that is what tells a buyer whether the thing they are about to pay for could
possibly answer their question. A report built on six photographs of the good
side is worth less, and they should know that before paying rather than after.

It keeps **the whole "could not assess" block**, including all four locked
systems. Those never move behind a paywall. Charging someone to find out that we
cannot assess their brakes would be indefensible.

It keeps **counts** - how many findings, at what severities - because a count is
the hook and it is honest. It drops every title, every detail, every confidence
basis, every box and every excerpt, because those are the product.

And it carries `accuracy_statement`, generated from the eval-gate registry rather
than written by hand, which today says that nothing has been measured. That
sentence is on the checkout page. See D-032.
"""

from __future__ import annotations

from .dossier import MODEL_LEVEL_TYPES
from .models import (
    LOCKED_SYSTEM_STATEMENT,
    LOCKED_SYSTEMS,
    Coverage,
    Finding,
    ImageRegionEvidence,
    Report,
    SeverityCount,
    SystemStatus,
    Teaser,
    TeaserSample,
    TeaserSystemRow,
)
from .registry import FINDING_TYPES
from .safety import is_locked

#: What a non-locked system row says in the teaser.
#:
#: The paid report puts the worst finding's title here, which is exactly the
#: thing being sold, so it cannot survive the projection. These are generic by
#: status and identical for every vehicle.
_STATUS_STATEMENTS: dict[SystemStatus, str] = {
    "no_issues_visible": (
        "Nothing adverse was visible in the media provided. That is not a "
        "clearance - it means nothing showed up in these photographs."
    ),
    "attention": "Something was found here. The full report says what, where, and how sure.",
    "cannot_determine": (
        "Could not be determined from the media provided. The full report says why."
    ),
    "locked_mechanic_required": LOCKED_SYSTEM_STATEMENT,
}

#: Severity order for the counts block, worst first.
_SEVERITIES = ("critical", "major", "minor", "info")


def accuracy_statement() -> str:
    """How much of this product has measured accuracy, from the registry.

    Generated rather than written, so it cannot drift from the gate table and
    cannot be quietly softened when it becomes commercially inconvenient. Today
    it is a sentence nobody would choose to put on a checkout page, which is a
    good sign that it is the honest one.
    """
    total = len(FINDING_TYPES)
    enabled = sum(1 for spec in FINDING_TYPES.values() if spec.enabled_for_paid)
    measured = sum(1 for spec in FINDING_TYPES.values() if spec.measured_precision is not None)

    if enabled == 0:
        return (
            f"None of the {total} finding types TIREKICK can produce has cleared "
            f"its accuracy threshold yet - {measured} have been measured at all. "
            f"That means no finding in this report has a published accuracy "
            f"number behind it. Everything is shown with its evidence so you can "
            f"judge it yourself, and the accuracy page explains exactly what has "
            f"and has not been tested."
        )
    return (
        f"{enabled} of {total} finding types have cleared their accuracy threshold "
        f"on a labelled test set. The rest are shown with their evidence and are "
        f"marked as unmeasured. Per-type precision and recall, including the "
        f"misses, are on the accuracy page."
    )


def _system_rows(report: Report) -> list[TeaserSystemRow]:
    rows: list[TeaserSystemRow] = []
    for row in report.systems:
        # LAW 2 rows are identical in every report TIREKICK emits, paid or not.
        statement = (
            LOCKED_SYSTEM_STATEMENT
            if row.system in LOCKED_SYSTEMS
            else _STATUS_STATEMENTS[row.status]
        )
        rows.append(TeaserSystemRow(system=row.system, status=row.status, statement=statement))
    return rows


def _vehicle_level(report: Report) -> list[Finding]:
    return [f for f in report.findings if f.type not in MODEL_LEVEL_TYPES]


def _counts(report: Report) -> list[SeverityCount]:
    """Severity tally for this car, and only this car.

    Counting the model-level records here put "7 major" on the teaser beside a
    headline that said two - five of the seven being recall campaigns filed
    against every car of the model year, free to remedy, and excluded from the
    red-flag score printed in the same panel. The number a stranger reads first
    has to be the number the sentence beside it is talking about.
    """
    tally = {severity: 0 for severity in _SEVERITIES}
    for finding in _vehicle_level(report):
        tally[finding.severity] += 1
    return [
        SeverityCount(severity=severity, count=tally[severity])  # type: ignore[arg-type]
        for severity in _SEVERITIES
        if tally[severity]
    ]


def _vehicle_summary(report: Report) -> str:
    """Year make model, and nothing else. No VIN in a teaser, masked or otherwise."""
    if report.vehicle is None:
        return ""
    decoded = report.vehicle.decoded
    parts = [str(decoded.year or ""), decoded.make or "", decoded.model or ""]
    if decoded.series:
        parts.append(decoded.series)
    return " ".join(p for p in parts if p).strip()


_SEVERITY_RANK = {"info": 0, "minor": 1, "major": 2, "critical": 3}


def _sample(report: Report) -> TeaserSample | None:
    """Pick the one finding that crosses the paywall.

    The worst-severity, best-evidenced finding *about this vehicle* that cites a
    photograph. Model-level records - recall campaigns, complaint patterns - are
    excluded: they describe every car of that model year rather than this one, so
    handing one over as the sample would advertise the product with a fact that
    is true of a car the buyer has never seen.

    Deliberately the strongest finding rather than the weakest. Showing the least
    of what the report found in order to hold the best back would be a sales
    tactic, and the coverage block directly above it already tells the buyer
    exactly how much of the car this could speak for.

    Locked systems are skipped explicitly even though `apply_safety_law` has
    already converted every such finding into a referral by the time a Report
    exists. The redundancy is deliberate: this is the most-read surface in the
    product, and a brake claim arriving on the free page would be the worst
    available place for that clamp to have failed silently (LAW 2).
    """
    best: Finding | None = None
    best_evidence: ImageRegionEvidence | None = None
    for finding in report.findings:
        if finding.type in MODEL_LEVEL_TYPES or is_locked(finding.system):
            continue
        evidence = next(
            (e for e in finding.evidence if isinstance(e, ImageRegionEvidence)), None
        )
        if evidence is None:
            continue
        if best is None or (
            _SEVERITY_RANK[finding.severity],
            finding.confidence,
        ) > (_SEVERITY_RANK[best.severity], best.confidence):
            best, best_evidence = finding, evidence

    if best is None or best_evidence is None:
        return None

    asset = next((a for a in report.assets if a.id == best_evidence.asset_id), None)
    if asset is None:  # pragma: no cover - referential integrity forbids this
        return None

    # "Each with its own photograph and box" is only true of the findings that
    # have one. A title brand read out of paperwork carries a document excerpt
    # and no photograph, and counting it here sold the buyer a picture that does
    # not exist - the claim is checkable the moment they pay.
    total = len(_vehicle_level(report))
    pictured = sum(
        1
        for f in _vehicle_level(report)
        if any(isinstance(e, ImageRegionEvidence) for e in f.evidence)
    )
    others = total - 1
    others_pictured = pictured - 1
    if total <= 1:
        statement = "The only finding about this vehicle, shown in full."
    elif others_pictured == others:
        statement = (
            f"One of {total} findings about this vehicle, shown in full. "
            f"The other {others} are in the paid report, each with its own "
            f"photograph and box."
        )
    elif others_pictured:
        statement = (
            f"One of {total} findings about this vehicle, shown in full. The "
            f"other {others} are in the paid report - {others_pictured} with a "
            f"photograph and a box, the rest cited to a document or a record."
        )
    else:
        statement = (
            f"One of {total} findings about this vehicle, shown in full. The "
            f"other {others} are in the paid report, cited to documents and "
            f"records rather than photographs."
        )

    return TeaserSample(
        finding_id=best.id,
        type=best.type,
        system=best.system,
        severity=best.severity,
        confidence=best.confidence,
        confidence_basis=best.confidence_basis,
        title=best.title,
        detail=best.detail,
        asset_id=asset.id,
        asset_path=asset.path,
        asset_width=asset.width,
        asset_height=asset.height,
        asset_synthetic=asset.synthetic,
        box=best_evidence.box,
        caption=best_evidence.caption,
        statement=statement,
    )


def _unlocks(report: Report) -> list[str]:
    """What THIS report contains, not what the product can contain.

    The list used to be six fixed bullets, and it was rendered twice: on the
    teaser and again above the payment button under "What you get". A buyer who
    uploaded eight photographs and nothing else was sold an audio spectrogram, a
    federal vehicle record and a readout of their own paperwork, paid $25, and
    opened a report where none of those sections render at all. Meanwhile the
    price comparison - a real paid section - was advertised nowhere.

    So the list is derived. A bullet appears when the section behind it exists.
    """
    lines: list[str] = []
    pictured = any(
        isinstance(e, ImageRegionEvidence) for f in report.findings for e in f.evidence
    )
    if pictured:
        lines.append("Every finding, with the photograph it came from and a box drawn on it")
    else:
        lines.append("Every finding in full, with the evidence each one is drawn from")
    lines.append("Why we are as confident as we are, per finding, in plain words")

    if report.vehicle is not None:
        record_parts = []
        if report.vehicle.recalls:
            record_parts.append(f"{len(report.vehicle.recalls)} recall campaign(s) on record")
        if any(f.type == "complaint_pattern" for f in report.findings):
            record_parts.append("owner complaint patterns for this model year")
        detail = ", ".join(record_parts) if record_parts else "what the VIN decodes to"
        lines.append(f"The full vehicle record: {detail}")
    if any(a.kind == "document" for a in report.assets):
        lines.append("What your own paperwork says, quoted, with the line it came from")
    if report.audio is not None:
        lines.append("The engine audio spectrogram, with the sharp sounds marked")
    if report.walkaround is not None:
        lines.append("Every frame taken from your walkaround video, and what was discarded")
    if report.price is not None:
        lines.append(
            "The asking price against the comparable listings you provided, "
            "with the arithmetic shown"
        )

    lines.append("Questions to ask the seller, written from what was actually found")
    lines.append("A negotiation script that never asks you to overstate anything")
    return lines


def build_teaser(report: Report, *, price_usd: float) -> Teaser:
    """Project a full report down to what may be shown for free."""
    coverage: Coverage = report.coverage

    return Teaser(
        schema_version=report.schema_version,
        report_id=report.report_id,
        inspection_id=report.inspection_id,
        generated_at=report.generated_at,
        mode=report.mode,
        banner=report.banner,
        vehicle_summary=_vehicle_summary(report),
        coverage=coverage,
        red_flag_score=report.verdict.red_flag_score,
        headline=report.verdict.headline,
        finding_count=len(_vehicle_level(report)),
        counts=_counts(report),
        mechanic_referral_count=len(report.mechanic_referrals),
        systems=_system_rows(report),
        sample=_sample(report),
        # Honesty is not behind the paywall. This block is the same in both.
        could_not_assess=list(report.verdict.could_not_assess),
        has_audio=report.audio is not None,
        has_price_check=report.price is not None,
        accuracy_statement=accuracy_statement(),
        price_usd=price_usd,
        unlocks=_unlocks(report),
        contains_synthetic_media=report.contains_synthetic_media,
    )
