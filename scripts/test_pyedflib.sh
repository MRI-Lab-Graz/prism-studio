#!/bin/bash
# Compatibility wrapper for moved script
# Use scripts/ci/test_pyedflib.sh as the canonical location.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/ci/test_pyedflib.sh" "$@"
