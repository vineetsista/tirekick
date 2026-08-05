import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";
import { PRICE_USD as SHARED_PRICE_USD } from "@tirekick/shared";
import Home from "@/app/page";
import { PurchaseGate } from "@/components/PurchaseGate";
import { PRICE_USD, checkoutState, paymentLink } from "@/lib/checkout";
import { demoReport, demoTeaser, headlineFinding } from "@/lib/report";

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

  it("describes the walkaround as the frame selection it is", () => {
    /**
     * This assertion used to be `expect(text).not.toMatch(/walkaround video/i)`,
     * because in P6 the page advertised a feature that did not exist.
     *
     * P7 built it. The ban then became the P6 failure inverted: a guard
     * suppressing a true claim, holding the page a phase behind the product in
     * the safe direction. Both directions are drift.
     *
     * So the rule is not "never mention video", it is "never imply the video was
     * watched". A walkaround is sampled - sharpest frame per bucket, duplicates
     * and blurs discarded, capped at twelve - and the page has to say so.
     */
    expect(text).toContain("It samples frames");
    expect(text).toContain("how many it dropped and why");
    expect(text).not.toMatch(/watches the (whole )?video|full video analysis/i);
  });

  it("does not advertise features that do not exist", () => {
    for (const phrase of [
      "title search",
      "market value guarantee",
      "vehicle history report",
      "accident history",
      "service records",
    ]) {
      expect(text.toLowerCase()).not.toContain(phrase);
    }
  });

  it("shows the buyer an actual finding rather than describing one", () => {
    /**
     * The page rendered zero images for seven phases while selling "each finding
     * boxed on the photograph it came from". Worse than a design flaw: it asked a
     * stranger to take a visual evidence product entirely on faith.
     *
     * The hero renders headlineFinding(demoReport) through the same component the
     * paid report uses, so the page cannot show a finding the engine did not
     * produce - which also makes copy drift structurally harder than the wording
     * assertions above can manage on their own.
     */
    const finding = headlineFinding(demoReport);
    expect(finding, "the fixture has no image-evidenced finding to show").not.toBeNull();
    expect(text).toContain(finding!.title);
    expect(text).toContain(finding!.confidenceBasis);
    expect(html).toContain(`/f/${demoReport.inspectionId}/`);
  });

  it("says the hero is real output and not a mock-up", () => {
    expect(text).toContain("That is not a mock-up");
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

describe("the landing page says what it costs", () => {
  /**
   * For nine phases the number appeared for the first time on the checkout page,
   * after the free teaser, under three acknowledgement checkboxes. A stranger
   * could read every word of the landing page and not learn the price of the
   * thing it was selling.
   *
   * That is the ordinary pattern for a paid product and it is not available to
   * this one. The page's entire argument is that TIREKICK tells you the
   * uncomfortable part before you are committed rather than after; a page that
   * withholds its own price while making that argument is refuting itself.
   */
  it("states the price", () => {
    expect(text).toContain(`$${PRICE_USD}`);
  });

  it("states it before the first call to action, not after", () => {
    const at = text.indexOf(`$${PRICE_USD}`);
    // Without this line the comparison passes on a page with no price at all:
    // indexOf returns -1, which is dutifully less than everything.
    expect(at, "the price is nowhere on the page").toBeGreaterThan(-1);
    expect(at).toBeLessThan(text.indexOf("See a free result"));
  });

  it("says what the money buys, including the case where it buys bad news", () => {
    expect(text).toContain("No subscription");
    // The refund-request sentence, said in advance. A buyer who pays and is told
    // nothing was visible has received the product, and should know that first.
    expect(text).toContain("nothing adverse is visible in your photographs");
  });

  it("reads the number from checkout rather than retyping it into copy", () => {
    /**
     * A price typed into prose is a price that stays behind when the real one
     * moves, on the surface that is read most often and checked least. Comments
     * are stripped first: discussing the number in a docstring is not quoting it
     * at a buyer, and the ban has to be on the copy or it will be worked around.
     */
    const source = readFileSync(resolve(process.cwd(), "src/app/page.tsx"), "utf8")
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/\/\/.*$/gm, "");
    expect(source).toContain("PRICE_USD");
    expect(source, "the landing page hardcodes a price").not.toMatch(/\$\d/);
  });
});

describe("one price, one source, and the number nothing here can check", () => {
  /**
   * The price existed three times and nothing compared any two of them:
   * `checkout.ts` for the landing page, `cli.py --price` for the teaser the
   * engine writes, `test_teaser.py` for the tests. The landing page printed the
   * TypeScript one and the teaser one click later printed the Python one.
   *
   * Above, `reads the number from checkout rather than retyping it into copy`
   * banned a fourth copy in landing-page prose and stopped there, so the
   * checkout page - the surface where the number is read hardest - was never
   * scanned at all. These assertions are in the copy suite because the price is
   * copy, and because a price is exactly the kind of claim this file exists to
   * hold to the product.
   *
   * The part that cannot be asserted from here is the charge. Stripe holds the
   * amount, on a payment link configured outside this repository, and no test in
   * this repository can read it. What follows checks the two things that are
   * checkable: that every surface prints one number, and that the app refuses to
   * offer a pay button unless the deployment declares which amount it configured
   * over there. A declaration is not the charge, and nothing checks the charge.
   */
  const read = (relative: string): string =>
    readFileSync(resolve(process.cwd(), relative), "utf8");
  const withoutComments = (source: string): string =>
    source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

  const linkKey = "NEXT_PUBLIC_STRIPE_PAYMENT_LINK";
  const amountKey = "NEXT_PUBLIC_STRIPE_PRICE_USD";
  const link = "https://buy.stripe.com/test_abc123";

  afterEach(() => {
    delete process.env[linkKey];
    delete process.env[amountKey];
  });

  it("prints one number on the landing page, the checkout page and the teaser", () => {
    expect(PRICE_USD).toBe(SHARED_PRICE_USD);
    // The teaser is written by Python. If the engine's price ever stops being
    // the shared constant, the number a buyer meets between these two pages
    // changes and this fails on the artifact rather than on a description of it.
    expect(demoTeaser.priceUsd).toBe(SHARED_PRICE_USD);
    // ...and the two pages render it, rather than merely importing it.
    expect(text).toContain(`$${SHARED_PRICE_USD} a car, once`);
    const gate = renderToStaticMarkup(<PurchaseGate teaser={demoTeaser} />);
    expect(gate).toContain(`Full report, $${SHARED_PRICE_USD}.`);
  });

  it("keeps checkout.ts from declaring a price of its own", () => {
    const source = withoutComments(read("src/lib/checkout.ts"));
    expect(source).toContain("@tirekick/shared");
    expect(source, "checkout.ts writes its own price literal").not.toMatch(
      /PRICE_USD\s*=\s*[0-9]/,
    );
  });

  it("keeps the checkout page from typing the price into copy", () => {
    const source = withoutComments(read("src/components/PurchaseGate.tsx"));
    expect(source).toContain("PRICE_USD");
    expect(source, "the checkout page hardcodes a price").not.toMatch(/\$\d/);
  });

  it("sends Stripe no amount, which is why nothing here can claim the charge", () => {
    /**
     * The landing page comment used to say the number "comes from checkout.ts,
     * which is what actually charges it". This is the fact that made that false:
     * the only thing the app puts on the URL is the reference the webhook needs.
     * Changing the constant moves every displayed price and moves nothing at
     * Stripe.
     */
    process.env[linkKey] = link;
    const href = paymentLink("insp_1");
    expect(href).not.toBeNull();
    const url = new URL(href!);
    expect([...url.searchParams.keys()]).toEqual(["client_reference_id"]);
    expect(url.searchParams.get("client_reference_id")).toBe("insp_1");
    expect(url.toString()).not.toContain(String(PRICE_USD));
  });

  it("offers nothing to pay when no payment link is configured", () => {
    expect(checkoutState("insp_1")).toEqual({ kind: "no_link" });
  });

  it("refuses a pay button when the deployment declares no amount", () => {
    // A link with no declared amount is the state that shipped: a button that
    // charges whatever Stripe happens to hold, beside a number chosen here.
    process.env[linkKey] = link;
    expect(checkoutState("insp_1")).toEqual({ kind: "amount_undeclared" });
  });

  it("refuses a pay button when the declared amount is not the displayed one", () => {
    process.env[linkKey] = link;
    process.env[amountKey] = String(PRICE_USD + 5);
    expect(checkoutState("insp_1")).toEqual({
      kind: "amount_disagrees",
      declared: String(PRICE_USD + 5),
    });
  });

  it("refuses a pay button when the declared amount is not a number at all", () => {
    process.env[linkKey] = link;
    process.env[amountKey] = "twenty five";
    expect(checkoutState("insp_1")).toEqual({
      kind: "amount_disagrees",
      declared: "twenty five",
    });
  });

  it("opens only when the declared amount and the displayed price agree", () => {
    process.env[linkKey] = link;
    process.env[amountKey] = String(PRICE_USD);
    const state = checkoutState("insp_1");
    expect(state.kind).toBe("ready");
    expect(state.kind === "ready" && state.href).toContain("client_reference_id=insp_1");
  });

  it("tells the buyer the payment page holds the real amount", () => {
    /**
     * This sentence sits beside the pay button, which only exists after three
     * checkboxes are ticked - a React state transition, and this suite renders
     * to static markup with no DOM to tick in. So the wording is asserted on the
     * source and nothing here proves it reaches a screen. The states below,
     * which are the ones that withhold the button, are asserted on real markup.
     */
    const source = read("src/components/PurchaseGate.tsx");
    expect(source).toContain("Stripe holds the amount it charges");
    expect(source).toContain("close it without paying");
  });

  it("says on the page that the amount was never declared, and links nothing", () => {
    process.env[linkKey] = link;
    const gate = renderToStaticMarkup(<PurchaseGate teaser={demoTeaser} />);
    expect(gate).toContain("has not declared the amount");
    expect(gate, "a payment href on a build that cannot state its price").not.toContain(
      link,
    );
  });

  it("says on the page when the deployment's two numbers disagree", () => {
    process.env[linkKey] = link;
    process.env[amountKey] = String(PRICE_USD + 5);
    const gate = renderToStaticMarkup(<PurchaseGate teaser={demoTeaser} />);
    expect(gate).toContain("this build disagrees with itself");
    expect(gate).toContain(`<code>${PRICE_USD + 5}</code>`);
    expect(gate, "a payment href beside a price the build contradicts").not.toContain(
      link,
    );
  });

  it("shows no configuration notice at all once the two numbers agree", () => {
    process.env[linkKey] = link;
    process.env[amountKey] = String(PRICE_USD);
    const gate = renderToStaticMarkup(<PurchaseGate teaser={demoTeaser} />);
    expect(gate).not.toContain("Payment is not connected yet");
    expect(gate).not.toContain("disagrees with itself");
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
    expect(css).toContain("This is not an inspection");
  });

  it("keeps the watermark off the printed page", () => {
    // On screen it is behind the evidence at 6% opacity. On paper it would be
    // ink across a photograph somebody is trying to read.
    const css = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8");
    expect(css).toMatch(/@media print[\s\S]*\.share-watermark[\s\S]*display:\s*none/);
  });
});
