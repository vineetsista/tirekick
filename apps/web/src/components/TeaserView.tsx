import Link from "next/link";
import { LOCKED_SYSTEM_STATEMENT, type SystemStatus, type Teaser } from "@tirekick/shared";
import { EvidenceCrop } from "./EvidenceCrop";
import { assetUrl, severityColor, statusColor, statusLabel, titleCase } from "@/lib/report";

/**
 * The free result.
 *
 * Everything here was chosen server-side by `teaser.py`. There is nothing hidden
 * in this markup - no findings arrive and get styled away - because a paywall
 * implemented in CSS is a paywall that lasts until someone opens the network tab.
 *
 * ---------------------------------------------------------------------------
 * ONE FINDING IS FREE, AND IT IS THE BEST ONE
 * ---------------------------------------------------------------------------
 *
 * This page sold "every finding, with the photograph it came from and a box drawn
 * on it" while rendering zero images. A stranger deciding whether to spend $25 on
 * a visual evidence product could not see any visual evidence first, which asks
 * them to take the entire thing on faith.
 *
 * So `teaser.sample` crosses the paywall in full - picture, box, confidence, and
 * the sentence explaining why that confidence and not a higher one. The worst
 * finding about the vehicle rather than the mildest, because showing the least of
 * what was found in order to hold the best back is a sales tactic, and the
 * coverage block above it already says how much of the car this could speak for.
 *
 * The ordering is deliberate and it is not the conversion-optimal one. Coverage
 * first, then what could not be assessed, then the sample, then the score, and
 * only then the offer. A buyer should be able to decide this is not worth $25 for
 * their six-photo listing before they ever see a price.
 */
