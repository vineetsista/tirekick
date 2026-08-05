import { z } from "zod";
import {
  LOCKED_SYSTEMS,
  LOCKED_SYSTEM_STATEMENT,
  SCHEMA_VERSION,
} from "./constants";

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

const lockedSet: ReadonlySet<string> = new Set(LOCKED_SYSTEMS);

export function isLockedSystem(system: SystemKey): boolean {
  return lockedSet.has(system);
}

/**
 * Turn a list of law violations into zod issues.
 *
 * The LAW 2 rules below are written once, as functions returning the sentences a
 * reader sees, and then attached in two places: a refinement on the sub-schema
 * (so a single finding or row cannot be parsed in violation) and `assertLaws` or
 * `parseTeaser` (which are reachable with an object that was never parsed). Two
 * hand-written copies of the same rule is the drift this package exists to stop,
 * so there is one copy and two call sites.
 */
function addLawIssues(problems: readonly string[], ctx: z.RefinementCtx): void {
  for (const message of problems) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message });
  }
}

export const runModeSchema = z.enum(["fixture", "live"]);

/** Which engine produced a finding. Mirrors `engine_name` in the db package. */
export const engineNameSchema = z.enum(["vision", "audio", "data", "pricing"]);
export type EngineName = z.infer<typeof engineNameSchema>;

/**
 * A `{low, high}` band, in the order a reader would say it.
 *
 * Mirrors CostBand._ordered and PriceRange._ordered in models.py. "$800 to $200"
 * is not a range, it is a typo - and it reaches the buyer either as a sentence
 * they say to a seller or as the floor every price verdict is computed against,
 * which makes an inverted one meaningless in both directions.
 */
function orderedBandSchema(label: string) {
  return z
    .object({ low: z.number().nonnegative(), high: z.number().nonnegative() })
    .superRefine((band, ctx) => {
      if (band.high < band.low) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `inverted ${label}: low=${band.low}, high=${band.high}`,
        });
      }
    });
}

/* ------------------------------------------------------------------ */
/* evidence - LAW 1                                                    */
/* ------------------------------------------------------------------ */

/** Normalized [0,1] box: x,y is the top-left corner. */
export const boundingBoxSchema = z
  .object({
    x: z.number().min(0).max(1),
    y: z.number().min(0).max(1),
    w: z.number().min(0).max(1),
    h: z.number().min(0).max(1),
  })
  .superRefine((box, ctx) => {
    /**
     * Four legal coordinates can still describe an illegal region (D-060).
     *
     * x=0.9 with w=0.4 puts 30% of the cited box outside the photograph. The
     * viewer draws it anyway - clipped, at the wrong size - and a reader cannot
     * redraw the region from the numbers to check the claim, which is the whole
     * point of publishing them (LAW 1). BoundingBox._inside_the_frame has
     * refused this since P9; this side accepted it.
     *
     * The tolerance is the size of a rounding error at four decimal places: the
     * coordinates arrive as fractions of a pixel count and are serialised
     * rounded, so an exactly-full-width box can land at 1.00001.
     */
    const epsilon = 1e-4;
    if (box.x + box.w > 1 + epsilon || box.y + box.h > 1 + epsilon) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message:
          `box runs past the image edge: x+w=${(box.x + box.w).toFixed(4)}, ` +
          `y+h=${(box.y + box.h).toFixed(4)}, both must be <= 1`,
      });
    }
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

export const evidenceSchema = z
  .discriminatedUnion("kind", [
    imageRegionEvidenceSchema,
    audioSegmentEvidenceSchema,
    dataRecordEvidenceSchema,
    documentExcerptEvidenceSchema,
  ])
  .superRefine((ev, ctx) => {
    /**
     * A segment that ends before it starts cites nothing a listener can play.
     * Mirrors AudioSegmentEvidence._ordered.
     *
     * It sits on the union rather than on the member because zod 3's
     * discriminatedUnion accepts only plain objects - refining
     * `audioSegmentEvidenceSchema` in place would take it out of the union it
     * belongs to. Every path that parses evidence goes through here, so the
     * enforcement point is the same one Python has.
     */
    if (ev.kind === "audio_segment" && ev.endSec < ev.startSec) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `audio evidence ends before it starts: ${ev.startSec} -> ${ev.endSec}`,
      });
    }
  });
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
  /**
   * Pixel dimensions of the decoded image, when it is one.
   *
   * Every `image_region` box in this report is a fraction of these. Without
   * them a cited box cannot be checked - the report would hash the pixels a
   * claim was written against without recording their shape.
   */
  width: z.number().int().positive().nullable().default(null),
  height: z.number().int().positive().nullable().default(null),
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

