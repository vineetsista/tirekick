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
        redact.assert_reviewed(tmp_path, [path], {})


def test_a_record_with_no_reviewer_is_refused(tmp_path: Path) -> None:
    path = _plate_image(tmp_path / "photo_01.jpg")
    records = {"photo_01.jpg": redact.AssetRedaction(asset="photo_01.jpg", regions=[_region()])}
    with pytest.raises(redact.RedactionError, match="no reviewer name"):
        redact.assert_reviewed(tmp_path, [path], records)


def test_a_reviewer_who_decided_nothing_is_refused(tmp_path: Path) -> None:
    """Signed, but neither regions nor an explicit 'nothing to redact'.

    That is a half-finished review, and it reads as approval unless something
    refuses it.
    """
    path = _plate_image(tmp_path / "photo_01.jpg")
    records = {
        "photo_01.jpg": redact.AssetRedaction(asset="photo_01.jpg", reviewed_by="vineet")
    }
    with pytest.raises(redact.RedactionError, match="Which is it"):
        redact.assert_reviewed(tmp_path, [path], records)


def test_an_explicit_nothing_to_redact_passes(tmp_path: Path) -> None:
    """A legitimate answer, and it has to be stated by a person."""
    path = _plate_image(tmp_path / "photo_01.jpg")
    records = {
        "photo_01.jpg": redact.AssetRedaction(
            asset="photo_01.jpg", reviewed_by="vineet", nothing_to_redact=True
        )
    }
    redact.assert_reviewed(tmp_path, [path], records)


def test_a_signed_record_with_regions_passes(tmp_path: Path) -> None:
    path = _plate_image(tmp_path / "photo_01.jpg")
    records = {
        "photo_01.jpg": redact.AssetRedaction(
            asset="photo_01.jpg", reviewed_by="vineet", regions=[_region()]
        )
    }
    redact.assert_reviewed(tmp_path, [path], records)


def test_one_unreviewed_image_fails_the_whole_directory(tmp_path: Path) -> None:
    first = _plate_image(tmp_path / "photo_01.jpg")
    second = _plate_image(tmp_path / "photo_02.jpg")
    records = {
        "photo_01.jpg": redact.AssetRedaction(
            asset="photo_01.jpg", reviewed_by="vineet", nothing_to_redact=True
        )
    }
    with pytest.raises(redact.RedactionError, match="photo_02"):
        redact.assert_reviewed(tmp_path, [first, second], records)


def test_a_bare_stem_record_vouches_for_nothing(tmp_path: Path) -> None:
    """Records are keyed by the full relative filename, extension included.

    A record keyed 'photo_01' used to vouch for photo_01.jpg and photo_01.png
    at once - one review silently covering a file nobody looked at. A bare-stem
    key must now match nothing.
    """
    jpg = _plate_image(tmp_path / "photo_01.jpg")
    png = _plate_image(tmp_path / "photo_01.png")
    records = {
        "photo_01": redact.AssetRedaction(
            asset="photo_01", reviewed_by="vineet", nothing_to_redact=True
        )
    }
    with pytest.raises(redact.RedactionError, match="no redaction record"):
        redact.assert_reviewed(tmp_path, [jpg, png], records)


def test_the_same_filename_in_two_folders_needs_two_records(tmp_path: Path) -> None:
    """Cameras name everything IMG_0001.jpg, so two capture sessions collide on
    filename alone. The key carries the subdirectory, and a review of one
    session's file says nothing about the other's."""
    (tmp_path / "session-a").mkdir()
    (tmp_path / "session-b").mkdir()
    first = _plate_image(tmp_path / "session-a" / "IMG_0001.jpg")
    second = _plate_image(tmp_path / "session-b" / "IMG_0001.jpg")
    records = {
        "session-a/IMG_0001.jpg": redact.AssetRedaction(
            asset="session-a/IMG_0001.jpg", reviewed_by="vineet", nothing_to_redact=True
        )
    }
    with pytest.raises(redact.RedactionError, match="session-b/IMG_0001.jpg"):
        redact.assert_reviewed(tmp_path, [first, second], records)


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


