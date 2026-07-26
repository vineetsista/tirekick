import type { BoundingBox, Finding, MechanicReferral } from "@tirekick/shared";
import { severityColor } from "@/lib/report";

/**
 * The annotated image. This is the signature visual (BRAND.md), so it gets the
 * details: sharp corners, no shadows, a targeting-reticle tick at each corner of
 * every box, and a fine grid across the whole frame. The grid is what does most
 * of the instrument-readout work and it costs nothing.
 *
 * Every box is an anchor to its finding. Evidence and claim are never more than
 * one interaction apart (LAW 1).
 */

type Annotation = {
  box: BoundingBox;
  color: string;
  label: string;
  href: string;
  caption: string;
};

function CornerTicks({ color }: { color: string }) {
  const arm = 9;
  const thickness = 2;
  const corners = [
    { top: -thickness, left: -thickness, borderTop: true, borderLeft: true },
    { top: -thickness, right: -thickness, borderTop: true, borderRight: true },
    { bottom: -thickness, left: -thickness, borderBottom: true, borderLeft: true },
    { bottom: -thickness, right: -thickness, borderBottom: true, borderRight: true },
  ] as const;

  return (
    <>
      {corners.map((c, i) => (
        <span
          key={i}
          aria-hidden
          style={{
            position: "absolute",
            width: arm,
            height: arm,
            top: "top" in c ? c.top : undefined,
            bottom: "bottom" in c ? c.bottom : undefined,
            left: "left" in c ? c.left : undefined,
            right: "right" in c ? c.right : undefined,
            borderTop: "borderTop" in c ? `${thickness}px solid ${color}` : undefined,
            borderBottom:
              "borderBottom" in c ? `${thickness}px solid ${color}` : undefined,
            borderLeft: "borderLeft" in c ? `${thickness}px solid ${color}` : undefined,
            borderRight:
              "borderRight" in c ? `${thickness}px solid ${color}` : undefined,
          }}
        />
      ))}
    </>
  );
}

export function Overlay({
  src,
  alt,
  annotations,
  synthetic,
}: {
  src: string;
  alt: string;
  annotations: Annotation[];
  synthetic: boolean;
}) {
  return (
    <figure style={{ margin: 0 }}>
      <div
        style={{
          position: "relative",
          background: "#000",
          border: "1px solid var(--tk-line)",
          lineHeight: 0,
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={alt}
          style={{
            width: "100%",
            height: "auto",
            display: "block",
            filter: "saturate(0.85) brightness(0.92)",
          }}
        />

        {/* Fine grid at low opacity - the CT-scan cue. */}
        <span
          aria-hidden
          style={{
            position: "absolute",
            inset: 0,
            pointerEvents: "none",
            backgroundImage:
              "repeating-linear-gradient(to right, rgba(230,237,243,0.04) 0 1px, transparent 1px 40px)," +
              "repeating-linear-gradient(to bottom, rgba(230,237,243,0.04) 0 1px, transparent 1px 40px)",
          }}
        />

        {annotations.map((a, i) => {
          const pct = (n: number) => `${(n * 100).toFixed(3)}%`;
          return (
            <a
              key={i}
              href={a.href}
              title={a.caption}
              style={{
                position: "absolute",
                left: pct(a.box.x),
                top: pct(a.box.y),
                width: pct(a.box.w),
                height: pct(a.box.h),
                border: `2px solid ${a.color}`,
                background: `color-mix(in srgb, ${a.color} 8%, transparent)`,
                borderRadius: 0,
                display: "block",
              }}
            >
              <CornerTicks color={a.color} />
              <span
                style={{
                  position: "absolute",
                  // Below the box normally; above it when the box runs to the
                  // bottom of the frame.
                  ...(a.box.y + a.box.h > 0.86
                    ? { bottom: "100%", marginBottom: 4 }
                    : { top: "100%", marginTop: 4 }),
                  // Right-anchored for boxes in the right half, so the label
                  // stays inside the image instead of being clipped at the edge.
                  ...(a.box.x + a.box.w > 0.5 ? { right: -2 } : { left: -2 }),
                  background: a.color,
                  color: "#0a0c0e",
                  fontSize: 10,
                  letterSpacing: "0.12em",
                  padding: "2px 6px",
                  whiteSpace: "nowrap",
                  lineHeight: 1.6,
                }}
              >
                {a.label}
              </span>
            </a>
          );
        })}

        {synthetic && (
          <span
            style={{
              position: "absolute",
              top: 10,
              right: 10,
              background: "var(--tk-locked)",
              color: "#0a0c0e",
              fontSize: 10,
              letterSpacing: "0.14em",
              padding: "3px 8px",
              lineHeight: 1.6,
            }}
          >
            SYNTHETIC FIXTURE
          </span>
        )}
      </div>
    </figure>
  );
}

export function annotationsFor(
  assetId: string,
  findings: Finding[],
  referrals: MechanicReferral[] = [],
): Annotation[] {
  const out: Annotation[] = [];
  for (const f of findings) {
    for (const ev of f.evidence) {
      if (ev.kind !== "image_region" || ev.assetId !== assetId) continue;
      out.push({
        box: ev.box,
        color: severityColor(f.severity),
        label: `${f.type.replace(/_/g, " ").toUpperCase()} / ${f.severity.toUpperCase()} / ${f.confidence.toFixed(2)}`,
        href: `#${f.id}`,
        caption: ev.caption,
      });
    }
  }

  // Referral evidence gets boxed too. LAW 1 requires the evidence behind every
  // statement to be visible, and a referral is a statement. It is drawn in the
  // locked color with no severity and no confidence in its label, because a
  // locked system never carries either (LAW 2).
  for (const r of referrals) {
    for (const ev of r.evidence) {
      if (ev.kind !== "image_region" || ev.assetId !== assetId) continue;
      out.push({
        box: ev.box,
        color: "var(--tk-locked)",
        label: `${r.system.toUpperCase()} / MECHANIC REQUIRED`,
        href: `#${r.id}`,
        caption: ev.caption,
      });
    }
  }
  return out;
}
