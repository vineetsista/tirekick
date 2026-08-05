import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { parseReport, parseTeaser, reportSchema } from "./schema";
import {
  LOCKED_SYSTEMS,
  LOCKED_SYSTEM_STATEMENT,
  PRICE_USD,
  SCHEMA_VERSION,
} from "./constants";

/**
 * THE DRIFT GATE (DECISIONS.md D-002).
 *
 * The Python engines emit the report; the web app consumes it through these zod
 * schemas. Nothing generates one side from the other, so this test is what keeps
 * them honest: it parses the real artifact the pipeline produced. If a Pydantic
 * model changes and zod does not, this fails at exactly the point the drift would
 * have broken the report viewer.
 */

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "../../..");
const reportPath = resolve(repoRoot, "fixtures/reports/demo-01.report.json");
const teaserPath = resolve(repoRoot, "fixtures/reports/demo-01.teaser.json");

describe("python -> typescript report contract", () => {
  it("the fixture report artifact exists", () => {
    expect(
      existsSync(reportPath),
      `Missing ${reportPath}. Run: pnpm run inspect:fixture`,
    ).toBe(true);
  });

  it("parses under the zod contract and satisfies the laws", () => {
    const raw: unknown = JSON.parse(readFileSync(reportPath, "utf8"));
    const report = parseReport(raw);

    expect(report.schemaVersion).toBe(SCHEMA_VERSION);
    expect(report.mode).toBe("fixture");
    expect(report.findings.length).toBeGreaterThan(0);
  });

  it("rejects unknown fields silently rather than crashing the viewer", () => {
    const raw = JSON.parse(readFileSync(reportPath, "utf8")) as Record<
      string,
      unknown
    >;
    const withExtra = { ...raw, someFutureField: 123 };
    expect(() => reportSchema.parse(withExtra)).not.toThrow();
  });

  it("renders the exact locked statement for every locked system", () => {
    const raw: unknown = JSON.parse(readFileSync(reportPath, "utf8"));
    const report = parseReport(raw);
    const locked = report.systems.filter(
      (s) => s.status === "locked_mechanic_required",
    );
    expect(locked.length).toBe(4);
    for (const row of locked) {
      expect(row.statement).toBe(LOCKED_SYSTEM_STATEMENT);
    }
  });

  it("declares its synthetic media", () => {
    const raw: unknown = JSON.parse(readFileSync(reportPath, "utf8"));
    const report = parseReport(raw);
    const anySynthetic = report.assets.some((a) => a.synthetic);
    expect(report.containsSyntheticMedia).toBe(anySynthetic);
  });
});

/**
 * The teaser is the other half of the same artifact, and the drift gate only
 * ever looked at the report.
 *
 * `teaser.py` emits this file and nothing in this package parsed it: the check
 * that a Pydantic change reaches zod stopped at the paywall. It is also the half
 * a stranger reads before paying, which makes it the worse one to leave ungated.
 */
describe("python -> typescript teaser contract", () => {
  it("the fixture teaser artifact exists", () => {
    expect(
      existsSync(teaserPath),
      `Missing ${teaserPath}. Run: pnpm run inspect:fixture`,
    ).toBe(true);
  });

  it("parses under the zod contract and is actually a teaser", () => {
    const raw: unknown = JSON.parse(readFileSync(teaserPath, "utf8"));
    const teaser = parseTeaser(raw);

    expect(teaser.schemaVersion).toBe(SCHEMA_VERSION);
    expect(teaser.mode).toBe("fixture");
    expect(teaser.couldNotAssess.length).toBeGreaterThan(0);
  });

  it("carries the same price the web app prints", () => {
    /**
     * The landing page printed the TypeScript constant and the teaser one click
     * later printed a number the Python CLI had chosen from its own literal
     * default. Two prices, on consecutive pages, in front of the same buyer,
     * with nothing in the repository comparing them.
     *
     * This is the value half of that gate and it reads the real artifact, so it
     * fails when the engine is re-run after either side moves. The source half -
     * forbidding a second literal at all - is in
     * packages/engines/tests/test_shared_constants_parity.py, because equal
     * literals pass every value comparison right up until the day they stop.
     */
    const raw: unknown = JSON.parse(readFileSync(teaserPath, "utf8"));
    const teaser = parseTeaser(raw);
    expect(teaser.priceUsd).toBe(PRICE_USD);
  });

  it("locks every locked system, in status and in wording", () => {
    const raw: unknown = JSON.parse(readFileSync(teaserPath, "utf8"));
    const teaser = parseTeaser(raw);
    const locked = teaser.systems.filter((s) =>
      (LOCKED_SYSTEMS as readonly string[]).includes(s.system),
    );
    expect(locked.length).toBe(LOCKED_SYSTEMS.length);
    for (const row of locked) {
      expect(row.status).toBe("locked_mechanic_required");
      expect(row.statement).toBe(LOCKED_SYSTEM_STATEMENT);
    }
  });
});
