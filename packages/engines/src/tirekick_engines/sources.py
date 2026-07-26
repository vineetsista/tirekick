"""Federal record lookups, cached to disk.

Three public APIs, all published by their issuing body for programmatic use and
all allowlisted in net.py (LAW 3):

  vPIC DecodeVinValues     what the manufacturer encoded into the VIN
  NHTSA recallsByVehicle   safety recall campaigns for a make/model/year
  NHTSA complaintsByVehicle owner-filed complaints for a make/model/year

Every response is wrapped in an envelope that records where it came from, when,
and the SHA-256 of the exact bytes returned. That envelope is what a citation in
the report points at, so "NHTSA said this" is a claim with a receipt behind it
rather than a claim about our memory of a lookup (LAW 1).

Fixture mode reads the cache and never opens a socket, which is what keeps CI
green with no network and no key (LAW 7). Live mode fetches and writes the cache
back. Only scripts/refresh_federal_cache.py runs live.

One deliberate asymmetry, and it is the only place where what we store differs
from what we received: complaint responses are reduced to counts before they are
written to disk. See `_reduce_complaints` and DECISIONS.md D-015.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import net
from .cogs import CostMeter
from .models import RunMode

VPIC_DECODE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}"
RECALLS_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"
COMPLAINTS_URL = "https://api.nhtsa.gov/complaints/complaintsByVehicle"
COMPLAINT_MODELS_URL = "https://api.nhtsa.gov/products/vehicle/models"

#: Federal records describe a model, not an inspection, so they are cached once
#: for the whole repository rather than per inspection directory.
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[4] / "fixtures" / "federal"

SOURCE_VPIC = "NHTSA vPIC"
SOURCE_RECALLS = "NHTSA Safety Recalls"
SOURCE_COMPLAINTS = "NHTSA Owner Complaints"
SOURCE_COMPLAINT_MODELS = "NHTSA Complaint Model Index"


class FederalRecordMissing(RuntimeError):
    """A cached federal record was requested and is not on disk."""


@dataclass(frozen=True)
class FederalRecord:
    """One cached response, with everything needed to cite it."""

    source: str
    url: str
    retrieved_at: str
    #: SHA-256 of the response body exactly as the server sent it. Survives even
    #: when the stored payload is a reduction of that body.
    body_sha256: str
    payload: dict[str, Any]
    note: str = ""

    def to_envelope(self) -> dict[str, Any]:
        return {
            "_source": self.source,
            "_url": self.url,
            "_retrieved_at": self.retrieved_at,
            "_body_sha256": self.body_sha256,
            "_note": self.note,
            "payload": self.payload,
        }

    @classmethod
    def from_envelope(cls, data: dict[str, Any]) -> FederalRecord:
        return cls(
            source=data["_source"],
            url=data["_url"],
            retrieved_at=data["_retrieved_at"],
            body_sha256=data["_body_sha256"],
            payload=data["payload"],
            note=data.get("_note", ""),
        )


def _slug(text: str) -> str:
    """Cache-key-safe form of a make or model name."""
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-") or "unknown"


def _reduce_complaints(body: dict[str, Any]) -> dict[str, Any]:
    """Turn a complaints response into counts, and keep nothing else.

    A single model-year query returns thousands of complaint narratives written by
    members of the public, each carrying a partial VIN, a date, a location, and
    frequently an account of someone's crash. TIREKICK needs exactly one thing
    from that: how many complaints were filed and against which components. It
    does not need, and will not store, the narratives.

    So the reduction happens here, before anything is written to disk - the raw
    bodies never enter the repository. The SHA-256 of the original body travels
    with the reduction, so a future run can still prove which response these
    counts were computed from. See DECISIONS.md D-015.
    """
    results = body.get("results") or []
    components: Counter[str] = Counter()
    crashes = 0
    fires = 0
    injuries = 0
    deaths = 0
    for entry in results:
        # NHTSA joins multiple components with commas in one string.
        for component in str(entry.get("components") or "").split(","):
            cleaned = component.strip()
            if cleaned:
                components[cleaned] += 1
        crashes += 1 if entry.get("crash") else 0
        fires += 1 if entry.get("fire") else 0
        injuries += int(entry.get("numberOfInjuries") or 0)
        deaths += int(entry.get("numberOfDeaths") or 0)

    return {
        "total": int(body.get("count") or len(results)),
        "top_components": [
            {"component": name, "count": count} for name, count in components.most_common(6)
        ],
        "with_crash": crashes,
        "with_fire": fires,
        "injuries_reported": injuries,
        "deaths_reported": deaths,
        "_reduction_note": (
            "Counts only. Complaint narratives are not retained: they are written "
            "by members of the public and carry partial VINs and accident accounts "
            "belonging to other people."
        ),
    }


@dataclass
class FederalSources:
    """Cached access to the three federal endpoints."""

    mode: RunMode
    cache_dir: Path
    meter: CostMeter

    def decode_vin(self, vin: str) -> FederalRecord:
        return self._get(
            key=f"vpic.decode.{vin}",
            source=SOURCE_VPIC,
            url=VPIC_DECODE_URL.format(vin=vin),
            params={"format": "json"},
        )

    def recalls(self, make: str, model: str, year: int) -> FederalRecord:
        return self._get(
            key=f"nhtsa.recalls.{year}.{_slug(make)}.{_slug(model)}",
            source=SOURCE_RECALLS,
            url=RECALLS_URL,
            params={"make": make, "model": model, "modelYear": str(year)},
        )

    def complaint_model_index(self, make: str, year: int) -> FederalRecord:
        """Model names the complaints endpoint will actually accept.

        The recall and complaint endpoints do not share a model vocabulary, and
        nothing in either response says so. Recalls take 'F-150'; complaints
        return HTTP 400 for it and index the same truck as 'F-150 SUPERCAB',
        'F-150 REGULAR CAB' and 'F-150 SUPER CREW'. Without this lookup the
        complaint section for two of the five golden vehicles would have been an
        empty result rendered as zero complaints, which reads as good news and is
        actually a failed query. See DECISIONS.md D-020.
        """
        return self._get(
            key=f"nhtsa.complaint-models.{year}.{_slug(make)}",
            source=SOURCE_COMPLAINT_MODELS,
            url=COMPLAINT_MODELS_URL,
            params={"modelYear": str(year), "make": make, "issueType": "c"},
        )

    def complaints(self, make: str, model: str, year: int) -> FederalRecord:
        return self._get(
            key=f"nhtsa.complaints.{year}.{_slug(make)}.{_slug(model)}",
            source=SOURCE_COMPLAINTS,
            url=COMPLAINTS_URL,
            params={"make": make, "model": model, "modelYear": str(year)},
            reduce=_reduce_complaints,
        )

    # ------------------------------------------------------------------ #

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _get(
        self,
        *,
        key: str,
        source: str,
        url: str,
        params: dict[str, str],
        reduce: Any = None,
    ) -> FederalRecord:
        path = self._path(key)
        if self.mode == "fixture":
            if not path.is_file():
                raise FederalRecordMissing(
                    f"No cached federal record at {path}. Fixture mode will not "
                    f"invent one - a fabricated database citation is the worst "
                    f"thing this codebase could emit (LAW 1). Run "
                    f"scripts/refresh_federal_cache.py to fetch it."
                )
            record = FederalRecord.from_envelope(json.loads(path.read_text(encoding="utf-8")))
            self.meter.record_federal_lookup(f"cache:{key}")
            return record

        response = net.get(url, params=params)
        body: dict[str, Any] = response.json()
        record = FederalRecord(
            source=source,
            url=str(response.url),
            retrieved_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            body_sha256=hashlib.sha256(response.content).hexdigest(),
            payload=reduce(body) if reduce else body,
            note="Reduced before caching." if reduce else "",
        )
        self.meter.record_federal_lookup(f"live:{key}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(record.to_envelope(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return record
