"""`check` has to read the bytes, not just the paperwork.

`assert_reviewed` asks whether a person looked at the pixels. That is a real
question and it is not this one. A reviewer can honestly sign "nothing to
redact" for an engine-bay shot, run `check`, watch it go green, and commit a
file that still names the driveway it was taken in - because until now nothing
between `init` and the commit ever opened the file.

So `check` now asks the second question too: does this image still carry a
metadata container at all. Containers, not coordinates - the reasoning is in
redact.py's docstring, and the short version is that Pillow can see a container
reliably and cannot see every place a coordinate hides inside one.
"""

from __future__ import annotations

import importlib.util
import struct
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import ExifTags, Image, PngImagePlugin

from tirekick_engines import redact
from tirekick_engines.models import BoundingBox

REPO_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "redact_media_check", REPO_ROOT / "scripts" / "redact_media.py"
)
assert _spec is not None and _spec.loader is not None
redact_media = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(redact_media)

#: A real XMP packet with a position in it. Phones and editing apps write the
#: coordinates here as well as into the EXIF GPS IFD, and Pillow's getxmp()
#: returns {} with a warning unless defusedxml happens to be installed - so a
#: check that went looking for the coordinates would find nothing and pass.
XMP_WITH_GPS = (
    b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
    b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    b'<rdf:Description xmlns:exif="http://ns.adobe.com/exif/1.0/" '
    b'exif:GPSLatitude="37,25.5000N" exif:GPSLongitude="122,5.1000W"/>'
    b'</rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
)


#: The first bytes of an MP4, with a (c)xyz atom holding a position. Samsung's
#: Motion Photo and Google's MicroVideo append exactly this kind of payload -
#: a whole video file - after the still's end marker, and it is what a large
#: share of phone photographs look like on disk.
MP4_WITH_GPS = b"\x00\x00\x00\x18ftypmp42\xa9xyz+37.4250-122.0850/"


def _iptc_app13(*datasets: bytes) -> bytes:
    """A JPEG APP13 segment carrying an IPTC IIM block.

    Hand-built because Pillow can read a Photoshop resource block and cannot
    write one, and an untested claim about IPTC is the defect class this
    repository keeps finding in itself.
    """
    resource = (
        b"8BIM"
        + struct.pack(">H", 0x0404)  # IPTC-NAA record
        + b"\x00\x00"  # empty Pascal name, padded to even
        + struct.pack(">I", len(b"".join(datasets)))
        + b"".join(datasets)
    )
    payload = b"Photoshop 3.0\x00" + resource
    return b"\xff\xed" + struct.pack(">H", len(payload) + 2) + payload


def _iptc_dataset(record: int, dataset: int, value: bytes) -> bytes:
    return b"\x1c" + bytes([record, dataset]) + struct.pack(">H", len(value)) + value


def _gps_exif(orientation: int | None = None) -> Image.Exif:
    exif = Image.Exif()
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps[ExifTags.GPS.GPSLatitudeRef] = "N"
    gps[ExifTags.GPS.GPSLatitude] = (37.0, 25.0, 30.0)
    gps[ExifTags.GPS.GPSLongitudeRef] = "W"
    gps[ExifTags.GPS.GPSLongitude] = (122.0, 5.0, 6.0)
    if orientation is not None:
        exif[0x0112] = orientation
    return exif


def _flat(width: int = 400, height: int = 200) -> Image.Image:
    return Image.fromarray(np.full((height, width, 3), 40, dtype=np.uint8))


def _plate_array() -> np.ndarray:
    """400x200 with a high-contrast striped block standing in for a plate."""
    array = np.full((200, 400, 3), 40, dtype=np.uint8)
    array[140:180, 120:280] = 255
    array[150:170, 130:270:8] = 0
    return array


def _clean(path: Path) -> Path:
    """What `apply` is supposed to leave behind: pixels and nothing else."""
    _flat().save(path)
    assert not redact.remaining_metadata(path)
    return path


def _with_gps(path: Path, orientation: int | None = None) -> Path:
    # tobytes(), because Pillow's PNG writer only serialises a GPS sub-IFD
    # correctly when it is handed the raw blob.
    _flat().save(path, exif=_gps_exif(orientation).tobytes())
    with Image.open(path) as image:
        assert dict(image.getexif().get_ifd(ExifTags.IFD.GPSInfo)), "GPS never written"
    return path


