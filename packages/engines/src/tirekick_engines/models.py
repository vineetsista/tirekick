"""The report contract, Python side.

Mirrors packages/shared/src/schema.ts. The two are held in sync by the drift gate
described in DECISIONS.md D-002: this module emits the fixture report, and the zod
schemas parse it in CI.

Serialization is camelCase (by_alias=True) because the web app is the consumer.
"""

from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

# Final so the type is Literal["1.0.0"], which is what Report.schema_version pins
# against - a version bump then fails to typecheck until the field is updated too.
SCHEMA_VERSION: Final = "1.0.0"

# LAW 2. Mirrored in packages/shared/src/constants.ts::LOCKED_SYSTEMS.
LOCKED_SYSTEMS: frozenset[str] = frozenset({"brakes", "restraints", "structure", "steering"})

LOCKED_SYSTEM_STATEMENT = "Not remotely verifiable - independent mechanic required."

REPORT_BANNER = (
    "Automated analysis of media you provided. This is not an inspection, a "
    "certification, or a warranty. Confidence is not certainty. Have an independent "
    "mechanic examine any vehicle before you buy it."
)

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]

Severity = Literal["info", "minor", "major", "critical"]

SystemKey = Literal[
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
]

RunMode = Literal["fixture", "live"]

EngineName = Literal["vision", "audio", "data", "pricing"]

ViewClass = Literal[
    "exterior_front",
    "exterior_rear",
    "exterior_side_left",
    "exterior_side_right",
    "exterior_three_quarter",
    "interior_front",
    "interior_rear",
    "engine_bay",
    "odometer",
    "dash",
    "tire",
    "vin_plate",
    "document",
    "undercarriage",
    "unknown",
]

FindingType = Literal[
    "exterior_damage",
    "rust_corrosion",
    "repaint_indicator",
    "tire_tread_estimate",
    "interior_wear",
    "fluid_leak_indicator",
    "dash_warning_light",
    "odometer_reading",
    "odometer_wear_mismatch",
    "audio_anomaly",
    "vin_decode",
    "open_recall",
    "complaint_pattern",
    "title_brand_indicator",
    "price_comparison",
    "documentation_gap",
]

SystemStatus = Literal[
    "no_issues_visible",
    "attention",
    "locked_mechanic_required",
    "cannot_determine",
]


