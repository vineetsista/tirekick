import { describe, expect, it } from "vitest";
import {
  assertLaws,
  findingSchema,
  isLockedSystem,
  priceCheckSchema,
  type Report,
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
      storageBytes: 0,
      federalLookups: 0,
      usdTotal: 0,
      note: "fixture mode",
    },
    containsSyntheticMedia: true,
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
    expect(() =>
      priceCheckSchema.parse({
        askingPriceUsd: 8000,
        comps: [],
        normalizationNotes: "n",
        fairRangeUsd: { low: 7000, high: 9000 },
        deductions: [],
        verdict: "in_range",
        verdictStatement: "fair",
      }),
    ).toThrow();
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
});

describe("a law-abiding report passes", () => {
  it("does not throw", () => {
    expect(() => assertLaws(baseReport())).not.toThrow();
  });
});
