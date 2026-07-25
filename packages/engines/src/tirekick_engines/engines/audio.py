"""Audio engine.

P0 status: **this engine makes no claims.** It registers the clip, records its
duration against the cost meter, and returns no findings.

That is not a stub left half-finished - it is the correct P0 output. The anomaly
detection lands in P3 and is gated at 0.70 precision (registry.py), and EVAL.md
already commits in advance to what happens if it misses that gate: the engine
ships as a spectrogram and a list of things to ask a mechanic, with no anomaly
claims attached at all. Emitting a confident-sounding audio finding before that
measurement exists would violate LAW 4 and, more to the point, would be a guess.
"""

from __future__ import annotations

from ..cogs import CostMeter
from ..models import Asset, DraftFinding

#: What a buyer is told about audio until P3 has numbers.
P0_STATEMENT = (
    "An engine audio clip was provided and stored with this inspection. TIREKICK "
    "does not yet analyze engine audio - that engine is in development and will "
    "not make claims until its accuracy has been measured and published. Listen "
    "to the clip yourself, and ask a mechanic to listen at a cold start."
)


def analyze(assets: list[Asset], meter: CostMeter) -> list[DraftFinding]:
    for asset in assets:
        if asset.kind == "audio" and asset.duration_sec is not None:
            meter.record_audio(asset.duration_sec)
    return []


def has_audio(assets: list[Asset]) -> bool:
    return any(a.kind == "audio" for a in assets)
