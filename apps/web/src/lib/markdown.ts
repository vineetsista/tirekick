/**
 * A markdown parser for exactly one document, which refuses everything else. D-062.
 *
 * `/accuracy` is the page LAW 6 requires the product to link, and for nine phases
 * it rendered `docs/ACCURACY.md` by dropping the raw source into a `<pre>`. A buyer
 * who followed the accuracy link - the one the teaser points at, above the payment
 * button - was shown `## Finding types and their gates`, `**bold**` with the
 * asterisks in, and a sixteen-row gate table as pipe-delimited text. The most
 * important page in the product was the least readable thing in it.
 *
 * The obvious fix is a markdown library. This is the less obvious one, and the
 * reason is the failure mode, not the dependency count.
 *
 * A general renderer's contract is "render what you understand, pass through what
 * you do not". Applied to this document that is precisely wrong. If someone adds a
 * table row and mistypes a pipe, a permissive renderer shows fifteen rows and a
 * stray line of text, and the missing gate is invisible - the same shape as every
 * other defect this repository has spent nine phases finding. So this parser
 * inverts the contract: it understands the constructs `docs/ACCURACY.md` actually
 * uses, and it throws on everything else, including malformed versions of what it
 * does support. The page parses at module scope, so a document this parser cannot
 * read fails `next build` instead of reaching a buyer half-rendered.
 *
 * That trade is only sound because the input is one file in this repository under
 * a gate. Pointing this at arbitrary markdown would be a bug.
 *
 * It returns an AST rather than an HTML string, and the page renders it through
 * JSX. Nothing here produces markup, so there is no `dangerouslySetInnerHTML` on
 * the path and no escaping question to get wrong.
 */

/**
 * Emphasis carries nodes, not a string, and the document's last line is why.
 *
 *     *No number appears on this page that is not reproducible from `bench/`.*
 *
 * With a flat `{ kind: "em"; text: string }` that code span stayed inside the
 * italic as two literal backticks, and the signature line of the accuracy page
 * published its own markdown syntax - a smaller copy of the exact failure this
 * module was written to end. The content of a `*run*` is parsed again, which is
 * how the code span arrives as a node; the recursion terminates because the
 * slice handed down is always strictly shorter than the run it came out of.
 */
export type Inline =
  | { kind: "text"; text: string }
  | { kind: "strong"; content: Inline[] }
  | { kind: "em"; content: Inline[] }
  | { kind: "code"; text: string };

export type Block =
  | { kind: "heading"; level: 1 | 2 | 3; content: Inline[] }
  | { kind: "paragraph"; content: Inline[] }
  | { kind: "list"; items: Inline[][] }
  | { kind: "table"; head: Inline[][]; rows: Inline[][][] }
  | { kind: "rule" };

/** Thrown for anything the parser will not render. Always names the line. */
export class MarkdownError extends Error {
  constructor(message: string, lineNumber: number, line: string) {
    super(`docs/ACCURACY.md line ${lineNumber}: ${message}\n  ${line.trim()}`);
    this.name = "MarkdownError";
  }
}

/**
 * Constructs that are legal markdown and are refused anyway.
 *
 * Each one is refused because rendering it would need a decision this parser is
 * not entitled to make on a document about honesty - a link needs a target policy,
 * an image needs the media gate that P9 built, raw HTML needs sanitising. Refusing
 * is not a limitation to be lifted later without thinking; it is the thinking.
 */
