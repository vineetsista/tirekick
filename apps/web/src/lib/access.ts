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

export function canReadReport(
  inspectionId: string,
  token: string | undefined,
): { allowed: boolean; reason: GrantReason | "public" | null } {
  if (isPubliclyReadable(inspectionId)) return { allowed: true, reason: "public" };
  const reason = verifyGrant(inspectionId, token);
  return { allowed: reason !== null, reason };
}
