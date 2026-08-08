# FIXTURE PROVENANCE

LAW 3 requires that every media file in this repository has a recorded origin. This
is that record. It is maintained per file, by hand, and a file that is not listed
here should not be in the repository.

Until P10 nothing checked that, and it showed. This file listed eight photographs,
one audio clip and one text document, while the directory also held a rendered
spectrogram (committed in P3), a walkaround video, and five frames extracted from it
(both P7). Seven files covered by the front page's "all media is synthetic" claim
had no provenance row at all, and the spectrogram's gap ran from P3 to P9. Each gap
opened in the commit that added the artifact and survived every phase gate after it,
because no gate read this file.

`packages/engines/tests/test_provenance.py` now reads it, in three directions: a
committed file with no row, a row naming a file that is not there, and the file
counts stated about whole directories. What it does **not** check is whether a row
is true - nothing here opens `audio_01.wav` to confirm it was synthesised the way
the row says. This document's enumeration is now a gate; its descriptions are still
prose, and the P10 audit found a frames row whose four counts were each correct and
whose sentence around them did not add up.

## How this file is checked

The parser is deliberately simple, so the conventions it relies on are written down
rather than inferred:

- A file is claimed by putting its name in a code span: `` `photo_01.jpg` ``.
- A contiguous run is claimed as `` `photo_01.jpg` `` .. `` `photo_08.jpg` `` and is
  expanded, so a ninth photograph in a directory whose row still ends at the eighth
  is an uncovered file rather than a silent pass.
- A `*` or `<placeholder>` makes a row a pattern, and **a pattern must state its
  count** - either in the next table cell or as digits immediately before the span.
  A pattern with no count is the one shape in which a new file can hide.
- A whole-directory count is written as the directory in a code span followed by
  `N files` on the same line.

The file list comes from `git ls-files`, not the working tree: an uncommitted
scratch file is not yet a provenance obligation.

| File | Origin | Notes |
|---|---|---|
| `PROVENANCE.md` | This document | Listed because the check requires every committed file under `fixtures/` to have a row, and exempting the record from its own rule is how records start drifting. |

---

## demo-01 - synthetic pipeline fixture

**Everything in `demo-01/media/` is synthetic. None of it is a photograph, a
recording, or a record of any vehicle. No accuracy claim will ever cite it.**

The purpose of this fixture is to prove the pipeline runs end to end without an API
key and to give the contract, the clamp, and the report viewer something real to
operate on. It proves plumbing. It proves nothing about cars.

### Media - `demo-01/media/`

Every file here is generated except `history_01.txt`, which was written by hand and
says so in its own row. Regenerate the photographs, the audio and the video with:

```
packages/engines/.venv/bin/python scripts/make_fixture_media.py
```

Then regenerate the frames and the spectrogram, which are derived from the video and
the audio rather than drawn (see the two rows that name their own scripts):

```
packages/engines/.venv/bin/python scripts/refresh_video_cache.py
packages/engines/.venv/bin/python scripts/refresh_audio_cache.py
```

