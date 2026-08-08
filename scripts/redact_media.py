"""Blur number plates and faces before media is committed. D-022.

Three modes, and the order matters.

    python scripts/redact_media.py init    <dir>   scaffold a record per image
    python scripts/redact_media.py propose <dir>   ask the model for regions (needs a key)
    python scripts/redact_media.py apply   <dir>   blur, in place, irreversibly
    python scripts/redact_media.py check   <dir>   fail if anything is unreviewed
                                                   or still carries metadata

`propose` never writes a reviewer name. A human opens `redactions.json`, checks
every box against the image, adds or corrects regions, and puts their own name in
`reviewed_by`. Only then does `apply` do anything, and only then does `check`
pass.

That sequence is the whole point. An automatic detector that misses one plate in
fifty produces a folder everybody now believes is safe, and `git rm` does not
remove anything from history - a single miss is permanent the moment the
repository goes public. So the model proposes and a person decides.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "packages" / "engines" / "src"))

from tirekick_engines import prompts, redact  # noqa: E402
from tirekick_engines.client import LiveModeUnavailable, ModelClient, resolve_model  # noqa: E402
from tirekick_engines.cogs import CostMeter  # noqa: E402
from tirekick_engines.models import BoundingBox  # noqa: E402

LOCATE_SCHEMA = {
    "type": "object",
    "properties": {
        "regions": {
            "type": "array",
            "description": "Everything that must be hidden. Empty is a real answer.",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": list(redact.REDACTABLE_KINDS)},
                    "box": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number", "minimum": 0, "maximum": 1},
                            "y": {"type": "number", "minimum": 0, "maximum": 1},
                            "w": {"type": "number", "minimum": 0, "maximum": 1},
                            "h": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                        "required": ["x", "y", "w", "h"],
                    },
                    "note": {"type": "string"},
                },
                "required": ["kind", "box", "note"],
            },
        }
    },
    "required": ["regions"],
}


def _walk(directory: Path, suffixes: frozenset[str]) -> list[Path]:
    """Every file with one of these suffixes, with nothing skipped by name.

    This used to skip any name containing ".spectrogram", to keep the generated
    spectrogram PNG out of the records. That is a substring match against a
    filename: front.spectrogram.jpg is a legal name for a photograph of the
    front of a car, and such a file was invisible to init, to apply and to
    check at once - never listed, never stripped, and reported clean. A
    generated image is cheap to sign off once; a name-shaped hole in the gate
    is not cheap at all.
    """
    return sorted(p for p in directory.rglob("*") if p.suffix.lower() in suffixes)


def images(directory: Path) -> list[Path]:
    """The files `apply` can actually open, blur and re-encode."""
    return _walk(directory, redact.STRIPPABLE_SUFFIXES)


def everything(directory: Path) -> list[Path]:
    """Every file in the directory, with no suffix filter at all.

    The one walk here that is not an allowlist, and the only one that can see a
    file nobody predicted. `unaccounted_files` is what reads it.
    """
    return sorted(p for p in directory.rglob("*") if p.is_file())


def documents(directory: Path) -> list[Path]:
    """Buyer paperwork this tool can account for.

    Not stripped and not blurred - a .txt has no metadata container and no
    pixels. It is walked so it can be *reviewed*, because a title history is
    where the seller's name and address actually are, and D-022 is a claim about
    what is safe to commit rather than a claim about EXIF.
    """
    return _walk(directory, redact.DOCUMENT_SUFFIXES)


def reviewable(directory: Path) -> list[Path]:
    """Everything a person has to sign off before it can be committed.

    Images and documents both. `assert_reviewed` used to be handed images only,
    so a document in the directory needed no reviewer, no record and no
    `nothing_to_redact` - it needed nothing, and got nothing.
    """
    return sorted(images(directory) + documents(directory))


def photographs(directory: Path) -> list[Path]:
    """Everything that looks like a camera file, including the formats this tool
    cannot process.

    `check` walks this wider set on purpose. A .heic is a photograph with GPS in
    it whether or not Pillow can open it, and the version of this scan that
    listed only the openable formats reported a directory clean while an
    untouched iPhone original sat in it.
    """
    return _walk(directory, redact.STRIPPABLE_SUFFIXES | redact.UNSTRIPPABLE_SUFFIXES)


def time_based_media(directory: Path) -> list[Path]:
    """Every video and audio file, including the containers no walker here
    understands.

    The wider set on purpose, for the reason `photographs` walks a wider set: a
    .webm carries its tags in an EBML element whether or not anything here can
    read one, and a scan that listed only the readable formats would report a
    directory clean with an untouched recording sitting in it.
    """
    return _walk(
        directory, redact.READABLE_MEDIA_SUFFIXES | redact.UNREADABLE_MEDIA_SUFFIXES
    )


def cmd_init(directory: Path) -> int:
    records = redact.load(directory)
    added = 0
    for path in reviewable(directory):
        key = redact.asset_key(directory, path)
        if key not in records:
            records[key] = redact.AssetRedaction(asset=key)
            added += 1
    out = redact.save(directory, records)
    print(f"  {added} new record(s) -> {out}")
    print("  Fill in regions and reviewed_by by hand, or run 'propose' first.")
    return 0


def cmd_propose(directory: Path) -> int:
    meter = CostMeter(mode="live", model=resolve_model())
    client = ModelClient(
        mode="live",
        cache_dir=directory / ".redact-cache",
        meter=meter,
        model=resolve_model(),
    )
    system = prompts.load("redact", "system")
    locate = prompts.load("redact", "locate")

    records = redact.load(directory)
    for path in images(directory):
        key = redact.asset_key(directory, path)
        try:
            response = client.call(
                engine="redact",
                task="locate",
                # The subject becomes a cache filename, so the key's slashes
                # are flattened - but it must still name one file, not a stem
                # that two files could share.
                subject=key.replace("/", "__"),
                prompt=locate.text,
                system=system.text,
                schema=LOCATE_SCHEMA,
                image_paths=[path],
                prompt_ref=locate.ref,
            )
        except LiveModeUnavailable as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        regions = [
            redact.Region(
                kind=r["kind"], box=BoundingBox(**r["box"]), note=r.get("note", "")
            )
            for r in response.get("regions", [])
        ]
        record = records.setdefault(key, redact.AssetRedaction(asset=key))
        record.regions = regions
        # Deliberately NOT set: reviewed_by. The model does not sign anything.
        record.reviewed_by = ""
        record.nothing_to_redact = False
        print(f"  {path.name}: {len(regions)} proposed region(s)")

    out = redact.save(directory, records)
    print(f"\n  wrote {out}")
    print("  NOTHING IS BLURRED YET. Open that file, check every box against the")
    print("  image, add what the model missed, then put your name in reviewed_by.")
    print(f"  Cost of this pass: ${meter.usd_total:.4f}")
    return 0


def cmd_apply(directory: Path) -> int:
    records = redact.load(directory)
    paths = images(directory)
    # Documents are not blurred and not re-encoded, but they are signed off, so
    # `apply` refuses over an unreviewed one rather than rewriting fourteen
    # photographs beside a title history nobody read.
    unaccounted = redact.unaccounted_files(directory, everything(directory))
    if unaccounted:
        print(
            "error: Media directory holds files this tool has no category for "
            "(D-022):\n  - " + "\n  - ".join(unaccounted),
            file=sys.stderr,
        )
        return 2
    try:
        redact.assert_reviewed(directory, reviewable(directory), records)
        # Both refusals happen before the first re-encode. The format check
        # used to run after the loop, so a directory holding one .heic had
        # every other file irreversibly rewritten and *then* got its error -
        # "refuses rather than reporting success" was really "mutates
        # everything it can, then reports failure".
        redact.assert_formats_strippable(directory, photographs(directory))
    except redact.RedactionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    clips = time_based_media(directory)
    try:
        # Before the first re-encode as well, for the reason above. A directory
        # holding one .webm used to have every photograph in it irreversibly
        # rewritten before anything noticed the file nothing can read.
        redact.assert_media_formats_readable(directory, clips)
    except redact.RedactionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    blurred = 0
    for path in paths:
        record = records[redact.asset_key(directory, path)]
        # Every reviewed image is re-encoded, not just the ones with regions.
        # The re-encode is what strips EXIF, and a photo with nothing to blur
        # still carries the GPS coordinates of wherever it was taken.
        redact.redact_file(path, path, record.regions)
        if record.regions:
            print(
                f"  {path.name}: {len(record.regions)} region(s) blurred, EXIF dropped"
            )
            blurred += 1
        else:
            print(f"  {path.name}: nothing to blur, EXIF dropped")

    for clip in clips:
        # No blurring here, and the tool says so rather than implying it. Nobody
        # has reviewed 210 frames of walkaround footage for plates, and this
        # pass does not pretend to have: it removes the container metadata and
        # the encoder's signature from the coded stream, which is the half that
        # can be done without a person.
        try:
            redact.strip_time_based_media(clip, clip)
        except redact.RedactionError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"  {clip.name}: remuxed, container metadata and encoder SEI dropped")

    # Those per-file lines each claim something was dropped. Check the claim
    # instead of printing it: a re-encode that quietly carried metadata through,
    # a remux that left the compressorname ffmpeg writes into its own output, or
    # a file this tool never had a way to touch, would otherwise be reported as
    # done.
    try:
        redact.assert_metadata_stripped(directory, photographs(directory))
        redact.assert_time_based_metadata_stripped(directory, clips)
    except redact.RedactionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        f"\n  {len(paths)} image(s) re-encoded in place, {blurred} with regions "
        f"blurred, {len(clips)} clip(s) remuxed. This is not reversible."
    )
    return 0


def cmd_check(directory: Path) -> int:
    problems: list[str] = []
    try:
        redact.assert_reviewed(directory, reviewable(directory), redact.load(directory))
    except redact.RedactionError as exc:
        problems.append(str(exc))

    # Every walk in this tool is an allowlist of suffixes, so anything outside
    # all of them used to be invisible - and `history_01.txt`, a title history,
    # sat in this repository's own committed media directory being reported as
    # part of a green run that had never opened it.
    unaccounted = redact.unaccounted_files(directory, everything(directory))
    if unaccounted:
        problems.append(
            "Media directory holds files this tool has no category for (D-022):\n  - "
            + "\n  - ".join(unaccounted)
        )

    # A signature says a person looked at the pixels. It says nothing about the
    # bytes around them, and that is where the GPS position lives - so a
    # directory of honest "nothing to redact" records used to pass this command
    # with the seller's driveway in every file.
    try:
        redact.assert_metadata_stripped(directory, photographs(directory))
    except redact.RedactionError as exc:
        problems.append(str(exc))

    # This used to be a printed apology. `check` walked past every .mp4 and
    # .wav and named them as unexamined, which was honest and left the clip in
    # this repository's own fixtures carrying a position atom, an encoder
    # banner and x264's entire command line for nine phases. A declared gap is
    # better than a hidden one and it is not a check.
    clips = time_based_media(directory)
    try:
        redact.assert_time_based_metadata_stripped(directory, clips)
    except redact.RedactionError as exc:
        problems.append(str(exc))

    if problems:
        # Every question, every run. Stopping at the first failure hides the
        # rest until it is fixed, and the reviewer who has just been told about
        # an unsigned file re-runs expecting green.
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1

    checked = photographs(directory)
    print(
        f"  {len(checked)} still image(s) in {directory}: reviewed, signed off, "
        f"no metadata container"
    )
    print(
        f"  {len(clips)} clip(s): every box and chunk walked, no tag atom, no "
        f"encoder banner, no user-data SEI"
    )
    # Counted and named separately from the images, because "reviewed" means
    # something different for a document: nobody blurred anything, a person read
    # it and said it carries no name, address or full VIN. Folding it into the
    # image count would let the stronger claim cover the weaker one.
    print(
        f"  {len(documents(directory))} document(s): signed off by a reader. "
        f"Nothing here strips a document - plain text has no container to strip."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] not in ("init", "propose", "apply", "check"):
        print(__doc__)
        return 2

    command, raw = args
    directory = Path(raw)
    if not directory.is_absolute():
        directory = REPO_ROOT / directory
    if not directory.is_dir():
        print(f"error: no directory at {directory}", file=sys.stderr)
        return 2

    return {
        "init": cmd_init,
        "propose": cmd_propose,
        "apply": cmd_apply,
        "check": cmd_check,
    }[command](directory)


if __name__ == "__main__":
    raise SystemExit(main())
