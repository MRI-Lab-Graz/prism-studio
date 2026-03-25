#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

SKIP_SETUP=0
RUN_ALL_TESTS=0
VERIFY_FIX_MODE="--no-fix"

for arg in "$@"; do
  case "$arg" in
    --skip-setup)
      SKIP_SETUP=1
      ;;
    --with-fix)
      VERIFY_FIX_MODE="--fix"
      ;;
    --run-all-tests)
      RUN_ALL_TESTS=1
      ;;
    -h|--help)
      cat <<'EOF'
Usage: bash scripts/deep_check.sh [options]

Deep local check routine:
  1) Sync local environment via setup.sh (default)
  2) Run verify_repo.py (default: --no-fix)
  3) Run full pytest suite (tests -ra -q)
  4) Optionally run tests/run_all_tests.py

Options:
  --skip-setup      Skip setup.sh dependency sync
  --with-fix        Run verify_repo.py with --fix instead of --no-fix
  --run-all-tests   Also run tests/run_all_tests.py
  -h, --help        Show this help
EOF
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown option: $arg"
      echo "Run: bash scripts/deep_check.sh --help"
      exit 1
      ;;
  esac
done

echo "[INFO] Repo root: $REPO_ROOT"

if [[ "$SKIP_SETUP" -eq 0 ]]; then
  echo "[STEP 1/3] Sync dependencies via setup.sh"
  # setup.sh may prompt when tkinter is missing; send one newline for non-interactive runs.
  printf '\n' | bash setup.sh
else
  echo "[STEP 1/3] Skipping setup (--skip-setup)"
fi

if [[ ! -d ".venv" ]]; then
  echo "[ERROR] Missing .venv in $REPO_ROOT"
  echo "Run: bash setup.sh"
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[STEP 2/3] Repository verification (tests/verify_repo.py $VERIFY_FIX_MODE)"
python tests/verify_repo.py . "$VERIFY_FIX_MODE"

echo "[STEP 3/3] Pytest suite (tests -ra -q)"
python -m pytest tests -ra -q

if [[ "$RUN_ALL_TESTS" -eq 1 ]]; then
  echo "[STEP 4/4] Comprehensive legacy harness (tests/run_all_tests.py)"
  python tests/run_all_tests.py
fi

echo "[OK] Deep local checks completed successfully."
