#!/usr/bin/env bash
# Creates the engines virtualenv and installs the package with dev extras.
# Idempotent - safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINES="$ROOT/packages/engines"
VENV="$ENGINES/.venv"

if [ ! -d "$VENV" ]; then
  echo "creating venv at $VENV"
  python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -e "$ENGINES[dev]"

echo "python: $("$VENV/bin/python" --version)"
echo "engines installed. run: pnpm run inspect:fixture"
