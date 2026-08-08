"""Irreversible redaction of number plates and faces.

Pulled forward from P6 because D-022 made it a blocker rather than a polish item:
real vehicle photographs cannot be committed until this exists, and the eval set
cannot be measured until they are.

The design question here is not how to blur. It is who is allowed to decide that
an image is clean.

An automatic detector that misses one plate in fifty is worse than no detector,
because it produces a folder everybody now believes is safe. `git rm` does not
remove anything from history, so a single miss is permanent and public the moment
the repository is. So the model never gets the last word: it proposes regions, a
human confirms or corrects them, and the confirmation is written down with a name
against it. `assert_reviewed` is the gate, and it fails on absence rather than
passing on it - an image with no redaction record is treated as unreviewed, not as
having nothing to redact.

"Nothing to redact" is a legitimate answer, and it has to be stated explicitly by
a person. That is the difference between a photograph somebody checked and a
photograph nobody looked at.

Stripping metadata is the other half of the job, and it is not conditional on
finding anything to blur. The re-encode in `redact_file` is the only thing in
this repository that removes EXIF, and most of the standard capture views -
interior, engine bay, odometer - carry no plate and no face, so they are exactly
the images a reviewer honestly marks "nothing to redact". Those files still hold
the GPS position of wherever the photograph was taken, which is somebody's
driveway.

`remaining_metadata` therefore asks whether a metadata container is present at
all, not whether a coordinate is present inside one. That is a deliberate choice
about what can honestly be checked. A position can sit in the EXIF GPS IFD, in
an XMP packet, in an IPTC record, in a JPEG comment or inside a vendor
MakerNote, and Pillow parses some of those and silently returns nothing for the
rest - getxmp() answers {} with a warning unless defusedxml happens to be
installed. A check that went looking for coordinates would read an empty dict
off a geotagged file and pass it. Containers are what Pillow can see reliably,
and "no containers" is exactly what the re-encode leaves behind, so the check
asserts the thing the tool actually establishes.

Except that Pillow is not the only reader of these files, and the bytes past the
end of the image are the ones it never sees. Samsung's Motion Photo and Google's
MicroVideo append an entire MP4 - GPS atom included - after the JPEG EOI marker,
and a decoder stops at EOI by definition, so that payload was invisible to every
container check here: the file decoded, reported nothing, and `strings` on it
printed the coordinates. That is the layout of a large share of the photographs
people actually take, so the end marker is walked to for real and anything past
it counts as a container.

Video and audio were the same hole, and they stayed open longer. An .mp4 keeps
a position in a (c)xyz atom under udta/meta/ilst, an encoder banner in the
32-byte compressorname of every sample entry, and - because x264 writes its
entire build line into a user-data SEI - a third copy down in the coded stream
where no container reader looks at all. A .wav carries a LIST/INFO block. None
of it was read: `check` named those files as unexamined instead, which is a
declared gap rather than a hidden one and is still a gap. This repository's own
committed clip carried all three payloads for nine phases while a test asserted
that green meant something.

`time_based_metadata` closes it, and walks the containers in pure Python rather
than shelling out to ffprobe. A check that answers "skipped, ffprobe is not
installed" has passed on exactly the machine where it mattered, and a gate that
can skip is not a gate. What no walker here understands - .webm's EBML, an
.mp3's ID3 frames - is named and refused by suffix, the same answer .heic gets,
because a file nobody opened is not a file anybody can vouch for.

The orientation tag is the one piece of EXIF that has to survive long enough to
be used: `redact_file` transposes the pixels to match it, and only then drops it
with the rest.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import BoundingBox

REDACTIONS_FILENAME = "redactions.json"

#: Blur radius as a fraction of the region's smaller side. Large, on purpose: a
#: lightly blurred plate is still readable by anything built to read plates, and
#: a plate that is readable has not been redacted.
BLUR_FRACTION = 0.35

#: Pixel grid applied under the blur. Blur alone is theoretically invertible if
#: the kernel is known; quantising to a coarse grid first destroys the
#: information rather than smearing it.
PIXEL_BLOCKS = 6

#: Every region is grown by this fraction of its size before blurring, because a
#: box drawn snugly around a plate usually clips a character at the edge.
PADDING_FRACTION = 0.08

REDACTABLE_KINDS = ("plate", "face", "vin", "document_id", "other")

#: What `apply` can open, transpose, blur and re-encode. The re-encode is the
#: only thing here that removes EXIF, so this is also the exact set of files the
#: tool is able to make any promise about.
STRIPPABLE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})

#: Photographic formats this tool cannot process. Named rather than ignored: an
#: iPhone shoots .heic by default, and a .heic that is quietly skipped is never
#: listed, never blurred and never re-encoded while `check` calls the directory
#: clean. Refusal is the only honest answer to a file we cannot read.
UNSTRIPPABLE_SUFFIXES = frozenset(
    {
        ".heic",
        ".heif",
        ".avif",
        ".webp",
        ".tif",
        ".tiff",
        ".bmp",
        ".gif",
        ".dng",
        ".cr2",
        ".cr3",
        ".nef",
        ".arw",
        ".orf",
        ".raf",
        ".rw2",
    }
)

#: Time-based media whose containers the walkers below can read end to end:
#: ISO base media (mp4/mov) and RIFF/WAVE. These were the files `check` used to
#: list as unexamined.
READABLE_MEDIA_SUFFIXES = frozenset({".mp4", ".m4v", ".mov", ".wav"})

#: Time-based media nothing here can walk. Named rather than ignored, for the
#: same reason .heic is: a .webm hides its tags in an EBML `Tags` element and an
#: .mp3 hides them in an ID3 frame, and neither has a reader in this file. The
#: gap moved, it did not close - so it still has to be refused out loud instead
#: of passing quietly through a directory scan.
UNREADABLE_MEDIA_SUFFIXES = frozenset(
    {
        ".avi",
        ".mkv",
        ".webm",
        ".mp3",
        ".m4a",
        ".aac",
        ".flac",
        ".ogg",
        ".mpg",
        ".mpeg",
        ".wmv",
        ".3gp",
    }
)

#: Buyer paperwork stored as plain text. There is no metadata container in a
#: .txt - the content is the whole file - so nothing here strips one. What a
#: document does need is the other half of D-022: a person confirming it is safe
#: to commit, because a title history is where the seller's name, address and
#: full VIN actually live, and no amount of pixel blurring touches any of them.
DOCUMENT_SUFFIXES = frozenset({".txt", ".md", ".csv"})

#: Documents this tool can neither read nor vouch for. A PDF carries an Info
#: dictionary and usually an XMP packet - author, producer, sometimes a path
#: naming the person who scanned it - and stripping those is a job nothing here
#: does. Refused for the same reason a .heic is.
UNREADABLE_DOCUMENT_SUFFIXES = frozenset(
    {".pdf", ".doc", ".docx", ".rtf", ".odt", ".pages", ".xls", ".xlsx", ".numbers"}
)

#: Files that are the record rather than the media it describes. Matched by exact
#: name, not by suffix: `.json` at large is not exempt from review, because a
#: buyer can upload one and an exempt suffix is a hole shaped like a file
#: extension.
NOT_MEDIA_FILENAMES = frozenset({REDACTIONS_FILENAME})


def unaccounted_files(directory: Path, paths: list[Path]) -> list[str]:
    """Refusal lines for files no category in this module claims.

    Every walk in this tool is an allowlist of suffixes, and until P11 the
    default for anything outside all of them was to be invisible - not listed,
    not reviewed, not stripped, and not mentioned by the success line. The
    directory this repository commits contains `history_01.txt`, a title history,
    and `check` printed "14 still image(s) ... no metadata container" over it for
    four phases without ever naming it. A real buyer's version of that file is a
    scan of a title certificate with their address on it.

    So the default is inverted here. A file this tool has no category for is
    refused by name, which is the same answer `.heic` already got - the
    difference is that `.heic` had to be predicted in advance and this does not.
    """
    known = (
        STRIPPABLE_SUFFIXES
        | UNSTRIPPABLE_SUFFIXES
        | READABLE_MEDIA_SUFFIXES
        | UNREADABLE_MEDIA_SUFFIXES
        | DOCUMENT_SUFFIXES
        | UNREADABLE_DOCUMENT_SUFFIXES
    )
    return [
        f"{asset_key(directory, path)}: nothing in this tool has a category for "
        f"{path.suffix or 'a file with no extension'}, so it was never reviewed, "
        f"never stripped and never checked. Add it to a suffix set in redact.py "
        f"or take it out of the media directory."
        for path in sorted(paths)
        if path.name not in NOT_MEDIA_FILENAMES and path.suffix.lower() not in known
    ]


class RedactionError(RuntimeError):
    """Redaction is missing, unreviewed, or malformed."""


class MalformedMedia(RedactionError):
    """A container that could not be walked to its end.

    Raised rather than returning an empty violation list, because those two
    answers are not the same answer and this repository has confused them
    before. "I looked everywhere and found nothing" and "I stopped reading
    halfway through a box that declared more bytes than the file has" both come
    out as green if the second one is allowed to return [].
    """


def asset_key(directory: Path, path: Path) -> str:
    """The record key for an image: its path relative to the redaction
    directory, extension and subdirectories included.

    A bare stem is not enough. photo_01.jpg and photo_01.png, or the same
    camera-default IMG_0001.jpg in two session folders, would share one record,
    and a single signature must never vouch for two files.
    """
    return path.relative_to(directory).as_posix()


@dataclass(frozen=True)
class Region:
    kind: str
    box: BoundingBox
    note: str = ""


@dataclass
class AssetRedaction:
    asset: str
    #: Who confirmed this image. A name, not a boolean.
    reviewed_by: str = ""
    reviewed_at: str = ""
    regions: list[Region] = field(default_factory=list)
    #: True only when a person looked and found nothing to hide.
    nothing_to_redact: bool = False

    @property
    def reviewed(self) -> bool:
        return bool(self.reviewed_by) and (self.nothing_to_redact or bool(self.regions))


def load(directory: Path) -> dict[str, AssetRedaction]:
    path = directory / REDACTIONS_FILENAME
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, AssetRedaction] = {}
    for asset, entry in (data.get("assets") or {}).items():
        out[asset] = AssetRedaction(
            asset=asset,
            reviewed_by=entry.get("reviewed_by", ""),
            reviewed_at=entry.get("reviewed_at", ""),
            nothing_to_redact=bool(entry.get("nothing_to_redact")),
            regions=[
                Region(
                    kind=r["kind"],
                    box=BoundingBox(**r["box"]),
                    note=r.get("note", ""),
                )
                for r in entry.get("regions") or []
            ],
        )
    return out


def save(directory: Path, records: dict[str, AssetRedaction]) -> Path:
    path = directory / REDACTIONS_FILENAME
    payload: dict[str, Any] = {
        "_note": (
            "Redaction record. Every image in this directory must appear here with "
            "a reviewed_by name before it can be committed (D-022). "
            "nothing_to_redact means a person looked and found nothing - it is not "
            "a default. Keys are the image path relative to this file's directory, "
            "extension included: 'photo_01.jpg', not 'photo_01'. A bare stem "
            "matches no image and vouches for nothing."
        ),
        "assets": {
            asset: {
                "reviewed_by": record.reviewed_by,
                "reviewed_at": record.reviewed_at,
                "nothing_to_redact": record.nothing_to_redact,
                "regions": [
                    {
                        "kind": r.kind,
                        "box": r.box.model_dump(),
                        "note": r.note,
                    }
                    for r in record.regions
                ],
            }
            for asset, record in sorted(records.items())
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def stamp_review(record: AssetRedaction, reviewer: str) -> AssetRedaction:
    record.reviewed_by = reviewer
    record.reviewed_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return record


def apply_to_image(image: Any, regions: list[Region]) -> Any:
    """Destroy the pixels inside each region. Returns a new image.

    Pixelate then blur. Blur alone smears information that is recoverable if the
    kernel is known; quantising to a coarse grid first throws it away.
    """
    from PIL import Image, ImageFilter

    out = image.convert("RGB").copy()
    width, height = out.size

    for region in regions:
        pad_w = region.box.w * PADDING_FRACTION
        pad_h = region.box.h * PADDING_FRACTION
        left = max(0, int((region.box.x - pad_w) * width))
        top = max(0, int((region.box.y - pad_h) * height))
        right = min(width, int((region.box.x + region.box.w + pad_w) * width))
        bottom = min(height, int((region.box.y + region.box.h + pad_h) * height))
        if right <= left or bottom <= top:
            continue

        patch = out.crop((left, top, right, bottom))
        small = patch.resize(
            (max(1, patch.width // PIXEL_BLOCKS), max(1, patch.height // PIXEL_BLOCKS)),
            Image.Resampling.BILINEAR,
        )
        patch = small.resize(patch.size, Image.Resampling.NEAREST)
        radius = max(4.0, min(patch.width, patch.height) * BLUR_FRACTION)
        patch = patch.filter(ImageFilter.GaussianBlur(radius=radius))
        out.paste(patch, (left, top))

    return out


def redact_file(source: Path, destination: Path, regions: list[Region]) -> None:
    from PIL import Image, ImageOps

    with Image.open(source) as image:
        # The reviewer drew their boxes on the image as a viewer displays it,
        # and every viewer honours the EXIF orientation tag while Image.open
        # does not. Transpose the pixels first, so the coordinates mean what
        # the reviewer saw - otherwise a box over a plate in a rotated phone
        # photo blurs a strip of sky and the plate ships readable.
        oriented = ImageOps.exif_transpose(image)
        result = apply_to_image(oriented, regions)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # A re-encode is not by itself a strip. Pillow carries the source image's
    # `info` dict through convert() and copy(), and its JPEG writer reads
    # `comment` (and, depending on version, `xmp`) out of that dict when the
    # caller passes neither - so the encoder banner ffmpeg stamps into every
    # extracted frame survived every pass of a tool whose error message says
    # "the re-encode is the only thing that removes it". Empty the dict and
    # there is nothing left for any writer to decide to keep.
    result.info.clear()
    # Re-encode rather than copy: the original EXIF carries GPS coordinates of
    # wherever the photograph was taken, which is somebody's driveway. The
    # orientation tag is discarded with the rest, which is safe precisely
    # because the pixels above were already transposed to match it.
    if destination.suffix.lower() == ".png":
        result.save(destination, format="PNG")
    else:
        result.save(destination, format="JPEG", quality=92)


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

#: JPEG markers with no length field after them: TEM, the eight restart markers,
#: and SOI. Everything else in the marker space is followed by a 16-bit length.
_JPEG_STANDALONE = frozenset({0x01, *range(0xD0, 0xD9)})


def _jpeg_scan_end(data: bytes, start: int) -> int | None:
    """Offset of the marker that ends the entropy-coded data starting here.

    Inside a scan an 0xFF byte is stuffed (0xFF 0x00), a restart marker, or a
    fill byte; anything else is the next real marker. This is why the scan
    cannot be skipped by a length field, and why searching the file for 0xFFD9
    is not the same as finding the end of the image.
    """
    i = start
    n = len(data)
    while i + 1 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        following = data[i + 1]
        if following == 0xFF:
            i += 1
            continue
        if following == 0x00 or 0xD0 <= following <= 0xD7:
            i += 2
            continue
        return i
    return None


def _jpeg_end(data: bytes) -> int | None:
    """Offset just past the JPEG's own EOI marker, or None if the segment
    structure is not one this can walk.

    Segments are skipped by their declared length, which is what keeps a whole
    nested JPEG - an EXIF thumbnail, a Photoshop preview - from being mistaken
    for the end of the file. Searching for the first 0xFFD9 would stop inside
    that thumbnail and report clean files dirty.
    """
    n = len(data)
    i = 2
    while i + 1 < n:
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        i += 2
        if marker == 0xD9:
            return i
        if marker in _JPEG_STANDALONE:
            continue
        if i + 2 > n:
            return None
        length = int.from_bytes(data[i : i + 2], "big")
        if length < 2:
            return None
        i += length
        if marker == 0xDA:
            end = _jpeg_scan_end(data, i)
            if end is None:
                return None
            i = end
    return None


def _png_end(data: bytes) -> int | None:
    """Offset just past the PNG's IEND chunk, or None if the chunk structure is
    not one this can walk."""
    n = len(data)
    i = len(_PNG_SIGNATURE)
    while i + 8 <= n:
        length = int.from_bytes(data[i : i + 4], "big")
        kind = data[i + 4 : i + 8]
        i += 12 + length  # length, type, payload, CRC
        if i > n:
            return None
        if kind == b"IEND":
            return i
    return None


def appended_payload(path: Path) -> str | None:
    """Name of the container glued on after the image's end marker, or None.

    Nothing that decodes the image can see this. A decoder stops at EOI or at
    IEND, so a Motion Photo reports no EXIF, no XMP, no comment and prints its
    coordinates to `strings`. The end marker therefore has to be walked to
    rather than searched for.

    None also comes back for a format this cannot walk, which is not a promise
    that the file is clean - it is the absence of an answer. Those formats are
    refused by suffix instead, see UNSTRIPPABLE_SUFFIXES.
    """
    data = path.read_bytes()
    if data.startswith(b"\xff\xd8"):
        end, name = _jpeg_end(data), "data appended after the JPEG EOI marker"
    elif data.startswith(_PNG_SIGNATURE):
        end, name = _png_end(data), "data appended after the PNG IEND chunk"
    else:
        return None
    if end is None or end >= len(data):
        return None
    return name


def remaining_metadata(path: Path) -> list[str]:
    """Names of the metadata containers this image still carries.

    An empty list means the file is pixels and nothing else, which is what a
    re-encode with nothing passed to the encoder produces. That sentence was
    false for as long as this only asked Pillow: everything past the image's
    end marker was invisible, and that is where a phone puts the video half of
    a Motion Photo. See the module docstring for why this reports containers
    rather than coordinates.

    The JFIF density block every JPEG carries is deliberately not counted. It
    describes the encoding, not the photograph, and a check that flagged it
    would cry wolf on every file this tool itself wrote.
    """
    from PIL import Image

    found: list[str] = []
    trailing = appended_payload(path)
    with Image.open(path) as image:
        info: dict[str, Any] = dict(image.info)
        # PNG keeps its tEXt/iTXt/zTXt chunks here as well as in info, and an
        # XMP packet in a PNG arrives as an iTXt chunk rather than an info key.
        text: dict[str, Any] = dict(getattr(image, "text", None) or {})

        if info.get("exif") or dict(image.getexif()):
            found.append("EXIF")
        if any("xmp" in str(key).lower() for key in (*info, *text)):
            found.append("XMP")
        # Pillow surfaces a JPEG's APP13 Photoshop resource block - which is
        # where IPTC location fields live - under this key.
        if info.get("photoshop") or info.get("iptc"):
            found.append("IPTC")
        if info.get("comment"):
            found.append("JPEG comment")
        if text:
            found.append("PNG text chunk")
    if trailing is not None:
        found.append(trailing)
    return found


# --------------------------------------------------------------------------- #
# time-based media: ISO-BMFF boxes, RIFF chunks, and the coded stream itself    #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Box:
    """One ISO-BMFF box: where its header starts, where its payload starts, and
    where the next sibling begins."""

    kind: bytes
    start: int
    body: int
    end: int


#: Boxes whose payload is nothing but more boxes, starting immediately.
_MP4_CONTAINERS = frozenset(
    {
        b"moov",
        b"trak",
        b"mdia",
        b"minf",
        b"stbl",
        b"edts",
        b"dinf",
        b"udta",
        b"mvex",
        b"moof",
        b"traf",
        b"mfra",
        b"ilst",
    }
)

#: Sample entry types this can find a length-prefixed AVC stream behind. Any
#: other coded format in a video track is reported as unwalkable rather than
#: waved through - see `_track_sei_violations`.
_AVC_SAMPLE_ENTRIES = frozenset({b"avc1", b"avc3"})

#: The UUID Adobe stamps on an XMP packet carried in an mp4 `uuid` box.
_XMP_UUID = bytes.fromhex("be7acfcb97a942e89c71999491e3afac")


def _is_box_type(raw: bytes) -> bool:
    """Whether these four bytes look like a box type rather than a length.

    Used only to tell the two shapes of `meta` apart. Guessing wrong turns a
    perfectly legal file into a MalformedMedia refusal, which is the cry-wolf
    direction, so the question is asked of the bytes instead of assumed.
    """
    return len(raw) == 4 and all(0x20 <= byte <= 0x7E for byte in raw)


def _printable(raw: bytes) -> str:
    """A short, quoted rendering of a field, for an error message a person has
    to act on. "still carries metadata" is not actionable; "Lavc60.31.102
    libx264" tells the reader exactly which tool put it there."""
    text = raw.decode("utf-8", "replace").strip("\x00").strip()
    return text[:70] if text else repr(bytes(raw[:16]))


