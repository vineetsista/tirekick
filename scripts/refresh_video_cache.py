"""Select walkaround frames and commit them. Needs ffmpeg.

Same reasoning as the audio cache (D-026): the selection is deterministic, free
arithmetic, and it still gets cached because fixture mode must need nothing. A
report that had to decode video at render time would make the gate proving
dependency-freedom itself depend on ffmpeg.

    python scripts/refresh_video_cache.py

Prints what it kept and what it threw away. The discards are the interesting
half - a selector that silently drops 90% of a video is indistinguishable from
one that analysed all of it, right up until someone asks why a scratch was missed.

Every frame this script commits goes through the same re-encode `redact apply`
performs, because ffmpeg stamps its encoder banner ("Lavc60.31.102") into a JPEG
COM segment on every frame it writes. Harmless content, but a COM segment is a
free-form text container that survives every copy, it is not what README.md
means when it says the committed images carry no metadata, and D-022 does not
have an exception for containers whose current contents happen to be dull.
`packages/engines/tests/test_redact_check.py` runs `redact check` over the
committed fixture media, so a frame that regains one fails a test.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "packages" / "engines" / "src"))

from tirekick_engines import redact, video  # noqa: E402
from tirekick_engines.engines import walkaround  # noqa: E402
from tirekick_engines.inputs import InspectionInput  # noqa: E402

FIXTURES = REPO_ROOT / "fixtures"


def refresh(inspection_dir: Path) -> int:
    manifest = inspection_dir / "manifest.json"
    if not manifest.is_file():
        return 0

    inspection = InspectionInput.load(manifest)
    media = inspection_dir / "media"
    cache = inspection_dir / "cached"
    written = 0

    for item in inspection.assets:
        if item.kind != "video":
            continue
        path = media / item.file
        if not path.is_file():
            print(f"  missing {path}")
            continue

        duration = video.probe_duration(path)
        work = media / "_frames"
        raw = video.extract_frames(path, work)
        selection = video.select_frames(raw, duration_sec=duration)

        # Clear previously committed frames for this clip, so a re-run does not
        # leave orphans that the report would never cite.
        for stale in media.glob(f"{item.id}.frame_*.jpg"):
            stale.unlink()

        names: list[str] = []
        for index, candidate in enumerate(selection.kept, start=1):
            name = walkaround.frame_name(item.id, index)
            frame = media / name
            raw[candidate.index].replace(frame)
            # Strip before commit, not after somebody notices. Selection ran on
            # the file ffmpeg wrote, so re-encoding here cannot move a frame in
            # or out of the selection - it only removes the containers around
            # the pixels that were already chosen.
            redact.redact_file(frame, frame, [])
            leftover = redact.remaining_metadata(frame)
            if leftover:
                # A raise, not an assert: `python -O` deletes an assert and
                # this line is the only thing standing between a stray
                # container and a commit.
                raise RuntimeError(f"{name} still carries {', '.join(leftover)}")
            names.append(name)

        for leftover in work.glob("raw_*.jpg"):
            leftover.unlink()
        if work.is_dir():
            work.rmdir()

        payload = walkaround.build_selection_payload(item.id, selection, names)
        out = walkaround.cache_path(cache, item.id)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        print(f"  {item.id}: {duration:.1f}s, {selection.sampled} sampled")
        print(f"    kept      {len(selection.kept)}")
        print(f"    blurred   {selection.dropped_blurred}")
        print(f"    duplicate {selection.dropped_duplicate}")
        print(f"    over cap  {selection.dropped_over_cap}")
        print(f"    -> {out.relative_to(REPO_ROOT)}")
        written += 1

    return written


def main() -> int:
    if not video.ffmpeg_available():
        print("error: ffmpeg/ffprobe are not installed", file=sys.stderr)
        return 2

    total = 0
    for manifest in sorted(FIXTURES.glob("*/manifest.json")):
        print(f"\n{manifest.parent.name}")
        total += refresh(manifest.parent)

    print(f"\nrefreshed {total} video asset(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
