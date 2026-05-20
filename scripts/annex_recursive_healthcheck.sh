#!/usr/bin/env bash

set -euo pipefail

DATASET_PATH="${1:-/Volumes/Thunder/129_PK01/rawdata}"

if [[ ! -d "$DATASET_PATH" ]]; then
  echo "ERROR: dataset path not found: $DATASET_PATH"
  exit 2
fi

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git is required"
  exit 2
fi

if ! command -v datalad >/dev/null 2>&1; then
  echo "ERROR: datalad is required"
  exit 2
fi

timestamp_utc="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# Broken symlinks indicate unresolved annex object targets in nested datasets.
broken_symlink_count="$(find "$DATASET_PATH" -type l ! -exec test -e {} \; -print | wc -l | tr -d ' ')"

missing_recursive_total="$(
  git -C "$DATASET_PATH" submodule foreach --quiet --recursive '
    c=$(git annex find --not --in=here 2>/dev/null | wc -l | tr -d " ")
    if [[ "$c" != "0" ]]; then
      echo "$c"
    fi
  ' | awk '{s+=$1} END {print s+0}'
)"

echo "[$timestamp_utc] dataset=$DATASET_PATH broken_symlinks=$broken_symlink_count recursive_missing=$missing_recursive_total"

if [[ "$broken_symlink_count" != "0" || "$missing_recursive_total" != "0" ]]; then
  echo "[$timestamp_utc] ALERT: Annex availability issues detected"
  git -C "$DATASET_PATH" submodule foreach --quiet --recursive '
    c=$(git annex find --not --in=here 2>/dev/null | wc -l | tr -d " ")
    if [[ "$c" != "0" ]]; then
      echo "$c $displaypath"
    fi
  ' | sort -nr | head -n 25
  exit 1
fi

echo "[$timestamp_utc] OK: Annex availability healthy"
