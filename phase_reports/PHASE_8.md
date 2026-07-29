# PHASE 8 - THE EVIDENCE

Branch: `main` | 517 tests | 51 decisions logged
Gates: 9/9 green.

P7 ended by saying there was no P8 to define and that the next phase was the
measurement phase, which cannot start without a key and a car. That is still
true. This phase does not claim otherwise and does not move any of the four
zeros.

What it does instead is finish something the product had been describing rather
than doing. TIREKICK sells one sentence - *here is what it can see, and here is
the picture it saw it in* - and until this phase the report rendered the first
half beside four numbers, and the free page rendered no picture at all.

---

## 1. The gap

`Overlay.tsx` has carried this comment since P2:

> Evidence and claim are never more than one interaction apart (LAW 1).

On the rendered dossier the evidence gallery sat at roughly 1,300px and the
findings began at roughly 5,000px, on a page 14,282px tall. What sat beside each
claim was this:

    photo_01 - Corrosion band along the lower rocker panel [0.08, 0.62, 0.34, 0.14]

A buyer reading "corrosion visible along the driver-side rocker panel" could not
see the corrosion without scrolling four thousand pixels and then picking the
right thumbnail out of thirteen, each about 340px wide, in which a box covering
34% by 14% of the frame renders about 115px by 20px.

The comment was true as an intention and false as a description. Nothing failed,
because **a claim about layout written in a docstring is not a test** - which is
the same sentence P7 wrote about LAWS.md and P6 wrote about the landing page, in
its third venue.

The free page was worse in kind. It advertised "every finding, with the
photograph it came from and a box drawn on it" while showing a stranger no
photograph, no box, and no finding. It asked someone to spend $25 on visual
evidence entirely on faith.

---

## 2. What shipped

**`crop.ts` + `EvidenceCrop`** - the cited region, at a readable size, beside the
claim. Geometry computed in source pixels and returned as percentages, so there
is no canvas, no client JavaScript and no image processing, and the box lands
*exactly* where the finding says it does. The magnification is stated on the
frame: a crop is a claim about scale as much as position, and a 4.1x blow-up of a
60px region must not read as a clear photograph of a large defect. The
coordinates are still printed, because they are what makes the claim checkable
against the asset hash. They are simply not the evidence any more.

**Asset dimensions** (D-045). A box is four fractions, and nothing recorded what
they were fractions *of*. The report hashed the exact bytes a claim was written
against while never recording their shape, so a reader could not redraw the box.
When dimensions are absent - a corrupt file, a format Pillow cannot open -
`cropFor` returns null and the viewer shows the whole frame rather than cropping
to a guess.

**`Teaser.sample`** (D-044) - one complete finding, free. The worst-severity,
best-evidenced finding about the vehicle, not the mildest, because showing the
least of what was found in order to hold the best back is a sales tactic. Not
model-level, so the product is never advertised with a fact about a car the buyer
has never seen. Never from a locked system, checked twice.

**`CoverageMap`** (D-047) - a plan view of the vehicle with three states per
region, and the third is the point: *never photographed*, dashed and dim, because
nothing in the report describes what it would have shown. The four locked systems
are drawn where they physically live - brakes behind the wheels, structure as the
outline of the car itself - so a buyer can see that the shell of the vehicle is
the exact thing we will never tell them is sound.

**Vehicle findings separated from model-level records.** The verdict has always
said "2 findings that are likely to cost money. Separately, 5 recall campaigns
are on record for this model year - free to fix". The list underneath then
rendered all fourteen in one column, five recall campaigns wearing the same MAJOR
badge as the corrosion on the rocker panel. A buyer scrolling that saw seven
major problems with the car in front of them. There were two. The layout
contradicted the paragraph directly above it.

**The design system**, rebuilt around the absence of a brand hue (D-048), and
`BRAND.md` rewritten to describe it.

---

## 3. What the phase found on the way

This is the part worth reading. Nine real defects, five of them in code this
phase had no intention of touching.

