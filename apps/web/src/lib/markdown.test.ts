import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { findingTypeSchema } from "@tirekick/shared";
import AccuracyPage from "@/app/accuracy/page";
import { ACCURACY_MD } from "@/generated/accuracy";
import {
  MarkdownError,
  parseInline,
  parseMarkdown,
  type Block,
  type Inline,
} from "@/lib/markdown";

/**
 * Three obligations, and the last two are the ones worth writing down.
 *
 * The first is that the parser reads docs/ACCURACY.md correctly. The second is
 * that it fails loudly on everything else - because the reason this parser exists
 * instead of a markdown library is that a permissive renderer would show a gate
 * table with a row silently missing. A test suite that only checked the happy path
 * would leave that property untested and therefore free to disappear.
 *
 * The third is that the AST reaches the page. A parser that reads all sixteen rows
 * and a page that renders fourteen of them is the same defect one layer further
 * on, and every assertion above it would stay green - so the last block in this
 * file renders the real component and counts the rows in the markup a buyer gets.
 */

const blocks = parseMarkdown(ACCURACY_MD);

const tables = blocks.filter((b): b is Extract<Block, { kind: "table" }> => b.kind === "table");

/**
 * The gate table, resolved once and loudly.
 *
 * A document that parsed with no table in it would make every assertion below
 * vacuous - `tables[0]?.rows` on nothing passes a lot of tests - so this stops
 * the whole file with the reason instead.
 */
const gate = tables[0];
if (!gate) throw new Error("docs/ACCURACY.md parsed with no table in it");

/**
 * `items[index]`, or a failure that says what was missing.
 *
 * `noUncheckedIndexedAccess` types every lookup below as `T | undefined` and the
 * one-character answer is `!`. A missing heading or a missing cell is precisely
 * the drift this file exists to catch, so it gets a sentence naming it rather
 * than a `TypeError` six frames away that somebody has to work backwards from.
 */
function at<T>(items: T[], index: number, what: string): T {
  const value = items[index];
  if (value === undefined) {
    throw new Error(`${what}: no index ${index} among ${items.length}`);
  }
  return value;
}

/** The plain text of an inline run, emphasis included. */
function flatten(content: Inline[]): string {
  return content
    .map((n) => (n.kind === "strong" || n.kind === "em" ? flatten(n.content) : n.text))
    .join("");
}

describe("the accuracy document parses", () => {
  it("parses without throwing, which is what the build depends on", () => {
    expect(blocks.length).toBeGreaterThan(20);
  });

  it("finds the document title as the only h1", () => {
    const h1 = blocks.filter(
      (b): b is Extract<Block, { kind: "heading" }> => b.kind === "heading" && b.level === 1,
    );
    expect(h1).toHaveLength(1);
    expect(flatten(at(h1, 0, "the document title").content)).toBe("TIREKICK ACCURACY");
  });

  it("finds the gate table with a row for every finding type", () => {
    expect(tables).toHaveLength(1);
    expect(flatten(at(gate.head, 0, "gate table header"))).toBe("Finding type");
    expect(flatten(at(gate.head, 4, "gate table header"))).toBe("In paid reports");
    expect(gate.rows).toHaveLength(findingTypeSchema.options.length);
  });

  it("keeps snake_case finding types intact", () => {
    /**
     * The specific corruption this parser is built to avoid. A renderer treating
     * `_` as emphasis turns odometer_wear_mismatch into odometer<em>wear</em>mismatch
     * and silently deletes two characters from the identifier column.
     */
    const names = gate.rows.map((row) => flatten(at(row, 0, "finding type cell")));
    expect(names).toContain("odometer_wear_mismatch");
    expect(names).toContain("exterior_damage");
    expect(names).toContain("documentation_gap");
    for (const row of gate.rows) {
      const name = at(row, 0, "finding type cell");
      expect(name).toHaveLength(1);
      expect(at(name, 0, "finding type node").kind).toBe("text");
    }
  });

  it("reads no finding type as sold, matching the registry", () => {
    // The same fact test_accuracy_doc.py pins on the Python side, asserted here
    // against the bytes the browser actually receives.
    for (const row of gate.rows) {
      expect(flatten(at(row, 4, "in-paid-reports cell"))).toBe("no");
    }
  });

  it("joins wrapped paragraphs into one block", () => {
    const paragraphs = blocks
      .filter((b): b is Extract<Block, { kind: "paragraph" }> => b.kind === "paragraph")
      .map((b) => flatten(b.content));
    expect(
      paragraphs.some((p) => p.includes("machinery to produce them has been finished")),
    ).toBe(true);
    // Wrapped at 88 columns in the source; a paragraph that stayed split would be
    // shorter than a single source line.
    expect(Math.max(...paragraphs.map((p) => p.length))).toBeGreaterThan(200);
  });

  it("joins wrapped bullets, including the recall bullet", () => {
    const lists = blocks.filter(
      (b): b is Extract<Block, { kind: "list" }> => b.kind === "list",
    );
    const items = lists.flatMap((l) => l.items.map(flatten));
    const recall = items.find((t) => t.startsWith("Whether a recall was actually performed"));
    expect(recall, "the recall bullet is the one LAW 6 leans on hardest").toBeDefined();
    expect(recall).toContain("recall work is free");
  });

  it("keeps the emphasis the document uses to carry its meaning", () => {
    const strongTexts = blocks
      .flatMap((b) =>
        b.kind === "paragraph" || b.kind === "heading"
          ? b.content
          : b.kind === "list"
            ? b.items.flat()
            : [],
      )
      .filter((n): n is Extract<Inline, { kind: "strong" }> => n.kind === "strong")
      .map((n) => flatten(n.content));
    expect(strongTexts.some((t) => t.includes("no accuracy numbers"))).toBe(true);
  });

  it("stays in step with the file on disk", () => {
    // apps/web/src/generated/accuracy.ts is written by sync-fixture-to-web.mjs.
    // If that copy ever goes stale, this page is publishing a different accuracy
    // position than the repository holds itself to.
    const onDisk = readFileSync(resolve(process.cwd(), "../../docs/ACCURACY.md"), "utf8");
    expect(ACCURACY_MD).toBe(onDisk);
  });
});

