import { parseReport, parseTeaser, type Report, type Teaser } from "@tirekick/shared";

/**
 * Adversarial reports, for the layout gate. Test-only - nothing ships this.
 *
 * ---------------------------------------------------------------------------
 * WHY
 * ---------------------------------------------------------------------------
 *
 * `layout.test.ts` lays out real components in a real engine and measures
 * overflow, line length and contrast. The checks are general. The input was not:
 * one fixture, `demo-01`, with eight findings, short titles and every optional
 * section populated. A report with forty findings, a 900-character detail, or a
 * federal recall string with no spaces in it had never been laid out by anything.
 *
 * That is where the next overflow comes from. Every layout defect P8 found was
 * caused by *content*, not by a rule: a grid whose minimums did not fit, a
 * heading whose one unbreakable token was longer than its panel, a paragraph
 * whose measure was unbounded. All three would have been caught by rendering the
 * same components against nastier data.
 *
 * ---------------------------------------------------------------------------
 * HOW THESE STAY HONEST
 * ---------------------------------------------------------------------------
 *
 * Every case is derived from the real fixture and then passed back through
 * `parseReport`, which runs the zod contract *and* `assertLaws`. So a stress case
 * cannot drift into something the pipeline could never emit: if a mutation
 * orphans a finding id, breaks referential integrity, or attaches a finding to a
 * locked system, the generator throws rather than producing a page that proves
 * nothing.
 *
 * That constraint is doing real work. It is the difference between "the layout
 * survives arbitrary JSON" - which is not a claim worth making - and "the layout
 * survives every report this pipeline is capable of emitting".
 */

/** Deep clone that does not care about prototypes; these are plain JSON trees. */
function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

/**
 * A word with no break opportunity in it.
 *
 * Not arbitrary: NHTSA component strings arrive looking like
 * `POWER TRAIN:AUTOMATIC TRANSMISSION:CONTROL MODULE (TCM)` and are joined into
 * titles with colons, which is what pushed a heading 40px past its panel at
 * 320px. This is that failure with the volume turned up.
 */
const UNBREAKABLE =
  "POWERTRAIN:AUTOMATIC_TRANSMISSION:CONTROL_MODULE:SOFTWARE_CALIBRATION_UPDATE_25V422000_SUPERSEDES_23V858000";

/** 900 characters, which is roughly what a chatty vision model returns. */
const LONG_DETAIL = (
  "The region shows a band of discolouration running along the lower edge of the " +
  "panel, consistent in texture with surface corrosion rather than with a paint " +
  "defect or a reflection, although the distinction cannot be made with certainty " +
  "from a single photograph taken at this angle and in this light. The affected " +
  "area appears continuous rather than spotted, which is more typical of moisture " +
  "held against the metal by trapped debris than of stone chipping. Whether the " +
  "metal beneath is sound, thinned, or perforated cannot be determined remotely at " +
  "any confidence, and no part of this observation should be read as a statement " +
  "about structural integrity, which is not assessed by this product under any " +
  "circumstances. A mechanic can establish the extent in a few minutes on a lift."
).slice(0, 900);

export interface StressCase<T> {
  name: string;
  /** What this case is trying to break, for the failure message. */
  because: string;
  value: T;
}