def _iter_boxes(data: bytes, start: int, end: int, where: str) -> tuple[list[_Box], int]:
    """The boxes laid end to end between these two offsets, and how many bytes
    were left over at the end.

    Leftovers are returned rather than raised on, because the caller decides
    what they mean: after the last top-level box they are appended payload - the
    Motion Photo trick, one container up - while inside a parent box they are a
    structure this did not understand. Raising here would collapse the two.

    Everything else about a box that does not fit is a refusal. A declared size
    that runs past the parent, or that is smaller than the header it sits in,
    means the walk cannot be trusted to have visited every box, and a walk that
    may have missed boxes must not be allowed to report "no metadata found".
    """
    boxes: list[_Box] = []
    pos = start
    while end - pos >= 8:
        size = int.from_bytes(data[pos : pos + 4], "big")
        kind = data[pos + 4 : pos + 8]
        header = 8
        if size == 1:
            # size==1 means the real size is a 64-bit largesize after the type.
            if end - pos < 16:
                raise MalformedMedia(
                    f"{where}: the {_printable(kind)} box at offset {pos} claims a "
                    f"64-bit size and there is no room for one."
                )
            size = int.from_bytes(data[pos + 8 : pos + 16], "big")
            header = 16
        elif size == 0:
            # size==0 means "to the end of the enclosing extent", which at the
            # top level is the end of the file.
            size = end - pos
        if size < header or pos + size > end:
            raise MalformedMedia(
                f"{where}: the {_printable(kind)} box at offset {pos} declares "
                f"{size} bytes and only {end - pos} remain. Unreadable is not clean."
            )
        boxes.append(_Box(kind=kind, start=pos, body=pos + header, end=pos + size))
        pos += size
    return boxes, end - pos


