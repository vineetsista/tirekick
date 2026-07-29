import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { chromium, type Browser, type Page } from "playwright";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createElement } from "react";
import { ReportView } from "@/components/ReportView";
import { TeaserView } from "@/components/TeaserView";
import Home from "@/app/page";
import { demoReport, demoTeaser } from "@/lib/report";
import { stressReports, stressTeasers } from "@/lib/stress";

/**
 * The gate that opens a browser.
 *
 * ---------------------------------------------------------------------------
 * WHY THIS EXISTS
 * ---------------------------------------------------------------------------
 *
 * P8 found eight defects. Six of them were invisible to a suite of 444 tests and
 * obvious within a minute of loading the built page:
 *
 *   - the pay button rendered near-black on nothing, on the checkout page
 *   - three layouts overflowed the viewport on a phone
 *   - a recall title pushed its heading 40px past the panel at 320px
 *   - prose ran to 159 characters a line
 *
 * None of that is visible to a markup assertion. `renderToStaticMarkup` produces
 * a string; a string has no width, no cascade and no computed colour. The
 * existing tests check that the right elements exist in the right order, which is
 * necessary and is not the same as checking that a person can read the result.
 *
 * Each of those six got a static test in the same phase, and those tests are
 * real - but every one of them is the shape of a bug that already happened. This
 * is the general check: render the actual components, apply the actual
 * stylesheet, lay it out in a real engine at real widths, and measure.
 *
 * ---------------------------------------------------------------------------
 * WHY NO SERVER AND NO BUILD
 * ---------------------------------------------------------------------------
 *
 * The page is assembled here rather than fetched from `next start`. A gate that
 * needs a production build and a listening port is a gate that is slow enough to
 * be skipped and flaky enough to be disabled, and neither the build nor the
 * server is what is under test - the components and the stylesheet are.
 *
 * Media and fonts are served straight off disk through a route handler, so
 * images have their real intrinsic dimensions and text is laid out in the real
 * faces. Without that, every `<img>` would measure zero and the overflow numbers
 * would be fiction.
 *
 * Requires chromium: `pnpm --filter web exec playwright install chromium`.
 * It fails loudly rather than skipping if the browser is absent - a gate that
 * quietly passes when it did not run is the thing this project keeps finding.
 */

const here = dirname(fileURLToPath(import.meta.url));
const srcRoot = resolve(here, "..");
const publicDir = resolve(srcRoot, "../public");
const css = readFileSync(join(srcRoot, "app", "globals.css"), "utf8");

/** Widths that matter: small phone, common phone, tablet, laptop. */
const WIDTHS = [320, 390, 768, 1440];

/**
 * Comfortable measure is 45-75 characters; past about 90 the eye stops reliably
 * finding the start of the next line. Measured here as real characters over real
 * line boxes rather than estimated from a `ch` value.
 */
const MAX_CHARS_PER_LINE = 92;

/** WCAG 2.1 AA. Large text is >=24px, or >=18.66px at weight >=700. */
const AA_NORMAL = 4.5;
const AA_LARGE = 3.0;

/**
 * The pages, plus the same components fed reports designed to break them.
 *
 * The checks below are general; for one commit the input was not. Everything ran
 * against `demo-01` - eight findings, short titles, every optional section
 * populated - which is the one report guaranteed not to surprise the layout,
 * because the layout was built while looking at it.
 *
 * `stress.ts` derives forty-finding reports, 900-character details, federal
 * component strings with no break opportunity in them, an empty-handed report
 * with no findings at all, assets whose dimensions could not be read, and
 * seven-figure prices - each passed back through `parseReport`, so every one is
 * something the pipeline could legally emit rather than arbitrary JSON.
 */