/** Repair cost band. Ordered, because a buyer says it out loud - see D-060. */
export const costBandSchema = orderedBandSchema("cost band");

/** LAW 2 on one finding. Mirrors Finding._law_2_no_locked_systems. */
function lockedFindingProblems(finding: {
  id: string;
  system: SystemKey;
}): string[] {
  if (!isLockedSystem(finding.system)) return [];
  return [`LAW 2: finding ${finding.id} attaches to locked system ${finding.system}`];
}

export const findingSchema = z
  .object({
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
    estimatedCostUsd: costBandSchema.nullable(),
    sellerQuestion: z.string().nullable(),
    mechanicCheck: z.string().nullable(),
    /** Which engine produced it. */
    engine: engineNameSchema,
  })
  .superRefine((finding, ctx) => addLawIssues(lockedFindingProblems(finding), ctx));
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

/**
 * LAW 2 on one systems row, all four clauses. Mirrors SystemRow._law_2_locked_rows.
 *
 * The wording clause is not decoration: a row that says "not remotely verifiable
 * - but nothing looks wrong" is a locked status carrying a clearance, and the
 * status clause cannot see it.
 */
function lockedRowProblems(row: {
  system: SystemKey;
  status: SystemStatus;
  statement: string;
  findingIds: readonly string[];
  confidence: number | null;
}): string[] {
  if (!isLockedSystem(row.system)) return [];
  const problems: string[] = [];
  if (row.status !== "locked_mechanic_required") {
    problems.push(`LAW 2: system ${row.system} has status ${row.status}`);
  }
  if (row.confidence !== null) {
    problems.push(`LAW 2: locked system ${row.system} carries a confidence`);
  }
  if (row.findingIds.length > 0) {
    problems.push(`LAW 2: locked system ${row.system} carries findings`);
  }
  if (row.statement !== LOCKED_SYSTEM_STATEMENT) {
    problems.push(`LAW 2: locked system ${row.system} paraphrases the locked statement`);
  }
  return problems;
}

export const systemRowSchema = z
  .object({
    system: systemKeySchema,
    status: systemStatusSchema,
    statement: z.string().min(1),
    findingIds: z.array(z.string()),
    /** Null for locked systems - a locked row never carries a confidence. */
    confidence: confidenceSchema.nullable(),
  })
  .superRefine((row, ctx) => addLawIssues(lockedRowProblems(row), ctx));
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

/**
 * What was taken from the walkaround video, and what was thrown away.
 *
 * The dropped counts are part of the contract. A report saying "12 frames
 * analysed" without saying 40 were discarded invites the reader to assume the
 * whole video was examined.
 */
export const walkaroundTrackSchema = z.object({
  assetId: z.string().min(1),
  durationSec: z.number().nonnegative(),
  framesSampled: z.number().int().nonnegative(),
  framesAnalysed: z.number().int().nonnegative(),
  droppedBlurred: z.number().int().nonnegative(),
  droppedDuplicate: z.number().int().nonnegative(),
  droppedOverCap: z.number().int().nonnegative(),
  frameAssetIds: z.array(z.string()),
  frameTimesSec: z.array(z.number()),
  statement: z.string().min(1),
});
export type WalkaroundTrack = z.infer<typeof walkaroundTrackSchema>;

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
  make: z.string().nullable(),
  model: z.string().nullable(),
  trim: z.string().nullable(),
  /** When the listing was seen. A stale comp describes a different market. */
  listedOn: z.string(),
  notes: z.string(),
});

/** A listing the buyer supplied that was not used, and why. */
export const excludedCompSchema = z.object({
  compId: z.string().min(1),
  reason: z.string().min(1),
});

export const priceDeductionSchema = z
  .object({
    findingId: z.string().min(1),
    label: z.string().min(1),
    lowUsd: z.number().nonnegative(),
    highUsd: z.number().nonnegative(),
    basis: z.string().min(1),
  })
  .superRefine((d, ctx) => {
    // Same shape as an ordered band under different field names, and the same
    // reason: this one is subtracted from an asking price in front of a seller.
    // Mirrors PriceDeduction._ordered.
    if (d.highUsd < d.lowUsd) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `inverted deduction: low=${d.lowUsd}, high=${d.highUsd}`,
      });
    }
  });

/** The fair range every verdict is computed against. Ordered - see D-060. */
export const priceRangeSchema = orderedBandSchema("price range");

