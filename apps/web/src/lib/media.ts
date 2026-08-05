import { createReadStream, existsSync } from "node:fs";
import { stat } from "node:fs/promises";
import { join, resolve, sep } from "node:path";
import { Readable } from "node:stream";
import type { Report, Teaser } from "@tirekick/shared";
import { PUBLIC_DEMO_ID } from "./access";
import { inspectionDir, loadReport, loadTeaser } from "./inspections";
import { demoReport, demoTeaser } from "./report";
import type { AccessTier } from "./access";

/**
 * What the media route is allowed to serve, and from where.
 *
 * The rule is narrower than "files in the media directory": a file is servable
 * only if the inspection's own report cites it. The media directory can contain
 * things a report never mentions - `redactions.json` sidecars carrying the
 * coordinates of every face a reviewer found, raw frames left behind by a
 * crashed extraction, an upload the pipeline rejected - and a route that serves
 * "whatever is on disk under this id" publishes all of it. A route that serves
 * "what the report cites" publishes exactly the evidence the buyer was shown
 * citations for, which is the same boundary the report itself draws (LAW 1).
 *
 * The teaser tier is one file wide: the sample finding's photograph. That is
 * D-044's boundary - one complete finding crosses the paywall - applied to
 * bytes instead of JSON.
 */

const REPO_ROOT = resolve(process.cwd(), "../..");

/**
 * demo-01's media is served from fixtures/, the source of truth, rather than
 * from a copy under public/ - a file in public/ is served by the framework
 * before any route handler runs, which would mean the access check below never
 * executes for the one inspection every stranger loads first. The check must
 * run for the public id too, or it is not the same check, it is a second code
 * path that happens to agree today (D-049's exact failure shape).
 */
export function mediaRoot(inspectionId: string): string {
  if (inspectionId === PUBLIC_DEMO_ID) {
    return resolve(REPO_ROOT, "fixtures", PUBLIC_DEMO_ID, "media");
  }
  return join(inspectionDir(inspectionId), "media");
}

/**
 * An inspection id is about to become a path component. `demo-01` and
 * `insp_<hex>` both fit this shape; `..`, `.git`, an empty string, and anything
 * with a separator in it do not.
 */
export function isValidInspectionId(id: string): boolean {
  return /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(id);
}

/**
 * A requested media path must be flat, visible, and boring: no traversal, no
 * dotfiles (`.redact-cache/` lives beside real media), no separators smuggled
 * inside a segment. Every path the pipeline has ever emitted passes; nothing
 * an attacker would want to request does.
 */
export function isValidMediaPath(segments: string[]): boolean {
  if (segments.length === 0) return false;
  return segments.every(
    (s) => /^[A-Za-z0-9_-][A-Za-z0-9._-]{0,127}$/.test(s) && !s.includes(".."),
  );
}

export interface MediaPolicy {
  /** Paths readable with a report-tier grant (or on the public demo). */
  report: ReadonlySet<string>;
  /** Paths readable with any grant at all, including `owner`. */
  teaser: ReadonlySet<string>;
}

/**
 * The allowlist, derived from the artifacts themselves on every request.
 *
 * Report tier: every asset the report cites, plus the spectrogram the audio
 * section renders (it is a derived view of a cited asset, referenced by
 * `audio.spectrogramPath` rather than by an Asset row). Teaser tier: the sample
 * photograph alone.
 */
export function mediaPolicy(report: Report | null, teaser: Teaser | null): MediaPolicy {
  const reportPaths = new Set<string>();
  if (report) {
    for (const asset of report.assets) reportPaths.add(asset.path);
    if (report.audio?.spectrogramPath) reportPaths.add(report.audio.spectrogramPath);
  }
  const teaserPaths = new Set<string>();
  if (teaser?.sample) teaserPaths.add(teaser.sample.assetPath);
  // Anything the free tier shows, the paid tier must also show.
  for (const p of teaserPaths) reportPaths.add(p);
  return { report: reportPaths, teaser: teaserPaths };
}

export async function policyFor(inspectionId: string): Promise<MediaPolicy> {
  if (inspectionId === PUBLIC_DEMO_ID) return mediaPolicy(demoReport, demoTeaser);
  const [report, teaser] = await Promise.all([
    loadReport(inspectionId),
    loadTeaser(inspectionId),
  ]);
  return mediaPolicy(report, teaser);
}

