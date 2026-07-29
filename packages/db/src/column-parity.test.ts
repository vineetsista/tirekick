import { describe, expect, it } from "vitest";
import { getTableColumns } from "drizzle-orm";
import { assetSchema, findingSchema } from "@tirekick/shared";
import { assets, findings } from "./schema";

/**
 * Every field in the contract has somewhere to be stored.
 *
 * ---------------------------------------------------------------------------
 * THE BUG THIS WAS WRITTEN FOR
 * ---------------------------------------------------------------------------
 *
 * `width` and `height` were added to `assetSchema` so that an `image_region` box
 * - which is expressed as fractions of them - stays checkable. Every layer
 * updated except this one. The `assets` table kept its nine columns, and nothing
 * failed: `enum-parity.test.ts` compares enum *values*, the contract drift test
 * compares the emitted report against zod, and neither of them looks at whether
 * a column exists to hold a field.
 *
 * The result would have been a persistence layer that accepts a report and
 * silently returns a different one - rows asserting a defect occupies 34% of a
 * photograph whose dimensions nothing recorded. The box survives, the thing that
 * makes it checkable does not, and the loss is invisible until someone tries to
 * redraw the box a year later.
 *
 * This is the same failure the project has now found four times: a second
 * definition of the same shape, kept in step by attention rather than by a test.
 *
 * ---------------------------------------------------------------------------
 * WHAT IT DOES NOT CHECK
 * ---------------------------------------------------------------------------
 *
 * Names and presence only - not types, not nullability. A `text` column holding
 * an integer would pass here. Worth stating plainly: this closes the gap where a
 * field has nowhere to go, which is the one that has actually occurred, and
 * leaves type-level drift to the round-trip test that persistence will need
 * before it is real. `inspections.ts` is still local disk and a subprocess.
 */

/** Columns that exist for storage rather than because the contract has them. */
const STORAGE_ONLY = new Set(["inspectionId", "createdAt"]);

/**
 * Contract fields the table deliberately stores under other names.
 *
 * `estimatedCostUsd` is one nullable `{low, high}` object in the contract and two
 * nullable integer columns here, so a query can filter on a repair band without
 * unpacking jsonb. The split is the reason this map exists rather than evidence
 * that something drifted - but it is written down, so a *new* divergence has to
 * be added here deliberately instead of arriving by accident.
 */
const RENAMED: Record<string, readonly string[]> = {
  estimatedCostUsd: ["estimatedCostLowUsd", "estimatedCostHighUsd"],
};

const tables = [
  ["assets", assets, assetSchema],
  ["findings", findings, findingSchema],
] as const;

describe("every contract field has a column", () => {
  for (const [name, table, schema] of tables) {
    const columns = new Set(Object.keys(getTableColumns(table)));

    it(`${name} stores every field in the contract`, () => {
      const missing: string[] = [];
      for (const field of Object.keys(schema.shape)) {
        const expected = RENAMED[field] ?? [field];
        for (const column of expected) {
          if (!columns.has(column)) missing.push(`${field} -> ${column}`);
        }
      }
      expect(missing).toEqual([]);
    });

    it(`${name} has no column the contract does not explain`, () => {
      const accounted = new Set<string>(STORAGE_ONLY);
      for (const field of Object.keys(schema.shape)) {
        for (const column of RENAMED[field] ?? [field]) accounted.add(column);
      }
      expect([...columns].filter((c) => !accounted.has(c))).toEqual([]);
    });
  }
});
