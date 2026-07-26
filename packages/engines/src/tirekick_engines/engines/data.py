"""Data engine - VIN decode, recalls, complaint patterns.

Everything here is a federal record or arithmetic on one. No model is called, so
nothing in this file can hallucinate; the failure mode it guards against is
different and, for a report a buyer pays for, worse: stating a true fact at a
precision the source does not support.

The specific trap is recalls. NHTSA publishes recall campaigns keyed to a
make/model/year, and it does not publish, on any public endpoint, whether a
campaign was performed on one particular vehicle. A report that lists four
recalls under a masked VIN reads as "this car has four open recalls" - which we
do not know and cannot find out. So every recall carries its scope in its own
text, `VehicleRecord.recall_scope` says it again above the list, and the seller
question asks for the paperwork rather than assuming its absence. See
DECISIONS.md D-016.
"""

from __future__ import annotations

import contextlib
from typing import Any

from .. import vin as vin_module
from ..models import (
    ComplaintSummary,
    ComponentCount,
    DataRecordEvidence,
    DecodedVehicle,
    DraftFinding,
    Recall,
    SourceCitation,
    SystemKey,
    VehicleRecord,
)
from ..sources import (
    SOURCE_COMPLAINTS,
    SOURCE_RECALLS,
    SOURCE_VPIC,
    FederalRecordMissing,
    FederalSources,
)


def _citation_for(record: VehicleRecord, source: str) -> SourceCitation | None:
    """The lookup a given claim is allowed to cite, found by name rather than index.

    Positional lookup would be quietly wrong the moment a vehicle resolves to
    more than one complaint model name, which is exactly what trucks do.
    """
    for citation in record.sources:
        if citation.source == source:
            return citation
    return None


def mask_vin(value: str) -> str:
    """LIABILITY section 6 - full VINs never appear on a shareable surface."""
    return vin_module.mask(value)


def _text(value: Any) -> str | None:
    """vPIC returns absent fields as empty strings. Empty is not a value."""
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _engine_description(row: dict[str, Any]) -> str | None:
    """Compose the engine line vPIC scatters across several fields.

    vPIC reports displacement to nine decimal places (a 3.0L V6 comes back as
    '2.998832712'), which is a unit-conversion artifact and not precision. It is
    rounded to one decimal here because printing the rest would imply we measured
    something.
    """
    parts: list[str] = []
    raw_litres = _text(row.get("DisplacementL"))
    if raw_litres:
        with contextlib.suppress(ValueError):
            parts.append(f"{float(raw_litres):.1f}L")
    cylinders = _int(row.get("EngineCylinders"))
    if cylinders:
        parts.append(f"{cylinders}-cyl")
    model = _text(row.get("EngineModel"))
    if model:
        parts.append(model)
    return " ".join(parts) or None


def _decode_error(row: dict[str, Any]) -> str | None:
    """vPIC's own verdict on the decode, passed through rather than interpreted.

    ErrorCode '0' is a clean decode. Anything else is returned verbatim: vPIC's
    error text is written for humans and says more than we would by paraphrasing
    it ('Check Digit (9th position) does not calculate properly').
    """
    code = _text(row.get("ErrorCode")) or "0"
    if code == "0":
        return None
    return _text(row.get("ErrorText")) or f"vPIC returned error code {code}."


def _decoded_from(row: dict[str, Any]) -> DecodedVehicle:
    return DecodedVehicle(
        year=_int(row.get("ModelYear")),
        make=_text(row.get("Make")),
        model=_text(row.get("Model")),
        series=_text(row.get("Series")),
        trim=_text(row.get("Trim")),
        body_class=_text(row.get("BodyClass")),
        vehicle_type=_text(row.get("VehicleType")),
        engine=_engine_description(row),
        fuel_type=_text(row.get("FuelTypePrimary")),
        drive_type=_text(row.get("DriveType")),
        transmission=_text(row.get("TransmissionStyle")),
        doors=_int(row.get("Doors")),
        plant_country=_text(row.get("PlantCountry")),
    )


def _recalls_from(payload: dict[str, Any]) -> list[Recall]:
    recalls: list[Recall] = []
    for entry in payload.get("results") or []:
        campaign = _text(entry.get("NHTSACampaignNumber"))
        component = _text(entry.get("Component"))
        summary = _text(entry.get("Summary"))
        if not (campaign and component and summary):
            # A campaign missing its own identity is not something we will render.
            continue
        recalls.append(
            Recall(
                campaign_number=campaign,
                component=component,
                summary=summary,
                consequence=_text(entry.get("Consequence")) or "",
                remedy=_text(entry.get("Remedy")) or "",
                report_received_date=_text(entry.get("ReportReceivedDate")) or "",
                park_it=bool(entry.get("parkIt")),
                park_outside=bool(entry.get("parkOutSide")),
            )
        )
    # Newest first. NHTSA returns campaign order, which is not chronological.
    recalls.sort(key=lambda r: r.campaign_number, reverse=True)
    return recalls


