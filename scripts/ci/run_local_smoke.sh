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

python prism.py --help >/dev/null
python prism-studio.py --help >/dev/null

echo "[OK] Local smoke checks passed (prism.py + prism-studio.py)."
