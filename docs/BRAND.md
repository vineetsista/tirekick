# BRAND

## The feeling

A buyer opens the report at 11pm the night before they drive out to see a car. They
are nervous, they are about to spend six thousand dollars in cash, and they do not
know what they are looking at.

The report should feel like **instrumentation**. Not a brochure, not a friendly app -
a readout. Dense, dark, monospaced, evidence-forward. The emotional target is the
moment a radiologist puts a scan on the light box: this is the machine's read, here is
the region it is pointing at, here is how sure it is, and here is what a human still
has to decide.

Bloomberg terminal, not car dealership. Flight recorder, not Carfax.

## Voice

- Flat, specific, technical. "Corrosion visible along the driver-side rocker panel,
  approximately 30cm, surface-level in the provided image."
- Never breezy, never salesy, never reassuring for the sake of it.
- Uncertainty stated in the same tone as certainty. "Cannot be determined from the
  provided media" is said plainly, without apology.
- Second person for actions the buyer takes. "Ask the seller when the timing belt was
  replaced."
- We name the AI. "TIREKICK's vision model flagged this region." Not "our technology."

## Type

- **JetBrains Mono** for all data: findings, confidences, tables, VINs, prices,
  timestamps, evidence labels. This is the product's signature and it is used
  aggressively, not as an accent.
- **Inter** for long-form prose only: explanations, the liability banner, the
  negotiation script.
- Tabular figures on. Numbers must align in columns.
- Uppercase, wide letter-spacing for section labels: `EVIDENCE GALLERY`, `SYSTEMS`.

## Color

Dark base. Color carries meaning and nothing else - no decorative color anywhere.

| Token | Value | Meaning |
|---|---|---|
| `--tk-bg` | `#0A0C0E` | page |
| `--tk-panel` | `#101418` | panel/card |
| `--tk-line` | `#1E252C` | rules, borders, grid |
| `--tk-text` | `#E6EDF3` | primary text |
| `--tk-muted` | `#8B98A5` | secondary text, units, captions |
| `--tk-accent` | `#38E1B0` | TIREKICK signal green - brand, active state, links |
| `--tk-sev-info` | `#5B9DD9` | observation, no action |
| `--tk-sev-minor` | `#E3B341` | cosmetic / monitor |
| `--tk-sev-major` | `#F0883E` | costs money |
| `--tk-sev-critical` | `#F85149` | walk away or verify before purchase |
| `--tk-locked` | `#A371F7` | safety-critical, mechanic required |
| `--tk-unknown` | `#6E7681` | cannot determine |

`--tk-locked` gets its own color on purpose. Purple is not on the severity ramp, so a
locked row cannot be misread as "green means fine" or "red means bad." It reads as a
different *kind* of statement, which is exactly what it is.

`--tk-unknown` is deliberately legible, not faded. "Cannot determine" is a first-class
output (LAW 1) and must not look like a disabled row.

## The overlay - the signature visual

The annotated image is the product. It gets the most design attention of anything.

- Photograph at full bleed on a dark field, slightly desaturated so annotation color
  wins.
- Finding boxes: 2px stroke in severity color, 8% fill of the same, sharp corners, no
  rounding, no drop shadow.
- Corner ticks on each box - short L-marks at the corners, like a targeting reticle.
  This is the detail that makes it read as instrument rather than markup.
- Label attached to the box: `RUST / MODERATE / 0.72` in mono uppercase, on a solid
  severity-colored bar, 11px, letter-spaced.
- A fine grid overlay at 4% opacity across the whole image. Free, subtle, and it does
  most of the CT-scan work.
- Every box is clickable and scrolls to its finding. Evidence and claim are never more
  than one interaction apart (LAW 1).

## Confidence bars

- A 10-segment discrete bar in mono, not a smooth gradient. Segments read as a
  measurement; a gradient reads as decoration.
- Filled segments in severity color, empty segments in `--tk-line`.
- Numeric value always adjacent: `0.72`. Never a bar alone.
- Never a letter grade. Never a star rating. Never a single number for the whole car
  that can be screenshotted away from its caveats (LIABILITY section 9).

## Layout

- 8px baseline grid, hard 1px rules between blocks, generous negative space around
  imagery and almost none inside data tables.
- Data tables are dense on purpose. Density signals seriousness.
- Section headers are a rule + uppercase label, left aligned, no icons.
- No rounded cards, no soft shadows, no gradients, no illustrations, no stock
  photography of smiling people, no car silhouettes.

## Logo / wordmark

`TIREKICK` set in JetBrains Mono, uppercase, heavy weight, letter-spaced. That is the
whole mark. A wordmark in the product's own typeface is honest about what we are.

Report watermark and share footer: `INSPECTED BY TIREKICK AI` in mono uppercase, muted,
plus the "not an inspection" line from LIABILITY section 4.

## What we never do

Bright friendly onboarding. Confetti. A mascot. A green checkmark next to a car.
Anything that makes a buyer feel *finished* rather than *equipped*.
