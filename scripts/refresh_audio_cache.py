"""Measure fixture audio and cache the result. Needs ffmpeg.

Audio analysis is deterministic arithmetic with no API call and no cost, so
caching it looks redundant. It is not: LAW 7 says a fixture run needs nothing,
and computing the spectrogram at report time would make the gate that proves
that dependency-free itself depend on ffmpeg being installed. So this script
runs by hand, writes the features and the rendered spectrogram, and both get
committed - the same shape as the federal record cache (D-026).

    python scripts/refresh_audio_cache.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "packages" / "engines" / "src"))

from tirekick_engines import signal  # noqa: E402
from tirekick_engines.engines import audio as audio_engine  # noqa: E402
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
        if item.kind != "audio":
            continue
        path = media / item.file
        if not path.is_file():
            print(f"  missing {path}")
            continue

        samples = signal.decode(path)
        measured = signal.features(samples)
        spec = signal.spectrogram(samples)

        out = audio_engine.cache_path(cache, item.id)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(measured)
        payload["_note"] = (
            "Measured from the committed audio by scripts/refresh_audio_cache.py. "
            "Deterministic arithmetic over the waveform - no model, no claims."
        )
        out.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        image = media / audio_engine.spectrogram_name(item.id)
        signal.write_spectrogram(spec, image)

        print(f"  {item.id}: {measured.duration_sec:.1f}s, ", end="")
        print(f"dominant {measured.dominant_hz}Hz, ", end="")
        print(f"{len(measured.transients)} transient(s)")
        print(f"    -> {out.relative_to(REPO_ROOT)}")
        print(f"    -> {image.relative_to(REPO_ROOT)}")
        written += 1

    return written


def main() -> int:
    if not signal.ffmpeg_available():
        print("error: ffmpeg is not installed", file=sys.stderr)
        return 2

    total = 0
    for manifest in sorted(FIXTURES.glob("*/manifest.json")):
        print(f"\n{manifest.parent.name}")
        total += refresh(manifest.parent)

    print(f"\nrefreshed {total} audio asset(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