class Base(BaseModel):
    """camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )


# --------------------------------------------------------------------------- #
# evidence - LAW 1                                                             #
# --------------------------------------------------------------------------- #


class BoundingBox(Base):
    """Normalized [0,1]; x,y is the top-left corner."""

    x: Annotated[float, Field(ge=0.0, le=1.0)]
    y: Annotated[float, Field(ge=0.0, le=1.0)]
    w: Annotated[float, Field(ge=0.0, le=1.0)]
    h: Annotated[float, Field(ge=0.0, le=1.0)]


class ImageRegionEvidence(Base):
    kind: Literal["image_region"] = "image_region"
    asset_id: str = Field(min_length=1)
    box: BoundingBox
    caption: str = Field(min_length=1)


class AudioSegmentEvidence(Base):
    kind: Literal["audio_segment"] = "audio_segment"
    asset_id: str = Field(min_length=1)
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)
    caption: str = Field(min_length=1)

    @model_validator(mode="after")
    def _ordered(self) -> AudioSegmentEvidence:
        if self.end_sec < self.start_sec:
            raise ValueError("audio evidence ends before it starts")
        return self


class DataRecordEvidence(Base):
    kind: Literal["data_record"] = "data_record"
    source: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    retrieved_at: str = Field(min_length=1)
    caption: str = Field(min_length=1)


class DocumentExcerptEvidence(Base):
    kind: Literal["document_excerpt"] = "document_excerpt"
    asset_id: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    caption: str = Field(min_length=1)


Evidence = Annotated[
    ImageRegionEvidence | AudioSegmentEvidence | DataRecordEvidence | DocumentExcerptEvidence,
    Field(discriminator="kind"),
]


# --------------------------------------------------------------------------- #
# assets                                                                       #
# --------------------------------------------------------------------------- #


class Asset(Base):
    id: str = Field(min_length=1)
    kind: Literal["photo", "video", "audio", "document"]
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    bytes: int = Field(ge=0)
    view_class: ViewClass | None = None
    view_confidence: Confidence | None = None
    duration_sec: float | None = Field(default=None, ge=0.0)
    synthetic: bool = False


# --------------------------------------------------------------------------- #
# findings - LAW 1 + LAW 2                                                     #
# --------------------------------------------------------------------------- #


class CostBand(Base):
    low: float = Field(ge=0.0)
    high: float = Field(ge=0.0)


class DraftFinding(Base):
    """What an engine proposes, before the laws are applied.

    Permissive on purpose: a model is free to hand us a finding about brakes, and
    safety.apply_safety_law is what makes sure that finding never reaches a report.
    Enforcement lives in one deterministic place rather than being spread across
    every engine (DECISIONS.md D-004).

    LAW 1 still binds here - even a draft must cite evidence.
    """

    id: str = Field(min_length=1)
    type: FindingType
    system: SystemKey
    title: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    severity: Severity
    confidence: Confidence
    confidence_basis: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)
    estimated_cost_usd: CostBand | None = None
    seller_question: str | None = None
    mechanic_check: str | None = None
    engine: EngineName


class Finding(Base):
    """A finding that has passed every law and may be rendered."""

    id: str = Field(min_length=1)
    type: FindingType
    system: SystemKey
    title: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    severity: Severity
    confidence: Confidence
    confidence_basis: str = Field(min_length=1)
    # LAW 1: a finding with no evidence is not a weak finding, it is not a finding.
    evidence: list[Evidence] = Field(min_length=1)
    estimated_cost_usd: CostBand | None = None
    seller_question: str | None = None
    mechanic_check: str | None = None
    engine: EngineName

    @model_validator(mode="after")
    def _law_2_no_locked_systems(self) -> Finding:
        if self.system in LOCKED_SYSTEMS:
            raise ValueError(
                f"LAW 2: finding {self.id!r} attaches to locked system "
                f"{self.system!r}. Locked systems are never cleared or graded "
                f"remotely; route this through safety.apply_safety_law, which "
                f"converts qualifying observations into mechanic referrals."
            )
        return self


class MechanicReferral(Base):
    """An observation near a locked system. Never a verdict on it (D-005)."""

    id: str = Field(min_length=1)
    system: SystemKey
    observation: str = Field(min_length=1)
    ask: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)


# --------------------------------------------------------------------------- #
# systems table                                                                #
# --------------------------------------------------------------------------- #


class SystemRow(Base):
    system: SystemKey
    status: SystemStatus
    statement: str = Field(min_length=1)
    finding_ids: list[str] = Field(default_factory=list)
    confidence: Confidence | None = None

    @model_validator(mode="after")
    def _law_2_locked_rows(self) -> SystemRow:
        if self.system in LOCKED_SYSTEMS:
            if self.status != "locked_mechanic_required":
                raise ValueError(
                    f"LAW 2: system {self.system!r} may only ever have status "
                    f"'locked_mechanic_required', got {self.status!r}"
                )
            if self.confidence is not None:
                raise ValueError(
                    f"LAW 2: locked system {self.system!r} cannot carry a confidence"
                )
            if self.finding_ids:
                raise ValueError(f"LAW 2: locked system {self.system!r} cannot carry findings")
            if self.statement != LOCKED_SYSTEM_STATEMENT:
                raise ValueError(
                    f"LAW 2: locked system {self.system!r} must use the exact locked "
                    f"statement, not a paraphrase"
                )
        return self


# --------------------------------------------------------------------------- #
# vehicle record                                                               #
# --------------------------------------------------------------------------- #


class Recall(Base):
    campaign_number: str = Field(min_length=1)
    component: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    #: What NHTSA says can happen if it is not fixed. Quoted, never paraphrased.
    consequence: str = ""
    remedy: str = ""
    report_received_date: str = ""
    #: NHTSA's own do-not-drive and do-not-park-indoors flags. When either is set
    #: the campaign is an emergency, and the report treats it as one.
    park_it: bool = False
    park_outside: bool = False


class DecodedVehicle(Base):
    year: int | None = None
    make: str | None = None
    model: str | None = None
    #: vPIC's series, where it has one. It is what separates a Silverado 1500
    #: from a 3500, which NHTSA indexes as different vehicles.
    series: str | None = None
    trim: str | None = None
    body_class: str | None = None
    vehicle_type: str | None = None
    engine: str | None = None
    fuel_type: str | None = None
    drive_type: str | None = None
    transmission: str | None = None
    doors: int | None = None
    plant_country: str | None = None


class ComponentCount(Base):
    component: str
    count: int


class ComplaintSummary(Base):
    total: int = Field(ge=0)
    top_components: list[ComponentCount] = Field(default_factory=list)
    with_crash: int = Field(default=0, ge=0)
    with_fire: int = Field(default=0, ge=0)
    injuries_reported: int = Field(default=0, ge=0)
    deaths_reported: int = Field(default=0, ge=0)
    #: What population these counts describe. Never this car.
    scope: str = Field(min_length=1)


class SourceCitation(Base):
    """One federal lookup, with what it covered and when it was made."""

    source: str = Field(min_length=1)
    url: str = Field(min_length=1)
    retrieved_at: str = Field(min_length=1)
    body_sha256: str = Field(min_length=64, max_length=64)
    statement: str = Field(min_length=1)


class VehicleRecord(Base):
    vin: str = Field(min_length=1)
    vin_masked: str = Field(min_length=1)
    #: Result of the offline check in vin.py, before any lookup ran.
    vin_valid: bool
    vin_statement: str = Field(min_length=1)
    decoded: DecodedVehicle
    #: vPIC's own error text when it could not decode. Surfaced, not swallowed.
    decode_error: str | None = None
    recalls: list[Recall] = Field(default_factory=list)
    #: LAW 1. NHTSA publishes recalls per model, not per VIN, and this sentence
    #: is what stops the list from reading as "open on this car".
    recall_scope: str = Field(min_length=1)
    complaint_summary: ComplaintSummary | None = None
    sources: list[SourceCitation] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# audio                                                                        #
# --------------------------------------------------------------------------- #


class AudioTransient(Base):
    """A sharp onset in the recording. A fact about the file, not a diagnosis."""

    at_sec: float = Field(ge=0.0)
    prominence: float = Field(ge=0.0)


class AudioTrack(Base):
    """The audio section: a picture, and measurements taken from it.

    `claims_enabled` is False and will stay False until `audio_anomaly` clears
    its gate on a labelled set. Every field here is a property of the waveform.
    None of them is a statement about an engine.
    """

    asset_id: str = Field(min_length=1)
    duration_sec: float = Field(ge=0.0)
    sample_rate: int = Field(gt=0)
    #: Rendered spectrogram, relative to the inspection media root. Empty when
    #: rendering has not been run.
    spectrogram_path: str = ""
    rms_dbfs: float
    peak_dbfs: float
    clipped_fraction: float = Field(ge=0.0, le=1.0)
    dominant_hz: float | None = None
    implied_rpm: int | None = None
    implied_rpm_basis: str = Field(min_length=1)
    transients: list[AudioTransient] = Field(default_factory=list)
    transient_statement: str = Field(min_length=1)
    usable: bool
    quality_statement: str = Field(min_length=1)
    quality_problems: list[str] = Field(default_factory=list)
    #: LAW 4. False until the anomaly detector has been measured.
    claims_enabled: bool = False
    claims_statement: str = Field(min_length=1)


class WalkaroundTrack(Base):
    """What was taken from the video, and what was thrown away.

    The dropped counts are reported, not just the kept ones. A report that says
    "12 frames analysed" without saying 40 were discarded invites the reader to
    assume the whole video was examined.
    """

    asset_id: str = Field(min_length=1)
    duration_sec: float = Field(ge=0.0)
    frames_sampled: int = Field(ge=0)
    frames_analysed: int = Field(ge=0)
    dropped_blurred: int = Field(ge=0)
    dropped_duplicate: int = Field(ge=0)
    dropped_over_cap: int = Field(ge=0)
    frame_asset_ids: list[str] = Field(default_factory=list)
    frame_times_sec: list[float] = Field(default_factory=list)
    statement: str = Field(min_length=1)


# --------------------------------------------------------------------------- #
# pricing                                                                      #
# --------------------------------------------------------------------------- #


class Comp(Base):
    id: str = Field(min_length=1)
    source_note: str = Field(min_length=1)
    asking_price_usd: float = Field(ge=0.0)
    mileage: int = Field(ge=0)
    year: int
    make: str | None = None
    model: str | None = None
    trim: str | None = None
    #: When the listing was seen, ISO date. A comp from six months ago describes a
    #: different market, and nothing in the arithmetic would notice.
    listed_on: str = ""
    notes: str = ""


class ExcludedComp(Base):
    """A listing the buyer supplied that was not used, and the reason."""

    comp_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class PriceDeduction(Base):
    finding_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    low_usd: float = Field(ge=0.0)
    high_usd: float = Field(ge=0.0)
    basis: str = Field(min_length=1)


class PriceRange(Base):
    low: float = Field(ge=0.0)
    high: float = Field(ge=0.0)


class PriceCheck(Base):
    asking_price_usd: float = Field(ge=0.0)
    # LAW 1: never a price verdict without the comps behind it.
    comps: list[Comp] = Field(min_length=1)
    #: Comps excluded from the range, and why. Rendered - a comp silently dropped
    #: is a comp the buyer thinks was counted.
    excluded: list[ExcludedComp] = Field(default_factory=list)
    normalization_notes: str = Field(min_length=1)
    fair_range_usd: PriceRange
    deductions: list[PriceDeduction] = Field(default_factory=list)
    verdict: Literal["below_range", "in_range", "above_range", "cannot_determine"]
    verdict_statement: str = Field(min_length=1)


# --------------------------------------------------------------------------- #
# coverage, cost, verdict                                                      #
# --------------------------------------------------------------------------- #


class Coverage(Base):
    requested_views: list[ViewClass]
    received_views: list[ViewClass]
    missing_views: list[ViewClass]
    photo_count: int = Field(ge=0)
    has_video: bool
    has_audio: bool
    score: Annotated[float, Field(ge=0.0, le=1.0)]
    statement: str = Field(min_length=1)


class Cost(Base):
    mode: RunMode
    #: Which model produced this report. Empty in fixture mode, where no model ran.
    model: str = ""
    #: Which prompt versions were in force. LAW 1 - a finding is traceable to the
    #: instructions that produced it, not only to the image.
    prompt_fingerprint: str = ""
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    images_analyzed: int = Field(ge=0)
    audio_seconds_processed: float = Field(ge=0.0)
    storage_bytes: int = Field(ge=0)
    #: vPIC and NHTSA queries. Free, and counted anyway - see CostMeter.
    federal_lookups: int = Field(default=0, ge=0)
    #: Seconds of walkaround video decoded locally. Free of API cost, and the
    #: frames it yields are not - they are counted in images_analyzed.
    video_seconds_processed: float = Field(default=0.0, ge=0.0)
    usd_total: float = Field(ge=0.0)
    note: str = Field(min_length=1)


class Verdict(Base):
    red_flag_score: int = Field(ge=0, le=100)
    headline: str = Field(min_length=1)
    # LIABILITY section 9: coverage limits lead, before conclusions.
    could_not_assess: list[str] = Field(min_length=1)
    summary: str = Field(min_length=1)


class ScriptBeat(Base):
    beat: str = Field(min_length=1)
    say: str = Field(min_length=1)


# --------------------------------------------------------------------------- #
# report                                                                       #
# --------------------------------------------------------------------------- #


class Report(Base):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    report_id: str = Field(min_length=1)
    inspection_id: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    mode: RunMode
    banner: str = Field(min_length=1)
    vehicle: VehicleRecord | None = None
    audio: AudioTrack | None = None
    walkaround: WalkaroundTrack | None = None
    assets: list[Asset] = Field(default_factory=list)
    coverage: Coverage
    verdict: Verdict
    findings: list[Finding] = Field(default_factory=list)
    systems: list[SystemRow] = Field(default_factory=list)
    mechanic_referrals: list[MechanicReferral] = Field(default_factory=list)
    price: PriceCheck | None = None
    seller_questions: list[str] = Field(default_factory=list)
    negotiation_script: list[ScriptBeat] = Field(default_factory=list)
    cost: Cost
    contains_synthetic_media: bool = False

    @model_validator(mode="after")
    def _referential_integrity(self) -> Report:
        """LAW 1: every citation must resolve. A dangling reference is a lie."""
        problems: list[str] = []
        asset_ids = {a.id for a in self.assets}
        finding_ids = {f.id for f in self.findings}

        def check(owner: str, evidence: list[Evidence]) -> None:
            for ev in evidence:
                asset_id = getattr(ev, "asset_id", None)
                if asset_id is not None and asset_id not in asset_ids:
                    problems.append(f"{owner} cites unknown asset {asset_id!r}")

        for f in self.findings:
            check(f"finding {f.id!r}", f.evidence)
        for r in self.mechanic_referrals:
            check(f"referral {r.id!r}", r.evidence)
        for row in self.systems:
            for fid in row.finding_ids:
                if fid not in finding_ids:
                    problems.append(f"system {row.system!r} cites unknown finding {fid!r}")
        if self.price is not None:
            for d in self.price.deductions:
                if d.finding_id not in finding_ids:
                    problems.append(f"price deduction cites unknown finding {d.finding_id!r}")

        declared = any(a.synthetic for a in self.assets)
        if declared != self.contains_synthetic_media:
            problems.append("contains_synthetic_media does not match the assets it describes")

        if problems:
            raise ValueError("LAW 1 violations:\n  - " + "\n  - ".join(problems))
        return self

    def to_json(self) -> str:
        import json

        return json.dumps(self.model_dump(by_alias=True, mode="json"), indent=2) + "\n"


# --------------------------------------------------------------------------- #
# teaser - the free projection. See teaser.py.                                 #
# --------------------------------------------------------------------------- #


class SeverityCount(Base):
    severity: Severity
    count: int = Field(ge=0)


class TeaserSystemRow(Base):
    """A systems row with no statement that could leak a finding.

    The paid row carries the worst finding's title. That is the product, so it
    does not survive the projection - except for locked systems, whose statement
    is identical in every report TIREKICK will ever emit (LAW 2).
    """

    system: SystemKey
    status: SystemStatus
    statement: str = Field(min_length=1)

    @model_validator(mode="after")
    def _law_2_locked_rows(self) -> TeaserSystemRow:
        if self.system in LOCKED_SYSTEMS:
            if self.status != "locked_mechanic_required":
                raise ValueError(f"LAW 2: teaser row {self.system!r} is not locked")
            if self.statement != LOCKED_SYSTEM_STATEMENT:
                raise ValueError(
                    f"LAW 2: teaser row {self.system!r} must use the exact locked "
                    f"statement, not a paraphrase"
                )
        return self


class Teaser(Base):
    """What a buyer sees before paying. A smaller object, not a hidden one."""

    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    report_id: str = Field(min_length=1)
    inspection_id: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    mode: RunMode
    banner: str = Field(min_length=1)
    #: Year make model. Never a VIN, masked or otherwise.
    vehicle_summary: str = ""
    #: Kept in full. It is what tells a buyer whether this could answer their
    #: question at all, and that belongs before the payment rather than after.
    coverage: Coverage
    red_flag_score: int = Field(ge=0, le=100)
    headline: str = Field(min_length=1)
    finding_count: int = Field(ge=0)
    counts: list[SeverityCount] = Field(default_factory=list)
    mechanic_referral_count: int = Field(ge=0)
    systems: list[TeaserSystemRow] = Field(default_factory=list)
    #: Never behind the paywall. Charging someone to discover that we cannot
    #: assess their brakes would be indefensible.
    could_not_assess: list[str] = Field(min_length=1)
    has_audio: bool = False
    has_price_check: bool = False
    #: Generated from the eval-gate registry, not written by hand (D-032).
    accuracy_statement: str = Field(min_length=1)
    price_usd: float = Field(ge=0.0)
    unlocks: list[str] = Field(min_length=1)
    contains_synthetic_media: bool = False

    def to_json(self) -> str:
        import json

        return json.dumps(self.model_dump(by_alias=True, mode="json"), indent=2) + "\n"
