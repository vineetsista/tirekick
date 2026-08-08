"""`check` has to read the clip too, and for nine phases it did not.

The still-image half of this grew a byte-level check, then a trailing-payload
check, then a refusal for formats it could not open. The video half got a
printed apology: `check` listed every .mp4 and .wav as "not examined" and went
green. That is a declared gap rather than a hidden one, which is the better of
two bad answers and is still an answer that lets a file ship unread.

What it let ship, in this repository's own fixtures, was a clip carrying three
separate payloads: an encoder banner in a (c)too tag atom, a second copy of it
in the 32-byte compressorname of the sample entry, and x264's entire command
line in a user-data SEI down in the coded stream, where no container reader
looks at all. A real walkaround video would carry the position it was shot in
as well, in the (c)xyz atom next to them.

So the containers are walked here, in pure Python. Not through ffprobe: a check
that can answer "skipped, the tool is not installed" has already passed on the
one machine where it mattered. ffmpeg is needed to *build* a dirty fixture and
to *remove* what is found, and both of those are allowed to be absent - reading
is not.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

from tirekick_engines import redact

REPO_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "redact_media_video", REPO_ROOT / "scripts" / "redact_media.py"
)
assert _spec is not None and _spec.loader is not None
redact_media = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(redact_media)

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe are not installed, and a dirty fixture has to be encoded",
)


def _ffmpeg(*args: str) -> None:
    result = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", *args], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def _dirty_clip(path: Path, *extra: str) -> Path:
    """An h264 clip exactly as ffmpeg hands it to you.

    Nobody asks for the banner in the compressorname or the build line in the
    SEI. They are what you get for encoding a video, which is why they are the
    payloads that survive every pass of a tool that only removes what somebody
    put there on purpose.
    """
    _ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=64x64:rate=10:duration=1",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        *extra,
        str(path),
    )
    return path


def _frame_count(path: Path) -> int:
    """Decoded frames, counted rather than read off a header field.

    nb_frames comes out of the sample table, so a strip that corrupted every
    chunk pointer while leaving the tables intact would still report the right
    number. Counting means something actually decoded.
    """
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return int(result.stdout.strip())


def _first_padded_free_box(data: bytes) -> int:
    """Offset of the payload of a `free` box that has one.

    The strip leaves these behind on purpose - a udta box retyped in place
    rather than cut out - so this is also the shape of the best hiding place in
    a stripped file: a box every reader is told to ignore, in a file that has
    just been declared clean.
    """
    position = 0
    while True:
        position = data.index(b"free", position + 1)
        size = int.from_bytes(data[position - 4 : position], "big")
        if size > 8 and not any(data[position + 4 : position - 4 + size]):
            return position + 4


def _sine_wav(path: Path, *extra: str) -> Path:
    _ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=0.2", *extra, str(path))
    return path


# --------------------------------------------------------------------------- #
# what an mp4 is carrying                                                      #
# --------------------------------------------------------------------------- #


@needs_ffmpeg
def test_the_gps_atom_in_a_udta_is_caught(tmp_path: Path) -> None:
    """(c)xyz is the atom that names the driveway.

    It is the video equivalent of the EXIF GPS IFD and it is the single thing
    this whole check exists for: a walkaround clip is shot standing next to the
    car, and the car is usually at the seller's house.
    """
    clip = _dirty_clip(tmp_path / "walkaround.mov", "-metadata", "location=+37.4250-122.0850/")

    found = redact.time_based_metadata(clip)
    assert any("©xyz" in item for item in found), found
    assert b"+37.4250-122.0850" in clip.read_bytes(), "the fixture never got a position"


@needs_ffmpeg
def test_the_encoder_banner_in_an_ilst_is_caught(tmp_path: Path) -> None:
    """(c)too holds the name of the tool that wrote the file.

    Harmless on its own, which is why it is the one everybody waves through -
    and it sits in the same ilst as the position, reached by the same walk. A
    check that skipped it would have to justify why udta/meta/ilst is worth
    walking into at all.
    """
    clip = _dirty_clip(tmp_path / "walkaround.mp4")

    found = redact.time_based_metadata(clip)
    assert "an mp4 udta box" in found
    assert "an mp4 meta box" in found
    assert "an mp4 ilst tag list" in found
    assert any("©too" in item for item in found), found


@needs_ffmpeg
def test_the_compressorname_names_the_library_that_wrote_it(tmp_path: Path) -> None:
    """A fixed 32-byte field inside the sample entry, not a tag anybody added.

    `-map_metadata -1` does not touch it, because it is not metadata as far as
    the muxer is concerned - it is part of the sample description. So it
    survives every strip that only drops tags, and it says "libx264" in a file
    the README describes as carrying nothing.
    """
    clip = _dirty_clip(tmp_path / "walkaround.mp4", "-map_metadata", "-1")

    found = redact.time_based_metadata(clip)
    assert any(item.startswith("an mp4 compressorname") for item in found), found
    assert any("libx264" in item for item in found), found


@needs_ffmpeg
def test_a_user_data_sei_in_the_coded_stream_is_caught(tmp_path: Path) -> None:
    """The copy no container reader will ever show you.

    x264 writes its full build string and option list into a user-data SEI on
    the first frame. It is inside mdat, past every box a metadata tool walks,
    and `strings` prints it. Finding it means walking the sample tables for
    real - avcC for the NAL length prefix, stsz for the sizes, stsc and stco
    for where the samples sit - because the cheap version of this, a substring
    search through mdat, fires on compressed data by coincidence and a check
    that cries wolf is a check people learn to skip.
    """
    clip = _dirty_clip(tmp_path / "walkaround.mp4")

    found = redact.time_based_metadata(clip)
    assert any(item.startswith("a user-data SEI") for item in found), found
    assert any("x264" in item for item in found), found
    assert b"x264 - core" in clip.read_bytes(), "the fixture never got an SEI"


@needs_ffmpeg
def test_the_sei_walk_stays_quiet_when_the_sei_was_filtered_out(tmp_path: Path) -> None:
    """The other half of the previous test, and the more important half.

    A detector that always fires proves nothing when it fires. This clip still
    has every container payload - udta, meta, ilst, the compressorname - and
    its type-6 NALs removed at the bitstream level, so the only difference
    between it and the file above is the thing the SEI walk claims to measure.
    """
    clip = _dirty_clip(tmp_path / "walkaround.mp4", "-bsf:v", "filter_units=remove_types=6")

    found = redact.time_based_metadata(clip)
    assert "an mp4 udta box" in found, "meant to still be dirty everywhere else"
    assert not any(item.startswith("a user-data SEI") for item in found), found


@needs_ffmpeg
def test_a_video_track_that_is_not_avc_is_reported_as_unwalkable(tmp_path: Path) -> None:
    """Silently skipping what you could not read is the defect, seven times over.

    This walker understands length-prefixed AVC and nothing else. An mpeg4 or
    hevc track therefore gets an honest "nothing here has looked at its coded
    stream" rather than an empty list that reads as clean.
    """
    clip = tmp_path / "walkaround.mp4"
    _ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=64x64:rate=10:duration=1",
        "-c:v",
        "mpeg4",
        "-pix_fmt",
        "yuv420p",
        str(clip),
    )

    found = redact.time_based_metadata(clip)
    assert any("cannot walk" in item and "mp4v" in item for item in found), found


@needs_ffmpeg
def test_a_sound_track_is_not_reported_as_unwalkable(tmp_path: Path) -> None:
    """The cry-wolf case for the rule above.

    "Report anything without an AVC sample entry" would fire on every audio
    track in the world, and a refusal nobody can act on is a refusal everybody
    routes around. A sound track has no coded video in it - that is a reason,
    not an omission.
    """
    clip = tmp_path / "engine.mp4"
    _ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=0.3",
        "-c:a",
        "aac",
        str(clip),
    )

    found = redact.time_based_metadata(clip)
    assert not any("cannot walk" in item for item in found), found


@needs_ffmpeg
def test_a_non_empty_free_box_is_caught(tmp_path: Path) -> None:
    """A `free` box is padding nobody reads, which makes it a good place to
    leave something.

    It matters more here than anywhere, because the strip in this file *creates*
    free boxes - it retypes udta in place rather than cutting it out. If a free
    box were assumed to be empty, the tool's own output would be the safest
    place in the repository to hide a coordinate.
    """
    clip = _dirty_clip(tmp_path / "walkaround.mp4")
    stripped = tmp_path / "clean.mp4"
    redact.strip_time_based_media(clip, stripped)
    assert redact.time_based_metadata(stripped) == []

    data = bytearray(stripped.read_bytes())
    at = _first_padded_free_box(bytes(data))
    data[at : at + 21] = b"+37.4250-122.0850/xxx"
    stripped.write_bytes(bytes(data))

    found = redact.time_based_metadata(stripped)
    assert any(item.startswith("a non-empty mp4 free box") for item in found), found


@needs_ffmpeg
def test_bytes_appended_after_the_last_box_are_caught(tmp_path: Path) -> None:
    """The Motion Photo trick, one container up.

    A player stops when it has read moov and mdat, so anything glued on after
    the last top-level box rides along invisibly - the same failure the still
    check found past the JPEG EOI marker. A bigger appendage than this one does
    not come back as a violation at all: it is refused as malformed, because
    bytes that do not parse as a box mean the walk cannot claim to have seen
    everything.
    """
    clip = _dirty_clip(tmp_path / "walkaround.mp4")
    stripped = tmp_path / "clean.mp4"
    redact.strip_time_based_media(clip, stripped)
    assert redact.time_based_metadata(stripped) == []

    with stripped.open("ab") as handle:
        handle.write(b"37.425")

    found = redact.time_based_metadata(stripped)
    assert any("appended after the last top-level box" in item for item in found), found


@needs_ffmpeg
def test_a_stripped_clip_carries_nothing(tmp_path: Path) -> None:
    """The refusal has to have a remedy, or it is only an obstacle.

    Every payload the checks above find, gone in one pass, and the picture
    untouched: `-c copy` with a bitstream filter re-muxes rather than
    re-encodes, so no frame is put through a second generation of compression
    to buy this.
    """
    clip = _dirty_clip(tmp_path / "walkaround.mov", "-metadata", "location=+37.4250-122.0850/")
    stripped = tmp_path / "clean.mp4"
    redact.strip_time_based_media(clip, stripped)

    assert redact.time_based_metadata(stripped) == []
    raw = stripped.read_bytes()
    for banner in (b"+37.4250-122.0850", b"x264 - core", b"libx264", b"VideoHandler"):
        assert banner not in raw, banner


@needs_ffmpeg
def test_strip_is_idempotent_and_keeps_every_frame(tmp_path: Path) -> None:
    """The failure this guards is silent and total.

    stco and co64 hold *absolute file offsets* into the media data. Cutting a
    box out of moov shifts every byte after it, and if moov comes first that
    means mdat moves while every chunk pointer keeps its old value - a file
    that still opens, still reports the right duration, and decodes garbage.
    Overwriting a box in place with a same-size `free` is the only safe answer,
    so the count of frames that actually decode is what this asserts, twice.
    """
    clip = _dirty_clip(tmp_path / "walkaround.mp4")
    before = _frame_count(clip)
    assert before == 10, "the fixture is not the length it claims"

    once = tmp_path / "once.mp4"
    redact.strip_time_based_media(clip, once)
    assert _frame_count(once) == before

    twice = tmp_path / "twice.mp4"
    redact.strip_time_based_media(once, twice)
    assert redact.time_based_metadata(twice) == []
    assert _frame_count(twice) == before


@needs_ffmpeg
def test_the_field_overwrite_moves_no_bytes(tmp_path: Path) -> None:
    """The rule the whole second step is built around, stated as an assertion.

    stco and co64 hold absolute file offsets. Cut a box out of moov in a
    faststart file - moov first, which is every mp4 meant to be streamed - and
    mdat slides backwards while every chunk pointer keeps its old value. So
    nothing is ever removed: udta is retyped to `free`, the standard skip box,
    and its payload zeroed, with its size left exactly as it was.

    Same length in, same length out, mdat at the same offset, and it still
    decodes.
    """
    clip = _dirty_clip(tmp_path / "walkaround.mp4", "-movflags", "+faststart")
    before = clip.read_bytes()
    assert before.index(b"moov") < before.index(b"mdat"), "not a faststart layout"

    data = bytearray(before)
    for offset, replacement in redact._mp4_scrub_edits(before):
        data[offset : offset + len(replacement)] = replacement

    assert len(data) == len(before), "the surgery changed the length of the file"
    assert data.index(b"mdat") == before.index(b"mdat"), "mdat moved"
    assert b"udta" not in bytes(data)
    assert b"VideoHandler" not in bytes(data)

    clip.write_bytes(bytes(data))
    assert _frame_count(clip) == 10


@needs_ffmpeg
def test_cutting_the_box_out_instead_corrupts_every_chunk_pointer(
    tmp_path: Path,
) -> None:
    """What the rule above is protecting against, demonstrated rather than
    asserted about.

    This is the obvious implementation - find udta, delete its bytes, shrink
    moov to match - and it produces a file that still has a valid header, still
    reports the right duration, still opens in a player, and decodes nothing,
    because every offset in stco now points 98 bytes into the wrong place. The
    metadata really is gone. So is the video.
    """
    clip = _dirty_clip(tmp_path / "walkaround.mp4", "-movflags", "+faststart")
    data = bytearray(clip.read_bytes())
    assert _frame_count(clip) == 10

    moov = data.index(b"moov") - 4
    moov_size = int.from_bytes(data[moov : moov + 4], "big")
    udta = data.index(b"udta") - 4
    udta_size = int.from_bytes(data[udta : udta + 4], "big")
    del data[udta : udta + udta_size]
    data[moov : moov + 4] = (moov_size - udta_size).to_bytes(4, "big")

    broken = tmp_path / "broken.mp4"
    broken.write_bytes(bytes(data))
    assert b"\xa9too" not in bytes(data), "the tag really was removed"
    assert not _decodes(broken), "cut a box out of moov and it still decoded"


def _decodes(path: Path) -> bool:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip().isdigit()


# --------------------------------------------------------------------------- #
# unreadable is not clean                                                      #
# --------------------------------------------------------------------------- #


@needs_ffmpeg
def test_a_truncated_mp4_raises_rather_than_reporting_clean(tmp_path: Path) -> None:
    """Half a file is not a clean file.

    A walk that stopped early has not seen the boxes it did not reach, and the
    empty list it would return is indistinguishable from the one a genuinely
    stripped clip produces. This is the same rule `assert_metadata_stripped`
    already applies to an image Pillow cannot open.
    """
    clip = _dirty_clip(tmp_path / "walkaround.mp4")
    truncated = tmp_path / "half.mp4"
    truncated.write_bytes(clip.read_bytes()[: clip.stat().st_size // 2])

    with pytest.raises(redact.MalformedMedia):
        redact.time_based_metadata(truncated)


def test_a_box_header_with_no_box_behind_it_raises(tmp_path: Path) -> None:
    """Twelve bytes claiming to be twenty-four.

    This is the shape a truncated upload takes, and it is also the placeholder
    the old tests used to stand in for a video - which is worth remembering,
    because the version of `check` that walked past every .mp4 reported this
    file as unexamined and exited zero.
    """
    clip = tmp_path / "walkaround.mp4"
    clip.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    with pytest.raises(redact.MalformedMedia):
        redact.time_based_metadata(clip)


@needs_ffmpeg
def test_garbage_after_the_last_box_raises_instead_of_reading_clean(
    tmp_path: Path,
) -> None:
    """The test that actually holds the walker to "unreadable is not clean".

    The two above it do not, and it took a mutation to find that out: with the
    raise deleted they still went red, but on the *no moov box* guard rather
    than on the overrun, so they would have passed a walker that quietly
    stopped at the first box it could not parse. This file has a complete moov
    and a complete mdat and twenty-one bytes on the end that are not a box, and
    a walker that returns what it managed to read reports it as carrying
    nothing at all.
    """
    clip = _dirty_clip(tmp_path / "walkaround.mp4")
    stripped = tmp_path / "clean.mp4"
    redact.strip_time_based_media(clip, stripped)
    assert redact.time_based_metadata(stripped) == []

    with stripped.open("ab") as handle:
        handle.write(b"+37.4250-122.0850/xxx")

    with pytest.raises(redact.MalformedMedia):
        redact.time_based_metadata(stripped)


@needs_ffmpeg
def test_a_nested_box_that_overruns_its_parent_raises(tmp_path: Path) -> None:
    """A box inside udta claiming more bytes than udta has.

    Everything before it reads fine, so a walker that gave up quietly here
    would return a list of real findings, look like it was working, and never
    say that it stopped short of the atom holding the position.
    """
    clip = _dirty_clip(tmp_path / "walkaround.mp4")
    data = bytearray(clip.read_bytes())
    # Four bytes past the type is the first child's size field.
    at = data.index(b"udta") + 4
    data[at : at + 4] = (0xFFFF).to_bytes(4, "big")
    clip.write_bytes(bytes(data))

    with pytest.raises(redact.MalformedMedia):
        redact.time_based_metadata(clip)


def test_an_mp4_with_no_moov_raises(tmp_path: Path) -> None:
    """No sample table, no walk, no claim.

    A fragmented or streaming-only file has nothing here can read the coded
    stream through, and answering [] would mean "I found no metadata" when the
    truth is "I could not look".
    """
    clip = tmp_path / "walkaround.mp4"
    clip.write_bytes(b"\x00\x00\x00\x10ftypisom\x00\x00\x02\x00")

    with pytest.raises(redact.MalformedMedia):
        redact.time_based_metadata(clip)


def test_a_wav_that_is_not_a_wav_raises(tmp_path: Path) -> None:
    """A renamed file is the commonest way a recording arrives in the wrong
    format, and reporting it clean is the worst available answer."""
    path = tmp_path / "engine.wav"
    path.write_bytes(b"not a riff file at all")

    with pytest.raises(redact.MalformedMedia):
        redact.time_based_metadata(path)


# --------------------------------------------------------------------------- #
# what a wav is carrying                                                       #
# --------------------------------------------------------------------------- #


@needs_ffmpeg
def test_a_wav_list_info_block_is_caught(tmp_path: Path) -> None:
    """The .wav is not inert. It carries whatever the recorder felt like.

    A LIST/INFO block holds the title, the artist, the software and the
    comment, and none of it is audible, so nobody notices it is there until it
    is in a public repository.
    """
    path = _sine_wav(tmp_path / "engine.wav", "-metadata", "title=the seller's driveway")

    assert redact.time_based_metadata(path) == ["a RIFF LIST/INFO block"]
    assert b"driveway" in path.read_bytes(), "the fixture never got a title"


@needs_ffmpeg
def test_a_broadcast_wave_bext_chunk_is_caught(tmp_path: Path) -> None:
    """bext is where a field recorder writes the date, the time and the machine.

    Not a tag anybody typed - the recorder puts it there - which puts it in the
    same class as the compressorname above: metadata that survives precisely
    because nobody chose it.
    """
    path = _sine_wav(tmp_path / "engine.wav", "-write_bext", "1")

    found = redact.time_based_metadata(path)
    assert any(item.startswith("a broadcast-wave bext chunk") for item in found), found


@needs_ffmpeg
def test_a_clean_wav_passes(tmp_path: Path) -> None:
    """The cry-wolf guard for the whole RIFF walk.

    `fmt `, `data` and `fact` are what makes a WAVE file a WAVE file. A check
    that flagged them would fire on every recording ever made, including the
    one this repository ships, and a gate that is always red gets switched off.
    """
    path = _sine_wav(tmp_path / "engine.wav", "-map_metadata", "-1", "-fflags", "+bitexact")

    assert redact.time_based_metadata(path) == []


@needs_ffmpeg
def test_stripping_a_wav_keeps_the_samples_and_drops_the_rest(tmp_path: Path) -> None:
    """Chunks can be cut out of a RIFF file in a way they can never be cut out
    of an mp4: a WAVE file holds no absolute offsets into itself, so nothing
    points at anything that moves."""
    dirty = _sine_wav(tmp_path / "engine.wav", "-metadata", "title=the seller's driveway")
    samples_before = dirty.read_bytes().find(b"data")
    assert samples_before > 0

    clean = tmp_path / "clean.wav"
    redact.strip_time_based_media(dirty, clean)

    assert redact.time_based_metadata(clean) == []
    assert b"driveway" not in clean.read_bytes()
    assert _frame_count_wav(dirty) == _frame_count_wav(clean)


def _frame_count_wav(path: Path) -> int:
    data = path.read_bytes()
    at = data.index(b"data")
    return int.from_bytes(data[at + 4 : at + 8], "little")


# --------------------------------------------------------------------------- #
# check and apply                                                              #
# --------------------------------------------------------------------------- #


@needs_ffmpeg
def test_check_refuses_the_dirty_clip_and_passes_the_stripped_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole defect, in one test.

    Nothing in this directory is unreviewed and nothing in it is an image, and
    the old `check` printed a "not examined" line and exited zero with the
    seller's position in the only file present.
    """
    clip = _dirty_clip(tmp_path / "walkaround.mov", "-metadata", "location=+37.4250-122.0850/")

    assert redact_media.cmd_check(tmp_path) == 1
    assert "walkaround.mov" in capsys.readouterr().err

    redact.strip_time_based_media(clip, clip)
    assert redact_media.cmd_check(tmp_path) == 0


