import { z } from "zod";
import { LOCKED_SYSTEMS, SCHEMA_VERSION } from "./constants";

/* ------------------------------------------------------------------ */
/* primitives                                                          */
/* ------------------------------------------------------------------ */

export const confidenceSchema = z.number().min(0).max(1);

export const severitySchema = z.enum(["info", "minor", "major", "critical"]);
export type Severity = z.infer<typeof severitySchema>;

/**
 * Vehicle systems. The four in LOCKED_SYSTEMS are hard-locked by LAW 2 and can
 * never carry a status other than "locked".
 */
export const systemKeySchema = z.enum([
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
]);
export type SystemKey = z.infer<typeof systemKeySchema>;

export const runModeSchema = z.enum(["fixture", "live"]);

/* ------------------------------------------------------------------ */
/* evidence - LAW 1                                                    */
/* ------------------------------------------------------------------ */

/** Normalized [0,1] box: x,y is the top-left corner. */
export const boundingBoxSchema = z.object({
  x: z.number().min(0).max(1),
  y: z.number().min(0).max(1),
  w: z.number().min(0).max(1),
  h: z.number().min(0).max(1),
});
export type BoundingBox = z.infer<typeof boundingBoxSchema>;

export const imageRegionEvidenceSchema = z.object({
  kind: z.literal("image_region"),
  assetId: z.string().min(1),
  box: boundingBoxSchema,
  caption: z.string().min(1),
});

export const audioSegmentEvidenceSchema = z.object({
  kind: z.literal("audio_segment"),
  assetId: z.string().min(1),
  startSec: z.number().min(0),
  endSec: z.number().min(0),
  caption: z.string().min(1),
});

export const dataRecordEvidenceSchema = z.object({
  kind: z.literal("data_record"),
  source: z.string().min(1),
  recordId: z.string().min(1),
  retrievedAt: z.string().min(1),
  caption: z.string().min(1),
});

export const documentExcerptEvidenceSchema = z.object({
  kind: z.literal("document_excerpt"),
  assetId: z.string().min(1),
  excerpt: z.string().min(1),
  caption: z.string().min(1),
});

export const evidenceSchema = z.discriminatedUnion("kind", [
  imageRegionEvidenceSchema,
  audioSegmentEvidenceSchema,
  dataRecordEvidenceSchema,
  documentExcerptEvidenceSchema,
]);
export type Evidence = z.infer<typeof evidenceSchema>;

/* ------------------------------------------------------------------ */
/* assets                                                              */
/* ------------------------------------------------------------------ */

export const assetKindSchema = z.enum(["photo", "video", "audio", "document"]);

export const viewClassSchema = z.enum([
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
]);
export type ViewClass = z.infer<typeof viewClassSchema>;

export const assetSchema = z.object({
  id: z.string().min(1),
  kind: assetKindSchema,
  path: z.string().min(1),
  sha256: z.string().length(64),
  bytes: z.number().int().nonnegative(),
  /** Set by the vision stage-1 classifier; null for non-photo assets. */
  viewClass: viewClassSchema.nullable(),
  viewConfidence: confidenceSchema.nullable(),
  durationSec: z.number().nonnegative().nullable(),
  /** True for generated fixture media. Surfaced in the report. See LAW 1. */
  synthetic: z.boolean(),
});
export type Asset = z.infer<typeof assetSchema>;

/* ------------------------------------------------------------------ */
/* findings - LAW 1                                                    */
/* ------------------------------------------------------------------ */

export const findingTypeSchema = z.enum([
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
]);
export type FindingType = z.infer<typeof findingTypeSchema>;

export const findingSchema = z.object({
  id: z.string().min(1),
  type: findingTypeSchema,
  system: systemKeySchema,
  title: z.string().min(1),
  detail: z.string().min(1),
  severity: severitySchema,
  confidence: confidenceSchema,
  /** Why this confidence. LAW 1 - a bare number is not enough. */
  confidenceBasis: z.string().min(1),
  /** LAW 1 - a finding with no evidence is not a finding. */
  evidence: z.array(evidenceSchema).min(1),
  /** Repair cost band, only when we can source it. Never invented. */
  estimatedCostUsd: z
    .object({ low: z.number().nonnegative(), high: z.number().nonnegative() })
    .nullable(),
  sellerQuestion: z.string().nullable(),
  mechanicCheck: z.string().nullable(),
  /** Which engine produced it. */
  engine: z.enum(["vision", "audio", "data", "pricing"]),
});
export type Finding = z.infer<typeof findingSchema>;