**The pay button was invisible.** The redesign deleted `--tk-accent` on the
grounds that the product has no brand hue - `globals.css` says so, in a comment,
where the token used to be. Four call sites still asked for it. The loudest:

    background: "var(--tk-accent)",   // undefined -> declaration dropped
    color: "#0a0c0e",                 // near-black, on a near-black page

That is the checkout page. An undefined custom property is invalid at
computed-value time, so the declaration is dropped and the property takes its
initial value: the button rendered as black text on nothing, on the one page in
the product where money changes hands. Every gate stayed green. TypeScript does
not read CSS, the snapshot recorded the broken string as the *expected* string,
and no test opens the checkout page. It was found by opening the page in a
browser, which nothing in seven phases had required.

**The `assets` table had nowhere to put the new dimensions.** It mirrors the
contract column for column and kept its nine columns while the contract grew to
eleven. Persistence would have accepted a report and returned a different one -
rows asserting a defect occupies 34% of a photograph whose shape nothing
recorded.

**Every value in the BRAND.md colour table was wrong**, and one named a token the
stylesheet had deleted. The document read as a specification and functioned as a
souvenir.

**The coverage map kept its own copy of the requested-view list**, three entries
long, while the contract had fifteen view classes and the pipeline requested
twelve. It agreed with the pipeline on the day it was written. A view added later
would have gone missing from the one component whose entire purpose is showing
what was *not* covered.

**Three layouts overflowed on a phone.** A grid track with a fixed minimum does
not wrap; when the container is narrower than the minimums, the row is simply
wider than its parent and the whole document gets a horizontal scrollbar. The
report ran 76px wide at 390px and the teaser 47px. At 320px a federal recall title
- `Recall 25V422000: POWER TRAIN:AUTOMATIC TRANSMISSION` - is one unbreakable
token to a line breaker and pushed its heading 40px past the panel.

**`FindingCard`'s docstring claimed a test that did not exist.** It said
"`ReportView.test.tsx` now asserts the ordering instead of trusting the comment."
It did not. The same sin, committed inside the change that was fixing it.

**Unbreakable tokens broke the page at every width.** Found the moment the
layout gate was pointed at reports designed to break it (D-051) rather than at
`demo-01`. A report whose titles are real NHTSA component strings -
`POWERTRAIN:AUTOMATIC_TRANSMISSION:CONTROL_MODULE:...` - ran **1,128px past a
320px viewport and 579px past a 1440px one**. Not a small-screen bug; a content
bug that a wide screen was hiding. Nothing in this product chooses those words.

The fix was one inherited declaration, and the first version of it was wrong:
`overflow-wrap: break-word` wrapped the text correctly and still let a flex item
force its row 366px wide, because `break-word` does not shrink min-content width
and a flex item defaults to `min-width: auto`. `anywhere` does. The two look
interchangeable by inspection; only laying out nastier content told them apart.

**Prose was set at 150-159 characters a line.** Measured on the built page at
1440px. Comfortable reading is 45-75 characters; about 90 is where the eye stops
reliably finding the start of the next line. The two worst blocks were the
`could not assess` list at 152 and a mechanic referral at 134 - the most
consequential sentences this product produces, set at the width hardest to read
them at. The whole design brief is "instrumentation, dense, evidence-forward",
and density had been allowed to mean *unbounded*, which is not the same thing.

Capping `.prose` at 62ch and `.prose-sm` at 64ch brought every block to 52-82
characters. The first attempt did not work on two table cells: `max-width` on a
`<td>` is a hint the automatic table layout may ignore, and it did, so those
columns kept setting 102- and 124-character lines while the stylesheet claimed
64ch. The measure has to sit on a block inside the cell. Five cells were wrong;
three of them were only found by the test written for the first two.

**The bundled fonts were being redistributed without their licence.** Three
variable subsets, all SIL OFL 1.1, which permits bundling inside a commercial
product on the condition that the licence text and copyright notice travel with
the binaries. Neither was present, which made the bundling itself non-compliant
while the interface built on top of it looked finished. This is the one
obligation in the repository that is legal rather than self-imposed.

---

## 4. The rule this phase adds

