"""What a buyer gives us, and how it is loaded from disk.

LAW 3: everything here is user-provided. There is no code path that acquires media
or listings on its own.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field

from .models import Asset, Comp, ViewClass


class AssetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: str
    file: str = Field(min_length=1)
    #: Optional operator hint. The vision classifier still runs and may disagree;
    #: disagreement is recorded rather than silently resolved.
    view_hint: ViewClass | None = None
    duration_sec: float | None = None
    #: True for generated media. Propagates to the report (LAW 1, D-010).
    synthetic: bool = False


class InspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = ""
    vin: str | None = None
    asking_price_usd: float | None = None
    #: Mileage as stated by the seller. Stated, not verified - the report says so.
    seller_stated_mileage: int | None = None
    #: What the advert claims the vehicle is. Checked against the VIN decode; a
    #: disagreement is one of the few things we can catch before anyone drives
    #: anywhere. Claimed, not verified, and never presented as a fact about the car.
    listing_year: int | None = None
    listing_make: str | None = None
    listing_model: str | None = None
    assets: list[AssetInput] = Field(default_factory=list)
    comps: list[Comp] = Field(default_factory=list)
    #: Free-text context the buyer typed. Never presented back as an observation.
    buyer_notes: str = ""
    synthetic: bool = False
    provenance: str = ""

    @classmethod
    def load(cls, manifest_path: Path) -> InspectionInput:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return cls.model_validate(data)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_size(path: Path) -> tuple[int | None, int | None]:
    """Pixel dimensions of an image, or (None, None) if it is not one.

    Reads the header only - PIL does not decode pixel data until asked - so this
    costs nothing meaningful even across a large upload.

    Failure is not an error. A file the manifest calls a photo may be corrupt, or
    a format PIL cannot open; the correct outcome is an asset with no recorded
    dimensions rather than a dead pipeline, and the viewer already treats absent
    dimensions as "cannot crop to this" instead of guessing.
    """
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:  # pragma: no cover - Pillow is a hard dependency
        return None, None
    try:
        with Image.open(path) as image:
            return int(image.width), int(image.height)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        # DecompressionBombError is a Pillow exception that inherits from
        # Exception directly, so it walked straight past the clause above and
        # killed a pipeline this function's docstring promises it cannot kill.
        # An image too large to open safely has no dimensions we can record,
        # which is precisely the state D-045 already handles.
        return None, None


def materialize_assets(inspection: InspectionInput, media_root: Path) -> list[Asset]:
    """Turn manifest entries into Assets, hashing the real bytes on disk.

    The hash is not decoration: it is what lets a golden test prove that a
    committed finding still refers to the same pixels it was written against.
    Dimensions are recorded for the same reason - a box cited as a fraction of an
    image is only checkable against an image of known size.
    """
    assets: list[Asset] = []
    root = media_root.resolve()
    for item in inspection.assets:
        # A manifest is a file, and a file is input. `media_root / item.file`
        # keeps nothing of the root when `item.file` is absolute, and climbs out
        # of it when it contains `..` - so a manifest could name `../report.json`
        # and have it hashed, sized, and later served as an asset. Nothing else
        # in the chain checks this: the web media route validates what it is
        # asked for, not what the pipeline decided to call an asset.
        if PurePosixPath(item.file).is_absolute() or Path(item.file).is_absolute():
            raise ValueError(
                f"asset {item.id!r} declares an absolute path ({item.file!r}). "
                f"Asset paths are relative to the inspection's media directory."
            )
        path = (media_root / item.file).resolve()
        if path != root and root not in path.parents:
            raise ValueError(
                f"asset {item.id!r} resolves outside the media root: {item.file!r} "
                f"-> {path}. An asset lives inside the inspection it belongs to."
            )
        if not path.is_file():
            raise FileNotFoundError(f"asset {item.id!r} missing at {path}")
        width, height = image_size(path) if item.kind == "photo" else (None, None)
        assets.append(
            Asset(
                id=item.id,
                kind=item.kind,  # type: ignore[arg-type]
                path=item.file,
                sha256=sha256_of(path),
                bytes=path.stat().st_size,
                view_class=None,
                view_confidence=None,
                duration_sec=item.duration_sec,
                synthetic=item.synthetic or inspection.synthetic,
                width=width,
                height=height,
            )
        )
    return assets
