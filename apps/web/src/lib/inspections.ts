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

/**
 * Claim a directory nobody else has, and return its id.
 *
 * The id used to be `insp_${randomUUID().slice(0, 8)}` - 32 bits - written
 * straight into `mkdir(..., { recursive: true })`, which succeeds silently on a
 * directory that already exists. Two inspections drawing the same eight hex
 * characters therefore did not collide loudly; they MERGED. The second upload's
 * media landed beside the first's, the second manifest overwrote the first, and
 * because a grant is an HMAC over the inspection id, whoever held either grant
 * held both - so the failure is not a lost upload, it is one stranger reading
 * another stranger's photographs.
 *
 * Thirty-two bits sounds like a lot and is not: the birthday bound puts an
 * even-odds collision at about 77,000 inspections, and the whole point of the
 * product is to be used more than 77,000 times.
 *
 * Two changes, and the second is the one that matters. The id is now a whole
 * UUID's worth of randomness, which makes a collision negligible - and
 * `recursive: false` makes the filesystem answer the question instead of us,
 * because "negligible" is a probability argument and EEXIST is a fact. A
 * probability argument is what the old code was already relying on.
 */
async function claimInspectionDir(): Promise<{ id: string; dir: string }> {
  for (let attempt = 0; attempt < 5; attempt++) {
    const id = `insp_${randomUUID().replaceAll("-", "")}`;
    const dir = inspectionDir(id);
    try {
      await mkdir(dir, { recursive: false });
      return { id, dir };
    } catch (err) {
      // EEXIST is the collision this exists to catch: try again with new
      // randomness. Anything else - a missing workspace, a read-only disk - is
      // not a collision and must not be retried into a confusing five-attempt
      // failure that hides what actually went wrong.
      if ((err as NodeJS.ErrnoException).code === "EEXIST") continue;
      if ((err as NodeJS.ErrnoException).code === "ENOENT") {
        await mkdir(WORKSPACE, { recursive: true });
        attempt--;
        continue;
      }
      throw err;
    }
  }
  throw new Error(
    "Could not claim an unused inspection directory in five attempts. That is not " +
      "a collision - at this id width it is a workspace that cannot be written to.",
  );
}

/** Write an inspection to disk in the layout the engines already expect. */
export async function createInspection(input: NewInspection): Promise<string> {
  const { id, dir } = await claimInspectionDir();
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
