import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Finding, MechanicReferral } from "@tirekick/shared";
import { Overlay, annotationsFor } from "./Overlay";
import { demoReport } from "@/lib/report";

/**
 * Overlay render tests (LAW 7).
 *
 * The overlay is where LAW 1 is either honoured or broken in the interface: a box
 * drawn on an image IS the citation. These tests assert the mapping from evidence
 * to box, and they assert the LAW 2 asymmetry survives the trip into the DOM -
 * a locked-system box may exist, but it may never carry a severity or a number.
 */

const box = { x: 0.1, y: 0.2, w: 0.3, h: 0.4 };

/** Indexing under noUncheckedIndexedAccess: fail loudly rather than assert away. */
function only<T>(items: T[]): T {
  expect(items).toHaveLength(1);
  return items[0] as T;
}

function finding(over: Partial<Finding> = {}): Finding {
  return {
    id: "f_test",
    type: "rust_corrosion",
    engine: "vision",
    severity: "major",
    confidence: 0.82,
    confidenceBasis: "test",
    title: "Test finding",
    detail: "Test detail",
    evidence: [
      { kind: "image_region", assetId: "photo_01", box, caption: "test caption" },
    ],
    estimatedCostUsd: null,
    sellerQuestion: null,
    mechanicCheck: null,
    ...over,
  } as Finding;
}

function referral(over: Partial<MechanicReferral> = {}): MechanicReferral {
  return {
    id: "r_test",
    system: "brakes",
    observation: "Test observation",
    ask: "Test ask",
    evidence: [
      { kind: "image_region", assetId: "photo_01", box, caption: "test caption" },
    ],
    ...over,
  } as MechanicReferral;
}

describe("annotationsFor", () => {
  it("keeps only evidence belonging to the requested asset", () => {
    const other = finding({
      id: "f_other",
      evidence: [
        { kind: "image_region", assetId: "photo_09", box, caption: "elsewhere" },
      ],
    });
    const out = annotationsFor("photo_01", [finding(), other]);
    expect(only(out).href).toBe("#f_test");
  });

  it("ignores evidence that is not an image region", () => {
    const audio = finding({
      id: "f_audio",
      evidence: [
        {
          kind: "audio_segment",
          assetId: "photo_01",
          startSec: 1,
          endSec: 2,
          caption: "not drawable",
        },
      ],
    });
    expect(annotationsFor("photo_01", [audio])).toHaveLength(0);
  });

  it("labels a finding with its severity and confidence to two decimals", () => {
    const a = only(annotationsFor("photo_01", [finding()]));
    expect(a.label).toBe("RUST CORROSION / MAJOR / 0.82");
    expect(a.caption).toBe("test caption");
  });

  it("emits one annotation per evidence region, not per finding", () => {
    const two = finding({
      evidence: [
        { kind: "image_region", assetId: "photo_01", box, caption: "first" },
        { kind: "image_region", assetId: "photo_01", box, caption: "second" },
      ],
    });
    expect(annotationsFor("photo_01", [two])).toHaveLength(2);
  });

  // LAW 2. A locked system can be pointed at, never scored.
  it("draws a referral box in the locked color with no severity and no number", () => {
    const a = only(annotationsFor("photo_01", [], [referral()]));
    expect(a.color).toBe("var(--tk-locked)");
    expect(a.label).toBe("BRAKES / MECHANIC REQUIRED");
    expect(a.label).not.toMatch(/\d/);
    expect(a.label).not.toMatch(/INFO|MINOR|MAJOR|CRITICAL/);
    expect(a.href).toBe("#r_test");
  });

  it("never labels any referral in the real fixture report with a number", () => {
    for (const asset of demoReport.assets) {
      const annotations = annotationsFor(asset.id, [], demoReport.mechanicReferrals);
      for (const a of annotations) {
        expect(a.label).not.toMatch(/\d/);
        expect(a.color).toBe("var(--tk-locked)");
      }
    }
  });
});

describe("Overlay rendering", () => {
  const annotations = annotationsFor("photo_01", [finding()], [referral()]);

  it("positions every box as a percentage of the frame", () => {
    const html = renderToStaticMarkup(
      <Overlay src="/f/x/photo_01.jpg" alt="test" annotations={annotations} synthetic={false} />,
    );
    expect(html).toContain("left:10.000%");
    expect(html).toContain("top:20.000%");
    expect(html).toContain("width:30.000%");
    expect(html).toContain("height:40.000%");
  });

  it("renders one anchor per annotation so every box links to its claim", () => {
    const html = renderToStaticMarkup(
      <Overlay src="/f/x/photo_01.jpg" alt="test" annotations={annotations} synthetic={false} />,
    );
    expect(html.match(/<a /g) ?? []).toHaveLength(annotations.length);
    expect(html).toContain('href="#f_test"');
    expect(html).toContain('href="#r_test"');
  });

  it("shows the synthetic badge only when the asset is synthetic", () => {
    const on = renderToStaticMarkup(
      <Overlay src="/x.jpg" alt="t" annotations={[]} synthetic={true} />,
    );
    const off = renderToStaticMarkup(
      <Overlay src="/x.jpg" alt="t" annotations={[]} synthetic={false} />,
    );
    expect(on).toContain("SYNTHETIC FIXTURE");
    expect(off).not.toContain("SYNTHETIC FIXTURE");
  });

  it("renders an image with alt text and no boxes when nothing was flagged", () => {
    const html = renderToStaticMarkup(
      <Overlay src="/f/x/photo_01.jpg" alt="engine bay - photo_01" annotations={[]} synthetic={false} />,
    );
    expect(html).toContain('alt="engine bay - photo_01"');
    expect(html).not.toContain("<a ");
  });
});

/**
 * LAW 1 at the level of the whole fixture report: every box drawn anywhere in the
 * evidence gallery must resolve to an anchor that actually exists on the page.
 * A citation pointing at nothing is worse than no citation.
 */
describe("evidence linkage across the fixture report", () => {
  it("links every drawn box to a finding or referral id present in the report", () => {
    const ids = new Set([
      ...demoReport.findings.map((f) => `#${f.id}`),
      ...demoReport.mechanicReferrals.map((r) => `#${r.id}`),
    ]);
    let drawn = 0;
    for (const asset of demoReport.assets) {
      for (const a of annotationsFor(
        asset.id,
        demoReport.findings,
        demoReport.mechanicReferrals,
      )) {
        expect(ids).toContain(a.href);
        expect(a.caption.length).toBeGreaterThan(0);
        drawn += 1;
      }
    }
    expect(drawn).toBeGreaterThan(0);
  });

  it("keeps every box inside the frame", () => {
    for (const asset of demoReport.assets) {
      for (const a of annotationsFor(
        asset.id,
        demoReport.findings,
        demoReport.mechanicReferrals,
      )) {
        expect(a.box.x).toBeGreaterThanOrEqual(0);
        expect(a.box.y).toBeGreaterThanOrEqual(0);
        expect(a.box.x + a.box.w).toBeLessThanOrEqual(1.0001);
        expect(a.box.y + a.box.h).toBeLessThanOrEqual(1.0001);
      }
    }
  });
});
