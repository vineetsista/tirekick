"""Redaction, and the gate that refuses media nobody has checked.

Most of this file is about `assert_reviewed`. The blurring itself is a few lines
of Pillow; the part that can actually hurt somebody is the bookkeeping that
decides an image is safe to publish.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from tirekick_engines import redact
from tirekick_engines.models import BoundingBox


def _plate_image(path: Path) -> Path:
    """An image with a high-contrast block standing in for a plate."""
    array = np.full((200, 400, 3), 40, dtype=np.uint8)
    # Sharp black-and-white stripes: readable, and obvious when destroyed.
    array[140:180, 120:280] = 255
    array[150:170, 130:270:8] = 0
    Image.fromarray(array).save(path)
    return path


def _region() -> redact.Region:
    return redact.Region(
        kind="plate",
        box=BoundingBox(x=120 / 400, y=140 / 200, w=160 / 400, h=40 / 200),
        note="rear plate",
    )


# --------------------------------------------------------------------------- #
# the gate                                                                     #
# --------------------------------------------------------------------------- #


def test_an_image_with_no_record_is_refused(tmp_path: Path) -> None:
    """Absence is not consent. The commonest way an unblurred plate ships is a
    file nobody remembered to list."""
    path = _plate_image(tmp_path / "photo_01.jpg")
    with pytest.raises(redact.RedactionError, match="no redaction record"):
        redact.assert_reviewed([path], {})


def test_a_record_with_no_reviewer_is_refused(tmp_path: Path) -> None:
    path = _plate_image(tmp_path / "photo_01.jpg")
    records = {"photo_01": redact.AssetRedaction(asset="photo_01", regions=[_region()])}
    with pytest.raises(redact.RedactionError, match="no reviewer name"):
        redact.assert_reviewed([path], records)


def test_a_reviewer_who_decided_nothing_is_refused(tmp_path: Path) -> None:
    """Signed, but neither regions nor an explicit 'nothing to redact'.

    That is a half-finished review, and it reads as approval unless something
    refuses it.
    """
    path = _plate_image(tmp_path / "photo_01.jpg")
    records = {"photo_01": redact.AssetRedaction(asset="photo_01", reviewed_by="vineet")}
    with pytest.raises(redact.RedactionError, match="Which is it"):
        redact.assert_reviewed([path], records)


def test_an_explicit_nothing_to_redact_passes(tmp_path: Path) -> None:
    """A legitimate answer, and it has to be stated by a person."""
    path = _plate_image(tmp_path / "photo_01.jpg")
    records = {
        "photo_01": redact.AssetRedaction(
            asset="photo_01", reviewed_by="vineet", nothing_to_redact=True
        )
    }
    redact.assert_reviewed([path], records)


def test_a_signed_record_with_regions_passes(tmp_path: Path) -> None:
    path = _plate_image(tmp_path / "photo_01.jpg")
    records = {
        "photo_01": redact.AssetRedaction(
            asset="photo_01", reviewed_by="vineet", regions=[_region()]
        )
    }
    redact.assert_reviewed([path], records)


def test_one_unreviewed_image_fails_the_whole_directory(tmp_path: Path) -> None:
    first = _plate_image(tmp_path / "photo_01.jpg")
    second = _plate_image(tmp_path / "photo_02.jpg")
    records = {
        "photo_01": redact.AssetRedaction(
            asset="photo_01", reviewed_by="vineet", nothing_to_redact=True
        )
    }
    with pytest.raises(redact.RedactionError, match="photo_02"):
        redact.assert_reviewed([first, second], records)


# --------------------------------------------------------------------------- #
# the blur                                                                     #
# --------------------------------------------------------------------------- #


def test_the_region_is_actually_destroyed(tmp_path: Path) -> None:
    """Not softened - destroyed.

    A lightly blurred plate is still readable by anything built to read plates.
    The check is that the high-frequency detail inside the region is gone.
    """
    source = _plate_image(tmp_path / "photo_01.jpg")
    out = tmp_path / "redacted.jpg"
    redact.redact_file(source, out, [_region()])

    def detail(path: Path) -> float:
        with Image.open(path) as image:
            patch = np.asarray(image.convert("L")).astype(np.float32)[140:180, 120:280]
        return float(np.abs(np.diff(patch, axis=1)).mean())

    assert detail(out) < detail(source) / 8


def test_pixels_outside_the_region_are_left_alone(tmp_path: Path) -> None:
    source = _plate_image(tmp_path / "photo_01.jpg")
    out = tmp_path / "redacted.jpg"
    redact.redact_file(source, out, [_region()])

    with Image.open(source) as a, Image.open(out) as b:
        before = np.asarray(a.convert("RGB")).astype(np.int16)
        after = np.asarray(b.convert("RGB")).astype(np.int16)
    # Top strip, well clear of the padded region.
    assert np.abs(before[:100] - after[:100]).mean() < 3.0


def test_the_padding_reaches_past_the_box(tmp_path: Path) -> None:
    """A snug box clips a character, and a partly visible plate is a plate."""
    source = _plate_image(tmp_path / "photo_01.jpg")
    out = tmp_path / "redacted.jpg"
    redact.redact_file(source, out, [_region()])

    with Image.open(source) as a, Image.open(out) as b:
        before = np.asarray(a.convert("L")).astype(np.int16)
        after = np.asarray(b.convert("L")).astype(np.int16)
    # A row just above the declared box top should still have been touched.
    assert np.abs(before[137:140, 120:280] - after[137:140, 120:280]).mean() > 0


def test_redaction_survives_a_round_trip_through_the_record(tmp_path: Path) -> None:
    records = {
        "photo_01": redact.AssetRedaction(
            asset="photo_01",
            reviewed_by="vineet",
            reviewed_at="2026-07-27T00:00:00Z",
            regions=[_region()],
        )
    }
    redact.save(tmp_path, records)
    loaded = redact.load(tmp_path)

    assert loaded["photo_01"].reviewed_by == "vineet"
    assert loaded["photo_01"].regions[0].kind == "plate"
    assert loaded["photo_01"].regions[0].box.w == pytest.approx(160 / 400)
    assert loaded["photo_01"].reviewed


def test_an_empty_directory_loads_as_no_records(tmp_path: Path) -> None:
    assert redact.load(tmp_path) == {}
