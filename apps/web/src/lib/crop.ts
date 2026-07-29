import type { BoundingBox } from "@tirekick/shared";

/**
 * Geometry for showing a cited region of a photograph at a readable size.
 *
 * ---------------------------------------------------------------------------
 * WHY THIS EXISTS
 * ---------------------------------------------------------------------------
 *
 * Until now a finding rendered its evidence as four numbers - `photo_01
 * [0.08, 0.62, 0.34, 0.14]` - and the photograph those numbers refer to sat in a
 * gallery several thousand pixels up the page. The component drawing that gallery
 * carries a comment saying "evidence and claim are never more than one
 * interaction apart (LAW 1)". On a 14,282px report they were about 4,000px apart,
 * and what sat beside the claim was a coordinate rather than a picture.
 *
 * A buyer reading "corrosion visible along the driver-side rocker panel" needs to
 * see the corrosion. That is the product.
 *
 * ---------------------------------------------------------------------------
 * THE MATH
 * ---------------------------------------------------------------------------
 *
 * Everything is computed in source pixels and returned as percentages, so the
 * result is a plain style object with no client-side JavaScript, no canvas, and
 * no image processing. The cited box lands exactly where the finding says it
 * does, which matters: a crop that is approximately right is a piece of evidence
 * that is approximately honest.
 *
 * Requires the asset's pixel dimensions. When those are absent - a corrupt file,
 * a format Pillow could not open - `cropFor` returns null and the caller shows
 * the whole frame instead of guessing at a region.
 */

/** Fraction of the crop's shorter axis the cited box should occupy. */
const BOX_FILL = 0.55;

/** Display aspect ratio of the crop frame, width / height. */
export const CROP_ASPECT = 3 / 2;

export interface CropGeometry {
  /** Style for the <img>, positioned inside an overflow-hidden frame. */
  image: {
    width: string;
    height: string;
    left: string;
    top: string;
  };
  /** Style for the box outline drawn over it. */
  box: {
    left: string;
    top: string;
    width: string;
    height: string;
  };
  /** How much the source is magnified, for the caption. 1 = whole frame. */
  magnification: number;
  /**
   * The aspect ratio the frame actually settled on, width / height.
   *
   * Usually `CROP_ASPECT`. It differs when the cited box is too tall or too wide
   * to fit at that ratio - a full-height box on a 4:3 photograph, say. In that
   * case the box wins and the frame changes shape, because showing part of a
   * cited region is a worse failure than an off-ratio picture: it looks like
   * evidence while hiding some of it.
   */
  aspect: number;
}

const pct = (n: number) => `${(n * 100).toFixed(4)}%`;
const clamp = (n: number, lo: number, hi: number) =>
  Math.min(Math.max(n, lo), Math.max(lo, hi));

/**
 * Work out how to show `box` within a frame of aspect `aspect`.
 *
 * Returns null when the source dimensions are unknown or degenerate - callers
 * must handle that rather than being handed a plausible-looking wrong answer.
 */
export function cropFor(
  box: BoundingBox,
  sourceWidth: number | null,
  sourceHeight: number | null,
  aspect: number = CROP_ASPECT,
): CropGeometry | null {
  if (!sourceWidth || !sourceHeight || sourceWidth <= 0 || sourceHeight <= 0) {
    return null;
  }
  if (!(aspect > 0)) return null;

  const W = sourceWidth;
  const H = sourceHeight;

  // The cited region, in pixels.
  const bx = box.x * W;
  const by = box.y * H;
  const bw = Math.max(box.w * W, 1);
  const bh = Math.max(box.h * H, 1);

  // Big enough that the box fills BOX_FILL of the frame on whichever axis is
  // binding, then squared up to the display aspect.
  let cw = Math.max(bw / BOX_FILL, (bh / BOX_FILL) * aspect);
  let ch = cw / aspect;

  // Never ask for more image than exists. Shrink both axes by one factor so the
  // aspect ratio survives the clamp.
  const fit = Math.min(1, W / cw, H / ch);
  cw *= fit;
  ch *= fit;

  // The cited box must be visible in full. If it does not fit at the display
  // ratio - a full-height box on a 4:3 photograph - grow the binding axis and
  // let the frame go off-ratio. `aspect` is returned so the caller can shape the
  // frame to what actually happened rather than to what was asked for.
  cw = Math.max(cw, Math.min(bw, W));
  ch = Math.max(ch, Math.min(bh, H));

  // Centre on the box, then slide back inside the frame. A box against an edge
  // is common - rocker panels are at the bottom of every photograph.
  const cx = bx + bw / 2;
  const cy = by + bh / 2;
  const x0 = clamp(cx - cw / 2, 0, W - cw);
  const y0 = clamp(cy - ch / 2, 0, H - ch);

  return {
    image: {
      width: pct(W / cw),
      height: pct(H / ch),
      left: pct(-x0 / cw),
      top: pct(-y0 / ch),
    },
    box: {
      left: pct((bx - x0) / cw),
      top: pct((by - y0) / ch),
      width: pct(bw / cw),
      height: pct(bh / ch),
    },
    magnification: W / cw,
    aspect: cw / ch,
  };
}
