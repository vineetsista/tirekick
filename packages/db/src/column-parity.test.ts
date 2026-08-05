import { describe, expect, it } from "vitest";
import { getTableColumns, getTableName, is } from "drizzle-orm";
import { PgTable } from "drizzle-orm/pg-core";
import {
  assetSchema,
  contractShape,
  findingSchema,
  priceCheckSchema,
} from "@tirekick/shared";
import * as schemaModule from "./schema";
import { assets, findings, priceChecks } from "./schema";

/**
 * Every field in the contract has somewhere to be stored, and somewhere that can
 * hold the value the contract permits.
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
 * Names, presence, and one property of the type: whether a column can hold a
 * fraction the contract accepts. Not nullability, not string length, not whether
 * a `text` column is holding a number. Worth stating plainly: this closes the gap
 * where a field has nowhere to go and the gap where it goes somewhere too small,
 * which are the two that have actually occurred, and leaves the rest to the
 * round-trip test that persistence will need before it is real. `inspections.ts`
 * is still local disk and a subprocess.
 *
 * ---------------------------------------------------------------------------
 * WHICH TABLES ARE IN THE LIST, AND WHY THE REST ARE NOT
 * ---------------------------------------------------------------------------
 *
 * `assets`, `findings` and `price_checks` shred a contract object into columns,
 * so a field with no column is a field that is silently dropped on the way in.
 * `price_checks` was not in this list, and had lost three of them: `excluded`,
 * `normalizationNotes` and `verdictStatement` - the comps that were thrown out,
 * the arithmetic that produced the range, and the sentence a buyer reads. The
 * verdict survived; everything that makes the verdict checkable did not. That is
 * the same defect the assets table had, found the same way, and the reason it
 * survived the fix that found it is that the fix added a test over two tables and
 * called the class closed.
 *
 * `reports` and `vehicle_records` store the whole contract object as one jsonb
 * document beside a handful of indexed columns, so field-by-field parity is not
 * the right question for them - the drift gate in packages/shared is. And
 * `inspections` is not a contract object at all; nothing in the report describes
 * an upload's lifecycle.
 *
 * That paragraph used to be the whole of the safeguard. `tables` below was a
 * hand-written array of three entries and nothing read the schema module to ask
 * whether it was still complete, so a fourth pgTable could be declared - shredding
 * a contract object, missing half its fields - and this file would go on reporting
 * three tables in parity. `enum-parity.test.ts` had already been through exactly
 * this and grown the gate that fixes it; this file had the same hole beside it and
 * did not. `compares every table the schema declares` is that gate: a new table is
 * either compared or named in CONTRACT_FREE_TABLES with a reason.
 */

/** Columns that exist for storage rather than because the contract has them. */
const STORAGE_ONLY = ["inspectionId", "createdAt"] as const;

/**
 * `price_checks` also carries a surrogate key. A price check has no id in the
 * contract - it belongs to its inspection and there is one - so the primary key
 * is a fact about the table rather than a field that went missing.
 */
const PRICE_CHECK_STORAGE_ONLY = [...STORAGE_ONLY, "id"] as const;

/**
 * Contract fields the table deliberately stores under other names, and which end
 * of the band each column holds.
 *
 * `estimatedCostUsd` and `fairRangeUsd` are each one `{low, high}` object in the
 * contract and two columns here, so a query can filter on a band without
 * unpacking jsonb. The split is the reason this map exists rather than evidence
 * that something drifted - but it is written down, so a *new* divergence has to
 * be added here deliberately instead of arriving by accident.
 */
const RENAMED: Record<string, Readonly<Record<string, "low" | "high">>> = {
  estimatedCostUsd: { estimatedCostLowUsd: "low", estimatedCostHighUsd: "high" },
  fairRangeUsd: { fairRangeLowUsd: "low", fairRangeHighUsd: "high" },
};

/** The columns one contract field is stored in - usually itself. */
function columnsFor(field: string): readonly string[] {
  const split = RENAMED[field];
  return split === undefined ? [field] : Object.keys(split);
}

/**
 * Tables that store no contract object field by field, and so are not compared.
 *
 * `reports` and `vehicle_records` hold the whole document in jsonb; the drift
 * gate in packages/shared is what checks those. `inspections` describes an
 * upload's lifecycle, which the report contract has no shape for. Named here
 * rather than simply left out of `tables`, which is the difference between a
 * decision and an oversight - and none of the three is exempt from the dollar
 * check below, which is the one that caught `inspections`.
 */
const CONTRACT_FREE_TABLES = new Set(["inspections", "reports", "vehicle_records"]);

