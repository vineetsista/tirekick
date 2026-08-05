import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Who is allowed to read a paid dossier.
 *
 * Until P6 the answer was "anyone who guesses the URL", because `/report/demo-01`
 * was a static route with no check on it. The teaser projection was correct - the
 * free payload genuinely never contained the findings - but the paid page itself
 * was open, which is a different hole and a worse one. This closes it.
 *
 * A grant is an HMAC over the inspection id and the reason access was given. It
 * is stateless on purpose: there is no database yet, and a signed token needs no
 * lookup to verify. When persistence lands this becomes a row, and the interface
 * here does not have to change.
 *
 * The reason is carried inside the signature rather than beside it, so a
 * `disclaimer` grant cannot be replayed as a `paid` one by editing a query
 * parameter.
 */

export type GrantReason = "paid" | "owner" | "demo";

/**
 * What a grant opens.
 *
 * `report` is the paid dossier and every photograph it cites. `teaser` is the
 * free projection and exactly one photograph - the sample finding's. The tiers
 * exist because the person who uploaded the car has to see the teaser before
 * they have paid for anything, and nothing about an upload is public: an
 * unpaid stranger with the URL gets neither tier.
 *
 * - `paid` opens both. The buyer bought the report; the media in it is theirs
 *   to read.
 * - `demo` opens both. It is issued deliberately, by us, to show a specific
 *   person a specific dossier - support, a partner - and is distinguishable
 *   from `paid` so a giveaway is never mistaken for revenue.
 * - `owner` opens the teaser only. It is issued to the uploader at upload
 *   time. They already possess their own photographs; what they have not paid
 *   for is the analysis, so the report tier stays shut.
 */
export type AccessTier = "teaser" | "report";

const TIER_REASONS: Record<AccessTier, readonly GrantReason[]> = {
  report: ["paid", "demo"],
  teaser: ["paid", "demo", "owner"],
};

const SEPARATOR = ".";

/**
 * Signing key.
 *
 * In development this falls back to a fixed string so the flow runs with no
 * setup. In production an unset key is a hard failure rather than a fallback:
 * a well-known signing key is the same as no signing at all, and the failure
 * mode of guessing wrong here is that every paid report is free forever.
 */
function signingKey(): string {
  const configured = process.env.TIREKICK_GRANT_SECRET;
  if (configured) return configured;

  if (process.env.NODE_ENV === "production") {
    throw new Error(
      "TIREKICK_GRANT_SECRET is not set. Refusing to sign access grants with a " +
        "known development key in production - that would make every paid report " +
        "readable by anyone who has read this source file.",
    );
  }
  return "dev-only-insecure-key-not-for-production";
}

export function issueGrant(inspectionId: string, reason: GrantReason): string {
  const payload = `${inspectionId}${SEPARATOR}${reason}`;
  const signature = createHmac("sha256", signingKey()).update(payload).digest("base64url");
  return `${reason}${SEPARATOR}${signature}`;
}

/**
 * Verify a grant. Returns the reason it was issued for, or null.
 *
 * Compared with `timingSafeEqual` rather than `===`. The practical risk of a
 * timing attack on a report token is small; using the constant-time comparison
 * costs nothing and means the next person to copy this function into somewhere
 * that matters copies the right thing.
 */
export function verifyGrant(inspectionId: string, token: string | undefined): GrantReason | null {
  if (!token) return null;

  const separatorIndex = token.indexOf(SEPARATOR);
  if (separatorIndex <= 0) return null;

  const reason = token.slice(0, separatorIndex) as GrantReason;
  if (!["paid", "owner", "demo"].includes(reason)) return null;

  const expected = issueGrant(inspectionId, reason);
  const a = Buffer.from(token);
  const b = Buffer.from(expected);
  if (a.length !== b.length) return null;

  return timingSafeEqual(a, b) ? reason : null;
}

/**
 * The one inspection readable without a grant.
 *
 * A public sample is a product decision, not a hole - a stranger has to be able
 * to see what they would be buying. It is named explicitly here rather than
 * inferred from a flag, so there is exactly one id in the codebase that is free
 * and it is greppable.
 */
export const PUBLIC_DEMO_ID = "demo-01";

export function isPubliclyReadable(inspectionId: string): boolean {
  return inspectionId === PUBLIC_DEMO_ID;
}

export function canRead(
  inspectionId: string,
  tier: AccessTier,
  token: string | undefined,
): { allowed: boolean; reason: GrantReason | "public" | null } {
  if (isPubliclyReadable(inspectionId)) return { allowed: true, reason: "public" };
  const reason = verifyGrant(inspectionId, token);
  if (reason === null) return { allowed: false, reason: null };
  return { allowed: TIER_REASONS[tier].includes(reason), reason };
}

export function canReadReport(
  inspectionId: string,
  token: string | undefined,
): { allowed: boolean; reason: GrantReason | "public" | null } {
  return canRead(inspectionId, "report", token);
}

/**
 * The cookie a grant travels in.
 *
 * A photograph is fetched by an `<img>` tag, which sends no headers we control
 * and can carry no query string we would want cached in referrer logs - so the
 * grant rides a cookie. One cookie per inspection, named for it, so holding a
 * grant for one report attaches nothing to requests for another.
 */
export function grantCookieName(inspectionId: string): string {
  return `tk_grant_${inspectionId}`;
}

/**
 * How long a grant cookie lives: the media retention window itself
 * (UNIT_ECONOMICS assumes 90-day retention). A cookie that outlives the files
 * it opens would promise access to bytes that are gone.
 */
export const GRANT_COOKIE_MAX_AGE_SECONDS = 90 * 24 * 60 * 60;
