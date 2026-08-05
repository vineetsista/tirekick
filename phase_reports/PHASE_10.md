# PHASE 10 - SEVEN GREEN FIXES, AND WHAT WAS WRONG WITH ALL OF THEM

Branch: `main` | 942 tests | 70 decisions logged
Gates: 11/11 green.

P9 ended by naming the half of a 70-finding audit it had not reached, starting
with an EXIF leak. This phase is that half. It went differently than planned, and
the way it went is the phase's actual result.

---

## 1. What was supposed to happen

Seven crews, one per defect cluster: the redaction tool, the history classifier,
the zod/Pydantic contract gap, the test infrastructure that could not fail, the
accuracy page, the web defects, the drifted documents. Each was given the audit's
verified findings and the repository's rules - tests first, watch them go red,
name the failure the comment prevents.

They did that. Seven crews, seven sets of fixes, every targeted suite green.
`pnpm gates` went nine for nine. 776 tests passed.

Then an adversary was pointed at each crew's work with one instruction: refute it.

**Seven of seven were defective.** Not one came back sound.

---

## 2. The one that mattered

The history crew closed a false negative and opened a false positive.

`_CLAUSE_BREAK` splits a document line into statements, because a denial has a
scope and it is not the whole line - "No accidents reported. SALVAGE TITLE ISSUED
03/2019" denies accidents and reports salvage. The crew added a pipe to that
pattern, on the reasoning that a table row holds two statements.

It does. And nothing tells a cell separator apart from a sentence boundary except
what the cells say. So every clean row of every markdown history report:

    | Salvage | None reported |

split into a bare label and an answer about nothing, and the label alone read as
an assertion. A clean-title document fed to the scanner produced five findings:

    title_salvage_doc_01     major  1.0   excerpt: '| Salvage | None reported |'
    title_flood_doc_01       major  1.0   excerpt: '| Flood or water damage | No records found |'
    title_total_loss_doc_01  major  1.0   excerpt: '| Total loss | Not reported |'
    title_lemon_doc_01       major  1.0   excerpt: '| Lemon law buyback | None |'
    title_junk_doc_01        major  1.0   excerpt: '| Junk | None |'

Five major findings at full confidence, on a car whose paperwork denies all five,
each one quoting its own denial as the evidence. This is the error `ACCURACY.md`
names as the one that costs a buyer a good deal, and D-017 - written in P2 - says
in as many words that an unanticipated wording ships as ambiguous rather than as
major, because that is the right direction to be wrong in.

The crew's own comment, three lines above the change, explains why the pipe must
not be there: splitting a table row "would turn the commonest clean-title layout
into a page of false alarms."

**Nine gates were green. 517 tests had not caught it, then 612, then 776.**

The pipe bought exactly one thing: one contrived row upgraded from hedged to full
strength. Removing it reddens one test, which at HEAD was already handled at
ambiguous. That is the whole trade, and it was made in the wrong direction by a
crew that had written down the reason not to.

---

## 3. What actually found it

Not a test. Deleting things.

The adversary took each mechanism the crew had added, broke it, and required
something to go red. Where nothing went red, the mechanism was unpinned - working
today, unprotected tomorrow, and indistinguishable in a green run from a mechanism
that does nothing. That found the pipe regression by asking a different question:
not "does this pass" but "what input shape does this now handle differently that
nobody tested".

It also found, across the seven crews:

- a redaction check that passed a signed-off JPEG carrying GPS in an MP4 appended
  after the EOI marker - the Samsung Motion Photo layout, which is what a large
  fraction of real phone photographs are;
- a format-refusal branch that could be deleted entirely with all twelve of its
  crew's new tests still green, because the one test guarding it passed for an
  unrelated reason;
- `phrase_has_teeth`, written to stop a law being kept by a toothless phrase,
  accepting `user-provided` - one of the four phrases it was written for - while
  its self-test parametrised the other four and quietly dropped that one;
- a test named `..._the_sdk_actually_defines` that asserted against a stub built
  three lines above it, and stayed green against a fake `anthropic` exporting
  neither name;
- a column-parity test with no completeness gate on its own table list: a fourth
  `pgTable` shredding the contract could be declared and eighteen tests stayed
  green;
- a markdown fix that implemented the CommonMark flanking rule on the next
  character rather than the delimiter run, so `a * b` was fixed and `2 ** 8` still
  failed the build;
- a comment calling `PRICE_USD` "the constant that actually charges it", when the
  amount lives in a Stripe payment link and the constant is never sent - and a
  second, unlinked price in Python already rendering to buyers on the teaser;
- three factual errors newly introduced by the crew fixing factual errors,
  including an arithmetic claim that 28 - 4 - 4 leaves five.

