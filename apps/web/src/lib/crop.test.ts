import { describe, expect, it } from "vitest";
import { CROP_ASPECT, cropFor } from "./crop";

/**
 * The crop is a claim about where a finding is. If it drifts, the report shows a
 * buyer one part of a car while telling them about another - which is a worse
 * failure than showing no image at all, because it looks like evidence.
 *
 * These assert the geometry rather than the styling: parse the percentages back
 * out and check they describe the region the box actually occupies.
 */

const num = (s: string) => Number.parseFloat(s);

/** Where the box lands in the source image, recovered from the output. */
function recover(
  geo: NonNullable<ReturnType<typeof cropFor>>,
  W: number,
  H: number,
) {
  // The image is scaled so its full width spans (W / cw) frames.
  const scaleX = num(geo.image.width) / 100;
  const scaleY = num(geo.image.height) / 100;
  const cw = W / scaleX;
  const ch = H / scaleY;
  const x0 = (-num(geo.image.left) / 100) * cw;
  const y0 = (-num(geo.image.top) / 100) * ch;
  return {
    cw,
    ch,
    x0,
    y0,
    boxX: x0 + (num(geo.box.left) / 100) * cw,
    boxY: y0 + (num(geo.box.top) / 100) * ch,
    boxW: (num(geo.box.width) / 100) * cw,
    boxH: (num(geo.box.height) / 100) * ch,
  };
}

describe("crop geometry", () => {
  const W = 1600;
  const H = 1200;

  it("puts the outline exactly on the cited pixels", () => {
    const box = { x: 0.08, y: 0.62, w: 0.34, h: 0.14 };
    const geo = cropFor(box, W, H)!;
    const r = recover(geo, W, H);

    expect(r.boxX).toBeCloseTo(box.x * W, 1);
    expect(r.boxY).toBeCloseTo(box.y * H, 1);
    expect(r.boxW).toBeCloseTo(box.w * W, 1);
    expect(r.boxH).toBeCloseTo(box.h * H, 1);
  });

  it("keeps the display aspect ratio when the box fits at it", () => {
    for (const box of [
      { x: 0.08, y: 0.62, w: 0.34, h: 0.14 },
      { x: 0.4, y: 0.1, w: 0.05, h: 0.5 },
      { x: 0.3, y: 0.3, w: 0.2, h: 0.2 },
    ]) {
      const geo = cropFor(box, W, H)!;
      const r = recover(geo, W, H);
      expect(r.cw / r.ch).toBeCloseTo(CROP_ASPECT, 3);
      expect(geo.aspect).toBeCloseTo(CROP_ASPECT, 3);
    }
  });

  it("gives up the aspect ratio rather than clipping the cited box", () => {
    // Too tall to fit in a 3:2 frame on a 4:3 photograph. The box must still be
    // whole, so the frame changes shape and says so.
    const box = { x: 0.45, y: 0.02, w: 0.4, h: 0.9 };
    const geo = cropFor(box, W, H)!;
    expect(geo.aspect).not.toBeCloseTo(CROP_ASPECT, 2);

    const r = recover(geo, W, H);
    expect(r.cw / r.ch).toBeCloseTo(geo.aspect, 3);
    expect(r.boxH).toBeCloseTo(box.h * H, 1);
  });

  it("shows a full-frame box at the photograph's own aspect ratio", () => {
    const geo = cropFor({ x: 0, y: 0, w: 1, h: 1 }, W, H)!;
    expect(geo.aspect).toBeCloseTo(W / H, 3);
    expect(geo.magnification).toBeCloseTo(1, 5);
  });

  it("never crops outside the source image", () => {
    // Boxes hard against every edge. Rocker panels really are at the bottom.
    for (const box of [
      { x: 0, y: 0, w: 0.1, h: 0.1 },
      { x: 0.9, y: 0.9, w: 0.1, h: 0.1 },
      { x: 0, y: 0.95, w: 0.3, h: 0.05 },
      { x: 0.97, y: 0.4, w: 0.03, h: 0.2 },
    ]) {
      const r = recover(cropFor(box, W, H)!, W, H);
      expect(r.x0).toBeGreaterThanOrEqual(-0.01);
      expect(r.y0).toBeGreaterThanOrEqual(-0.01);
      expect(r.x0 + r.cw).toBeLessThanOrEqual(W + 0.01);
      expect(r.y0 + r.ch).toBeLessThanOrEqual(H + 0.01);
    }
  });

  it("keeps the whole cited box inside the crop", () => {
    for (const box of [
      { x: 0, y: 0.95, w: 0.3, h: 0.05 },
      { x: 0.45, y: 0.02, w: 0.4, h: 0.9 },
      { x: 0.9, y: 0.9, w: 0.1, h: 0.1 },
    ]) {
      const r = recover(cropFor(box, W, H)!, W, H);
      expect(r.boxX).toBeGreaterThanOrEqual(r.x0 - 0.01);
      expect(r.boxY).toBeGreaterThanOrEqual(r.y0 - 0.01);
      expect(r.boxX + r.boxW).toBeLessThanOrEqual(r.x0 + r.cw + 0.01);
      expect(r.boxY + r.boxH).toBeLessThanOrEqual(r.y0 + r.ch + 0.01);
    }
  });

  it("magnifies a small region and does not shrink a full-frame one", () => {
    const small = cropFor({ x: 0.45, y: 0.45, w: 0.04, h: 0.04 }, W, H)!;
    expect(small.magnification).toBeGreaterThan(3);

    const whole = cropFor({ x: 0, y: 0, w: 1, h: 1 }, W, H)!;
    expect(whole.magnification).toBeCloseTo(1, 5);
  });

  it("returns null rather than guessing when the source size is unknown", () => {
    const box = { x: 0.1, y: 0.1, w: 0.2, h: 0.2 };
    expect(cropFor(box, null, null)).toBeNull();
    expect(cropFor(box, 1600, null)).toBeNull();
    expect(cropFor(box, 0, 1200)).toBeNull();
    expect(cropFor(box, -1, 1200)).toBeNull();
    expect(cropFor(box, 1600, 1200, 0)).toBeNull();
  });

  it("handles a portrait source without inverting the frame", () => {
    const r = recover(cropFor({ x: 0.2, y: 0.7, w: 0.4, h: 0.1 }, 1200, 1600)!, 1200, 1600);
    expect(r.cw / r.ch).toBeCloseTo(CROP_ASPECT, 3);
    expect(r.cw).toBeLessThanOrEqual(1200 + 0.01);
  });
});
