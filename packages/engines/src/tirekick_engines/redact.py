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

What this file still does not read is video and audio. An .mp4 holds a position
in its (c)xyz atom and a .wav can carry a LIST/INFO block, and nothing here
opens either. That is a stated gap, not a covered one: `check` names the files
it did not examine rather than letting its success line imply it did.

The orientation tag is the one piece of EXIF that has to survive long enough to
be used: `redact_file` transposes the pixels to match it, and only then drops it
with the rest.
"""

from __future__ import annotations

import json
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

#: Files `check` walks past without opening. Named so the tool can say so out
#: loud: an .mp4 carries a position in its (c)xyz atom and a .wav can carry a
#: LIST/INFO block, and nothing here reads either. Listing them is not the same
#: as checking them, and the success line says which of the two happened.
UNEXAMINED_MEDIA_SUFFIXES = frozenset(
    {
        ".mp4",
        ".mov",
        ".m4v",
        ".avi",
        ".mkv",
        ".webm",
        ".wav",
        ".mp3",
        ".m4a",
        ".aac",
        ".flac",
        ".ogg",
    }
)


class RedactionError(RuntimeError):
    """Redaction is missing, unreviewed, or malformed."""


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
                f"{key}: no redaction record. Every image needs one, even if "
                f"the answer is that there is nothing to redact."
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
