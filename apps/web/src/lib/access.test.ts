import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import {
  bumpRevocationEpoch,
  canReadReport,
  issueGrant,
  PUBLIC_DEMO_ID,
  revocationEpoch,
  verifyGrant,
} from "./access";
import { inspectionDir } from "./inspections";

/**
 * The lifetime of a grant, tested as a lifetime rather than as a comment.
 *
 * Until now a grant was an HMAC over the inspection id and the reason and
 * nothing else, which made it a bearer token with no end: `/access/<id>?t=...`
 * re-minted the cookie on demand, so a link forwarded once, or left in a shared
 * machine's history, or leaked in a Referer header, still opened the dossier
 * and every photograph of the seller's car two years later - long after the
 * ninety-day retention window the docstring claimed the cookie was matched to.
 * The only bound in the system was the cookie's maxAge, which is advice to a
 * browser, and the holder of the token is not obliged to use a browser.
 *
 * Every test below asserts a property of the TOKEN, not of the cookie.
 *
 * The clock arrives as a parameter, not as a stubbed global. Mocking `Date`
 * would prove the module agrees with whatever we mocked; passing an explicit
 * instant proves the comparison is real and leaves the production call sites
 * using the real clock, which is the code that actually ships.
 */

const DAY_MS = 24 * 60 * 60 * 1000;
const NOW = Date.UTC(2026, 7, 8, 12, 0, 0);

const created: string[] = [];

function scratchInspection(suffix: string): string {
  const id = `insp_accesstest_${suffix}`;
  created.push(id);
  return id;
}

afterAll(() => {
  for (const id of created) rmSync(inspectionDir(id), { recursive: true, force: true });
});

describe("a grant expires", () => {
  it("verifies a grant issued a moment ago", () => {
    // The baseline the rest of the file leans on: if a fresh grant did not
    // verify, every expiry assertion below would pass for the wrong reason.
    const id = scratchInspection("fresh");
    expect(verifyGrant(id, issueGrant(id, "paid", NOW), NOW)).toBe("paid");
  });

  it("refuses a grant issued ninety-one days ago", () => {
    // The forwarded payment link. Ninety days is the media retention window, so
    // a grant older than that opens files that are gone - or worse, files that
    // are not, belonging to a seller who was told the window had closed.
    const id = scratchInspection("stale");
    const token = issueGrant(id, "paid", NOW - 91 * DAY_MS);
    expect(verifyGrant(id, token, NOW)).toBeNull();
  });

  it("still verifies a grant issued eighty-nine days ago", () => {
    // The other direction of error. A buyer who paid on day one and comes back
    // on day eighty-nine has bought something that is still there; expiring
    // early would take a report away from the person who owns it.
    const id = scratchInspection("nearly");
    const token = issueGrant(id, "paid", NOW - 89 * DAY_MS);
    expect(verifyGrant(id, token, NOW)).toBe("paid");
  });

  it("refuses a grant stamped in the future", () => {
    // Only we can mint a signed future timestamp, so this is a broken clock
    // rather than an attack - but a token dated 2099 would be a permanent
    // bearer token again, which is the exact thing this file exists to end.
    const id = scratchInspection("future");
    const token = issueGrant(id, "paid", NOW + 30 * DAY_MS);
    expect(verifyGrant(id, token, NOW)).toBeNull();
  });

  it("closes the paid gate on an expired grant, not just verifyGrant", () => {
    // verifyGrant could be correct and unused. This asserts the reader-facing
    // check - the one the report page and the media route actually call -
    // carries the expiry through rather than consulting the reason alone.
    const id = scratchInspection("gate");
    const token = issueGrant(id, "paid", NOW - 91 * DAY_MS);
    expect(canReadReport(id, token, NOW).allowed).toBe(false);
    expect(canReadReport(id, issueGrant(id, "paid", NOW), NOW).allowed).toBe(true);
  });
});

describe("the timestamp is inside the signature", () => {
  it("refuses a token whose timestamp has been edited forward", () => {
    // The whole point of signing the instant rather than appending it. If the
    // timestamp sat beside the signature, the holder of an expired link would
    // renew it by typing a bigger number, and the expiry above would be
    // decoration.
    const id = scratchInspection("tamper");
    const expired = issueGrant(id, "paid", NOW - 91 * DAY_MS);
    const [reason, , signature] = expired.split(".");
    const forged = `${reason}.${Math.floor(NOW / 1000)}.${signature}`;
    expect(verifyGrant(id, forged, NOW)).toBeNull();
  });

  it("refuses a token whose timestamp has been edited at all", () => {
    const id = scratchInspection("tamper2");
    const fresh = issueGrant(id, "paid", NOW);
    const [reason, issuedAt, signature] = fresh.split(".");
    const forged = `${reason}.${Number(issuedAt) - 1}.${signature}`;
    expect(verifyGrant(id, forged, NOW)).toBeNull();
  });

  it("refuses a garbage timestamp instead of reading a number out of it", () => {
    // `parseInt("12abc")` is 12 and `Number("")` is 0, and either would be a
    // timestamp we invented on the holder's behalf. Unparseable means deny.
    const id = scratchInspection("garbage");
    const [reason, , signature] = issueGrant(id, "paid", NOW).split(".");
    for (const stamp of ["", "abc", "12abc", "-1", "1e9", " 1754", "1754.5", "0x10", "٤٢"]) {
      expect(verifyGrant(id, `${reason}.${stamp}.${signature}`, NOW)).toBeNull();
    }
  });

  it("still refuses the empty, malformed and truncated tokens it always did", () => {
    // Carried over from flow.test.ts: the new three-part format must not have
    // opened a shape that the two-part parser used to reject.
    const id = scratchInspection("shapes");
    for (const token of [
      "",
      "paid",
      "paid.",
      ".sig",
      "garbage",
      "paid.short",
      "paid.1.2.3",
      "..",
      "paid..sig",
      "..sig",
    ]) {
      expect(verifyGrant(id, token, NOW)).toBeNull();
    }
    expect(verifyGrant(id, undefined, NOW)).toBeNull();
  });
});