def resolve_complaint_models(
    index_payload: dict[str, Any], model: str, series: str | None
) -> list[str]:
    """Which names the complaints endpoint will accept for this vehicle.

    The complaints index is a different vocabulary from the one vPIC decodes to.
    Resolution goes from most specific to least:

      1. model + series, when vPIC gave a series - 'Silverado' + '1500' is
         indexed as 'SILVERADO 1500', and matching it exactly avoids blending a
         half-ton truck's complaints with a one-ton's.
      2. the model name exactly - the common case, 'ACCORD'.
      3. every indexed name beginning with the model - the F-150 case, where the
         index splits by cab configuration and the VIN does not say which.

    Returning several names is not a failure; it is the honest answer when the
    index draws a distinction the VIN cannot. The caller names them in the scope
    sentence so the buyer knows what was counted.
    """
    indexed = index_payload.get("results") or []
    names = sorted({str(r.get("model") or "").strip().upper() for r in indexed})
    names = [n for n in names if n]
    target = model.strip().upper()

    if series:
        specific = f"{target} {series.strip().upper()}"
        if specific in names:
            return [specific]

    if target in names:
        return [target]

    prefixed = [n for n in names if n.startswith(target + " ")]
    return prefixed


def _merge_complaint_payloads(
    payloads: list[dict[str, Any]], label: str, names: list[str]
) -> ComplaintSummary:
    """Sum reductions across however many index names this vehicle resolved to."""
    counts: dict[str, int] = {}
    total = crashes = fires = injuries = deaths = 0
    for payload in payloads:
        total += int(payload.get("total") or 0)
        crashes += int(payload.get("with_crash") or 0)
        fires += int(payload.get("with_fire") or 0)
        injuries += int(payload.get("injuries_reported") or 0)
        deaths += int(payload.get("deaths_reported") or 0)
        for entry in payload.get("top_components") or []:
            counts[entry["component"]] = counts.get(entry["component"], 0) + int(entry["count"])

    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:6]

    if len(names) > 1:
        scope = (
            f"Complaints filed with NHTSA by owners of the {label}, across the "
            f"whole model year. NHTSA indexes this vehicle under more than one "
            f"name ({', '.join(names)}) and the VIN does not say which one this "
            f"car is, so the counts cover all of them. They describe the model, "
            f"not this car - and a high count on a common vehicle is partly just "
            f"a high count of vehicles."
        )
    else:
        scope = (
            f"Complaints filed with NHTSA by owners of the {label}, across the "
            f"whole model year. They describe the model. None of them describes "
            f"this car, and a high count on a common vehicle is partly just a "
            f"high count of vehicles."
        )

    return ComplaintSummary(
        total=total,
        top_components=[ComponentCount(component=name, count=count) for name, count in top],
        with_crash=crashes,
        with_fire=fires,
        injuries_reported=injuries,
        deaths_reported=deaths,
        scope=scope,
    )


def _invalid_vin_record(raw: str, check: vin_module.VinCheck) -> VehicleRecord:
    """A VIN we would not look up. Said plainly, with nothing invented around it."""
    return VehicleRecord(
        vin=check.vin or raw,
        vin_masked=mask_vin(check.vin or raw),
        vin_valid=False,
        vin_statement=check.statement,
        decoded=DecodedVehicle(),
        decode_error=None,
        recalls=[],
        recall_scope=(
            "No recall lookup was run. Recalls are looked up from the decoded "
            "make, model and year, and this VIN did not decode."
        ),
        complaint_summary=None,
        sources=[],
    )


