"""The published gate table has to be the measured one. D-061.

docs/ACCURACY.md is the page LAW 6 requires the product to link, and until P10 its
central claim - "there is no second place to type a precision figure" - was false
about itself. The table was hand-typed, and by P9 it had drifted: fifteen rows for
sixteen registered types, and Status values naming phases that were four phases
gone.

Drift in a document nobody generates is not a mistake, it is the default. So the
question this file exists to answer is not "is the table correct today" but "can
the table become wrong without anything failing", and the answer has to be no.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from tirekick_engines import registry

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "sync_accuracy_table.py"
DOC = REPO_ROOT / "docs" / "ACCURACY.md"


def _load_script():
    """Import the sync script as a module - it lives outside the package."""
    spec = importlib.util.spec_from_file_location("sync_accuracy_table", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_accuracy_table"] = module
    spec.loader.exec_module(module)
    return module


sync = _load_script()


def test_the_committed_table_matches_the_registry() -> None:
    """The gate. Hand-edit the table and this goes red with a diff."""
    assert sync.main(["--check"]) == 0, (
        "docs/ACCURACY.md no longer matches the registry. "
        "Run: python scripts/sync_accuracy_table.py"
    )


def test_every_registered_type_is_published() -> None:
    """The specific P9 drift: documentation_gap existed and was never listed.

    A finding type with a gate that no published page mentions is a gate nobody
    can hold us to.
    """
    published = DOC.read_text(encoding="utf-8")
    for name in registry.FINDING_TYPES:
        assert f"| {name} |" in published, f"{name} has a gate but no published row"


def test_the_table_says_which_types_reach_a_paid_report() -> None:
    """LAW 4's actual switch is `enabled_for_paid`, so print that, not a proxy.

    The old table's Status column said "disabled - awaiting P2", which described
    a roadmap. The column a buyer needs is whether this type is in the report
    they are about to pay for.
    """
    table = sync.render_table()
    assert "| In paid reports |" in table
    for spec in registry.FINDING_TYPES.values():
        row = next(line for line in table.splitlines() if line.startswith(f"| {spec.type} |"))
        assert f"| {'yes' if spec.enabled_for_paid else 'no'} |" in row


def test_nothing_is_currently_sold() -> None:
    """The page's first sentence is a claim about the registry. Hold them together.

    Not a style rule - it is the state of the project. If a type ever does clear
    its gate, this fails, and whoever enabled it has to come here and rewrite the
    opening paragraph by hand rather than let it quietly go stale.
    """
    assert not registry.enabled_types(), (
        "a finding type is now enabled for paid reports. Update the opening "
        "paragraph of docs/ACCURACY.md, which states that none are."
    )


def test_a_zero_gate_publishes_as_not_applicable() -> None:
    """ "0.00" would read as the loosest gate on the page rather than no gate.

    complaint_pattern and price_comparison are summaries, not judgments. The
    flattering misreading is the one worth designing against.
    """
    table = sync.render_table()
    for name in ("complaint_pattern", "price_comparison"):
        row = next(line for line in table.splitlines() if line.startswith(f"| {name} |"))
        assert "| n/a |" in row
        assert "0.00" not in row


def test_a_measured_number_reaches_the_page_without_being_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point: change the measurement, the page changes.

    Written against a temporary bench file so it proves the path from
    bench/results/latest.json to the rendered row, rather than trusting that
    the path exists because the code reads as though it does.
    """
    bench = tmp_path / "latest.json"
    bench.write_text(
        '{"headline": {"by_type": {"rust_corrosion": '
        '{"precision": 0.91, "n_predictions": 120}}}}',
        encoding="utf-8",
    )
    rebuilt = registry._with_measurements(registry.FINDING_TYPES, bench)
    monkeypatch.setattr(registry, "FINDING_TYPES", rebuilt)

    row = next(
        line
        for line in sync.render_table().splitlines()
        if line.startswith("| rust_corrosion |")
    )
    assert "| 0.91 |" in row
    assert "| 120 |" in row
    assert "| yes |" in row, "0.91 clears the 0.85 gate on n=120, so it is sold"
    assert "| enabled |" in row


def test_a_measurement_below_gate_publishes_as_below_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The case that matters more: a bad number must not quietly read as absent."""
    bench = tmp_path / "latest.json"
    bench.write_text(
        '{"headline": {"by_type": {"rust_corrosion": '
        '{"precision": 0.40, "n_predictions": 120}}}}',
        encoding="utf-8",
    )
    rebuilt = registry._with_measurements(registry.FINDING_TYPES, bench)
    monkeypatch.setattr(registry, "FINDING_TYPES", rebuilt)

    row = next(
        line
        for line in sync.render_table().splitlines()
        if line.startswith("| rust_corrosion |")
    )
    assert "| 0.40 |" in row
    assert "| no |" in row
    assert "| below gate |" in row
    assert "not measured" not in row, "a measured failure must not read as unmeasured"


def test_the_check_fails_when_the_document_is_edited_by_hand(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A gate that cannot fail is the failure this project keeps finding.

    So the gate is pointed at a doctored copy and required to go red. Without
    this, `test_the_committed_table_matches_the_registry` would pass just as
    happily if `main` returned 0 unconditionally.
    """
    doctored = tmp_path / "ACCURACY.md"
    doctored.write_text(
        DOC.read_text(encoding="utf-8").replace(
            "| rust_corrosion | 0.85 | not measured | 0 | no | not measured |",
            "| rust_corrosion | 0.85 | 0.97 | 400 | yes | enabled |",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(sync, "DOC_PATH", doctored)

    assert sync.main(["--check"]) == 1
    assert "0.97" in capsys.readouterr().out, "the diff has to name what drifted"


def test_a_document_without_markers_fails_loudly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deleting the markers must not silently disable the gate."""
    stripped = tmp_path / "ACCURACY.md"
    stripped.write_text("# TIREKICK ACCURACY\n\nno markers here\n", encoding="utf-8")
    monkeypatch.setattr(sync, "DOC_PATH", stripped)

    with pytest.raises(SystemExit) as caught:
        sync.main(["--check"])
    assert "no generated region" in str(caught.value)