export function TeaserView({ teaser }: { teaser: Teaser }) {
  const grouped = groupSystems(teaser);

  return (
    <div className="wrap" style={{ paddingTop: "var(--s-6)", paddingBottom: "var(--s-9)" }}>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          flexWrap: "wrap",
          gap: "var(--s-3)",
          paddingBottom: "var(--s-4)",
          borderBottom: "1px solid var(--tk-rule)",
        }}
      >
        <Link href="/" style={{ textDecoration: "none" }}>
          <span style={{ fontWeight: 800, letterSpacing: "0.24em", fontSize: "var(--t-md)" }}>
            TIREKICK
          </span>
        </Link>
        <span className="label data">free result / {teaser.inspectionId}</span>
      </header>

      <div
        className="panel panel-edge prose-sm"
        style={{ marginTop: "var(--s-5)", borderLeftColor: "var(--tk-locked)" }}
      >
        {teaser.banner}{" "}
        <Link href="/accuracy">
          See how accurate TIREKICK actually is, including the misses.
        </Link>
      </div>

      {teaser.containsSyntheticMedia && (
        <div
          className="panel prose-sm"
          style={{
            marginTop: "var(--s-3)",
            color: "var(--tk-locked)",
            borderColor: "var(--tk-locked)",
          }}
        >
          This is a demonstration built from synthetic media. Nothing here about
          condition describes a real vehicle.
        </div>
      )}

      <h1 style={{ fontSize: "var(--t-xl)", marginTop: "var(--s-6)" }}>
        {teaser.vehicleSummary}
      </h1>

      {/* ------------------------------------------------------------------ */}
      {/* coverage, before anything that looks like a conclusion             */}
      {/* ------------------------------------------------------------------ */}

      <section className="section">
        <div className="section-label">
          <span>What your media covered</span>
        </div>
        <CoverageBars teaser={teaser} />
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* limits, before the hook                                            */}
      {/* ------------------------------------------------------------------ */}

      <section className="section">
        <div className="section-label">
          <span>What this analysis could not assess</span>
        </div>
        <ul
          className="prose-sm"
          style={{
            margin: 0,
            paddingLeft: 0,
            listStyle: "none",
            display: "grid",
            gap: "var(--s-3)",
          }}
        >
          {teaser.couldNotAssess.map((line, i) => (
            <li
              key={i}
              style={{ borderLeft: "2px solid var(--tk-locked)", paddingLeft: "var(--s-3)" }}
            >
              {line}
            </li>
          ))}
        </ul>
        <p className="prose-sm dim" style={{ marginTop: "var(--s-4)" }}>
          This list is free and always will be. Paying does not shorten it.
        </p>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* the sample - one real finding, complete                            */}
      {/* ------------------------------------------------------------------ */}

      <section className="section">
        <div className="section-label">
          <span>One finding, in full, free</span>
        </div>
        {teaser.sample ? (
          <div
            className="panel panel-edge"
            style={{
              borderLeftColor: severityColor(teaser.sample.severity),
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(300px, 100%), 1fr))",
              gap: "var(--s-5)",
              alignItems: "start",
            }}
          >
            <EvidenceCrop
              src={assetUrl(teaser.inspectionId, teaser.sample.assetPath)}
              box={teaser.sample.box}
              color={severityColor(teaser.sample.severity)}
              caption={teaser.sample.caption}
              assetId={teaser.sample.assetId}
              sourceWidth={teaser.sample.assetWidth}
              sourceHeight={teaser.sample.assetHeight}
              synthetic={teaser.sample.assetSynthetic}
            />
            <div>
              <div style={{ display: "flex", gap: "var(--s-2)", alignItems: "center" }}>
                <span
                  className="chip chip-solid"
                  style={{ background: severityColor(teaser.sample.severity) }}
                >
                  {teaser.sample.severity}
                </span>
                <span className="label">{titleCase(teaser.sample.type)}</span>
                <span
                  className="data"
                  style={{
                    marginLeft: "auto",
                    color: severityColor(teaser.sample.severity),
                  }}
                >
                  {teaser.sample.confidence.toFixed(2)}
                </span>
              </div>

              <h2 style={{ fontSize: "var(--t-lg)", marginTop: "var(--s-3)" }}>
                {teaser.sample.title}
              </h2>
              <p className="prose-sm" style={{ marginTop: "var(--s-3)" }}>
                {teaser.sample.detail}
              </p>
              <p className="prose-sm dim" style={{ marginTop: "var(--s-3)" }}>
                <strong style={{ fontWeight: 600 }}>Why this confidence:</strong>{" "}
                {teaser.sample.confidenceBasis}
              </p>
              {/*
                Prose, not a label. This is a two-line sentence, and the label
                style - uppercase, 0.18em tracking - is for three-word section
                headings. Set in it, the one sentence that tells a buyer how
                much of the report they are not seeing was the hardest thing on
                the page to read.
              */}
              <p
                className="prose-sm"
                style={{
                  marginTop: "var(--s-4)",
                  paddingTop: "var(--s-3)",
                  borderTop: "1px solid var(--tk-rule)",
                  color: "var(--tk-paper)",
                }}
              >
                {teaser.sample.statement}
              </p>
            </div>
          </div>
        ) : (
          <div className="panel prose-sm muted">
            Nothing in this analysis cites a photograph, so there is no sample to
            show. That is itself the result: the media provided did not support a
            visual finding. The list above says what could not be assessed, and
            why.
          </div>
        )}
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* the count                                                          */}
      {/* ------------------------------------------------------------------ */}

      <section className="section">
        <div className="section-label">
          <span>What we found</span>
        </div>
        <div className="panel">
          <div className="split split-metric">
            <div>
              <div className="label">Red-flag score</div>
              <div
                className="data"
                style={{
                  fontSize: "var(--t-2xl)",
                  lineHeight: 1.1,
                  color: "var(--tk-sev-major)",
                }}
              >
                {teaser.redFlagScore}
                <span className="dim" style={{ fontSize: "var(--t-md)" }}>
                  /100
                </span>
              </div>
              <p className="prose-sm dim" style={{ margin: "var(--s-2) 0 0" }}>
                Severity and confidence of what was visible on this vehicle. Not a
                grade.
              </p>
            </div>
            <div style={{ minWidth: 0 }}>
              <p className="prose" style={{ margin: 0 }}>
                {teaser.headline}
              </p>
              <div
                style={{
                  display: "flex",
                  gap: "var(--s-2)",
                  flexWrap: "wrap",
                  marginTop: "var(--s-4)",
                }}
              >
                {teaser.counts.map((c) => (
                  <span
                    key={c.severity}
                    className="chip"
                    style={{ color: severityColor(c.severity) }}
                  >
                    {c.count} {c.severity}
                  </span>
                ))}
                <span className="chip" style={{ color: "var(--tk-locked)" }}>
                  {teaser.mechanicReferralCount} for your mechanic
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* systems, grouped                                                   */}
      {/* ------------------------------------------------------------------ */}

      <section className="section">
        <div className="section-label">
          <span>Systems</span>
        </div>
        {/*
          Grouped rather than tabulated. The teaser gives every non-locked row the
          same generic sentence by design - the specific one is the product - so a
          fourteen-row table printed "Something was found here. The full report
          says what, where, and how sure." nine times down a column. Nine copies of
          one sentence is not information, and it read as a paywall taunting the
          reader rather than as a summary.
        */}
        <div style={{ display: "grid", gap: "var(--s-4)" }}>
          {grouped.map((group) => (
            <div
              key={group.status}
              className="panel panel-edge"
              style={{ borderLeftColor: statusColor(group.status) }}
            >
              <div style={{ display: "flex", gap: "var(--s-3)", alignItems: "baseline" }}>
                <span className="chip" style={{ color: statusColor(group.status) }}>
                  {statusLabel(group.status)}
                </span>
                <span className="data dim">{group.systems.length}</span>
              </div>
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "var(--s-4)",
                  margin: "var(--s-3) 0",
                }}
              >
                {group.systems.map((s) => (
                  <span key={s} className="label" style={{ color: "var(--tk-paper)" }}>
                    {s}
                  </span>
                ))}
              </div>
              <p className="prose-sm muted" style={{ margin: 0 }}>
                {group.statement}
              </p>
            </div>
          ))}
        </div>
        <p className="prose-sm dim" style={{ marginTop: "var(--s-4)" }}>
          The rows marked {LOCKED_SYSTEM_STATEMENT.toLowerCase().replace(/\.$/, "")}{" "}
          are locked in software. TIREKICK will not report on them at any
          confidence, on any vehicle, ever &mdash; paid or not.
        </p>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* the offer, last                                                    */}
      {/* ------------------------------------------------------------------ */}

      <section className="section">
        <div className="section-label">
          <span>The full report</span>
        </div>
        <div className="panel panel-edge" style={{ borderLeftColor: "var(--tk-paper)" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: "var(--s-3)" }}>
            <span className="data" style={{ fontSize: "var(--t-2xl)" }}>
              ${teaser.priceUsd.toFixed(0)}
            </span>
            <span className="label">one report, no subscription</span>
          </div>

          <ul className="prose-sm" style={{ margin: "var(--s-5) 0 0", paddingLeft: "var(--s-5)" }}>
            {teaser.unlocks.map((line, i) => (
              <li key={i} style={{ marginBottom: "var(--s-2)" }}>
                {line}
              </li>
            ))}
          </ul>

          <div
            className="panel"
            style={{
              marginTop: "var(--s-5)",
              borderColor: "var(--tk-sev-major)",
              background: "transparent",
            }}
          >
            <div className="label" style={{ color: "var(--tk-sev-major)" }}>
              Before you pay, the accuracy position
            </div>
            <p className="prose-sm" style={{ margin: "var(--s-2) 0 0" }}>
              {teaser.accuracyStatement}{" "}
              <Link href="/accuracy">Read the accuracy page.</Link>
            </p>
          </div>

          <div style={{ marginTop: "var(--s-5)" }}>
            <Link href={`/buy/${teaser.inspectionId}`} className="btn btn-primary">
              Continue to the full report
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