/* ------------------------------------------------------------------ */
/* systems table                                                       */
/* ------------------------------------------------------------------ */

export const systemStatusSchema = z.enum([
  /** Nothing adverse visible in the media provided. Not a clearance. */
  "no_issues_visible",
  /** One or more findings attached. */
  "attention",
  /** LAW 2. The only permitted status for a locked system. */
  "locked_mechanic_required",
  /** Media did not cover it. A first-class outcome. */
  "cannot_determine",
]);
export type SystemStatus = z.infer<typeof systemStatusSchema>;

export const systemRowSchema = z.object({
  system: systemKeySchema,
  status: systemStatusSchema,
  statement: z.string().min(1),
  findingIds: z.array(z.string()),
  /** Null for locked systems - a locked row never carries a confidence. */
  confidence: confidenceSchema.nullable(),
});
export type SystemRow = z.infer<typeof systemRowSchema>;

/* ------------------------------------------------------------------ */
/* vehicle record - data engine                                        */
/* ------------------------------------------------------------------ */

export const recallSchema = z.object({
  campaignNumber: z.string().min(1),
  component: z.string().min(1),
  summary: z.string().min(1),
  /** NHTSA's stated consequence of leaving it unfixed. Quoted, never paraphrased. */
  consequence: z.string(),
  remedy: z.string(),
  reportReceivedDate: z.string(),
  /** NHTSA's do-not-drive flag. */
  parkIt: z.boolean(),
  /** NHTSA's do-not-park-indoors flag (fire risk while parked). */
  parkOutside: z.boolean(),
});

/** One federal lookup: what it covered, when, and the hash of the bytes returned. */
export const sourceCitationSchema = z.object({
  source: z.string().min(1),
  url: z.string().min(1),
  retrievedAt: z.string().min(1),
  bodySha256: z.string().length(64),
  statement: z.string().min(1),
});
export type SourceCitation = z.infer<typeof sourceCitationSchema>;

export const vehicleRecordSchema = z.object({
  vin: z.string().min(1),
  /** Display form with the last 6 masked. LIABILITY section 6. */
  vinMasked: z.string().min(1),
  /** Offline ISO 3779 check, run before any lookup. */
  vinValid: z.boolean(),
  vinStatement: z.string().min(1),
  decoded: z.object({
    year: z.number().int().nullable(),
    make: z.string().nullable(),
    model: z.string().nullable(),
    /** Separates a Silverado 1500 from a 3500 - different vehicles to NHTSA. */
    series: z.string().nullable(),
    trim: z.string().nullable(),
    bodyClass: z.string().nullable(),
    vehicleType: z.string().nullable(),
    engine: z.string().nullable(),
    fuelType: z.string().nullable(),
    driveType: z.string().nullable(),
    transmission: z.string().nullable(),
    doors: z.number().int().nullable(),
    plantCountry: z.string().nullable(),
  }),
  /** vPIC's own error text when it could not decode. Surfaced, not swallowed. */
  decodeError: z.string().nullable(),
  recalls: z.array(recallSchema),
  /**
   * LAW 1. NHTSA publishes recalls per model, not per VIN. This sentence is what
   * stops the list from reading as "open on this particular car".
   */
  recallScope: z.string().min(1),
  complaintSummary: z
    .object({
      total: z.number().int().nonnegative(),
      topComponents: z.array(
        z.object({ component: z.string(), count: z.number().int() }),
      ),
      withCrash: z.number().int().nonnegative(),
      withFire: z.number().int().nonnegative(),
      injuriesReported: z.number().int().nonnegative(),
      deathsReported: z.number().int().nonnegative(),
      /** What population these counts describe. Never this car. */
      scope: z.string().min(1),
    })
    .nullable(),
  sources: z.array(sourceCitationSchema),
});
export type VehicleRecord = z.infer<typeof vehicleRecordSchema>;

/* ------------------------------------------------------------------ */
/* audio                                                               */
/* ------------------------------------------------------------------ */

/** A sharp onset in the recording. A fact about the file, not a diagnosis. */
export const audioTransientSchema = z.object({
  atSec: z.number().nonnegative(),
  prominence: z.number().nonnegative(),
});
export type AudioTransient = z.infer<typeof audioTransientSchema>;

/**
 * The audio section: a picture, and measurements taken from it.
 *
 * `claimsEnabled` is false and stays false until audio_anomaly clears its gate
 * on a labelled set (LAW 4). Every field here is a property of the waveform;
 * none of them is a statement about an engine.
 */