const REFUSED: { pattern: RegExp; why: string }[] = [
  { pattern: /!\[/, why: "images are not supported (the media gate owns image serving)" },
  { pattern: /\]\(/, why: "links are not supported" },
  { pattern: /^\s*>/, why: "blockquotes are not supported" },
  { pattern: /^\s*```/, why: "fenced code blocks are not supported" },
  { pattern: /^\s*\d+\.\s/, why: "numbered lists are not supported" },
  { pattern: /^\s{2,}[-*+]\s/, why: "nested lists are not supported" },
  // `(<50)` is prose and must survive; `<span>` is not.
  { pattern: /<\/?[a-zA-Z][^>]*>/, why: "raw HTML is not supported" },
];

const COMMENT = /^\s*<!--.*-->\s*$/;

function refuse(line: string, lineNumber: number): void {
  for (const { pattern, why } of REFUSED) {
    if (pattern.test(line)) throw new MarkdownError(why, lineNumber, line);
  }
}

/**
 * A capture group of a match that succeeded.
 *
 * `noUncheckedIndexedAccess` types every group as `string | undefined`, and the
 * one-character answer is `!`. This is the same claim written so that it is
 * checked: the group can only be absent if a pattern in this file lost its
 * parentheses, which is a defect here and not in the document - so it throws with
 * the text it matched rather than substituting "" and rendering an empty heading
 * nobody notices.
 */
function captured(match: RegExpExecArray, index: number): string {
  const value = match[index];
  if (value === undefined) {
    throw new Error(`markdown.ts: matched ${JSON.stringify(match[0])} with no group ${index}`);
  }
  return value;
}

/** How many `*` in a row start at `i`. Zero if `source[i]` is not one. */
function runLength(source: string, i: number): number {
  let n = 0;
  while (source[i + n] === "*") n += 1;
  return n;
}

/**
 * Where the run of `n` asterisks opened just before `from` is closed, or -1.
 *
 * Two things stop a `*` from closing anything, and both are the same mistake the
 * opener rule above makes if it is written per-character:
 *
 *   - a run preceded by whitespace is not right-flanking, so the middle
 *     asterisk of `*a * b*` is content and the italic runs to the end;
 *   - an asterisk inside a code span is not a delimiter at all, so `` `a*b` ``
 *     cannot end the emphasis that opened before it.
 *
 * A run shorter than the opener cannot close it either. A longer one can, and the
 * asterisks it does not spend are left in the stream to be read again - `*a**`
 * is an italic followed by a literal asterisk, which is what CommonMark says and
 * what the eye says.
 */
function closingRun(source: string, from: number, n: number): number {
  let p = from;
  while (p < source.length) {
    if (source[p] === "`") {
      const end = source.indexOf("`", p + 1);
      // An unclosed backtick swallows the rest of the line here and the caller
      // reports the emphasis as unterminated. The document has no line where the
      // two are distinguishable, and both messages name the same line.
      p = end === -1 ? source.length : end + 1;
      continue;
    }
    if (source[p] !== "*") {
      p += 1;
      continue;
    }
    const m = runLength(source, p);
    if (m >= n && /\S/.test(source[p - 1] ?? "")) return p;
    p += m;
  }
  return -1;
}

/**
 * Split a run of text into inline nodes.
 *
 * Underscores are deliberately not emphasis. Every finding type in the gate table
 * is snake_case - `exterior_damage`, `odometer_wear_mismatch` - and a parser that
 * treated `_` as emphasis would silently italicise half of one identifier and eat
 * the underscores out of the other half, corrupting the exact column the page
 * exists to publish. GFM has intra-word rules that mostly avoid this; "mostly" is
 * not a property worth having here when the alternative is not supporting it.
 */