export function stressReports(base: Report): StressCase<Report>[] {
  const cases: StressCase<Report>[] = [];

  // ---------------------------------------------------------------- volume --
  // Forty findings. Ids are unique and the originals are kept, so every system
  // row still cites a finding that exists.
  {
    const r = clone(base);
    const source = base.findings.filter((f) => f.evidence.length > 0);
    const extra = [];
    for (let i = 0; i < 40; i += 1) {
      const f = clone(source[i % source.length]!);
      f.id = `stress_finding_${i}`;
      f.title = `${f.title} (${i + 1})`;
      extra.push(f);
    }
    r.findings = [...r.findings, ...extra];
    cases.push({
      name: "forty-findings",
      because: "a long report must not change how a single card lays out",
      value: r,
    });
  }

  // ------------------------------------------------------------------ text --
  {
    const r = clone(base);
    for (const f of r.findings) {
      f.detail = LONG_DETAIL;
      f.confidenceBasis = LONG_DETAIL.slice(0, 400);
      f.sellerQuestion = LONG_DETAIL.slice(0, 300);
      f.mechanicCheck = LONG_DETAIL.slice(0, 300);
    }
    for (const ref of r.mechanicReferrals) ref.observation = LONG_DETAIL;
    r.verdict.summary = LONG_DETAIL;
    r.verdict.headline = LONG_DETAIL.slice(0, 220);
    cases.push({
      name: "long-prose",
      because: "the measure cap must hold when the text is much longer than the fixture's",
      value: r,
    });
  }

  {
    const r = clone(base);
    for (const f of r.findings) {
      f.title = `${UNBREAKABLE}`;
      f.detail = `Prefix. ${UNBREAKABLE} suffix.`;
    }
    r.verdict.headline = UNBREAKABLE;
    if (r.vehicle) {
      r.vehicle.decoded.make = UNBREAKABLE.slice(0, 40);
      r.vehicle.decoded.model = UNBREAKABLE.slice(0, 40);
    }
    cases.push({
      name: "unbreakable-tokens",
      because:
        "a 100-character word with no break opportunity is what federal component " +
        "strings actually look like",
      value: r,
    });
  }

  // --------------------------------------------------------------- absence --
  // The empty-handed report: a buyer whose upload produced almost nothing. This
  // is the first real upload's most likely shape, and no page had ever rendered
  // it - every previous test used the fixture where everything is populated.
  {
    const r = clone(base);
    r.findings = [];
    r.mechanicReferrals = [];
    for (const row of r.systems) row.findingIds = [];
    r.price = null;
    r.audio = null;
    r.walkaround = null;
    r.vehicle = null;
    r.verdict.redFlagScore = 0;
    r.verdict.headline = "Nothing was visible in the media provided.";
    cases.push({
      name: "empty-handed",
      because: "the first real upload will look more like this than like the fixture",
      value: r,
    });
  }

  // Assets whose dimensions could not be read - a corrupt file, or a format
  // Pillow could not open. `cropFor` returns null and the viewer must fall back
  // to the whole frame rather than cropping to a guess (D-045).
  {
    const r = clone(base);
    for (const a of r.assets) {
      a.width = null;
      a.height = null;
    }
    cases.push({
      name: "no-dimensions",
      because: "the crop fallback path had never been laid out",
      value: r,
    });
  }

  // ---------------------------------------------------------------- extremes --
  {
    const r = clone(base);
    for (const f of r.findings) {
      f.confidence = f.confidence > 0.5 ? 1 : 0.01;
      if (f.estimatedCostUsd) {
        f.estimatedCostUsd = { low: 0, high: 9_999_999 };
      }
    }
    r.verdict.redFlagScore = 100;
    if (r.price) {
      r.price.askingPriceUsd = 9_999_999;
      r.price.fairRangeUsd = { low: 0, high: 9_999_999 };
    }
    cases.push({
      name: "extreme-numbers",
      because: "a seven-figure price must not push a table wider than the page",
      value: r,
    });
  }

  // Every case must be something the pipeline could legally emit.
  return cases.map((c) => ({ ...c, value: parseReport(c.value) }));
}

export function stressTeasers(base: Teaser): StressCase<Teaser>[] {
  const cases: StressCase<Teaser>[] = [];

  {
    const t = clone(base);
    // No finding cites a photograph: an upload with no vision responses, or a
    // report built entirely from federal records. The free page must render an
    // honest empty state rather than an empty frame (D-044).
    t.sample = null;
    cases.push({
      name: "no-sample",
      because: "the free page must say so rather than showing an empty frame",
      value: t,
    });
  }

  {
    const t = clone(base);
    if (t.sample) {
      t.sample.title = UNBREAKABLE;
      t.sample.detail = LONG_DETAIL;
      t.sample.confidenceBasis = LONG_DETAIL.slice(0, 400);
      t.sample.assetWidth = null;
      t.sample.assetHeight = null;
    }
    t.headline = LONG_DETAIL.slice(0, 240);
    cases.push({
      name: "long-sample",
      because: "the one finding a stranger sees must survive an uncroppable asset",
      value: t,
    });
  }

  return cases.map((c) => ({ ...c, value: parseTeaser(c.value) }));
}
