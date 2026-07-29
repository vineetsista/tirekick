import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * A bundled font ships with the licence that lets us bundle it.
 *
 * Three variable subsets are vendored and served from our own origin. All three
 * are SIL OFL 1.1, which permits exactly this - including inside a commercial
 * product - on the condition that the licence text and the original copyright
 * notice travel with the binaries. For a while they did not, which made the
 * bundling itself non-compliant while the interface built on top of it looked
 * finished.
 *
 * Redistributing someone's typeface is the one thing in this repository where
 * the obligation is legal rather than self-imposed, so it gets a test rather than
 * a note in a phase report.
 */

const here = dirname(fileURLToPath(import.meta.url));
const fontsDir = resolve(here, "../../public/fonts");
const cssPath = resolve(here, "../app/globals.css");

const files = readdirSync(fontsDir);
const faces = files.filter((f) => f.endsWith(".woff2"));

describe("bundled fonts", () => {
  it("bundles the faces the stylesheet actually loads", () => {
    const css = readFileSync(cssPath, "utf8");
    const loaded = [...css.matchAll(/url\("\/fonts\/([^"]+)"\)/g)].map((m) => m[1]);
    expect(loaded.length).toBeGreaterThan(0);
    for (const file of loaded) {
      expect(files, `globals.css loads ${file}, which is not here`).toContain(file);
    }
    // And nothing is vendored that no stylesheet asks for - an unused font is
    // weight on every page load and a licence obligation for nothing.
    for (const face of faces) {
      expect(loaded, `${face} is bundled but never loaded`).toContain(face);
    }
  });

  it("gives every face a licence file beside it", () => {
    expect(faces.length).toBeGreaterThan(0);
    for (const face of faces) {
      const licence = `${face.replace(/\.woff2$/, "")}-OFL.txt`;
      expect(files, `${face} has no licence (${licence})`).toContain(licence);
    }
  });

  it("carries the real OFL 1.1 text and a copyright line, not a summary", () => {
    for (const face of faces) {
      const licence = join(fontsDir, `${face.replace(/\.woff2$/, "")}-OFL.txt`);
      const text = readFileSync(licence, "utf8");

      // The upstream file, not a paraphrase of it.
      expect(text).toContain("SIL OPEN FONT LICENSE Version 1.1");
      expect(text).toMatch(/^Copyright \d{4}/m);
      expect(text).toContain("PERMISSION & CONDITIONS");
      // The clause that makes bundling legal is the one worth pinning.
      expect(text).toContain(
        "Permission is hereby granted, free of charge, to any person obtaining",
      );
      expect(text.length).toBeGreaterThan(3000);
    }
  });

  it("names every bundled face in the notice", () => {
    const notice = readFileSync(join(fontsDir, "LICENSE.md"), "utf8");
    for (const face of faces) {
      expect(notice, `${face} is not accounted for in LICENSE.md`).toContain(face);
    }
  });
});
