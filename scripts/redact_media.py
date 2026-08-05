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


def photographs(directory: Path) -> list[Path]:
    """Everything that looks like a camera file, including the formats this tool
    cannot process.

    `check` walks this wider set on purpose. A .heic is a photograph with GPS in
    it whether or not Pillow can open it, and the version of this scan that
    listed only the openable formats reported a directory clean while an
    untouched iPhone original sat in it.
    """
    return _walk(directory, redact.STRIPPABLE_SUFFIXES | redact.UNSTRIPPABLE_SUFFIXES)


def cmd_init(directory: Path) -> int:
    records = redact.load(directory)
    added = 0
    for path in images(directory):
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
    try:
        redact.assert_reviewed(directory, paths, records)
        # Both refusals happen before the first re-encode. The format check
        # used to run after the loop, so a directory holding one .heic had
        # every other file irreversibly rewritten and *then* got its error -
        # "refuses rather than reporting success" was really "mutates
        # everything it can, then reports failure".
        redact.assert_formats_strippable(directory, photographs(directory))
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

    # Those per-file lines each claim "EXIF dropped". Check the claim instead of
    # printing it: a re-encode that quietly carried metadata through, or a file
    # this tool never had a way to touch, would otherwise be reported as done.
    try:
        redact.assert_metadata_stripped(directory, photographs(directory))
    except redact.RedactionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        f"\n  {len(paths)} image(s) re-encoded in place, {blurred} with regions "
        f"blurred. This is not reversible."
    )
    return 0


def cmd_check(directory: Path) -> int:
    problems: list[str] = []
    try:
        redact.assert_reviewed(directory, images(directory), redact.load(directory))
    except redact.RedactionError as exc:
        problems.append(str(exc))

    # A signature says a person looked at the pixels. It says nothing about the
    # bytes around them, and that is where the GPS position lives - so a
    # directory of honest "nothing to redact" records used to pass this command
    # with the seller's driveway in every file.
    try:
        redact.assert_metadata_stripped(directory, photographs(directory))
    except redact.RedactionError as exc:
        problems.append(str(exc))

    if problems:
        # Both questions, every run. Stopping at the first failure hides the
        # second until the first is fixed, and the reviewer who has just been
        # told about an unsigned file re-runs expecting green.
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1

    checked = photographs(directory)
    print(
        f"  {len(checked)} still image(s) in {directory}: reviewed, signed off, "
        f"no metadata container"
    )
    _report_what_was_not_examined(directory)
    return 0


def _report_what_was_not_examined(directory: Path) -> None:
    """Say which files green does not cover.

    `check` reads still images. An .mp4 carries a position in its (c)xyz atom
    and a .wav can carry a LIST/INFO block, and nothing here opens either - so
    a success line that said "every image ... has been reviewed, signed off and
    stripped" left the reader to infer the limit from the word "image". Naming
    the unread files is the difference between a declared gap and a hidden one.
    """
    unexamined = _walk(directory, redact.UNEXAMINED_MEDIA_SUFFIXES)
    if not unexamined:
        return
    names = ", ".join(redact.asset_key(directory, p) for p in unexamined)
    print(
        f"  not examined: {names}. This tool reads still images only, and an "
        f".mp4 can carry GPS in its (c)xyz atom. Nothing here has checked them."
    )


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