describe("the parser refuses what it cannot render", () => {
  const refusals: [string, string][] = [
    ["a link", "See [the protocol](https://example.com) for details."],
    ["an image", "![a car](/photo.jpg)"],
    ["a blockquote", "> quoted"],
    ["a fenced code block", "```\ncode\n```"],
    ["a numbered list", "1. first"],
    ["a nested list", "- top\n  - nested"],
    ["raw HTML", "text with <span>markup</span>"],
    ["an unterminated bold", "**never closed"],
    ["an unterminated code span", "a `code span that never closes"],
    ["a heading too deep to style", "#### too deep"],
  ];

  for (const [name, source] of refusals) {
    it(`throws on ${name}`, () => {
      expect(() => parseMarkdown(source)).toThrow(MarkdownError);
    });
  }

  it("names the line number, so the build failure is actionable", () => {
    expect(() => parseMarkdown("fine\n\nalso fine\n\n> quoted")).toThrow(/line 5/);
  });

  it("throws when a table row is short, rather than rendering a gap", () => {
    /**
     * The failure this whole design is for. A mistyped pipe in the gate table
     * drops a finding type off the published page, and a permissive renderer
     * shows the remaining rows as though the table were complete.
     */
    const table = ["| a | b | c |", "|---|---|---|", "| 1 | 2 | 3 |", "| 4 | 5 |"].join("\n");
    expect(() => parseMarkdown(table)).toThrow(/row has 2 cells, header has 3/);
  });

  it("throws when a table row is long", () => {
    const table = ["| a | b |", "|---|---|", "| 1 | 2 | 3 |"].join("\n");
    expect(() => parseMarkdown(table)).toThrow(/row has 3 cells, header has 2/);
  });

  it("throws when a table has no delimiter row", () => {
    expect(() => parseMarkdown("| a | b |\n| 1 | 2 |")).toThrow(/delimiter row/);
  });

  it("throws when a table has a header and no body", () => {
    expect(() => parseMarkdown("| a | b |\n|---|---|")).toThrow(/no rows/);
  });
});

