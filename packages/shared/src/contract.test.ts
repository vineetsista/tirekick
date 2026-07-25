import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { parseReport, reportSchema } from "./schema.js";
import { LOCKED_SYSTEM_STATEMENT, SCHEMA_VERSION } from "./constants.js";

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