def _with_payload_appended(path: Path, payload: bytes = MP4_WITH_GPS) -> Path:
    """A clean image with a whole other file glued on after its end marker."""
    _clean(path)
    with path.open("ab") as handle:
        handle.write(payload)
    with Image.open(path) as image:
        # Pillow stops reading at the end marker and reports nothing about what
        # follows, which is the entire reason this needs its own detector.
        assert image.info.get("exif") is None
        assert image.size == (400, 200)
    assert payload in path.read_bytes()
    return path


def _signed(*assets: str) -> dict[str, redact.AssetRedaction]:
    return {
        asset: redact.AssetRedaction(asset=asset, reviewed_by="vineet", nothing_to_redact=True)
        for asset in assets
    }


# --------------------------------------------------------------------------- #
# what counts as metadata                                                      #
# --------------------------------------------------------------------------- #


def test_remaining_metadata_finds_exif(tmp_path: Path) -> None:
    assert redact.remaining_metadata(_with_gps(tmp_path / "a.jpg")) == ["EXIF"]


def test_remaining_metadata_finds_xmp_with_no_exif_at_all(tmp_path: Path) -> None:
    """The vector a GPS-tag search misses.

    Pillow cannot parse XMP without defusedxml, so anything that went looking
    for exif:GPSLatitude would read an empty dict off this file and call it
    clean.
    """
    path = tmp_path / "a.jpg"
    _flat().save(path, xmp=XMP_WITH_GPS)
    with Image.open(path) as image:
        assert "xmp" in image.info, "XMP never written"
        assert not dict(image.getexif()), "meant to be XMP-only"

    assert redact.remaining_metadata(path) == ["XMP"]


def test_remaining_metadata_finds_a_jpeg_comment(tmp_path: Path) -> None:
    """A COM segment is free-form text that survives every copy.

    In this repository it is an encoder banner - ffmpeg stamps one into every
    frame it extracts - which is exactly why it is easy to wave through. It is
    still an arbitrary string that nobody reads before committing.
    """
    path = tmp_path / "a.jpg"
    _flat().save(path, comment=b"shot at 37.425N 122.085W")
    assert redact.remaining_metadata(path) == ["JPEG comment"]


def test_remaining_metadata_finds_a_png_text_chunk(tmp_path: Path) -> None:
    path = tmp_path / "a.png"
    chunks = PngImagePlugin.PngInfo()
    chunks.add_text("Comment", "taken at home")
    _flat().save(path, pnginfo=chunks)
    assert redact.remaining_metadata(path) == ["PNG text chunk"]


def test_remaining_metadata_finds_iptc(tmp_path: Path) -> None:
    """IPTC is where an editing app writes the place name.

    The docstring has claimed this container since the check was written and
    nothing held it to the claim, so this test exists as much to pin the
    Photoshop-resource-block key Pillow actually uses as to pin the branch.
    """
    path = tmp_path / "a.jpg"
    _clean(path)
    raw = path.read_bytes()
    app13 = _iptc_app13(
        _iptc_dataset(2, 92, b"the seller's driveway"),  # 2:92 Sublocation
        _iptc_dataset(2, 90, b"Palo Alto"),  # 2:90 City
    )
    path.write_bytes(raw[:2] + app13 + raw[2:])
    with Image.open(path) as image:
        assert image.info.get("photoshop"), "APP13 never written"
        assert not dict(image.getexif()), "meant to be IPTC-only"

    assert redact.remaining_metadata(path) == ["IPTC"]


def test_remaining_metadata_finds_a_video_appended_after_the_jpeg_eoi(
    tmp_path: Path,
) -> None:
    """The Motion Photo layout, which is most of the phones in the world.

    Samsung and Pixel write a whole MP4 - GPS atom included - after the JPEG's
    EOI marker. Every other container in this file is something Pillow parses,
    and Pillow stops dead at EOI, so this payload was invisible: the check read
    the image, found nothing, and called the file pixels while the coordinates
    sat in the same bytes on disk.
    """
    path = _with_payload_appended(tmp_path / "front.jpg")
    assert redact.remaining_metadata(path) == ["data appended after the JPEG EOI marker"]