const PAGES: [string, string][] = [
  ["report", renderToStaticMarkup(createElement(ReportView, { report: demoReport }))],
  ["teaser", renderToStaticMarkup(createElement(TeaserView, { teaser: demoTeaser }))],
  ["landing", renderToStaticMarkup(createElement(Home))],
  ...stressReports(demoReport).map(
    (c): [string, string] => [
      `report/${c.name}`,
      renderToStaticMarkup(createElement(ReportView, { report: c.value })),
    ],
  ),
  ...stressTeasers(demoTeaser).map(
    (c): [string, string] => [
      `teaser/${c.name}`,
      renderToStaticMarkup(createElement(TeaserView, { teaser: c.value })),
    ],
  ),
  // The checkout page's pay button only exists after three checkboxes are ticked
  // and Stripe is configured, so it never appears in static markup. Its styling
  // is a class for exactly that reason; this puts the class on a page so the
  // contrast pass below covers the one button in the product that takes money.
  ["primary-action", `<div class="wrap" style="padding:40px">
     <a class="btn btn-primary" href="#">Pay $25 and open the report</a>
   </div>`],
];

let browser: Browser;
let page: Page;

beforeAll(async () => {
  try {
    browser = await chromium.launch({ args: ["--no-sandbox"] });
  } catch (cause) {
    // Deliberately fatal rather than skipped. A layout gate that goes green
    // because no browser was installed is worse than no layout gate: it reports
    // that the pages were checked when nothing looked at them.
    throw new Error(
      "The layout gate needs chromium and could not launch it.\n" +
        "  pnpm --filter web exec playwright install chromium\n" +
        "This test does not skip - see D-050.",
      { cause },
    );
  }
  page = await browser.newPage();

  // Serve /f/** and /fonts/** off disk so images and faces are real.
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.protocol === "data:") return route.continue();
    const file = join(publicDir, url.pathname);
    if (url.pathname.startsWith("/f/") || url.pathname.startsWith("/fonts/")) {
      try {
        return await route.fulfill({ body: readFileSync(file) });
      } catch {
        return route.abort();
      }
    }
    return route.fulfill({ status: 204, body: "" });
  });
}, 120_000);

afterAll(async () => {
  await browser?.close();
});

async function load(html: string, width: number) {
  await page.setViewportSize({ width, height: 900 });
  await page.setContent(
    `<!doctype html><html><head><meta charset="utf-8">
     <style>${css}</style></head><body>${html}</body></html>`,
    { waitUntil: "load" },
  );
  await page.evaluate(() => document.fonts.ready);
}