def _child_boxes(data: bytes, box: _Box) -> list[_Box]:
    """The boxes nested inside this one, or [] if this box holds fields rather
    than boxes.

    `meta` and `stsd` both put a few bytes of their own in front of their
    children, which is the sort of detail that is easy to get wrong in the
    direction of silently walking off the end of the real children and finding
    nothing.
    """
    if box.kind in _MP4_CONTAINERS:
        start = box.body
    elif box.kind == b"meta":
        # ISO-BMFF makes `meta` a FullBox - four bytes of version and flags
        # before the children - and QuickTime does not. Look for a box type in
        # both places instead of picking one and refusing every file that
        # disagrees.
        start = box.body if _is_box_type(data[box.body + 4 : box.body + 8]) else box.body + 4
    elif box.kind == b"stsd":
        # version and flags, then entry_count, then the sample entries.
        start = box.body + 8
    else:
        return []
    children, leftover = _iter_boxes(
        data, min(start, box.end), box.end, f"inside {_printable(box.kind)}"
    )
    if leftover:
        raise MalformedMedia(
            f"the {_printable(box.kind)} box at offset {box.start} ends with "
            f"{leftover} byte(s) that are not a box. Unreadable is not clean."
        )
    return children


def _find(data: bytes, boxes: list[_Box], path: tuple[bytes, ...]) -> _Box | None:
    """The first box reachable by following this chain of types down."""
    current = boxes
    found: _Box | None = None
    for kind in path:
        found = next((box for box in current if box.kind == kind), None)
        if found is None:
            return None
        current = _child_boxes(data, found)
    return found