| File | Origin | Notes |
|---|---|---|
| `photo_01.jpg` .. `photo_08.jpg` | Drawn by `scripts/make_fixture_media.py` | 1600x1200 diagrams, not photographs. Each carries a burned-in diagonal "SYNTHETIC FIXTURE - NOT A PHOTOGRAPH" watermark so a frame lifted out of the repo still declares itself. |
| `video_01.mp4` | Drawn by `scripts/make_fixture_media.py` (`make_video`) | 14.0s, 640x400, 15fps, encoded by ffmpeg/libx264 at crf 26. A window panning across a wide painted strip - it is a walkaround in the sense that consecutive frames show different regions, and in no other sense. "SYNTHETIC WALKAROUND - NOT A VEHICLE" is painted into the strip. Two segments are deliberate and are ground truth for `test_video.py`: 4.0-6.0s is motion-blurred, 8.0-10.5s is stationary. |
| `video_01.frame_01.jpg` .. `frame_05.jpg` | Extracted from `video_01.mp4` by `scripts/refresh_video_cache.py` | Not drawn and not hand-picked. The selector sampled 28 frames at 2fps, discarded 4 as too blurred, kept the sharpest survivor in each 1.5-second bucket, and dropped 4 of those as showing a view already chosen - leaving these five, at 0.0s, 2.0s, 3.5s, 8.5s and 13.5s. The bucketing step is why the three numbers do not subtract to five: it is a per-window winner, not a filter. Every count here is in `demo-01/cached/video.frames.video_01.json` and none of them is typed twice. They are committed rather than decoded at report time so that a fixture run needs no ffmpeg (D-026). The frames inherit the video's watermark, because it is painted into the strip they are cropped from. |
| `audio_01.wav` | Synthesized by `scripts/make_fixture_media.py` (`make_audio`) | 22.0s, 22050Hz, mono, 16-bit PCM, written with the `wave` module - no ffmpeg involved. A 31.5Hz fundamental with six harmonics, 0.7Hz amplitude modulation, and gaussian noise from a seeded generator, with three impulses placed at 5.0s, 11.5s and 17.25s. Those times are ground truth by construction, which is what lets `test_signal.py` assert the onset detector *found* something rather than merely ran. It still does not sound like a car. The previous version of this fixture was two mixed sine tones, and this row said so for seven phases after it stopped being true - the synthesis was replaced in P3 and the row was still describing the old one at P9. A pure tone has no transients, so the detector ran against it and found nothing, forever, indistinguishably from being broken. |
| `audio_01.spectrogram.png` | Rendered from `audio_01.wav` by `scripts/refresh_audio_cache.py` | Deterministic arithmetic over the waveform, committed for the same reason the frames are (D-026). It is the picture the audio engine ships in place of a claim (D-027), so it is product output as much as it is fixture media. |
| `redactions.json` | Written by `scripts/redact_media.py init`, signed by a human | Not media. The D-022 review record for every image in this directory, committed because `redact check` refuses a directory whose images have no signed record - and because the repository submitting to its own media rule was a P10 change, not something it had always done. Every entry here says `nothing_to_redact`, which is true and uninteresting: the media is drawn, so there is no plate and no face. It is also the file D-052 exists for. A sidecar naming a reviewer and boxing faces must never be served, so the media route serves what the report cites rather than what the directory holds, and `media.test.ts` puts a real one of these in a directory and asserts a paid grant cannot fetch it. |
| `history_01.txt` | Hand-written for this repository | An invented seller disclosure. It declares itself in its first three lines. It denies salvage, flood, lemon and junk brands and reports hail and structural damage, so that the title-brand scanner is exercised in both directions on every run - including the negation cases, which are the ones that can wrongly condemn a clean car. |

The marked rectangles drawn in each image are at the exact coordinates the cached
findings cite, so the evidence boxes in the report land on something visible. That
correspondence is the point of drawing them.

### Manifest - `demo-01/manifest.json`

Hand-written. Declares the eleven assets above (eight photos, the video, the audio,
the document), the documentation VIN, the asking price and mileage, and the five
comparable listings. `"synthetic": true` is read by the pipeline and is what puts the
"contains synthetic media" note above the verdict.

### Cached responses - `demo-01/cached/` - 31 files

Two different kinds of file live here, and the difference matters more than the
shared directory suggests.

**29 `vision.*.json` files are hand-authored placeholders. Not model output.** No
model has seen these images. The text was written by the build team to exercise the
schema, and every one of them carries a `_fixture_note` saying so.

11 `vision.*.video_01_f<NN>.json` files of the 29 describe the extracted video
frames rather than the photographs, which is how the fixture demonstrates the thing
that matters about a walkaround: frames close coverage gaps the seller's photographs
left.
All five frames carry a view classification - four exterior, one `unknown`. Only two
of those four carry stage-2 damage, repaint and rust responses.

**That asymmetry is deliberate and it is load-bearing.** A stage-2 pass with no
cached response does not run, and the engine stays silent rather than inventing a
"nothing found" - and, importantly, does not mark the system as examined either. Two
exterior frames that are classified and then not analysed are the standing proof
that the degradation path behaves that way on every run, not only when a unit test
constructs it. If a future edit makes an uncached pass fabricate a clean result, the
report built from this directory changes.

**2 files are measured, not authored**, and carry `_note` rather than `_fixture_note`
because they are not placeholders for anything:

- `audio.features.audio_01.json` - written by `scripts/refresh_audio_cache.py`.
  Deterministic arithmetic over `audio_01.wav`: duration, dBFS, dominant frequency,
  steadiness, and detected transients. No model, no claims.
- `video.frames.video_01.json` - written by `scripts/refresh_video_cache.py`. The
  frame selection above, with the sharpness score behind each keep and the counts
  behind each discard.

Two of the hand-authored files are deliberately adversarial, so that the LAW 2 clamp
is exercised on every single run rather than only in the unit tests:

- `vision.engine_bay.photo_08.json` contains `vf_bay_03`, a fabricated
  "brake components appear to be in good condition" at confidence 0.96. The clamp
  must discard it. If it ever appears in a report, the law has failed.
