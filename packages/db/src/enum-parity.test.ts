import { describe, expect, it } from "vitest";
import { isPgEnum } from "drizzle-orm/pg-core";
import {
  assetKindSchema,
  engineNameSchema,
  findingTypeSchema,
  severitySchema,
  systemKeySchema,
  runModeSchema,
} from "@tirekick/shared";
import * as tables from "./schema";
import {
  assetKind,
  engineName,
  findingType,
  runMode,
  severity,
  systemKey,
} from "./schema";

/**
 * Postgres enums cannot be derived from zod at runtime, so they are typed out
 * twice. This test is the reason that is safe: a value added to the contract and
 * not to the column fails here, before a row with an unrepresentable value is
 * ever written.
 */
const pairs = [
  ["asset_kind", assetKind.enumValues, assetKindSchema.options],
  ["severity", severity.enumValues, severitySchema.options],
  ["system_key", systemKey.enumValues, systemKeySchema.options],
  ["finding_type", findingType.enumValues, findingTypeSchema.options],
  ["engine_name", engineName.enumValues, engineNameSchema.options],
  ["run_mode", runMode.enumValues, runModeSchema.options],
] as const;

/**
 * Enums that exist only in the database.
 *
 * `inspection_status` describes an upload's lifecycle - created, uploading,
 * queued, running, complete, failed - and the report contract has no opinion
 * about it, because a report is what exists after that lifecycle ends. It is
 * named here rather than simply omitted, which is the difference between a
 * decision and an oversight.
 */
const CONTRACT_FREE = new Set(["inspection_status"]);

describe("postgres enums match the zod contract", () => {
  for (const [name, pgValues, zodValues] of pairs) {
    it(`${name} is in parity`, () => {
      expect([...pgValues].sort()).toEqual([...zodValues].sort());
    });
  }

  /**
   * The list above is itself a second copy, and it drifted too.
   *
   * `engine_name` was declared in schema.ts, mirrors the contract's `engine`
   * field, and was in neither `pairs` nor any exemption - it was simply not
   * looked at, and adding a fifth engine to one side would have been caught by
   * nothing. Comparing the enums the list happens to name proves only that the
   * list is consistent with itself; this asks the schema what enums it actually
   * declares, so an enum added tomorrow either gets compared or gets named.
   */
  it("compares every enum the schema declares", () => {
    const declared = Object.entries(tables)
      .filter(([, value]) => isPgEnum(value))
      .map(([, value]) => (value as { enumName: string }).enumName);
    const covered = new Set<string>([...pairs.map(([name]) => name), ...CONTRACT_FREE]);
    expect(declared.filter((name) => !covered.has(name))).toEqual([]);
  });
});
