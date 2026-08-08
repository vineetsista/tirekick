/**
 * The wordmark, in one place.
 *
 * BRAND.md specifies it as "Archivo, uppercase, 800 weight, 0.22em tracking",
 * and until P11 it was typed as an inline style at every site that drew it.
 * BRAND.md knew: it recorded the drift as two sites disagreeing on tracking and
 * wrote down the reason it was not simply corrected - "a wordmark defined in two
 * places will drift again the moment a third appears."
 *
 * Four more appeared. By P11 the mark was set six times, in three different
 * tracking values, at two different weights:
 *
 *     ReportNav        800  0.22em     <- the documented figure
 *     PurchaseGate     700  0.22em     <- and a different weight
 *     new/page         700  0.22em     <- and again
 *     TeaserView       800  0.24em
 *     accuracy/page    800  0.24em
 *     page (landing)   800  0.26em
 *
 * The list above says six because the test below found six. It was written
 * saying five, from a grep for the two properties, and `new/page.tsx` set them
 * on the `<Link>` rather than on a `<span>` inside it - so the count in this
 * comment was wrong in the commit that removed the duplication it describes.
 *
 * So the copies are gone rather than reconciled, which is what D-049 asks for
 * when a definition exists in more than one place: the duplication is removed,
 * or it ships with the test that compares the copies. `Wordmark.test.tsx` holds
 * the second half - nothing else in the app may render this word.
 *
 * Size stays a prop because BRAND.md does not specify one, and the mark is
 * genuinely smaller in the report nav than on the purchase gate. Weight and
 * tracking are not props, because those are the two things the document does
 * specify, and a prop is a place for them to drift from it again.
 */

export const WORDMARK_WEIGHT = 800;
export const WORDMARK_TRACKING = "0.22em";

export function Wordmark({ fontSize = "var(--t-sm)" }: { fontSize?: string }) {
  return (
    <span
      style={{
        fontWeight: WORDMARK_WEIGHT,
        letterSpacing: WORDMARK_TRACKING,
        fontSize,
      }}
    >
      TIREKICK
    </span>
  );
}