def lookup(raw_vin: str | None, sources: FederalSources) -> VehicleRecord | None:
    """Decode the VIN, then pull recalls and complaints for what it decoded to."""
    if not raw_vin:
        return None

    check = vin_module.validate(raw_vin)
    if not check.valid:
        return _invalid_vin_record(raw_vin, check)

    vin_value = check.vin
    try:
        decode_record = sources.decode_vin(vin_value)
    except FederalRecordMissing:
        return None

    row = (decode_record.payload.get("Results") or [{}])[0]
    decoded = _decoded_from(row)
    decode_error = _decode_error(row)

    citations = [
        SourceCitation(
            source=decode_record.source,
            url=decode_record.url,
            retrieved_at=decode_record.retrieved_at,
            body_sha256=decode_record.body_sha256,
            statement=(
                "What the manufacturer encoded into this VIN. It describes how the "
                "vehicle left the factory, not its condition today."
            ),
        )
    ]

    recalls: list[Recall] = []
    complaints: ComplaintSummary | None = None
    year, make, model = decoded.year, decoded.make, decoded.model

    if year and make and model:
        label = f"{year} {make} {model}"
        try:
            recall_record = sources.recalls(make, model, year)
            recalls = _recalls_from(recall_record.payload)
            citations.append(
                SourceCitation(
                    source=recall_record.source,
                    url=recall_record.url,
                    retrieved_at=recall_record.retrieved_at,
                    body_sha256=recall_record.body_sha256,
                    statement=(
                        f"Every safety recall campaign NHTSA has filed against the "
                        f"{label}. Keyed to the model, not to this VIN."
                    ),
                )
            )
        except FederalRecordMissing:
            pass

        try:
            index_record = sources.complaint_model_index(make, year)
            names = resolve_complaint_models(index_record.payload, model, decoded.series)
            payloads = []
            for name in names:
                record = sources.complaints(make, name, year)
                payloads.append(record.payload)
                citations.append(
                    SourceCitation(
                        source=record.source,
                        url=record.url,
                        retrieved_at=record.retrieved_at,
                        body_sha256=record.body_sha256,
                        statement=(
                            f"Owner-filed complaint counts for the {year} {make} "
                            f"{name}. Counts only - the narratives belong to the "
                            f"people who wrote them and are not retained."
                        ),
                    )
                )
            if payloads:
                complaints = _merge_complaint_payloads(payloads, label, names)
        except FederalRecordMissing:
            pass

        recall_scope = (
            f"{len(recalls)} recall campaign(s) on record for the {label}. NHTSA "
            f"publishes recalls by model, not by VIN, and does not publish whether "
            f"a campaign was carried out on any individual vehicle. So this is a "
            f"list of what could apply to this car - not a list of what is "
            f"outstanding on it. A dealer can tell you, by VIN, in a phone call, "
            f"and the work is free."
        )
    else:
        recall_scope = (
            "No recall lookup was run. Recalls are looked up from the decoded make, "
            "model and year, and this VIN did not decode to all three."
        )

    return VehicleRecord(
        vin=vin_value,
        vin_masked=mask_vin(vin_value),
        vin_valid=True,
        vin_statement=check.statement,
        decoded=decoded,
        decode_error=decode_error,
        recalls=recalls,
        recall_scope=recall_scope,
        complaint_summary=complaints,
        sources=citations,
    )


#: Maps an NHTSA component string onto our system keys. Locked systems are listed
#: first so that a campaign naming one is routed to a mechanic referral by
#: safety.apply_safety_law rather than matching a later, looser hint.
_COMPONENT_HINTS: tuple[tuple[str, SystemKey], ...] = (
    ("AIR BAG", "restraints"),
    ("SEAT BELT", "restraints"),
    ("CHILD SEAT", "restraints"),
    ("BRAKE", "brakes"),
    ("STEERING", "steering"),
    ("STRUCTURE", "structure"),
    ("FRAME", "structure"),
    ("ENGINE", "engine"),
    ("FUEL", "engine"),
    ("ELECTRICAL", "electrical"),
    ("EXTERIOR LIGHTING", "electrical"),
    ("BACK OVER PREVENTION", "electrical"),
    ("SUSPENSION", "suspension"),
    ("WHEEL", "suspension"),
    ("TIRE", "tires"),
    ("POWER TRAIN", "transmission"),
    ("VISIBILITY", "glass"),
    ("EQUIPMENT", "exterior"),
    ("LATCH", "exterior"),
)


def _system_for(component: str) -> SystemKey:
    upper = component.upper()
    for hint, system in _COMPONENT_HINTS:
        if hint in upper:
            return system
    return "documentation"


