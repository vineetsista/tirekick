"""Blur number plates and faces before media is committed. D-022.

Three modes, and the order matters.

    python scripts/redact_media.py init    <dir>   scaffold a record per image
    python scripts/redact_media.py propose <dir>   ask the model for regions (needs a key)
    python scripts/redact_media.py apply   <dir>   blur, in place, irreversibly
    python scripts/redact_media.py check   <dir>   fail if anything is unreviewed

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

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}

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


def images(directory: Path) -> list[Path]:
    return sorted(
        p
        for p in directory.rglob("*")
        if p.suffix.lower() in IMAGE_SUFFIXES and ".spectrogram" not in p.name
    )


def cmd_init(directory: Path) -> int:
    records = redact.load(directory)
    added = 0
    for path in images(directory):
        if path.stem not in records:
            records[path.stem] = redact.AssetRedaction(asset=path.stem)
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
        try:
            response = client.call(
                engine="redact",
                task="locate",
                subject=path.stem,
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
        record = records.setdefault(path.stem, redact.AssetRedaction(asset=path.stem))
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
        redact.assert_reviewed(paths, records)
    except redact.RedactionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    blurred = 0
    for path in paths:
        record = records[path.stem]
        if not record.regions:
            continue
        redact.redact_file(path, path, record.regions)
        print(f"  {path.name}: {len(record.regions)} region(s) blurred, EXIF dropped")
        blurred += 1

    print(f"\n  {blurred} image(s) modified in place. This is not reversible.")
    return 0


def cmd_check(directory: Path) -> int:
    try:
        redact.assert_reviewed(images(directory), redact.load(directory))
    except redact.RedactionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"  every image in {directory} has been reviewed and signed off")
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
