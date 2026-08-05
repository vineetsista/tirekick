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