def recall_findings(record: VehicleRecord | None) -> list[DraftFinding]:
    """One draft per recall campaign, each citing the federal record behind it.

    Severity is not model-judged. An open campaign is `major`; a campaign NHTSA
    has flagged do-not-drive or do-not-park-indoors is `critical`. Ranking the
    rest against each other would be us inventing a judgment that the source does
    not contain.
    """
    if record is None:
        return []

    citation = _citation_for(record, SOURCE_RECALLS)
    if citation is None:
        # No recall lookup happened, so there is nothing to cite and therefore -
        # LAW 1 - nothing to report. The gap is named in the vehicle record.
        return []

    drafts: list[DraftFinding] = []
    for recall in record.recalls:
        urgent = recall.park_it or recall.park_outside
        urgency = ""
        if recall.park_it:
            urgency = (
                " NHTSA has flagged this campaign DO NOT DRIVE: the agency is "
                "telling owners to stop driving affected vehicles until the "
                "repair is done."
            )
        elif recall.park_outside:
            urgency = (
                " NHTSA has flagged this campaign PARK OUTSIDE: affected vehicles "
                "can catch fire while parked and should be kept away from "
                "structures until the repair is done."
            )

        consequence = (
            f" NHTSA states the consequence: {recall.consequence}" if recall.consequence else ""
        )

        drafts.append(
            DraftFinding(
                id=f"recall_{recall.campaign_number}",
                type="open_recall",
                system=_system_for(recall.component),
                title=f"Recall {recall.campaign_number}: {recall.component}",
                detail=(
                    f"{recall.summary}{consequence}{urgency} This campaign is on "
                    f"record for this model year. TIREKICK cannot tell whether it "
                    f"was ever carried out on this particular vehicle - NHTSA "
                    f"does not publish per-VIN repair status - so treat it as a "
                    f"question to settle, not as a defect found. Any dealer will "
                    f"check by VIN and perform outstanding recall work free."
                ),
                severity="critical" if urgent else "major",
                confidence=1.0,
                confidence_basis=(
                    "Transcribed from the NHTSA recall record, not judged by a "
                    "model. The certainty is that this campaign exists and covers "
                    "this model year. Whether it is outstanding on this car is "
                    "not something we know."
                ),
                evidence=[
                    DataRecordEvidence(
                        source=citation.source,
                        record_id=recall.campaign_number,
                        retrieved_at=citation.retrieved_at,
                        caption=(
                            f"NHTSA campaign {recall.campaign_number} - " f"{recall.component}"
                        ),
                    )
                ],
                seller_question=(
                    f"Recall {recall.campaign_number} covers this model year. Has "
                    f"it been done on this car, and do you have the dealer "
                    f"paperwork?"
                ),
                mechanic_check=None,
                engine="data",
            )
        )
    return drafts


def complaint_findings(record: VehicleRecord | None) -> list[DraftFinding]:
    """One summary of what owners of this model complain about.

    Deliberately `info` severity and deliberately about the model. A complaint
    count is a prior, not an observation: it tells a buyer what to look at on this
    kind of car, and says nothing whatsoever about the one in the photographs.
    Writing it any other way would be the cheapest dishonesty in the report.
    """
    if record is None or record.complaint_summary is None:
        return []

    summary = record.complaint_summary
    if summary.total == 0 or not summary.top_components:
        return []

    citation = _citation_for(record, SOURCE_COMPLAINTS)
    if citation is None:
        return []

    decoded = record.decoded
    label = f"{decoded.year} {decoded.make} {decoded.model}"
    leaders = ", ".join(
        f"{c.component.lower()} ({c.count})" for c in summary.top_components[:4]
    )

    return [
        DraftFinding(
            id="complaint_pattern_summary",
            type="complaint_pattern",
            system="documentation",
            title=f"What owners of the {label} complain about",
            detail=(
                f"{summary.total:,} owners filed complaints with NHTSA about the "
                f"{label}. The most reported areas were {leaders}. This is a "
                f"pattern across the model, not an observation about this car - a "
                f"popular car accumulates complaints simply by being everywhere. "
                f"Use it as a list of things to look at closely and ask about."
            ),
            severity="info",
            confidence=1.0,
            confidence_basis=(
                "A count of public records, not a judgment. What is certain is the "
                "number of complaints filed about this model year. Nothing here is "
                "evidence about the vehicle you are looking at."
            ),
            evidence=[
                DataRecordEvidence(
                    source=citation.source,
                    record_id=f"complaints/{decoded.year}-{decoded.make}-{decoded.model}",
                    retrieved_at=citation.retrieved_at,
                    caption=(f"{summary.total:,} owner complaints on file for the {label}"),
                )
            ],
            seller_question=(
                f"Owners of this model most often report problems with "
                f"{summary.top_components[0].component.lower()}. Has this car had "
                f"any work done there?"
            ),
            mechanic_check=(
                f"Ask a mechanic to pay particular attention to "
                f"{summary.top_components[0].component.lower()} on this model."
            ),
            engine="data",
        )
    ]