def _track_handler(data: bytes, trak: _Box) -> bytes | None:
    """The four-character handler type of this track - `vide`, `soun`, or
    nothing if the track never says."""
    hdlr = _find(data, _child_boxes(data, trak), (b"mdia", b"hdlr"))
    if hdlr is None or hdlr.end - hdlr.body < 12:
        return None
    return data[hdlr.body + 8 : hdlr.body + 12]


def _visual_sample_entry_violations(data: bytes, stsd: _Box) -> list[str]:
    """The encoder banner ffmpeg writes into every sample entry it produces.

    compressorname is a fixed 32-byte field 42 bytes into a VisualSampleEntry -
    a length byte then the text - and it is not metadata anybody chose to add,
    which is exactly why it survives. It named the library and version that
    encoded this repository's fixture clip in a file the README described as
    carrying nothing.
    """
    found: list[str] = []
    for entry in _child_boxes(data, stsd):
        if entry.end - entry.body < 78:
            raise MalformedMedia(
                f"the {_printable(entry.kind)} sample entry at offset {entry.start} "
                f"is shorter than a VisualSampleEntry. Unreadable is not clean."
            )
        field_bytes = data[entry.body + 42 : entry.body + 74]
        if any(field_bytes):
            length = min(field_bytes[0], 31)
            found.append(f"an mp4 compressorname ({_printable(field_bytes[1 : 1 + length])})")
    return found


def _stsz_sizes(data: bytes, stbl: list[_Box]) -> list[int]:
    stsz = next((box for box in stbl if box.kind == b"stsz"), None)
    if stsz is None or stsz.end - stsz.body < 12:
        raise MalformedMedia("a video track with no readable stsz sample size table.")
    uniform = int.from_bytes(data[stsz.body + 4 : stsz.body + 8], "big")
    count = int.from_bytes(data[stsz.body + 8 : stsz.body + 12], "big")
    if uniform:
        return [uniform] * count
    table = stsz.body + 12
    if table + 4 * count > stsz.end:
        raise MalformedMedia(
            f"the stsz box at offset {stsz.start} promises {count} sample sizes "
            f"and does not hold them. Unreadable is not clean."
        )
    return [
        int.from_bytes(data[table + 4 * i : table + 4 * i + 4], "big") for i in range(count)
    ]


