import { execFile } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { promisify } from "node:util";
import { randomUUID } from "node:crypto";
import { parseReport, parseTeaser, type Report, type Teaser } from "@tirekick/shared";

const run = promisify(execFile);

/**
 * Where an uploaded inspection lives, and how it gets analysed.
 *
 * This is the development-and-test implementation, and it is honest about being
 * one: inspections are directories on local disk and analysis is a subprocess
 * call into the Python CLI. On Vercel neither of those exists - there is no
 * writable filesystem and no Python runtime - so production needs object storage
 * and the worker host the brief already calls for.
 *
 * It is built anyway, for one reason: LAW 7 requires an end-to-end upload -> paid
 * dossier test, and that test cannot exist without an upload that actually runs.
 * Six phases shipped green gates with that clause unmet because nothing forced
 * the question. The interface below is the one the worker will implement, so
 * swapping the transport does not change the flow or the test.
 */

export const WORKSPACE = resolve(
  process.env.TIREKICK_WORKSPACE ?? resolve(process.cwd(), "../../.workspace"),
);

const REPO_ROOT = resolve(process.cwd(), "../..");
const PYTHON = resolve(REPO_ROOT, "packages/engines/.venv/bin/python");

export interface NewInspection {
  vin?: string | undefined;
  askingPriceUsd?: number | undefined;
  sellerStatedMileage?: number | undefined;
  listingYear?: number | undefined;
  listingMake?: string | undefined;
  listingModel?: string | undefined;
  buyerNotes?: string | undefined;
  files: { name: string; kind: "photo" | "video" | "audio" | "document"; bytes: Buffer }[];
}

export function inspectionDir(id: string): string {
  return join(WORKSPACE, id);
}

/**
 * An uploaded filename is attacker-controlled text that is about to become a
 * filesystem path. `photo.jpg` stays `photo.jpg`; `../../report.json` becomes
 * `report.json` inside media/ rather than a write outside it; a name that
 * sanitizes to nothing is refused rather than guessed at.
 *
 * The character set is the one every asset the pipeline has ever emitted
 * already uses, so this constrains uploads to the shapes the rest of the
 * system - the media route's allowlist included - is tested against.
 */
export function sanitizeUploadName(name: string): string {
  const base = name.split(/[/\\]/).pop() ?? "";
  const cleaned = base.replace(/[^A-Za-z0-9._-]/g, "_").replace(/^\.+/, "");
  if (!cleaned || !/[A-Za-z0-9]/.test(cleaned)) {
    throw new Error(`Unusable upload filename: ${JSON.stringify(name)}`);
  }
  return cleaned;
}

/** Write an inspection to disk in the layout the engines already expect. */
export async function createInspection(input: NewInspection): Promise<string> {
  const id = `insp_${randomUUID().slice(0, 8)}`;
  const dir = inspectionDir(id);
  await mkdir(join(dir, "media"), { recursive: true });
  await mkdir(join(dir, "cached"), { recursive: true });

  const assets = [];
  const used = new Set<string>();
  for (const file of input.files) {
    const cleaned = sanitizeUploadName(file.name);
    // Two uploads named photo.jpg must not silently become one file.
    let name = cleaned;
    for (let n = 2; used.has(name); n++) {
      name = cleaned.replace(/(\.[^.]+)?$/, (ext) => `_${n}${ext}`);
    }
    used.add(name);
    await writeFile(join(dir, "media", name), file.bytes);
    assets.push({
      id: name.replace(/\.[^.]+$/, ""),
      kind: file.kind,
      file: name,
    });
  }

  await writeFile(
    join(dir, "manifest.json"),
    JSON.stringify(
      {
        id,
        label: "Buyer upload",
        vin: input.vin ?? null,
        asking_price_usd: input.askingPriceUsd ?? null,
        seller_stated_mileage: input.sellerStatedMileage ?? null,
        listing_year: input.listingYear ?? null,
        listing_make: input.listingMake ?? null,
        listing_model: input.listingModel ?? null,
        buyer_notes: input.buyerNotes ?? "",
        // LAW 3: everything here arrived from the buyer. Nothing was fetched.
        provenance: "Uploaded by the buyer.",
        assets,
        comps: [],
      },
      null,
      2,
    ),
    "utf8",
  );

  return id;
}

/**
 * Analyse an inspection. Writes report.json and teaser.json beside it.
 *
 * Fixture mode by default, which means an upload with no cached responses
 * produces a report with no vision findings rather than a crash - and the
 * coverage block says what was not examined. That is the correct behaviour for
 * a build with no API key, and it is what CI exercises.
 */
export async function analyse(id: string, mode: "fixture" | "live" = "fixture"): Promise<void> {
  const dir = inspectionDir(id);
  if (!existsSync(PYTHON)) {
    throw new Error(
      `No Python environment at ${PYTHON}. Run 'pnpm run py:setup'. Production ` +
        `analysis runs on the worker host, not here.`,
    );
  }
  await run(
    PYTHON,
    [
      "-m",
      "tirekick_engines.cli",
      "inspect",
      "--dir",
      dir,
      "--mode",
      mode,
      "--out",
      join(dir, "report.json"),
      "--teaser-out",
      join(dir, "teaser.json"),
    ],
    { cwd: REPO_ROOT, env: { ...process.env, PYTHONPATH: join(REPO_ROOT, "packages/engines/src") } },
  );
}

export async function loadReport(id: string): Promise<Report | null> {
  const path = join(inspectionDir(id), "report.json");
  if (!existsSync(path)) return null;
  return parseReport(JSON.parse(await readFile(path, "utf8")));
}

export async function loadTeaser(id: string): Promise<Teaser | null> {
  const path = join(inspectionDir(id), "teaser.json");
  if (!existsSync(path)) return null;
  return parseTeaser(JSON.parse(await readFile(path, "utf8")));
}