@needs_ffmpeg
def test_apply_strips_the_clip_and_then_verifies_its_own_claim(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`apply` prints a line per file saying what it dropped. That line is a
    claim, and this repository's rule is that a claim nothing checks is the
    defect.

    So `apply` re-runs the walk over its own output before it reports success -
    which is not ceremony: the remux writes a *fresh* compressorname and hdlr
    name into the file it was asked to strip, and without the second pass over
    the bytes the tool would confidently hand back a file it had just re-dirtied.
    """
    _dirty_clip(tmp_path / "walkaround.mp4")

    assert redact_media.cmd_apply(tmp_path) == 0
    assert redact.time_based_metadata(tmp_path / "walkaround.mp4") == []
    assert "remuxed" in capsys.readouterr().out
    assert redact_media.cmd_check(tmp_path) == 0


def test_check_refuses_a_container_nothing_here_can_walk(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The gap moved, it did not close.

    A .webm keeps its tags in an EBML `Tags` element and there is no EBML
    reader in this repository. Naming and refusing it is the same answer .heic
    gets, and the alternative - walking past it - is exactly what this whole
    phase was written to remove.
    """
    (tmp_path / "walkaround.webm").write_bytes(b"\x1aE\xdf\xa3not really webm")

    assert redact_media.cmd_check(tmp_path) == 1
    assert "walkaround.webm" in capsys.readouterr().err


@needs_ffmpeg
def test_apply_refuses_before_it_rewrites_anything(tmp_path: Path) -> None:
    """ "Refuses rather than reporting success" has meant "mutates everything it
    can, then reports failure" in this file before.

    A remux is not reversible either, so the refusal for an unwalkable
    container has to land before the first ffmpeg call, not after the loop.

    The names are deliberate. With the .webm sorting first, this test passed
    against a build with the pre-flight refusal deleted - the loop hit the
    unreadable file before it reached anything it could damage, and the test
    was measuring the alphabet. Sorting it last is the only version of this
    that asks the question.
    """
    clip = _dirty_clip(tmp_path / "aaa_walkaround.mp4")
    before = clip.read_bytes()
    (tmp_path / "zzz_engine.webm").write_bytes(b"\x1aE\xdf\xa3not really webm")

    assert redact_media.cmd_apply(tmp_path) == 2
    assert clip.read_bytes() == before, "refused, and remuxed anyway"


def test_the_committed_fixture_clip_and_wav_pass_check() -> None:
    """D-022 applied to this repository's own media, for the half that was
    exempt from it.

    fixtures/demo-01/media/video_01.mp4 shipped for nine phases with an encoder
    banner in its ilst, a second one in its compressorname and x264's command
    line in its coded stream, while a test three files over asserted that
    `check` on this exact directory returned zero. It did. It was not reading
    the clip.

    No ffmpeg guard on this one on purpose: the walk is pure Python, and a test
    of a committed artefact that can quietly skip itself is worth nothing.
    """
    media = REPO_ROOT / "fixtures" / "demo-01" / "media"
    for name in ("video_01.mp4", "audio_01.wav"):
        assert redact.time_based_metadata(media / name) == [], name

    redact.assert_time_based_metadata_stripped(media, redact_media.time_based_media(media))


def test_the_committed_clip_still_decodes_to_the_frames_it_always_did() -> None:
    """The strip that cleaned the fixture had to not break it.

    Every other suite that reads this clip - frame selection, walkaround,
    scaling - takes 210 frames of 640x400 for granted, and a remux that
    repointed the chunk offsets would leave a file that opens and decodes
    nothing.
    """
    if shutil.which("ffprobe") is None:
        pytest.skip("ffprobe is not installed")
    clip = REPO_ROOT / "fixtures" / "demo-01" / "media" / "video_01.mp4"
    assert _frame_count(clip) == 210


# --------------------------------------------------------------------------- #
# when the car was filmed                                                      #
# --------------------------------------------------------------------------- #


@needs_ffmpeg
def test_the_creation_time_says_when_the_car_was_filmed(tmp_path: Path) -> None:
    """The one field here read by value rather than by container, on purpose.

    `mvhd`, `tkhd` and `mdhd` are structurally required, so there is no
    container to assert the absence of - only two fixed-width fields holding
    seconds since 1904 UTC of the moment the recording was made. A walkaround
    video shot at the viewing says when the buyer stood in the seller's
    driveway, and beside a listing that is a strong identifier.

    The committed fixture clip carries zeroes in all three, which is why this
    test builds its own: the fixture is clean because ffmpeg was asked for
    `-fflags +bitexact`, not because anything checked, and a fixture that is
    clean by accident of an encoder flag cannot tell a working check from an
    absent one.
    """
    clip = _dirty_clip(
        tmp_path / "walkaround.mp4", "-metadata", "creation_time=2024-06-01T14:30:00Z"
    )

    stamped = [line for line in redact.mp4_metadata(clip) if "timestamp" in line]
    assert len(stamped) == 3, redact.mp4_metadata(clip)
    assert all("creation=3800097000" in line for line in stamped)


@needs_ffmpeg
def test_stripping_zeroes_the_timestamps_without_moving_a_byte(tmp_path: Path) -> None:
    """Zeroed rather than removed, and the file length is the proof.

    These three boxes cannot be dropped - the file is not a file without them -
    so the fields are overwritten in place. Everything `stco` points at stays
    where it was.
    """
    clip = _dirty_clip(
        tmp_path / "walkaround.mp4", "-metadata", "creation_time=2024-06-01T14:30:00Z"
    )
    out = tmp_path / "clean.mp4"
    redact.strip_time_based_media(clip, out)

    assert redact.mp4_metadata(out) == []

    # Stripping an already-clean clip finds nothing more to remove. Byte
    # equality is deliberately NOT asserted here: the second pass remuxes and
    # recomputes `btrt`'s max-bitrate field from the now-smaller file, so two
    # bytes differ that describe the encoding rather than the recording. Pinning
    # the bytes would fail on a fact about ffmpeg's arithmetic and read as a
    # metadata leak.
    again = tmp_path / "clean2.mp4"
    redact.strip_time_based_media(out, again)
    assert redact.mp4_metadata(again) == []
    assert again.stat().st_size == out.stat().st_size


@needs_ffmpeg
def test_the_in_place_scrub_alone_zeroes_the_timestamps(tmp_path: Path) -> None:
    """The scrub is pinned directly, because the pipeline hides it.

    `strip_time_based_media` remuxes through ffmpeg with `-fflags +bitexact`
    before the in-place pass runs, and that flag already zeroes these three
    fields. So deleting the timestamp edit from `_mp4_scrub_edits` changes
    nothing that any end-to-end test can see: the mechanism was decorative under
    every test that went through the whole strip, and a mutation run said so.

    That is worth keeping rather than deleting, because the offset-preserving
    scrub is the half of the strip this repository controls - the ffmpeg
    invocation is a flag on somebody else's tool, and "clean because of a flag
    we happen to pass" is how the fixture clip came to be clean by accident in
    the first place. So it is tested where it can actually fail: the edits are
    applied on their own, with no remux in front of them.
    """
    clip = _dirty_clip(
        tmp_path / "walkaround.mp4", "-metadata", "creation_time=2024-06-01T14:30:00Z"
    )
    data = bytearray(clip.read_bytes())
    assert [line for line in redact.mp4_metadata(clip) if "timestamp" in line]

    for offset, replacement in redact._mp4_scrub_edits(bytes(data)):
        data[offset : offset + len(replacement)] = replacement

    scrubbed = tmp_path / "scrubbed.mp4"
    scrubbed.write_bytes(bytes(data))

    assert len(data) == clip.stat().st_size, "the scrub moved bytes"
    assert [line for line in redact.mp4_metadata(scrubbed) if "timestamp" in line] == []
