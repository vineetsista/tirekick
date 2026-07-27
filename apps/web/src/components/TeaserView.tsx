import { LOCKED_SYSTEM_STATEMENT, type Teaser } from "@tirekick/shared";
import { severityColor, statusColor, statusLabel, titleCase } from "@/lib/report";

/**
 * The free result.
 *
 * Everything this renders was chosen server-side by `teaser.py`. There is
 * nothing hidden in this markup - no findings arrive and then get styled away -
 * because a paywall implemented in CSS is a paywall that lasts until someone
 * opens the network tab.
 *
 * The ordering is deliberate and it is not the conversion-optimal one. Coverage
 * comes first, then what we could not assess, and only then the score and the
 * offer. A buyer should be able to decide this is not worth $25 for their
 * six-photo listing before they ever see a price.
 */
export function TeaserView({ teaser }: { teaser: Teaser }) {
  return (
    <div className="wrap" style={{ paddingTop: 40, paddingBottom: 96 }}>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          flexWrap: "wrap",
          gap: 12,
          paddingBottom: 20,
          borderBottom: "1px solid var(--tk-line)",
        }}
      >
        <div style={{ fontSize: 22, letterSpacing: "0.22em", fontWeight: 700 }}>
          TIREKICK
        </div>
        <div className="mono-label">free result / {teaser.inspectionId}</div>
      </header>

      <div
        className="prose"
        style={{
          marginTop: 24,
          border: "1px solid var(--tk-locked)",
          borderLeftWidth: 4,
          background: "rgba(163,113,247,0.07)",
          padding: "16px 18px",
          fontSize: 14,
          lineHeight: 1.6,
        }}
      >
        {teaser.banner}{" "}
        <a href="/accuracy">See how accurate TIREKICK actually is, including the misses.</a>
      </div>

      {teaser.containsSyntheticMedia && (
        <div
          className="prose"
          style={{
            marginTop: 12,
            border: "1px solid var(--tk-locked)",
            padding: "12px 16px",
            fontSize: 13,
            color: "var(--tk-locked)",
          }}
        >
          This is a demonstration built from synthetic media. Nothing here about
          condition describes a real vehicle.
        </div>
      )}

      {teaser.vehicleSummary && (
        <div style={{ marginTop: 28, fontSize: 26 }}>{teaser.vehicleSummary}</div>
      )}

      {/* Coverage first. Before the score, before the price. */}
      <section className="section">
        <div className="section-label">What your media covered</div>
        <div className="panel">
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "baseline" }}>
            <div>
              <div className="mono-label">Media coverage</div>
              <div style={{ fontSize: 34, lineHeight: 1.2 }}>
                {(teaser.coverage.score * 100).toFixed(0)}
                <span className="muted" style={{ fontSize: 16 }}>
                  %
                </span>
              </div>
            </div>
            <div style={{ flex: "1 1 320px" }}>
              <div style={{ display: "flex", gap: 3, flexWrap: "wrap", marginBottom: 10 }}>
                {teaser.coverage.requestedViews.map((v) => {
                  const got = teaser.coverage.receivedViews.includes(v);
                  return (
                    <span
                      key={v}
                      title={titleCase(v)}
                      style={{
                        fontSize: 10,
                        letterSpacing: "0.1em",
                        padding: "3px 7px",
                        border: `1px solid ${got ? "var(--tk-accent)" : "var(--tk-line)"}`,
                        color: got ? "var(--tk-accent)" : "var(--tk-unknown)",
                        textTransform: "uppercase",
                      }}
                    >
                      {v.replace(/_/g, " ")}
                    </span>
                  );
                })}
              </div>
              <div className="prose muted" style={{ fontSize: 13 }}>
                {teaser.coverage.statement}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Never behind the paywall. */}
      <section className="section">
        <div className="section-label">What this analysis could not assess</div>
        <div className="panel">
          <ul className="prose" style={{ margin: 0, paddingLeft: 20, fontSize: 13 }}>
            {teaser.couldNotAssess.map((line, i) => (
              <li key={i} style={{ marginBottom: 8 }}>
                {line}
              </li>
            ))}
          </ul>
          <div
            className="prose muted"
            style={{
              fontSize: 12,
              marginTop: 16,
              paddingTop: 12,
              borderTop: "1px solid var(--tk-line)",
            }}
          >
            This list is free and always will be. Paying does not shorten it.
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section-label">What we found</div>
        <div className="panel">
          <div style={{ display: "flex", gap: 32, flexWrap: "wrap" }}>
            <div style={{ minWidth: 130 }}>
              <div className="mono-label">Red-flag score</div>
              <div style={{ fontSize: 46, lineHeight: 1.1, color: "var(--tk-sev-major)" }}>
                {teaser.redFlagScore}
                <span className="muted" style={{ fontSize: 18 }}>
                  /100
                </span>
              </div>
              <div className="muted" style={{ fontSize: 11, maxWidth: 180 }}>
                Severity and confidence of what was visible on this vehicle. Not a
                grade.
              </div>
            </div>
            <div style={{ flex: "1 1 340px" }}>
              <div style={{ fontSize: 18, marginBottom: 16 }}>{teaser.headline}</div>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                {teaser.counts.map((c) => (
                  <span
                    key={c.severity}
                    style={{
                      fontSize: 11,
                      letterSpacing: "0.1em",
                      border: `1px solid ${severityColor(c.severity)}`,
                      color: severityColor(c.severity),
                      padding: "4px 9px",
                      textTransform: "uppercase",
                    }}
                  >
                    {c.count} {c.severity}
                  </span>
                ))}
                {teaser.mechanicReferralCount > 0 && (
                  <span
                    style={{
                      fontSize: 11,
                      letterSpacing: "0.1em",
                      border: "1px solid var(--tk-locked)",
                      color: "var(--tk-locked)",
                      padding: "4px 9px",
                      textTransform: "uppercase",
                    }}
                  >
                    {teaser.mechanicReferralCount} for your mechanic
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section-label">Systems</div>
        <table>
          <thead>
            <tr>
              <th style={{ width: "22%" }}>System</th>
              <th style={{ width: "26%" }}>Status</th>
              <th>What that means</th>
            </tr>
          </thead>
          <tbody>
            {teaser.systems.map((row) => {
              const color = statusColor(row.status);
              const locked = row.status === "locked_mechanic_required";
              return (
                <tr key={row.system}>
                  <td style={{ textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    {row.system}
                  </td>
                  <td>
                    <span
                      style={{
                        fontSize: 10,
                        letterSpacing: "0.12em",
                        border: `1px solid ${color}`,
                        color,
                        padding: "2px 7px",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {statusLabel(row.status)}
                    </span>
                  </td>
                  <td
                    className="prose"
                    style={{ fontSize: 13, color: locked ? "var(--tk-locked)" : undefined }}
                  >
                    {row.statement}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="prose muted" style={{ fontSize: 12, marginTop: 14 }}>
          The four rows marked{" "}
          {LOCKED_SYSTEM_STATEMENT.toLowerCase().replace(/\.$/, "")} are locked in
          software. TIREKICK will not report on them at any confidence, on any
          vehicle, ever - paid or not.
        </div>
      </section>

      <section className="section">
        <div className="section-label">The full report</div>
        <div className="panel" style={{ borderLeft: "3px solid var(--tk-accent)" }}>
          <div style={{ display: "flex", gap: 28, flexWrap: "wrap", alignItems: "baseline" }}>
            <div style={{ fontSize: 38 }}>${teaser.priceUsd.toFixed(0)}</div>
            <div className="muted" style={{ fontSize: 13 }}>
              one report, no subscription
            </div>
          </div>

          <ul className="prose" style={{ margin: "18px 0 0", paddingLeft: 20, fontSize: 14 }}>
            {teaser.unlocks.map((line, i) => (
              <li key={i} style={{ marginBottom: 8 }}>
                {line}
              </li>
            ))}
          </ul>

          {/* LAW 6. The honest number, generated from the eval gate, before the
              button rather than after it. */}
          <div
            className="prose"
            style={{
              marginTop: 22,
              padding: "14px 16px",
              border: "1px solid var(--tk-sev-major)",
              fontSize: 13,
              lineHeight: 1.6,
            }}
          >
            <div
              className="mono-label"
              style={{ color: "var(--tk-sev-major)", marginBottom: 8 }}
            >
              Before you pay, the accuracy position
            </div>
            {teaser.accuracyStatement}{" "}
            <a href="/accuracy">Read the accuracy page.</a>
          </div>

          <a
            href={`/buy/${teaser.inspectionId}`}
            style={{
              display: "inline-block",
              marginTop: 22,
              padding: "13px 26px",
              border: "1px solid var(--tk-accent)",
              color: "var(--tk-accent)",
              fontSize: 14,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              textDecoration: "none",
            }}
          >
            Continue to the full report
          </a>
        </div>
      </section>
    </div>
  );
}
