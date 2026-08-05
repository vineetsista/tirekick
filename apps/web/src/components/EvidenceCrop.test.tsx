import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { EvidenceCrop } from "./EvidenceCrop";

/**
 * The failure branch of the evidence component.
 *
 * `cropFor` returns null when an asset's pixel dimensions were never recorded -
 * a corrupt file, a format Pillow could not open - and what this component does
 * with that null is the only thing a buyer sees on the worst day. D-045 wrote
 * the rule down: "cropFor returns null and the viewer shows the whole frame,
 * because a crop that is approximately right is evidence that is approximately
 * honest." The component then shipped `objectFit: cover` in that branch, which
 * cuts the frame to a 3:2 centre and throws away whatever did not fit - in the
 * component whose entire job is showing the buyer the region a finding cites.
 *
 * Nothing failed, because the decision lived in a document and the fallback was
 * the branch no fixture exercised. These assertions are that decision, moved
 * into a place that can go red.
 */

const BOX = { x: 0.08, y: 0.62, w: 0.34, h: 0.14 };
const COLOR = "#c2410c";

function render(sourceWidth: number | null, sourceHeight: number | null) {
  return renderToStaticMarkup(
    <EvidenceCrop
      src="/f/demo-01/photo_01.jpg"
      box={BOX}
      color={COLOR}
      caption="corrosion along the driver-side rocker panel"
      assetId="photo_01"
      sourceWidth={sourceWidth}
      sourceHeight={sourceHeight}
    />,
  );
}

const cropped = render(1600, 1200);
const whole = render(null, null);

describe("with the source dimensions recorded", () => {
  it("positions the image inside the frame and draws the cited box on it", () => {
    expect(cropped).toContain("position:absolute");
    expect(cropped).toContain("max-width:none");
    expect(cropped).toContain(`border:2px solid ${COLOR}`);
  });

  it("states the box as a fraction of the frame", () => {
    expect(cropped).toContain("34×14% of frame");
  });
});

describe("with the source dimensions missing", () => {
  it("shows the whole photograph rather than a centre cut of it", () => {
    /**
     * `cover` is the one object-fit value that removes pixels, and it does so
     * silently and unboundedly: a 4:3 photograph loses a seventh of its height,
     * a portrait one loses half its length, and the finding's region may be in
     * any of it. `contain` shows every pixel the buyer paid for, letterboxed
     * against the frame's black backdrop.
     */
    expect(whole).toContain("object-fit:contain");
    expect(whole).not.toContain("object-fit:cover");
  });

  it("keeps a fixed frame so the page does not shift when the image lands", () => {
    // Nothing knows this image's shape until it arrives. The report is 14,000px
    // of anchor targets; an unreserved image reflows everything below it after
    // load and lands a #finding anchor somewhere else. The frame ratio holds the
    // space, and `contain` means holding it costs no pixels.
    expect(whole).toContain("aspect-ratio:1.5");
  });

  it("draws no box, because it does not know where the box would go", () => {
    expect(whole).not.toContain(COLOR);
  });

  it("says in the caption that this is the whole frame and the region is unmarked", () => {
    // The old caption said "region not shown", which was true of the box and not
    // of the photograph, and left a buyer with no idea what they were looking at.
    expect(whole).toContain("whole frame - region not marked, dimensions unrecorded");
  });

  it("does not describe the image as cropped in its alt text", () => {
    expect(whole).not.toContain("Cropped region");
    expect(cropped).toContain("Cropped region");
  });
});