def test_remaining_metadata_finds_a_payload_appended_after_the_png_iend(
    tmp_path: Path,
) -> None:
    """Same trick, other format. A PNG decoder stops at IEND and everything
    after it rides along untouched."""
    path = _with_payload_appended(tmp_path / "front.png")
    assert redact.remaining_metadata(path) == ["data appended after the PNG IEND chunk"]


def test_a_jpeg_nested_inside_a_marker_segment_is_not_trailing_data(
    tmp_path: Path,
) -> None:
    """The cry-wolf case the detector has to survive.

    A whole JPEG - an EXIF thumbnail, a Photoshop preview - lives inside a
    length-prefixed segment and carries its own EOI marker. A detector that
    searched for the first or the last EOI would report trailing data on a file
    that ends exactly where it should, and a check that fires on clean files is
    one people learn to skip.
    """
    nested = tmp_path / "nested.jpg"
    _clean(nested)
    path = tmp_path / "a.jpg"
    _flat().save(path, comment=nested.read_bytes())

    data = path.read_bytes()
    assert data.count(b"\xff\xd9") > 1, "no nested end marker to trip over"
    assert redact.remaining_metadata(path) == ["JPEG comment"]


def test_remaining_metadata_is_empty_for_a_freshly_encoded_file(
    tmp_path: Path,
) -> None:
    """The JFIF density block a JPEG always carries is not metadata about the
    photograph, and treating it as such would make the check cry wolf on every
    file the tool itself produced."""
    assert redact.remaining_metadata(_clean(tmp_path / "a.jpg")) == []
    assert redact.remaining_metadata(_clean(tmp_path / "a.png")) == []


# --------------------------------------------------------------------------- #
# check reads the bytes                                                        #
# --------------------------------------------------------------------------- #


