import { createHmac, timingSafeEqual } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { inspectionDir } from "./inspections";

/**
 * Who is allowed to read a paid dossier, and for how long.
 *
 * Until P6 the answer was "anyone who guesses the URL", because `/report/demo-01`
 * was a static route with no check on it. The teaser projection was correct - the
 * free payload genuinely never contained the findings - but the paid page itself
 * was open, which is a different hole and a worse one. This closes it.
 *
 * A grant is an HMAC over the inspection id, the reason access was given, the
 * instant it was issued, and the inspection's revocation epoch. The first three
 * are stateless; the fourth is one small file on disk, read on every verify.
 *
 * The middle two are the P11 repair, and they are a repair of this file lying to
 * its reader. Until now the payload was the id and the reason and nothing else:
 * no issued-at, no expiry, no nonce. The only time bound anywhere in the system
 * was the cookie's maxAge, which is advice to a browser and nothing more, while
 * the docstring on that constant described ninety days as a lifetime matched to
 * the media retention window. It was not a lifetime. A payment-confirmation link
 * forwarded once, or sitting in a shared machine's history, or leaked through a
 * Referer header on the pre-cookie hop, still resolved two years later: the same
 * HMAC recomputed, the cookie re-minted for another ninety days, and the holder
 * read the dossier and every photograph of the seller's car and driveway. That
 * is a claim - "a grant lasts ninety days" - that nothing checked, which is the
 * defect this product keeps finding in itself.
 *
 * Everything the holder could otherwise edit is inside the signature rather than
 * beside it: the reason, so a `demo` grant cannot be replayed as a `paid` one by
 * rewriting a prefix, and the timestamp, so an expired link cannot be renewed by
 * typing a bigger number.
 *
 * Changing the payload shape invalidates every grant minted before this deploy.
 * That is the intended consequence and not a migration to be smoothed over: the
 * old tokens are precisely the ones with no end on them.
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

/**
 * Where a revocation is recorded: a counter file beside the inspection itself.
 *
 * There is no database yet, and inventing one here would be a bigger lie than
 * the one being fixed. A file named for the inspection it revokes is the honest
 * local implementation of "revoke this grant and nobody else's", and when the
 * row lands the two functions below become a SELECT and an UPDATE without the
 * callers noticing.
 *
 * Bumping the global signing secret would also revoke the leaked link. It would
 * revoke every other buyer's link in the same motion, which is why nobody would
 * ever actually do it, which is why `grep -rn revok` over this source used to
 * return one hit and it was a comment claiming revocation worked.
 */
const REVOCATION_EPOCH_FILE = "grant-epoch";

function revocationEpochPath(inspectionId: string): string {
  return join(inspectionDir(inspectionId), REVOCATION_EPOCH_FILE);
}

/**
 * How many times this inspection's grants have been revoked. Null means the
 * file is there and unreadable, and the caller must deny.
 *
 * The two failure directions here are not symmetric, so they are separated on
 * purpose. A MISSING file means "never revoked" and reads as 0, because every
 * grant already in a browser belongs to an inspection with no such file beside
 * it, and a missing file that denied would sign out the entire existing
 * customer base at deploy time - a self-inflicted outage dressed as security.
 * A file that exists but does not parse is a different thing: somebody, or some
 * half-finished write, put something there, and we cannot tell whether this
 * inspection was revoked. D-017 sends an unclear reading to the cautious side,
 * and here the cautious side is deny - a buyer can be issued a new link, while
 * a seller cannot un-leak a photograph of their driveway.
 */
export function revocationEpoch(inspectionId: string): number | null {
  let raw: string;
  try {
    raw = readFileSync(revocationEpochPath(inspectionId), "utf8");
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return 0;
    return null;
  }
  const trimmed = raw.trim();
  if (!/^[0-9]{1,12}$/.test(trimmed)) return null;
  return Number(trimmed);
}

/**
 * Revoke every grant outstanding for one inspection. Returns the new epoch.
 *
 * Exported because a revocation nobody can perform is the same claim-with-
 * nothing-behind-it this file was full of: support has to be able to call it
 * when a buyer says they forwarded the link to the wrong address.
 *
 * Re-issuing after a bump works and is meant to: the new grant is signed
 * against the new epoch, so revocation is a door that closes, not one that
 * locks the paying customer out with the leak.
 */
export function bumpRevocationEpoch(inspectionId: string): number {
  const current = revocationEpoch(inspectionId);
  // An unreadable epoch file is already denying everything; bumping past it
  // must not be a way to accidentally reset it to a value grants can match.
  const next = (current ?? 0) + 1;
  const dir = inspectionDir(inspectionId);
  mkdirSync(dir, { recursive: true });
  writeFileSync(revocationEpochPath(inspectionId), `${next}\n`, "utf8");
  return next;
}

function sign(inspectionId: string, reason: GrantReason, issuedAt: number, epoch: number): string {
  const payload = [inspectionId, reason, issuedAt, epoch].join(SEPARATOR);
  return createHmac("sha256", signingKey()).update(payload).digest("base64url");
}

/**
 * Mint a grant. `now` is a parameter, and that is the whole seam.
 *
 * The tests need to ask what happens on day ninety-one without waiting ninety
 * one days, and the alternative - stubbing the global `Date` - proves only that
 * the module agrees with the stub. An injected instant leaves every production
 * call site reading the real clock, which is the code that actually ships, and
 * still lets a test state the arithmetic it believes in.
 */
export function issueGrant(
  inspectionId: string,
  reason: GrantReason,
  now: number = Date.now(),
): string {
  const issuedAt = Math.floor(now / 1000);
  const epoch = revocationEpoch(inspectionId) ?? 0;
  const signature = sign(inspectionId, reason, issuedAt, epoch);
  return `${reason}${SEPARATOR}${issuedAt}${SEPARATOR}${signature}`;
}

