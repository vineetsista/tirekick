"""Vision engine.

Stage 1 classifies each photo into a view. Stage 2 runs targeted passes against
the views that support them - there is no point asking an odometer question of a
photo of a tire, and doing so is how a model gets talked into hallucinating.

The routing table is the safety mechanism people usually skip. A general "tell me
what is wrong with this car" prompt over every image produces confident findings
about parts that are not in the frame. Every pass here is narrow, is sent only at
views that can answer it, and is constrained by a schema that permits only the
finding types that pass can legitimately produce.

Two things the model is never asked for, both because it would answer:

Repair costs. There is no source behind a number the model invents, and a dollar
figure in a report is the line a buyer acts on. Cost bands stay out of the schema
until they have a real source (D-024).

A verdict on a locked system. The prompts say not to and the schema permits it
anyway, because the model must remain able to report *observations* near brakes
and structure - that is the D-005 asymmetry. What stops a verdict reaching the
report is `safety.apply_safety_law`, deterministically, downstream (D-004).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import prompts
from ..client import FixtureMissing, ModelClient
from ..models import Asset, BoundingBox, DraftFinding, ImageRegionEvidence, ViewClass
from ..safety import ALL_SYSTEMS

#: Which stage-2 passes apply to which view. A pass never runs on a view it cannot
#: answer for.
PASSES_BY_VIEW: dict[str, tuple[str, ...]] = {
    "exterior_front": ("damage", "rust", "repaint"),
    "exterior_rear": ("damage", "rust", "repaint"),
    "exterior_side_left": ("damage", "rust", "repaint"),
    "exterior_side_right": ("damage", "rust", "repaint"),
    "exterior_three_quarter": ("damage", "rust", "repaint"),
    "interior_front": ("interior_wear",),
    "interior_rear": ("interior_wear",),
    "engine_bay": ("engine_bay",),
    "odometer": ("odometer",),
    "dash": ("dash_lights",),
    "tire": ("tire_tread",),
    "vin_plate": (),
    "document": (),
    "undercarriage": ("rust",),
    "unknown": (),
}

#: Which systems each pass is actually capable of producing a finding about.
#: This is what licenses a "no issues visible" row: a system nothing ever looked at
#: must read `cannot_determine`, not clean. Note that no pass maps to `glass`,
#: `suspension`, `transmission`, or `fluids` - so those can never be reported clean,
#: which is correct, because we cannot see them.
PASS_SYSTEMS: dict[str, tuple[str, ...]] = {
    "damage": ("exterior",),
    "rust": ("exterior",),
    "repaint": ("exterior",),
    "interior_wear": ("interior",),
    "engine_bay": ("engine",),
    "odometer": ("documentation",),
    "dash_lights": ("electrical",),
    "tire_tread": ("tires",),
}

#: Finding types each pass may emit, enforced in the schema rather than asked for
#: in prose. A rust pass that returns a dash warning light has misunderstood the
#: question, and the cheapest place to refuse that is at the tool boundary.
PASS_FINDING_TYPES: dict[str, tuple[str, ...]] = {
    "damage": ("exterior_damage",),
    "rust": ("rust_corrosion",),
    "repaint": ("repaint_indicator",),
    "interior_wear": ("interior_wear",),
    "engine_bay": ("fluid_leak_indicator", "rust_corrosion"),
    "odometer": ("odometer_reading",),
    "dash_lights": ("dash_warning_light",),
    "tire_tread": ("tire_tread_estimate",),
}

VIEW_CLASSES: tuple[str, ...] = (
    "exterior_front",
    "exterior_rear",
    "exterior_side_left",
    "exterior_side_right",
    "exterior_three_quarter",
    "interior_front",
    "interior_rear",
    "engine_bay",
    "odometer",
    "dash",
    "tire",
    "vin_plate",
    "document",
    "undercarriage",
    "unknown",
)

_UNIT = {"type": "number", "minimum": 0, "maximum": 1}

CLASSIFY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "view_class": {"type": "string", "enum": list(VIEW_CLASSES)},
        "confidence": dict(_UNIT),
        "basis": {
            "type": "string",
            "description": "One sentence on what in the image decided this.",
        },
    },
    "required": ["view_class", "confidence", "basis"],
}


def findings_schema(pass_name: str) -> dict[str, Any]:
    """The tool schema for one stage-2 pass."""
    return {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "description": (
                    "Everything visible in this image that this pass covers. An "
                    "empty array is a valid and frequently correct answer."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": list(PASS_FINDING_TYPES[pass_name]),
                        },
                        "system": {"type": "string", "enum": list(ALL_SYSTEMS)},
                        "title": {"type": "string"},
                        "detail": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": ["info", "minor", "major", "critical"],
                        },
                        "confidence": dict(_UNIT),
                        "confidence_basis": {
                            "type": "string",
                            "description": (
                                "What about THIS IMAGE makes you more or less sure. "
                                "Not what is common on this kind of vehicle."
                            ),
                        },
                        "evidence": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "box": {
                                        "type": "object",
                                        "properties": {
                                            "x": dict(_UNIT),
                                            "y": dict(_UNIT),
                                            "w": dict(_UNIT),
                                            "h": dict(_UNIT),
                                        },
                                        "required": ["x", "y", "w", "h"],
                                    },
                                    "caption": {"type": "string"},
                                },
                                "required": ["box", "caption"],
                            },
                        },
                        "seller_question": {"type": ["string", "null"]},
                        "mechanic_check": {"type": ["string", "null"]},
                    },
                    "required": [
                        "type",
                        "system",
                        "title",
                        "detail",
                        "severity",
                        "confidence",
                        "confidence_basis",
                        "evidence",
                    ],
                },
            }
        },
        "required": ["findings"],
    }


def _image_path(asset: Asset, media_root: Path | None) -> list[Path]:
    if media_root is None:
        return []
    path = media_root / asset.path
    return [path] if path.is_file() else []


def classify_views(
    assets: list[Asset], client: ModelClient, media_root: Path | None = None
) -> list[Asset]:
    """Stage 1. Returns new Assets carrying their view classification."""
    prompt = prompts.load("vision", "classify")
    system = prompts.system("vision")

    classified: list[Asset] = []
    for asset in assets:
        if asset.kind != "photo":
            classified.append(asset)
            continue
        try:
            response = client.call(
                engine="vision",
                task="classify",
                subject=asset.id,
                prompt=prompt.text,
                system=system.text,
                schema=CLASSIFY_SCHEMA,
                image_paths=_image_path(asset, media_root),
                prompt_ref=prompt.ref,
            )
        except FixtureMissing:
            # An image with no cached classification simply was not classified.
            # It stays in the report as an asset, carries no view, receives no
            # stage-2 pass, and counts toward no coverage - so the systems table
            # reads `cannot_determine` rather than clean.
            #
            # Stage 2 has always degraded this way. Stage 1 did not, so a single
            # uncached photograph took down the entire run - found by the LAW 7
            # end-to-end test the moment it first uploaded a real file.
            classified.append(asset)
            continue

        view: ViewClass = response["view_class"]
        classified.append(
            asset.model_copy(
                update={"view_class": view, "view_confidence": response["confidence"]}
            )
        )
    return classified


def _evidence_from(asset_id: str, raw: dict[str, Any]) -> ImageRegionEvidence:
    box = raw["box"]
    return ImageRegionEvidence(
        asset_id=asset_id,
        box=BoundingBox(x=box["x"], y=box["y"], w=box["w"], h=box["h"]),
        caption=raw["caption"],
    )


def draft_findings(
    assets: list[Asset], client: ModelClient, media_root: Path | None = None
) -> tuple[list[DraftFinding], set[str]]:
    """Stage 2. Targeted passes, one per (asset, applicable pass).

    Returns the drafts alongside the set of systems that were actually examined.
    That second value is what the dossier needs in order to tell "we looked and saw
    nothing" apart from "nothing looked" - the two render very differently and only
    one of them is reassuring.

    Drafts may name locked systems. safety.apply_safety_law decides what happens
    to those; this engine does not get to decide (DECISIONS.md D-004).
    """
    system = prompts.system("vision")
    drafts: list[DraftFinding] = []
    examined: set[str] = set()

    for asset in assets:
        if asset.kind != "photo" or asset.view_class is None:
            continue
        for pass_name in PASSES_BY_VIEW.get(asset.view_class, ()):
            prompt = prompts.load("vision", pass_name)
            try:
                response = client.call(
                    engine="vision",
                    task=pass_name,
                    subject=asset.id,
                    prompt=prompt.text,
                    system=system.text,
                    schema=findings_schema(pass_name),
                    image_paths=_image_path(asset, media_root),
                    prompt_ref=prompt.ref,
                )
            except FixtureMissing:
                # A pass with no cached response simply did not run. Silence here
                # is honest; inventing a "nothing found" would not be - and it must
                # not mark the system examined either.
                continue
            examined.update(PASS_SYSTEMS.get(pass_name, ()))
            for index, raw in enumerate(response.get("findings", []), start=1):
                drafts.append(
                    DraftFinding(
                        id=raw.get("id") or f"vf_{pass_name}_{asset.id}_{index:02d}",
                        type=raw["type"],
                        system=raw["system"],
                        title=raw["title"],
                        detail=raw["detail"],
                        severity=raw["severity"],
                        confidence=raw["confidence"],
                        confidence_basis=raw["confidence_basis"],
                        evidence=[_evidence_from(asset.id, e) for e in raw["evidence"]],
                        # Never model-supplied. See the module docstring and D-024.
                        estimated_cost_usd=raw.get("estimated_cost_usd"),
                        seller_question=raw.get("seller_question"),
                        mechanic_check=raw.get("mechanic_check"),
                        engine="vision",
                    )
                )
    return drafts, examined
