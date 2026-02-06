#!/bin/bash
# Convenience script to run repository verification with proper environment

cd "$(dirname "$0")"
source .venv/bin/activate
python3 tests/verify_repo.py . "$@"
