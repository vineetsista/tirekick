import { NextResponse, type NextRequest } from "next/server";
import {
  GRANT_COOKIE_MAX_AGE_SECONDS,
  grantCookieName,
  verifyGrant,
} from "@/lib/access";
import { isValidInspectionId } from "@/lib/media";

/**
 * Where a grant becomes a cookie.
 *
 * A grant is issued as a link - after a payment, at upload time - and a link
 * cannot set a header. This route is the exchange: verify the token in the
 * query string, move it into an httpOnly cookie scoped to the site, and send
 * the visitor to the page the grant opens. After this hop the token never
 * appears in a URL again, which is the point - URLs leak through referrers,
 * history sync, and screenshots; an httpOnly cookie does none of those.
 *
 * An invalid token is a 404, indistinguishable from an id that never existed.
 */
export async function GET(
  request: NextRequest,
  context: { params: Promise<{ inspectionId: string }> },
): Promise<Response> {
  const { inspectionId } = await context.params;
  if (!isValidInspectionId(inspectionId)) return notFound();

  const token = request.nextUrl.searchParams.get("t") ?? undefined;
  const reason = verifyGrant(inspectionId, token);
  if (reason === null) return notFound();

  // `owner` opens the teaser tier only, so that is where it lands.
  const fallback =
    reason === "owner" ? `/teaser/${inspectionId}` : `/report/${inspectionId}`;
  const next = safeInternalPath(request.nextUrl.searchParams.get("next")) ?? fallback;

  const response = NextResponse.redirect(new URL(next, request.nextUrl.origin), 303);
  response.cookies.set({
    name: grantCookieName(inspectionId),
    value: token!,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: GRANT_COOKIE_MAX_AGE_SECONDS,
  });
  return response;
}

/**
 * `next` must stay on this site. A path that does not start with exactly one
 * slash is refused: `//evil.example` is a protocol-relative URL and
 * `https://...` is an absolute one, and either would turn this route into an
 * open redirect that launders a hostile link through our domain.
 */
function safeInternalPath(next: string | null): string | null {
  if (!next) return null;
  if (!next.startsWith("/") || next.startsWith("//") || next.includes("\\")) return null;
  return next;
}

function notFound(): Response {
  return new Response(null, {
    status: 404,
    headers: { "Cache-Control": "private, no-store" },
  });
}
