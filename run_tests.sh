#!/bin/bash
# Convenience script to run all tests with the correct environment

cd "$(dirname "$0")"
source .venv/bin/activate
python3 tests/run_all_tests.py "$@"
