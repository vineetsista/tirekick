import type { NextRequest } from "next/server";
import { canRead, grantCookieName, isPubliclyReadable } from "@/lib/access";
import {
  fileStream,
  isValidInspectionId,
  isValidMediaPath,
  openMediaFile,
  parseRange,
  policyFor,
  tierFor,
} from "@/lib/media";

/**
 * The photographs, behind the same check as the page that cites them.
 *
 * Until P9 this path was a directory under public/: the report page verified a
 * grant while the evidence it renders did not, so the product's whole promise -
 * here is what it can see, and here is the picture it saw it in - was gated on
 * one side only. This handler is the other side.
 *
 * Three properties, in the order they are checked:
 *
 * 1. The URL must be well-formed before it touches the filesystem. A malformed
 *    id or path is a 404, not an error - the shape of a rejected request is
 *    not a debugging aid we owe an attacker.
 * 2. The file must be cited by the inspection's own artifacts. The media
 *    directory is not a public root; the report's citations are the entire
 *    published surface (see lib/media.ts for why the difference matters).
 * 3. The viewer must hold the tier the file needs. Denial is a 404, the same
 *    status as absence, so an unauthenticated probe cannot distinguish "this
 *    inspection exists but you may not see it" from "there is nothing here".
 *
 * Range requests get the single-range handling a browser's <audio> element
 * needs (Safari refuses to play from a server that ignores Range). Responses
 * for granted media are private and uncached; the public demo may be cached
 * briefly by anyone.
 */
export async function GET(
  request: NextRequest,
  context: { params: Promise<{ inspectionId: string; path: string[] }> },
): Promise<Response> {
  const { inspectionId, path } = await context.params;

  if (!isValidInspectionId(inspectionId) || !isValidMediaPath(path)) {
    return notFound();
  }
  const relPath = path.join("/");

  const policy = await policyFor(inspectionId);
  const tier = tierFor(policy, relPath);
  if (!tier) return notFound();

  const token = request.cookies.get(grantCookieName(inspectionId))?.value;
  if (!canRead(inspectionId, tier, token).allowed) return notFound();

  const file = await openMediaFile(inspectionId, relPath);
  if (!file) return notFound();

  const headers = new Headers({
    "Content-Type": file.contentType,
    "X-Content-Type-Options": "nosniff",
    "Accept-Ranges": "bytes",
    "Cache-Control": isPubliclyReadable(inspectionId)
      ? "public, max-age=300"
      : "private, no-store",
  });

  const range = parseRange(request.headers.get("range"), file.size);
  if (range === null) {
    headers.set("Content-Range", `bytes */${file.size}`);
    return new Response(null, { status: 416, headers });
  }
  if (range) {
    headers.set("Content-Range", `bytes ${range.start}-${range.end}/${file.size}`);
    headers.set("Content-Length", String(range.end - range.start + 1));
    return new Response(fileStream(file.fullPath, range), { status: 206, headers });
  }

  headers.set("Content-Length", String(file.size));
  return new Response(fileStream(file.fullPath), { status: 200, headers });
}

function notFound(): Response {
  return new Response(null, {
    status: 404,
    headers: { "Cache-Control": "private, no-store" },
  });
}
