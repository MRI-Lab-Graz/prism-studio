"""
Discover acquisition timestamps and scanner-site location from existing BIDS
JSON sidecars in a project's rawdata, for the Environment Data Import "Scan
Project MRI Data" feature.

Builds one row per (subject, session) using the earliest acquisition tag
found across that session's sidecars, so it can be fed through the existing
survey-style environment conversion pipeline unchanged.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# Same tag set already treated as privacy-sensitive in src/mri_json_scrubber.py,
# checked in priority order (most precise first).
_TIMESTAMP_DATETIME_TAGS = ("AcquisitionDateTime",)
_TIMESTAMP_DATE_TIME_TAG_PAIRS = (
    ("AcquisitionDate", "AcquisitionTime"),
    ("SeriesDate", "SeriesTime"),
    ("StudyDate", "StudyTime"),
    ("ContentDate", "ContentTime"),
)
_LOCATION_TAGS = ("InstitutionAddress", "InstitutionName")

_SUB_RE = re.compile(r"sub-([^_/\\]+)")
_SES_RE = re.compile(r"ses-([^_/\\]+)")

# Some DICOM-derived JSONs report seconds as a single digit (e.g. "12:18:2.12"
# instead of "12:18:02.12"), which datetime.fromisoformat rejects outright.
_TIME_SECONDS_RE = re.compile(r"(\d{2}:\d{2}):(\d)([.:]|$)")


def _pad_seconds(dt_str: str) -> str:
    return _TIME_SECONDS_RE.sub(r"\g<1>:0\2\3", dt_str)


def _parse_iso(dt_str: str) -> datetime | None:
    try:
        return datetime.fromisoformat(_pad_seconds(dt_str.strip()))
    except (ValueError, AttributeError):
        return None


def parse_sidecar_timestamp(sidecar: dict[str, Any]) -> datetime | None:
    """Return the earliest-priority acquisition timestamp found in one sidecar."""
    for tag in _TIMESTAMP_DATETIME_TAGS:
        value = str(sidecar.get(tag) or "").strip()
        if value:
            dt = _parse_iso(value)
            if dt is not None:
                return dt

    for date_tag, time_tag in _TIMESTAMP_DATE_TIME_TAG_PAIRS:
        date_value = str(sidecar.get(date_tag) or "").strip()
        time_value = str(sidecar.get(time_tag) or "").strip()
        if date_value and time_value:
            dt = _parse_iso(f"{date_value}T{time_value}")
            if dt is not None:
                return dt

    return None


def extract_sidecar_location(sidecar: dict[str, Any]) -> str:
    """Return the first non-empty institution/site tag found in one sidecar."""
    for tag in _LOCATION_TAGS:
        value = str(sidecar.get(tag) or "").strip()
        if value:
            return value
    return ""


def _subject_session_from_path(json_path: Path, rawdata_root: Path) -> tuple[str, str]:
    relative_parts = json_path.relative_to(rawdata_root).parts
    subject = ""
    session = ""
    for part in relative_parts:
        if not subject:
            sub_match = _SUB_RE.match(part)
            if sub_match:
                subject = f"sub-{sub_match.group(1)}"
                continue
        if not session:
            ses_match = _SES_RE.match(part)
            if ses_match:
                session = f"ses-{ses_match.group(1)}"
    return subject, session


def discover_mri_acquisition_rows(rawdata_root: Path) -> list[dict[str, Any]]:
    """Scan rawdata for one row per (subject, session) with the earliest
    acquisition timestamp and first institution/site tag found among that
    session's modality JSON sidecars.
    """
    if not rawdata_root.exists() or not rawdata_root.is_dir():
        return []

    json_paths = sorted(rawdata_root.glob("sub-*/ses-*/*/*.json")) + sorted(
        rawdata_root.glob("sub-*/*/*.json")
    )

    groups: dict[tuple[str, str], dict[str, Any]] = {}

    for json_path in json_paths:
        subject, session = _subject_session_from_path(json_path, rawdata_root)
        if not subject:
            continue

        try:
            sidecar = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(sidecar, dict):
            continue

        dt = parse_sidecar_timestamp(sidecar)
        location = extract_sidecar_location(sidecar)
        if dt is None and not location:
            continue

        key = (subject, session)
        existing = groups.get(key)
        if existing is None:
            groups[key] = {
                "participant_id": subject,
                "session_id": session,
                "timestamp": dt,
                "location": location,
                "filename": json_path.relative_to(rawdata_root).as_posix(),
            }
            continue

        if dt is not None and (existing["timestamp"] is None or dt < existing["timestamp"]):
            existing["timestamp"] = dt
            existing["filename"] = json_path.relative_to(rawdata_root).as_posix()
        if not existing["location"] and location:
            existing["location"] = location

    rows: list[dict[str, Any]] = []
    for (subject, session), row in sorted(groups.items()):
        if row["timestamp"] is None:
            continue
        rows.append(
            {
                "participant_id": subject,
                "session_id": session,
                "timestamp": row["timestamp"].isoformat(),
                "location": row["location"],
                "filename": row["filename"],
            }
        )
    return rows


def build_mri_acquisition_table(rawdata_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build a tabular dataframe of MRI-derived environment rows plus scan stats."""
    json_paths = sorted(rawdata_root.glob("sub-*/ses-*/*/*.json")) + sorted(
        rawdata_root.glob("sub-*/*/*.json")
    )
    subjects_found = sorted(
        {subject for subject, _ in (
            _subject_session_from_path(p, rawdata_root) for p in json_paths
        ) if subject}
    )

    rows = discover_mri_acquisition_rows(rawdata_root)
    subjects_with_timestamp = sorted({row["participant_id"] for row in rows})
    rows_with_location = sum(1 for row in rows if row["location"])

    stats = {
        "subjects_found": len(subjects_found),
        "rows_with_timestamp": len(rows),
        "rows_with_location": rows_with_location,
        "subjects_missing_timestamp": sorted(
            set(subjects_found) - set(subjects_with_timestamp)
        ),
    }

    columns = ["participant_id", "session_id", "timestamp", "location", "filename"]
    df = pd.DataFrame(rows, columns=columns)
    return df, stats
