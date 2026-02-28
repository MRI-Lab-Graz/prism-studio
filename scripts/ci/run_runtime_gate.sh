#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT"

if [[ ! -d ".venv" ]]; then
  echo "[ERROR] Missing .venv in $REPO_ROOT"
  echo "Run setup first: bash setup.sh"
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix
