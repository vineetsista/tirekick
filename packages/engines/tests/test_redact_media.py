"""The redaction script's apply step, and the EXIF it exists to destroy.

`apply` re-encodes every reviewed image, not just the ones with regions to
blur. The re-encode is the only thing that strips EXIF, and EXIF is where the
GPS coordinates of somebody's driveway live. An interior shot with nothing to
blur is still a photograph of where the seller keeps their car.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest
from PIL import ExifTags, Image

from tirekick_engines import redact
from tirekick_engines.models import BoundingBox

REPO_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "redact_media", REPO_ROOT / "scripts" / "redact_media.py"
)
assert _spec is not None and _spec.loader is not None
redact_media = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(redact_media)


def _gps_exif() -> Image.Exif:
    """The tag this whole module exists to destroy: a real GPS position."""
    exif = Image.Exif()
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps[ExifTags.GPS.GPSLatitudeRef] = "N"
    gps[ExifTags.GPS.GPSLatitude] = (37.0, 25.0, 30.0)
    gps[ExifTags.GPS.GPSLongitudeRef] = "W"
    gps[ExifTags.GPS.GPSLongitude] = (122.0, 5.0, 6.0)
    return exif


def _image_with_gps(path: Path) -> Path:
    array = np.full((200, 400, 3), 40, dtype=np.uint8)
    # tobytes(), because Pillow's PNG writer serialises a GPS sub-IFD correctly
    # only when handed the raw EXIF blob.
    Image.fromarray(array).save(path, exif=_gps_exif().tobytes())
    # A test that "removes" GPS which was never written proves nothing.
    with Image.open(path) as image:
        assert dict(image.getexif().get_ifd(ExifTags.IFD.GPSInfo))
    return path


def _gps_tags(path: Path) -> dict:
    with Image.open(path) as image:
        return dict(image.getexif().get_ifd(ExifTags.IFD.GPSInfo))


def test_apply_strips_gps_from_an_image_with_nothing_to_redact(tmp_path: Path) -> None:
    """The dangerous case is the clean one.

    Most of the standard capture views - interior, engine bay, odometer - have
    no plate and no face, so the reviewer correctly writes nothing_to_redact.
    If apply then leaves the file untouched, its EXIF GPS ships to a public
    repository with a reviewer's name vouching for it.
    """
    path = _image_with_gps(tmp_path / "engine_bay.jpg")
    records = {
        "engine_bay.jpg": redact.AssetRedaction(
            asset="engine_bay.jpg", reviewed_by="vineet", nothing_to_redact=True
        )
    }
    redact.save(tmp_path, records)

    assert redact_media.cmd_apply(tmp_path) == 0
    assert not _gps_tags(path)
    with Image.open(path) as image:
        assert image.format == "JPEG"


def test_apply_strips_gps_from_a_png_and_keeps_it_a_png(tmp_path: Path) -> None:
    """PNGs can carry EXIF too, and a re-encode must not silently turn a .png
    file into JPEG bytes wearing the wrong extension."""
    path = _image_with_gps(tmp_path / "odometer.png")
    records = {
        "odometer.png": redact.AssetRedaction(
            asset="odometer.png", reviewed_by="vineet", nothing_to_redact=True
        )
    }
    redact.save(tmp_path, records)

    assert redact_media.cmd_apply(tmp_path) == 0
    assert not _gps_tags(path)
    with Image.open(path) as image:
        assert image.format == "PNG"


def test_apply_strips_gps_from_a_blurred_image_too(tmp_path: Path) -> None:
    """The region-bearing path already re-encoded; keep it honest as well."""
    path = _image_with_gps(tmp_path / "rear_plate.jpg")
    records = {
        "rear_plate.jpg": redact.AssetRedaction(
            asset="rear_plate.jpg",
            reviewed_by="vineet",
            regions=[
                redact.Region(
                    kind="plate",
                    box=BoundingBox(x=0.3, y=0.7, w=0.4, h=0.2),
                    note="rear plate",
                )
            ],
        )
    }
    redact.save(tmp_path, records)

    assert redact_media.cmd_apply(tmp_path) == 0
    assert not _gps_tags(path)


def test_apply_still_refuses_an_unreviewed_directory(tmp_path: Path) -> None:
    """Re-encoding everything must not soften the gate: no review, no apply."""
    _image_with_gps(tmp_path / "engine_bay.jpg")

    assert redact_media.cmd_apply(tmp_path) == 2
    # And the file is untouched - GPS intact is correct here, because apply
    # refused to run rather than half-running.
    assert _gps_tags(tmp_path / "engine_bay.jpg")


def test_init_keys_records_by_relative_filename(tmp_path: Path) -> None:
    """Two files, two records - even when stems collide across folders.

    Keyed by bare stem, session-a/IMG_0001.jpg and session-b/IMG_0001.jpg
    collapsed into one record, and one signature vouched for a file nobody
    looked at.
    """
    (tmp_path / "session-a").mkdir()
    (tmp_path / "session-b").mkdir()
    for folder in ("session-a", "session-b"):
        array = np.full((50, 50, 3), 40, dtype=np.uint8)
        Image.fromarray(array).save(tmp_path / folder / "IMG_0001.jpg")

    assert redact_media.cmd_init(tmp_path) == 0
    records = redact.load(tmp_path)
    assert set(records) == {"session-a/IMG_0001.jpg", "session-b/IMG_0001.jpg"}

    # Signing only one of them must not clear the directory.
    records["session-a/IMG_0001.jpg"].reviewed_by = "vineet"
    records["session-a/IMG_0001.jpg"].nothing_to_redact = True
    redact.save(tmp_path, records)
    with pytest.raises(redact.RedactionError, match="session-b/IMG_0001.jpg"):
        redact.assert_reviewed(tmp_path, redact_media.images(tmp_path), records)
