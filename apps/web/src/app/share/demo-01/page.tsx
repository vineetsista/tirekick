import type { Metadata } from "next";
import { SHARE_FOOTER } from "@tirekick/shared";
import { ReportView } from "@/components/ReportView";
import { demoReport } from "@/lib/report";

export const metadata: Metadata = {
  title: "TIREKICK - shared report",
  description: "An automated analysis of buyer-supplied media. Not an inspection.",
  // A shared link is likely to be sent to a seller. It should not end up in a
  // search index attached to somebody's car.
  robots: { index: false, follow: false },
};

/**
 * The public share surface. LIABILITY section 4, row six.
 *
 * That table has specified "footer + watermark, plus the same 'not an
 * inspection' line" since P0, and nothing implemented it - the disclaimer
 * architecture described a page that did not exist for six phases, which is the
 * same class of drift P6 found on the landing page, sitting inside the liability
 * document itself.
 *
 * The watermark matters more here than anywhere else in the product. A report
 * page is read by the buyer who commissioned it and knows what it is. A shared
 * link gets forwarded to a seller, a partner, or a forum, arriving with no
 * context at all - so the page has to say what it is on its own, in a way that
 * survives a screenshot.
 */
export default function SharePage() {
  return (
    <div style={{ position: "relative" }}>
      {/* Fixed, diagonal, low-contrast, and behind the content so it never
          obstructs the evidence it is labelling. Survives a screenshot, which a
          footer does not. */}
      <div
        aria-hidden
        className="share-watermark"
        style={{
          position: "fixed",
          inset: 0,
          pointerEvents: "none",
          zIndex: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            transform: "rotate(-30deg)",
            fontSize: 64,
            letterSpacing: "0.3em",
            color: "var(--tk-locked)",
            opacity: 0.06,
            whiteSpace: "nowrap",
            fontWeight: 700,
          }}
        >
          {SHARE_FOOTER} &middot; {SHARE_FOOTER}
        </div>
      </div>

      <div style={{ position: "relative", zIndex: 1 }}>
        <div
          className="wrap"
          style={{
            paddingTop: 24,
            display: "flex",
            justifyContent: "space-between",
            gap: 16,
            flexWrap: "wrap",
            alignItems: "baseline",
          }}
        >
          <span className="mono-label" style={{ color: "var(--tk-locked)" }}>
            Shared report &middot; {SHARE_FOOTER}
          </span>
          <a href="/accuracy" style={{ fontSize: 12 }}>
            How accurate is this?
          </a>
        </div>

        <ReportView report={demoReport} />
      </div>
    </div>
  );
}
