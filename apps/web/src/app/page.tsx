import Link from "next/link";
import { REPORT_BANNER } from "@tirekick/shared";

/**
 * P0 landing page. Deliberately plain: the real page, the pricing, and the upload
 * flow land in P5. What it does carry already is the honesty architecture -
 * what this is and is not, above the fold, in body copy rather than fine print
 * (LIABILITY section 4).
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
        You give TIREKICK the photos, a walkaround video, thirty seconds of engine
        audio, the VIN, and a few comparable listings. It gives you back what it can
        see - each finding boxed on the photo it came from, with how confident it is -
        plus the open recalls on that VIN, a price check against your comps, and the
        questions to ask before you hand over any money.
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

      <div style={{ marginTop: 40, display: "flex", gap: 20, flexWrap: "wrap" }}>
        <Link
          href="/report/demo-01"
          style={{
            border: "1px solid var(--tk-accent)",
            color: "var(--tk-accent)",
            padding: "12px 20px",
            fontSize: 13,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
          }}
        >
          See a sample report
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

      <p className="muted prose" style={{ marginTop: 40, fontSize: 13, maxWidth: 640 }}>
        The sample report is generated from synthetic fixture media - drawings, not
        photographs of any car. Real accuracy numbers do not exist yet, and the
        accuracy page says so in its first line rather than waiting until we have
        something flattering to put there.
      </p>
    </div>
  );
}
