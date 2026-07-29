import { readdirSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Prose keeps its measure.
 *
 * ---------------------------------------------------------------------------
 * WHAT WAS WRONG
 * ---------------------------------------------------------------------------
 *
 * The content column is 1240px and prose was set across all of it. Measured on
 * the built page at 1440px, body copy ran to 150-159 characters a line. Reading
 * research puts comfortable measure at 45-75 characters and treats about 90 as
 * the point where the eye stops reliably finding the start of the next line.
 *
 * The two worst blocks were the `could not assess` list at 152 characters and a
 * mechanic referral at 134 - the most consequential sentences this product
 * produces, set at the width hardest to read them at. Nothing failed, because
 * legibility is not a thing a markup assertion can see.
 *
 * ---------------------------------------------------------------------------
 * THE td TRAP
 * ---------------------------------------------------------------------------
 *
 * The first fix put `max-width` on `.prose-sm` and left `className="prose-sm"`
 * on two `<td>` elements. `max-width` on a table cell is a *hint* the automatic
 * table layout algorithm may ignore, and it did: those columns kept setting
 * 102- and 124-character lines while the stylesheet said 64ch. The measure has
 * to sit on a block inside the cell.
 *
 * So this checks the two things that actually broke, statically, with no browser
 * needed: the cap is declared, and no prose class sits directly on a `<td>`
 * where the cap would be quietly discarded.
 */

const here = dirname(fileURLToPath(import.meta.url));
const srcRoot = resolve(here, "..");
const css = readFileSync(join(srcRoot, "app", "globals.css"), "utf8");

/** Body of a top-level rule, e.g. `.prose { ... }`. */
function ruleBody(selector: string): string {
  const re = new RegExp(`\\${selector}\\s*\\{([^}]*)\\}`);
  return re.exec(css)?.[1] ?? "";
}

function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (entry === "generated" || entry === "__snapshots__") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...sourceFiles(full));
    else if (/\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry)) out.push(full);
  }
  return out;
}

describe("prose measure", () => {
  for (const selector of [".prose", ".prose-sm"]) {
    it(`${selector} caps its line length in ch`, () => {
      const body = ruleBody(selector);
      expect(body, `${selector} rule not found`).not.toEqual("");

      const match = /max-width:\s*(\d+(?:\.\d+)?)ch/.exec(body);
      expect(match, `${selector} declares no max-width in ch`).not.toBeNull();

      const ch = Number(match![1]);
      // `ch` is the width of a "0", wider than the average glyph in a
      // proportional serif, so 62ch measures out around 72-78 real characters.
      // Anything past 75ch is past 90 real characters on the page.
      expect(ch).toBeGreaterThanOrEqual(40);
      expect(ch).toBeLessThanOrEqual(75);
    });
  }

  it("never puts a prose class directly on a table cell", () => {
    const offenders: string[] = [];
    for (const file of sourceFiles(srcRoot)) {
      const source = readFileSync(file, "utf8");
      // <td ... className="... prose ..."> - the cap would be advisory there.
      for (const m of source.matchAll(/<td[^>]*className=\{?"([^"]*)"/g)) {
        const classes = m[1] ?? "";
        if (/\bprose(-sm)?\b/.test(classes)) {
          offenders.push(`${relative(srcRoot, file)}: <td class="${classes}">`);
        }
      }
    }
    expect(
      offenders,
      "max-width on a <td> is a hint the table layout may ignore - " +
        "put the prose class on a block inside the cell instead",
    ).toEqual([]);
  });
});
