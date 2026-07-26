"""Fetch the federal records the golden tests run against. LAW 3.

This is the only script in the repository that opens a network connection, and it
reaches exactly three hosts, all of them federal APIs published for programmatic
use and all of them allowlisted in net.py. It harvests no listings and visits no
marketplace, and net.get will refuse if anyone ever tries to make it.

It is never run by CI. CI reads the cache this writes, which is why CI needs no
network and no key (LAW 7). Run it by hand when the golden set changes, or when
the recall data behind the fixtures should be refreshed:

    python scripts/refresh_federal_cache.py

Recall and complaint data genuinely changes over time - a campaign filed next
month will change the count for a 2013 F-150. That is exactly why the cache is
committed: the golden tests assert against a fixed snapshot, and refreshing it is
a visible diff someone has to read, rather than a silent change in what the tests
mean.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "packages" / "engines" / "src"))

from tirekick_engines.cogs import CostMeter  # noqa: E402
from tirekick_engines.engines import data as data_engine  # noqa: E402
from tirekick_engines.sources import DEFAULT_CACHE_DIR, FederalSources  # noqa: E402

GOLDEN_VINS_PATH = DEFAULT_CACHE_DIR / "GOLDEN_VINS.json"


def golden_vins() -> list[dict[str, str]]:
    data = json.loads(GOLDEN_VINS_PATH.read_text(encoding="utf-8"))
    vins: list[dict[str, str]] = data["vins"]
    return vins


def main() -> int:
    meter = CostMeter(mode="live")
    sources = FederalSources(mode="live", cache_dir=DEFAULT_CACHE_DIR, meter=meter)

    failures = 0
    for entry in golden_vins():
        vin = entry["vin"]
        print(f"\n{vin}  (expecting {entry['expect']})")
        record = data_engine.lookup(vin, sources)
        if record is None:
            print("  FAILED: no record returned")
            failures += 1
            continue

        decoded = record.decoded
        print(f"  decoded   {decoded.year} {decoded.make} {decoded.model}")
        print(f"  trim      {decoded.trim or '-'}")
        print(f"  engine    {decoded.engine or '-'}")
        print(f"  recalls   {len(record.recalls)}")
        if record.complaint_summary:
            print(f"  complaints{record.complaint_summary.total:>5}")
        if record.decode_error:
            print(f"  DECODE ERROR: {record.decode_error}")
            failures += 1
        if not record.recalls:
            # Worth shouting about: an empty recall list is indistinguishable in
            # the report from a car with no recalls, and here it usually means
            # the make/model strings vPIC returned are not the strings the recall
            # endpoint indexes on.
            print("  WARNING: no recalls returned - check the make/model strings")

    print(f"\ncache: {DEFAULT_CACHE_DIR}")
    print(f"federal lookups: {meter.federal_lookups}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
