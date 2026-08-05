import { describe, expect, it } from "vitest";
import {
  assertLaws,
  boundingBoxSchema,
  confidenceSchema,
  contractShape,
  findingSchema,
  isLockedSystem,
  parseTeaser,
  priceCheckSchema,
  systemRowSchema,
  teaserSystemRowSchema,
  type PriceCheck,
  type Report,
  type Teaser,
} from "./schema";
import { LOCKED_SYSTEMS, LOCKED_SYSTEM_STATEMENT, SCHEMA_VERSION } from "./constants";

/** Minimal law-abiding report used as the base for adversarial mutations. */
function baseReport(): Report {
  return {
    schemaVersion: SCHEMA_VERSION,
    reportId: "rpt_test",
    inspectionId: "insp_test",
    generatedAt: "2026-01-01T00:00:00Z",
    mode: "fixture",
    banner: "banner",
    vehicle: null,
    audio: null,
    walkaround: null,
    assets: [
      {
        id: "asset_1",
        kind: "photo",
        path: "a.jpg",
        sha256: "a".repeat(64),
        bytes: 1,
        viewClass: "exterior_side_left",
        viewConfidence: 0.9,
        durationSec: null,
        synthetic: true,
        width: 1600,
        height: 1200,
      },
    ],
    coverage: {
      requestedViews: ["exterior_side_left"],
      receivedViews: ["exterior_side_left"],
      missingViews: [],
      photoCount: 1,
      hasVideo: false,
      hasAudio: false,
      score: 1,
      statement: "one view",
    },
    verdict: {
      redFlagScore: 10,
      headline: "headline",
      couldNotAssess: ["brakes"],
      summary: "summary",
    },
    findings: [
      {
        id: "f1",
        type: "rust_corrosion",
        system: "exterior",
        title: "Corrosion visible on rocker panel",
        detail: "detail",
        severity: "major",
        confidence: 0.7,
        confidenceBasis: "clear, well-lit region",
        evidence: [
          {
            kind: "image_region",
            assetId: "asset_1",
            box: { x: 0.1, y: 0.1, w: 0.2, h: 0.2 },
            caption: "rocker panel",
          },
        ],
        estimatedCostUsd: null,
        sellerQuestion: null,
        mechanicCheck: null,
        engine: "vision",
      },
    ],
    systems: [
      {
        system: "exterior",
        status: "attention",
        statement: "corrosion visible",
        findingIds: ["f1"],
        confidence: 0.7,
      },
      ...LOCKED_SYSTEMS.map((system) => ({
        system,
        status: "locked_mechanic_required" as const,
        statement: LOCKED_SYSTEM_STATEMENT,
        findingIds: [],
        confidence: null,
      })),
    ],
    mechanicReferrals: [],
    price: null,
    sellerQuestions: [],
    negotiationScript: [],
    cost: {
      mode: "fixture",
      model: "",
      promptFingerprint: "",
      inputTokens: 0,
      outputTokens: 0,
      imagesAnalyzed: 0,
      audioSecondsProcessed: 0,
      videoSecondsProcessed: 0,
      storageBytes: 0,
      federalLookups: 0,
      usdTotal: 0,
      note: "fixture mode",
    },
    containsSyntheticMedia: true,
  };
}

/**
 * A price check that parses. Every price test below mutates one field of this.
 *
 * It exists because the version of "rejects a price verdict with no comps" that
 * preceded it built its payload inline and omitted `excluded`, so the parse threw
 * on a missing key rather than on the empty comps array. The test passed, and
 * would have gone on passing with the `.min(1)` deleted - which is the LAW 1
 * clause it claims to be guarding.
 */
function basePriceCheck(): PriceCheck {
  return {
    askingPriceUsd: 8000,
    comps: [
      {
        id: "comp_1",
        sourceNote: "pasted by the buyer",
        askingPriceUsd: 8500,
        mileage: 90_000,
        year: 2013,
        make: "Honda",
        model: "Accord",
        trim: null,
        listedOn: "2026-01-01",
        notes: "",
      },
    ],
    excluded: [],
    normalizationNotes: "mileage-adjusted",
    fairRangeUsd: { low: 7000, high: 9000 },
    deductions: [],
    verdict: "in_range",
    verdictStatement: "asking price sits inside the range",
  };
}

