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

Three faces, each doing one job. All are self-hosted in `apps/web/public/fonts`
so the report renders identically offline and nothing about a buyer's vehicle is
announced to a font CDN (LAW 3 in spirit, if not in letter). `fonts.test.ts`
checks both directions - every face the stylesheet loads is vendored, and every
vendored face is loaded - and that each one ships with the OFL text that makes
redistributing it legal. That obligation is the one in this repository that is
somebody else's rather than self-imposed, so it gets a test rather than a note.

- **JetBrains Mono** (`--tk-mono`) for measured values: confidences, VINs, box
  coordinates, prices, timestamps, asset ids, hashes. Tabular figures on, so
  numbers align in columns. This is the product's signature and it is used
  aggressively, not as an accent.
- **Archivo** (`--tk-display`) for the interface itself: headings, labels, the
  wordmark, table headers, and the plan-view drawing. Grotesque, tight, slightly
  condensed - it holds up at 10px uppercase with 0.18em tracking, which is most
  of what this interface is made of.
- **Newsreader** (`--tk-prose`) for anything a buyer reads as sentences:
  finding detail, the confidence basis, the liability banner, the negotiation
  script. A serif, deliberately. The report is a document that argues for a
  conclusion, and the passages that argue should not look like chrome.

Uppercase with wide letter-spacing is for section labels of a few words -
`EVIDENCE GALLERY`, `SYSTEMS`. Never for a sentence. Set in it, a two-line
sentence becomes the hardest thing on the page to read.

## Color

Dark base. Color carries meaning and nothing else - no decorative color anywhere.

| Token | Value | Meaning |
|---|---|---|
| `--tk-void` | `#0b0a09` | page |
| `--tk-shell` | `#15120f` | panel/card |
| `--tk-shell-2` | `#1c1815` | raised panel, table stripe |
| `--tk-rule` | `#2b2621` | rules, borders, grid |
| `--tk-rule-bright` | `#453d35` | hovered rule, link underline |
| `--tk-paper` | `#f4efe6` | primary text, and the only "primary action" fill |
| `--tk-graphite` | `#a8a094` | secondary text, units, captions |
| `--tk-pencil` | `#8b8377` | tertiary - coordinates, ids, provenance |
| `--tk-sev-info` | `#6ba8d8` | observation, no action |
| `--tk-sev-minor` | `#e8b33d` | cosmetic / monitor |
| `--tk-sev-major` | `#ef8b3f` | costs money |
| `--tk-sev-critical` | `#f2554c` | walk away or verify before purchase |
| `--tk-locked` | `#b08bf5` | safety-critical, mechanic required |
| `--tk-unknown` | `#9a9186` | cannot determine |

The base is warm rather than blue-black - a workshop under a sodium lamp, not a
terminal. The warmth is load-bearing: against a cool ground the severity ramp
reads as neon, and a report about somebody's actual money should not look like a
game.

**There is no brand hue, and that is the decision.** An accent green existed
through P7 and was used for links, active states, the checkout button, and the
`no_issues_visible` status. The last of those is the problem: it painted "nothing
adverse was visible in the photographs you sent" in the same colour every other
product on the market uses for *pass*, which is the one thing LAW 2 says this
product may never say. Rather than keep a hue and forbid its most natural use, we
removed it. The only chroma on the page is the meaning ramp above. A primary
action is `--tk-paper` on `--tk-void` - the highest contrast available, earned by
contrast rather than by colour.

`--tk-locked` gets its own colour on purpose. Purple is not on the severity ramp,
so a locked row cannot be misread as "green means fine" or "red means bad." It
reads as a different *kind* of statement, which is exactly what it is.

`--tk-unknown` is deliberately legible, not faded. "Cannot determine" is a
first-class output (LAW 1) and must not look like a disabled row. It was raised
from `#6E7681`, which measured 4.03:1 against the panel and so failed WCAG AA
while carrying exactly the content this project claims to take most seriously.