- The same file contains `vf_bay_02`, an adverse observation near the front hub. The
  clamp must keep it as a mechanic referral, stripped of severity and confidence.
  If it disappears, the asymmetry in DECISIONS.md D-005 has failed - we would be
  suppressing a warning, which is its own kind of dishonesty.
- `history_01.txt` reports structural repair, which must leave the pipeline as a
  mechanic referral rather than a finding. It is the standing proof that LAW 2 is
  about the system named, not about which engine happened to name it.

### VIN and vehicle record - this part is real

**The federal records in this fixture are genuine, and the VIN is a documentation
VIN.** This is the one place where `demo-01` is not synthetic, and it is worth being
precise about, because "some of this is real" is exactly the kind of claim that
rots if nobody writes it down.

`1HGCR2F37DA000000` carries the real world manufacturer identifier and descriptor
section of a 2013 Honda Accord LX sedan - the manufacturer, plant, line, body and
engine codes - with the last six characters, the serial that identifies one physical
car, set to `000000` and the position-9 check digit recomputed so the VIN is
internally valid. It decodes cleanly against live vPIC. It belongs to nobody. See
DECISIONS.md D-019.

Everything the data engine reports about it is real: the decode, the five recall
campaigns, and the 1,418 owner complaints are what NHTSA returned on the date
stamped in `fixtures/federal/`. The photographs remain drawings, and the report says
so above the verdict. The two statements sit next to each other on purpose - a
reader should be able to tell exactly which half of this fixture is which.

### Comparable listings

The five comps in `manifest.json` are invented numbers, not real listings, and are
labeled as such in their `notes`. Four exist to exercise the mileage fit in the
pricing engine, which needs a spread of mileages to fit against. The fifth is a 2013
Civic priced beside the Accords, present so the relevance check is exercised on
every run rather than only when somebody remembers to test it.

### Repair cost bands

Two cached findings carry an invented `estimated_cost_usd` band. In a paid report a
cost band needs a real source, and the model is never asked for one - see DECISIONS.md
D-024, which names this file as the place the fixture's invented bands are declared.

---

## Federal record cache - `fixtures/federal/` - 27 files

Snapshots of four public NHTSA endpoints, written only by
`scripts/refresh_federal_cache.py` and read by everything else:

| Filename pattern | Count | Endpoint |
|---|---|---|
| `vpic.decode.<vin>.json` | 6 | vPIC `DecodeVinValues` |
| `nhtsa.recalls.<year>.<make>.<model>.json` | 6 | `recalls/recallsByVehicle` |
| `nhtsa.complaints.<year>.<make>.<model>.json` | 8 | `complaints/complaintsByVehicle` |
| `nhtsa.complaint-models.<year>.<make>.json` | 6 | `products/vehicle/models`, which resolves NHTSA's second model vocabulary (D-020) |
| `GOLDEN_VINS.json` | 1 | not a snapshot - the golden set itself, described below |

There are more complaint files than recall files because one recall query can cover
several body styles that complaints index separately - the 2013 F-150 is three
complaint files and one recall file.

Every file records the exact URL it came from, when it was fetched, and the SHA-256
of the response body. CI reads this directory and never opens a socket (LAW 7).

Complaint responses are the exception to "we store what we received": they are
reduced to counts before anything is written, because the raw responses are
megabytes of narratives written by members of the public, carrying partial VINs and
accounts of other people's crashes. Those never enter this repository. The hash of
the full response survives, so the counts stay traceable to the bytes they came
from. See DECISIONS.md D-015.

`GOLDEN_VINS.json` lists the five VINs the P1 golden tests run against, and why each
one is in the set. There are six decode files rather than five because the sixth is
`1HGCR2F37DA000000`, the demo-01 fixture VIN, which the pipeline needs cached and
the golden tests do not score. Recall counts genuinely change over time, so
refreshing this cache is a deliberate act that produces a diff someone has to read.

---

## Generated report artifacts - `fixtures/reports/`

`demo-01.report.json` and `demo-01.teaser.json` are output, not input. Both are
written by `pnpm inspect:fixture` and committed so that the `fixture:clean` gate can
byte-compare them after every run; a change anywhere in the engines that alters
either file fails the build with a diff someone has to read. They contain no media
and no origin question of their own - everything in them derives from the files
enumerated above.

---

## Real media

There is none yet, in this directory or in `bench/`. It was expected in P2 and every
phase since has shipped without it, which is the single fact that keeps every
finding type disabled - `docs/ACCURACY.md` says so at the top. When it arrives this file
gains a row per file: what it is, who photographed it, when, and with what consent.
Media saved manually from public listings gets the same treatment, one file at a
time, per LAW 3. The eval set's own record lives in `bench/PROVENANCE.md`.