export const audioTrackSchema = z.object({
  assetId: z.string().min(1),
  durationSec: z.number().nonnegative(),
  sampleRate: z.number().int().positive(),
  /** Rendered spectrogram, relative to the media root. Empty if not rendered. */
  spectrogramPath: z.string(),
  rmsDbfs: z.number(),
  peakDbfs: z.number(),
  clippedFraction: z.number().min(0).max(1),
  dominantHz: z.number().nullable(),
  impliedRpm: z.number().int().nullable(),
  impliedRpmBasis: z.string().min(1),
  transients: z.array(audioTransientSchema),
  transientStatement: z.string().min(1),
  usable: z.boolean(),
  qualityStatement: z.string().min(1),
  qualityProblems: z.array(z.string()),
  claimsEnabled: z.boolean(),
  claimsStatement: z.string().min(1),
});
export type AudioTrack = z.infer<typeof audioTrackSchema>;

/* ------------------------------------------------------------------ */
/* pricing                                                             */
/* ------------------------------------------------------------------ */

export const compSchema = z.object({
  id: z.string().min(1),
  /** Pasted by the user. LAW 3 - never harvested. */
  sourceNote: z.string().min(1),
  askingPriceUsd: z.number().nonnegative(),
  mileage: z.number().int().nonnegative(),
  year: z.number().int(),
  trim: z.string().nullable(),
  notes: z.string(),
});

export const priceDeductionSchema = z.object({
  findingId: z.string().min(1),
  label: z.string().min(1),
  lowUsd: z.number().nonnegative(),
  highUsd: z.number().nonnegative(),
  basis: z.string().min(1),
});

export const priceCheckSchema = z.object({
  askingPriceUsd: z.number().nonnegative(),
  /** LAW 1 - never a verdict without the comps behind it. min 1 enforced here. */
  comps: z.array(compSchema).min(1),
  normalizationNotes: z.string().min(1),
  fairRangeUsd: z.object({
    low: z.number().nonnegative(),
    high: z.number().nonnegative(),
  }),
  deductions: z.array(priceDeductionSchema),
  verdict: z.enum(["below_range", "in_range", "above_range", "cannot_determine"]),
  verdictStatement: z.string().min(1),
});
export type PriceCheck = z.infer<typeof priceCheckSchema>;

/* ------------------------------------------------------------------ */
/* coverage - LIABILITY section 9                                      */
/* ------------------------------------------------------------------ */

/**
 * What the media actually covered. Rendered before the verdict so a thin report
 * cannot read as a clean one.
 */
export const coverageSchema = z.object({
  requestedViews: z.array(viewClassSchema),
  receivedViews: z.array(viewClassSchema),
  missingViews: z.array(viewClassSchema),
  photoCount: z.number().int().nonnegative(),
  hasVideo: z.boolean(),
  hasAudio: z.boolean(),
  /** receivedViews / requestedViews, rounded to 2dp. */
  score: z.number().min(0).max(1),
  statement: z.string().min(1),
});
export type Coverage = z.infer<typeof coverageSchema>;

/* ------------------------------------------------------------------ */
/* cost - LAW 5                                                        */
/* ------------------------------------------------------------------ */

export const costSchema = z.object({
  mode: runModeSchema,
  /** Which model produced this report. Empty in fixture mode - no model ran. */
  model: z.string(),
  /** Which prompt versions were in force, so a finding traces to its instructions. */
  promptFingerprint: z.string(),
  inputTokens: z.number().int().nonnegative(),
  outputTokens: z.number().int().nonnegative(),
  imagesAnalyzed: z.number().int().nonnegative(),
  audioSecondsProcessed: z.number().nonnegative(),
  storageBytes: z.number().int().nonnegative(),
  /** vPIC and NHTSA queries. Free, and counted anyway. LAW 5. */
  federalLookups: z.number().int().nonnegative(),
  usdTotal: z.number().nonnegative(),
  /** Why the total is what it is - "fixture mode, no API calls" counts. */
  note: z.string().min(1),
});
export type Cost = z.infer<typeof costSchema>;

/* ------------------------------------------------------------------ */
/* mechanic referrals - LAW 2 escape valve, see D-005                  */
/* ------------------------------------------------------------------ */

export const mechanicReferralSchema = z.object({
  id: z.string().min(1),
  system: systemKeySchema,
  /** An observation, never a verdict on the locked system. */
  observation: z.string().min(1),
  ask: z.string().min(1),
  evidence: z.array(evidenceSchema).min(1),
});
export type MechanicReferral = z.infer<typeof mechanicReferralSchema>;

