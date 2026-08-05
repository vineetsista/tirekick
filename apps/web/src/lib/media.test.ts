import { existsSync, mkdirSync, rmSync } from "node:fs";
import { copyFile, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { NextRequest } from "next/server";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { GET as mediaGET } from "@/app/f/[inspectionId]/[...path]/route";
import { GET as accessGET } from "@/app/access/[inspectionId]/route";
import { grantCookieName, issueGrant } from "./access";
import { inspectionDir, sanitizeUploadName } from "./inspections";
import {
  contentTypeFor,
  isValidInspectionId,
  isValidMediaPath,
  mediaPolicy,
  parseRange,
  tierFor,
} from "./media";
import { demoReport, demoTeaser } from "./report";

/**
 * The media gate, tested as the thing it is: an access check in front of bytes.
 *
 * Two kinds of case here. The public demo, where the check must let a stranger
 * through and still refuse to serve anything the report does not cite; and a
 * private workspace inspection, where every tier boundary - none, owner, paid -
 * is probed with real HTTP objects against real files on disk.
 *
 * Every deny in this file asserts 404, not 403, on purpose: the route must not
 * confirm to an unauthenticated prober that an inspection exists (D-052).
 */

const REPO_ROOT = resolve(process.cwd(), "../..");
const FIXTURE_MEDIA = join(REPO_ROOT, "fixtures/demo-01/media");

const GATED_ID = "insp_mediagate";
const SAMPLE_PATH = demoTeaser.sample!.assetPath; // photo_05.jpg for the fixture

function requestFor(
  url: string,
  opts: { cookie?: string; range?: string } = {},
): NextRequest {
  const headers = new Headers();
  if (opts.cookie) headers.set("cookie", opts.cookie);
  if (opts.range) headers.set("range", opts.range);
  return new NextRequest(`http://localhost${url}`, { headers });
}

function mediaParams(inspectionId: string, ...path: string[]) {
  return { params: Promise.resolve({ inspectionId, path }) };
}

async function fetchMedia(
  inspectionId: string,
  path: string[],
  opts: { cookie?: string; range?: string } = {},
): Promise<Response> {
  return mediaGET(
    requestFor(`/f/${inspectionId}/${path.join("/")}`, opts),
    mediaParams(inspectionId, ...path),
  );
}

function paidCookie(id: string): string {
  return `${grantCookieName(id)}=${issueGrant(id, "paid")}`;
}

function ownerCookie(id: string): string {
  return `${grantCookieName(id)}=${issueGrant(id, "owner")}`;
}

beforeAll(async () => {
  // A private inspection, assembled from the fixture's own artifacts so the
  // report passes the contract, with only TWO media files present: the teaser
  // sample and one report-tier photograph. Everything else the report cites is
  // deliberately absent, so "cited but missing" has a case too.
  const dir = inspectionDir(GATED_ID);
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(join(dir, "media"), { recursive: true });
  for (const name of ["report", "teaser"] as const) {
    const raw = await readFile(
      join(REPO_ROOT, `fixtures/reports/demo-01.${name}.json`),
      "utf8",
    );
    await writeFile(
      join(dir, `${name}.json`),
      raw.replaceAll("demo-01", GATED_ID),
      "utf8",
    );
  }
  await copyFile(join(FIXTURE_MEDIA, SAMPLE_PATH), join(dir, "media", SAMPLE_PATH));
  await copyFile(
    join(FIXTURE_MEDIA, "photo_01.jpg"),
    join(dir, "media", "photo_01.jpg"),
  );
  // A file that exists INSIDE media/ and is cited by nothing: the redaction
  // sidecar, which carries the coordinates of every plate and face a reviewer
  // marked. The allowlist test below is only a real test because this file is
  // really there to be leaked.
  await writeFile(
    join(dir, "media", "redactions.json"),
    JSON.stringify({ reviewer: "a-real-name", regions: [] }),
    "utf8",
  );
});

afterAll(() => {
  rmSync(inspectionDir(GATED_ID), { recursive: true, force: true });
});

describe("the media policy is the report's own citations", () => {
  const policy = mediaPolicy(demoReport, demoTeaser);

  it("report tier covers every cited asset and the spectrogram", () => {
    for (const asset of demoReport.assets) {
      expect(policy.report.has(asset.path)).toBe(true);
    }
    expect(policy.report.has(demoReport.audio!.spectrogramPath)).toBe(true);
  });

  it("teaser tier is exactly one file wide: the sample photograph", () => {
    expect(policy.teaser.size).toBe(1);
    expect(policy.teaser.has(SAMPLE_PATH)).toBe(true);
  });

  it("everything the free tier shows, the paid tier also shows", () => {
    for (const p of policy.teaser) expect(policy.report.has(p)).toBe(true);
  });

  it("tiers a file nothing cites as unservable, not as public", () => {
    expect(tierFor(policy, "redactions.json")).toBeNull();
    expect(tierFor(policy, "report.json")).toBeNull();
    expect(tierFor(policy, SAMPLE_PATH)).toBe("teaser");
    expect(tierFor(policy, "photo_01.jpg")).toBe("report");
  });

  it("an inspection with no artifacts serves nothing", () => {
    const empty = mediaPolicy(null, null);
    expect(empty.report.size).toBe(0);
    expect(empty.teaser.size).toBe(0);
  });
});

describe("ids and paths are validated before they touch the filesystem", () => {
  it("accepts the shapes the product mints", () => {
    expect(isValidInspectionId("demo-01")).toBe(true);
    expect(isValidInspectionId("insp_ab12cd34")).toBe(true);
  });

  it("rejects everything with a future as a path component", () => {
    for (const id of ["", "..", "../demo-01", "a/b", ".git", "-x", "_x", "a".repeat(65)]) {
      expect(isValidInspectionId(id), id).toBe(false);
    }
  });

  it("accepts every path the pipeline has ever emitted", () => {
    for (const asset of demoReport.assets) {
      expect(isValidMediaPath([asset.path]), asset.path).toBe(true);
    }
    expect(isValidMediaPath([demoReport.audio!.spectrogramPath])).toBe(true);
  });

  it("rejects traversal, dotfiles and smuggled separators", () => {
    for (const segments of [
      [],
      [".."],
      ["..", "report.json"],
      [".redact-cache"],
      [".hidden.jpg"],
      ["a\\b.jpg"],
      ["photo_01.jpg/"],
      [""],
    ]) {
      expect(isValidMediaPath(segments), JSON.stringify(segments)).toBe(false);
    }
  });
});

describe("range parsing", () => {
  const SIZE = 1000;

  it("no header means the whole file", () => {
    expect(parseRange(null, SIZE)).toBeUndefined();
  });

  it("parses the shapes browsers actually send", () => {
    expect(parseRange("bytes=0-99", SIZE)).toEqual({ start: 0, end: 99 });
    expect(parseRange("bytes=200-", SIZE)).toEqual({ start: 200, end: 999 });
    expect(parseRange("bytes=-100", SIZE)).toEqual({ start: 900, end: 999 });
    expect(parseRange("bytes=0-9999", SIZE)).toEqual({ start: 0, end: 999 });
  });

  it("treats malformed and multi-range headers as no range, per spec", () => {
    for (const h of ["bytes=", "bytes=-", "octets=0-1", "bytes=0-1,5-6", "garbage"]) {
      expect(parseRange(h, SIZE), h).toBeUndefined();
    }
  });

  it("flags unsatisfiable ranges for the 416 path", () => {
    expect(parseRange("bytes=1000-", SIZE)).toBeNull();
    expect(parseRange("bytes=5-2", SIZE)).toBeNull();
    expect(parseRange("bytes=-0", SIZE)).toBeNull();
    expect(parseRange("bytes=0-", 0)).toBeNull();
  });
});

describe("content types", () => {
  it("maps what the pipeline emits and refuses to guess at the rest", () => {
    expect(contentTypeFor("photo_01.jpg")).toBe("image/jpeg");
    expect(contentTypeFor("audio_01.spectrogram.png")).toBe("image/png");
    expect(contentTypeFor("audio_01.wav")).toBe("audio/wav");
    expect(contentTypeFor("video_01.mp4")).toBe("video/mp4");
    expect(contentTypeFor("history_01.txt")).toBe("text/plain; charset=utf-8");
    expect(contentTypeFor("mystery.xyz")).toBe("application/octet-stream");
    expect(contentTypeFor("noextension")).toBe("application/octet-stream");
  });
});

describe("GET /f/<id>/<path> - the public demo", () => {
  it("serves a cited photograph to a stranger, with honest headers", async () => {
    const res = await fetchMedia("demo-01", ["photo_01.jpg"]);
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("image/jpeg");
    expect(res.headers.get("x-content-type-options")).toBe("nosniff");
    expect(res.headers.get("accept-ranges")).toBe("bytes");
    expect(res.headers.get("cache-control")).toBe("public, max-age=300");
    const bytes = await res.arrayBuffer();
    expect(bytes.byteLength).toBeGreaterThan(1000);
    expect(res.headers.get("content-length")).toBe(String(bytes.byteLength));
  });

  it("serves the spectrogram, which is cited but is not an asset row", async () => {
    const res = await fetchMedia("demo-01", [demoReport.audio!.spectrogramPath]);
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("image/png");
  });

  it("answers a Range request with 206 and the exact slice", async () => {
    const res = await fetchMedia("demo-01", ["audio_01.wav"], { range: "bytes=0-99" });
    expect(res.status).toBe(206);
    expect(res.headers.get("content-length")).toBe("100");
    const full = await fetchMedia("demo-01", ["audio_01.wav"]);
    const size = Number(full.headers.get("content-length"));
    expect(res.headers.get("content-range")).toBe(`bytes 0-99/${size}`);
    expect((await res.arrayBuffer()).byteLength).toBe(100);
  });

  it("answers an unsatisfiable Range with 416", async () => {
    const res = await fetchMedia("demo-01", ["photo_01.jpg"], {
      range: "bytes=999999999-",
    });
    expect(res.status).toBe(416);
    expect(res.headers.get("content-range")).toMatch(/^bytes \*\/\d+$/);
  });

  it("refuses to serve files the report does not cite, even ones on disk", async () => {
    // manifest.json sits right beside the media; nothing cites it; 404.
    expect((await fetchMedia("demo-01", ["manifest.json"])).status).toBe(404);
    expect((await fetchMedia("demo-01", ["redactions.json"])).status).toBe(404);
  });

  it("refuses traversal at every layer", async () => {
    expect((await fetchMedia("demo-01", ["..", "manifest.json"])).status).toBe(404);
    expect((await fetchMedia("demo-01", ["..%2Fmanifest.json"])).status).toBe(404);
    expect((await fetchMedia("../demo-01", ["photo_01.jpg"])).status).toBe(404);
  });
});

describe("GET /f/<id>/<path> - a private inspection", () => {
  it("serves nothing without a grant - not even the free sample", async () => {
    expect((await fetchMedia(GATED_ID, [SAMPLE_PATH])).status).toBe(404);
    expect((await fetchMedia(GATED_ID, ["photo_01.jpg"])).status).toBe(404);
  });

  it("serves exactly the sample to an owner grant", async () => {
    const cookie = ownerCookie(GATED_ID);
    expect((await fetchMedia(GATED_ID, [SAMPLE_PATH], { cookie })).status).toBe(200);
    expect((await fetchMedia(GATED_ID, ["photo_01.jpg"], { cookie })).status).toBe(404);
  });

  it("serves cited media to a paid grant, privately and uncached", async () => {
    const res = await fetchMedia(GATED_ID, ["photo_01.jpg"], {
      cookie: paidCookie(GATED_ID),
    });
    expect(res.status).toBe(200);
    expect(res.headers.get("cache-control")).toBe("private, no-store");
  });

  it("404s a cited file that is missing on disk rather than guessing", async () => {
    // photo_02.jpg is in the report's asset list; the file was never copied in.
    const res = await fetchMedia(GATED_ID, ["photo_02.jpg"], {
      cookie: paidCookie(GATED_ID),
    });
    expect(res.status).toBe(404);
  });

  it("refuses the redaction sidecar to a PAID grant - on disk, uncited, private", async () => {
    // The strongest grant the product issues does not open a file the report
    // does not cite. The sidecar names the reviewer and boxes every face.
    const res = await fetchMedia(GATED_ID, ["redactions.json"], {
      cookie: paidCookie(GATED_ID),
    });
    expect(res.status).toBe(404);
  });

  it("rejects a grant for a different inspection and a forged one", async () => {
    const other = `${grantCookieName(GATED_ID)}=${issueGrant("insp_other", "paid")}`;
    expect((await fetchMedia(GATED_ID, [SAMPLE_PATH], { cookie: other })).status).toBe(404);
    const forged = `${grantCookieName(GATED_ID)}=paid.not-a-signature`;
    expect((await fetchMedia(GATED_ID, [SAMPLE_PATH], { cookie: forged })).status).toBe(404);
  });
});

describe("GET /access/<id> - where a grant becomes a cookie", () => {
  async function callAccess(id: string, query: string): Promise<Response> {
    const req = new NextRequest(`http://localhost/access/${id}${query}`);
    return accessGET(req, { params: Promise.resolve({ inspectionId: id }) });
  }

  it("exchanges a paid token for an httpOnly cookie and lands on the report", async () => {
    const token = issueGrant(GATED_ID, "paid");
    const res = await callAccess(GATED_ID, `?t=${encodeURIComponent(token)}`);
    expect(res.status).toBe(303);
    expect(res.headers.get("location")).toBe(`http://localhost/report/${GATED_ID}`);
    const cookie = res.headers.get("set-cookie")!;
    expect(cookie).toContain(`${grantCookieName(GATED_ID)}=`);
    expect(cookie).toContain(token);
    expect(cookie.toLowerCase()).toContain("httponly");
    expect(cookie.toLowerCase()).toContain("samesite=lax");
    expect(cookie.toLowerCase()).toContain("path=/");
  });

  it("lands an owner token on the teaser, the tier it actually opens", async () => {
    const token = issueGrant(GATED_ID, "owner");
    const res = await callAccess(GATED_ID, `?t=${encodeURIComponent(token)}`);
    expect(res.status).toBe(303);
    expect(res.headers.get("location")).toBe(`http://localhost/teaser/${GATED_ID}`);
  });

  it("honors an internal next= and refuses to become an open redirect", async () => {
    const token = encodeURIComponent(issueGrant(GATED_ID, "paid"));
    const good = await callAccess(GATED_ID, `?t=${token}&next=/buy/${GATED_ID}`);
    expect(good.headers.get("location")).toBe(`http://localhost/buy/${GATED_ID}`);

    for (const evil of ["https://evil.example/", "//evil.example/x", "/\\evil.example"]) {
      const res = await callAccess(GATED_ID, `?t=${token}&next=${encodeURIComponent(evil)}`);
      expect(res.headers.get("location"), evil).toBe(
        `http://localhost/report/${GATED_ID}`,
      );
    }
  });

  it("404s an invalid token without setting anything", async () => {
    const res = await callAccess(GATED_ID, "?t=paid.forged");
    expect(res.status).toBe(404);
    expect(res.headers.get("set-cookie")).toBeNull();
  });
});

describe("upload filenames become safe media paths", () => {
  it("keeps honest names and flattens hostile ones", () => {
    expect(sanitizeUploadName("photo.jpg")).toBe("photo.jpg");
    expect(sanitizeUploadName("IMG_2024 (1).heic")).toBe("IMG_2024__1_.heic");
    expect(sanitizeUploadName("../../../../report.json")).toBe("report.json");
    expect(sanitizeUploadName("..\\..\\win.jpg")).toBe("win.jpg");
    expect(sanitizeUploadName(".hidden.jpg")).toBe("hidden.jpg");
  });

  it("refuses names with nothing left in them", () => {
    for (const name of ["", "...", "///", "🚗"]) {
      expect(() => sanitizeUploadName(name), name).toThrow(/filename/i);
    }
  });

  it("produces names the media route's own validator accepts", () => {
    for (const name of ["photo.jpg", "a b c.png", "../../x.wav", "weird🚗name.mp4"]) {
      expect(isValidMediaPath([sanitizeUploadName(name)]), name).toBe(true);
    }
  });
});

// The fixture directory this suite reads from must exist, or every assertion
// above was vacuously green against nothing (the D-050 lesson, applied here).
it("the fixture media this suite serves actually exists", () => {
  expect(existsSync(join(FIXTURE_MEDIA, "photo_01.jpg"))).toBe(true);
  expect(existsSync(join(FIXTURE_MEDIA, SAMPLE_PATH))).toBe(true);
});
