import type { Metadata } from "next";
import Link from "next/link";
import { Wordmark } from "@/components/Wordmark";
import { UploadForm } from "./UploadForm";

/**
 * Where an inspection begins.
 *
 * The copy below promises exactly what this build does and no more. There is
 * no vision model key here, so photographs are catalogued rather than examined,
 * and the result says which systems nothing looked at (LAW 4: unmeasured
 * ability is not offered for money - and it is not dressed up here either).
 * What works today: document reading, records structure, coverage accounting,
 * and the audio measurements - each labelled with what it is.
 */

export const metadata: Metadata = {
  title: "TIREKICK - new analysis",
  description:
    "Upload the listing's media. TIREKICK analyzes what you provide and says plainly what it could not assess.",
  robots: { index: false, follow: false },
};

export default function NewInspectionPage() {
  return (
    <div className="wrap" style={{ paddingTop: 40, paddingBottom: 96, maxWidth: 760 }}>
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
        <Link href="/" style={{ color: "inherit", textDecoration: "none" }}>
          <Wordmark fontSize="22px" />
        </Link>
        <div className="mono-label">new analysis</div>
      </header>

      <h1 style={{ fontSize: 28, margin: "32px 0 8px", fontWeight: 400 }}>
        The media you provide, analyzed
      </h1>
      <div className="prose muted" style={{ fontSize: 14 }}>
        Nothing is fetched, scraped or assumed. If you do not upload it, the
        report does not mention it - and what the media cannot show is listed as
        exactly that, not skipped.
      </div>

      <section className="section">
        <div className="section-label">What this build does with it</div>
        <div
          className="panel prose"
          style={{ borderLeft: "3px solid var(--tk-unknown)", fontSize: 14, lineHeight: 1.7 }}
        >
          This build runs with no vision model attached. Your photographs are
          catalogued and every frame accounted for, documents are read, audio is
          measured, and the result states system by system what was not examined.
          No finding type has a measured accuracy yet; the{" "}
          <a href="/accuracy">accuracy page</a> is the ledger of that. Your files
          stay on this machine, and the free result is readable only in this
          browser - it gets an access cookie, not a public URL.
        </div>
      </section>

      <section className="section">
        <div className="section-label">Start</div>
        <UploadForm />
      </section>

      <div className="prose muted" style={{ fontSize: 12, marginTop: 40 }}>
        Automated analysis of media you provided. This is not an inspection, a
        certification, or a warranty. Brakes, airbags, frame and steering are
        never assessed remotely - an independent mechanic is the only way to
        clear them.
      </div>
    </div>
  );
}