def _chunk_offsets(data: bytes, stbl: list[_Box]) -> list[int]:
    for box in stbl:
        if box.kind not in (b"stco", b"co64"):
            continue
        width = 4 if box.kind == b"stco" else 8
        count = int.from_bytes(data[box.body + 4 : box.body + 8], "big")
        table = box.body + 8
        if table + width * count > box.end:
            raise MalformedMedia(
                f"the {_printable(box.kind)} box at offset {box.start} promises "
                f"{count} chunk offsets and does not hold them."
            )
        return [
            int.from_bytes(data[table + width * i : table + width * i + width], "big")
            for i in range(count)
        ]
    raise MalformedMedia("a video track with no stco or co64 chunk offset table.")


def _sample_offsets(data: bytes, stbl: list[_Box], sizes: list[int]) -> list[int]:
    """Where each coded sample actually starts in the file.

    stsc stores runs rather than one entry per chunk, so this has to expand
    them. Getting it wrong does not throw - it silently reads the wrong bytes
    and reports a clean stream, which is the failure mode that matters here.
    """
    stsc = next((box for box in stbl if box.kind == b"stsc"), None)
    chunks = _chunk_offsets(data, stbl)
    if stsc is None or stsc.end - stsc.body < 8:
        raise MalformedMedia("a video track with no readable stsc chunk map.")
    entry_count = int.from_bytes(data[stsc.body + 4 : stsc.body + 8], "big")
    table = stsc.body + 8
    if table + 12 * entry_count > stsc.end:
        raise MalformedMedia(
            f"the stsc box at offset {stsc.start} promises {entry_count} entries "
            f"and does not hold them."
        )
    runs = [
        (
            int.from_bytes(data[table + 12 * i : table + 12 * i + 4], "big"),
            int.from_bytes(data[table + 12 * i + 4 : table + 12 * i + 8], "big"),
        )
        for i in range(entry_count)
    ]

    offsets: list[int] = []
    sample = 0
    for index, (first_chunk, per_chunk) in enumerate(runs):
        if first_chunk < 1 or per_chunk < 1:
            raise MalformedMedia(
                f"the stsc box at offset {stsc.start} describes a run starting at "
                f"chunk {first_chunk} with {per_chunk} sample(s) in it."
            )
        last_chunk = runs[index + 1][0] - 1 if index + 1 < len(runs) else len(chunks)
        for chunk in range(first_chunk, min(last_chunk, len(chunks)) + 1):
            position = chunks[chunk - 1]
            for _ in range(per_chunk):
                if sample >= len(sizes):
                    return offsets
                offsets.append(position)
                position += sizes[sample]
                sample += 1
    return offsets


def _first_sei_user_data(nal: bytes) -> bytes | None:
    """The payload of this NAL's first SEI message, if that message is
    user_data_unregistered.

    payloadType and payloadSize are both written as a run of 0xFF bytes plus a
    final byte, so a naive read of one byte finds type 255 on anything real.
    Only the first message is inspected, which is where an encoder puts its
    build string and is all this claims to look at.
    """
    position = 1  # past the one-byte NAL header
    payload_type = 0
    while position < len(nal) and nal[position] == 0xFF:
        payload_type += 255
        position += 1
    if position >= len(nal):
        return None
    payload_type += nal[position]
    position += 1
    if payload_type != 5:  # user_data_unregistered
        return None
    payload_size = 0
    while position < len(nal) and nal[position] == 0xFF:
        payload_size += 255
        position += 1
    if position >= len(nal):
        return None
    payload_size += nal[position]
    position += 1
    # A type 5 payload opens with a 16-byte uuid_iso_iec_11578 nobody wants to
    # read; the human-readable half is whatever follows it.
    return nal[position + 16 : position + payload_size]


def _track_sei_violations(data: bytes, trak: _Box) -> list[str]:
    """User-data SEI messages hiding in this track's coded stream.

    x264 writes its whole command line - every option, every build number -
    into one of these on the first frame, and no container reader will ever
    show it to you. `strings` will.

    The temptation is to search mdat for a byte pattern. That fires on
    compressed data by coincidence, and a check that cries wolf is a check
    people learn to skip, so this walks the sample tables properly: avcC gives
    the NAL length prefix width, stsz the sample sizes, stsc and stco where the
    samples sit.

    A video track whose samples are not AVC is reported as unwalkable, not
    skipped. Silently skipping the thing you could not read is the exact defect
    this repository has now found in itself seven times.
    """
    stbl_box = _find(data, _child_boxes(data, trak), (b"mdia", b"minf", b"stbl"))
    handler = _track_handler(data, trak)
    if stbl_box is None:
        if handler == b"vide":
            return ["a video track with no sample table, so nothing has read its stream"]
        return []
    stbl = _child_boxes(data, stbl_box)
    stsd = next((box for box in stbl if box.kind == b"stsd"), None)
    entries = _child_boxes(data, stsd) if stsd is not None else []
    avc = next((box for box in entries if box.kind in _AVC_SAMPLE_ENTRIES), None)
    if avc is None:
        if handler == b"vide" or handler is None:
            kinds = ", ".join(_printable(box.kind) for box in entries) or "none at all"
            return [
                f"a video track this cannot walk: its sample entries are {kinds}, "
                f"not AVC, so nothing here has looked at its coded stream for a "
                f"user-data SEI"
            ]
        # A sound or text track has no coded video in it. That is a reason by
        # construction, not an omission, and it is written down here so the next
        # reader does not have to guess which of the two it was.
        return []

    avcc = next(
        (box for box in _sub_boxes_of_sample_entry(data, avc) if box.kind == b"avcC"), None
    )
    if avcc is None or avcc.end - avcc.body < 5:
        raise MalformedMedia(
            f"the {_printable(avc.kind)} sample entry at offset {avc.start} carries "
            f"no readable avcC, so the NAL length prefix width is unknown."
        )
    nal_length = (data[avcc.body + 4] & 0x03) + 1

    sizes = _stsz_sizes(data, stbl)
    offsets = _sample_offsets(data, stbl, sizes)
    found: list[str] = []
    for offset, size in zip(offsets, sizes, strict=False):
        if offset + size > len(data):
            raise MalformedMedia(
                f"a sample at offset {offset} runs {offset + size - len(data)} "
                f"byte(s) past the end of the file. Unreadable is not clean."
            )
        sample = data[offset : offset + size]
        position = 0
        while position + nal_length <= len(sample):
            length = int.from_bytes(sample[position : position + nal_length], "big")
            position += nal_length
            if length == 0 or position + length > len(sample):
                raise MalformedMedia(
                    f"a NAL in the sample at offset {offset} declares {length} "
                    f"byte(s) and the sample does not hold them."
                )
            nal = sample[position : position + length]
            position += length
            if nal[0] & 0x1F != 6:  # not SEI
                continue
            payload = _first_sei_user_data(nal)
            if payload is not None:
                found.append(f"a user-data SEI in the coded stream ({_printable(payload)})")
                return found
    return found


