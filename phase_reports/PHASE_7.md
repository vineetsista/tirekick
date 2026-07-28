# PHASE 7 - THE AUDIT

Tag: `v0.8` | Branch: `main` | 41 commits | 216 tracked files
Gates: 9/9 green, locally and in CI. 396 tests. 43 decisions logged.

This phase was not planned. P6 ended by saying there was no P7 to define and the
next move was not mine. Then I was asked whether everything was actually done -
end to end, README and all - and the honest answer turned out to be no, in four
separate places, three of which were things this project had already written down
and then not built.

---

## 1. What the audit found

I went looking for the gap between what the repository *claims* and what it
*does*. Four findings, in descending order of how bad they are.

**LAW 7 has required an end-to-end upload -> paid dossier test since P0. There was
none.** Six phases tagged ALL GATES GREEN with a clause of one of the seven laws
unmet. Not disputed, not deferred with a note - unnoticed.

**`/report/demo-01` had no access check.** The teaser projection was genuinely
correct; the free payload never contained a finding. But the paid page itself was
a static route anyone could open by guessing a URL. P4's own phase report listed
this as gap 4 and then four more phases shipped past it.

**LIABILITY.md section 4 specifies seven disclaimer placements. Two did not
exist** - the share page and the print running footer. Specified in P0, never
built, and the drift was inside the document that describes our liability
position.

**The walkaround video is in the brief's list of inputs and had never been
built.** `kind: "video"` was in the schema, `hasVideo` was in coverage, and
nothing processed one. In P6 I removed the claim from the landing page, which made
the copy honest and quietly shrank the product. That was the wrong trade.

The pattern is the same one P6 found on the landing page, and it is worth stating
as a general rule rather than as three incidents: **a document that describes the
build is not a check on the build.** LAWS.md, LIABILITY.md, the landing page and
`package.json` had each drifted from the code, and in every case nothing failed
because nothing looked.

---

## 2. What shipped

**`video.py` + `walkaround.py`** - the missing input. A 45-second walkaround at
30fps is 1,350 frames; sending them all costs roughly $30 in image tokens, most of
it spent on motion blur and on the same rear quarter four times. So the engine is
a selection problem: sample on a fixed grid, keep the sharpest frame per
1.5-second bucket by variance of the Laplacian, drop perceptual near-duplicates,
cap at 12. Survivors go through the *same* vision path as an uploaded photograph,
because a frame is a photograph that arrived inside a video.

Measured on the demo fixture: **coverage 67% -> 83%**, by supplying the exterior
side and three-quarter views the photographs never had. That is the number this
phase is actually for. A seller photographs the side they want shown; a buyer
walking round the car covers all of it.

The discards are reported alongside the keeps. "5 frames analysed" without "23
discarded" invites the reader to assume the whole video was examined - the same
examined-versus-covered distinction the systems table already makes.

**`access.ts`** - a stateless HMAC grant over the inspection id and the reason it
was issued. The reason travels inside the signature, so a `demo` grant cannot be
replayed as `paid` by editing a prefix. Exactly one id is publicly readable and it
is a named constant rather than an inferred flag. In production an unset signing
key is a hard failure, not a fallback: a well-known development key is the same as
no signing, and the failure mode is that every paid report is free forever.

**`flow.test.ts`** - the LAW 7 test, finally. Real bytes to a real directory,
shelling out to the real Python CLI, reading the real artifacts off disk. It
documents its own limits in its header: it drives the flow, not a browser. No
click, no network, no Stripe.

**`test_laws_are_kept.py`** - parses LAWS.md, extracts every file it names, and
fails if one is missing; asserts the e2e test exists and actually calls the flow;
asserts each law is still present with its key clause; asserts the gate script
still runs the suites the laws depend on.

**The share page and print footer**, with a diagonal watermark that survives a
screenshot where a footer does not, and `noindex`, because a shared report should
not end up in a search index attached to somebody's car.

**The README**, rewritten. It now opens with four zeros and a sentence saying they
are the honest summary, carries the seven laws as a table with an *enforced by*
column, and includes the pipeline diagram and the four-step procedure for adding a
finding type - the one that makes the eval gate unavoidable.

---

## 3. The things the new tests found immediately