D-049. **A duplicated definition ships with the test that compares the copies, in
the same change.** Not a comment saying "mirrored in X" - that is a note asking a
future reader to do the check by hand, and five phases of evidence say they do
not.

Six such tests now exist beside the P2 enum check:

- `column-parity.test.ts` - every contract field has a column, and every column
  is explained by a contract field.
- `tokens.test.ts` - every `var(--tk-*)` in the source is defined in
  `globals.css`, and the BRAND.md colour table matches it value for value, and
  no colour joins the meaning ramp undocumented.
- `measure.test.ts` - the prose cap is declared in `ch`, and no prose class sits
  on a `<td>` where the cap would be silently discarded.
- `fonts.test.ts` - every bundled `.woff2` has its OFL beside it, the licence is
  the real upstream text rather than a summary, the notice accounts for every
  face, and nothing is vendored that no stylesheet loads.
- `layout.test.ts` - the one that opens a browser (D-050). The real components,
  the real stylesheet, laid out in chromium at 320/390/768/1440: nothing
  overflows, no paragraph passes 92 characters a line, and every piece of text
  clears WCAG AA against the first opaque background above it.

Each was written by first breaking the thing it checks and watching it go red.

Two of them found bugs in work that had *just been done deliberately and
carefully*, which is the strongest argument for the rule this phase can offer.
The BRAND.md test found nine wrong values in a colour table rewritten by hand
thirty seconds earlier, for exactly that purpose. The measure test found three
more uncapped table cells immediately after two had been fixed by reading the
code for them.

---

## 5. Where the project stands

| | |
|---|---|
| Phases | 8 |
| Tests | 517 |
| Gates | 9/9 green |
| Decisions logged | 51 |
| Finding types the engines can produce | 16 |
| **Finding types with a measured accuracy** | **0** |
| **Finding types enabled for a paid report** | **0** |
| **Real vehicles this has ever seen** | **0** |
| **Live model calls ever made** | **0** |

The four zeros have not moved and this phase could not have moved them. The
report is now a considerably better instrument for showing evidence it has never
gathered about a car it has never seen. That is worth saying plainly: **making
the evidence legible is not the same as making it correct**, and a buyer looking
at a beautifully cropped box around a region a model has never been measured on
is being shown a confident-looking picture of an unvalidated claim.

The accuracy page still says so in its first line. That is the only thing holding
those two facts together, and it is doing more work after this phase than before
it.

---

## 6. What is left, unchanged in order

1. **An API key, one car photographed, a Vercel deploy.** Eighth phase asking.
2. **Run vision live and label the output.** The first real photograph will
   falsify something.
3. **Measure, publish the misses.** `bench/` is built, tested and empty.
4. **Persistence and Stripe.** The grant is enforced but issued without payment;
   `inspections.ts` is local disk and a subprocess and says so in its own header.
5. **Repair cost bands.** A licensing question, not an engineering one.

Newly named this phase, and not yet handled:

- **Media is served unguarded.** `/f/<id>/*` is static: the report *page* checks a
  grant, the photographs behind it do not. It costs nothing while exactly one
  synthetic inspection exists and is a real hole the moment a second one does.
  Whatever replaces local disk has to serve media through the same check.
- **`BOX_FILL = 0.55` and the 700px/620px layout breakpoints are judgement, not
  measurement.** They have been checked against one synthetic fixture at three
  viewport widths.
- **The stress cases are derived, not generated.** `stress.ts` (D-051) mutates
  the real fixture into eight adversarial shapes and validates each through
  `parseReport`. That covers the failure modes anyone thought to name. It is not
  property-based: nothing searches the space of legal reports for a shape nobody
  anticipated, and the two overflow bugs it found were both found because someone
  guessed the right nasty input.

The measurement phase is still the honest successor to this one, and it still
needs a key and a car.

---

## 7. NEXT

Still the measurement phase, and it still cannot start without a key and a car.
Nothing in this phase changed that, and a report that displays evidence well is a
sharper version of the same unproven instrument - which is worth being slightly
uncomfortable about, rather than pleased.
