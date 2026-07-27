import {
  LOCKED_SYSTEM_STATEMENT,
  SHARE_FOOTER,
  type Finding,
  type Report,
  type VehicleRecord,
} from "@tirekick/shared";
import { AudioTrackView } from "./AudioTrackView";
import { ConfidenceBar } from "./ConfidenceBar";
import { Overlay, annotationsFor } from "./Overlay";
import {
  assetUrl,
  severityColor,
  statusColor,
  statusLabel,
  titleCase,
} from "@/lib/report";

function Section({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section className="section">
      <div className="section-label">{label}</div>
      {children}
    </section>
  );
}

/** LAW 6 + LIABILITY section 4. Above the verdict, not dismissible, not 9px. */
function Banner({ text }: { text: string }) {
  return (
    <div
      className="prose"
      style={{
        border: "1px solid var(--tk-locked)",
        borderLeftWidth: 4,
        background: "rgba(163,113,247,0.07)",
        padding: "16px 18px",
        fontSize: 14,
        lineHeight: 1.6,
      }}
    >
      {text}{" "}
      <a href="/accuracy">See how accurate TIREKICK actually is, including the misses.</a>
    </div>
  );
}

/**
 * Coverage renders BEFORE the verdict. LIABILITY section 9 - a report built on
 * six photos of the good side must say so next to the conclusion, or the
 * conclusion reads as more than it is.
 */