export const priceCheckSchema = z.object({
  askingPriceUsd: z.number().nonnegative(),
  /** LAW 1 - never a verdict without the comps behind it. min 1 enforced here. */
  comps: z.array(compSchema).min(1),
  /** Rendered - a comp silently dropped is a comp the buyer thinks was counted. */
  excluded: z.array(excludedCompSchema),
  normalizationNotes: z.string().min(1),
  fairRangeUsd: priceRangeSchema,
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
  videoSecondsProcessed: z.number().nonnegative(),
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
  walkaround: walkaroundTrackSchema.nullable(),
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
/* introspection, for the gates that compare this file to a second copy */
/* ------------------------------------------------------------------ */

/**
 * The field schemas of a contract object, reached through any refinements.
 *
 * A `z.object` that gains a `.superRefine` becomes a ZodEffects and no longer
 * has `.shape`. `findingSchema`, `systemRowSchema` and `teaserSystemRowSchema`
 * are all refined now, and the column-parity gate in packages/db reads exactly
 * that `.shape` to ask whether every contract field has a column to live in.
 * Its two alternatives were to unwrap zod's internals from a package that does
 * not depend on zod, or to quietly stop comparing the tables whose schema had
 * been refined - which is the failure that gate was written to catch.
 *
 * This hands back the field schemas, not a parser for the whole object: there is
 * deliberately no way to get an unrefined `findingSchema` out of this module and
 * parse a locked-system finding with it.
 */
export function contractShape(schema: z.ZodTypeAny): z.ZodRawShape {
  let inner: z.ZodTypeAny = schema;
  while (inner instanceof z.ZodEffects) inner = inner.innerType() as z.ZodTypeAny;
  if (!(inner instanceof z.ZodObject)) {
    throw new Error(
      `contractShape: ${inner._def.typeName} is not an object schema, refined or otherwise`,
    );
  }
  return inner.shape as z.ZodRawShape;
}

/* ------------------------------------------------------------------ */
/* law assertions - checked on every parse, not just in tests          */
/* ------------------------------------------------------------------ */

/**
 * Structural checks the type system cannot express. Runs after zod parse; a report
 * that fails any of these is a law violation and must not render.
 *
 * This function is the zod-side twin of the model validators in `models.py`, and
 * for nine phases it was the smaller of the two. Anything Python refuses and this
 * accepts is a report the pipeline cannot emit but the viewer will happily render
 * - which is the wrong way round, because the viewer is the side a buyer reads.
 *
 * LAW 2 is not enforced here alone. `lockedFindingProblems` and
 * `lockedRowProblems` are refinements on `findingSchema` and `systemRowSchema`,
 * which is where Pydantic enforces them too, so a single finding or row cannot be
 * parsed in violation by any call site. They are re-run here because this
 * function is exported and takes an already-typed `Report`: a caller that builds
 * one in TypeScript and never parses it reaches these checks and nothing else.
 * The rules themselves are written once, above; only the call sites are two.
 */
export function assertLaws(report: Report): void {
  const problems: string[] = [];

  // LAW 2: no finding may attach to a locked system.
  for (const f of report.findings) problems.push(...lockedFindingProblems(f));

  // LAW 2: every locked system row must be locked, silent and unscored.
  for (const row of report.systems) problems.push(...lockedRowProblems(row));

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

  // LAW 1: the synthetic-media flag must describe the assets it ships with.
  //
  // It is a single boolean that decides whether the "some of this media was
  // generated" banner renders. False on a report carrying generated photographs
  // presents fixture media as a real car's; true on a report of real photographs
  // disclaims evidence that needed no disclaimer. Report._referential_integrity
  // has compared the two since the laws were first written as code.
  const anySynthetic = report.assets.some((a) => a.synthetic);
  if (anySynthetic !== report.containsSyntheticMedia) {
    problems.push("LAW 1: containsSyntheticMedia does not match the assets it describes");
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

/* ------------------------------------------------------------------ */
/* teaser - the free projection                                        */
/* ------------------------------------------------------------------ */

export const severityCountSchema = z.object({
  severity: severitySchema,
  count: z.number().int().nonnegative(),
});

/**
 * A systems row with no statement that could leak a finding. The paid row
 * carries the worst finding's title; locked rows carry the LAW 2 statement,
 * which is identical in every report TIREKICK emits, paid or free.
 */
function lockedTeaserRowProblems(row: {
  system: SystemKey;
  status: SystemStatus;
  statement: string;
}): string[] {
  if (!isLockedSystem(row.system)) return [];
  const problems: string[] = [];
  if (row.status !== "locked_mechanic_required") {
    problems.push(`LAW 2: teaser row ${row.system} is not locked, it says ${row.status}`);
  }
  if (row.statement !== LOCKED_SYSTEM_STATEMENT) {
    problems.push(`LAW 2: teaser row ${row.system} paraphrases the locked statement`);
  }
  return problems;
}

export const teaserSystemRowSchema = z
  .object({
    system: systemKeySchema,
    status: systemStatusSchema,
    statement: z.string().min(1),
  })
  .superRefine((row, ctx) => addLawIssues(lockedTeaserRowProblems(row), ctx));

/**
 * What a buyer sees before paying.
 *
 * This is a genuinely smaller object, not the paid report with things hidden in
 * CSS. Nothing omitted here was ever serialised, which is the only version of a
 * paywall that survives someone opening the network tab.
 */
/**
 * One complete finding, given away.
 *
 * A deliberately separate field rather than a `findings` array of length one.
 * `parseTeaser` refuses any payload carrying `findings` or `assets` - the failure
 * it guards against is a refactor quietly routing a full report down the free
 * path - and that guard stays exactly as strict. This is a disclosure with its
 * own name, which is auditable in a way that a loosened guard would not be.
 */
export const teaserSampleSchema = z.object({
  findingId: z.string().min(1),
  type: findingTypeSchema,
  system: systemKeySchema,
  severity: severitySchema,
  confidence: confidenceSchema,
  confidenceBasis: z.string().min(1),
  title: z.string().min(1),
  detail: z.string().min(1),
  assetId: z.string().min(1),
  assetPath: z.string().min(1),
  assetWidth: z.number().int().positive().nullable().default(null),
  assetHeight: z.number().int().positive().nullable().default(null),
  assetSynthetic: z.boolean().default(false),
  box: boundingBoxSchema,
  caption: z.string().min(1),
  /** "One of 9 findings about this vehicle." Never reads as the whole result. */
  statement: z.string().min(1),
});
export type TeaserSample = z.infer<typeof teaserSampleSchema>;

export const teaserSchema = z.object({
  schemaVersion: z.literal(SCHEMA_VERSION),
  reportId: z.string().min(1),
  inspectionId: z.string().min(1),
  generatedAt: z.string().min(1),
  mode: runModeSchema,
  banner: z.string().min(1),
  /** Year make model. Never a VIN, masked or otherwise. */
  vehicleSummary: z.string(),
  /** Kept in full - it says whether this could answer the question at all. */
  coverage: coverageSchema,
  redFlagScore: z.number().int().min(0).max(100),
  headline: z.string().min(1),
  findingCount: z.number().int().nonnegative(),
  counts: z.array(severityCountSchema),
  mechanicReferralCount: z.number().int().nonnegative(),
  systems: z.array(teaserSystemRowSchema),
  /**
   * One complete finding, free. Null when nothing cites a photograph - an upload
   * with no vision responses, or a report built entirely from federal records.
   */
  sample: teaserSampleSchema.nullable().default(null),
  /** Never behind the paywall. */
  couldNotAssess: z.array(z.string()).min(1),
  hasAudio: z.boolean(),
  hasPriceCheck: z.boolean(),
  /** Generated from the eval-gate registry, not written by hand. */
  accuracyStatement: z.string().min(1),
  priceUsd: z.number().nonnegative(),
  unlocks: z.array(z.string()).min(1),
  containsSyntheticMedia: z.boolean(),
});
export type Teaser = z.infer<typeof teaserSchema>;

/**
 * Parse a teaser, and assert it is actually a teaser.
 *
 * The failure this guards against is a refactor that starts passing the full
 * report through the teaser route. Zod alone would not notice - extra keys are
 * stripped silently by default - so the shape is checked explicitly.
 *
 * LAW 2 on the systems rows is not checked here. It is a refinement on
 * `teaserSystemRowSchema`, which the parse below runs, so a locked row that is
 * not locked never reaches this function's body - and, unlike `assertLaws`,
 * there is no way into `parseTeaser` that skips the parse. It used to be checked
 * here instead, which is why it is worth saying where it went.
 */
export function parseTeaser(input: unknown): Teaser {
  const teaser = teaserSchema.parse(input);

  const leaked = ["findings", "mechanicReferrals", "assets", "price", "vehicle", "audio"];
  const present = leaked.filter(
    (key) => typeof input === "object" && input !== null && key in input,
  );
  if (present.length > 0) {
    throw new Error(
      `Teaser payload carries paid-only fields: ${present.join(", ")}. ` +
        "The teaser must be built by teaser.build_teaser, not by deleting keys " +
        "from a report.",
    );
  }

  return teaser;
}