/** Coverage with "missing" drawn as loudly as "arrived". */
function CoverageBars({ teaser }: { teaser: Teaser }) {
  const c = teaser.coverage;
  const received = new Set(c.receivedViews);
  return (
    <div className="panel">
      <div
        style={{
          display: "flex",
          gap: "var(--s-5)",
          flexWrap: "wrap",
          alignItems: "baseline",
        }}
      >
        <div>
          <div className="label">Media coverage</div>
          <div className="data" style={{ fontSize: "var(--t-2xl)", lineHeight: 1.1 }}>
            {(c.score * 100).toFixed(0)}
            <span className="dim" style={{ fontSize: "var(--t-md)" }}>
              %
            </span>
          </div>
        </div>
        <div style={{ flex: "1 1 320px", minWidth: 0 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(min(124px, 100%), 1fr))",
              gap: "var(--s-3)",
            }}
          >
            {c.requestedViews.map((v) => {
              const got = received.has(v);
              return (
                <span
                  key={v}
                  className="label"
                  style={{
                    color: got ? "var(--tk-paper)" : "var(--tk-unknown)",
                    borderBottom: `2px ${got ? "solid" : "dashed"} ${
                      got ? "var(--tk-paper)" : "var(--tk-unknown)"
                    }`,
                    paddingBottom: 3,
                    fontSize: "var(--t-2xs)",
                  }}
                >
                  {v.replace(/_/g, " ")}
                </span>
              );
            })}
          </div>
        </div>
      </div>
      <p className="prose-sm muted" style={{ margin: "var(--s-4) 0 0" }}>
        {c.statement}
      </p>
    </div>
  );
}

const STATUS_ORDER: SystemStatus[] = [
  "attention",
  "locked_mechanic_required",
  "cannot_determine",
  "no_issues_visible",
];

function groupSystems(teaser: Teaser) {
  const byStatus = new Map<SystemStatus, { systems: string[]; statement: string }>();
  for (const row of teaser.systems) {
    const entry = byStatus.get(row.status) ?? { systems: [], statement: row.statement };
    entry.systems.push(titleCase(row.system));
    byStatus.set(row.status, entry);
  }
  return STATUS_ORDER.filter((s) => byStatus.has(s)).map((status) => ({
    status,
    ...byStatus.get(status)!,
  }));
}