export function parseInline(source: string, lineNumber: number): Inline[] {
  const out: Inline[] = [];
  let text = "";

  const flush = () => {
    if (text) out.push({ kind: "text", text });
    text = "";
  };

  let i = 0;
  while (i < source.length) {
    const char = source[i] ?? "";

    if (char === "`") {
      // No prose use of a backtick exists in this document, so an unmatched one
      // is always a malformed code span rather than a character somebody meant.
      const code = /^`([^`]+)`/.exec(source.slice(i));
      if (!code) throw new MarkdownError("unterminated code span", lineNumber, source);
      flush();
      out.push({ kind: "code", text: captured(code, 1) });
      i += code[0].length;
      continue;
    }

    if (char === "*") {
      /**
       * A `*` that opens nothing is one of two different things, and only one of
       * them is a malformed document.
       *
       *   `2 ** 8`  - an exponent, a multiplication sign, a footnote marker, a
       *               bullet quoted in prose. CommonMark will not open emphasis
       *               on a delimiter RUN followed by whitespace or by the end of
       *               the line, and neither does this: it is text, and refusing
       *               it would fail the build on the day this page acquires an
       *               asterisk in a sentence.
       *   `**foo`   - somebody opened emphasis and did not close it. That is the
       *               half-rendered line this parser exists to stop, so it throws.
       *
       * The run is measured before the rule is applied, and that is the whole
       * point of this block. The first version of the rule looked at the single
       * character after the first asterisk; for `2 ** 8` that character is
       * another asterisk, so the run was read as opening emphasis and the build
       * died on the sentence it was written to allow.
       */
      const n = runLength(source, i);
      const after = source[i + n] ?? "";
      if (!/\S/.test(after)) {
        text += "*".repeat(n);
        i += n;
        continue;
      }

      if (n > 2) {
        // `***x***` is bold italic in CommonMark. There is no node for it here
        // and the document has never used it; rendering one of the two levels
        // and dropping the other is exactly the quiet half-render this parser
        // refuses, so it says so instead.
        throw new MarkdownError(
          `a run of three asterisks or more has no node here (found ${n})`,
          lineNumber,
          source,
        );
      }

      const close = closingRun(source, i + n, n);
      if (close === -1) throw new MarkdownError("unterminated emphasis", lineNumber, source);

      flush();
      const content = parseInline(source.slice(i + n, close), lineNumber);
      out.push(n === 2 ? { kind: "strong", content } : { kind: "em", content });
      i = close + n;
      continue;
    }

    text += char;
    i += 1;
  }

  flush();
  return out;
}

function cells(line: string, lineNumber: number): Inline[][] {
  const trimmed = line.trim();
  const inner = trimmed.slice(1, trimmed.endsWith("|") ? -1 : undefined);
  return inner.split("|").map((cell) => parseInline(cell.trim(), lineNumber));
}

export function parseMarkdown(source: string): Block[] {
  const lines = source.split("\n");
  const blocks: Block[] = [];
  let i = 0;

  const lineNo = () => i + 1;

  /**
   * The line at `n`, and "" for anything past the end of the document.
   *
   * Every read below already sits inside an `n < lines.length` guard, so under
   * `noUncheckedIndexedAccess` the alternative was thirty `!` assertions - thirty
   * claims that nothing checks. "" is also the honest value: every predicate in
   * this function treats a blank line as "the block ended here", which is exactly
   * what the end of the file means. The delimiter-row lookahead depended on that
   * already.
   */
  const at = (n: number): string => lines[n] ?? "";

  while (i < lines.length) {
    const line = at(i);

    if (!line.trim() || COMMENT.test(line)) {
      i += 1;
      continue;
    }

    refuse(line, lineNo());

    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      const level = captured(heading, 1).length;
      if (level > 3) {
        throw new MarkdownError(`heading level ${level} has no style`, lineNo(), line);
      }
      blocks.push({
        kind: "heading",
        level: level as 1 | 2 | 3,
        content: parseInline(captured(heading, 2).trim(), lineNo()),
      });
      i += 1;
      continue;
    }

    if (/^-{3,}\s*$/.test(line)) {
      blocks.push({ kind: "rule" });
      i += 1;
      continue;
    }

    if (line.trimStart().startsWith("|")) {
      const start = lineNo();
      const head = cells(line, start);
      const delimiter = at(i + 1);
      if (!/^\s*\|(\s*:?-{2,}:?\s*\|)+\s*$/.test(delimiter)) {
        throw new MarkdownError(
          "a table header must be followed by a |---|---| delimiter row",
          start + 1,
          delimiter,
        );
      }
      if (cells(delimiter, start + 1).length !== head.length) {
        throw new MarkdownError(
          `delimiter row has ${cells(delimiter, start + 1).length} cells, header has ${head.length}`,
          start + 1,
          delimiter,
        );
      }
      i += 2;

      const rows: Inline[][][] = [];
      while (i < lines.length && at(i).trimStart().startsWith("|")) {
        refuse(at(i), lineNo());
        const row = cells(at(i), lineNo());
        // The assertion that matters. A mistyped pipe in the gate table must not
        // render as a short row that nobody notices.
        if (row.length !== head.length) {
          throw new MarkdownError(
            `row has ${row.length} cells, header has ${head.length}`,
            lineNo(),
            at(i),
          );
        }
        rows.push(row);
        i += 1;
      }

      if (!rows.length) {
        throw new MarkdownError("table has a header and no rows", start, line);
      }
      blocks.push({ kind: "table", head, rows });
      continue;
    }

    if (/^[-*+]\s/.test(line)) {
      const items: Inline[][] = [];
      while (i < lines.length && /^[-*+]\s/.test(at(i))) {
        const start = lineNo();
        refuse(at(i), start);
        let item = at(i).slice(2).trim();
        i += 1;
        // A wrapped bullet continues on an indented line, and the source wraps at
        // 88 columns, so most bullets on this page have one.
        while (i < lines.length && /^\s{2,}\S/.test(at(i)) && !/^\s{2,}[-*+]\s/.test(at(i))) {
          refuse(at(i), lineNo());
          item += ` ${at(i).trim()}`;
          i += 1;
        }
        items.push(parseInline(item, start));
      }
      blocks.push({ kind: "list", items });
      continue;
    }

    const start = lineNo();
    let paragraph = line.trim();
    i += 1;
    while (i < lines.length) {
      const next = at(i);
      if (
        !next.trim() ||
        COMMENT.test(next) ||
        /^#{1,6}\s/.test(next) ||
        /^-{3,}\s*$/.test(next) ||
        /^[-*+]\s/.test(next) ||
        next.trimStart().startsWith("|")
      ) {
        break;
      }
      refuse(next, lineNo());
      paragraph += ` ${next.trim()}`;
      i += 1;
    }
    blocks.push({ kind: "paragraph", content: parseInline(paragraph, start) });
  }

  return blocks;
}