describe("laid out in a real browser", () => {
  describe.each(PAGES)("%s", (name, html) => {
    it.each(WIDTHS)(`fits the viewport at %ipx`, async (width) => {
      await load(html, width);

      const overflow = await page.evaluate(() => {
        const de = document.documentElement;
        const over = de.scrollWidth - de.clientWidth;
        if (over <= 1) return { over: 0, culprits: [] as string[] };

        // Report the elements whose own content overflows, ignoring anything
        // inside a clipping ancestor - a crop image is 1300px wide on purpose.
        const culprits: string[] = [];
        for (const el of Array.from(document.querySelectorAll("*"))) {
          if (getComputedStyle(el).overflowX !== "visible") continue;
          if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) {
            culprits.push(
              `${el.tagName}.${String(el.className).slice(0, 30)} ` +
                `content=${el.scrollWidth} box=${el.clientWidth} ` +
                `"${(el.textContent ?? "").trim().slice(0, 40)}"`,
            );
          }
        }
        return { over, culprits: culprits.slice(0, 5) };
      });

      expect(
        overflow.over,
        `${name} overflows by ${overflow.over}px at ${width}px:\n  ` +
          overflow.culprits.join("\n  "),
      ).toBe(0);
    });

    it("keeps prose to a readable measure at 1440px", async () => {
      await load(html, 1440);

      const wide = await page.evaluate((limit) => {
        const bad: string[] = [];
        for (const el of Array.from(document.querySelectorAll("p, li, h1, h2, h3"))) {
          const text = (el.textContent ?? "").trim();
          if (text.length < 120) continue;

          // Real line boxes, from the layout engine. Characters per line is the
          // text length over the number of rects the range actually occupies.
          const range = document.createRange();
          range.selectNodeContents(el);
          const lines = range.getClientRects().length;
          if (lines === 0) continue;
          const cpl = text.length / lines;
          if (cpl > limit) {
            bad.push(`${el.tagName} ${Math.round(cpl)}cpl "${text.slice(0, 44)}"`);
          }
        }
        return bad.slice(0, 6);
      }, MAX_CHARS_PER_LINE);

      expect(wide, `${name} sets prose past ${MAX_CHARS_PER_LINE} characters a line`).toEqual([]);
    });

    it("renders every piece of text at AA contrast", async () => {
      await load(html, 1440);

      const failures = await page.evaluate(
        ({ normal, large }) => {
          const parse = (c: string): [number, number, number, number] => {
            const n = c.match(/[\d.]+/g)?.map(Number) ?? [0, 0, 0, 0];
            return [n[0] ?? 0, n[1] ?? 0, n[2] ?? 0, n[3] ?? 1];
          };
          const lin = (v: number) => {
            const s = v / 255;
            return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
          };
          const lum = ([r, g, b]: number[]) =>
            0.2126 * lin(r ?? 0) + 0.7152 * lin(g ?? 0) + 0.0722 * lin(b ?? 0);
          const ratio = (a: number[], b: number[]) => {
            const [la, lb] = [lum(a), lum(b)];
            return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
          };

          /** First opaque background up the tree - what the text actually sits on. */
          const backdrop = (el: Element): number[] => {
            let node: Element | null = el;
            while (node) {
              const cs = getComputedStyle(node);
              const [r, g, b, a] = parse(cs.backgroundColor);
              if (a === 1) return [r, g, b];
              node = node.parentElement;
            }
            return [11, 10, 9];
          };

          const bad: string[] = [];
          for (const el of Array.from(document.querySelectorAll("*"))) {
            // Only elements holding their own visible text.
            const own = Array.from(el.childNodes)
              .filter((n) => n.nodeType === 3)
              .map((n) => n.textContent ?? "")
              .join("")
              .trim();
            if (own.length < 4) continue;

            const cs = getComputedStyle(el);
            if (cs.visibility === "hidden" || cs.display === "none") continue;
            if (parseFloat(cs.opacity) < 0.95) continue;
            const rect = el.getBoundingClientRect();
            if (rect.width < 2 || rect.height < 2) continue;
            // Text over a picture is not measurable this way; those carry their
            // own scrim and are asserted by eye, not here.
            if (getComputedStyle(el).backgroundImage !== "none") continue;

            const size = parseFloat(cs.fontSize);
            const weight = Number(cs.fontWeight) || 400;
            const isLarge = size >= 24 || (size >= 18.66 && weight >= 700);
            const need = isLarge ? large : normal;

            const fg = parse(cs.color);
            const r = ratio([fg[0], fg[1], fg[2]], backdrop(el));
            if (r < need) {
              bad.push(
                `${el.tagName}.${String(el.className).slice(0, 24)} ` +
                  `${r.toFixed(2)}:1 (needs ${need}) ${Math.round(size)}px ` +
                  `"${own.slice(0, 34)}"`,
              );
            }
          }
          return bad.slice(0, 8);
        },
        { normal: AA_NORMAL, large: AA_LARGE },
      );

      expect(failures, `${name} has text below WCAG AA`).toEqual([]);
    });
  });

  it("gives the primary action a real hit target", async () => {
    // 44x44 is the WCAG 2.5.5 target size. A button that takes money should not
    // be the thing a buyer has to aim at.
    // By name. Looking it up by index broke the moment stress pages were
    // inserted ahead of it, and the test went red pointing at the wrong page.
    const primary = PAGES.find(([name]) => name === "primary-action");
    expect(primary, "the primary-action harness page is missing").toBeDefined();
    await load(primary![1], 390);
    const box = await page.locator(".btn-primary").boundingBox();
    expect(box).not.toBeNull();
    expect(box!.height).toBeGreaterThanOrEqual(44);
    expect(box!.width).toBeGreaterThanOrEqual(44);
  });
});
