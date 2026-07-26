import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  LOCKED_SYSTEMS,
  LOCKED_SYSTEM_STATEMENT,
  SHARE_FOOTER,
} from "@tirekick/shared";
import { ReportView } from "./ReportView";
import { demoReport } from "@/lib/report";

/**
 * Report snapshot tests (LAW 7).
 *
 * The snapshot catches unintended drift in the rendered dossier. The assertions
 * around it catch the changes that actually matter: a disclaimer that stopped
 * rendering, a locked system that acquired a score, a finding that lost its
 * evidence. A snapshot alone would go green on a reworded law; these do not.
 */

const html = renderToStaticMarkup(<ReportView report={demoReport} />);

/**
 * Report copy is authored in Python and escaped by React on the way out, so an
 * apostrophe in a finding arrives here as &#x27;. Assertions about what a buyer
 * reads run against the decoded text; assertions about structure (ids, hrefs,
 * styles) run against the raw markup.
 */
const text = html
  .replace(/&#x27;/g, "'")
  .replace(/&quot;/g, '"')
  .replace(/&lt;/g, "<")
  .replace(/&gt;/g, ">")
  .replace(/&amp;/g, "&");

describe("dossier snapshot", () => {
  it("renders the fixture report identically to the committed snapshot", () => {
    expect(html).toMatchSnapshot();
  });
});

describe("disclaimer architecture (LAW 6, LIABILITY section 4)", () => {
  it("renders the banner above the verdict, not at the bottom", () => {
    expect(text).toContain(demoReport.banner);
    expect(text.indexOf(demoReport.banner)).toBeLessThan(text.indexOf("Red-flag score"));
  });

  it("renders the share footer and a link to the accuracy page", () => {
    expect(html).toContain(SHARE_FOOTER);
    expect(html).toContain('href="/accuracy"');
  });

  it("declares the synthetic media provenance (D-010)", () => {
    expect(demoReport.containsSyntheticMedia).toBe(true);
    expect(text).toContain("nothing here describes a real vehicle");
  });

  it("states what the analysis could not assess", () => {
    expect(html).toContain("What this analysis could not assess");
    expect(demoReport.verdict.couldNotAssess.length).toBeGreaterThan(0);
    for (const line of demoReport.verdict.couldNotAssess) {
      expect(text).toContain(line);
    }
  });

  it("puts coverage before the verdict, so the conclusion is read in context", () => {
    expect(html.indexOf("Media coverage")).toBeLessThan(html.indexOf("Red-flag score"));
  });
});

describe("safety-critical lock (LAW 2)", () => {
  it("renders all four locked systems as mechanic-required with no confidence", () => {
    for (const system of LOCKED_SYSTEMS) {
      const row = demoReport.systems.find((s) => s.system === system);
      expect(row, `missing system row: ${system}`).toBeDefined();
      expect(row!.status).toBe("locked_mechanic_required");
      expect(row!.statement).toBe(LOCKED_SYSTEM_STATEMENT);
      // A locked row never carries a confidence, so no bar can be rendered on it.
      expect(row!.confidence).toBeNull();
    }
    expect(html).toContain("MECHANIC REQUIRED");
  });

  it("never renders a pass verdict on a locked system", () => {
    for (const system of LOCKED_SYSTEMS) {
      const row = demoReport.systems.find((s) => s.system === system)!;
      expect(row.status).not.toBe("no_issues_visible");
    }
  });

  it("renders referrals as observations and asks, never as scored findings", () => {
    for (const r of demoReport.mechanicReferrals) {
      expect(LOCKED_SYSTEMS as readonly string[]).toContain(r.system);
      expect(text).toContain(r.observation);
      expect(text).toContain(r.ask);
      expect(r).not.toHaveProperty("severity");
      expect(r).not.toHaveProperty("confidence");
    }
  });

  it("carries no finding whose type targets a locked system", () => {
    for (const f of demoReport.findings) {
      expect(LOCKED_SYSTEMS as readonly string[]).not.toContain(f.type);
    }
  });
});

describe("evidence and confidence (LAW 1)", () => {
  it("gives every finding at least one piece of evidence", () => {
    expect(demoReport.findings.length).toBeGreaterThan(0);
    for (const f of demoReport.findings) {
      expect(f.evidence.length, `no evidence on ${f.id}`).toBeGreaterThan(0);
    }
  });

  it("gives every finding a confidence and a stated basis for it", () => {
    for (const f of demoReport.findings) {
      expect(f.confidence).toBeGreaterThan(0);
      expect(f.confidence).toBeLessThanOrEqual(1);
      expect(f.confidenceBasis.length).toBeGreaterThan(0);
      expect(text).toContain(f.confidenceBasis);
    }
  });

  it("renders every finding with an anchor the overlay boxes can target", () => {
    for (const f of demoReport.findings) {
      expect(html).toContain(`id="${f.id}"`);
      expect(text).toContain(f.title);
    }
    for (const r of demoReport.mechanicReferrals) {
      expect(html).toContain(`id="${r.id}"`);
    }
  });

  it("renders the evidence section for each finding", () => {
    const evidenceHeadings = html.match(/>Evidence</g) ?? [];
    expect(evidenceHeadings).toHaveLength(demoReport.findings.length);
  });
});

describe("price check (never a verdict without comps)", () => {
  it("shows the comps behind any price range it states", () => {
    if (!demoReport.price) return;
    expect(demoReport.price.comps.length).toBeGreaterThan(0);
    expect(html).toContain("The comps behind this range");
    for (const c of demoReport.price.comps) {
      expect(text).toContain(c.sourceNote);
    }
  });

  it("links every deduction to a finding that exists", () => {
    if (!demoReport.price) return;
    const ids = new Set(demoReport.findings.map((f) => f.id));
    for (const d of demoReport.price.deductions) {
      expect(ids).toContain(d.findingId);
      expect(html).toContain(`href="#${d.findingId}"`);
    }
  });
});

describe("cost visibility (LAW 5)", () => {
  it("prints the cost of producing this report", () => {
    expect(html).toContain("Cost to produce");
    expect(html).toContain(`$${demoReport.cost.usdTotal.toFixed(4)}`);
    expect(text).toContain(demoReport.cost.note);
  });

  it("stamps the run mode into the rendered report (D-009)", () => {
    expect(html).toContain(`mode: ${demoReport.mode}`);
  });
});

describe("buyer-facing output", () => {
  it("renders every seller question and negotiation beat", () => {
    expect(demoReport.sellerQuestions.length).toBeGreaterThan(0);
    for (const q of demoReport.sellerQuestions) expect(text).toContain(q);
    expect(demoReport.negotiationScript.length).toBeGreaterThan(0);
    for (const beat of demoReport.negotiationScript) {
      expect(text).toContain(beat.beat);
    }
  });

  it("renders an overlay tile for every photo asset", () => {
    const photos = demoReport.assets.filter((a) => a.kind === "photo");
    expect(photos.length).toBeGreaterThan(0);
    for (const p of photos) {
      expect(html).toContain(`/f/${demoReport.inspectionId}/${p.path}`);
    }
  });
});