So D-065: a fix ships with the mutation that proves its test can fail. It earned
itself twice more inside this phase. The replacement history classifier passed its
own 123 tests and then survived a mutation with one guard unpinned - deleting the
guard that stops a trailing "none reported" from deleting an asserted salvage
brand changed nothing, so that guard got the test it was missing. Every mechanism
in this phase's final state has a recorded mutation and a red test behind it.

---

## 4. What shipped

**The redaction tool reads bytes** (D-067). `check` asserts the absence of
metadata containers - EXIF, XMP, IPTC, JPEG COM, PNG text chunks, and trailing
data after the EOI marker - rather than hunting for coordinates, because Pillow
parses some container formats and silently returns nothing for others, so a
coordinate-hunting check reads an empty dict off a geotagged file and passes it. A
format it cannot strip is refused, not skipped.

Then the repository submitted to its own rule for the first time. The gate runs
over `fixtures/demo-01/media` in `gates.sh`, and immediately found five committed
video frames carrying ffmpeg's encoder banner in a COM segment - while README.md
told the world the committed images carry no metadata. It had been true of the
photographs and false of the frames since P7.

**The history classifier was rebuilt around what a clause actually is** (D-066).
A pipe is never a boundary. `.` and `;` are, but a following clause containing
nothing except answer words belongs to the label in front of it, while one with a
subject of its own denies the brand beside it nothing. Every separator is now
exercised in both directions, because a separator tested only where it upgrades is
a separator nobody weighed.

**Three published numbers became generated ones.** `docs/ACCURACY.md`'s gate table
is written from the registry (D-061) - it had drifted to fifteen rows for sixteen
types, with Status values naming phases four phases gone. The README's standing
table and its quotation of the product are written from the repository (D-063) -
the test count was wrong, and the block quoting the product's own words in a code
fence was a paraphrase of them. Both documents had claimed to be generated. Neither
was.

**`/accuracy` is rendered rather than dumped** (D-062), by a parser that throws on
anything it does not understand and parses at module scope, so a document it cannot
read fails the build instead of reaching a buyer half-rendered. For nine phases the
page LAW 6 obliges the product to link showed its own source in a `<pre>`.

**The provenance records are compared against `git ls-files`** (D-069), after one
of them ran seven phases with an unlisted artifact while stating in its own text
that nothing checked it.

**LAW 2 moved onto the zod sub-schemas** (D-070), where Pydantic already enforced
it. **One price, one source** (D-068), with the Stripe amount named as the thing
this repository cannot assert. **The SDK contract is checked by a job that installs
the SDK** (D-064), because the one line that would check it inside pytest is the
line that removed the retry tests from CI for a phase.

### Still open

- `redact check` reads still images only. An `.mp4` can carry GPS in a `(c)xyz`
  atom and `fixtures/demo-01/media/video_01.mp4` is committed. The tool says so in
  its own output rather than reporting a clean directory.
- `docs/EVAL.md` has promised F1, precision at high confidence, a severity
  confusion matrix and a calibration plot since P0. `bench.py` computes none of
  them. Now marked unimplemented in the document instead of reading as though they
  exist.
- Money columns in the db schema are integers where the contract is float, so
  persisting $8499.50 truncates. Named with its exemption rather than left silent.
- `unkept_promises()` inspects `.py` only; a future `Component.tsx::useThing`
  promise would have its file checked and its symbol ignored. Stated in the
  docstring rather than pretended away.

---

## 5. Where the project stands

| | |
|---|---|
| Phases | 10 |
| Tests | 942 |
| Gates | 11/11 green |
| Decisions logged | 70 |
| Audit findings from P9 | 70 |
| Crews whose work survived adversarial review unmodified | **0 of 7** |
| Finding types the engines can produce | 16 |
| **Finding types with a measured accuracy** | **0** |
| **Finding types enabled for a paid report** | **0** |
| **Real vehicles this has ever seen** | **0** |
| **Live model calls ever made** | **0** |

The four zeros have not moved. Tenth phase.

What this phase is actually evidence for is narrower and more uncomfortable than
the previous nine. Those found claims that nothing checked, and the fix was always
to add the check. This one added checks, in seven places at once, by crews
following that exact rule - and every one of them shipped something the check did
not cover. One shipped a defect worse than the one it fixed.

The rule "write a test" is not sufficient, because a test can pass for a reason
unrelated to the code it is presented as guarding, and that is invisible in a green
run. The only thing that distinguished a real mechanism from a decorative one was
breaking it on purpose. Nine gates, 776 tests, and a clean car reported as a wreck.

---

## 6. NEXT

Still the measurement phase, and it still cannot start without a key and a car.
Tenth phase asking.

Everything reachable without one has now been done twice - once by a crew and once
by the adversary that refuted it. The repository is public as of this phase, which
changes nothing about the four zeros and removes the last excuse for the parts of
it that were only ever going to be read by their author.