/** A teaser that parses, for mutating in the LAW 2 tests below. */
function baseTeaser(): Teaser {
  const report = baseReport();
  return {
    schemaVersion: SCHEMA_VERSION,
    reportId: report.reportId,
    inspectionId: report.inspectionId,
    generatedAt: report.generatedAt,
    mode: "fixture",
    banner: report.banner,
    vehicleSummary: "2013 Honda Accord",
    coverage: report.coverage,
    redFlagScore: 10,
    headline: "headline",
    findingCount: 1,
    counts: [{ severity: "major", count: 1 }],
    mechanicReferralCount: 0,
    systems: [
      { system: "exterior", status: "attention", statement: "Something was found here." },
      ...LOCKED_SYSTEMS.map((system) => ({
        system,
        status: "locked_mechanic_required" as const,
        statement: LOCKED_SYSTEM_STATEMENT,
      })),
    ],
    sample: null,
    couldNotAssess: ["brakes"],
    hasAudio: false,
    hasPriceCheck: false,
    accuracyStatement: "no finding type has been measured yet",
    priceUsd: 25,
    unlocks: ["every finding"],
    containsSyntheticMedia: true,
  };
}

/** A locked systems row exactly as LAW 2 requires it. Mutated one field at a time. */
function lockedRow() {
  return {
    system: "brakes" as const,
    status: "locked_mechanic_required" as const,
    statement: LOCKED_SYSTEM_STATEMENT,
    findingIds: [] as string[],
    confidence: null,
  };
}

describe("LAW 1 - truth", () => {
  it("rejects a finding with no evidence", () => {
    const f = baseReport().findings[0]!;
    expect(() => findingSchema.parse({ ...f, evidence: [] })).toThrow();
  });

  it("rejects a finding whose evidence cites an asset not in the report", () => {
    const r = baseReport();
    r.findings[0]!.evidence[0] = {
      kind: "image_region",
      assetId: "asset_ghost",
      box: { x: 0, y: 0, w: 0.1, h: 0.1 },
      caption: "nowhere",
    };
    expect(() => assertLaws(r)).toThrow(/cites unknown asset/);
  });

  it("rejects a system row citing a finding that does not exist", () => {
    const r = baseReport();
    r.systems[0]!.findingIds = ["f_ghost"];
    expect(() => assertLaws(r)).toThrow(/cites unknown finding/);
  });

  it("rejects a price verdict with no comps behind it", () => {
    expect(() => priceCheckSchema.parse({ ...basePriceCheck(), comps: [] })).toThrow();
  });

  it("rejects a report whose synthetic-media flag contradicts its assets", () => {
    const r = baseReport();
    r.containsSyntheticMedia = false;
    expect(() => assertLaws(r)).toThrow(/containsSyntheticMedia does not match/);
  });

  it("rejects a report that declares synthetic media it does not carry", () => {
    const r = baseReport();
    r.assets[0]!.synthetic = false;
    expect(() => assertLaws(r)).toThrow(/containsSyntheticMedia does not match/);
  });
});

describe("LAW 2 - safety-critical", () => {
  it("names exactly the four locked systems", () => {
    expect([...LOCKED_SYSTEMS]).toEqual([
      "brakes",
      "restraints",
      "structure",
      "steering",
    ]);
    expect(isLockedSystem("brakes")).toBe(true);
    expect(isLockedSystem("exterior")).toBe(false);
  });

  it("rejects a report where a finding attaches to a locked system", () => {
    const r = baseReport();
    r.findings[0]!.system = "brakes";
    expect(() => assertLaws(r)).toThrow(/attaches to locked system brakes/);
  });

  it("rejects a locked system row that claims anything other than locked", () => {
    const r = baseReport();
    const brakes = r.systems.find((s) => s.system === "brakes")!;
    brakes.status = "no_issues_visible";
    brakes.statement = "Brakes look fine.";
    expect(() => assertLaws(r)).toThrow(/system brakes has status/);
  });

  it("rejects a confidence score on a locked system row", () => {
    const r = baseReport();
    r.systems.find((s) => s.system === "steering")!.confidence = 0.98;
    expect(() => assertLaws(r)).toThrow(/carries a confidence/);
  });

  it("rejects a locked system row that paraphrases the locked statement", () => {
    const r = baseReport();
    r.systems.find((s) => s.system === "structure")!.statement =
      "Not remotely verifiable. Ask a mechanic.";
    expect(() => assertLaws(r)).toThrow(/paraphrases the locked statement/);
  });
});

