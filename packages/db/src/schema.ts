import {
  boolean,
  doublePrecision,
  index,
  integer,
  jsonb,
  pgEnum,
  pgTable,
  text,
  timestamp,
  uniqueIndex,
} from "drizzle-orm/pg-core";
import type {
  BoundingBox,
  Coverage,
  Evidence,
  Report,
  VehicleRecord,
} from "@tirekick/shared";

/**
 * Enum values are duplicated from the zod contract on purpose - Postgres enums
 * cannot be derived from zod at runtime. The contract drift test in
 * packages/shared covers the report payload; these enums are covered by
 * src/enum-parity.test.ts.
 */

export const assetKind = pgEnum("asset_kind", [
  "photo",
  "video",
  "audio",
  "document",
]);

export const severity = pgEnum("severity", ["info", "minor", "major", "critical"]);

export const systemKey = pgEnum("system_key", [
  "exterior",
  "interior",
  "engine",
  "transmission",
  "brakes",
  "suspension",
  "steering",
  "tires",
  "electrical",
  "restraints",
  "structure",
  "fluids",
  "glass",
  "documentation",
]);

export const findingType = pgEnum("finding_type", [
  "exterior_damage",
  "rust_corrosion",
  "repaint_indicator",
  "tire_tread_estimate",
  "interior_wear",
  "fluid_leak_indicator",
  "dash_warning_light",
  "odometer_reading",
  "odometer_wear_mismatch",
  "audio_anomaly",
  "vin_decode",
  "open_recall",
  "complaint_pattern",
  "price_comparison",
  "documentation_gap",
]);

export const engineName = pgEnum("engine_name", [
  "vision",
  "audio",
  "data",
  "pricing",
]);

export const inspectionStatus = pgEnum("inspection_status", [
  "created",
  "uploading",
  "queued",
  "running",
  "complete",
  "failed",
]);

export const runMode = pgEnum("run_mode", ["fixture", "live"]);

/* ------------------------------------------------------------------ */

export const inspections = pgTable(
  "inspections",
  {
    id: text("id").primaryKey(),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
    status: inspectionStatus("status").notNull().default("created"),
    mode: runMode("mode").notNull().default("fixture"),
    /** Buyer email, nullable until they pay. */
    buyerEmail: text("buyer_email"),
    vin: text("vin"),
    askingPriceUsd: integer("asking_price_usd"),
    /** Stripe payment reference; null means teaser-only. */
    paymentRef: text("payment_ref"),
    paidAt: timestamp("paid_at", { withTimezone: true }),
    /** LIABILITY section 4 - the pre-payment acknowledgement. */
    disclaimerAcceptedAt: timestamp("disclaimer_accepted_at", { withTimezone: true }),
    /** LIABILITY section 6 - opt-in, off by default. */
    trainingOptIn: boolean("training_opt_in").notNull().default(false),
  },
  (t) => [index("inspections_created_at_idx").on(t.createdAt)],
);

export const assets = pgTable(
  "assets",
  {
    id: text("id").primaryKey(),
    inspectionId: text("inspection_id")
      .notNull()
      .references(() => inspections.id, { onDelete: "cascade" }),
    kind: assetKind("kind").notNull(),
    path: text("path").notNull(),
    sha256: text("sha256").notNull(),
    bytes: integer("bytes").notNull(),
    viewClass: text("view_class"),
    viewConfidence: doublePrecision("view_confidence"),
    durationSec: doublePrecision("duration_sec"),
    synthetic: boolean("synthetic").notNull().default(false),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [
    index("assets_inspection_idx").on(t.inspectionId),
    uniqueIndex("assets_inspection_sha_idx").on(t.inspectionId, t.sha256),
  ],
);

export const findings = pgTable(
  "findings",
  {
    id: text("id").primaryKey(),
    inspectionId: text("inspection_id")
      .notNull()
      .references(() => inspections.id, { onDelete: "cascade" }),
    type: findingType("type").notNull(),
    system: systemKey("system").notNull(),
    title: text("title").notNull(),
    detail: text("detail").notNull(),
    severity: severity("severity").notNull(),
    confidence: doublePrecision("confidence").notNull(),
    confidenceBasis: text("confidence_basis").notNull(),
    /**
     * LAW 1 - not null, and the application layer enforces length >= 1 via the
     * zod contract before insert. Postgres cannot express "non-empty array" on a
     * jsonb column, so the guarantee lives in the contract, not here.
     */
    evidence: jsonb("evidence").$type<Evidence[]>().notNull(),
    estimatedCostLowUsd: integer("estimated_cost_low_usd"),
    estimatedCostHighUsd: integer("estimated_cost_high_usd"),
    sellerQuestion: text("seller_question"),
    mechanicCheck: text("mechanic_check"),
    engine: engineName("engine").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [
    index("findings_inspection_idx").on(t.inspectionId),
    index("findings_type_idx").on(t.type),
  ],
);

export const vehicleRecords = pgTable(
  "vehicle_records",
  {
    vin: text("vin").primaryKey(),
    payload: jsonb("payload").$type<VehicleRecord>().notNull(),
    source: text("source").notNull(),
    retrievedAt: timestamp("retrieved_at", { withTimezone: true }).notNull(),
    /** Cache expiry - recalls change, so this is not permanent. */
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
  },
  (t) => [index("vehicle_records_expires_idx").on(t.expiresAt)],
);

export const priceChecks = pgTable("price_checks", {
  id: text("id").primaryKey(),
  inspectionId: text("inspection_id")
    .notNull()
    .references(() => inspections.id, { onDelete: "cascade" }),
  askingPriceUsd: integer("asking_price_usd").notNull(),
  /** LAW 3 - user-pasted comps only. */
  comps: jsonb("comps").notNull(),
  fairRangeLowUsd: integer("fair_range_low_usd").notNull(),
  fairRangeHighUsd: integer("fair_range_high_usd").notNull(),
  deductions: jsonb("deductions").notNull(),
  verdict: text("verdict").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const reports = pgTable(
  "reports",
  {
    id: text("id").primaryKey(),
    inspectionId: text("inspection_id")
      .notNull()
      .references(() => inspections.id, { onDelete: "cascade" }),
    schemaVersion: text("schema_version").notNull(),
    mode: runMode("mode").notNull(),
    /** The full rendered contract - the artifact the viewer parses. */
    payload: jsonb("payload").$type<Report>().notNull(),
    coverage: jsonb("coverage").$type<Coverage>().notNull(),
    redFlagScore: integer("red_flag_score").notNull(),
    /** LAW 5 - measured, per report. */
    costUsd: doublePrecision("cost_usd").notNull(),
    costDetail: jsonb("cost_detail").notNull(),
    containsSyntheticMedia: boolean("contains_synthetic_media")
      .notNull()
      .default(false),
    /** Public share token; null means not shared. */
    shareToken: text("share_token"),
    generatedAt: timestamp("generated_at", { withTimezone: true }).notNull(),
  },
  (t) => [
    index("reports_inspection_idx").on(t.inspectionId),
    uniqueIndex("reports_share_token_idx").on(t.shareToken),
  ],
);

/** Convenience re-export so callers get the box type without importing shared. */
export type { BoundingBox };