/** The tier a given file needs, or null if nothing cites it. */
export function tierFor(policy: MediaPolicy, relPath: string): AccessTier | null {
  if (policy.teaser.has(relPath)) return "teaser";
  if (policy.report.has(relPath)) return "report";
  return null;
}

/**
 * Resolve a validated relative path against the media root, and refuse the
 * result unless it is still inside it. The allowlist should already make
 * escape impossible; this is the check that stays true if the allowlist ever
 * grows a hole (nothing validates the filenames a manifest declares).
 */
export function resolveInsideMediaRoot(root: string, relPath: string): string | null {
  const full = resolve(root, relPath);
  if (full !== root && !full.startsWith(root + sep)) return null;
  return full;
}

const CONTENT_TYPES: Record<string, string> = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".webp": "image/webp",
  ".gif": "image/gif",
  ".mp4": "video/mp4",
  ".mov": "video/quicktime",
  ".webm": "video/webm",
  ".wav": "audio/wav",
  ".mp3": "audio/mpeg",
  ".m4a": "audio/mp4",
  ".txt": "text/plain; charset=utf-8",
  ".pdf": "application/pdf",
};

/**
 * Unknown extensions are served as opaque bytes rather than guessed at, and
 * every response carries `X-Content-Type-Options: nosniff` at the route - a
 * buyer-uploaded file with an odd extension must never be sniffed into
 * something executable.
 */
export function contentTypeFor(relPath: string): string {
  const dot = relPath.lastIndexOf(".");
  const ext = dot === -1 ? "" : relPath.slice(dot).toLowerCase();
  return CONTENT_TYPES[ext] ?? "application/octet-stream";
}

export interface MediaFile {
  fullPath: string;
  size: number;
  contentType: string;
}

/** Stat a policy-approved file. Null means "serve a 404", never "guess". */
export async function openMediaFile(
  inspectionId: string,
  relPath: string,
): Promise<MediaFile | null> {
  const root = mediaRoot(inspectionId);
  if (!existsSync(root)) return null;
  const fullPath = resolveInsideMediaRoot(root, relPath);
  if (!fullPath) return null;
  try {
    const s = await stat(fullPath);
    if (!s.isFile()) return null;
    return { fullPath, size: s.size, contentType: contentTypeFor(relPath) };
  } catch {
    return null;
  }
}

export interface ByteRange {
  start: number;
  end: number; // inclusive
}

/**
 * Single-range parsing, which is all a browser's media element sends.
 *
 * Returns undefined when there is no usable Range header (serve the whole
 * file, 200), null when the range is syntactically valid but unsatisfiable
 * (416), and a ByteRange for the 206 path. Multi-range requests are treated
 * as no range: serving the whole file is always a correct answer to a Range
 * request, and multipart/byteranges is machinery with no caller here.
 */
export function parseRange(header: string | null, size: number): ByteRange | null | undefined {
  if (!header) return undefined;
  const m = /^bytes=(\d*)-(\d*)$/.exec(header.trim());
  if (!m || (m[1] === "" && m[2] === "")) return undefined;
  if (size === 0) return null;

  if (m[1] === "") {
    // Suffix range: last N bytes.
    const suffix = Number(m[2]);
    if (suffix === 0) return null;
    const start = Math.max(0, size - suffix);
    return { start, end: size - 1 };
  }

  const start = Number(m[1]);
  if (start >= size) return null;
  const end = m[2] === "" ? size - 1 : Math.min(Number(m[2]), size - 1);
  if (end < start) return null;
  return { start, end };
}

/**
 * A Node Readable as a web stream, for the Response body. Files here are
 * inspection media measured in megabytes; streaming from disk keeps the
 * route's memory flat without pretending this is a CDN.
 */
export function fileStream(fullPath: string, range?: ByteRange): ReadableStream {
  const nodeStream = range
    ? createReadStream(fullPath, { start: range.start, end: range.end })
    : createReadStream(fullPath);
  return Readable.toWeb(nodeStream) as ReadableStream;
}