/**
 * LAW 2 is refused by the schema that defines the shape, not only by the
 * function that inspects a whole report.
 *
 * Pydantic enforces this on `Finding`, `SystemRow` and `TeaserSystemRow`
 * themselves, so `Finding(system="brakes", ...)` cannot be constructed at all.
 * Zod enforced it only in `assertLaws` and `parseTeaser`, which meant
 * `findingSchema.safeParse({...finding, system: "brakes"})` succeeded - and any
 * call site that parses one finding or one row rather than a whole report got
 * the permissive copy of the law the product rests on.
 *
 * These parse a single object. Nothing here goes through `assertLaws`, which is
 * the point: the report-level tests above would pass with every refinement below
 * deleted.
 */
describe("LAW 2 - the sub-schema refuses it, not just the whole report", () => {
  it("rejects a finding attached to a locked system", () => {
    const f = baseReport().findings[0]!;
    expect(() => findingSchema.parse({ ...f, system: "brakes" })).toThrow(
      /attaches to locked system brakes/,
    );
  });

  it("accepts a finding on a system that is not locked", () => {
    const f = baseReport().findings[0]!;
    expect(() => findingSchema.parse(f)).not.toThrow();
  });

  it("rejects a locked row with any status but locked", () => {
    expect(() =>
      systemRowSchema.parse({
        ...lockedRow(),
        status: "no_issues_visible",
        statement: "Brakes look fine.",
      }),
    ).toThrow(/system brakes has status no_issues_visible/);
  });

  it("rejects a locked row that carries a confidence", () => {
    expect(() => systemRowSchema.parse({ ...lockedRow(), confidence: 0.9 })).toThrow(
      /carries a confidence/,
    );
  });

  it("rejects a locked row that carries findings", () => {
    expect(() => systemRowSchema.parse({ ...lockedRow(), findingIds: ["f1"] })).toThrow(
      /carries findings/,
    );
  });

  it("rejects a locked row that paraphrases the locked statement", () => {
    expect(() =>
      systemRowSchema.parse({ ...lockedRow(), statement: "Ask a mechanic." }),
    ).toThrow(/paraphrases the locked statement/);
  });

  it("accepts a locked row that obeys all four clauses", () => {
    expect(() => systemRowSchema.parse(lockedRow())).not.toThrow();
  });

  it("leaves an unlocked row alone", () => {
    expect(() =>
      systemRowSchema.parse({
        system: "exterior",
        status: "no_issues_visible",
        statement: "Nothing adverse visible.",
        findingIds: [],
        confidence: 0.8,
      }),
    ).not.toThrow();
  });

  it("rejects a locked teaser row with any status but locked", () => {
    expect(() =>
      teaserSystemRowSchema.parse({
        system: "brakes",
        status: "no_issues_visible",
        statement: "Nothing looks wrong.",
      }),
    ).toThrow(/teaser row brakes is not locked/);
  });

  it("rejects a locked teaser row that paraphrases the locked statement", () => {
    expect(() =>
      teaserSystemRowSchema.parse({
        system: "structure",
        status: "locked_mechanic_required",
        statement: "Not remotely verifiable. Ask a mechanic.",
      }),
    ).toThrow(/paraphrases the locked statement/);
  });

  it("accepts a locked teaser row in the exact wording", () => {
    expect(() =>
      teaserSystemRowSchema.parse({
        system: "steering",
        status: "locked_mechanic_required",
        statement: LOCKED_SYSTEM_STATEMENT,
      }),
    ).not.toThrow();
  });
});

/**
 * The field schemas of a contract object survive being refined.
 *
 * `contractShape` exists because the LAW 2 refinements above turn
 * `findingSchema` into a ZodEffects, which has no `.shape` - and the
 * column-parity gate in packages/db reads exactly that to ask whether every
 * contract field has somewhere to be stored. Without this the gate would have
 * had to unwrap zod's internals from a package that does not depend on zod, or
 * quietly drop `findings` from the tables it compares.
 */
