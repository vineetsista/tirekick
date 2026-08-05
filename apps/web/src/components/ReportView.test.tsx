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
    expect(text).toContain("no statement here about condition");
    // The fixture is mixed: drawn media, real federal records. Saying only
    // "this is synthetic" would understate the vehicle record, and saying
    // nothing would overstate the photographs.
    expect(text).toContain("The federal records below are real");
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

describe("vehicle record (P1 data engine)", () => {
  const vehicle = demoReport.vehicle!;

  it("renders the decoded vehicle from the federal record", () => {
    expect(vehicle).not.toBeNull();
    expect(text).toContain(vehicle.vinMasked);
    expect(text).toContain(String(vehicle.decoded.year));
    expect(text).toContain(vehicle.decoded.make!);
  });

  it("never renders the full VIN", () => {
    // LIABILITY section 6. The serial identifies one physical car.
    expect(html).not.toContain(vehicle.vin);
    expect(vehicle.vinMasked).toContain("******");
  });

  it("states the recall scope above the recall count, not below it", () => {
    expect(text).toContain(vehicle.recallScope);
    expect(text).toContain("by model, not by VIN");
    expect(html.indexOf("Recalls - what this list is")).toBeLessThan(
      html.indexOf("Owner complaints for this model"),
    );
  });

  it("never claims a recall is outstanding on this particular vehicle", () => {
    // The single most likely misreading of this report.
    const recalls = demoReport.findings.filter((f) => f.type === "open_recall");
    expect(recalls.length).toBeGreaterThan(0);
    for (const finding of recalls) {
      expect(finding.detail).toContain("cannot tell whether it was ever carried out");
    }
    expect(text).not.toContain("open recalls on this VIN");
  });

  it("says complaint counts describe the model rather than this car", () => {
    expect(vehicle.complaintSummary).not.toBeNull();
    expect(text).toContain(vehicle.complaintSummary!.scope);
    expect(text).toContain("None of them describes this car");
  });

  it("cites every federal lookup with what it covered and when", () => {
    // LAW 1 - a database claim carries a citation exactly as a visual one does.
    expect(vehicle.sources.length).toBeGreaterThan(0);
    for (const source of vehicle.sources) {
      expect(text).toContain(source.source);
      expect(text).toContain(source.retrievedAt);
      expect(source.bodySha256).toHaveLength(64);
    }
  });
});

describe("engine audio (P3)", () => {
  const track = demoReport.audio!;

  it("renders a spectrogram and the measurements taken from it", () => {
    expect(track).not.toBeNull();
    expect(html).toContain(track.spectrogramPath);
    expect(text).toContain(`${track.durationSec.toFixed(1)}s`);
    expect(text).toContain(`${track.impliedRpm!.toLocaleString()} rpm`);
  });

  it("states the gate before the picture, not under it", () => {
    // LAW 4 has to be read before the evidence it is qualifying.
    //
    // Anchored on the figure caption rather than the image URL: React hoists a
    // <link rel="preload"> for every image to the top of the document, so the
    // path appears long before the element a reader actually sees.
    expect(text.indexOf(track.claimsStatement.slice(0, 40))).toBeLessThan(
      text.indexOf("frequency, low at bottom"),
    );
  });

  it("marks where the transients are without naming what made them", () => {
    expect(track.transients.length).toBeGreaterThan(0);
    for (const t of track.transients) {
      expect(text).toContain(`${t.atSec.toFixed(1)}s`);
    }
    expect(text).toContain("not telling you what it heard");
  });

  it("makes no audio claim anywhere in the report", () => {
    expect(track.claimsEnabled).toBe(false);
    expect(demoReport.findings.some((f) => f.engine === "audio")).toBe(false);
    expect(demoReport.findings.some((f) => f.type === "audio_anomaly")).toBe(false);
    // The words a knocking-engine report would use, none of which we have earned.
    for (const phrase of ["knock", "misfire", "bearing", "valvetrain", "tappet"]) {
      expect(text.toLowerCase()).not.toContain(phrase);
    }
  });

  it("says what the absence of transients would not mean", () => {
    expect(track.transientStatement.length).toBeGreaterThan(0);
  });
});

