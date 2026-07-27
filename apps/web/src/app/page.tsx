import Link from "next/link";
import { REPORT_BANNER } from "@tirekick/shared";
import { demoTeaser } from "@/lib/report";

/**
 * The landing page, rewritten in P6 against the laws it is supposed to embody.
 *
 * The P0 version claimed TIREKICK returns "the open recalls on that VIN". By P1
 * that was known to be false - NHTSA publishes recalls per model and no public
 * endpoint says whether one was performed on an individual car (D-016) - and the
 * report had three separate caveats saying so while the front page went on
 * promising the thing the report refuses to claim. It also advertised walkaround
 * video analysis, which does not exist.
 *
 * Marketing copy drifts out of sync with the product silently, in the direction
 * of overclaiming, because nothing fails when it does. This page now states the
 * accuracy position above the fold, from the same generated sentence the checkout
 * page uses, so the least flattering fact about the product is the third thing a
 * stranger reads.
 */
export default function Home() {
  return (
    <div className="wrap" style={{ paddingTop: 72, paddingBottom: 96, maxWidth: 860 }}>
      <div style={{ fontSize: 26, letterSpacing: "0.24em", fontWeight: 700 }}>TIREKICK</div>

      <h1
        className="prose"
        style={{ fontSize: 34, lineHeight: 1.25, margin: "28px 0 20px", fontWeight: 600 }}
      >
        An AI reads the listing photos before you drive out to see the car.
      </h1>

      <p className="prose" style={{ fontSize: 16, color: "var(--tk-muted)", maxWidth: 640 }}>
        You give TIREKICK the photos, thirty seconds of engine audio, the VIN, any
        paperwork you have, and a few comparable listings you found yourself. It
        gives back what it can actually see - each finding boxed on the photograph it
        came from, with how confident it is and why - plus the recall campaigns on
        record for that model year, a spectrogram of the engine audio, what your own
        documents say, and the questions to ask before you hand over any money.
      </p>

      <div
        className="prose"
        style={{
          marginTop: 32,
          border: "1px solid var(--tk-locked)",
          borderLeftWidth: 4,
          background: "rgba(163,113,247,0.07)",
          padding: "18px 20px",
          fontSize: 15,
          lineHeight: 1.6,
        }}
      >
        <strong style={{ fontWeight: 600 }}>What it is not.</strong> {REPORT_BANNER}{" "}
        Brakes, airbags, frame, and steering are locked off in software - TIREKICK will
        not tell you those are fine, because it cannot know that from a photograph and
        no confidence score would make it safe to guess.
      </div>

      {/* LAW 6. The same generated sentence the checkout page carries, above the
          fold, because the version of this page that buries it is the version
          that eventually stops saying it. */}
      <div
        className="prose"
        style={{
          marginTop: 16,
          border: "1px solid var(--tk-sev-major)",
          padding: "18px 20px",
          fontSize: 15,
          lineHeight: 1.6,
        }}
      >
        <strong style={{ fontWeight: 600 }}>How much of this is measured.</strong>{" "}
        {demoTeaser.accuracyStatement}
      </div>

      <div style={{ marginTop: 40, display: "flex", gap: 20, flexWrap: "wrap" }}>
        <Link
          href="/teaser/demo-01"
          style={{
            border: "1px solid var(--tk-accent)",
            color: "var(--tk-accent)",
            padding: "12px 20px",
            fontSize: 13,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
          }}
        >
          See a free result
        </Link>
        <Link
          href="/report/demo-01"
          style={{
            border: "1px solid var(--tk-line)",
            color: "var(--tk-text)",
            padding: "12px 20px",
            fontSize: 13,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
          }}
        >
          See a full report
        </Link>
        <Link
          href="/accuracy"
          style={{
            border: "1px solid var(--tk-line)",
            color: "var(--tk-text)",
            padding: "12px 20px",
            fontSize: 13,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
          }}
        >
          How accurate is it
        </Link>
      </div>

      <div className="section">
        <div className="section-label">What the report will not do</div>
        <ul className="prose" style={{ margin: 0, paddingLeft: 20, fontSize: 15, maxWidth: 700 }}>
          <li style={{ marginBottom: 10 }}>
            <strong style={{ fontWeight: 600 }}>Tell you a car is fine.</strong> There
            is no pass. The strongest thing it says is that nothing adverse was
            visible in the photographs you sent, which is a statement about the
            photographs.
          </li>
          <li style={{ marginBottom: 10 }}>
            <strong style={{ fontWeight: 600 }}>
              Tell you whether a recall was done on your car.
            </strong>{" "}
            NHTSA publishes recall campaigns per model, and publishes nothing about
            individual vehicles. The report lists what could apply and tells you to
            ring a dealer, who will check by VIN for free.
          </li>
          <li style={{ marginBottom: 10 }}>
            <strong style={{ fontWeight: 600 }}>Check the title.</strong> TIREKICK
            queries no title registry. If it names a title brand, it is quoting a
            document you uploaded, with the line shown so you can read it yourself.
          </li>
          <li style={{ marginBottom: 10 }}>
            <strong style={{ fontWeight: 600 }}>Diagnose the engine from audio.</strong>{" "}
            It draws the recording as a spectrogram and marks where the sharp sounds
            are. It does not say what made them, because that has not been measured.
          </li>
          <li>
            <strong style={{ fontWeight: 600 }}>Replace a mechanic.</strong> It is
            worth about an hour of a careful friend&rsquo;s attention before you drive
            across town. That is genuinely useful and it is not an inspection.
          </li>
        </ul>
      </div>

      <p className="muted prose" style={{ marginTop: 40, fontSize: 13, maxWidth: 660 }}>
        The sample report is generated from synthetic fixture media - drawings, not
        photographs of any car - except the vehicle record, which is real federal
        data for a documentation VIN that identifies nobody. Real accuracy numbers do
        not exist yet, and the accuracy page says so in its first line rather than
        waiting until we have something flattering to put there.
      </p>
    </div>
  );
}
