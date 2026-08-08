#!/usr/bin/env bash
#
# Every gate, one command. CI runs this exact script so a green local run and a
# green CI run mean the same thing (LAW 7).
#
# Deliberately runs to completion instead of failing fast: a run that reports
# "python green, contract green, web snapshot drifted" is more useful than one
# that stops at the first error. Exit code is non-zero if any gate failed.
#
# Needs no ANTHROPIC_API_KEY. TIREKICK_MODE defaults to fixture (D-009).

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="$ROOT/packages/engines/.venv/bin"
if [ ! -x "$PY/python" ]; then
  echo "python venv missing - run: pnpm py:setup"
  exit 1
fi

# CI installs ffmpeg explicitly and the audio/video suites need it. Without this
# check, a machine with no ffmpeg prints ALL GATES GREEN with those suites
# skipped - a green that does not mean what CI's green means, which is the one
# thing this script promises not to do.
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "ffmpeg/ffprobe missing - install ffmpeg (e.g. apt-get install ffmpeg)"
  exit 1
fi

NAMES=()
CODES=()

gate() {
  local name="$1"; shift
  echo ""
  echo "=============================================================="
  echo "  GATE: $name"
  echo "=============================================================="
  "$@"
  local code=$?
  NAMES+=("$name")
  CODES+=("$code")
  if [ $code -ne 0 ]; then
    echo ">>> $name FAILED (exit $code)"
  fi
  return 0
}

# --- Python engines -----------------------------------------------------------
gate "py:lint"    bash -c "'$PY/ruff' check packages/engines && '$PY/ruff' format --check packages/engines"
# --config-file is not optional here. mypy discovers config from the working
# directory, and this script runs from the repo root, where there is no
# pyproject.toml - so from P0 until P2 this gate silently ran with default
# settings and `strict = true` never applied. An entirely untyped function
# passed it. Name the config or the gate is decoration.
gate "py:types"   "$PY/mypy" --config-file packages/engines/pyproject.toml packages/engines/src
gate "py:test"    "$PY/pytest" packages/engines -q

# --- The fixture inspection must run end to end (P0 gate) ---------------------
gate "inspect:fixture" "$PY/python" -m tirekick_engines.cli inspect \
  --fixture demo-01 --out fixtures/reports/demo-01.report.json \
  --teaser-out fixtures/reports/demo-01.teaser.json

# --- The emitted report must still satisfy the zod contract (D-002) -----------
gate "contract:check" pnpm run contract:check

# --- TypeScript ---------------------------------------------------------------
gate "ts:typecheck" pnpm run typecheck
gate "ts:test"      pnpm run test
gate "ts:build"     pnpm run build

# --- The committed media must carry no metadata (D-022) -----------------------
# Until P10 this was a command a human remembered to type, which is why five
# committed frames carried ffmpeg's encoder banner in a JPEG COM segment while
# README.md told the world the images carry none. `check` reads the bytes now,
# not only the sign-off sheet, so a geotagged photograph fails here rather than
# on the day somebody downloads it.
gate "redact:media" "$PY/python" scripts/redact_media.py check fixtures/demo-01/media

# --- The eval harness must run, and its committed result must not drift -------
# bench/results/latest.json is what registry.py reads to decide whether a finding
# type may be sold, and until P11 it was a committed artifact that no gate
# regenerated - so P11 added four metrics to bench.py and every gate stayed green
# with the old shape still on disk. The pair below is the same arrangement
# inspect:fixture and fixture:clean already use for the report.
#
# While bench/labels/ is empty this pins the REFUSAL rather than any measurement:
# `scored: false` and a sentence saying so. That is exactly the thing that must
# not quietly become 0.0 - an expected calibration error of zero reads as
# perfectly calibrated - and it starts pinning real numbers the day the first
# labelled session lands.
gate "bench:run"   "$PY/python" -m tirekick_engines.cli bench
gate "bench:clean" git diff --exit-code -- bench/results/latest.json

# --- The README's numbers must be the repository's numbers (D-063) ------------
# It collects both suites to count tests, so it is slower than it looks and it
# is the last gate that can fail for a reason worth knowing about.
gate "readme:numbers" "$PY/python" scripts/check_readme.py --check

# --- The committed golden artifacts must not have drifted silently ------------
# The inspect:fixture gate regenerates the report AND the teaser, so both are
# diffed. Watching only the report let a teaser.py change rewrite the committed
# teaser in the working tree under a green run.
gate "fixture:clean" git diff --exit-code -- \
  fixtures/reports/demo-01.report.json fixtures/reports/demo-01.teaser.json

echo ""
echo "=============================================================="
echo "  SUMMARY"
echo "=============================================================="
failed=0
for i in "${!NAMES[@]}"; do
  if [ "${CODES[$i]}" -eq 0 ]; then
    printf "  PASS  %s\n" "${NAMES[$i]}"
  else
    printf "  FAIL  %s (exit %s)\n" "${NAMES[$i]}" "${CODES[$i]}"
    failed=1
  fi
done
echo ""
if [ $failed -eq 0 ]; then
  echo "  ALL GATES GREEN"
else
  echo "  GATES RED"
fi
exit $failed
