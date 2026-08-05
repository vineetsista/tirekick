"""TIREKICK CLI.

Every run prints, in order: the mode it is running in (D-009), the eval gate table
(LAW 4), the safety clamp log (LAW 2), and the cost of the report (LAW 5). None of
these are behind a verbose flag. A number you have to ask for is a number nobody
reads.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import bench as bench_module
from . import teaser as teaser_module
from .client import resolve_mode
from .pipeline import run_inspection
from .registry import gate_status_table

REPO_ROOT = Path(__file__).resolve().parents[4]


def _banner(mode: str, inspection_dir: Path) -> str:
    rule = "=" * 72
    return "\n".join(
        [
            rule,
            "  TIREKICK - automated used-car analysis",
            "  Not an inspection. Safety-critical systems are never cleared remotely.",
            rule,
            f"  mode        {mode}"
            + ("  (cached responses, no API calls)" if mode == "fixture" else ""),
            f"  inspection  {inspection_dir}",
            "",
        ]
    )


def cmd_inspect(args: argparse.Namespace) -> int:
    mode = resolve_mode(args.mode)

    if args.fixture:
        inspection_dir = REPO_ROOT / "fixtures" / args.fixture
    else:
        inspection_dir = Path(args.dir).resolve()

    if not (inspection_dir / "manifest.json").is_file():
        print(f"error: no manifest.json in {inspection_dir}", file=sys.stderr)
        return 2

    print(_banner(mode, inspection_dir))

    result = run_inspection(
        inspection_dir=inspection_dir,
        mode=mode,
        generated_at=args.generated_at,
    )

    print("  EVAL GATE (LAW 4) - only 'yes' rows may appear in a paid report")
    print(gate_status_table())
    print()

    print("  SAFETY CLAMP (LAW 2)")
    if result.clamp_log:
        for line in result.clamp_log:
            print(f"    {line}")
    else:
        print("    No draft findings touched a locked system on this run.")
    print()

    report = result.report
    print("  REPORT")
    print(f"    findings            {len(report.findings)}")
    print(f"    mechanic referrals  {len(report.mechanic_referrals)}")
    print(f"    red-flag score      {report.verdict.red_flag_score}/100")
    print(f"    coverage            {report.coverage.score:.0%}")
    if report.contains_synthetic_media:
        print(
            "    NOTE                contains synthetic media; not evidence about any vehicle"
        )
    print()

    print(result.meter.render())
    print()

    if args.teaser_out:
        teaser = teaser_module.build_teaser(report, price_usd=args.price)
        teaser_path = _resolve(args.teaser_out)
        teaser_path.parent.mkdir(parents=True, exist_ok=True)
        teaser_path.write_text(teaser.to_json(), encoding="utf-8")
        print(f"  wrote {teaser_path}  (free projection, {len(teaser.to_json())} bytes)")

    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = REPO_ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report.to_json(), encoding="utf-8")
        print(f"  wrote {out_path}")
    else:
        print(report.to_json())

    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    """LAW 4. Score generated reports against human labels."""
    labels_dir = _resolve(args.labels)
    reports_dir = _resolve(args.reports)
    results_path = _resolve(args.out)

    if args.inspections:
        inspections_dir = _resolve(args.inspections)
        reports_dir.mkdir(parents=True, exist_ok=True)
        for manifest in sorted(inspections_dir.glob("*/manifest.json")):
            run = run_inspection(inspection_dir=manifest.parent, mode=resolve_mode(args.mode))
            out = reports_dir / f"{manifest.parent.name}.report.json"
            out.write_text(run.report.to_json(), encoding="utf-8")
            print(f"  ran {manifest.parent.name} -> {out.name}")
        print()

    if not labels_dir.is_dir():
        print(f"error: no labels directory at {labels_dir}", file=sys.stderr)
        return 2

    scored = bench_module.run(labels_dir, reports_dir)
    print(bench_module.render(scored))
    print()

    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(
        json.dumps(scored, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"  wrote {results_path}")
    print(
        "  The eval gate and docs/ACCURACY.md read this file. Nothing ships to a "
        "paid report until it clears its gate here (LAW 4)."
    )
    return 0


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tirekick", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect", help="run an inspection end to end")
    source = inspect.add_mutually_exclusive_group(required=True)
    source.add_argument("--fixture", help="fixture name under fixtures/, e.g. demo-01")
    source.add_argument("--dir", help="path to an inspection directory")
    inspect.add_argument("--mode", choices=["fixture", "live"], default=None)
    inspect.add_argument("--out", help="write the report JSON here")
    inspect.add_argument("--teaser-out", default=None, help="write the free teaser here")
    # The default is the shared constant, not a number typed here. It was a
    # literal, and the teaser it wrote into the artifact was the second price a
    # buyer met - the landing page printed the TypeScript copy and this printed
    # its own, with nothing comparing them. See teaser.PRICE_USD.
    inspect.add_argument(
        "--price",
        type=float,
        default=teaser_module.PRICE_USD,
        help="price shown on the teaser; defaults to the shared constant",
    )
    inspect.add_argument(
        "--generated-at",
        default=None,
        help="fixed timestamp, so golden fixture output is byte-stable",
    )
    inspect.set_defaults(func=cmd_inspect)

    bench = sub.add_parser("bench", help="score reports against labels (LAW 4)")
    bench.add_argument("--labels", default="bench/labels")
    bench.add_argument("--reports", default="bench/reports")
    bench.add_argument("--out", default="bench/results/latest.json")
    bench.add_argument(
        "--inspections",
        default=None,
        help="run every inspection in this directory before scoring",
    )
    bench.add_argument("--mode", choices=["fixture", "live"], default=None)
    bench.set_defaults(func=cmd_bench)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
