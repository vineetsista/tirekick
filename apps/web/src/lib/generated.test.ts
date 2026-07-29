import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The synced copy must match the artifact it was copied from.
 *
 * `scripts/sync-fixture-to-web.mjs` copies the pipeline's output into
 * `src/generated/`, where it is imported at module scope and parsed through the
 * zod contract. It runs on `pnpm dev` and `pnpm build` and at no other time.
 *
 * So regenerating the fixture without re-running sync leaves the app - and every
 * component test - reading a stale report. That happened three times while
 * building this phase, and each time the symptom was a test failing against data
 * that no longer existed, or worse, passing against data that did.
 *
 * `fixture:clean` already proves the fixture is not stale against the pipeline.
 * Nothing proved the copy was not stale against the fixture. This closes the
 * second half of that chain.
 */

const repoRoot = resolve(process.cwd(), "../..");

const PAIRS = [
  ["fixtures/reports/demo-01.report.json", "src/generated/demo-01.report.json"],
  ["fixtures/reports/demo-01.teaser.json", "src/generated/demo-01.teaser.json"],
] as const;

describe("src/generated is in sync with fixtures/", () => {
  for (const [source, copy] of PAIRS) {
    it(`${copy} matches ${source}`, () => {
      const a = JSON.parse(readFileSync(resolve(repoRoot, source), "utf8"));
      const b = JSON.parse(readFileSync(resolve(process.cwd(), copy), "utf8"));
      expect(
        b,
        `${copy} is stale. Run: pnpm --filter web run sync`,
      ).toEqual(a);
    });
  }
});