describe("title brand indicators (P1 history engine)", () => {
  it("quotes the document line behind every title-brand finding", () => {
    const brands = demoReport.findings.filter(
      (f) => f.type === "title_brand_indicator",
    );
    expect(brands.length).toBeGreaterThan(0);
    for (const finding of brands) {
      const excerpt = finding.evidence.find((e) => e.kind === "document_excerpt");
      expect(excerpt, `${finding.id} cites no document excerpt`).toBeDefined();
      expect(text).toContain(excerpt!.excerpt);
    }
  });

  it("does not flag a brand the paperwork explicitly denies", () => {
    // The fixture document denies salvage, flood, lemon and junk. A scanner
    // that matched on the keyword alone would report all four.
    const ids = demoReport.findings.map((f) => f.id).join(" ");
    expect(ids).not.toContain("title_salvage");
    expect(ids).not.toContain("title_flood");
    expect(ids).not.toContain("title_lemon");
    expect(ids).not.toContain("title_junk");
  });

  it("routes a document reporting structural damage to a mechanic referral", () => {
    // LAW 2 does not care which engine spoke.
    const referral = demoReport.mechanicReferrals.find(
      (r) => r.id === "ref_title_structural_history_01",
    );
    expect(referral).toBeDefined();
    expect(referral!.system).toBe("structure");
    expect(demoReport.findings.some((f) => f.system === "structure")).toBe(false);
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

  /**
   * The test the layout comment used to stand in for.
   *
   * `Overlay.tsx` has claimed since P2 that "evidence and claim are never more
   * than one interaction apart (LAW 1)". On the rendered dossier the gallery sat
   * at roughly 1,300px and the findings began at roughly 5,000px, and what sat
   * beside each claim was `photo_01 [0.08, 0.62, 0.34, 0.14]`. The comment was
   * true as an intention and false as a description, and nothing failed, because
   * a claim about layout written in a docstring is not a test.
   *
   * So this asserts adjacency as a measured property of the markup rather than
   * trusting any comment - including the ones written this phase.
   */
  it("puts the cited photograph inside the finding that cites it", () => {
    const cited = demoReport.findings.filter((f) =>
      f.evidence.some((e) => e.kind === "image_region"),
    );
    expect(cited.length).toBeGreaterThan(0);

    for (const finding of cited) {
      const start = html.indexOf(`id="${finding.id}"`);
      expect(start, `${finding.id} does not render`).toBeGreaterThan(-1);

      // The finding's own markup, bounded by wherever the next one begins.
      const nextStarts = demoReport.findings
        .map((f) => html.indexOf(`id="${f.id}"`))
        .filter((i) => i > start);
      const end = nextStarts.length ? Math.min(...nextStarts) : html.length;
      const article = html.slice(start, end);

      for (const e of finding.evidence) {
        if (e.kind !== "image_region") continue;
        const asset = demoReport.assets.find((a) => a.id === e.assetId);
        expect(asset, `${e.assetId} is cited but absent`).toBeDefined();
        expect(
          article,
          `${finding.id} cites ${e.assetId} without showing it`,
        ).toContain(`/f/${demoReport.inspectionId}/${asset!.path}`);
      }
    }
  });

  it("keeps the coordinates as well as the picture", () => {
    // The numbers are what makes a claim checkable against the asset hash. The
    // crop replaced them as the *evidence*, not as the citation.
    for (const finding of demoReport.findings) {
      for (const e of finding.evidence) {
        if (e.kind !== "image_region") continue;
        expect(text).toContain(
          `${e.assetId} [${e.box.x.toFixed(2)}, ${e.box.y.toFixed(2)}, ` +
            `${e.box.w.toFixed(2)}, ${e.box.h.toFixed(2)}]`,
        );
      }
    }
  });

  it("renders an evidence list for every finding whose evidence is not an image", () => {
    const withOther = demoReport.findings.filter((f) =>
      f.evidence.some((e) => e.kind !== "image_region"),
    );
    expect(withOther.length).toBeGreaterThan(0);
    expect(html.match(/>Evidence</g) ?? []).toHaveLength(withOther.length);
  });

  it("shows a crop only for an asset whose dimensions were recorded", () => {
    // cropFor returns null without them and the component falls back to the
    // whole frame. Silently cropping to a guessed region would be evidence that
    // is approximately honest.
    for (const finding of demoReport.findings) {
      for (const e of finding.evidence) {
        if (e.kind !== "image_region") continue;
        const asset = demoReport.assets.find((a) => a.id === e.assetId)!;
        expect(asset.width, `${asset.id} has no width`).toBeTruthy();
        expect(asset.height, `${asset.id} has no height`).toBeTruthy();
      }
    }
  });
});

describe("the sticky nav is a contents page for what is actually there", () => {
  /**
   * The nav was a hand-written array sitting next to the sections it claimed to
   * list, and it drifted the way hand-written lists always do: P7 added the
   * walkaround section, nobody added the walkaround entry, and for two phases the
   * only route to it was scrolling past the gallery. `run` had never been in it
   * either. Nothing failed, because no test compared the two.
   *
   * The list is derived now. This is the assertion that keeps it derived - it
   * fails for a section rendered outside the array as loudly as it failed for the
   * walkaround, which the derivation on its own cannot do.
   */
  const navStart = html.indexOf('aria-label="Report sections"');
  const nav = html.slice(navStart, html.indexOf("</nav>", navStart));

  /** The <section> elements `Section` renders, by id. Gallery tiles are divs. */
  const rendered = [...html.matchAll(/<section class="section" id="([^"]+)"/g)].map(
    (m) => m[1]!,
  );

  it("renders the sections this fixture should produce", () => {
    // A guard on the guard: both assertions below pass vacuously if the scan
    // finds nothing, and the whole point is the section nobody noticed.
    expect(rendered.length).toBeGreaterThan(10);
    expect(demoReport.walkaround, "the fixture has no walkaround to list").not.toBeNull();
    expect(rendered).toContain("walkaround");
  });

  it("gives every rendered section an entry in the nav", () => {
    const missing = rendered.filter((id) => !nav.includes(`href="#${id}"`));
    expect(missing, `sections a reader cannot navigate to: ${missing.join(", ")}`).toEqual(
      [],
    );
  });

  it("points every nav entry at a section that exists", () => {
    // The other direction. An anchor to a section the report did not render
    // scrolls nowhere and reads as a broken page rather than an absent feature.
    const targets = [...nav.matchAll(/href="#([^"]+)"/g)].map((m) => m[1]!);
    expect(targets.length).toBe(rendered.length);
    for (const id of targets) {
      expect(rendered, `nav links #${id}, which nothing renders`).toContain(id);
    }
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
