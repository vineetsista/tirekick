import type { BoundingBox } from "@tirekick/shared";
import { cropFor } from "@/lib/crop";

/**
 * The cited region of a photograph, shown beside the claim it supports.
 *
 * LAW 1 says every finding cites visible evidence. Until now "visible" meant a
 * row of four numbers - `photo_01 [0.08, 0.62, 0.34, 0.14]` - with the actual
 * photograph in a gallery thousands of pixels away. A coordinate is a citation,
 * not evidence. This is the evidence.
 *
 * The corner ticks are the one piece of brand carried over from the first
 * version: a reticle rather than a rounded highlight, because the frame is an
 * instrument reading and not a photo filter.
 */
export function EvidenceCrop({
  src,
  box,
  color,
  caption,
  assetId,
  sourceWidth,
  sourceHeight,
  href,
  synthetic,
}: {
  src: string;
  box: BoundingBox;
  color: string;
  caption: string;
  assetId: string;
  sourceWidth: number | null;
  sourceHeight: number | null;
  href?: string;
  synthetic?: boolean;
}) {
  const geo = cropFor(box, sourceWidth, sourceHeight);

  /**
   * What to show when the asset's pixel dimensions were never recorded.
   *
   * D-045 already decided this - "cropFor returns null and the viewer shows the
   * whole frame" - and this branch then shipped `objectFit: cover`, which is the
   * opposite: a centre cut that silently discards a seventh of a 4:3 photograph,
   * half of a portrait one, and gives no sign which part went. The cited region
   * can be in any of the part that went, in the component whose only job is
   * showing a buyer the region a finding cites. It was safe from review because
   * it is the failure branch, and no fixture had a dimensionless asset until the
   * stress cases arrived.
   *
   * `contain` shows every pixel. The frame keeps its ratio, so the space is
   * still reserved before the image loads - a report of this length is navigated
   * by anchors, and an unreserved image lands them somewhere else. The bars it
   * costs are the honest shape of not knowing how big the photograph is, and the
   * caption says as much.
   */
  const wholeFrame = {
    width: "100%",
    height: "100%",
    objectFit: "contain",
    display: "block",
  } as const;

  const frame = (
    <div
      style={{
        position: "relative",
        overflow: "hidden",
        background: "#000",
        border: "1px solid var(--tk-rule)",
        aspectRatio: geo ? geo.aspect : 3 / 2,
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={
          geo
            ? `Cropped region of ${assetId}: ${caption}`
            : `${assetId}: ${caption}`
        }
        style={geo ? { position: "absolute", ...geo.image, maxWidth: "none" } : wholeFrame}
      />

      {geo && (
        <span
          aria-hidden
          style={{
            position: "absolute",
            ...geo.box,
            border: `2px solid ${color}`,
            boxShadow: `0 0 0 1px rgba(0,0,0,0.55)`,
          }}
        >
          {(
            [
              { top: -2, left: -2, borderTop: true, borderLeft: true },
              { top: -2, right: -2, borderTop: true, borderRight: true },
              { bottom: -2, left: -2, borderBottom: true, borderLeft: true },
              { bottom: -2, right: -2, borderBottom: true, borderRight: true },
            ] as const
          ).map((c, i) => (
            <span
              key={i}
              style={{
                position: "absolute",
                width: 11,
                height: 11,
                top: "top" in c ? c.top : undefined,
                bottom: "bottom" in c ? c.bottom : undefined,
                left: "left" in c ? c.left : undefined,
                right: "right" in c ? c.right : undefined,
                borderTop: "borderTop" in c ? `3px solid ${color}` : undefined,
                borderBottom: "borderBottom" in c ? `3px solid ${color}` : undefined,
                borderLeft: "borderLeft" in c ? `3px solid ${color}` : undefined,
                borderRight: "borderRight" in c ? `3px solid ${color}` : undefined,
              }}
            />
          ))}
        </span>
      )}

      {synthetic && (
        <span
          className="label"
          style={{
            position: "absolute",
            top: 8,
            left: 8,
            background: "var(--tk-locked)",
            color: "var(--tk-void)",
            fontSize: 9,
            padding: "2px 6px",
          }}
        >
          Synthetic
        </span>
      )}

      {/*
        A crop is a claim about scale as much as position. Stating the
        magnification stops a 4x blow-up of a 60px region reading as a
        clear photograph of a large defect.
      */}
      {geo && geo.magnification > 1.05 && (
        <span
          className="data"
          style={{
            position: "absolute",
            bottom: 8,
            right: 8,
            background: "rgba(11,10,9,0.82)",
            color: "var(--tk-graphite)",
            fontSize: 10,
            padding: "2px 6px",
            border: "1px solid var(--tk-rule)",
          }}
        >
          {geo.magnification.toFixed(1)}&times;
        </span>
      )}
    </div>
  );

  return (
    <figure style={{ margin: 0 }}>
      {href ? (
        <a href={href} style={{ display: "block", textDecoration: "none" }}>
          {frame}
        </a>
      ) : (
        frame
      )}
      <figcaption
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: "var(--s-3)",
          marginTop: "var(--s-2)",
          fontSize: "var(--t-xs)",
        }}
      >
        <span className="data dim">{assetId}</span>
        <span className="dim" style={{ textAlign: "right" }}>
          {geo
            ? `${(box.w * 100).toFixed(0)}×${(box.h * 100).toFixed(0)}% of frame`
            : "whole frame - region not marked, dimensions unrecorded"}
        </span>
      </figcaption>
    </figure>
  );
}