/**
 * A clock that disagrees with itself must not mint an immortal token.
 *
 * A timestamp in the future is inside the signature, so it came from us: a host
 * whose clock ran fast, not an attacker. Five minutes of tolerance covers the
 * skew between two machines that both think they have NTP; anything beyond that
 * is refused, because a grant stamped 2099 is the permanent bearer token this
 * file just finished removing.
 */
const GRANT_CLOCK_SKEW_SECONDS = 5 * 60;

/**
 * Verify a grant. Returns the reason it was issued for, or null.
 *
 * Every unclear reading returns null. A token that is malformed, truncated, or
 * carries a timestamp we cannot parse is denied rather than guessed at:
 * `Number("")` is 0 and `parseInt("12abc")` is 12, and either would be a
 * timestamp we invented on the holder's behalf and then trusted.
 *
 * The signature is compared with `timingSafeEqual` rather than `===`. The
 * practical risk of a timing attack on a report token is small; using the
 * constant-time comparison costs nothing and means the next person to copy this
 * function into somewhere that matters copies the right thing.
 */
export function verifyGrant(
  inspectionId: string,
  token: string | undefined,
  now: number = Date.now(),
): GrantReason | null {
  if (!token) return null;

  const parts = token.split(SEPARATOR);
  if (parts.length !== 3) return null;
  const [rawReason, rawIssuedAt, signature] = parts;
  // Three parts can still be three empty strings: `"..".split(".")` is
  // `["", "", ""]`. Each check below already rejects an empty field on its own
  // accident - the reason allowlist, the digit pattern, the length compare -
  // and saying it once here means that stays true if any one of them is later
  // rewritten. It is also what makes these three genuinely strings instead of
  // a cast that tells the type checker to stop worrying.
  if (!rawReason || !rawIssuedAt || !signature) return null;

  const reason = rawReason as GrantReason;
  if (!["paid", "owner", "demo"].includes(reason)) return null;

  // Digits only, and a bounded number of them. This is the check that keeps a
  // hand-edited timestamp from being coerced into something arithmetic will
  // happily compare.
  if (!/^[0-9]{1,12}$/.test(rawIssuedAt)) return null;
  const issuedAt = Number(rawIssuedAt);

  const epoch = revocationEpoch(inspectionId);
  if (epoch === null) return null;

  const expected = sign(inspectionId, reason, issuedAt, epoch);
  const a = Buffer.from(signature);
  const b = Buffer.from(expected);
  if (a.length !== b.length) return null;
  if (!timingSafeEqual(a, b)) return null;

  // The signature only proves we minted this. Whether it is still alive is a
  // separate question, and it is the one that was never asked before P11.
  const nowSeconds = Math.floor(now / 1000);
  if (issuedAt > nowSeconds + GRANT_CLOCK_SKEW_SECONDS) return null;
  if (grantExpires(inspectionId, reason) && nowSeconds - issuedAt > GRANT_COOKIE_MAX_AGE_SECONDS) {
    return null;
  }

  return reason;
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

/**
 * One grant is exempt from the ninety-day clock, deliberately and narrowly: a
 * `demo` grant on the one public inspection.
 *
 * demo-01 is the sample a stranger reads before they trust us with a VIN. Its
 * media is the fixture, checked into the repository, and it is not subject to
 * the retention window the expiry is derived from - so an expiring demo grant
 * would take the public sample dark ninety days after a deploy, and nobody
 * would find out until a customer did. That is the failure this exemption
 * prevents, and it is written down here rather than left to fall out of the
 * arithmetic somewhere else.
 *
 * The exemption is the intersection of the reason and the id, not either alone.
 * A `paid` grant is a paid grant wherever it points, and a `demo` grant handed
 * to a partner to look at a real customer's car is an ordinary grant over
 * ordinary photographs of somebody's driveway; both expire. Widening this to
 * the whole id, or to the whole reason, would restore the permanent bearer
 * token under a friendlier name.
 *
 * Note what it is not exempt from: revocation, and the future-timestamp check.
 * If the sample dossier ever has to be pulled, bumping its epoch pulls it.
 */
function grantExpires(inspectionId: string, reason: GrantReason): boolean {
  return !(reason === "demo" && inspectionId === PUBLIC_DEMO_ID);
}

export function canRead(
  inspectionId: string,
  tier: AccessTier,
  token: string | undefined,
  now: number = Date.now(),
): { allowed: boolean; reason: GrantReason | "public" | null } {
  if (isPubliclyReadable(inspectionId)) return { allowed: true, reason: "public" };
  const reason = verifyGrant(inspectionId, token, now);
  if (reason === null) return { allowed: false, reason: null };
  return { allowed: TIER_REASONS[tier].includes(reason), reason };
}

export function canReadReport(
  inspectionId: string,
  token: string | undefined,
  now: number = Date.now(),
): { allowed: boolean; reason: GrantReason | "public" | null } {
  return canRead(inspectionId, "report", token, now);
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
 * How long a grant lives: the media retention window itself (UNIT_ECONOMICS
 * assumes 90-day retention). A grant that outlives the files it opens would
 * promise access to bytes that are gone.
 *
 * This constant is now used twice, and the second use is the one that means
 * anything. It is the cookie's `maxAge`, which is a request that a browser
 * forget the token - and browsers are not the threat, because a forwarded link
 * is read by whoever holds it however they like. It is ALSO the bound checked
 * inside `verifyGrant` against the signed issued-at, which is the thing an
 * expired token cannot argue with. Until P11 only the first existed, and this
 * docstring described the second.
 */
export const GRANT_COOKIE_MAX_AGE_SECONDS = 90 * 24 * 60 * 60;
