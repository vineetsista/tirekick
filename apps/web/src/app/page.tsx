import Link from "next/link";
import { REPORT_BANNER } from "@tirekick/shared";
import { CoverageMap } from "@/components/CoverageMap";
import { EvidenceCrop } from "@/components/EvidenceCrop";
import {
  assetById,
  assetUrl,
  demoReport,
  demoTeaser,
  headlineFinding,
  severityColor,
} from "@/lib/report";

/**
 * The landing page.
 *
 * ---------------------------------------------------------------------------
 * THE HERO IS THE PRODUCT'S OWN OUTPUT, NOT A DESCRIPTION OF IT
 * ---------------------------------------------------------------------------
 *
 * Two problems, one fix.
 *
 * The first is that this page rendered zero images. TIREKICK sells "each finding
 * boxed on the photograph it came from" and a stranger deciding whether to spend
 * $25 could not see one anywhere before paying. A visual evidence product whose
 * shop window is a wall of text is asking to be taken on faith, which is the
 * opposite of what it claims to offer.
 *
 * The second is drift. The P0 page promised per-VIN recall status for four
 * phases after the report had been rewritten to refuse exactly that claim, and
 * nothing failed, because prose in a page has no relationship to the engine.
 * `Marketing.test.tsx` catches the wording. It cannot catch the gap between a
 * described product and a real one.
 *
 * So the hero renders `headlineFinding(demoReport)` through the same components
 * the paid report uses, from the same parsed artifact. The page cannot advertise
 * a finding the engine did not produce, cannot show a confidence the engine did
 * not assign, and changes the moment the pipeline's output changes.
 */
