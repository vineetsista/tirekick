# PHASE 11 - THE CHECKS WERE THE CLAIMS

Branch: `main`
Gates: 13/13 green.

P10 ended by saying that writing a test is not enough, because a test can pass
for a reason unrelated to the code it is presented as guarding. This phase took
that seriously and pointed six independent audits at the repository, then refuted
every finding they produced.

**33 confirmed, 17 refuted.** And the confirmed ones were, with few exceptions,
not missing checks. They were the checks.

---

## 1. What this phase was

P10 left four items open in its own §4. One of them was already fixed - the
money columns had been changed to `doublePrecision` in the same commit that
carried the report naming them as open, and a type-parity test already refused
any dollar column that could not keep the cents. So the phase report describing
what nothing checked ended with a paragraph nothing checked.

That is the whole shape of this phase in one sentence, and it is worth being
uncomfortable about, because the correction was found by an agent reading the
code rather than by any of the eleven gates.

The other three were closed. Then six audits ran over the rest: the engines for
correctness, the engines for unpinned mechanisms, the web and the contracts, the
documents for drift, the repository for privacy and security, and the README as a
cold reader. Every finding was then handed to an adversary instructed to refute
it, with instructions to default to refuted.

---

## 2. The thing worth reading

**The redaction gate announced, in its own output, that it did not read videos.**

    14 still image(s): reviewed, signed off, no metadata container
    not examined: audio_01.wav, video_01.mp4. This tool reads still images only,
    and an .mp4 can carry GPS in its (c)xyz atom. Nothing here has checked them.

That is an honest sentence. It is not a check, and it returned zero, and the gate
was green over it for four phases. What sat underneath it, in this repository's
own committed fixture, was a clip carrying three separate payloads: an encoder
banner in a `(c)too` tag atom, a second copy of it in the 32-byte
`compressorname` of the sample entry, and x264's entire build string and option
list in a user-data SEI down inside `mdat`, where no container reader looks at
all. A real walkaround video is shot standing next to the car, and carries the
position it was shot in beside them.

**The same gate never opened `history_01.txt` either, and never named it.** Every
walk in the tool was an allowlist of suffixes, so a file whose type nobody had
predicted was invisible: not listed, not reviewed, not stripped, and absent from
the success line. In this repository that file is a synthetic title history. In a
buyer's directory it is a scan of a title certificate with their address on it.

Both are the same defect as the five frames P10 found, one format up, and this is
the third phase in a row where the repository's own media failed the gate it had
just been handed. The lesson is not about media. It is that a gap stated in prose
stops being read as a gap - it becomes a caption on a green run.

---

## 3. What shipped

**The container check reads bytes, in three formats** (D-071). A pure-Python
ISO-BMFF box walker, a RIFF/WAVE chunk walker, and a real AVC sample-table walk -
`avcC` for the NAL length prefix, `stsz` for the sizes, `stsc`/`stco` for where
samples sit - because grepping `mdat` for a byte pair fires on compressed data by
coincidence, and a check that cries wolf is a check people learn to skip. Nothing
is ever removed: `stco` holds absolute file offsets, so a `udta` is retyped to
`free` and zeroed at its original size. Creation timestamps are read by value,
because they say when the car was filmed.

**Nothing in the media directory is invisible** (D-072). The default inverted from
skip to refuse. Documents are their own category - nothing strips a `.txt`, so
what they get is a person confirming the file is safe to commit.

**The eval harness computes the four metrics it promised at P0, and refuses to
report them** (D-073). F1, precision at 0.80, a severity confusion matrix and
calibration. The eval set is empty, so all four are ratios over zero, and three of
the four fail toward *flattery* if written the obvious way - an expected
calibration error accumulated from 0.0 and never divided reports **0.0, which
reads as perfectly calibrated.** Every rate with a zero denominator is null, the
result file carries `"scored": false`, and `render()` prints the refusal instead
of the table, because a table of dashes is still a table.

**A denial is scoped to the brand standing next to it** (D-078).
`SALVAGE TITLE ISSUED 03/2019, no accidents reported` produced no finding at all.
A vehicle whose own paperwork declares a salvage brand shipped as clean. That is
the inverse of P10's regression and it is worse, because a false major is
something the buyer can check - LAW 1 puts the quoted line beside the claim - and
a silent drop gives them nothing to check.

**The clamp publishes facts the pipeline owns, not the model's prose** (D-080).
LAW 2 decided "warns or clears" from severity alone and then copied the model's
sentence into the report verbatim, so a plausible `minor` draft reading *"the pads
appear to have plenty of life left"* reached a buyer as a brake observation. A
deterministic control that forwards generated text is only as deterministic as the
text.

