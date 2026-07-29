import { readdirSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Every design token a component asks for exists.
 *
 * ---------------------------------------------------------------------------
 * THE BUG THIS WAS WRITTEN FOR
 * ---------------------------------------------------------------------------
 *
 * The redesign removed `--tk-accent` on the grounds that the product has no
 * brand hue - severity is the only chroma on the page. `globals.css` even says
 * so, in a comment, in the place the token used to be. Four call sites kept
 * asking for it, and the loudest was this:
 *
 *     background: "var(--tk-accent)",   // undefined -> transparent
 *     color: "#0a0c0e",                 // near-black, on a near-black page
 *
 * That is the pay button. An undefined custom property is not an error in CSS;
 * it is invalid at computed-value time, so the declaration is dropped and the
 * property takes its initial value. The button rendered as black text on
 * nothing, on the one page in the product where money changes hands, and every
 * gate stayed green: TypeScript does not read CSS, the snapshot recorded the
 * broken string as the expected string, and no test opens the checkout page.
 *
 * Three of the four call sites were in files the redesign never touched. That is
 * the general shape of it - deleting a token is a change to every file that
 * used it, and nothing connected the two halves.
 *
 * ---------------------------------------------------------------------------
 * WHAT IT CHECKS
 * ---------------------------------------------------------------------------
 *
 * Existence, not correctness. A component that asks for `--tk-sev-critical`
 * where it meant `--tk-sev-info` passes here and is wrong. This closes the gap
 * where a token resolves to nothing at all, which is the failure that silently
 * removes an element from the page rather than miscolouring it.
 */

const here = dirname(fileURLToPath(import.meta.url));
const srcRoot = resolve(here, "..");
const cssPath = join(srcRoot, "app", "globals.css");

const css = readFileSync(cssPath, "utf8");

/** Custom properties globals.css defines, anywhere in it. */
const defined = new Set<string>(
  [...css.matchAll(/(--[a-z0-9-]+)\s*:/gi)].flatMap((m) => (m[1] ? [m[1]] : [])),
);

/** Properties a component may set on itself and then read back. */
const LOCALLY_SCOPED = new Set<string>([]);

function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (entry === "generated" || entry === "__snapshots__") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...sourceFiles(full));
    } else if (/\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

describe("design tokens", () => {
  it("defines at least the tokens the design system is built on", () => {
    // Guards the guard: a regex that matched nothing would make every
    // assertion below vacuous, and the suite would go green on an empty file.
    for (const token of ["--tk-void", "--tk-paper", "--tk-sev-critical", "--s-4"]) {
      expect(defined.has(token), `${token} is not defined`).toBe(true);
    }
    expect(defined.size).toBeGreaterThan(20);
  });

  it("has no component asking for a token that does not exist", () => {
    const files = sourceFiles(srcRoot);
    expect(files.length).toBeGreaterThan(5);

    const dangling: string[] = [];
    for (const file of files) {
      const source = readFileSync(file, "utf8");
      for (const match of source.matchAll(/var\(\s*(--[a-z0-9-]+)/gi)) {
        const token = match[1];
        if (!token || defined.has(token) || LOCALLY_SCOPED.has(token)) continue;
        dangling.push(`${relative(srcRoot, file)}: ${token}`);
      }
    }
    expect(dangling).toEqual([]);
  });

  it("has no stylesheet rule asking for a token that does not exist", () => {
    const dangling: string[] = [];
    for (const match of css.matchAll(/var\(\s*(--[a-z0-9-]+)/gi)) {
      const token = match[1];
      if (token && !defined.has(token)) dangling.push(token);
    }
    expect(dangling).toEqual([]);
  });
});

/**
 * The colour table in docs/BRAND.md is the palette, or it is fiction.
 *
 * Through P7 that table named `--tk-bg: #0A0C0E`, `--tk-accent: #38E1B0` and an
 * `--tk-unknown` that had already been raised for contrast. Not one of the
 * fourteen values was still true, and one of them named a token the stylesheet
 * had deleted outright. The document read as a specification and functioned as a
 * souvenir.
 *
 * This is the fourth instance of the pattern the project keeps finding - LAWS.md,
 * LIABILITY.md, the landing page, and now BRAND.md - so it gets the same
 * treatment LAWS.md got: the document is parsed and checked against the build.
 * A designer changing a hex value in the stylesheet now has to change the table,
 * which is the entire point of writing the table down.
 */
describe("docs/BRAND.md describes the stylesheet that exists", () => {
  const brandPath = resolve(srcRoot, "../../../docs/BRAND.md");
  const brand = readFileSync(brandPath, "utf8");

  /**
   * The screen palette, scoped to the first `:root` block.
   *
   * `@media print` redefines nine of these to ink on white - the report is meant
   * to be handed to a mechanic on paper. Reading the whole file would compare the
   * documented screen colours against the print overrides and fail on every one
   * of them, which is what the first run of this test did.
   *
   * Literal hex only, so aliases like `--tk-bg: var(--tk-void)` are skipped.
   */
  function hexMap(source: string, pattern: RegExp): Map<string, string> {
    const out = new Map<string, string>();
    for (const m of source.matchAll(pattern)) {
      const [, token, value] = m;
      if (token && value) out.set(token, value.toLowerCase());
    }
    return out;
  }

  const rootStart = css.indexOf(":root");
  const rootBlock = css.slice(rootStart, css.indexOf("}", rootStart));
  const cssValues = hexMap(rootBlock, /(--[a-z0-9-]+)\s*:\s*(#[0-9a-f]{3,8})\s*;/gi);

  /** `| \`--tk-void\` | \`#0b0a09\` | page |` */
  const documented = hexMap(
    brand,
    /^\|\s*`(--[a-z0-9-]+)`\s*\|\s*`(#[0-9a-f]{3,8})`\s*\|/gim,
  );

  it("documents a table this test can actually read", () => {
    expect(documented.size).toBeGreaterThan(10);
  });

  it("names no token the stylesheet does not define", () => {
    const missing = [...documented.keys()].filter((t) => !cssValues.has(t));
    expect(missing).toEqual([]);
  });

  it("gives every documented token the value the stylesheet gives it", () => {
    const wrong: string[] = [];
    for (const [token, value] of documented) {
      const actual = cssValues.get(token);
      if (actual && actual !== value) wrong.push(`${token}: doc ${value} != css ${actual}`);
    }
    expect(wrong).toEqual([]);
  });

  it("documents every colour the meaning ramp is made of", () => {
    // The severity ramp and the two off-ramp states are the whole semantic
    // vocabulary. A new one arriving undocumented is how the table started
    // drifting in the first place.
    for (const token of cssValues.keys()) {
      if (!/^--tk-(sev-|locked$|unknown$)/.test(token)) continue;
      expect(documented.has(token), `${token} is not in the BRAND.md table`).toBe(true);
    }
  });
});