export default function Home() {
  const finding = headlineFinding(demoReport);
  const evidence = finding?.evidence.find((e) => e.kind === "image_region");
  const asset = evidence ? assetById(demoReport, evidence.assetId) : undefined;

  return (
    <>
      <nav
        className="no-print"
        style={{
          position: "sticky",
          top: 0,
          zIndex: 20,
          background: "rgba(11,10,9,0.92)",
          backdropFilter: "blur(8px)",
          borderBottom: "1px solid var(--tk-rule)",
        }}
      >
        <div
          className="wrap"
          style={{
            height: "var(--tk-nav-h)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--s-4)",
          }}
        >
          <span
            style={{
              fontWeight: 800,
              letterSpacing: "0.26em",
              fontSize: "var(--t-sm)",
            }}
          >
            TIREKICK
          </span>
          <span style={{ display: "flex", gap: "var(--s-5)", fontSize: "var(--t-sm)" }}>
            <Link href="/accuracy">Accuracy</Link>
            <Link href="/teaser/demo-01">Sample</Link>
          </span>
        </div>
      </nav>

      <div className="wrap" style={{ paddingTop: "var(--s-8)", paddingBottom: "var(--s-9)" }}>
        {/* ---------------------------------------------------------------- */}
        {/* hero                                                              */}
        {/* ---------------------------------------------------------------- */}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(320px, 100%), 1fr))",
            gap: "var(--s-7)",
            alignItems: "center",
          }}
        >
          <div>
            <h1 style={{ fontSize: "var(--t-3xl)", fontWeight: 800 }}>
              An AI reads the listing photos before you drive out to see the car.
            </h1>
            <p
              className="prose"
              style={{ marginTop: "var(--s-5)", color: "var(--tk-graphite)", maxWidth: "46ch" }}
            >
              You give TIREKICK the photos, a walkaround video, thirty seconds of
              engine audio, the VIN, any paperwork you have, and a few comparable
              listings you found yourself. It gives back what it can actually see
              &mdash; each finding boxed on the photograph it came from, with how
              confident it is and why &mdash; plus the recall campaigns on record
              for that model year, a spectrogram of the engine audio, what your own
              documents say, and the questions to ask before you hand over any
              money.
            </p>
          </div>

          {finding && evidence?.kind === "image_region" && asset ? (
            <figure
              style={{
                margin: 0,
                border: "1px solid var(--tk-rule)",
                background: "var(--tk-shell)",
                padding: "var(--s-4)",
              }}
            >
              <EvidenceCrop
                src={assetUrl(demoReport.inspectionId, asset.path)}
                box={evidence.box}
                color={severityColor(finding.severity)}
                caption={evidence.caption}
                assetId={evidence.assetId}
                sourceWidth={asset.width}
                sourceHeight={asset.height}
                synthetic={asset.synthetic}
              />
              <figcaption style={{ marginTop: "var(--s-4)" }}>
                <span
                  className="chip chip-solid"
                  style={{ background: severityColor(finding.severity) }}
                >
                  {finding.severity}
                </span>
                <span className="label" style={{ marginLeft: "var(--s-2)" }}>
                  confidence {finding.confidence.toFixed(2)}
                </span>
                <div className="prose" style={{ marginTop: "var(--s-3)" }}>
                  {finding.title}
                </div>
                <div
                  className="prose-sm dim"
                  style={{ marginTop: "var(--s-2)" }}
                >
                  {finding.confidenceBasis}
                </div>
              </figcaption>
            </figure>
          ) : null}
        </div>

        <p className="prose-sm dim" style={{ marginTop: "var(--s-4)" }}>
          That is not a mock-up. It is a real finding from the sample report,
          rendered by the same code the paid report uses, from the same file. If
          the engine stops producing it, this page stops showing it.
        </p>

        {/* ---------------------------------------------------------------- */}
        {/* the two disclosures, above any call to action                     */}
        {/* ---------------------------------------------------------------- */}

        <div
          style={{
            marginTop: "var(--s-7)",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(300px, 100%), 1fr))",
            gap: "var(--s-4)",
          }}
        >
          <div
            className="panel panel-edge"
            style={{ borderLeftColor: "var(--tk-locked)" }}
          >
            <div className="label" style={{ color: "var(--tk-locked)" }}>
              What it is not
            </div>
            <p className="prose-sm" style={{ margin: "var(--s-3) 0 0" }}>
              {REPORT_BANNER} Brakes, airbags, frame, and steering are locked off
              in software &mdash; TIREKICK will not tell you those are fine,
              because it cannot know that from a photograph and no confidence
              score would make it safe to guess.
            </p>
          </div>

          {/* LAW 6. The same generated sentence the checkout page carries. The
              version of this page that buries it is the version that eventually
              stops saying it. */}
          <div
            className="panel panel-edge"
            style={{ borderLeftColor: "var(--tk-sev-major)" }}
          >
            <div className="label" style={{ color: "var(--tk-sev-major)" }}>
              How much of this is measured
            </div>
            <p className="prose-sm" style={{ margin: "var(--s-3) 0 0" }}>
              {demoTeaser.accuracyStatement}
            </p>
          </div>
        </div>

        <div
          style={{
            marginTop: "var(--s-6)",
            display: "flex",
            gap: "var(--s-3)",
            flexWrap: "wrap",
          }}
        >
          <Link href="/teaser/demo-01" className="btn btn-primary">
            See a free result
          </Link>
          <Link href="/report/demo-01" className="btn">
            See a full report
          </Link>
          <Link href="/accuracy" className="btn">
            How accurate is it
          </Link>
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* the signature                                                     */}
        {/* ---------------------------------------------------------------- */}

        <section className="section">
          <div className="section-label">
            <span>What it looked at, and what it did not</span>
          </div>
          <p className="prose" style={{ maxWidth: "62ch", marginTop: 0 }}>
            Every report opens with this map. Most inspection tools show you a
            column of ticks; the useful half of an automated analysis is the half
            it could not do, so that is drawn at the same weight as everything
            else.
          </p>
          <div style={{ marginTop: "var(--s-5)" }}>
            <CoverageMap report={demoReport} />
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* refusals                                                          */}
        {/* ---------------------------------------------------------------- */}

        <section className="section">
          <div className="section-label">
            <span>What the report will not do</span>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(280px, 100%), 1fr))",
              gap: "var(--s-5)",
            }}
          >
            {[
              {
                head: "Tell you a car is fine.",
                body: "There is no pass. The strongest thing it says is that nothing adverse was visible in the photographs you sent, which is a statement about the photographs.",
              },
              {
                head: "Tell you whether a recall was done on your car.",
                body: "NHTSA publishes recall campaigns per model, and publishes nothing about individual vehicles. The report lists what could apply and tells you to ring a dealer, who will check by VIN for free.",
              },
              {
                head: "Check the title.",
                body: "TIREKICK queries no title registry. If it names a title brand, it is quoting a document you uploaded, with the line shown so you can read it yourself.",
              },
              {
                head: "Diagnose the engine from audio.",
                body: "It draws the recording as a spectrogram and marks where the sharp sounds are. It does not say what made them, because that has not been measured.",
              },
              {
                head: "Tell you what the walkaround showed in full.",
                body: "It samples frames, keeps the sharpest of each moment, and discards the blurred and the duplicated. The report says how many it dropped and why, because five frames analysed is not the same as a video watched.",
              },
              {
                head: "Replace a mechanic.",
                body: "It is worth about an hour of a careful friend's attention before you drive across town. That is genuinely useful and it is not an inspection.",
              },
            ].map((item) => (
              <div key={item.head}>
                <div className="prose" style={{ fontWeight: 600 }}>
                  {item.head}
                </div>
                <p className="prose-sm muted" style={{ margin: "var(--s-2) 0 0" }}>
                  {item.body}
                </p>
              </div>
            ))}
          </div>
        </section>

        <p
          className="prose-sm dim"
          style={{ marginTop: "var(--s-8)", maxWidth: "72ch" }}
        >
          The sample report is generated from synthetic fixture media &mdash;
          drawings, not photographs of any car &mdash; except the vehicle record,
          which is real federal data for a documentation VIN that identifies
          nobody. Real accuracy numbers do not exist yet, and the accuracy page
          says so in its first line rather than waiting until we have something
          flattering to put there.
        </p>
      </div>
    </>
  );
}