describe("contractShape", () => {
  it("reaches the fields of a schema a refinement wrapped", () => {
    expect(Object.keys(contractShape(boundingBoxSchema)).sort()).toEqual([
      "h",
      "w",
      "x",
      "y",
    ]);
    expect(Object.keys(contractShape(findingSchema))).toContain("estimatedCostUsd");
  });

  it("refuses a schema that is not an object under its refinements", () => {
    expect(() => contractShape(confidenceSchema)).toThrow(/not an object/);
  });
});

/**
 * The free page is held to LAW 2 by the same wording as the paid one.
 *
 * `parseTeaser` checked the statement and not the status, so a teaser row could
 * say `no_issues_visible` while carrying the sentence that says the opposite -
 * a cleared brake system on the one surface a stranger reads before paying.
 * Python's TeaserSystemRow has refused both since it was written.
 */
describe("LAW 2 - the teaser is locked by the same rule", () => {
  /**
   * A hand-built teaser, not one the pipeline emitted - this file has no
   * pipeline. The artifact `teaser.py` actually writes is parsed by
   * contract.test.ts, which is the gate that would catch a drift between them.
   */
  it("accepts a hand-built teaser whose locked rows obey LAW 2", () => {
    expect(() => parseTeaser(baseTeaser())).not.toThrow();
  });

  it("rejects a locked teaser row with any status but locked", () => {
    const t = baseTeaser();
    t.systems.find((s) => s.system === "restraints")!.status = "no_issues_visible";
    expect(() => parseTeaser(t)).toThrow(/teaser row restraints is not locked/);
  });

  it("rejects a locked teaser row that paraphrases the statement", () => {
    const t = baseTeaser();
    t.systems.find((s) => s.system === "brakes")!.statement = "See a mechanic.";
    expect(() => parseTeaser(t)).toThrow(/paraphrases the locked statement/);
  });
});

/**
 * The shapes D-060 taught the Python models to refuse, refused here too.
 *
 * Every one of these was representable in zod while `models.py` rejected it,
 * which means the two copies of the contract disagreed about what a valid report
 * is - and the permissive copy was the one that renders to the buyer.
 */
describe("D-060 - a shape must be the shape it claims to be", () => {
  it("rejects a box that runs off the edge of the photograph", () => {
    expect(() => boundingBoxSchema.parse({ x: 0.9, y: 0.1, w: 0.4, h: 0.2 })).toThrow(
      /past the image edge/,
    );
    expect(() => boundingBoxSchema.parse({ x: 0.1, y: 0.85, w: 0.2, h: 0.3 })).toThrow(
      /past the image edge/,
    );
  });

  it("allows a full-frame box that serialisation rounded a hair past 1", () => {
    expect(() =>
      boundingBoxSchema.parse({ x: 0.5, y: 0.5, w: 0.50005, h: 0.5 }),
    ).not.toThrow();
  });

  it("rejects audio evidence that ends before it starts", () => {
    const f = baseReport().findings[0]!;
    expect(() =>
      findingSchema.parse({
        ...f,
        evidence: [
          {
            kind: "audio_segment",
            assetId: "asset_1",
            startSec: 9,
            endSec: 4,
            caption: "a knock at idle",
          },
        ],
      }),
    ).toThrow(/ends before it starts/);
  });

  it("rejects an inverted repair cost band", () => {
    const f = baseReport().findings[0]!;
    expect(() =>
      findingSchema.parse({ ...f, estimatedCostUsd: { low: 800, high: 200 } }),
    ).toThrow(/inverted cost band/);
  });

  it("rejects an inverted fair price range", () => {
    const p = basePriceCheck();
    p.fairRangeUsd = { low: 9000, high: 7000 };
    expect(() => priceCheckSchema.parse(p)).toThrow(/inverted price range/);
  });

  it("rejects an inverted price deduction", () => {
    const p = basePriceCheck();
    p.deductions = [
      { findingId: "f1", label: "rust", lowUsd: 900, highUsd: 300, basis: "the band above" },
    ];
    expect(() => priceCheckSchema.parse(p)).toThrow(/inverted deduction/);
  });
});

describe("a law-abiding report passes", () => {
  it("does not throw", () => {
    expect(() => assertLaws(baseReport())).not.toThrow();
  });
});
