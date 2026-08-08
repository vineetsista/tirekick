import Link from "next/link";
import { Wordmark } from "./Wordmark";

/**
 * Persistent navigation for a document that is 14,000 pixels tall.
 *
 * The report had none. A buyer who wanted the price check after reading the
 * findings scrolled past nine thousand pixels of evidence to find it, and a buyer
 * who arrived from a share link had no way to know the price check existed at
 * all. Long documents get a contents page; this is the screen equivalent.
 *
 * Anchors rather than client-side routing, so it works with JavaScript disabled,
 * survives a print, and every section keeps a real URL somebody can send to a
 * mechanic. `scroll-padding-top` in globals.css keeps the target clear of the bar.
 */
export function ReportNav({
  sections,
}: {
  // The caller derives this list from the sections it renders, so `count` is
  // present-but-undefined for the sections that have nothing to count, and
  // `exactOptionalPropertyTypes` treats that as different from absent.
  sections: { id: string; label: string; count?: number | undefined }[];
}) {
  return (
    <nav
      className="no-print"
      style={{
        position: "sticky",
        top: 0,
        zIndex: 20,
        background: "rgba(11,10,9,0.94)",
        backdropFilter: "blur(8px)",
        borderBottom: "1px solid var(--tk-rule)",
      }}
      aria-label="Report sections"
    >
      <div
        className="wrap"
        style={{
          minHeight: "var(--tk-nav-h)",
          display: "flex",
          alignItems: "center",
          gap: "var(--s-4)",
        }}
      >
        <Link href="/" style={{ textDecoration: "none", flex: "0 0 auto" }}>
          <Wordmark />
        </Link>

        {/*
          Sixteen sections do not fit on a laptop, so this scrolls. It did so
          silently: the last label was sliced down the middle by the edge of the
          container, which reads as a rendering fault rather than as an
          invitation to scroll. The mask fades the final few pixels instead, so
          the cut looks deliberate and implies more to the right.
        */}
        <div
          style={{
            display: "flex",
            gap: "var(--s-4)",
            overflowX: "auto",
            flex: "1 1 auto",
            minWidth: 0,
            scrollbarWidth: "none",
            maskImage:
              "linear-gradient(to right, #000 calc(100% - 28px), transparent)",
            WebkitMaskImage:
              "linear-gradient(to right, #000 calc(100% - 28px), transparent)",
          }}
        >
          {sections.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              className="label"
              style={{
                whiteSpace: "nowrap",
                textDecoration: "none",
                paddingBlock: "var(--s-3)",
                color: "var(--tk-graphite)",
              }}
            >
              {s.label}
              {s.count !== undefined && (
                <span className="data" style={{ marginLeft: 6, color: "var(--tk-pencil)" }}>
                  {s.count}
                </span>
              )}
            </a>
          ))}
        </div>

      </div>
    </nav>
  );
}