describe("inline parsing", () => {
  it("prefers bold over italic so **x** is not an empty emphasis", () => {
    expect(parseInline("**x**", 1)).toEqual([
      { kind: "strong", content: [{ kind: "text", text: "x" }] },
    ]);
  });

  it("reads italic, bold and code in one run", () => {
    expect(parseInline("a *b* c **d** e `f`", 1)).toEqual([
      { kind: "text", text: "a " },
      { kind: "em", content: [{ kind: "text", text: "b" }] },
      { kind: "text", text: " c " },
      { kind: "strong", content: [{ kind: "text", text: "d" }] },
      { kind: "text", text: " e " },
      { kind: "code", text: "f" },
    ]);
  });

  it("reads a code span inside emphasis as code, not as two backticks", () => {
    /**
     * The document's last line is `*...reproducible from \`bench/\`.*`, and with
     * a flat emphasis node the page printed the backticks. Emphasis carries
     * nodes for exactly this line.
     */
    expect(parseInline("*from `bench/`.*", 1)).toEqual([
      {
        kind: "em",
        content: [
          { kind: "text", text: "from " },
          { kind: "code", text: "bench/" },
          { kind: "text", text: "." },
        ],
      },
    ]);
  });

  it("leaves underscores completely alone", () => {
    expect(parseInline("odometer_wear_mismatch", 1)).toEqual([
      { kind: "text", text: "odometer_wear_mismatch" },
    ]);
  });

  it("leaves a less-than sign in prose alone", () => {
    // registry.py emits `n too small (<50)` as a status, and that reaches a cell.
    expect(() => parseMarkdown("| a |\n|---|\n| n too small (<50) |")).not.toThrow();
  });

  it("does not read a multiplication-shaped asterisk as emphasis", () => {
    // `2 * 3 * 4` has no closing delimiter adjacent to a word, so it is text.
    expect(parseInline("a * b", 1)).toEqual([{ kind: "text", text: "a * b" }]);
  });

  /**
   * The flanking rule belongs to the delimiter RUN, not to one character.
   *
   * The first version of this fix looked at the character after the *first*
   * asterisk, which for `a ** b` is another asterisk - non-whitespace - so the
   * run was read as opening emphasis and the build died on a sentence that
   * contained `2 ** 8`. That is the same defect the rule was added to prevent,
   * one asterisk wider, and nothing here held it. So the cases are enumerated
   * by run length rather than described.
   */
  it.each([
    "a * b",
    "a ** b",
    "a *** b",
    "2 ** 8",
    "a footnote marker*",
    "cited above**",
  ])("reads %j as text, because the run opens nothing", (source) => {
    expect(parseInline(source, 1)).toEqual([{ kind: "text", text: source }]);
  });

  it("still throws on an asterisk run that opens emphasis and never closes it", () => {
    /**
     * The other side of the line the cases above draw, and the reason this is
     * not simply "an unmatched asterisk is text". `*foo` is somebody meaning
     * emphasis; rendering it as a literal asterisk is the quiet half-render the
     * parser exists to refuse. Loosening the rule far enough to let `a ** b`
     * through would take this with it if nothing asserted it, at every run
     * length the loosening applies to.
     */
    expect(() => parseInline("*foo", 1)).toThrow(/unterminated emphasis/);
    expect(() => parseInline("**foo", 1)).toThrow(/unterminated emphasis/);
    expect(() => parseInline("a *b c", 1)).toThrow(/unterminated emphasis/);
    expect(() => parseInline("a **b c", 1)).toThrow(/unterminated emphasis/);
  });

  /**
   * The half-render the run scan closes.
   *
   * Matching emphasis with `[^*]+?` meant `*a * b*` matched `*a *` and left ` b*`
   * as text: an italic ending in the wrong place and a literal asterisk on the
   * page, with nothing thrown. Publishing a delimiter is the exact failure the
   * module docstring promises to refuse, so it must not be reachable by writing
   * a sentence with an asterisk inside emphasis.
   */
  it("carries a prose asterisk inside emphasis instead of half-rendering it", () => {
    expect(parseInline("*a * b*", 1)).toEqual([
      { kind: "em", content: [{ kind: "text", text: "a * b" }] },
    ]);
    expect(parseInline("**a * b**", 1)).toEqual([
      { kind: "strong", content: [{ kind: "text", text: "a * b" }] },
    ]);
  });

  it("does not let an asterisk inside a code span close emphasis", () => {
    // Same class as `a ** b`: an asterisk that is not a delimiter. Inside
    // backticks it is content, and a closer scan that did not know that would
    // end the italic in the middle of the code span.
    expect(parseInline("*see `a*b` here*", 1)).toEqual([
      {
        kind: "em",
        content: [
          { kind: "text", text: "see " },
          { kind: "code", text: "a*b" },
          { kind: "text", text: " here" },
        ],
      },
    ]);
    expect(parseInline("`2 ** 8`", 1)).toEqual([{ kind: "code", text: "2 ** 8" }]);
  });

  it("spends only as many asterisks as it opened with", () => {
    // `*a**` is an italic and then a literal asterisk, in CommonMark and to the
    // eye. Consuming the whole closing run would swallow a character the writer
    // typed; the leftover goes back into the stream and is read again.
    expect(parseInline("*a**", 1)).toEqual([
      { kind: "em", content: [{ kind: "text", text: "a" }] },
      { kind: "text", text: "*" },
    ]);
  });

  it("will not close a double run with a single one", () => {
    /**
     * `**a*b**` is bold text with an asterisk in the middle of a word. A run of
     * one cannot close a run of two, so the inner `*` stays in the content -
     * where it reads as an opener with nothing to close it, and the build stops.
     * Refusing is the trade this parser makes everywhere; the alternative here
     * is ending the bold at the wrong asterisk and printing the rest.
     */
    expect(() => parseInline("**a*b**", 1)).toThrow(/unterminated emphasis/);
  });

  it("refuses a run of three, rather than guessing which nesting was meant", () => {
    // `***x***` is legal CommonMark for bold italic. This parser has no node for
    // it, and the document has never used it; refusing beats rendering one of
    // the two and losing the other silently.
    expect(() => parseInline("***x***", 1)).toThrow(/three asterisks/);
  });
});