def test_check_refuses_a_signed_off_image_that_still_carries_gps(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole defect, in one test.

    Every record is signed, every answer is honest, and the file still names
    the seller's driveway because nobody ran `apply`. `check` is the last thing
    that runs before the commit, so `check` is where this has to fail.
    """
    _with_gps(tmp_path / "engine_bay.jpg")
    redact.save(tmp_path, _signed("engine_bay.jpg"))

    assert redact_media.cmd_check(tmp_path) == 1
    assert "engine_bay.jpg" in capsys.readouterr().err


def test_check_refuses_gps_that_is_only_in_the_xmp(tmp_path: Path) -> None:
    path = tmp_path / "front.jpg"
    _flat().save(path, xmp=XMP_WITH_GPS)
    redact.save(tmp_path, _signed("front.jpg"))

    assert redact_media.cmd_check(tmp_path) == 1


def test_check_passes_media_that_has_actually_been_stripped(tmp_path: Path) -> None:
    _clean(tmp_path / "engine_bay.jpg")
    _clean(tmp_path / "odometer.png")
    redact.save(tmp_path, _signed("engine_bay.jpg", "odometer.png"))

    assert redact_media.cmd_check(tmp_path) == 0


def test_check_refuses_a_format_this_tool_cannot_strip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An iPhone photograph is a .heic, and this tool cannot open one.

    Skipping it is the worst available answer: the file is never listed, never
    blurred, never re-encoded, and `check` reports the directory clean while
    the untouched original sits in the commit. Refuse what cannot be vouched
    for.
    """
    _clean(tmp_path / "front.jpg")
    (tmp_path / "IMG_0001.heic").write_bytes(b"\x00\x00\x00\x20ftypheic")
    redact.save(tmp_path, _signed("front.jpg"))

    assert redact_media.cmd_check(tmp_path) == 1
    assert "IMG_0001.heic" in capsys.readouterr().err


def test_check_refuses_a_signed_off_motion_photo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Signed, honest, and carrying a video with a position in it.

    Nothing about this file looks wrong to Pillow. It decodes, it has no EXIF,
    no XMP, no comment - and `strings` on it prints the coordinates.
    """
    path = _with_payload_appended(tmp_path / "front.jpg")
    redact.save(tmp_path, _signed("front.jpg"))

    assert redact_media.cmd_check(tmp_path) == 1
    assert "front.jpg" in capsys.readouterr().err
    assert b"+37.4250-122.0850" in path.read_bytes()


def test_apply_strips_an_appended_payload_and_then_check_is_green(
    tmp_path: Path,
) -> None:
    """The refusal has to have a remedy, or it is just an obstacle.

    `apply` re-encodes from the decoded pixels, so whatever was glued on after
    the end marker is not carried into the new file. This runs the real
    sequence rather than asserting it.
    """
    path = _with_payload_appended(tmp_path / "front.jpg")
    redact.save(tmp_path, _signed("front.jpg"))

    assert redact_media.cmd_apply(tmp_path) == 0
    assert b"+37.4250-122.0850" not in path.read_bytes()
    assert redact.remaining_metadata(path) == []
    assert redact_media.cmd_check(tmp_path) == 0


def test_check_refuses_a_format_pillow_can_open_but_this_tool_cannot_strip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The refusal, tested against a format that does not refuse itself.

    The .heic test above passes whether or not the format branch exists,
    because Pillow cannot identify a .heic and the unreadable-file handler
    reports it anyway - so it guards nothing it is presented as guarding.
    Pillow opens a .webp happily and reports no containers in one, so if the
    refusal is ever deleted this directory goes green with an image nobody
    reviewed and nothing re-encoded.
    """
    _clean(tmp_path / "front.jpg")
    _flat().save(tmp_path / "IMG_0002.webp")
    assert redact.remaining_metadata(tmp_path / "IMG_0002.webp") == []
    redact.save(tmp_path, _signed("front.jpg"))

    assert redact_media.cmd_check(tmp_path) == 1
    assert "IMG_0002.webp" in capsys.readouterr().err


def test_check_refuses_an_image_it_cannot_open(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ "Fails on the unreadable as well as the dirty" is a docstring sentence,
    so something has to hold it to it.

    A .jpg that is not a JPEG is the shape a truncated upload or a renamed file
    takes, and a check that swallowed the error would report it clean.
    """
    _clean(tmp_path / "front.jpg")
    (tmp_path / "broken.jpg").write_bytes(b"not a jpeg at all")
    redact.save(tmp_path, _signed("front.jpg", "broken.jpg"))

    assert redact_media.cmd_check(tmp_path) == 1
    assert "broken.jpg" in capsys.readouterr().err


def test_check_reports_the_paperwork_and_the_bytes_in_one_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two different failures, one run.

    Stopping at the first hides the second until the first is fixed, and a
    reviewer who has just been told about an unsigned file will fix that,
    re-run, and only then discover the GPS.
    """
    _with_gps(tmp_path / "signed_but_dirty.jpg")
    _clean(tmp_path / "never_reviewed.jpg")
    redact.save(tmp_path, _signed("signed_but_dirty.jpg"))

    assert redact_media.cmd_check(tmp_path) == 1
    err = capsys.readouterr().err
    assert "never_reviewed.jpg" in err
    assert "signed_but_dirty.jpg" in err


# --------------------------------------------------------------------------- #
# apply verifies its own claim                                                 #
# --------------------------------------------------------------------------- #


def test_apply_refuses_to_report_success_over_a_format_it_cannot_strip(
    tmp_path: Path,
) -> None:
    """`apply` prints "EXIF dropped" per file and a count at the end. Neither
    is true of the .heic it silently walked past."""
    _clean(tmp_path / "front.jpg")
    (tmp_path / "IMG_0001.heic").write_bytes(b"\x00\x00\x00\x20ftypheic")
    redact.save(tmp_path, _signed("front.jpg"))

    assert redact_media.cmd_apply(tmp_path) == 2


def test_the_re_encode_drops_containers_the_caller_never_mentioned(
    tmp_path: Path,
) -> None:
    """The remedy has to actually remove what the refusal names.

    `check` tells the reviewer "Run 'apply' - the re-encode is the only thing
    that removes it", and for two containers that was false. Pillow's JPEG
    writer reads `comment` and `xmp` from the *source* image's info when the
    caller passes neither, so both rode straight through the re-encode. A
    reviewer following the instruction got the same error again, and the fixture
    frames kept ffmpeg's encoder banner through every pass.
    """
    source = tmp_path / "front.jpg"
    _flat().save(
        source,
        comment=b"Lavc60.31.102\x00",
        xmp=XMP_WITH_GPS,
        exif=_gps_exif().tobytes(),
    )
    assert set(redact.remaining_metadata(source)) == {"EXIF", "XMP", "JPEG comment"}

    out = tmp_path / "clean.jpg"
    redact.redact_file(source, out, [])
    assert redact.remaining_metadata(out) == []


def test_the_re_encode_drops_png_text_chunks(tmp_path: Path) -> None:
    source = tmp_path / "front.png"
    chunks = PngImagePlugin.PngInfo()
    chunks.add_text("Comment", "taken at home")
    _flat().save(source, pnginfo=chunks)
    assert redact.remaining_metadata(source) == ["PNG text chunk"]

    out = tmp_path / "clean.png"
    redact.redact_file(source, out, [])
    assert redact.remaining_metadata(out) == []


def test_apply_refuses_before_it_re_encodes_anything(tmp_path: Path) -> None:
    """ "Refuses rather than reporting success" was really "mutates everything
    it can, then reports failure".

    The refusal ran after the loop, so a directory holding one file this tool
    cannot touch still had every other file irreversibly re-encoded before the
    error printed. The exit code was right and the disk was already changed.
    """
    dirty = _with_gps(tmp_path / "front.jpg")
    before = dirty.read_bytes()
    (tmp_path / "IMG_0001.heic").write_bytes(b"\x00\x00\x00\x20ftypheic")
    redact.save(tmp_path, _signed("front.jpg"))

    assert redact_media.cmd_apply(tmp_path) == 2
    assert dirty.read_bytes() == before, "refused, and re-encoded anyway"


def test_a_clip_that_cannot_be_walked_to_the_end_is_refused_not_announced(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """What this test used to assert is now the defect.

    Until P11 `check` printed an apology - "not examined: walkaround.mp4. This
    tool reads still images only" - and returned 0. That was an honest declared
    gap and it is not a check, and the clip in this repository's own fixtures
    carried a position atom, an encoder banner and x264's entire command line
    for four phases underneath it.

    The bytes below are the same truncated header the old test used: an `ftyp`
    box claiming 24 bytes with 12 on disk. It used to be waved through with a
    printed note. It is now refused, because a container that cannot be walked
    to the end is not a container anybody can call clean.
    """
    _clean(tmp_path / "front.jpg")
    (tmp_path / "walkaround.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
    redact.save(tmp_path, _signed("front.jpg"))

    assert redact_media.cmd_check(tmp_path) == 1
    err = capsys.readouterr().err
    assert "walkaround.mp4" in err
    assert "Unreadable is not clean" in err


def test_a_photograph_is_not_hidden_by_the_word_spectrogram_in_its_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The directory walk used to skip any name containing '.spectrogram'.

    That is a substring match against a filename, and front.spectrogram.jpg is
    a legal name for a photograph of the front of a car. Such a file was
    invisible to init, to apply and to check at once - never listed, never
    stripped, and reported clean.
    """
    _with_gps(tmp_path / "front.spectrogram.jpg")

    assert redact_media.cmd_check(tmp_path) == 1
    assert "front.spectrogram.jpg" in capsys.readouterr().err


def test_the_committed_fixture_media_passes_check(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """D-022 applied to this repository's own media.

    Every file under fixtures/demo-01/media is synthetic and has nothing to
    redact, and until now nothing said so and nothing checked. The frames
    ffmpeg extracts carried its encoder banner in a JPEG COM segment while
    README.md told the world the committed images carry no EXIF.
    """
    assert redact_media.cmd_check(REPO_ROOT / "fixtures" / "demo-01" / "media") == 0
    capsys.readouterr()


def test_apply_then_check_is_green_on_a_rotated_photograph_with_gps(
    tmp_path: Path,
) -> None:
    """Where stripping and orientation meet.

    The orientation tag is EXIF, so stripping EXIF throws it away - which is
    only safe because the pixels were transposed to match it first. This runs
    the real sequence and checks both halves at once: the blur lands where the
    reviewer drew it in the displayed frame, and nothing is left behind for
    `check` to find.
    """
    path = tmp_path / "rear.jpg"
    Image.fromarray(_plate_array()).save(path, exif=_gps_exif(orientation=6).tobytes())
    with Image.open(path) as image:
        assert dict(image.getexif().get_ifd(ExifTags.IFD.GPSInfo)), "GPS never written"
        displayed = np.asarray(_transposed(image).convert("L"))

    # Raw rows 140:180, cols 120:280 rotate to rows 120:280, cols 20:60 of the
    # 200x400 portrait every viewer shows. That portrait is what the reviewer
    # boxed.
    records = {
        "rear.jpg": redact.AssetRedaction(
            asset="rear.jpg",
            reviewed_by="vineet",
            regions=[
                redact.Region(
                    kind="plate",
                    box=BoundingBox(x=20 / 200, y=120 / 400, w=40 / 200, h=160 / 400),
                    note="rear plate, as displayed",
                )
            ],
        )
    }
    redact.save(tmp_path, records)

    assert redact_media.cmd_apply(tmp_path) == 0
    assert redact.remaining_metadata(path) == []
    assert redact_media.cmd_check(tmp_path) == 0

    with Image.open(path) as image:
        # No orientation tag survives, so the pixels themselves must already be
        # the displayed frame.
        assert image.size == (200, 400)
        after = np.asarray(image.convert("L"))

    def stripe_detail(array: np.ndarray) -> float:
        # The stripes run horizontally once rotated, so the detail that has to
        # die is the row-to-row variation.
        return float(np.abs(np.diff(array.astype(np.float32)[120:280, 20:60], axis=0)).mean())

    assert stripe_detail(after) < stripe_detail(displayed) / 8


def _transposed(image: Image.Image) -> Any:
    from PIL import ImageOps

    return ImageOps.exif_transpose(image)


# --------------------------------------------------------------------------- #
# nothing in the directory is invisible                                        #
# --------------------------------------------------------------------------- #


def test_check_refuses_a_document_nobody_signed_off(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A title history is where the seller's name and address actually are.

    Every walk in this tool is an allowlist of suffixes, and `.txt` was in none
    of them - so `history_01.txt` sat in this repository's own committed media
    directory while `check` printed "14 still image(s) ... no metadata
    container" over it and never named it. Nothing strips a plain-text file,
    because there is no container to strip; what it needs is the other half of
    D-022, a person saying it is safe to commit.
    """
    _clean(tmp_path / "front.jpg")
    (tmp_path / "history_01.txt").write_text("Seller: A Person, 12 Example St\n")
    redact.save(tmp_path, _signed("front.jpg"))

    assert redact_media.cmd_check(tmp_path) == 1
    assert "history_01.txt" in capsys.readouterr().err


def test_check_passes_a_document_that_was_read_and_signed_off(tmp_path: Path) -> None:
    _clean(tmp_path / "front.jpg")
    (tmp_path / "history_01.txt").write_text("SYNTHETIC - describes no owner\n")
    redact.save(tmp_path, _signed("front.jpg", "history_01.txt"))

    assert redact_media.cmd_check(tmp_path) == 0


def test_check_refuses_a_file_no_category_here_claims(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The default was to be invisible, and now it is to be refused.

    `.heic` had to be predicted in advance to be refused. This does not: a
    suffix nothing in redact.py has a category for is named and refused, so the
    next unanticipated file type fails the gate on the day it arrives rather
    than on the day somebody reads the directory listing.
    """
    _clean(tmp_path / "front.jpg")
    (tmp_path / "title_scan.pdf").write_bytes(b"%PDF-1.4\n")
    (tmp_path / "notes.sqlite").write_bytes(b"SQLite format 3\x00")
    redact.save(tmp_path, _signed("front.jpg"))

    assert redact_media.cmd_check(tmp_path) == 1
    err = capsys.readouterr().err
    assert "notes.sqlite" in err


def test_the_redaction_record_itself_is_not_treated_as_media(tmp_path: Path) -> None:
    """`redactions.json` is the paperwork, not the thing being vouched for.

    Exempted by exact filename rather than by suffix: a buyer can upload a
    .json, and an exempt suffix is a hole shaped like a file extension.
    """
    _clean(tmp_path / "front.jpg")
    redact.save(tmp_path, _signed("front.jpg"))
    assert redact_media.cmd_check(tmp_path) == 0

    (tmp_path / "listing_export.json").write_text("{}\n")
    assert redact_media.cmd_check(tmp_path) == 1


def test_init_scaffolds_a_record_for_a_document_too(tmp_path: Path) -> None:
    """`init` walked images only, so the document it now refuses to pass had no
    way to acquire the record it is refused for lacking."""
    _clean(tmp_path / "front.jpg")
    (tmp_path / "history_01.txt").write_text("x\n")

    assert redact_media.cmd_init(tmp_path) == 0
    assert set(redact.load(tmp_path)) == {"front.jpg", "history_01.txt"}