def test_boxes_land_where_the_reviewer_drew_them_on_a_rotated_photo(
    tmp_path: Path,
) -> None:
    """Phone photos are stored sideways with an EXIF orientation tag, and every
    viewer silently honours it. The reviewer draws their box on the image as
    displayed, so the blur has to land in that frame - a box applied to the raw
    sensor grid blurs a strip of nothing and ships the plate readable.
    """
    source = _plate_image(tmp_path / "photo_01.jpg")
    # Re-save the plate image tagged Orientation=6: raw 400x200 landscape that
    # every viewer rotates 90 degrees clockwise into a 200x400 portrait.
    with Image.open(source) as raw:
        exif = Image.Exif()
        exif[0x0112] = 6
        raw.save(source, exif=exif)

    # The plate block sits at raw rows 140:180, cols 120:280. Rotated 90
    # degrees clockwise it displays at rows 120:280, cols 20:60 of the 200x400
    # portrait - and that is the frame the reviewer's box is drawn in.
    region = redact.Region(
        kind="plate",
        box=BoundingBox(x=20 / 200, y=120 / 400, w=40 / 200, h=160 / 400),
        note="rear plate, as displayed",
    )
    out = tmp_path / "redacted.jpg"
    redact.redact_file(source, out, [region])

    def stripe_detail(array: np.ndarray) -> float:
        patch = array.astype(np.float32)[120:280, 20:60]
        # The stripes run horizontally after rotation, so the detail that must
        # die is the variation from row to row.
        return float(np.abs(np.diff(patch, axis=0)).mean())

    from PIL import ImageOps

    with Image.open(source) as image:
        displayed = np.asarray(ImageOps.exif_transpose(image).convert("L"))
    with Image.open(out) as image:
        # The output has no orientation tag left, so its pixels must already
        # be the displayed frame: portrait, not raw landscape.
        assert image.size == (200, 400)
        after = np.asarray(image.convert("L"))

    assert stripe_detail(after) < stripe_detail(displayed) / 8


def test_redaction_survives_a_round_trip_through_the_record(tmp_path: Path) -> None:
    records = {
        "photo_01.jpg": redact.AssetRedaction(
            asset="photo_01.jpg",
            reviewed_by="vineet",
            reviewed_at="2026-07-27T00:00:00Z",
            regions=[_region()],
        )
    }
    redact.save(tmp_path, records)
    loaded = redact.load(tmp_path)

    assert loaded["photo_01.jpg"].reviewed_by == "vineet"
    assert loaded["photo_01.jpg"].regions[0].kind == "plate"
    assert loaded["photo_01.jpg"].regions[0].box.w == pytest.approx(160 / 400)
    assert loaded["photo_01.jpg"].reviewed


def test_an_empty_directory_loads_as_no_records(tmp_path: Path) -> None:
    assert redact.load(tmp_path) == {}


def test_the_written_note_tells_the_reader_what_a_key_has_to_be(
    tmp_path: Path,
) -> None:
    """The record is edited by hand, so the file has to say how to edit it.

    A bare stem silently vouched for nothing once the key gained its extension,
    and the only place a person finds that out is the note at the top of the
    file they are typing into. The note is a claim about behaviour, so it is
    checked against the behaviour rather than trusted.
    """
    import json

    path = redact.save(
        tmp_path,
        {
            "photo_01.jpg": redact.AssetRedaction(
                asset="photo_01.jpg", reviewed_by="vineet", nothing_to_redact=True
            )
        },
    )
    note = json.loads(path.read_text(encoding="utf-8"))["_note"]

    assert "photo_01.jpg" in note and "photo_01'" in note
    # The note is only true if a stem really does vouch for nothing.
    image = _plate_image(tmp_path / "photo_01.jpg")
    stem_only = {
        "photo_01": redact.AssetRedaction(
            asset="photo_01", reviewed_by="vineet", nothing_to_redact=True
        )
    }
    with pytest.raises(redact.RedactionError, match="no redaction record"):
        redact.assert_reviewed(tmp_path, [image], stem_only)


def test_the_note_is_not_loaded_as_an_asset(tmp_path: Path) -> None:
    """It sits beside `assets`, not inside it. A note that loaded as a record
    would be a signature against a file that does not exist."""
    redact.save(
        tmp_path,
        {
            "photo_01.jpg": redact.AssetRedaction(
                asset="photo_01.jpg", reviewed_by="vineet", nothing_to_redact=True
            )
        },
    )
    assert list(redact.load(tmp_path)) == ["photo_01.jpg"]
