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
            "a default."
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
    # Re-encode rather than copy: the original EXIF carries GPS coordinates of
    # wherever the photograph was taken, which is somebody's driveway. The
    # orientation tag is discarded with the rest, which is safe precisely
    # because the pixels above were already transposed to match it.
    if destination.suffix.lower() == ".png":
        result.save(destination, format="PNG")
    else:
        result.save(destination, format="JPEG", quality=92)


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
