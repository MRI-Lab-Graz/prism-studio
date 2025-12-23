#!/bin/bash
set -euo pipefail

# Build a macOS .app bundle for Prism Validator.
# This uses the repo-local ./.venv and installs build deps via scripts/setup/setup.sh.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "⚠️ This script is intended for macOS (Darwin)."
fi

if [[ ! -d ".venv" ]]; then
  echo "❌ .venv not found. Run setup first:" 
  echo "   bash scripts/setup/setup.sh --build"
  exit 1
fi

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo "❌ Virtual environment not active. Activate it first:" 
  echo "   source .venv/bin/activate"
  exit 1
fi

# Ensure build requirements are present (pyinstaller)
python -c "import PyInstaller" >/dev/null 2>&1 || {
  echo "❌ PyInstaller not installed in the current venv. Install build deps via:" 
  echo "   bash scripts/setup/setup.sh --build"
  exit 1
}

# Build the desktop GUI as a proper macOS app bundle.
python scripts/build/build_app.py \
  --entry prism-validator-gui.py \
  --name PrismValidator \
  --mode onedir \
  --clean-output

echo "✅ Done. App bundle: dist/PrismValidator.app"