function Coverage({ report }: { report: Report }) {
  const c = report.coverage;
  return (
    <div className="panel">
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "baseline" }}>
        <div>
          <div className="mono-label">Media coverage</div>
          <div style={{ fontSize: 34, lineHeight: 1.2 }}>
            {(c.score * 100).toFixed(0)}
            <span className="muted" style={{ fontSize: 16 }}>%</span>
          </div>
        </div>
        <div style={{ flex: "1 1 320px" }}>
          <div style={{ display: "flex", gap: 3, flexWrap: "wrap", marginBottom: 10 }}>
            {c.requestedViews.map((v) => {
              const got = c.receivedViews.includes(v);
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
            {c.statement}
          </div>
        </div>
      </div>
    </div>
  );
}

function Verdict({ report }: { report: Report }) {
  const v = report.verdict;
  return (
    <div className="panel">
      <div style={{ display: "flex", gap: 28, flexWrap: "wrap" }}>
        <div style={{ minWidth: 120 }}>
          <div className="mono-label">Red-flag score</div>
          <div style={{ fontSize: 46, lineHeight: 1.1, color: "var(--tk-sev-major)" }}>
            {v.redFlagScore}
            <span className="muted" style={{ fontSize: 18 }}>/100</span>
          </div>
          <div className="muted" style={{ fontSize: 11, maxWidth: 180 }}>
            Severity and confidence of what was visible. Not a grade, and not a
            statement about the vehicle overall.
          </div>
        </div>
        <div style={{ flex: "1 1 380px" }}>
          <div style={{ fontSize: 18, marginBottom: 12 }}>{v.headline}</div>
          <div className="prose muted" style={{ fontSize: 13 }}>
            {v.summary}
          </div>
        </div>
      </div>

      <div
        style={{
          marginTop: 24,
          paddingTop: 20,
          borderTop: "1px solid var(--tk-line)",
        }}
      >
        <div className="mono-label" style={{ color: "var(--tk-locked)" }}>
          What this analysis could not assess
        </div>
        <ul className="prose" style={{ margin: "12px 0 0", paddingLeft: 20, fontSize: 13 }}>
          {v.couldNotAssess.map((line, i) => (
            <li key={i} style={{ marginBottom: 6 }}>
              {line}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function FindingCard({ finding }: { finding: Finding }) {
  const color = severityColor(finding.severity);
  return (
    <div
      id={finding.id}
      className="panel"
      style={{ borderLeft: `3px solid ${color}`, scrollMarginTop: 24 }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 16,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <div>
          <span
            style={{
              fontSize: 10,
              letterSpacing: "0.14em",
              background: color,
              color: "#0a0c0e",
              padding: "2px 7px",
            }}
          >
            {finding.severity.toUpperCase()}
          </span>
          <span className="mono-label" style={{ marginLeft: 10 }}>
            {finding.type.replace(/_/g, " ")} / {finding.engine}
          </span>
        </div>
        <ConfidenceBar value={finding.confidence} color={color} />
      </div>

      <div style={{ fontSize: 16, margin: "14px 0 8px" }}>{finding.title}</div>
      <div className="prose" style={{ fontSize: 13, marginBottom: 14 }}>
        {finding.detail}
      </div>

      <div className="prose muted" style={{ fontSize: 12, marginBottom: 14 }}>
        <strong style={{ fontWeight: 500 }}>Why this confidence:</strong>{" "}
        {finding.confidenceBasis}
      </div>

      {/* LAW 1 - the evidence is rendered with the claim, never elsewhere. */}
      <div style={{ borderTop: "1px solid var(--tk-line)", paddingTop: 12 }}>
        <div className="mono-label">Evidence</div>
        <ul style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 12 }}>
          {finding.evidence.map((ev, i) => (
            <li key={i} className="muted" style={{ marginBottom: 4 }}>
              {ev.kind === "image_region" && (
                <>
                  <span style={{ color: "var(--tk-text)" }}>{ev.assetId}</span> - {ev.caption}{" "}
                  <span style={{ color: "var(--tk-unknown)" }}>
                    [{ev.box.x.toFixed(2)}, {ev.box.y.toFixed(2)}, {ev.box.w.toFixed(2)},{" "}
                    {ev.box.h.toFixed(2)}]
                  </span>
                </>
              )}
              {ev.kind === "audio_segment" && (
                <>
                  <span style={{ color: "var(--tk-text)" }}>{ev.assetId}</span> -{" "}
                  {ev.startSec.toFixed(1)}s to {ev.endSec.toFixed(1)}s - {ev.caption}
                </>
              )}
              {ev.kind === "data_record" && (
                <>
                  <span style={{ color: "var(--tk-text)" }}>{ev.source}</span> /{" "}
                  {ev.recordId} - {ev.caption}{" "}
                  <span style={{ color: "var(--tk-unknown)" }}>({ev.retrievedAt})</span>
                </>
              )}
              {ev.kind === "document_excerpt" && (
                <>
                  <span style={{ color: "var(--tk-text)" }}>{ev.assetId}</span> - &ldquo;
                  {ev.excerpt}&rdquo;
                </>
              )}
            </li>
          ))}
        </ul>
      </div>

      {(finding.estimatedCostUsd || finding.sellerQuestion || finding.mechanicCheck) && (
        <div
          style={{
            marginTop: 14,
            paddingTop: 12,
            borderTop: "1px solid var(--tk-line)",
            fontSize: 12,
          }}
          className="prose"
        >
          {finding.estimatedCostUsd && (
            <div style={{ marginBottom: 6 }}>
              <span className="mono-label">Est. repair</span>{" "}
              <span style={{ color }}>
                ${finding.estimatedCostUsd.low.toLocaleString()} - $
                {finding.estimatedCostUsd.high.toLocaleString()}
              </span>
            </div>
          )}
          {finding.sellerQuestion && (
            <div style={{ marginBottom: 6 }}>
              <span className="mono-label">Ask the seller</span> {finding.sellerQuestion}
            </div>
          )}
          {finding.mechanicCheck && (
            <div>
              <span className="mono-label">Ask a mechanic</span> {finding.mechanicCheck}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * The federal record, and - just as prominently - the edges of it.
 *
 * Recalls are the section of this report most likely to be misread. NHTSA
 * publishes campaigns per model and never per VIN, so a list under a masked VIN
 * reads as "open on this car" unless something says otherwise loudly. The scope
 * note is rendered above the counts, in the locked colour, for that reason.
 */
function VehicleRecordSection({ vehicle }: { vehicle: VehicleRecord }) {
  const d = vehicle.decoded;
  const fields: [string, string | number | null][] = [
    ["VIN", vehicle.vinMasked],
    ["Year", d.year],
    ["Make", d.make],
    ["Model", d.series ? `${d.model ?? ""} ${d.series}`.trim() : d.model],
    ["Trim", d.trim],
    ["Engine", d.engine],
    ["Drive", d.driveType],
    ["Body", d.bodyClass],
  ];

  return (
    <Section label="Vehicle record">
      <div className="panel">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
            gap: 16,
          }}
        >
          {fields.map(([label, value]) => (
            <div key={label}>
              <div className="mono-label">{label}</div>
              <div>{value === null || value === "" ? "-" : value}</div>
            </div>
          ))}
        </div>

        <div className="prose muted" style={{ fontSize: 12, marginTop: 16 }}>
          {vehicle.vinStatement}
        </div>

        {vehicle.decodeError && (
          <div
            className="prose"
            style={{
              marginTop: 12,
              fontSize: 13,
              color: "var(--tk-sev-major)",
              border: "1px solid var(--tk-sev-major)",
              padding: "10px 14px",
            }}
          >
            {vehicle.decodeError}
          </div>
        )}

        {/* The caveat leads the recall count, never trails it. */}
        <div
          style={{
            marginTop: 20,
            paddingTop: 16,
            borderTop: "1px solid var(--tk-line)",
          }}
        >
          <div className="mono-label" style={{ color: "var(--tk-locked)" }}>
            Recalls - what this list is
          </div>
          <div
            className="prose"
            style={{ fontSize: 13, marginTop: 8, color: "var(--tk-locked)" }}
          >
            {vehicle.recallScope}
          </div>
        </div>

        {vehicle.complaintSummary && (
          <div style={{ marginTop: 20 }}>
            <div className="mono-label">Owner complaints for this model</div>
            <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginTop: 10 }}>
              <div>
                <div style={{ fontSize: 26 }}>
                  {vehicle.complaintSummary.total.toLocaleString()}
                </div>
                <div className="muted" style={{ fontSize: 11 }}>
                  complaints filed
                </div>
              </div>
              <div style={{ flex: "1 1 320px" }}>
                <table style={{ marginTop: 0 }}>
                  <tbody>
                    {vehicle.complaintSummary.topComponents.map((c) => (
                      <tr key={c.component}>
                        <td style={{ fontSize: 12 }}>{c.component}</td>
                        <td
                          className="muted"
                          style={{ fontSize: 12, textAlign: "right", width: 70 }}
                        >
                          {c.count.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="prose muted" style={{ fontSize: 12, marginTop: 12 }}>
              {vehicle.complaintSummary.scope}
            </div>
          </div>
        )}

        {/* LAW 1 - every lookup behind this section, with when and from where. */}
        {vehicle.sources.length > 0 && (
          <div
            style={{
              marginTop: 20,
              paddingTop: 16,
              borderTop: "1px solid var(--tk-line)",
            }}
          >
            <div className="mono-label">Sources</div>
            <ul style={{ margin: "10px 0 0", paddingLeft: 18, fontSize: 12 }}>
              {vehicle.sources.map((s) => (
                <li key={s.url + s.retrievedAt} className="muted" style={{ marginBottom: 8 }}>
                  <span style={{ color: "var(--tk-text)" }}>{s.source}</span>{" "}
                  <span style={{ color: "var(--tk-unknown)" }}>
                    (retrieved {s.retrievedAt})
                  </span>
                  <div style={{ marginTop: 2 }}>{s.statement}</div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Section>
  );
}

export function ReportView({ report }: { report: Report }) {
  const photos = report.assets.filter((a) => a.kind === "photo");

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
        <div className="mono-label">
          {report.reportId} / {report.generatedAt} / mode: {report.mode}
        </div>
      </header>

      <div style={{ marginTop: 24 }}>
        <Banner text={report.banner} />
      </div>

      {report.containsSyntheticMedia && (
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
          This report was generated from synthetic fixture media. The images are
          drawings, not photographs, and no statement here about condition
          describes a real vehicle. The federal records below are real: the VIN
          carries genuine manufacturer codes with an invented serial, so it
          decodes to a real model and identifies nobody&rsquo;s car.
        </div>
      )}

      {/* Coverage before conclusions. */}
      <Section label="Coverage">
        <Coverage report={report} />
      </Section>

      <Section label="Verdict">
        <Verdict report={report} />
      </Section>

      <Section label="Evidence gallery">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
            gap: 20,
          }}
        >
          {photos.map((asset) => {
            const annotations = annotationsFor(
              asset.id,
              report.findings,
              report.mechanicReferrals,
            );
            return (
              <div key={asset.id}>
                <Overlay
                  src={assetUrl(report.inspectionId, asset.path)}
                  alt={`${asset.viewClass ?? "unclassified"} - ${asset.id}`}
                  annotations={annotations}
                  synthetic={asset.synthetic}
                />
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 10,
                    marginTop: 8,
                    fontSize: 11,
                  }}
                >
                  <span className="mono-label">
                    {asset.id} / {asset.viewClass ?? "unknown"}
                  </span>
                  <span className="muted">
                    {annotations.length === 0
                      ? "nothing flagged on this image"
                      : `${annotations.length} region${annotations.length > 1 ? "s" : ""} flagged`}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      <Section label={`Findings (${report.findings.length})`}>
        <div style={{ display: "grid", gap: 16 }}>
          {report.findings.map((f) => (
            <FindingCard key={f.id} finding={f} />
          ))}
        </div>
      </Section>

      <Section label="Systems">
        <table>
          <thead>
            <tr>
              <th style={{ width: "18%" }}>System</th>
              <th style={{ width: "22%" }}>Status</th>
              <th>Statement</th>
            </tr>
          </thead>
          <tbody>
            {report.systems.map((row) => {
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
                    {row.confidence !== null && (
                      <span style={{ marginLeft: 12, display: "inline-block" }}>
                        <ConfidenceBar value={row.confidence} color={color} label="MAX" />
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="prose muted" style={{ fontSize: 12, marginTop: 14 }}>
          The four rows marked {LOCKED_SYSTEM_STATEMENT.toLowerCase().replace(/\.$/, "")}{" "}
          are locked in software. TIREKICK will not report on them at any confidence,
          on any vehicle, ever.
        </div>
      </Section>

      {report.mechanicReferrals.length > 0 && (
        <Section label="For your mechanic">
          <div style={{ display: "grid", gap: 12 }}>
            {report.mechanicReferrals.map((r) => (
              <div
                key={r.id}
                id={r.id}
                className="panel"
                style={{ borderLeft: "3px solid var(--tk-locked)", scrollMarginTop: 24 }}
              >
                <div className="mono-label" style={{ color: "var(--tk-locked)" }}>
                  {r.system}
                </div>
                <div style={{ margin: "8px 0 10px", fontSize: 15 }}>{r.observation}</div>
                <div className="prose muted" style={{ fontSize: 13 }}>
                  {r.ask}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {report.audio && (
        <Section label="Engine audio">
          <AudioTrackView track={report.audio} inspectionId={report.inspectionId} />
        </Section>
      )}

      {report.vehicle && <VehicleRecordSection vehicle={report.vehicle} />}

      {report.price && (
        <Section label="Price check">
          <div className="panel">
            <div style={{ display: "flex", gap: 32, flexWrap: "wrap", alignItems: "baseline" }}>
              <div>
                <div className="mono-label">Asking</div>
                <div style={{ fontSize: 30 }}>
                  ${report.price.askingPriceUsd.toLocaleString()}
                </div>
              </div>
              <div>
                <div className="mono-label">Supported by these comps</div>
                <div style={{ fontSize: 30, color: "var(--tk-accent)" }}>
                  ${Math.round(report.price.fairRangeUsd.low).toLocaleString()} - $
                  {Math.round(report.price.fairRangeUsd.high).toLocaleString()}
                </div>
              </div>
            </div>
            <div className="prose" style={{ fontSize: 14, marginTop: 16 }}>
              {report.price.verdictStatement}
            </div>

            <div style={{ marginTop: 20 }}>
              <div className="mono-label">The comps behind this range</div>
              <table style={{ marginTop: 8 }}>
                <thead>
                  <tr>
                    <th>Listing</th>
                    <th>Year / trim</th>
                    <th>Mileage</th>
                    <th>Asking</th>
                  </tr>
                </thead>
                <tbody>
                  {report.price.comps.map((c) => (
                    <tr key={c.id}>
                      <td className="muted" style={{ fontSize: 12 }}>
                        {c.sourceNote}
                      </td>
                      <td>
                        {c.year} {c.trim ?? ""}
                      </td>
                      <td>{c.mileage.toLocaleString()}</td>
                      <td>${c.askingPriceUsd.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {report.price.deductions.length > 0 && (
              <div style={{ marginTop: 20 }}>
                <div className="mono-label">Deductions, each linked to a finding</div>
                <table style={{ marginTop: 8 }}>
                  <tbody>
                    {report.price.deductions.map((d) => (
                      <tr key={d.findingId}>
                        <td>
                          <a href={`#${d.findingId}`}>{d.label}</a>
                        </td>
                        <td style={{ color: "var(--tk-sev-major)", whiteSpace: "nowrap" }}>
                          -${d.lowUsd.toLocaleString()} to -${d.highUsd.toLocaleString()}
                        </td>
                        <td className="muted prose" style={{ fontSize: 12 }}>
                          {d.basis}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="prose muted" style={{ fontSize: 12, marginTop: 18 }}>
              {report.price.normalizationNotes}
            </div>
          </div>
        </Section>
      )}

      <Section label="Questions for the seller">
        <ol className="prose" style={{ paddingLeft: 22, fontSize: 14 }}>
          {report.sellerQuestions.map((q, i) => (
            <li key={i} style={{ marginBottom: 8 }}>
              {q}
            </li>
          ))}
        </ol>
      </Section>

      <Section label="Negotiation script">
        <div style={{ display: "grid", gap: 12 }}>
          {report.negotiationScript.map((beat, i) => (
            <div key={i} className="panel">
              <div className="mono-label">{beat.beat}</div>
              <div className="prose" style={{ marginTop: 8, fontSize: 14 }}>
                &ldquo;{beat.say}&rdquo;
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* LAW 5. Internal-facing in P0; see DECISIONS.md D-012. */}
      <Section label="Run metadata">
        <table>
          <tbody>
            <tr>
              <td className="mono-label">Mode</td>
              <td>{report.cost.mode}</td>
            </tr>
            <tr>
              <td className="mono-label">Images analyzed</td>
              <td>{report.cost.imagesAnalyzed}</td>
            </tr>
            <tr>
              <td className="mono-label">Tokens</td>
              <td>
                {report.cost.inputTokens.toLocaleString()} in /{" "}
                {report.cost.outputTokens.toLocaleString()} out
              </td>
            </tr>
            <tr>
              <td className="mono-label">Audio processed</td>
              <td>{report.cost.audioSecondsProcessed.toFixed(1)}s</td>
            </tr>
            <tr>
              <td className="mono-label">Cost to produce</td>
              <td style={{ color: "var(--tk-accent)" }}>
                ${report.cost.usdTotal.toFixed(4)}
              </td>
            </tr>
            <tr>
              <td className="mono-label">Note</td>
              <td className="prose muted" style={{ fontSize: 12 }}>
                {report.cost.note}
              </td>
            </tr>
          </tbody>
        </table>
      </Section>

      <footer
        style={{
          marginTop: 72,
          paddingTop: 20,
          borderTop: "1px solid var(--tk-line)",
          display: "flex",
          justifyContent: "space-between",
          gap: 16,
          flexWrap: "wrap",
          fontSize: 11,
        }}
      >
        <span className="mono-label">{SHARE_FOOTER}</span>
        <span className="muted prose" style={{ maxWidth: 620 }}>
          Automated analysis of buyer-supplied media. Not an inspection. Have an
          independent mechanic examine any vehicle before you buy it.{" "}
          <a href="/accuracy">Accuracy and known limits</a>.
        </span>
      </footer>
    </div>
  );
}