/* ------------------------------------------------------------------ */
/* report                                                              */
/* ------------------------------------------------------------------ */

export const verdictSchema = z.object({
  /** 0-100. Never rendered without its caveats. BRAND.md. */
  redFlagScore: z.number().int().min(0).max(100),
  headline: z.string().min(1),
  /** Coverage limits lead. LIABILITY section 9. */
  couldNotAssess: z.array(z.string()).min(1),
  summary: z.string().min(1),
});

export const reportSchema = z.object({
  schemaVersion: z.literal(SCHEMA_VERSION),
  reportId: z.string().min(1),
  inspectionId: z.string().min(1),
  generatedAt: z.string().min(1),
  mode: runModeSchema,
  /** LAW 6 - the banner is part of the data, not just the template. */
  banner: z.string().min(1),
  vehicle: vehicleRecordSchema.nullable(),
  audio: audioTrackSchema.nullable(),
  assets: z.array(assetSchema),
  coverage: coverageSchema,
  verdict: verdictSchema,
  findings: z.array(findingSchema),
  systems: z.array(systemRowSchema),
  mechanicReferrals: z.array(mechanicReferralSchema),
  price: priceCheckSchema.nullable(),
  sellerQuestions: z.array(z.string()),
  negotiationScript: z.array(
    z.object({ beat: z.string().min(1), say: z.string().min(1) }),
  ),
  cost: costSchema,
  /** True if any asset is synthetic. Surfaced prominently. */
  containsSyntheticMedia: z.boolean(),
});
export type Report = z.infer<typeof reportSchema>;

/* ------------------------------------------------------------------ */
/* law assertions - checked on every parse, not just in tests          */
/* ------------------------------------------------------------------ */

const lockedSet: ReadonlySet<string> = new Set(LOCKED_SYSTEMS);

export function isLockedSystem(system: SystemKey): boolean {
  return lockedSet.has(system);
}

/**
 * Structural checks the type system cannot express. Runs after zod parse; a report
 * that fails any of these is a law violation and must not render.
 */
export function assertLaws(report: Report): void {
  const problems: string[] = [];

  // LAW 2: no finding may attach to a locked system.
  for (const f of report.findings) {
    if (isLockedSystem(f.system)) {
      problems.push(`LAW 2: finding ${f.id} attaches to locked system ${f.system}`);
    }
  }

  // LAW 2: every locked system row must be locked, with no confidence.
  for (const row of report.systems) {
    if (isLockedSystem(row.system)) {
      if (row.status !== "locked_mechanic_required") {
        problems.push(`LAW 2: system ${row.system} has status ${row.status}`);
      }
      if (row.confidence !== null) {
        problems.push(`LAW 2: locked system ${row.system} carries a confidence`);
      }
      if (row.findingIds.length > 0) {
        problems.push(`LAW 2: locked system ${row.system} carries findings`);
      }
    }
  }

  // LAW 1: evidence must reference assets that exist in the report.
  const assetIds = new Set(report.assets.map((a) => a.id));
  const checkEvidence = (ownerId: string, ev: Evidence[]): void => {
    for (const e of ev) {
      if (e.kind === "data_record") continue;
      if (!assetIds.has(e.assetId)) {
        problems.push(`LAW 1: ${ownerId} cites unknown asset ${e.assetId}`);
      }
    }
  };
  for (const f of report.findings) checkEvidence(f.id, f.evidence);
  for (const r of report.mechanicReferrals) checkEvidence(r.id, r.evidence);

  // LAW 1: system rows must reference findings that exist.
  const findingIds = new Set(report.findings.map((f) => f.id));
  for (const row of report.systems) {
    for (const id of row.findingIds) {
      if (!findingIds.has(id)) {
        problems.push(`LAW 1: system ${row.system} cites unknown finding ${id}`);
      }
    }
  }

  // LAW 1: price deductions must link to a real finding.
  if (report.price) {
    for (const d of report.price.deductions) {
      if (!findingIds.has(d.findingId)) {
        problems.push(`LAW 1: price deduction cites unknown finding ${d.findingId}`);
      }
    }
  }

  if (problems.length > 0) {
    throw new Error(`Report violates TIREKICK laws:\n  - ${problems.join("\n  - ")}`);
  }
}

/** Parse + law check. This is the only function the web app should use. */
export function parseReport(input: unknown): Report {
  const report = reportSchema.parse(input);
  assertLaws(report);
  return report;
}
