import { execFileSync } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { NextRequest } from "next/server";
import { afterAll, describe, expect, it, vi } from "vitest";
import { GET as mediaGET } from "@/app/f/[inspectionId]/[...path]/route";
import { canRead, canReadReport, grantCookieName, issueGrant, verifyGrant } from "./access";
import { analyse, createInspection, inspectionDir, loadReport, loadTeaser } from "./inspections";

/**
 * The end-to-end test LAW 7 has required since P0 and nobody wrote.
 *
 * Upload -> analyse -> free teaser -> acknowledge -> grant -> paid dossier, driven
 * through the real modules rather than mocks. It uploads actual bytes, shells out
 * to the actual Python engines, and reads the actual artifacts off disk.
 *
 * What it does NOT cover, stated plainly so nobody reads more into a green tick
 * than is there: it drives the flow, not a browser. There is no click, no
 * network, and no Stripe. A regression in React rendering or in a form handler
 * would not fail this test - the component suites cover those separately.
 *
 * Six phases were tagged with "ALL GATES GREEN" while this clause of LAW 7 went
 * unmet, because gates.sh encoded the tests that existed rather than the tests
 * the law names. That is fixed too: see `test_laws.py::test_law_7_named_tests_exist`.
 */

const REPO_ROOT = resolve(process.cwd(), "../..");
const PYTHON = resolve(REPO_ROOT, "packages/engines/.venv/bin/python");
const created: string[] = [];

afterAll(() => {
  for (const id of created) rmSync(inspectionDir(id), { recursive: true, force: true });
});

async function fixtureBytes(name: string): Promise<Buffer> {
  return readFile(join(REPO_ROOT, "fixtures/demo-01/media", name));
}

const hasEngines = existsSync(PYTHON);

describe.skipIf(!hasEngines)("upload -> paid dossier", () => {
  it("runs the whole flow and gates the paid report on a grant", async () => {
    // 1. Upload. Real bytes, written to a real inspection directory.
    const id = await createInspection({
      vin: "1HGCR2F37DA000000",
      askingPriceUsd: 8900,
      sellerStatedMileage: 128540,
      listingYear: 2013,
      listingMake: "Honda",
      listingModel: "Accord",
      files: [
        { name: "photo_01.jpg", kind: "photo", bytes: await fixtureBytes("photo_01.jpg") },
        { name: "history_01.txt", kind: "document", bytes: await fixtureBytes("history_01.txt") },
      ],
    });
    created.push(id);
    expect(existsSync(join(inspectionDir(id), "manifest.json"))).toBe(true);

    // 2. Analyse. Fixture mode, so no key and no network.
    await analyse(id);

    const report = await loadReport(id);
    const teaser = await loadTeaser(id);
    expect(report).not.toBeNull();
    expect(teaser).not.toBeNull();

    // 3. The upload had no cached vision responses, so there are no vision
    //    findings - and the report says what was not examined rather than
    //    implying the car is clean. This is the honest empty-handed case.
    expect(report!.findings.every((f) => f.engine !== "vision")).toBe(true);
    expect(report!.verdict.couldNotAssess.length).toBeGreaterThan(0);
    expect(report!.systems.every((s) => s.status !== "no_issues_visible")).toBe(true);

    // The document it DID get was read: the paperwork reports structural damage,
    // which must arrive as a mechanic referral rather than a finding (LAW 2).
    expect(report!.mechanicReferrals.some((r) => r.system === "structure")).toBe(true);

    // 4. The free teaser carries no paid content.
    const blob = JSON.stringify(teaser);
    for (const finding of report!.findings) {
      expect(blob).not.toContain(finding.title);
    }

    // 5. Without a grant, the paid report is not readable.
    expect(canReadReport(id, undefined).allowed).toBe(false);
    expect(canReadReport(id, "paid.forged-signature").allowed).toBe(false);

    // 6. With one, it is.
    const grant = issueGrant(id, "paid");
    const access = canReadReport(id, grant);
    expect(access.allowed).toBe(true);
    expect(access.reason).toBe("paid");

    // 7. The photographs obey the same grant as the page (P9, D-052). The
    //    uploaded document is a cited asset; without the cookie its bytes are
    //    a 404, with it they are the exact bytes that went in.
    const doc = report!.assets.find((a) => a.kind === "document")!;
    const url = `http://localhost/f/${id}/${doc.path}`;
    const params = { params: Promise.resolve({ inspectionId: id, path: [doc.path] }) };

    const anonymous = await mediaGET(new NextRequest(url), params);
    expect(anonymous.status).toBe(404);

    const granted = await mediaGET(
      new NextRequest(url, {
        headers: { cookie: `${grantCookieName(id)}=${grant}` },
      }),
      params,
    );
    expect(granted.status).toBe(200);
    expect(granted.headers.get("cache-control")).toBe("private, no-store");
    const served = Buffer.from(await granted.arrayBuffer());
    expect(served.equals(await fixtureBytes("history_01.txt"))).toBe(true);

    // 8. The uploader's own grant opens the teaser tier, not the dossier.
    const owner = issueGrant(id, "owner");
    expect(canRead(id, "teaser", owner).allowed).toBe(true);
    expect(canRead(id, "report", owner).allowed).toBe(false);
  }, 120_000);
});

describe("access grants", () => {
  it("does not let a grant for one inspection open another", () => {
    const grant = issueGrant("insp_aaaa", "paid");
    expect(verifyGrant("insp_aaaa", grant)).toBe("paid");
    expect(verifyGrant("insp_bbbb", grant)).toBeNull();
  });

  it("does not let a weaker reason be replayed as payment", () => {
    // The reason is inside the signature, not beside it, so editing the prefix
    // invalidates the token rather than upgrading it.
    const demo = issueGrant("insp_aaaa", "demo");
    const forged = demo.replace(/^demo/, "paid");
    expect(verifyGrant("insp_aaaa", forged)).toBeNull();
  });

  it("rejects an empty, malformed or truncated token", () => {
    for (const token of ["", "paid", "paid.", ".sig", "garbage", "paid.short"]) {
      expect(verifyGrant("insp_aaaa", token)).toBeNull();
    }
    expect(verifyGrant("insp_aaaa", undefined)).toBeNull();
  });

  it("keeps exactly one publicly readable inspection, and names it", () => {
    // A stranger has to be able to see what they would be buying. That is a
    // product decision, so it is one greppable id rather than an inferred flag.
    expect(canReadReport("demo-01", undefined).allowed).toBe(true);
    expect(canReadReport("demo-02", undefined).allowed).toBe(false);
  });

  it("refuses to sign with the development key in production", () => {
    // A well-known signing key is the same as no signing at all, so the
    // production path must fail loudly rather than fall back.
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("TIREKICK_GRANT_SECRET", "");
    try {
      expect(() => issueGrant("insp_aaaa", "paid")).toThrow(/TIREKICK_GRANT_SECRET/);
    } finally {
      vi.unstubAllEnvs();
    }
  });
});

describe("the engines are reachable from the web app", () => {
  it.skipIf(!hasEngines)("can invoke the CLI it depends on", () => {
    const out = execFileSync(PYTHON, ["-m", "tirekick_engines.cli", "--help"], {
      cwd: REPO_ROOT,
      env: { ...process.env, PYTHONPATH: join(REPO_ROOT, "packages/engines/src") },
    }).toString();
    expect(out).toContain("inspect");
    expect(out).toContain("bench");
  });
});
