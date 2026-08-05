import {
  LOCKED_SYSTEM_STATEMENT,
  SHARE_FOOTER,
  type PriceCheck,
  type Report,
  type VehicleRecord,
  type WalkaroundTrack,
} from "@tirekick/shared";
import { AudioTrackView } from "./AudioTrackView";
import { ConfidenceBar } from "./ConfidenceBar";
import { CoverageMap } from "./CoverageMap";
import { FindingCard } from "./FindingCard";
import { Overlay, annotationsFor } from "./Overlay";
import { ReportNav } from "./ReportNav";
import {
  assetById,
  assetUrl,
  bySeverity,
  partitionFindings,
  statusColor,
  statusLabel,
} from "@/lib/report";

function Section({
  id,
  label,
  note,
  children,
}: {
  id: string;
  label: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="section" id={id}>
      <div className="section-label">
        <span>{label}</span>
        {note && (
          <span className="dim" style={{ letterSpacing: "0.04em", textTransform: "none" }}>
            {note}
          </span>
        )}
      </div>
      {children}
    </section>
  );
}

/** LAW 6 + LIABILITY section 4. Above the verdict, not dismissible, not 9px. */
function Banner({ text }: { text: string }) {
  return (
    <div
      className="panel panel-edge prose-sm"
      style={{ borderLeftColor: "var(--tk-locked)" }}
    >
      {text} <a href="/accuracy">See how accurate TIREKICK actually is, including the misses.</a>
    </div>
  );
}