def _sub_boxes_of_sample_entry(data: bytes, entry: _Box) -> list[_Box]:
    """The extension boxes after a VisualSampleEntry's 78 fixed bytes."""
    if entry.end - entry.body < 78:
        raise MalformedMedia(
            f"the {_printable(entry.kind)} sample entry at offset {entry.start} is "
            f"shorter than a VisualSampleEntry. Unreadable is not clean."
        )
    boxes, _ = _iter_boxes(data, entry.body + 78, entry.end, "inside a sample entry")
    return boxes


#: Header boxes carrying a creation and a modification time. All three are
#: structurally required, so unlike `udta` they cannot be removed - only zeroed.
_TIMED_HEADER_BOXES = frozenset({b"mvhd", b"tkhd", b"mdhd"})


def _header_timestamp_violations(data: bytes, box: _Box) -> list[str]:
    """`creation_time` and `modification_time`, which say when the car was filmed.

    This is the one check here that reads a value rather than asserting a
    container is absent, and it is deliberate. The usual argument for containers
    (D-067) is that a reader cannot see reliably inside every one of them - and
    that argument does not apply to a fixed-width field at a known offset in a
    box the walker has already located and length-checked.

    It matters because the fields are seconds since 1904 UTC of the moment the
    recording was made. Combined with a seller's listing that is a strong
    identifier, and a walkaround video shot at the viewing tells you when the
    buyer was standing in the seller's driveway.

    The committed fixture clip has zeroes in all three, but only because ffmpeg
    was asked for `-fflags +bitexact`. Nothing checked, so the fixture was clean
    by an accident of one encoder flag - which is exactly the shape of a test
    that passes for a reason unrelated to the thing it is presented as guarding.
    """
    version = data[box.body]
    width = 8 if version == 1 else 4
    stop = box.body + 4 + 2 * width
    if stop > box.end:
        raise MalformedMedia(
            f"the {_printable(box.kind)} box at offset {box.start} is too short "
            f"to hold the version {version} times it declares. Unreadable is not clean."
        )
    created = int.from_bytes(data[box.body + 4 : box.body + 4 + width], "big")
    modified = int.from_bytes(data[box.body + 4 + width : stop], "big")
    if not created and not modified:
        return []
    return [
        f"an mp4 {_printable(box.kind)} timestamp "
        f"(creation={created}, modification={modified})"
    ]


def _walk_mp4(data: bytes, boxes: list[_Box], found: list[str], handler: bytes | None) -> None:
    for box in boxes:
        kind = box.kind
        if kind == b"udta":
            found.append("an mp4 udta box")
        elif kind == b"meta":
            found.append("an mp4 meta box")
        elif kind == b"ilst":
            found.append("an mp4 ilst tag list")
        elif kind == b"loci":
            found.append("an mp4 loci location box")
        elif kind[:1] == b"\xa9":
            # 0xA9 is the copyright sign that prefixes every QuickTime tag
            # atom. (c)xyz is the one that holds the position the phone was
            # standing in when it recorded.
            found.append(f"the mp4 tag atom {kind.decode('latin-1')}")
        elif kind == b"uuid" and data[box.body : box.body + 16] == _XMP_UUID:
            found.append("an XMP packet in an mp4 uuid box")
        elif kind in (b"free", b"skip") and any(data[box.body : box.end]):
            # A `free` box is meant to be padding, so nothing reads it and
            # nothing complains about what is inside it. That makes it a good
            # place to leave something and a bad thing to trust.
            found.append(
                f"a non-empty mp4 {_printable(kind)} box at offset {box.start} "
                f"({_printable(data[box.body : box.body + 32])})"
            )
        elif kind == b"hdlr":
            if box.end - box.body < 24:
                raise MalformedMedia(
                    f"the hdlr box at offset {box.start} is too short to hold a "
                    f"handler type. Unreadable is not clean."
                )
            name = data[box.body + 24 : box.end]
            if name.strip(b"\x00 "):
                found.append(f"an mp4 hdlr name ({_printable(name)})")
        elif kind in _TIMED_HEADER_BOXES:
            found.extend(_header_timestamp_violations(data, box))

        if kind == b"trak":
            handler = _track_handler(data, box)
        if kind == b"stsd" and handler == b"vide":
            found.extend(_visual_sample_entry_violations(data, box))
        _walk_mp4(data, _child_boxes(data, box), found, handler)


def mp4_metadata(path: Path) -> list[str]:
    """Everything an ISO base media file is carrying that is not picture or
    sound.

    Containers again, not coordinates, for the same reason the still-image
    check works that way - except that here there is one thing worth reading
    out loud, because the string in a compressorname or an SEI names the tool
    that put it there and tells the reader what to do about it.
    """
    data = path.read_bytes()
    top, leftover = _iter_boxes(data, 0, len(data), "mp4")
    if not any(box.kind == b"moov" for box in top):
        raise MalformedMedia(
            f"{path.name} has no top-level moov box, so there is no sample table "
            f"to walk and nothing here can say what is in it."
        )
    found: list[str] = []
    if leftover:
        # The Motion Photo trick, one container up: a payload glued past the
        # last box, invisible to every player because a player stops at moov.
        found.append(f"{leftover} byte(s) appended after the last top-level box")
    _walk_mp4(data, top, found, None)
    moov = next(box for box in top if box.kind == b"moov")
    for trak in _child_boxes(data, moov):
        if trak.kind == b"trak":
            found.extend(_track_sei_violations(data, trak))
    return found


#: RIFF chunks a WAVE file needs in order to be a WAVE file. Flagging these
#: would make the check fire on every recording ever made, and a check that
#: fires on everything is one nobody reads.
_WAV_STRUCTURAL = frozenset({b"fmt ", b"data", b"fact"})

#: Chunks worth naming individually, because the reader should know which tool
#: to blame. Everything else unrecognised is still refused, just less
#: specifically.
_WAV_KNOWN_CARRIERS = {
    b"LIST": "a RIFF LIST/INFO block",
    b"INFO": "a RIFF INFO block",
    b"id3 ": "an ID3 tag",
    b"ID3 ": "an ID3 tag",
    b"bext": "a broadcast-wave bext chunk, which holds an origination date and time",
    b"iXML": "an iXML chunk",
    b"_PMX": "an XMP packet in a _PMX chunk",
}


