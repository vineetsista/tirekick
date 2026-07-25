import { describe, expect, it } from "vitest";
import {
  assetKindSchema,
  findingTypeSchema,
  severitySchema,
  systemKeySchema,
  runModeSchema,
} from "@tirekick/shared";
import { assetKind, findingType, runMode, severity, systemKey } from "./schema.js";

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
  ["run_mode", runMode.enumValues, runModeSchema.options],
] as const;

describe("postgres enums match the zod contract", () => {
  for (const [name, pgValues, zodValues] of pairs) {
    it(`${name} is in parity`, () => {
      expect([...pgValues].sort()).toEqual([...zodValues].sort());
    });
  }
});
