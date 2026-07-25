"""Vision engine.

Stage 1 classifies each photo into a view. Stage 2 runs targeted passes against
the views that support them - there is no point asking an odometer question of a
photo of a tire, and doing so is how a model gets talked into hallucinating.

P0 is structure only: both stages read from the fixture cache. The live VLM passes
land in P2, behind the eval gate (LAW 4). What is real here is the shape - the
routing table, the schema every response must satisfy, and the refusal to accept a
finding whose evidence does not resolve to a region of an actual image.
"""

from __future__ import annotations

from typing import Any

from ..client import FixtureMissing, ModelClient
from ..models import Asset, BoundingBox, DraftFinding, ImageRegionEvidence

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

CLASSIFY_PROMPT = (
    "Classify this photograph of a vehicle into exactly one view category. "
    "Report the category and your confidence. If the photo does not clearly show "
    "one of the categories, answer 'unknown' - a wrong classification sends the "
    "wrong analysis pass at it, which is worse than no classification."
)

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

PASS_PROMPTS: dict[str, str] = {
    "damage": (
        "Identify visible exterior damage: dents, creases, scratches, cracked "
        "trim, misaligned panels. For each, give a bounding box, a severity, and "
        "your confidence. Report only what is visible in this image. Shadows, "
        "reflections, and water are not damage. If nothing is visible, return an "
        "empty list - an empty list is a correct answer."
    ),
    "rust": (
        "Identify visible corrosion. Distinguish surface rust from bubbling or "
        "perforation, and say which you see. Give a bounding box per instance. "
        "Do not infer structural rust you cannot see."
    ),
    "repaint": (
        "Identify cues suggesting a panel has been refinished: color or texture "
        "mismatch against adjacent panels, orange peel, overspray on trim or "
        "seals, masking lines. These are cues to ask about, not conclusions. "
        "State them as cues."
    ),
    "interior_wear": (
        "Describe visible interior wear: seat bolsters, steering wheel, pedals, "
        "shift knob, headliner. Wear is evidence about use; report what you see "
        "without estimating mileage from it here."
    ),
    "engine_bay": (
        "Describe what is visible in the engine bay: fluid leaks or residue, "
        "corrosion on terminals, aftermarket parts, recent replacements. Do not "
        "assess brakes, steering components, or structure."
    ),
    "odometer": (
        "Read the odometer. Report the digits and units exactly as displayed, and "
        "your confidence in the reading. If it is not legible, say so."
    ),
    "dash_lights": (
        "Identify illuminated warning lamps on the instrument cluster. Name each "
        "lamp. Do not interpret what a lamp means for the vehicle's condition."
    ),
    "tire_tread": (
        "Estimate visible tread depth and note uneven wear patterns, sidewall "
        "damage, and the DOT date code if legible. Give your confidence; tread "
        "depth from a photograph is an estimate, not a measurement."
    ),
}


def classify_views(assets: list[Asset], client: ModelClient) -> list[Asset]:
    """Stage 1. Returns new Assets carrying their view classification."""
    classified: list[Asset] = []
    for asset in assets:
        if asset.kind != "photo":
            classified.append(asset)
            continue
        response = client.call(
            engine="vision",
            task="classify",
            subject=asset.id,
            prompt=CLASSIFY_PROMPT,
            images=1,
        )
        classified.append(
            asset.model_copy(
                update={
                    "view_class": response["view_class"],
                    "view_confidence": response["confidence"],
                }
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
    assets: list[Asset], client: ModelClient
) -> tuple[list[DraftFinding], set[str]]:
    """Stage 2. Targeted passes, one per (asset, applicable pass).

    Returns the drafts alongside the set of systems that were actually examined.
    That second value is what the dossier needs in order to tell "we looked and saw
    nothing" apart from "nothing looked" - the two render very differently and only
    one of them is reassuring.

    Drafts may name locked systems. safety.apply_safety_law decides what happens
    to those; this engine does not get to decide (DECISIONS.md D-004).
    """
    drafts: list[DraftFinding] = []
    examined: set[str] = set()
    for asset in assets:
        if asset.kind != "photo" or asset.view_class is None:
            continue
        for pass_name in PASSES_BY_VIEW.get(asset.view_class, ()):
            try:
                response = client.call(
                    engine="vision",
                    task=pass_name,
                    subject=asset.id,
                    prompt=PASS_PROMPTS[pass_name],
                    images=1,
                )
            except FixtureMissing:
                # A pass with no cached response simply did not run. Silence here
                # is honest; inventing a "nothing found" would not be - and it must
                # not mark the system examined either.
                continue
            examined.update(PASS_SYSTEMS.get(pass_name, ()))
            for raw in response.get("findings", []):
                drafts.append(
                    DraftFinding(
                        id=raw["id"],
                        type=raw["type"],
                        system=raw["system"],
                        title=raw["title"],
                        detail=raw["detail"],
                        severity=raw["severity"],
                        confidence=raw["confidence"],
                        confidence_basis=raw["confidence_basis"],
                        evidence=[_evidence_from(asset.id, e) for e in raw["evidence"]],
                        estimated_cost_usd=raw.get("estimated_cost_usd"),
                        seller_question=raw.get("seller_question"),
                        mechanic_check=raw.get("mechanic_check"),
                        engine="vision",
                    )
                )
    return drafts, examined