def wav_metadata(path: Path) -> list[str]:
    """Every chunk in this WAVE file that is not the sound or the shape of it.

    A .wav looks inert and is not. Recorders write the take, the date and the
    machine into a bext chunk; editors write a LIST/INFO block; anything that
    has been through a tagger carries ID3. None of it is audible and all of it
    ships.
    """
    data = path.read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise MalformedMedia(
            f"{path.name} does not begin with a RIFF/WAVE header, so nothing here "
            f"can walk it. Unreadable is not clean."
        )
    declared = int.from_bytes(data[4:8], "little") + 8
    found: list[str] = []
    if declared > len(data):
        raise MalformedMedia(
            f"{path.name} declares {declared} bytes and holds {len(data)}. "
            f"Unreadable is not clean."
        )
    if declared < len(data):
        found.append(f"{len(data) - declared} byte(s) appended after the RIFF chunk")

    position = 12
    while position + 8 <= declared:
        kind = data[position : position + 4]
        size = int.from_bytes(data[position + 4 : position + 8], "little")
        # Chunks are padded to an even length and the pad byte is not counted
        # in the size. Forgetting it walks the rest of the file misaligned and
        # reports garbage chunk names on a perfectly clean recording.
        advance = 8 + size + (size & 1)
        if position + 8 + size > declared:
            raise MalformedMedia(
                f"{path.name}: the {_printable(kind)} chunk at offset {position} "
                f"declares {size} bytes and the file does not hold them."
            )
        if kind not in _WAV_STRUCTURAL:
            found.append(
                _WAV_KNOWN_CARRIERS.get(kind, f"an unrecognised RIFF chunk {_printable(kind)}")
            )
        position += advance
    if position != declared:
        raise MalformedMedia(
            f"{path.name}: the chunk list ends {declared - position} byte(s) short "
            f"of the length the RIFF header declares."
        )
    return found


def time_based_metadata(path: Path) -> list[str]:
    """Names of everything this video or audio file carries besides the
    recording.

    An empty list is the same promise `remaining_metadata` makes about a still:
    something walked the whole container and found nothing in it. It is not
    "the walker gave up", which raises.
    """
    suffix = path.suffix.lower()
    if suffix == ".wav":
        return wav_metadata(path)
    if suffix in READABLE_MEDIA_SUFFIXES:
        return mp4_metadata(path)
    raise MalformedMedia(
        f"{path.name}: nothing in this file knows how to read a {suffix} container."
    )


def _mp4_scrub_edits(data: bytes) -> list[tuple[int, bytes]]:
    """Byte-for-byte overwrites that empty an mp4's metadata fields, as
    (offset, replacement) pairs.

    THE WHOLE POINT IS THAT NOTHING IS EVER REMOVED. `stco` and `co64` hold
    absolute file offsets to the media chunks, so deleting a box shifts
    everything after it and silently repoints every chunk pointer into the
    middle of a frame - a file that still opens, still reports the right
    duration, and decodes garbage. A `udta` box is therefore retyped to `free`,
    the standard skip box, and its payload zeroed while its size is left
    exactly as it was. Same size, same offsets, no rewrite of the tables, safe
    for any layout including the one where moov comes first.
    """
    edits: list[tuple[int, bytes]] = []

    def visit(boxes: list[_Box], handler: bytes | None) -> None:
        for box in boxes:
            if box.kind == b"udta":
                edits.append((box.start + 4, b"free"))
                edits.append((box.body, bytes(box.end - box.body)))
                continue  # its children are inside the payload just zeroed
            if box.kind == b"hdlr" and box.end - box.body > 24:
                edits.append((box.body + 24, bytes(box.end - box.body - 24)))
            if box.kind in _TIMED_HEADER_BOXES:
                # Zeroed, not removed: these three boxes are structurally
                # required and the fields are fixed-width, so the timestamps go
                # and every offset in the file stays exactly where it was.
                width = 8 if data[box.body] == 1 else 4
                if box.body + 4 + 2 * width <= box.end:
                    edits.append((box.body + 4, bytes(2 * width)))
            if box.kind == b"trak":
                handler = _track_handler(data, box)
            if box.kind == b"stsd" and handler == b"vide":
                for entry in _child_boxes(data, box):
                    if entry.end - entry.body >= 78:
                        edits.append((entry.body + 42, bytes(32)))
            visit(_child_boxes(data, box), handler)

    top, _ = _iter_boxes(data, 0, len(data), "mp4")
    visit(top, None)
    return edits


def strip_time_based_media(source: Path, destination: Path) -> None:
    """Rewrite this video or audio file with nothing in it but the recording.

    Two steps for an mp4, because no single tool does both. ffmpeg drops the
    container metadata and filters the user-data SEI out of the coded stream
    without re-encoding a frame - `-c copy` with a bitstream filter, so the
    picture is bit-identical and nothing is lost to a second generation of
    compression. What ffmpeg will not give up is its own signature: it writes a
    fresh compressorname and a fresh hdlr name into whatever it produces, and
    there is no flag for that. So the second step overwrites those fields in
    place, in this file, by hand.

    Refuses when ffmpeg is absent instead of returning quietly. A strip that
    silently did nothing would leave the file exactly as dirty as it was and
    let `apply` print that it had been cleaned.
    """
    suffix = source.suffix.lower()
    if suffix == ".wav":
        _strip_wav(source, destination)
        return
    if suffix not in READABLE_MEDIA_SUFFIXES:
        raise RedactionError(
            f"{source.name}: nothing here can rewrite a {suffix} file, so it "
            f"cannot be cleared. Convert it to mp4 or wav first."
        )
    if shutil.which("ffmpeg") is None:
        raise RedactionError(
            f"{source.name}: ffmpeg is not installed, and it is the only thing "
            f"here that can drop an mp4's metadata and filter the user-data SEI "
            f"out of the coded stream. Refusing rather than reporting a file "
            f"cleaned that nothing touched."
        )
    with tempfile.TemporaryDirectory() as work:
        staged = Path(work) / f"staged{suffix}"
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(source),
                "-c",
                "copy",
                # Type 6 is SEI. This is what removes x264's build line, and it
                # happens at the bitstream level so no frame is re-encoded.
                "-bsf:v",
                "filter_units=remove_types=6",
                "-map_metadata",
                "-1",
                "-map_chapters",
                "-1",
                # Without these, ffmpeg stamps its own version into the output
                # it was just asked to strip.
                "-fflags",
                "+bitexact",
                "-flags:v",
                "+bitexact",
                str(staged),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not staged.is_file():
            raise RedactionError(
                f"{source.name}: ffmpeg could not rewrite it ({result.stderr.strip()})."
            )
        data = bytearray(staged.read_bytes())

    for offset, replacement in _mp4_scrub_edits(bytes(data)):
        data[offset : offset + len(replacement)] = replacement
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(bytes(data))