/**
 * Every pgTable the schema module exports, paired with its SQL name.
 *
 * Widened to `unknown` first because the module also exports pgEnums, and a type
 * predicate cannot narrow a union that does not already contain its target.
 */
const DECLARED: readonly (readonly [string, PgTable])[] = (
  Object.values(schemaModule) as unknown[]
)
  .filter((value): value is PgTable => is(value, PgTable))
  .map((table) => [getTableName(table), table] as const);

type ContractField = NonNullable<ReturnType<typeof contractShape>[string]>;

/**
 * Does the contract permit a value with a fractional part here?
 *
 * Asked of the schema rather than read off a list of column names. `$8,499.50`
 * is an asking price `priceCheckSchema` accepts and an `integer` column turned
 * into `$8,499` on the way in - a different number, in a product whose entire
 * job is to argue about that number, changed with nothing recording that it was.
 *
 * A split field is probed as the whole band: both of its columns hold the same
 * type, so one answer covers them.
 */
function acceptsAFraction(leaf: ContractField, split: boolean): boolean {
  return leaf.safeParse(split ? { low: 0.5, high: 0.5 } : 0.5).success;
}

/** Postgres integer types. `numeric` and `double precision` keep the cents. */
function truncatesFractions(column: { getSQLType(): string }): boolean {
  return /^(small|big)?int(eger)?$/.test(column.getSQLType());
}

const tables = [
  ["assets", assets, assetSchema, STORAGE_ONLY],
  ["findings", findings, findingSchema, STORAGE_ONLY],
  ["price_checks", priceChecks, priceCheckSchema, PRICE_CHECK_STORAGE_ONLY],
] as const;

describe("every contract field has a column", () => {
  for (const [name, table, schema, storageOnly] of tables) {
    const columnDefs = getTableColumns(table);
    const columns = new Set(Object.keys(columnDefs));
    const shape = contractShape(schema);

    it(`${name} stores every field in the contract`, () => {
      const missing: string[] = [];
      for (const field of Object.keys(shape)) {
        for (const column of columnsFor(field)) {
          if (!columns.has(column)) missing.push(`${field} -> ${column}`);
        }
      }
      expect(missing).toEqual([]);
    });

    it(`${name} has no column the contract does not explain`, () => {
      const accounted = new Set<string>(storageOnly);
      for (const field of Object.keys(shape)) {
        for (const column of columnsFor(field)) accounted.add(column);
      }
      expect([...columns].filter((c) => !accounted.has(c))).toEqual([]);
    });

    it(`${name} stores fractional contract values in columns that keep them`, () => {
      const truncated: string[] = [];
      for (const [field, leaf] of Object.entries(shape)) {
        if (leaf === undefined) continue;
        if (!acceptsAFraction(leaf, RENAMED[field] !== undefined)) continue;
        for (const column of columnsFor(field)) {
          const def = columnDefs[column as keyof typeof columnDefs];
          if (def !== undefined && truncatesFractions(def)) {
            truncated.push(`${field} -> ${column} is ${def.getSQLType()}`);
          }
        }
      }
      expect(truncated).toEqual([]);
    });
  }

  /**
   * The list above is itself a second copy, and nothing checked it.
   *
   * A pgTable declared in schema.ts and left out of `tables` was compared by
   * nothing: adding one that shredded a contract object and omitted two of its
   * fields left this file at "13 passed". Comparing the tables the list happens
   * to name proves only that the list is consistent with itself; this asks the
   * schema what tables it actually declares, so a table added tomorrow either
   * gets compared or gets named.
   */
  it("compares every table the schema declares", () => {
    const covered = new Set<string>([
      ...tables.map(([name]) => name),
      ...CONTRACT_FREE_TABLES,
    ]);
    expect(DECLARED.map(([name]) => name).filter((n) => !covered.has(n))).toEqual([]);
  });

  /**
   * No dollar amount anywhere is stored in a column that cannot hold cents.
   *
   * The per-table check runs only on the three tables that shred a contract
   * object, and `inspections.asking_price_usd` is on none of them: it is the
   * price the buyer typed, on a table the contract has no shape for. It was an
   * `integer` as well, so the exemption above was quietly covering a truncation.
   *
   * This one is name-driven, and that is its limit: a dollar column not named
   * `*Usd` is not caught by it. Nothing here checks that the naming holds.
   */
  it("stores no dollar amount in a column that truncates cents", () => {
    const truncating: string[] = [];
    for (const [name, table] of DECLARED) {
      for (const [field, column] of Object.entries(getTableColumns(table))) {
        if (!field.endsWith("Usd")) continue;
        if (truncatesFractions(column)) {
          truncating.push(`${name}.${column.name} is ${column.getSQLType()}`);
        }
      }
    }
    expect(truncating).toEqual([]);
  });
});
