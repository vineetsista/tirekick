import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { WORDMARK_TRACKING, WORDMARK_WEIGHT } from "./Wordmark";

/**
 * The wordmark is defined once, and docs/BRAND.md describes that one definition.
 *
 * BRAND.md recorded this drift rather than correcting it, and said why: "a
 * wordmark defined in two places will drift again the moment a third appears."
 * It was right, and it undercounted. By P11 the mark was set at six sites in
 * three tracking values and two weights, while the document still described the
 * drift as two sites disagreeing.
 *
 * D-049 is the rule that applies: a duplicated definition ships with the test
 * that compares the copies. The better answer available here was to delete the
 * copies, so these tests guard the deletion - one that nothing may render this
 * word except `Wordmark.tsx`, and one that the two numbers BRAND.md publishes
 * are the two numbers the component uses.
 */

const srcRoot = resolve(__dirname, "..");

function tsxFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) {
      if (entry === "__snapshots__" || entry === "generated") continue;
      out.push(...tsxFiles(path));
      continue;
    }
    if (entry.endsWith(".tsx")) out.push(path);
  }
  return out;
}

describe("the wordmark has one definition", () => {
  /**
   * A JSX text node that is exactly the word, which is what drawing the mark
   * looks like. Prose mentioning the product ("You give TIREKICK the photos")
   * is not a wordmark and is deliberately not matched - it has text on both
   * sides of it, so it never sits alone between two tags.
   */
  const RENDERED = />\s*TIREKICK\s*</;

  it("is rendered by no component except Wordmark.tsx", () => {
    const offenders = tsxFiles(srcRoot)
      .filter((path) => !path.endsWith("Wordmark.tsx") && !path.endsWith(".test.tsx"))
      .filter((path) => RENDERED.test(readFileSync(path, "utf8")))
      .map((path) => path.slice(srcRoot.length + 1));

    expect(offenders).toEqual([]);
  });

  /**
   * The six sites this replaced each set `letterSpacing` inline beside the
   * word. Catching the styling as well as the text means a copy that renders
   * the mark through a variable - and so slips past the check above - still has
   * to explain why it is hand-setting the two properties BRAND.md specifies.
   */
  it("is styled by no component except Wordmark.tsx", () => {
    const offenders = tsxFiles(srcRoot)
      .filter((path) => !path.endsWith("Wordmark.tsx") && !path.endsWith(".test.tsx"))
      .filter((path) => {
        const source = readFileSync(path, "utf8");
        return source.includes("TIREKICK") && /letterSpacing:\s*"0\.2[0-9]em"/.test(source);
      })
      .map((path) => path.slice(srcRoot.length + 1));

    expect(offenders).toEqual([]);
  });
});

describe("docs/BRAND.md describes the wordmark that exists", () => {
  const brand = readFileSync(resolve(srcRoot, "../../../docs/BRAND.md"), "utf8");

  /**
   * Parsed out of the sentence that specifies it, so the document cannot say
   * 800/0.22em while the component says something else. This is the same
   * treatment the colour table got in P8 and for the same reason: a
   * specification nothing compares to the build is a souvenir.
   */
  const specified = /(\d{3})\s*weight,\s*([\d.]+em)\s*tracking/.exec(brand);

  it("states a weight and a tracking figure at all", () => {
    expect(specified).not.toBeNull();
  });

  it("states the ones the component uses", () => {
    expect(Number(specified?.[1])).toBe(WORDMARK_WEIGHT);
    expect(specified?.[2]).toBe(WORDMARK_TRACKING);
  });
});
