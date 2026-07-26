"""The end-to-end run: input manifest in, law-abiding Report out."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .client import ModelClient
from .cogs import CostMeter
from .dossier import build_report
from .engines import audio as audio_engine
from .engines import data as data_engine
from .engines import history as history_engine
from .engines import vision as vision_engine
from .inputs import InspectionInput, materialize_assets
from .models import Report, RunMode
from .sources import DEFAULT_CACHE_DIR, FederalSources


@dataclass
class RunResult:
    report: Report
    clamp_log: list[str]
    meter: CostMeter


def run_inspection(
    *,
    inspection_dir: Path,
    mode: RunMode,
    generated_at: str | None = None,
    federal_cache_dir: Path | None = None,
) -> RunResult:
    """Run every engine against one inspection directory.

    Layout: manifest.json, media/, cached/ (fixture responses).
    """
    inspection = InspectionInput.load(inspection_dir / "manifest.json")
    meter = CostMeter(mode=mode)
    client = ModelClient(mode=mode, cache_dir=inspection_dir / "cached", meter=meter)
    sources = FederalSources(
        mode=mode,
        cache_dir=federal_cache_dir or DEFAULT_CACHE_DIR,
        meter=meter,
    )

    media_root = inspection_dir / "media"
    assets = materialize_assets(inspection, media_root)

    # Vision stage 1, then stage 2 against the classified views.
    assets = vision_engine.classify_views(assets, client)
    drafts, examined_systems = vision_engine.draft_findings(assets, client)

    # Audio makes no claims in P0; it records the clip against the cost meter.
    drafts.extend(audio_engine.analyze(assets, meter))

    vehicle = data_engine.lookup(inspection.vin, sources)
    drafts.extend(data_engine.recall_findings(vehicle))
    drafts.extend(data_engine.complaint_findings(vehicle))
    drafts.extend(
        data_engine.decode_findings(
            vehicle,
            listing_year=inspection.listing_year,
            listing_make=inspection.listing_make,
            listing_model=inspection.listing_model,
        )
    )

    # Reads the buyer's own paperwork. Queries no title registry.
    drafts.extend(history_engine.title_brand_findings(assets, media_root))

    report, clamp_log = build_report(
        inspection_id=inspection.id,
        report_id=f"rpt_{inspection.id}",
        mode=mode,
        assets=assets,
        drafts=drafts,
        vehicle=vehicle,
        asking_price_usd=inspection.asking_price_usd,
        comps=inspection.comps,
        subject_mileage=inspection.seller_stated_mileage,
        meter=meter,
        examined_systems=examined_systems,
        generated_at=generated_at,
    )
    return RunResult(report=report, clamp_log=clamp_log, meter=meter)
