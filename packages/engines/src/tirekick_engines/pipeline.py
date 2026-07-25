"""The end-to-end run: input manifest in, law-abiding Report out."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .client import ModelClient
from .cogs import CostMeter
from .dossier import build_report
from .engines import audio as audio_engine
from .engines import data as data_engine
from .engines import vision as vision_engine
from .inputs import InspectionInput, materialize_assets
from .models import Report, RunMode


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
) -> RunResult:
    """Run every engine against one inspection directory.

    Layout: manifest.json, media/, cached/ (fixture responses).
    """
    inspection = InspectionInput.load(inspection_dir / "manifest.json")
    meter = CostMeter(mode=mode)
    client = ModelClient(mode=mode, cache_dir=inspection_dir / "cached", meter=meter)

    assets = materialize_assets(inspection, inspection_dir / "media")

    # Vision stage 1, then stage 2 against the classified views.
    assets = vision_engine.classify_views(assets, client)
    drafts, examined_systems = vision_engine.draft_findings(assets, client)

    # Audio makes no claims in P0; it records the clip against the cost meter.
    drafts.extend(audio_engine.analyze(assets, meter))

    vehicle = data_engine.lookup(inspection.vin, client)
    drafts.extend(data_engine.recall_findings(vehicle))

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