**An extrapolated price is a refusal, not a $0 range** (D-081). Comps at 50k, 100k
and 150k miles with a subject at 260,000 produced `fair_range_usd = $0-$0`, an
`above_range` verdict, and a sentence the buyer was told to say out loud.

**Grants expire and can be revoked per inspection** (D-079), **an inspection
directory is claimed rather than assumed** (D-076) - 32-bit ids handed to
`mkdir(recursive: true)` merged two strangers' uploads and cross-granted their
photographs - **a promise this repository cannot read is refused rather than
skipped** (D-074), **the wordmark has one definition** (D-075) after drifting to
six sites in three tracking values, and **the last hand-typed number in the
generated standing table became a derived one** (D-077), two paragraphs under the
sentence promising every number in it was already derived.

### Still open

- `bumpRevocationEpoch` is exported, tested, and called by nothing. LIABILITY
  section 6 promises a revocable grant; the property exists in code and a buyer
  cannot exercise it. The same defect class in a smaller box.
- The revocation epoch is a file in the local workspace, so it inherits every
  limitation `inspections.ts` already declares about local disk. Persistence is
  still disk and Stripe is still a payment link.
- Nothing here reads a `.webm`, an `.mp3` or a `.pdf`. They are refused by name
  rather than skipped, which is a smaller gap than the one this phase closed and
  is still a gap.
- `_NEGATED_ASSERTION` blanks up to twenty characters past the negation, so
  "Salvage brand: none, title issued 2019" has the assertion verb swallowed and
  comes out denied. Not a regression, and widening that pattern is how this
  engine broke the last two times.

---

## 4. What mutation testing found this time

D-065 says a fix ships with the mutation that proves its test can fail. It went on
earning itself inside the phase that was applying it.

**Three mechanisms in this phase were decorative when written**, and a mutation
is the only thing that said so:

- A byte-level scrub that zeroes a video's `creation_time` was written, tested,
  and mutated. **Nothing went red.** ffmpeg's `+bitexact` flag had already zeroed
  those fields, so the scrub was doing nothing any end-to-end test could see -
  and the committed fixture was clean by an accident of one encoder flag rather
  than because anything checked. It is now pinned where it can fail, with no
  remux in front of it.
- Three malformed-container tests all stayed green under the mutation that
  disabled the malformed-container refusal, because a different guard rescued
  each of them. They would have passed a walker that silently stopped at the
  first box it could not parse. Replaced with two that fail.
- A harness-coverage predicate accepted a test whose body had been deleted, so
  the rule requiring every predicate to be exercised was satisfied by a test that
  exercised nothing.

Two more things were checked rather than trusted, which is the same instinct
arriving earlier:

- A crew was told that a dedupe key made a change safe. It wrote the test for
  that claim instead of accepting it, mutated the key, and watched the test go
  red - so "continuing past a denial cannot double-report" is now a checked fact.
- The wordmark test found a sixth call site while the docstring of the component
  removing the duplication said five, because the count had come from a grep and
  one site styled a `<Link>` rather than a `<span>`.

All of them are named here rather than quietly fixed, because the interesting
number is not how many tests passed.

---

## 5. Where the project stands

| | |
|---|---|
| Phases | 11 |
| Gates | 13/13 green |
| Audit findings confirmed this phase | 33 |
| Audit findings refuted this phase | 17 |
| Mechanisms found decorative by mutation, in this phase's own work | 3 |
| Finding types the engines can produce | 16 |
| **Finding types with a measured accuracy** | **0** |
| **Finding types enabled for a paid report** | **0** |
| **Real vehicles this has ever seen** | **0** |
| **Live model calls ever made** | **0** |

The four zeros have not moved. Eleventh phase.

What this phase is evidence for is narrower than P10's and points the same way.
P10 found that a crew following the rules ships mechanisms its own tests do not
pin. P11 found that the *checks themselves* are claims, and they rot exactly like
the claims they were written to police: a gate that names what it does not read
is read as a gate; a phase report's list of open defects goes stale in the commit
that writes it; a document describing an absent test keeps describing it for a
phase after the test is built; and a generated table can carry one typed number
directly beneath the sentence promising it cannot.

Eleven phases in, the repository is good at catching claims in the product and
still catching claims in its own instruments. The instruments are the thing to
distrust next.

---

## 6. NEXT

Still the measurement phase, and it still cannot start without a key and a car.
Eleventh phase asking.

Nothing above moved a zero. Every one of these fixes made the machine more honest
about a car it has never seen.
