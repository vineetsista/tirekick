import { Fragment } from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { ACCURACY_MD } from "@/generated/accuracy";
import { parseMarkdown, type Block, type Inline } from "@/lib/markdown";
import { Wordmark } from "@/components/Wordmark";

export const metadata: Metadata = {
  title: "TIREKICK accuracy - including the misses",
  description:
    "How accurate TIREKICK is, per finding type, with sample sizes and known failure modes.",
};

/**
 * The page LAW 6 requires the product to link, typeset instead of dumped.
 *
 * For nine phases this component read `docs/ACCURACY.md` and put the entire
 * string in a `<pre>`. A buyer who followed the accuracy link - the one directly
 * above the payment button - was shown `## Finding types and their gates`,
 * `**bold**` with the asterisks in, and the sixteen-row gate table as
 * pipe-delimited text. Every other surface in the product was designed twice
 * over while the one page that carries the honesty claim was the least readable
 * thing in it, which is its own kind of dishonesty: a disclosure nobody can read
 * is a disclosure in name.
 *
 * Nothing here rewrites the document. The words, the order and the table are the
 * file's, because the page a customer reads and the page this repository holds
 * itself to have to be the same file (LAW 6) - typesetting is the only thing
 * that happens between them.
 */

/**
 * Parsed once, at module scope, on purpose.
 *
 * `markdown.ts` throws on anything it does not understand, and this is where
 * that throw has to land: at module evaluation, which is `next build`. A parse
 * moved inside the component would fail at request time instead - a 500 on the
 * accuracy page, in production, discovered by a buyer.
 */
const BLOCKS: Block[] = parseMarkdown(ACCURACY_MD);

export default function AccuracyPage() {
  return (
    <div
      className="wrap"
      style={{ paddingTop: "var(--s-7)", paddingBottom: "var(--s-9)", maxWidth: 900 }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          flexWrap: "wrap",
          gap: "var(--s-3)",
          paddingBottom: "var(--s-4)",
          borderBottom: "1px solid var(--tk-rule)",
        }}
      >
        <Link href="/" style={{ textDecoration: "none" }}>
          <Wordmark fontSize="var(--t-md)" />
        </Link>
        <span className="label">docs/ACCURACY.md &middot; typeset, not rewritten</span>
      </header>

      <article>
        {BLOCKS.map((block, i) => (
          <BlockView key={i} block={block} />
        ))}
      </article>
    </div>
  );
}

function BlockView({ block }: { block: Block }) {
  switch (block.kind) {
    case "heading":
      return <Heading level={block.level} content={block.content} />;

    case "paragraph":
      return (
        <p className="prose" style={{ margin: "var(--s-4) 0 0" }}>
          <Inlines content={block.content} />
        </p>
      );

    case "list":
      return (
        <ul
          className="prose"
          style={{
            margin: "var(--s-4) 0 0",
            paddingLeft: "var(--s-5)",
            display: "grid",
            gap: "var(--s-3)",
          }}
        >
          {block.items.map((item, i) => (
            <li key={i}>
              <Inlines content={item} />
            </li>
          ))}
        </ul>
      );

    case "table":
      return <GateTable head={block.head} rows={block.rows} />;

    case "rule":
      return (
        <hr
          style={{ margin: "var(--s-7) 0 0", border: 0, borderTop: "1px solid var(--tk-rule)" }}
        />
      );
  }
}

/**
 * Sections are separated by size and space, not by a rule.
 *
 * The document draws two horizontal rules of its own, one of them immediately
 * before an `##`. A heading that also carried a top border would have put two
 * lines a hundred pixels apart with nothing between them, and the reader would
 * have had to work out which one meant something.
 */
function Heading({ level, content }: { level: 1 | 2 | 3; content: Inline[] }) {
  const inner = <Inlines content={content} />;
  if (level === 1) {
    return <h1 style={{ fontSize: "var(--t-2xl)", marginTop: "var(--s-6)" }}>{inner}</h1>;
  }
  if (level === 2) {
    return <h2 style={{ fontSize: "var(--t-xl)", marginTop: "var(--s-8)" }}>{inner}</h2>;
  }
  return <h3 style={{ fontSize: "var(--t-lg)", marginTop: "var(--s-6)" }}>{inner}</h3>;
}

/**
 * The gate table. Sixteen rows, and all sixteen have to arrive.
 *
 * Every cell is a value `scripts/sync_accuracy_table.py` wrote out of the
 * registry rather than a sentence anybody composed, so the whole body is set in
 * the machine face - the same rule the report tables follow.
 *
 * `nowrap` and `.table-scroll` together, and the pair is the point. `body` sets
 * `overflow-wrap: anywhere`, which lets a table cell shrink to one character:
 * without `nowrap` this table squeezes itself into a 320px phone by breaking
 * `odometer_wear_mismatch` across six line boxes, corrupting on screen the exact
 * identifier column the parser refuses to corrupt in the source. With it, the
 * row keeps its width and the table scrolls sideways inside its own box, which
 * leaves the document itself free of a horizontal scrollbar.
 *
 * Both halves of that are claims about a browser, and until P10 nothing opened
 * one on this page - the paragraph above said "three lines" because somebody
 * estimated it. `layout.test.ts` now lays this page out at 320px: the viewport
 * check holds `.table-scroll`, and "keeps the gate table's identifiers unbroken"
 * holds `nowrap` by counting line boxes per cell. Six is the number that test
 * printed with the rule deleted; what it asserts is one.
 */
function GateTable({ head, rows }: { head: Inline[][]; rows: Inline[][][] }) {
  return (
    <div className="table-scroll" style={{ marginTop: "var(--s-5)" }}>
      <table>
        <thead>
          <tr>
            {head.map((cell, i) => (
              <th key={i}>
                <Inlines content={cell} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, c) => (
                <td
                  key={c}
                  className="data"
                  style={{ fontSize: "var(--t-sm)", whiteSpace: "nowrap" }}
                >
                  <Inlines content={cell} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Inline nodes as elements. No `dangerouslySetInnerHTML` anywhere on this path -
 * the parser hands back an AST rather than markup precisely so that there is no
 * escaping decision to get wrong on the page that publishes our honesty claim.
 *
 * Text runs are wrapped in a keyed `Fragment` rather than a `<span>`: React needs
 * the key, and the document does not need an element around every third word.
 */
function Inlines({ content }: { content: Inline[] }) {
  return (
    <>
      {content.map((node, i) => {
        switch (node.kind) {
          case "text":
            return <Fragment key={i}>{node.text}</Fragment>;
          case "strong":
            // 600, not bold: Newsreader is a 400-600 variable face, and asking
            // for 700 gets a synthesised weight rather than a drawn one.
            return (
              <strong key={i} style={{ fontWeight: 600 }}>
                <Inlines content={node.content} />
              </strong>
            );
          case "em":
            return (
              <em key={i}>
                <Inlines content={node.content} />
              </em>
            );
          case "code":
            return (
              <code
                key={i}
                className="data"
                style={{
                  fontSize: "0.92em",
                  background: "var(--tk-shell-2)",
                  padding: "1px 5px",
                }}
              >
                {node.text}
              </code>
            );
        }
      })}
    </>
  );
}