**On paper the palette inverts.** `@media print` in `globals.css` redefines nine
tokens to ink on white and leaves the four severity colours and `--tk-locked`
alone, because a report is something a buyer hands to a mechanic in a workshop and
the severity of a finding must survive a black-and-white laser printer. Eight of
the nine are neutrals; the ninth is `--tk-unknown`, which is on the meaning ramp
and is darkened anyway - "cannot determine" has to stay readable on paper, and it
carries no severity to preserve. The table above is the screen palette; the print
overrides are read from the same file.

The table is checked. `apps/web/src/lib/tokens.test.ts` parses it and fails if a
value here disagrees with `globals.css`, if it names a token the stylesheet does
not define, or if a colour joins the meaning ramp without being documented here.
Every value in it was wrong before that test existed.

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

## The coverage map - the other signature visual

A plan view of the vehicle, drawn once per report, showing three states per
region: **flagged** (a finding cites a photograph of it, severity colour),
**looked at** (a photograph arrived and nothing adverse was visible - hairline,
no fill, and deliberately not green), and **not provided** (dashed and dim,
because nothing in the report describes what it would have shown). The four
locked systems are drawn over the top where they physically live: brakes behind
the wheels, steering and restraints in the cabin, structure as the outline of the
car itself.

This is the one place the rule below about car silhouettes does not apply, and
the exception is the point. Every other inspection interface draws a car in order
to decorate a checklist of green ticks. This one draws it because *where we
looked* is the most honest thing the product knows, and a map is the only way to
show that the useful half of an automated analysis is the half it could not do.

A region flags from the `viewClass` of the photograph a finding cites, never from
the finding's `system`. Keying it off `system` lit all four flanks for one
corrosion finding on a rocker panel, because all four are `exterior` - the
component reported damage on parts of the car nothing had been found on, which is
the precise failure it exists to prevent.

## Confidence bars

- A 10-segment discrete bar in mono, not a smooth gradient. Segments read as a
  measurement; a gradient reads as decoration.
- Filled segments in severity color, empty segments in `--tk-line`.
- Numeric value always adjacent: `0.72`. Never a bar alone.
- Never a letter grade. Never a star rating. Never a single number for the whole car
  that can be screenshotted away from its caveats (LIABILITY section 9).

## Layout

- 4px spacing grid (`--s-1` through `--s-9`), named so a gap has a reason. Hard
  1px rules between blocks, generous negative space around imagery and almost
  none inside data tables.
- Data tables are dense on purpose. Density signals seriousness.
- Section headers are a rule + uppercase label, left aligned, no icons.
- Evidence sits inside the finding that cites it. A coordinate beside a claim and
  the photograph four thousand pixels away is a citation, not evidence (LAW 1).
- Every multi-column split collapses to one column before it overflows. A grid
  track with a fixed minimum does not wrap, and the failure mode is a horizontal
  scrollbar on the whole document.
- No rounded cards, no soft shadows, no gradients, no stock photography of
  smiling people. No car silhouettes except the coverage map above, which earns
  its exception by drawing what was *not* covered.

## Logo / wordmark

`TIREKICK` set in Archivo, uppercase, 800 weight, 0.22em tracking. That is the
whole mark - the interface face rather than a drawn logo, because a wordmark in
the product's own type is honest about what we are.

It is typed as two inline styles rather than a class, and the two disagree: the
report nav is 0.22em and the landing page is 0.26em. Nothing holds them in step,
because `tokens.test.ts` checks that a token *exists*, not that two hand-written
values match. 0.22em is the intended figure; the landing page is the one that is
wrong, and it is recorded here rather than silently corrected because a wordmark
defined in two places will drift again the moment a third appears.

Report watermark and share footer: `ANALYZED BY TIREKICK AI` in mono uppercase, muted,
plus the "not an inspection" line from LIABILITY section 4. It read `INSPECTED BY`
until P9 - the claim the entire liability architecture denies, in the passive
voice, on the surfaces most likely to be forwarded to a stranger.

## What we never do

Bright friendly onboarding. Confetti. A mascot. A green checkmark next to a car.
Anything that makes a buyer feel *finished* rather than *equipped*.