describe("a grant can be revoked", () => {
  it("verifies against an inspection that has never been revoked", () => {
    // The absent-file case, stated on its own because it is the one that
    // decides whether this feature is deployable: every grant already in a
    // cookie belongs to an inspection with no epoch file beside it, and a
    // missing file that denied would log the whole existing customer base out.
    const id = scratchInspection("noepoch");
    expect(revocationEpoch(id)).toBe(0);
    expect(verifyGrant(id, issueGrant(id, "paid", NOW), NOW)).toBe("paid");
  });

  it("invalidates one inspection's grants without touching another's", () => {
    // The reason the epoch is per-inspection rather than a global secret
    // rotation: revoking a leaked link for one car must not sign every other
    // buyer out of the report they paid for this morning.
    const revoked = scratchInspection("revoked");
    const bystander = scratchInspection("bystander");

    const revokedGrant = issueGrant(revoked, "paid", NOW);
    const bystanderGrant = issueGrant(bystander, "paid", NOW);

    expect(bumpRevocationEpoch(revoked)).toBe(1);

    expect(verifyGrant(revoked, revokedGrant, NOW)).toBeNull();
    expect(verifyGrant(bystander, bystanderGrant, NOW)).toBe("paid");
  });

  it("issues a grant that survives the revocation it comes after", () => {
    // Revocation must not be a one-way door. Support revokes a leaked link,
    // then re-issues one to the buyer who actually paid; if the new grant died
    // with the old one the only remedy left would be a refund.
    const id = scratchInspection("reissue");
    bumpRevocationEpoch(id);
    expect(verifyGrant(id, issueGrant(id, "paid", NOW), NOW)).toBe("paid");
  });

  it("denies when the epoch file exists but cannot be read as a number", () => {
    // A file somebody wrote by hand, or a half-written file, is not the same
    // as no file. Absence means "never revoked"; nonsense means we do not know
    // whether this inspection was revoked, and D-017 sends an unclear reading
    // to the cautious side - here, deny, because the buyer can ask for a new
    // link and the seller cannot un-leak a photograph.
    const id = scratchInspection("corrupt");
    mkdirSync(inspectionDir(id), { recursive: true });
    const token = issueGrant(id, "paid", NOW);
    writeFileSync(join(inspectionDir(id), "grant-epoch"), "not a number", "utf8");
    expect(revocationEpoch(id)).toBeNull();
    expect(verifyGrant(id, token, NOW)).toBeNull();
  });
});

describe("the public demo does not expire", () => {
  it("keeps a demo grant on the public inspection valid past the window", () => {
    // Deliberate, and narrow. demo-01 is the sample a stranger reads before
    // they trust us with a VIN; if its grant aged out, the demo would go dark
    // ninety days after a deploy and nobody would notice until a customer did.
    const token = issueGrant(PUBLIC_DEMO_ID, "demo", NOW - 400 * DAY_MS);
    expect(verifyGrant(PUBLIC_DEMO_ID, token, NOW)).toBe("demo");
  });

  it("does not extend that exemption to other reasons on the demo id", () => {
    // The exemption is for the public sample, not for the id. A paid grant is
    // a paid grant wherever it points, and letting the demo's exemption widen
    // to every reason would resurrect the permanent bearer token under a
    // different name.
    const token = issueGrant(PUBLIC_DEMO_ID, "paid", NOW - 91 * DAY_MS);
    expect(verifyGrant(PUBLIC_DEMO_ID, token, NOW)).toBeNull();
  });

  it("does not extend that exemption to demo grants on private inspections", () => {
    // A `demo` grant handed to a partner to look at a real customer's car is
    // an ordinary grant over ordinary photographs, and it expires with them.
    const id = scratchInspection("privatedemo");
    const token = issueGrant(id, "demo", NOW - 91 * DAY_MS);
    expect(verifyGrant(id, token, NOW)).toBeNull();
  });

  it("still refuses a revoked demo grant on the public inspection", () => {
    // Exempt from the clock is not exempt from us. If the sample dossier ever
    // has to be pulled, bumping its epoch must pull it.
    // Only the epoch file is removed afterwards, and the directory only if this
    // test is what created it: demo-01 is a real id, and a test that rm -rf's a
    // real inspection directory is a worse bug than the one it is checking for.
    const dir = inspectionDir(PUBLIC_DEMO_ID);
    const dirExisted = existsSync(dir);
    const token = issueGrant(PUBLIC_DEMO_ID, "demo", NOW);
    try {
      bumpRevocationEpoch(PUBLIC_DEMO_ID);
      expect(verifyGrant(PUBLIC_DEMO_ID, token, NOW)).toBeNull();
    } finally {
      rmSync(join(dir, "grant-epoch"), { force: true });
      if (!dirExisted) rmSync(dir, { recursive: true, force: true });
    }
  });
});
