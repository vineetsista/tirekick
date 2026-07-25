"""What a buyer gives us, and how it is loaded from disk.

LAW 3: everything here is user-provided. There is no code path that acquires media
or listings on its own.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

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


def materialize_assets(inspection: InspectionInput, media_root: Path) -> list[Asset]:
    """Turn manifest entries into Assets, hashing the real bytes on disk.

    The hash is not decoration: it is what lets a golden test prove that a
    committed finding still refers to the same pixels it was written against.
    """
    assets: list[Asset] = []
    for item in inspection.assets:
        path = media_root / item.file
        if not path.is_file():
            raise FileNotFoundError(f"asset {item.id!r} missing at {path}")
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
            )
        )
    return assets