def _strip_wav(source: Path, destination: Path) -> None:
    """Rebuild a WAVE file out of its structural chunks and nothing else.

    Pure Python and no ffmpeg, because there is nothing here that needs
    decoding: the samples are already the samples. Dropping a chunk is safe in
    RIFF in a way it is never safe in mp4 - a WAVE file holds no absolute
    offsets into itself, so nothing points at anything that moves.
    """
    data = source.read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise MalformedMedia(
            f"{source.name} does not begin with a RIFF/WAVE header, so this cannot "
            f"rebuild it without guessing at what the samples are."
        )
    declared = min(int.from_bytes(data[4:8], "little") + 8, len(data))
    kept: list[bytes] = []
    position = 12
    while position + 8 <= declared:
        kind = data[position : position + 4]
        size = int.from_bytes(data[position + 4 : position + 8], "little")
        if position + 8 + size > declared:
            raise MalformedMedia(
                f"{source.name}: the {_printable(kind)} chunk at offset {position} "
                f"declares more bytes than the file holds."
            )
        if kind in _WAV_STRUCTURAL:
            kept.append(data[position : position + 8 + size + (size & 1)])
        position += 8 + size + (size & 1)
    body = b"WAVE" + b"".join(kept)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"RIFF" + len(body).to_bytes(4, "little") + body)


def _unreadable_media_problem(directory: Path, path: Path) -> str | None:
    """The refusal line for a video or audio file no walker here understands.

    The same answer .heic gets, and for the same reason. A .webm that is
    quietly skipped is never walked, never stripped and never listed, while
    `check` prints a green line about the directory it is sitting in.
    """
    if path.suffix.lower() in READABLE_MEDIA_SUFFIXES:
        return None
    return (
        f"{asset_key(directory, path)}: nothing here can walk a {path.suffix} "
        f"container, so it can promise nothing about what is inside this one. "
        f"Convert it to mp4 or wav, then re-run."
    )


def assert_media_formats_readable(directory: Path, media_paths: list[Path]) -> None:
    """Refuse before anything is rewritten, not after.

    `assert_formats_strippable` learned this the expensive way: a refusal that
    runs at the end of the loop means "irreversibly rewrite everything I can,
    then report failure".
    """
    problems = [
        problem
        for problem in (
            _unreadable_media_problem(directory, path) for path in sorted(media_paths)
        )
        if problem is not None
    ]
    if problems:
        raise RedactionError(
            "Video or audio is in a format nothing here can walk (D-022):\n  - "
            + "\n  - ".join(problems)
        )


def assert_time_based_metadata_stripped(directory: Path, media_paths: list[Path]) -> None:
    """Refuse to proceed while any video or audio file still carries anything
    but the recording.

    The still-image half of this had a matching function for four phases while
    the video half had a printed apology. A clip carries the position it was
    shot in, the encoder that made it, and - in the coded stream, where no
    container reader looks - the whole x264 command line.
    """
    problems: list[str] = []
    for path in sorted(media_paths):
        key = asset_key(directory, path)
        refusal = _unreadable_media_problem(directory, path)
        if refusal is not None:
            problems.append(refusal)
            continue
        try:
            found = time_based_metadata(path)
        except MalformedMedia as exc:
            # A container that could not be walked is not a clean container.
            problems.append(f"{key}: could not be walked to the end. {exc}")
            continue
        except OSError as exc:
            problems.append(f"{key}: could not be opened to check it ({exc}).")
            continue
        if found:
            problems.append(
                f"{key}: still carries {', '.join(found)}. Run 'apply' - the "
                f"remux and the field overwrite are the only things that remove it."
            )
    if problems:
        raise RedactionError(
            "Video and audio still carry metadata (D-022):\n  - " + "\n  - ".join(problems)
        )


def _unstrippable_problem(directory: Path, path: Path) -> str | None:
    """The refusal line for a file this tool cannot open and re-encode, or None
    if it can.

    Pulled out so `apply` can ask it *before* it starts re-encoding. The
    refusal used to run after the loop, which made "apply refuses rather than
    reporting success" mean "apply irreversibly rewrites every file it can, and
    then reports failure".
    """
    if path.suffix.lower() in STRIPPABLE_SUFFIXES:
        return None
    return (
        f"{asset_key(directory, path)}: this tool cannot open or re-encode "
        f"{path.suffix} files, so it can promise nothing about what is inside "
        f"this one. Convert it to JPEG or PNG, then review the result."
    )


def assert_formats_strippable(directory: Path, image_paths: list[Path]) -> None:
    """Refuse before anything is touched, not after."""
    problems = [
        problem
        for problem in (_unstrippable_problem(directory, path) for path in sorted(image_paths))
        if problem is not None
    ]
    if problems:
        raise RedactionError(
            "Media is in a format this tool cannot clear (D-022):\n  - "
            + "\n  - ".join(problems)
        )


def assert_metadata_stripped(directory: Path, image_paths: list[Path]) -> None:
    """Refuse to proceed while any image still carries a metadata container.

    `assert_reviewed` asks whether a person looked at the pixels. This asks
    whether anything ever looked at the bytes around them, and until it existed
    the answer was no: nothing between `init` and the commit opened the file, so
    a directory of honestly signed "nothing to redact" records passed `check`
    with the seller's coordinates in every one of them.

    Fails on the unreadable as well as the dirty. A format this tool cannot open
    is not a format it can clear.
    """
    problems: list[str] = []
    for path in sorted(image_paths):
        refusal = _unstrippable_problem(directory, path)
        if refusal is not None:
            problems.append(refusal)
            continue
        key = asset_key(directory, path)
        try:
            containers = remaining_metadata(path)
        except OSError as exc:
            # Unreadable is not clean. UnidentifiedImageError lands here too.
            problems.append(f"{key}: could not be opened to check it ({exc}).")
            continue
        if containers:
            problems.append(
                f"{key}: still carries {', '.join(containers)}. Run 'apply' - "
                f"the re-encode is the only thing that removes it."
            )
    if problems:
        raise RedactionError(
            "Media still carries metadata (D-022):\n  - " + "\n  - ".join(problems)
        )


def assert_reviewed(
    directory: Path, image_paths: list[Path], records: dict[str, AssetRedaction]
) -> None:
    """Refuse to proceed unless every image has been signed off by a person.

    Fails on absence. An image with no record is unreviewed, which is not the same
    as an image with nothing to redact, and conflating the two is exactly how an
    unblurred plate reaches a public repository.
    """
    problems: list[str] = []
    for path in sorted(image_paths):
        key = asset_key(directory, path)
        record = records.get(key)
        if record is None:
            problems.append(
                f"{key}: no redaction record. Every image and every document "
                f"needs one, even if the answer is that there is nothing to "
                f"redact."
            )
            continue
        if not record.reviewed_by:
            problems.append(f"{key}: no reviewer name against it.")
        elif not record.reviewed:
            problems.append(
                f"{key}: reviewed by {record.reviewed_by} but neither regions "
                f"nor an explicit nothing_to_redact. Which is it?"
            )
    if problems:
        raise RedactionError(
            "Media is not cleared for commit (D-022):\n  - " + "\n  - ".join(problems)
        )