/**
 * What /accuracy actually serves.
 *
 * Everything above this line is about an AST. An AST is not what a buyer reads,
 * and the failure that started this - nine phases of the most important page in
 * the product being a `<pre>` full of pipes - happened entirely between a correct
 * document and the markup rendered from it. So this renders the real page
 * component and reads the markup, which is the only artifact the buyer sees.
 *
 * The finding types come from `findingTypeSchema` rather than from a list typed
 * here, so a seventeenth type added to the registry fails this test until it
 * reaches the published page. That is the direction the drift always runs: the
 * registry gains a row, the document is regenerated, and nothing notices if the
 * page renders fifteen of them.
 */
/**
 * An asterisk run that survived as a delimiter, as opposed to one somebody typed.
 *
 * This is `markdown.ts`'s opening rule read back off the page: a run with a word
 * immediately after it is the only shape that can open emphasis, so on a correctly
 * rendered page it has either been consumed into a `<strong>`/`<em>` or thrown. A
 * run with whitespace (or the end of the text) on the far side opened nothing, and
 * the parser publishes it as the character it is - `2 ** 8` is an exponent.
 */
const SURVIVING_DELIMITER = /\*+(?=[^\s*])/g;

describe("the rendered page publishes every finding type", () => {
  const html = renderToStaticMarkup(createElement(AccuracyPage));

  /** Body cell text, with entities left alone - every value here is plain ASCII. */
  const cells = [...html.matchAll(/<td[^>]*>([^<]*)<\/td>/g)].map((m) =>
    (m[1] ?? "").trim(),
  );

  it("renders the document as markup rather than as its own source", () => {
    /**
     * The nine-phase defect, asserted as the three things it looked like on
     * screen: `## Finding types and their gates`, `**bold**` with the asterisks
     * in, and the gate table as pipes.
     *
     * The two source lines are taken out of the document rather than typed here,
     * and then checked non-empty. A quoted line would go vacuously green the
     * first time somebody rewords a heading - passing because it found nothing
     * to look for, which is the failure mode this whole file is about.
     */
    const heading = ACCURACY_MD.split("\n").find((l) => l.startsWith("## ")) ?? "";
    const bold = ACCURACY_MD.split("\n").find((l) => l.startsWith("**")) ?? "";
    expect(heading, "no `## ` line in the document to look for").not.toBe("");
    expect(bold, "no `**` line in the document to look for").not.toBe("");

    expect(html).not.toContain(heading);
    expect(html).not.toContain(bold);
    expect(html).not.toContain("|---|");
    expect(html).toContain("<table");
  });

  it("gives every registered finding type a cell", () => {
    const missing = findingTypeSchema.options.filter((type) => !cells.includes(type));
    expect(missing, "finding types that reach no cell on the rendered page").toEqual([]);
  });

  it("renders as many rows as the document has, and no fewer", () => {
    const rows = [...html.matchAll(/<tr>/g)].length;
    // The header row plus one per finding type. A row lost between the AST and
    // the markup is the same missing gate as a row lost in the source.
    expect(rows).toBe(gate.rows.length + 1);
  });

  it("still says no finding type is in a paid report", () => {
    // LAW 4's actual state, on the page a buyer reads before paying. Four zeros
    // are only honest if the page showing them is legible.
    expect(cells.filter((c) => c === "no")).toHaveLength(findingTypeSchema.options.length);
  });

  it("leaves no markdown delimiter anywhere in the rendered text", () => {
    /**
     * The general form of the defect this page had for nine phases, rather than
     * the six examples of it above. A delimiter a reader sees means some
     * construct was matched and then printed back out with its syntax attached,
     * which is the half-render the parser exists to prevent and is easy to
     * reintroduce one nesting case at a time.
     *
     * "No asterisk on the page" is what this used to say, and it contradicted
     * the parser in the same commit that changed it: `markdown.ts` reads `2 ** 8`
     * as text precisely so the build survives a sentence with an asterisk in it,
     * and this test would then have failed on that sentence. The property that
     * is actually wanted is narrower - no run that could have opened emphasis -
     * and it is the parser's own rule, so the two cannot drift apart.
     *
     * A backtick has no such exemption: the parser throws on an unmatched one,
     * so none can reach a reader at all.
     */
    // The detector has to be able to fire. A rule this narrow could be narrowed
    // one character further into matching nothing, and would then pass this page
    // for the same reason the page passed for nine phases: because nobody looked.
    expect("half *rendered and 2 ** 8".match(SURVIVING_DELIMITER)).toEqual(["*"]);

    const text = html.replace(/<[^>]+>/g, " ");
    expect(text).not.toContain("`");
    expect(
      text.match(SURVIVING_DELIMITER),
      "asterisk runs with a word after them, which is a delimiter the page printed",
    ).toBeNull();
  });

  it("keeps the document's own words, not a rewrite of them", () => {
    const text = html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
    expect(text).toContain("there are still no accuracy numbers");
    expect(text).toContain("recall work is free");
    expect(text).toContain("No number appears on this page that is not reproducible");
  });

  it("publishes an asterisk the parser permits, all the way to the markup", async () => {
    /**
     * The other end of the flanking rule, and the reason it is asserted here and
     * not only on the AST. The rule exists so that `next build` does not die the
     * day this page acquires a sentence with an asterisk in it - and that is a
     * claim about the published page, not about `parseInline`. Asserting it on
     * the parser alone left the two halves free to contradict each other, which
     * is exactly what they did: the parser was loosened to permit a prose
     * asterisk in the same commit as a page test forbidding every asterisk.
     *
     * So a document with the permitted shapes in it is put through the real page
     * component, and both halves are asserted at once: the sentence survives
     * verbatim, and the delimiter check above still passes on it.
     */
    vi.resetModules();
    const doc = "# t\n\nA byte has 2 ** 8 values, and 3 * 4 is 12. See the marker*\n";
    vi.doMock("@/generated/accuracy", () => ({ ACCURACY_MD: doc }));
    const mod = await import("@/app/accuracy/page");
    const text = renderToStaticMarkup(createElement(mod.default)).replace(/<[^>]+>/g, " ");
    expect(text).toContain("A byte has 2 ** 8 values, and 3 * 4 is 12. See the marker*");
    expect(text.match(SURVIVING_DELIMITER)).toBeNull();
    vi.doUnmock("@/generated/accuracy");
    vi.resetModules();
  });

  it("parses at import time, which is where the build failure has to happen", async () => {
    /**
     * The whole trade this parser makes - strictness in exchange for a loud
     * failure - is only paid out if the failure lands during `next build`. A
     * parse moved inside the component would still throw, at request time, on
     * the accuracy page, in production, discovered by a buyer.
     *
     * So the page module is re-imported over a document the parser refuses, and
     * the assertion is that the *import* rejects. Nothing is rendered here: if
     * this passes only when a component is called, the parse is in the wrong
     * place and this test says so.
     */
    vi.resetModules();
    vi.doMock("@/generated/accuracy", () => ({ ACCURACY_MD: "# fine\n\n> quoted\n" }));
    await expect(import("@/app/accuracy/page")).rejects.toThrow(
      /blockquotes are not supported/,
    );
    vi.doUnmock("@/generated/accuracy");
    vi.resetModules();
  });
});
