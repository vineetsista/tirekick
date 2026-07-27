import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import Home from "@/app/page";
import { demoReport, demoTeaser } from "@/lib/report";

/**
 * A copy audit of the public page, against the product it is describing.
 *
 * This suite exists because the P0 landing page promised "the open recalls on
 * that VIN" and went on promising it through all of P1, during which the report
 * itself acquired three separate caveats explaining that we cannot know any such
 * thing. It also advertised walkaround video analysis, which has never existed.
 *
 * Nothing failed. Marketing copy drifts out of sync with the product silently and
 * always in the same direction, because no test looks at it. These do.
 */

const html = renderToStaticMarkup(<Home />);
const text = html
  .replace(/&#x27;|&rsquo;/g, "'")
  .replace(/&quot;/g, '"')
  .replace(/&amp;/g, "&")
  .replace(/<[^>]+>/g, " ")
  .replace(/\s+/g, " ");

describe("the landing page does not claim what the report refuses to", () => {
  it("never promises per-VIN recall status", () => {
    // D-016. NHTSA publishes recalls per model and nothing per vehicle.
    expect(text).not.toMatch(/recalls on (that|this|your) VIN/i);
    expect(text).not.toMatch(/open recalls on/i);
    expect(text).toContain("recall campaigns on record for that model year");
  });

  it("says out loud that recall status per car is unknowable here", () => {
    expect(text).toContain("Tell you whether a recall was done on your car");
    expect(text).toContain("publishes nothing about individual vehicles");
  });

  it("never promises a title search", () => {
    expect(text).toContain("queries no title registry");
    expect(text).not.toMatch(/title check|title search|verify the title/i);
  });

  it("never promises an audio diagnosis", () => {
    // P3 built a working detector and ships zero claims from it.
    expect(text).toContain("does not say what made them");
    for (const word of ["knock", "misfire", "diagnose the fault", "engine health"]) {
      expect(text.toLowerCase()).not.toContain(word.toLowerCase());
    }
  });

  it("does not advertise features that do not exist", () => {
    // Walkaround video was on the P0 page and has never been built.
    expect(text).not.toMatch(/walkaround video|video analysis/i);
  });

  it("never says the report can clear a car", () => {
    expect(text).toContain("There is no pass");
    for (const phrase of [
      "peace of mind",
      "buy with confidence",
      "know it's safe",
      "verified",
      "certified",
    ]) {
      expect(text.toLowerCase()).not.toContain(phrase.toLowerCase());
    }
  });
});

describe("the landing page carries the honesty architecture", () => {
  it("states what it is not, above the fold", () => {
    expect(text).toContain(demoReport.banner);
    expect(text.indexOf(demoReport.banner)).toBeLessThan(text.indexOf("See a free result"));
  });

  it("states the accuracy position before any call to action", () => {
    // LAW 6. The version of this page that buries it is the version that
    // eventually stops saying it.
    expect(text).toContain(demoTeaser.accuracyStatement);
    expect(text.indexOf(demoTeaser.accuracyStatement)).toBeLessThan(
      text.indexOf("See a free result"),
    );
  });

  it("names the four locked systems on the front page", () => {
    for (const system of ["Brakes", "airbags", "frame", "steering"]) {
      expect(text).toContain(system);
    }
    expect(text).toContain("locked off in software");
  });

  it("links the accuracy page", () => {
    expect(html).toContain('href="/accuracy"');
  });

  it("declares that the sample is built on synthetic media", () => {
    expect(text).toContain("synthetic fixture media");
    // ...and is precise about the half of it that is real.
    expect(text).toContain("except the vehicle record, which is real federal data");
  });
});

describe("the disclaimer architecture matches LIABILITY section 4", () => {
  /**
   * That table names seven placements. Six phases shipped with two of them -
   * the share page and the print footer - specified and unbuilt, which is the
   * same drift P6 found on the landing page, sitting in the liability document.
   */
  const liability = readFileSync(
    resolve(process.cwd(), "../../docs/LIABILITY.md"),
    "utf8",
  );

  it("still specifies a share surface, and one exists", () => {
    expect(liability).toContain("Share page / public link");
    expect(existsSync(resolve(process.cwd(), "src/app/share/demo-01/page.tsx"))).toBe(true);
  });

  it("still specifies a PDF/print footer, and one exists", () => {
    expect(liability).toContain("PDF export");
    const css = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8");
    expect(css).toContain("@media print");
    // "Running footer" means every page, which is what position:fixed buys.
    expect(css).toMatch(/body::after[\s\S]*position:\s*fixed/);
    expect(css).toContain("Not an inspection");
  });

  it("keeps the watermark off the printed page", () => {
    // On screen it is behind the evidence at 6% opacity. On paper it would be
    // ink across a photograph somebody is trying to read.
    const css = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8");
    expect(css).toMatch(/@media print[\s\S]*\.share-watermark[\s\S]*display:\s*none/);
  });
});
