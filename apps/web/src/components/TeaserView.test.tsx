import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { LOCKED_SYSTEMS, LOCKED_SYSTEM_STATEMENT } from "@tirekick/shared";
import { TeaserView } from "./TeaserView";
import { PurchaseGate } from "./PurchaseGate";
import { demoReport, demoTeaser } from "@/lib/report";

/**
 * The paywall, tested on the rendered markup.
 *
 * `test_teaser.py` proves the projection drops the paid content. This proves the
 * component does not put it back - by importing the full report alongside the
 * teaser and searching the free HTML for every sentence in it.
 */

const html = renderToStaticMarkup(<TeaserView teaser={demoTeaser} />);
const text = html
  .replace(/&#x27;/g, "'")
  .replace(/&quot;/g, '"')
  .replace(/&lt;/g, "<")
  .replace(/&gt;/g, ">")
  .replace(/&amp;/g, "&");

describe("the paywall holds in the markup", () => {
  it("renders no finding title, detail or basis", () => {
    expect(demoReport.findings.length).toBeGreaterThan(0);
    for (const finding of demoReport.findings) {
      expect(text).not.toContain(finding.title);
      expect(text).not.toContain(finding.detail);
      expect(text).not.toContain(finding.confidenceBasis);
    }
  });

  it("renders no evidence of any kind", () => {
    for (const finding of demoReport.findings) {
      for (const ev of finding.evidence) {
        if ("caption" in ev) expect(text).not.toContain(ev.caption);
        if (ev.kind === "document_excerpt") expect(text).not.toContain(ev.excerpt);
      }
    }
    expect(html).not.toContain("<img");
  });

  it("renders no mechanic referral observation, only a count", () => {
    expect(demoReport.mechanicReferrals.length).toBeGreaterThan(0);
    for (const referral of demoReport.mechanicReferrals) {
      expect(text).not.toContain(referral.observation);
    }
    expect(text).toContain(`${demoTeaser.mechanicReferralCount} for your mechanic`);
  });

  it("never shows the VIN, masked or otherwise", () => {
    const vehicle = demoReport.vehicle!;
    expect(html).not.toContain(vehicle.vin);
    expect(html).not.toContain(vehicle.vinMasked);
  });

  it("shows the vehicle only as year, make and model", () => {
    expect(text).toContain("2013 HONDA Accord");
  });
});

describe("what stays free, and where it sits", () => {
  it("puts coverage before the price", () => {
    // A buyer should be able to decide this is not worth it for their six-photo
    // listing before they ever see a number.
    expect(text.indexOf("What your media covered")).toBeLessThan(
      text.indexOf(`$${demoTeaser.priceUsd.toFixed(0)}`),
    );
  });

  it("puts what we could not assess before the price too", () => {
    expect(text.indexOf("What this analysis could not assess")).toBeLessThan(
      text.indexOf(`$${demoTeaser.priceUsd.toFixed(0)}`),
    );
    for (const line of demoTeaser.couldNotAssess) {
      expect(text).toContain(line);
    }
  });

  it("says the limits list is not shortened by paying", () => {
    expect(text).toContain("This list is free and always will be");
  });

  it("renders all four locked rows verbatim", () => {
    for (const system of LOCKED_SYSTEMS) {
      const row = demoTeaser.systems.find((s) => s.system === system)!;
      expect(row.statement).toBe(LOCKED_SYSTEM_STATEMENT);
    }
    expect(text).toContain(LOCKED_SYSTEM_STATEMENT);
  });

  it("states the accuracy position above the call to action", () => {
    expect(text).toContain(demoTeaser.accuracyStatement);
    expect(text.indexOf(demoTeaser.accuracyStatement)).toBeLessThan(
      text.indexOf("Continue to the full report"),
    );
  });
});

describe("the purchase gate (LIABILITY section 4)", () => {
  const gate = renderToStaticMarkup(<PurchaseGate teaser={demoTeaser} />);

  it("offers no way to pay before the acknowledgements are ticked", () => {
    // Rendered-and-disabled is still a thing to click at. The button does not
    // exist in the initial markup at all.
    expect(gate).not.toContain("Pay $");
    expect(gate).toContain("Confirm all three above to continue");
  });

  it("ships every checkbox unticked", () => {
    expect(gate).not.toContain('checked=""');
    expect(gate.match(/type="checkbox"/g)?.length).toBe(3);
  });

  it("names the three things a person would say they were not told", () => {
    expect(gate).toContain("not a physical inspection");
    expect(gate).toContain("brakes, airbags, frame and steering cannot be assessed");
    expect(gate).toContain("independent mechanic examine any vehicle");
  });

  it("states what has been measured before what is being sold", () => {
    expect(gate.indexOf("What has actually been measured")).toBeLessThan(
      gate.indexOf("What you get"),
    );
  });

  it("carries the banner even on the checkout page", () => {
    expect(gate).toContain(demoTeaser.banner);
  });
});