function Verdict({ report }: { report: Report }) {
  const v = report.verdict;
  return (
    <div className="panel">
      <div className="split split-metric" style={{ gap: "var(--s-6)" }}>
        <div>
          <div className="label">Red-flag score</div>
          <div
            className="data"
            style={{
              fontSize: "var(--t-3xl)",
              lineHeight: 1,
              color: "var(--tk-sev-major)",
            }}
          >
            {v.redFlagScore}
            <span className="dim" style={{ fontSize: "var(--t-lg)" }}>
              /100
            </span>
          </div>
          <p className="prose-sm dim" style={{ margin: "var(--s-3) 0 0" }}>
            Severity and confidence of what was visible. Not a grade, and not a
            statement about the vehicle overall.
          </p>
        </div>
        <div style={{ minWidth: 0 }}>
          <p className="prose" style={{ margin: 0, fontSize: "var(--t-lg)" }}>
            {v.headline}
          </p>
          <p className="prose-sm muted" style={{ marginTop: "var(--s-4)" }}>
            {v.summary}
          </p>
        </div>
      </div>

      <div
        style={{
          marginTop: "var(--s-5)",
          paddingTop: "var(--s-5)",
          borderTop: "1px solid var(--tk-rule)",
        }}
      >
        <div className="label" style={{ color: "var(--tk-locked)" }}>
          What this analysis could not assess
        </div>
        <ul
          className="prose-sm"
          style={{
            margin: "var(--s-3) 0 0",
            paddingLeft: 0,
            listStyle: "none",
            display: "grid",
            gap: "var(--s-3)",
          }}
        >
          {v.couldNotAssess.map((line, i) => (
            <li
              key={i}
              style={{ borderLeft: "2px solid var(--tk-locked)", paddingLeft: "var(--s-3)" }}
            >
              {line}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/**
 * The walkaround, which the schema has carried since P7 and nothing rendered.
 *
 * `report.walkaround` reached the JSON with all of it - 28 frames sampled, 5
 * analysed, 4 dropped blurred, 4 dropped duplicate - and the viewer dropped the
 * lot on the floor. The only trace was one sentence buried in the
 * `couldNotAssess` list. A buyer who uploaded a video had no way to find out what
 * happened to it.
 *
 * The discards are the interesting half. "5 frames analysed" without "23
 * discarded" invites the reader to assume the whole video was examined.
 */
function Walkaround({ track }: { track: WalkaroundTrack }) {
  const rows: [string, number | string][] = [
    ["Video length", `${track.durationSec.toFixed(1)}s`],
    ["Frames sampled", track.framesSampled],
    ["Frames analysed", track.framesAnalysed],
    ["Dropped - too blurred", track.droppedBlurred],
    ["Dropped - duplicate view", track.droppedDuplicate],
    ["Dropped - over the cap", track.droppedOverCap],
  ];
  return (
    <div className="panel">
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(min(130px, 100%), 1fr))",
          gap: "var(--s-4)",
        }}
      >
        {rows.map(([label, value]) => (
          <div key={label}>
            <div className="label">{label}</div>
            <div className="data" style={{ fontSize: "var(--t-lg)" }}>
              {value}
            </div>
          </div>
        ))}
      </div>
      <p className="prose-sm muted" style={{ marginTop: "var(--s-5)" }}>
        {track.statement}
      </p>
      {track.frameTimesSec.length > 0 && (
        <p className="prose-sm dim" style={{ marginTop: "var(--s-3)" }}>
          Frames kept from{" "}
          <span className="data">
            {track.frameTimesSec.map((t) => `${t.toFixed(1)}s`).join(", ")}
          </span>
          . Each was then classified and analysed exactly as an uploaded
          photograph would have been.
        </p>
      )}
    </div>
  );
}

function PriceSection({ price }: { price: PriceCheck }) {
  /*
   * The fair range used to render in the brand accent, which was green, on every
   * report regardless of the verdict. On this fixture the verdict is
   * `above_range` - the seller is asking more than the comparables support - and
   * the number was coloured as though that were good news.
   *
   * Colour follows the verdict now, and `in_range` is deliberately uncoloured.
   * A price the comps support is not a win, it is the absence of a problem, and
   * this interface does not congratulate anyone.
   */
  const verdictColor: Record<string, string> = {
    above_range: "var(--tk-sev-major)",
    below_range: "var(--tk-sev-info)",
    in_range: "var(--tk-paper)",
    cannot_determine: "var(--tk-unknown)",
  };
  const color = verdictColor[price.verdict] ?? "var(--tk-paper)";

  return (
    <div className="panel">
      <div style={{ display: "flex", gap: "var(--s-7)", flexWrap: "wrap" }}>
        <div>
          <div className="label">Asking</div>
          <div className="data" style={{ fontSize: "var(--t-xl)" }}>
            ${price.askingPriceUsd.toLocaleString()}
          </div>
        </div>
        <div>
          <div className="label">Supported by these comps</div>
          <div className="data" style={{ fontSize: "var(--t-xl)" }}>
            ${Math.round(price.fairRangeUsd.low).toLocaleString()}&ndash;$
            {Math.round(price.fairRangeUsd.high).toLocaleString()}
          </div>
        </div>
        <div>
          <div className="label">Verdict</div>
          <span className="chip" style={{ color, fontSize: "var(--t-xs)" }}>
            {price.verdict.replace(/_/g, " ")}
          </span>
        </div>
      </div>

      <p className="prose" style={{ marginTop: "var(--s-5)" }}>
        {price.verdictStatement}
      </p>

      <div style={{ marginTop: "var(--s-6)" }}>
        <div className="label">The comps behind this range</div>
        <div className="table-scroll">
          <table style={{ marginTop: "var(--s-2)" }}>
            <thead>
              <tr>
                <th>Listing</th>
                <th>Year / trim</th>
                <th>Mileage</th>
                <th>Asking</th>
              </tr>
            </thead>
            <tbody>
              {price.comps.map((c) => (
                <tr key={c.id}>
                  <td>
                    <div className="prose-sm dim">{c.sourceNote}</div>
                  </td>
                  <td>
                    {c.year} {c.trim ?? ""}
                  </td>
                  <td className="data">{c.mileage.toLocaleString()}</td>
                  <td className="data">${c.askingPriceUsd.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {price.excluded.length > 0 && (
        <div style={{ marginTop: "var(--s-6)" }}>
          <div className="label" style={{ color: "var(--tk-unknown)" }}>
            Listings you gave us that were left out, and why
          </div>
          <div className="table-scroll">
            <table style={{ marginTop: "var(--s-2)" }}>
              <tbody>
                {price.excluded.map((e) => (
                  <tr key={e.compId}>
                    <td className="data" style={{ whiteSpace: "nowrap" }}>
                      {e.compId}
                    </td>
                    <td>
                      <div className="prose-sm dim">{e.reason}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {price.deductions.length > 0 && (
        <div style={{ marginTop: "var(--s-6)" }}>
          <div className="label">Deductions, each linked to a finding</div>
          <div className="table-scroll">
            <table style={{ marginTop: "var(--s-2)" }}>
              <tbody>
                {price.deductions.map((d) => (
                  <tr key={d.findingId}>
                    <td>
                      <a href={`#${d.findingId}`}>{d.label}</a>
                    </td>
                    <td
                      className="data"
                      style={{ color: "var(--tk-sev-major)", whiteSpace: "nowrap" }}
                    >
                      &minus;${d.lowUsd.toLocaleString()} to &minus;$
                      {d.highUsd.toLocaleString()}
                    </td>
                    <td>
                      <div className="prose-sm dim">{d.basis}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="prose-sm dim" style={{ marginTop: "var(--s-5)" }}>
        {price.normalizationNotes}
      </p>
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
    <div className="panel">
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(min(140px, 100%), 1fr))",
          gap: "var(--s-4)",
        }}
      >
        {fields.map(([label, value]) => (
          <div key={label}>
            <div className="label">{label}</div>
            <div className="data">{value === null || value === "" ? "—" : value}</div>
          </div>
        ))}
      </div>

      <p className="prose-sm dim" style={{ marginTop: "var(--s-5)" }}>
        {vehicle.vinStatement}
      </p>

      {vehicle.decodeError && (
        <div
          className="panel prose-sm"
          style={{
            marginTop: "var(--s-3)",
            color: "var(--tk-sev-major)",
            borderColor: "var(--tk-sev-major)",
            background: "transparent",
          }}
        >
          {vehicle.decodeError}
        </div>
      )}

      {/* The caveat leads the recall count, never trails it. */}
      <div
        style={{
          marginTop: "var(--s-5)",
          paddingTop: "var(--s-4)",
          borderTop: "1px solid var(--tk-rule)",
        }}
      >
        <div className="label" style={{ color: "var(--tk-locked)" }}>
          Recalls &mdash; what this list is
        </div>
        <p className="prose-sm" style={{ marginTop: "var(--s-2)", color: "var(--tk-locked)" }}>
          {vehicle.recallScope}
        </p>
      </div>

      {vehicle.complaintSummary && (
        <div style={{ marginTop: "var(--s-5)" }}>
          <div className="label">Owner complaints for this model</div>
          <div
            style={{
              display: "flex",
              gap: "var(--s-6)",
              flexWrap: "wrap",
              marginTop: "var(--s-3)",
            }}
          >
            <div>
              <div className="data" style={{ fontSize: "var(--t-xl)" }}>
                {vehicle.complaintSummary.total.toLocaleString()}
              </div>
              <div className="label">complaints filed</div>
            </div>
            <div style={{ flex: "1 1 320px", minWidth: 0 }}>
              <ComplaintBars components={vehicle.complaintSummary.topComponents} />
            </div>
          </div>
          <p className="prose-sm dim" style={{ marginTop: "var(--s-4)" }}>
            {vehicle.complaintSummary.scope}
          </p>
        </div>
      )}

      {/* LAW 1 - every lookup behind this section, with when and from where. */}
      {vehicle.sources.length > 0 && (
        <div
          style={{
            marginTop: "var(--s-5)",
            paddingTop: "var(--s-4)",
            borderTop: "1px solid var(--tk-rule)",
          }}
        >
          <div className="label">Sources</div>
          <ul style={{ margin: "var(--s-3) 0 0", paddingLeft: "var(--s-5)" }}>
            {vehicle.sources.map((s) => (
              <li key={s.url + s.retrievedAt} className="prose-sm dim" style={{ marginBottom: "var(--s-2)" }}>
                <span style={{ color: "var(--tk-paper)" }}>{s.source}</span>{" "}
                <span className="data" style={{ color: "var(--tk-pencil)" }}>
                  (retrieved {s.retrievedAt})
                </span>
                <div>{s.statement}</div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** Complaint counts as bars. A column of numbers hides the shape of the data. */
function ComplaintBars({
  components,
}: {
  components: { component: string; count: number }[];
}) {
  const max = Math.max(1, ...components.map((c) => c.count));
  return (
    <div style={{ display: "grid", gap: "var(--s-2)" }}>
      {components.map((c) => (
        <div key={c.component} style={{ display: "grid", gap: 3 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: "var(--s-3)",
              fontSize: "var(--t-sm)",
            }}
          >
            <span>{c.component}</span>
            <span className="data dim">{c.count.toLocaleString()}</span>
          </div>
          <div style={{ height: 4, background: "var(--tk-rule)" }}>
            <div
              style={{
                width: `${(c.count / max) * 100}%`,
                height: "100%",
                background: "var(--tk-graphite)",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ReportView({ report }: { report: Report }) {
  const photos = report.assets.filter((a) => a.kind === "photo");
  const assets = new Map(report.assets.map((a) => [a.id, a]));
  const { vehicle: vehicleFindings, model: modelFindings } = partitionFindings(
    report.findings,
  );
  const frameIds = new Set(report.walkaround?.frameAssetIds ?? []);

  const sections = [
    { id: "coverage", label: "Coverage" },
    { id: "verdict", label: "Verdict" },
    { id: "findings", label: "Findings", count: vehicleFindings.length },
    ...(modelFindings.length ? [{ id: "recalls", label: "Recalls", count: modelFindings.length }] : []),
    ...(report.mechanicReferrals.length
      ? [{ id: "mechanic", label: "For your mechanic", count: report.mechanicReferrals.length }]
      : []),
    { id: "gallery", label: "Media", count: photos.length },
    { id: "systems", label: "Systems" },
    ...(report.audio ? [{ id: "audio", label: "Audio" }] : []),
    ...(report.vehicle ? [{ id: "record", label: "Vehicle record" }] : []),
    ...(report.price ? [{ id: "price", label: "Price" }] : []),
    ...(report.sellerQuestions.length
      ? [{ id: "questions", label: "Questions", count: report.sellerQuestions.length }]
      : []),
    ...(report.negotiationScript.length ? [{ id: "script", label: "Script" }] : []),
  ];

  return (
    <>
      <ReportNav sections={sections} />

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
          <h1 style={{ fontSize: "var(--t-xl)" }}>
            {report.vehicle
              ? [report.vehicle.decoded.year, report.vehicle.decoded.make, report.vehicle.decoded.model]
                  .filter(Boolean)
                  .join(" ")
              : "Inspection report"}
          </h1>
          <span className="label data">
            {report.reportId} / {report.generatedAt} / mode: {report.mode}
          </span>
        </header>

        <div style={{ marginTop: "var(--s-5)" }}>
          <Banner text={report.banner} />
        </div>

        {report.containsSyntheticMedia && (
          <div
            className="panel prose-sm"
            style={{
              marginTop: "var(--s-3)",
              borderColor: "var(--tk-locked)",
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

        {/* Coverage before conclusions. LIABILITY section 9. */}
        <Section id="coverage" label="What was looked at">
          <CoverageMap report={report} />
        </Section>

        <Section id="verdict" label="Verdict">
          <Verdict report={report} />
        </Section>

        {/* ---------------------------------------------------------------- */}
        {/* findings about THIS CAR                                          */}
        {/* ---------------------------------------------------------------- */}

        <Section
          id="findings"
          label={`Findings about this vehicle (${vehicleFindings.length})`}
          note="worst first"
        >
          {vehicleFindings.length > 0 ? (
            <div style={{ display: "grid", gap: "var(--s-4)" }}>
              {bySeverity(vehicleFindings).map((f) => (
                <FindingCard
                  key={f.id}
                  finding={f}
                  assets={assets}
                  inspectionId={report.inspectionId}
                />
              ))}
            </div>
          ) : (
            <div className="panel prose-sm muted">
              Nothing adverse was visible in the media provided. That is a
              statement about the photographs and not a clearance &mdash; read the
              coverage map above for what was never looked at.
            </div>
          )}
        </Section>

        {/* ---------------------------------------------------------------- */}
        {/* records about the MODEL, kept apart                              */}
        {/* ---------------------------------------------------------------- */}

        {modelFindings.length > 0 && (
          <Section
            id="recalls"
            label={`On record for this model (${modelFindings.length})`}
            note="not about this specific car"
          >
            {/*
              These used to sit in one undifferentiated list with the findings
              above, five recall campaigns wearing the same MAJOR badge as the
              corrosion on the rocker panel. A buyer scrolling that saw seven
              serious problems with the car in front of them. There are two.

              The verdict paragraph already says so - "Separately, 5 recall
              campaign(s) are on record for this model year - free to fix" - and
              the scoring engine already excludes them from the red-flag score for
              exactly this reason (D-021). The layout was the only part of the
              system still conflating them.
            */}
            <div
              className="panel panel-edge prose-sm"
              style={{ borderLeftColor: "var(--tk-locked)", marginBottom: "var(--s-4)" }}
            >
              These describe the model and year, not the car you are looking at.
              They are not counted in the red-flag score. Recall work is free at a
              dealer, and a dealer will tell you by VIN whether it was done on this
              specific vehicle &mdash; which is something no public database
              publishes and this report cannot know.
            </div>
            <div style={{ display: "grid", gap: "var(--s-4)" }}>
              {bySeverity(modelFindings).map((f) => (
                <FindingCard
                  key={f.id}
                  finding={f}
                  assets={assets}
                  inspectionId={report.inspectionId}
                />
              ))}
            </div>
          </Section>
        )}

        {report.mechanicReferrals.length > 0 && (
          <Section
            id="mechanic"
            label={`For your mechanic (${report.mechanicReferrals.length})`}
            note="locked systems - observation only, no severity, no confidence"
          >
            <div style={{ display: "grid", gap: "var(--s-3)" }}>
              {report.mechanicReferrals.map((r) => (
                <div
                  key={r.id}
                  id={r.id}
                  className="panel panel-edge"
                  style={{ borderLeftColor: "var(--tk-locked)" }}
                >
                  <div className="label" style={{ color: "var(--tk-locked)" }}>
                    {r.system}
                  </div>
                  <p className="prose" style={{ margin: "var(--s-2) 0 var(--s-3)" }}>
                    {r.observation}
                  </p>
                  <p className="prose-sm muted" style={{ margin: 0 }}>
                    {r.ask}
                  </p>
                </div>
              ))}
            </div>
          </Section>
        )}

        {report.walkaround && (
          <Section id="walkaround" label="Walkaround video" note="what was kept, and what was thrown away">
            <Walkaround track={report.walkaround} />
          </Section>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* every frame, with anchors the findings link back to              */}
        {/* ---------------------------------------------------------------- */}

        <Section
          id="gallery"
          label={`All media (${photos.length})`}
          note="every image, whether anything was found on it or not"
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(300px, 100%), 1fr))",
              gap: "var(--s-5)",
            }}
          >
            {photos.map((asset) => {
              const annotations = annotationsFor(
                asset.id,
                report.findings,
                report.mechanicReferrals,
              );
              const fromVideo = frameIds.has(asset.id);
              return (
                <div key={asset.id} id={`asset-${asset.id}`} className="section">
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
                      gap: "var(--s-3)",
                      marginTop: "var(--s-2)",
                      fontSize: "var(--t-xs)",
                    }}
                  >
                    <span className="label">
                      <span className="data">{asset.id}</span>
                      {fromVideo && (
                        <span className="dim" style={{ marginLeft: 6 }}>
                          from video
                        </span>
                      )}
                    </span>
                    <span className="dim">
                      {asset.viewClass === null || asset.viewClass === "unknown"
                        ? "view not identified"
                        : annotations.length === 0
                          ? "nothing flagged here"
                          : `${annotations.length} region${annotations.length > 1 ? "s" : ""} flagged`}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </Section>

        <Section id="systems" label="Systems">
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th style={{ width: "16%" }}>System</th>
                  <th style={{ width: "20%" }}>Status</th>
                  <th>Statement</th>
                </tr>
              </thead>
              <tbody>
                {report.systems.map((row) => {
                  const color = statusColor(row.status);
                  const locked = row.status === "locked_mechanic_required";
                  return (
                    <tr key={row.system}>
                      <td className="label" style={{ color: "var(--tk-paper)" }}>
                        {row.system}
                      </td>
                      <td>
                        <span className="chip" style={{ color }}>
                          {statusLabel(row.status)}
                        </span>
                      </td>
                      <td style={{ color: locked ? "var(--tk-locked)" : undefined }}>
                        {/*
                          The measure lives on this div, not on the <td>. A
                          max-width on a table cell is a hint the auto table
                          algorithm is free to ignore, and it did: this column
                          set the longest sentences in the report at 102
                          characters a line while claiming to be capped at 64.
                        */}
                        <div className="prose-sm">
                          {row.statement}
                          {row.confidence !== null && (
                            <span style={{ marginLeft: "var(--s-3)", display: "inline-block" }}>
                              <ConfidenceBar value={row.confidence} color={color} label="MAX" />
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="prose-sm dim" style={{ marginTop: "var(--s-4)" }}>
            The four rows marked{" "}
            {LOCKED_SYSTEM_STATEMENT.toLowerCase().replace(/\.$/, "")} are locked in
            software. TIREKICK will not report on them at any confidence, on any
            vehicle, ever.
          </p>
        </Section>

        {report.audio && (
          <Section id="audio" label="Engine audio">
            <AudioTrackView
              track={report.audio}
              inspectionId={report.inspectionId}
              // The clip's real filename, from the asset row the track cites.
              // Deriving it as `${assetId}.wav` worked for the fixture by
              // coincidence of naming; the media route serves what the report
              // cites, so the citation is the only safe source of the path.
              clipPath={assetById(report, report.audio.assetId)?.path ?? null}
            />
          </Section>
        )}

        {report.vehicle && (
          <Section id="record" label="Vehicle record">
            <VehicleRecordSection vehicle={report.vehicle} />
          </Section>
        )}

        {report.price && (
          <Section id="price" label="Price check">
            <PriceSection price={report.price} />
          </Section>
        )}

        {report.sellerQuestions.length > 0 && (
          <Section
            id="questions"
            label={`Questions for the seller (${report.sellerQuestions.length})`}
          >
            <ol
              className="prose-sm"
              style={{ paddingLeft: "var(--s-5)", display: "grid", gap: "var(--s-2)" }}
            >
              {report.sellerQuestions.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ol>
          </Section>
        )}

        {report.negotiationScript.length > 0 && (
          <Section id="script" label="Negotiation script">
            <div style={{ display: "grid", gap: "var(--s-3)" }}>
              {report.negotiationScript.map((beat, i) => (
                <div key={i} className="panel">
                  <div className="label">{beat.beat}</div>
                  <p className="prose" style={{ margin: "var(--s-2) 0 0" }}>
                    &ldquo;{beat.say}&rdquo;
                  </p>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* LAW 5. Internal-facing in P0; see DECISIONS.md D-012. */}
        <Section id="run" label="Run metadata">
          <div className="table-scroll">
            <table>
              <tbody>
                <tr>
                  <td className="label">Mode</td>
                  <td className="data">{report.cost.mode}</td>
                </tr>
                <tr>
                  <td className="label">Images analyzed</td>
                  <td className="data">{report.cost.imagesAnalyzed}</td>
                </tr>
                <tr>
                  <td className="label">Tokens</td>
                  <td className="data">
                    {report.cost.inputTokens.toLocaleString()} in /{" "}
                    {report.cost.outputTokens.toLocaleString()} out
                  </td>
                </tr>
                <tr>
                  <td className="label">Audio processed</td>
                  <td className="data">{report.cost.audioSecondsProcessed.toFixed(1)}s</td>
                </tr>
                <tr>
                  <td className="label">Cost to produce</td>
                  <td className="data">${report.cost.usdTotal.toFixed(4)}</td>
                </tr>
                <tr>
                  <td className="label">Note</td>
                  <td>
                    <div className="prose-sm dim">{report.cost.note}</div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </Section>

        <footer
          style={{
            marginTop: "var(--s-9)",
            paddingTop: "var(--s-5)",
            borderTop: "1px solid var(--tk-rule)",
            display: "flex",
            justifyContent: "space-between",
            gap: "var(--s-4)",
            flexWrap: "wrap",
          }}
        >
          <span className="label">{SHARE_FOOTER}</span>
          <span className="prose-sm dim" style={{ maxWidth: "62ch" }}>
            Automated analysis of buyer-supplied media. Not an inspection. Have an
            independent mechanic examine any vehicle before you buy it.{" "}
            <a href="/accuracy">Accuracy and known limits</a>.
          </span>
        </footer>
      </div>
    </>
  );
}
