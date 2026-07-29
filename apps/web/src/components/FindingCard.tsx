import type { Asset, Finding } from "@tirekick/shared";
import { ConfidenceBar } from "./ConfidenceBar";
import { EvidenceCrop } from "./EvidenceCrop";
import { assetUrl, severityColor, titleCase } from "@/lib/report";

/**
 * A finding, with the picture it came from.
 *
 * ---------------------------------------------------------------------------
 * THE LAW 1 LAYOUT BUG THIS FIXES
 * ---------------------------------------------------------------------------
 *
 * `Overlay.tsx` carries the comment "Evidence and claim are never more than one
 * interaction apart (LAW 1)". On the rendered report the evidence gallery sat at
 * roughly 1,300px and the findings began at roughly 5,000px, on a page 14,282px
 * tall. What sat beside the claim was this:
 *
 *     photo_01 - Corrosion band along the lower rocker panel [0.08, 0.62, 0.34, 0.14]
 *
 * Four numbers. A buyer reading "corrosion visible along the driver-side rocker
 * panel" could not see the corrosion without scrolling four thousand pixels and
 * then finding the right thumbnail among thirteen, each about 340px wide, in
 * which a box covering 34% by 14% of the frame renders about 115px by 20px.
 *
 * The comment described an intention. The layout did something else, and nothing
 * checked, because a claim about layout written in a docstring is not a test.
 * `ReportView.test.tsx` now asserts the ordering instead of trusting the comment.
 *
 * The coordinates stay - they are what makes the claim checkable against the
 * hash, and the asset now records its pixel dimensions so a reader can redraw the
 * box themselves. They just are not the evidence any more.
 */
export function FindingCard({
  finding,
  assets,
  inspectionId,
}: {
  finding: Finding;
  assets: Map<string, Asset>;
  inspectionId: string;
}) {
  const color = severityColor(finding.severity);
  const imageEvidence = finding.evidence.filter((e) => e.kind === "image_region");
  const otherEvidence = finding.evidence.filter((e) => e.kind !== "image_region");

  return (
    <article
      id={finding.id}
      className="panel panel-edge"
      style={{ borderLeftColor: color }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: "var(--s-4)",
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "var(--s-3)" }}>
          <span className="chip chip-solid" style={{ background: color }}>
            {finding.severity}
          </span>
          <span className="label">
            {titleCase(finding.type)} &middot; {finding.engine}
          </span>
        </div>
        <ConfidenceBar value={finding.confidence} color={color} />
      </header>

      <div
        className={imageEvidence.length > 0 ? "split split-figure" : "split"}
        style={{ marginTop: "var(--s-4)" }}
      >
        {imageEvidence.length > 0 && (
          <div style={{ display: "grid", gap: "var(--s-3)" }}>
            {imageEvidence.map((ev, i) => {
              if (ev.kind !== "image_region") return null;
              const asset = assets.get(ev.assetId);
              if (!asset) return null;
              return (
                <EvidenceCrop
                  key={i}
                  src={assetUrl(inspectionId, asset.path)}
                  box={ev.box}
                  color={color}
                  caption={ev.caption}
                  assetId={ev.assetId}
                  sourceWidth={asset.width}
                  sourceHeight={asset.height}
                  synthetic={asset.synthetic}
                  href={`#asset-${ev.assetId}`}
                />
              );
            })}
          </div>
        )}

        <div style={{ minWidth: 0 }}>
          <h3 style={{ fontSize: "var(--t-lg)" }}>{finding.title}</h3>
          <p className="prose-sm" style={{ marginTop: "var(--s-3)" }}>
            {finding.detail}
          </p>
          <p className="prose-sm dim" style={{ marginTop: "var(--s-3)" }}>
            <strong style={{ fontWeight: 600 }}>Why this confidence:</strong>{" "}
            {finding.confidenceBasis}
          </p>

          {imageEvidence.map((ev, i) =>
            ev.kind === "image_region" ? (
              <p
                key={i}
                className="prose-sm dim"
                style={{ marginTop: "var(--s-2)", fontSize: "var(--t-sm)" }}
              >
                {ev.caption}{" "}
                <span className="data" style={{ color: "var(--tk-pencil)" }}>
                  {ev.assetId} [{ev.box.x.toFixed(2)}, {ev.box.y.toFixed(2)},{" "}
                  {ev.box.w.toFixed(2)}, {ev.box.h.toFixed(2)}]
                </span>
              </p>
            ) : null,
          )}

          {otherEvidence.length > 0 && (
            <div
              style={{
                marginTop: "var(--s-4)",
                paddingTop: "var(--s-3)",
                borderTop: "1px solid var(--tk-rule)",
              }}
            >
              <div className="label">Evidence</div>
              <ul
                className="prose-sm"
                style={{ margin: "var(--s-2) 0 0", paddingLeft: "var(--s-5)" }}
              >
                {otherEvidence.map((ev, i) => (
                  <li key={i} className="dim" style={{ marginBottom: "var(--s-1)" }}>
                    {ev.kind === "audio_segment" && (
                      <>
                        <span className="data" style={{ color: "var(--tk-paper)" }}>
                          {ev.assetId}
                        </span>{" "}
                        <span className="data">
                          {ev.startSec.toFixed(1)}s&ndash;{ev.endSec.toFixed(1)}s
                        </span>{" "}
                        &mdash; {ev.caption}
                      </>
                    )}
                    {ev.kind === "data_record" && (
                      <>
                        <span style={{ color: "var(--tk-paper)" }}>{ev.source}</span> /{" "}
                        <span className="data">{ev.recordId}</span> &mdash; {ev.caption}{" "}
                        <span className="data" style={{ color: "var(--tk-pencil)" }}>
                          ({ev.retrievedAt})
                        </span>
                      </>
                    )}
                    {ev.kind === "document_excerpt" && (
                      <>
                        <span className="data" style={{ color: "var(--tk-paper)" }}>
                          {ev.assetId}
                        </span>{" "}
                        &mdash; &ldquo;{ev.excerpt}&rdquo;
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(finding.estimatedCostUsd || finding.sellerQuestion || finding.mechanicCheck) && (
            <div
              style={{
                marginTop: "var(--s-4)",
                paddingTop: "var(--s-3)",
                borderTop: "1px solid var(--tk-rule)",
                display: "grid",
                gap: "var(--s-2)",
              }}
            >
              {finding.estimatedCostUsd && (
                <div className="prose-sm">
                  <span className="label">Est. repair</span>{" "}
                  <span className="data" style={{ color }}>
                    ${finding.estimatedCostUsd.low.toLocaleString()}&ndash;$
                    {finding.estimatedCostUsd.high.toLocaleString()}
                  </span>
                </div>
              )}
              {finding.sellerQuestion && (
                <div className="prose-sm">
                  <span className="label">Ask the seller</span> {finding.sellerQuestion}
                </div>
              )}
              {finding.mechanicCheck && (
                <div className="prose-sm">
                  <span className="label">Ask a mechanic</span> {finding.mechanicCheck}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