def decode_findings(
    record: VehicleRecord | None,
    *,
    listing_year: int | None = None,
    listing_make: str | None = None,
    listing_model: str | None = None,
) -> list[DraftFinding]:
    """Flag a VIN we could not use, or one that disagrees with the listing.

    A clean decode is not a finding - it is the vehicle record, and it renders
    there. This function fires only when something is wrong, which is the only
    time a buyer needs a card about it.
    """
    if record is None:
        return []

    citation = _citation_for(record, SOURCE_VPIC)

    if not record.vin_valid:
        # No lookup ran, so there is no federal record to cite. LAW 1 forbids a
        # finding without evidence, and the honest place for this is the vehicle
        # record and the "could not assess" block, both of which carry it.
        return []

    drafts: list[DraftFinding] = []

    if record.decode_error and citation is not None:
        drafts.append(
            DraftFinding(
                id="vin_decode_error",
                type="vin_decode",
                system="documentation",
                title="The federal database could not fully decode this VIN",
                detail=(
                    f"NHTSA vPIC returned: {record.decode_error} A VIN that does "
                    f"not decode cleanly is worth resolving before money changes "
                    f"hands - it can be a transcription error in the listing, or "
                    f"it can be a VIN that does not match the vehicle. Read the "
                    f"number off the dash plate and the driver's door jamb "
                    f"yourself and check that they agree with each other and with "
                    f"the title."
                ),
                severity="major",
                confidence=1.0,
                confidence_basis=(
                    "This is vPIC's own error text, passed through unmodified. The "
                    "certainty is about what the database said, not about why."
                ),
                evidence=[
                    DataRecordEvidence(
                        source=citation.source,
                        record_id=record.vin_masked,
                        retrieved_at=citation.retrieved_at,
                        caption=f"vPIC decode response for {record.vin_masked}",
                    )
                ],
                seller_question=(
                    "Can you send me a photo of the VIN plate on the dash and the "
                    "sticker in the driver's door jamb?"
                ),
                mechanic_check=None,
                engine="data",
            )
        )

    mismatches = _listing_mismatches(record, listing_year, listing_make, listing_model)
    if mismatches and citation is not None:
        decoded = record.decoded
        drafts.append(
            DraftFinding(
                id="vin_listing_mismatch",
                type="vin_decode",
                system="documentation",
                title="The VIN does not decode to the vehicle in the listing",
                detail=(
                    f"The listing describes a {listing_year or ''} "
                    f"{listing_make or ''} {listing_model or ''}".strip()
                    + f", but this VIN decodes to a {decoded.year} {decoded.make} "
                    f"{decoded.model}. Specifically: {'; '.join(mismatches)}. This "
                    f"is usually a typo in an advert. It is occasionally not. Do "
                    f"not send a deposit until the VIN on the car matches the VIN "
                    f"on the title and both match what you were shown."
                ),
                severity="major",
                confidence=1.0,
                confidence_basis=(
                    "A string comparison between what you told us the listing says "
                    "and what the federal database returned. No judgment involved; "
                    "the uncertainty is entirely about which of the two is wrong."
                ),
                evidence=[
                    DataRecordEvidence(
                        source=citation.source,
                        record_id=record.vin_masked,
                        retrieved_at=citation.retrieved_at,
                        caption=(
                            f"vPIC decodes this VIN as {decoded.year} "
                            f"{decoded.make} {decoded.model}"
                        ),
                    )
                ],
                seller_question=(
                    "The VIN you gave me decodes to a different vehicle than the "
                    "listing describes. Can we check the VIN together?"
                ),
                mechanic_check=None,
                engine="data",
            )
        )

    return drafts


def _listing_mismatches(
    record: VehicleRecord,
    listing_year: int | None,
    listing_make: str | None,
    listing_model: str | None,
) -> list[str]:
    """Compare the listing's claim against the decode, conservatively.

    Model names are compared loosely on purpose. vPIC says 'Silverado' where a
    listing says 'Silverado 1500', and calling that a mismatch would cry wolf on
    almost every truck. Only a genuine disagreement counts.
    """
    decoded = record.decoded
    problems: list[str] = []

    if listing_year and decoded.year and listing_year != decoded.year:
        problems.append(f"listing says {listing_year}, VIN decodes to {decoded.year}")

    if listing_make and decoded.make and listing_make.strip().upper() != decoded.make.upper():
        problems.append(f"listing says {listing_make}, VIN decodes to {decoded.make}")

    if listing_model and decoded.model:
        claimed = listing_model.strip().upper()
        actual = decoded.model.upper()
        if claimed not in actual and actual not in claimed:
            problems.append(f"listing says {listing_model}, VIN decodes to {decoded.model}")

    return problems
