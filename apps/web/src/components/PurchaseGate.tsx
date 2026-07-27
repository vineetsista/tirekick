"use client";

import { useState } from "react";
import type { Teaser } from "@tirekick/shared";
import { PRICE_USD, checkoutConfigured, paymentLink } from "@/lib/checkout";

/**
 * The pre-payment acknowledgement. LIABILITY section 4, row three.
 *
 * The spec for this is precise and it is precise for a reason: a checkbox,
 * unticked by default, in its own paragraph, at the moment of the decision it
 * qualifies. Not a link to terms. Not a pre-ticked convenience. The design rule
 * from that document is that a disclaimer a user can get past without reading
 * has not been placed correctly, so the button does not exist until the box is
 * ticked - it is not merely greyed out.
 *
 * The three statements were chosen as the three things a person who feels
 * cheated afterwards would say they were not told. Two of them cost conversions.
 */

const ACKNOWLEDGEMENTS = [
  {
    id: "remote",
    text:
      "I understand this is an automated analysis of photographs, audio and " +
      "documents I provided - not a physical inspection, and not a mechanic.",
  },
  {
    id: "locked",
    text:
      "I understand brakes, airbags, frame and steering cannot be assessed from " +
      "media at all, and that this report will not tell me anything about them.",
  },
  {
    id: "mechanic",
    text:
      "I understand I should have an independent mechanic examine any vehicle " +
      "before buying it, and that this report is not a substitute for that.",
  },
];

export function PurchaseGate({ teaser }: { teaser: Teaser }) {
  const [ticked, setTicked] = useState<Record<string, boolean>>({});
  const allTicked = ACKNOWLEDGEMENTS.every((a) => ticked[a.id]);
  const link = paymentLink(teaser.inspectionId);
  const configured = checkoutConfigured();

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
        <div style={{ fontSize: 22, letterSpacing: "0.22em", fontWeight: 700 }}>
          TIREKICK
        </div>
        <div className="mono-label">before you buy</div>
      </header>

      <h1 style={{ fontSize: 28, margin: "32px 0 8px", fontWeight: 400 }}>
        {teaser.vehicleSummary || "Your inspection"}
      </h1>
      <div className="muted" style={{ fontSize: 14 }}>
        Full report, ${PRICE_USD}. One payment, no subscription.
      </div>

      {/* The accuracy position, before the acknowledgements, before the button. */}
      <section className="section">
        <div className="section-label">What has actually been measured</div>
        <div
          className="panel prose"
          style={{ borderLeft: "3px solid var(--tk-sev-major)", fontSize: 14, lineHeight: 1.7 }}
        >
          {teaser.accuracyStatement}
          <div style={{ marginTop: 14 }}>
            <a href="/accuracy">
              The accuracy page lists every finding type, its threshold, and whether it
              has been measured.
            </a>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section-label">What you get</div>
        <ul className="prose" style={{ margin: 0, paddingLeft: 20, fontSize: 14 }}>
          {teaser.unlocks.map((line, i) => (
            <li key={i} style={{ marginBottom: 8 }}>
              {line}
            </li>
          ))}
        </ul>
      </section>

      <section className="section">
        <div className="section-label">What you are not getting</div>
        <div className="panel">
          <ul className="prose" style={{ margin: 0, paddingLeft: 20, fontSize: 14 }}>
            {teaser.couldNotAssess.map((line, i) => (
              <li key={i} style={{ marginBottom: 8 }}>
                {line}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="section">
        <div className="section-label">Please read and confirm</div>
        <div style={{ display: "grid", gap: 4 }}>
          {ACKNOWLEDGEMENTS.map((item) => (
            <label
              key={item.id}
              htmlFor={item.id}
              className="panel"
              style={{
                display: "flex",
                gap: 14,
                alignItems: "flex-start",
                cursor: "pointer",
                borderLeft: `3px solid ${
                  ticked[item.id] ? "var(--tk-accent)" : "var(--tk-line)"
                }`,
              }}
            >
              <input
                id={item.id}
                type="checkbox"
                checked={Boolean(ticked[item.id])}
                onChange={(e) =>
                  setTicked((prev) => ({ ...prev, [item.id]: e.target.checked }))
                }
                style={{ marginTop: 3, width: 17, height: 17, accentColor: "var(--tk-accent)" }}
              />
              <span className="prose" style={{ fontSize: 14, lineHeight: 1.6 }}>
                {item.text}
              </span>
            </label>
          ))}
        </div>
      </section>

      <div style={{ marginTop: 32 }}>
        {!allTicked && (
          <div className="muted" style={{ fontSize: 13 }}>
            Confirm all three above to continue.
          </div>
        )}

        {/* Not rendered at all until confirmed, rather than rendered-and-disabled.
            A greyed-out button is still a thing to click at. */}
        {allTicked && configured && link && (
          <a
            href={link}
            style={{
              display: "inline-block",
              padding: "15px 30px",
              background: "var(--tk-accent)",
              color: "#0a0c0e",
              fontSize: 15,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              textDecoration: "none",
              fontWeight: 500,
            }}
          >
            Pay ${PRICE_USD} and open the report
          </a>
        )}

        {/* An unconfigured checkout says so. A dead href that looks live is
            worse than a button that admits it is not ready. */}
        {allTicked && !configured && (
          <div
            className="panel prose"
            style={{ borderLeft: "3px solid var(--tk-unknown)", fontSize: 14 }}
          >
            <div className="mono-label" style={{ marginBottom: 8 }}>
              Payment is not connected yet
            </div>
            This build has no Stripe payment link configured, so there is nothing to
            charge you with. Set <code>NEXT_PUBLIC_STRIPE_PAYMENT_LINK</code> to
            enable checkout.
          </div>
        )}
      </div>

      <div className="prose muted" style={{ fontSize: 12, marginTop: 40 }}>
        {teaser.banner}
      </div>
    </div>
  );
}
