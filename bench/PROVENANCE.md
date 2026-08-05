# BENCH PROVENANCE

LAW 3 requires that every media file in this repository has a recorded origin,
and it names this file as the record for the eval set. This is that record.

**There is no media in `bench/` yet.** 4 files are committed here and none of
them is media: `README.md` (how to capture and label), `PROVENANCE.md` (this
file), `labels/TEMPLATE.json` (an empty label file to copy), and
`results/latest.json` (the harness output, currently scoring nothing). The eval
set does not exist; that is why 0 of the 16 registered finding types are enabled,
and `docs/ACCURACY.md` says so on the page the product links from every report.

This file exists ahead of the media rather than after it, because a provenance
record written retroactively is a reconstruction, not a record.

When capture sessions land under `bench/inspections/`, every media file gets a
row here before it is committed: what it is, who photographed it, when, of what
vehicle, and with what consent. Media saved manually from a public listing gets
the same treatment, one file at a time, with the listing named - no bulk
collection, no crawler, not even a "temporary" one (LAW 3).

A media file in `bench/` that is not listed here should not be in the repository.
`packages/engines/tests/test_provenance.py` enforces the enumeration - a committed
file with no row, a row naming a file that is not there, and the count above are all
gates as of P10. It does not enforce that a row is TRUE, which for real capture
media is the half that matters: nothing here can check who photographed a car or
whether they had the seller's consent.

That gate arrived late. `fixtures/PROVENANCE.md` went seven phases with the
rendered spectrogram unlisted and two phases with the walkaround video and its five
frames unlisted - seven files in all - under exactly the arrangement this paragraph
used to describe. The emptiness of this directory is why the same thing has not yet
happened here, and emptiness is not a control.

Plates and faces are blurred before anything is committed. The redaction engine
exists as of P9 (`packages/engines/src/tirekick_engines/redact.py`, driven by
`scripts/redact_media.py`), and it refuses to pass an image that carries no
signed review record - absence is treated as unreviewed, not as nothing to do.
The repository stays private until that step has been run over everything here -
see `bench/README.md` and DECISIONS.md D-022 and D-029.
