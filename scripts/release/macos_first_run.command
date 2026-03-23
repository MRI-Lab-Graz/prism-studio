#!/bin/bash
set -euo pipefail

# One-click first-run helper for unsigned/not-notarized macOS app bundles.
# Place this file in the same folder as PrismStudio.app and double-click it.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

APP_PATH=""
for candidate in "PrismStudio.app" "PrismValidator.app"; do
  if [[ -d "$candidate" ]]; then
    APP_PATH="$candidate"
    break
  fi
done

if [[ -z "$APP_PATH" ]]; then
  echo "Could not find PrismStudio.app or PrismValidator.app in: $SCRIPT_DIR"
  echo "Move this helper into the same folder as the .app, then run again."
  read -r -p "Press Enter to close..." _
  exit 1
fi

echo "Preparing first launch for $APP_PATH ..."

# Remove only quarantine metadata recursively.
if xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null; then
  echo "Removed com.apple.quarantine attribute."
else
  echo "No quarantine attribute found or removal was not needed."
fi

echo "Opening $APP_PATH ..."
open "$APP_PATH"

echo
echo "If macOS still blocks the app:"
echo "1) Right-click the app and choose Open"
echo "2) Click Open in the warning dialog"
echo
read -r -p "Press Enter to close..." _