Writing a check is how you find out what it catches. Three, within an hour:

- `pnpm run py:types` still lacked the `--config-file` flag that had made the
  mypy gate silently non-strict for three phases. The gate script had it; the
  package script did not; nothing compared them.
- `inspect:fixture` did not emit the teaser, so `fixture:clean` could not notice
  the teaser going stale.
- The e2e test crashed on its first run. An uploaded photo with no cached
  response took the whole pipeline down, because stage-1 `classify_views` never
  caught `FixtureMissing` the way stage-2 did. The empty-handed case had never
  been exercised, because every previous run used the fixture that has every
  response cached.

That last one is the useful one. It is the exact path a real buyer's first upload
takes, and it was fatal.

---

## 4. Decisions (D-039 - D-043)

- **D-039** Walkaround video ships as a frame-selection problem.
- **D-040** The perceptual dedupe threshold is a guess, and says so.
- **D-041** The paid report is gated by a signed grant.
- **D-042** The laws are now checked against the build.
- **D-043** The share page and print footer exist because the liability doc said
  they did.

D-040 is the one I would defend hardest. The threshold moved from 8 to 5 and is
deliberately **not** tuned against the fixture: a synthetic panning strip has far
less texture than a car in daylight, so its hash distances are compressed, and
fitting to it would be overfitting to a drawing. The constant carries a comment
saying it is unvalidated, and the test asserts the property that matters - camera
pause below the threshold, sweep above it - rather than the number.

---

## 5. Where the project stands

| | |
|---|---|
| Phases | 7 |
| Tests | 396 |
| Gates | 9/9 green, local and CI |
| Decisions logged | 43 |
| Finding types the engines can produce | 16 |
| **Finding types with a measured accuracy** | **0** |
| **Finding types enabled for a paid report** | **0** |
| **Real vehicles this has ever seen** | **0** |
| **Live model calls ever made** | **0** |

The four zeros have not moved and this phase could not have moved them. Everything
above is plumbing, correctness and honesty work. None of it is evidence that the
product works, and one more input being built means one more input with no
measured accuracy.

---

## 6. What is left, unchanged in order

1. **An API key, one car photographed, a Vercel deploy.** Seventh phase asking.
2. **Run vision live and label the output.** The first real photograph will
   falsify something.
3. **Measure, publish the misses.** `bench/` is built, tested and empty.
4. **Persistence and Stripe.** The paywall is now enforced but the grant is issued
   without payment; `inspections.ts` is local disk and a subprocess, and says so in
   its own header. Neither is production.
5. **Repair cost bands.** A licensing question, not an engineering one.

Newly named and previously unstated: the prompt version is not in the response
cache key, `min_n = 50` in the eval gate is asserted rather than derived, and
`DUPLICATE_HASH_DISTANCE` has never seen real footage.

---

## 7. YOUR 2 HOURS

### Read (30 min)

1. **`README.md`** - 10 min. It is rewritten; tell me if the first screen still
   overstates anything.
2. **`packages/engines/tests/test_laws_are_kept.py`** - 10 min, header included.
   It is the smallest file here with the largest claim on the project's honesty.
3. **`DECISIONS.md` D-039 to D-043** - 10 min.

### Assigned reading (20 min)

**`phase_reports/PHASE_4.md`, section on gaps.** Your own project's report from
three phases ago, naming an unenforced paywall, which then shipped three more
times.

The point is not the paywall. It is that writing a gap down felt like handling it.
Every check added this phase exists because something true was written in a
markdown file and nothing ever read it back.

### FOUNDER REPS

Unchanged, and I am still not going to invent new ones.

1. **Vercel deploy.** `apps/web`, `pnpm --filter web run build`, no env vars.
2. **API key** in `.env`, low cap.
3. **One car**: eight photographs per `bench/README.md`, thirty seconds of engine
   audio, **and now a walkaround video** - one slow lap, phone held steady, no
   narration needed.

Rep 3 is still the one that changes what this project is.

---

## 8. NEXT

Same answer as P6, and I mean it more now. There is no P8 to define. The build has
run ahead of the evidence by five phases, and this phase - which added a real
engine but mostly went back over ground already claimed - is what running ahead
looks like from the inside.

The next phase is the measurement phase, and it cannot start without a key and a
car.
