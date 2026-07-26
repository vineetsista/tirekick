import type { Metadata } from "next";
import Link from "next/link";
import { ACCURACY_MD } from "@/generated/accuracy";

export const metadata: Metadata = {
  title: "TIREKICK accuracy - including the misses",
  description:
    "How accurate TIREKICK is, per finding type, with sample sizes and known failure modes.",
};

/**
 * Rendered verbatim from docs/ACCURACY.md (LAW 6). Presenting the source document
 * rather than a marketing rewrite of it is the point: the page a customer reads
 * and the page we hold ourselves to are the same file.
 */
export default function AccuracyPage() {
  return (
    <div className="wrap" style={{ paddingTop: 48, paddingBottom: 96, maxWidth: 900 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          flexWrap: "wrap",
          gap: 12,
          paddingBottom: 20,
          borderBottom: "1px solid var(--tk-line)",
        }}
      >
        <Link href="/" style={{ fontSize: 20, letterSpacing: "0.22em", fontWeight: 700 }}>
          TIREKICK
        </Link>
        <span className="mono-label">docs/ACCURACY.md - rendered verbatim</span>
      </div>

      <pre
        style={{
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          fontFamily: "var(--tk-mono)",
          fontSize: 13,
          lineHeight: 1.7,
          marginTop: 32,
        }}
      >
        {ACCURACY_MD}
      </pre>
    </div>
  );
}
