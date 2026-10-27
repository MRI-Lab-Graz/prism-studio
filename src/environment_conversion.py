"""
Environment conversion engine (canonical backend for Studio + CLI).

Takes a tabular file (xlsx/csv/tsv/sav/rds/rdata) from a survey export, maps
columns for timestamp, participant ID, session, and optional location, then
derives privacy-safe environmental context metadata (time-based anchors,
sun/moon phase, season) and writes a PRISM-compatible environment.tsv.

The converter enriches rows with live Open-Meteo lookups when coordinates are
available. Provider failures are treated as partial-enrichment warnings so
conversion can still finish with the core temporal fields intact.

Used by `prism_tools.py environment preview|convert` and, through those
commands, by the Studio Environment tab. Keep Flask out of this module.
"""

from __future__ import annotations

import csv
import json
import math
import random
import re
import unicodedata
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter, sleep
from typing import Any

import pandas as pd
import requests

from src.bids_integration import check_and_update_bidsignore
from src.cleaning_notes import cleaning_note
from src.term_registry import find_term, load_registry
from src.session_map import resolve_import_session
from src.converters.file_reader import (
    expected_delimiter_for_suffix,
    infer_tabular_kind,
    read_tabular_file,
)
from src.environment_engine_helpers import (
    handle_validate_environment_conversion_inputs,
)
from src.environment_provider_helpers import (
    handle_cache_key_for_day,
    handle_extract_environment_hour,
    handle_fetch_environment_day,
    handle_fetch_environment_hour,
    handle_hourly_series,
    handle_hourly_value,
    handle_load_environment_provider_cache,
    handle_payload_has_hourly_data,
    handle_pollen_risk_bin,
    handle_save_environment_provider_cache,
)
from src.environment_result_helpers import handle_persist_environment_outputs
from src.environment_windows import (
    WindowSpec,
    compute_window,
    duration_to_timedelta,
    missing_hours,
    window_column_name,
)
from src.environment_temporal import (
    estimate_daylight_hours as _shared_estimate_daylight_hours,
    hour_to_bin as _shared_hour_to_bin,
    hours_since_sun as _shared_hours_since_sun,
    season_code as _shared_season_code,
    sun_phase as _shared_sun_phase,
)
from src.project_root import require_existing_project_root


class EnvironmentConversionCancelledError(Exception):
    """Raised when an environment conversion is cancelled by the user."""


ALLOWED_SUFFIXES = {".xlsx", ".csv", ".tsv", ".sav", ".rds", ".rdata", ".rda"}
WEATHER_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
GEOCODING_TIMEOUT_SECONDS = 5
WEATHER_TIMEOUT_SECONDS = 8
AIR_QUALITY_TIMEOUT_SECONDS = 5
POLLEN_TIMEOUT_SECONDS = 5
PROVIDER_RETRY_ATTEMPTS = 3
PROVIDER_RETRY_BACKOFF_SECONDS = 0.75

OUTPUT_COLUMNS = [
    "subject_id",
    "session_id",
    "hour_bin",
    "season_code",
    "sun_phase",
    "sun_hours_today",
    "hours_since_sun",
    "elevation_m",
    "heatwave_status",
    "moon_phase",
    "moon_illumination_pct",
    "temp_c",
    "apparent_temp_c",
    "dew_point_c",
    "humidity_pct",
    "pressure_hpa",
    "precip_mm",
    "wind_speed_ms",
    "cloud_cover_pct",
    "uv_index",
    "shortwave_radiation_wm2",
    "weather_regime",
    "aqi",
    "pm25_ug_m3",
    "pm10_ug_m3",
    "no2_ug_m3",
    "o3_ug_m3",
    "pollen_birch",
    "pollen_grass",
    "pollen_mugwort",
    "pollen_ragweed",
    "pollen_total",
    "pollen_risk_bin",
]

# ── Time / astronomy helpers ───────────────────────────────────────────────────


def _hour_bin(hour: int) -> str:
    return _shared_hour_to_bin(hour)


def _season_code(doy: int) -> str:
    return _shared_season_code(doy)


def _estimate_daylight(doy: int, lat: float = 47.0) -> float:
    return _shared_estimate_daylight_hours(doy, lat)


def _sun_phase(hour: int, daylight: float) -> str:
    return _shared_sun_phase(hour, daylight)


def _hours_since_sun(hour: int, daylight: float) -> float:
    return _shared_hours_since_sun(hour, daylight)


def _moon_status(dt: datetime) -> tuple[str, float]:
    epoch = datetime(2001, 1, 1, tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    days = (dt - epoch).total_seconds() / 86400.0
    synodic = 29.53058867
    frac = (days % synodic) / synodic
    illum = round((1 - math.cos(2 * math.pi * frac)) / 2 * 100.0, 1)
    if frac < 0.03 or frac >= 0.97:
        phase = "new_moon"
    elif frac < 0.22:
        phase = "waxing_crescent"
    elif frac < 0.28:
        phase = "first_quarter"
    elif frac < 0.47:
        phase = "waxing_gibbous"
    elif frac < 0.53:
        phase = "full_moon"
    elif frac < 0.72:
        phase = "waning_gibbous"
    elif frac < 0.78:
        phase = "last_quarter"
    else:
        phase = "waning_crescent"
    return phase, illum


_TIMESTAMP_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
]


def _parse_timestamp(value: str) -> datetime | None:
    cleaned = str(value or "").strip().rstrip("Z").strip()
    if not cleaned or cleaned.lower() in ("nan", "none", "n/a", ""):
        return None
    # Try ISO with timezone offset
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        pass
    for fmt in _TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    # Pandas fallback for ambiguous formats
    try:
        return pd.to_datetime(cleaned, dayfirst=False).to_pydatetime()
    except Exception:
        return None


def _bids_label(value: str, prefix: str) -> str:
    """``prefix-label`` with ASCII letters and digits only (like every other converter), '' if none."""
    v = unicodedata.normalize("NFC", str(value or "").strip())
    if v.lower() in ("nan", "none", "n/a"):
        return ""
    if v.lower().startswith(f"{prefix}-"):
        v = v[len(prefix) + 1 :]
    label = re.sub(r"[^A-Za-z0-9]+", "", v)
    return f"{prefix}-{label}" if label else ""


def _compute_row(
    dt: datetime,
    subject_id: str,
    session_id: str,
    lat: float | None,
) -> dict:
    doy = dt.timetuple().tm_yday
    hour = dt.hour
    lat_val = lat if lat is not None else 47.0
    daylight = _estimate_daylight(doy, lat_val)
    moon_phase, moon_illum = _moon_status(dt)
    return {
        "subject_id": subject_id,
        "session_id": session_id,
        "hour_bin": _hour_bin(hour),
        "season_code": _season_code(doy),
        "sun_phase": _sun_phase(hour, daylight),
        "sun_hours_today": daylight,
        "hours_since_sun": _hours_since_sun(hour, daylight),
        "elevation_m": None,
        "heatwave_status": "unknown",
        "moon_phase": moon_phase,
        "moon_illumination_pct": moon_illum,
        "temp_c": None,
        "apparent_temp_c": None,
        "dew_point_c": None,
        "humidity_pct": None,
        "pressure_hpa": None,
        "precip_mm": None,
        "wind_speed_ms": None,
        "cloud_cover_pct": None,
        "uv_index": None,
        "shortwave_radiation_wm2": None,
        "weather_regime": "frontal",
        "aqi": None,
        "pm25_ug_m3": None,
        "pm10_ug_m3": None,
        "no2_ug_m3": None,
        "o3_ug_m3": None,
        "pollen_birch": None,
        "pollen_grass": None,
        "pollen_mugwort": None,
        "pollen_ragweed": None,
        "pollen_total": None,
        "pollen_risk_bin": "unknown",
    }


def _hourly_value(payload: dict, key: str, timestamp_iso: str) -> float | None:
    return handle_hourly_value(payload, key, timestamp_iso)


def _pollen_risk_bin(total: float | None) -> str:
    return handle_pollen_risk_bin(total)


def _provider_warning(provider: str, exc: Exception) -> str:
    return f"{provider} API unavailable ({exc})"


def _fetch_provider_json(url: str, params: dict[str, Any], timeout: int) -> dict:
    last_exc: Exception | None = None
    for attempt in range(1, PROVIDER_RETRY_ATTEMPTS + 1):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_exc = exc
            if attempt >= PROVIDER_RETRY_ATTEMPTS:
                break
            sleep(PROVIDER_RETRY_BACKOFF_SECONDS * attempt)

    assert last_exc is not None
    raise requests.RequestException(
        f"{last_exc} after {PROVIDER_RETRY_ATTEMPTS} attempts"
    ) from last_exc


def _payload_has_hourly_data(payload: dict[str, Any] | None) -> bool:
    return handle_payload_has_hourly_data(payload)


def _cache_key_for_day(date_str: str, lat: float, lon: float) -> str:
    return handle_cache_key_for_day(date_str, lat, lon)


def _load_environment_provider_cache(
    cache_path: Path,
) -> dict[str, dict[str, dict[str, Any]]]:
    return handle_load_environment_provider_cache(cache_path)


def _save_environment_provider_cache(
    cache_path: Path,
    entries: dict[str, dict[str, dict[str, Any]]],
) -> None:
    handle_save_environment_provider_cache(cache_path, entries)


def _fetch_environment_day(
    dt: datetime,
    lat: float,
    lon: float,
    *,
    cached_payloads: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, dict], list[str]]:
    return handle_fetch_environment_day(
        dt,
        lat,
        lon,
        cached_payloads=cached_payloads,
        payload_has_hourly_data=_payload_has_hourly_data,
        fetch_provider_json=_fetch_provider_json,
        provider_warning=_provider_warning,
        weather_archive_url=WEATHER_ARCHIVE_URL,
        air_quality_url=AIR_QUALITY_URL,
        weather_timeout_seconds=WEATHER_TIMEOUT_SECONDS,
        air_quality_timeout_seconds=AIR_QUALITY_TIMEOUT_SECONDS,
        pollen_timeout_seconds=POLLEN_TIMEOUT_SECONDS,
    )


def _extract_environment_hour(dt: datetime, provider_payloads: dict[str, dict]) -> dict:
    return handle_extract_environment_hour(
        dt,
        provider_payloads,
        hourly_value=_hourly_value,
        pollen_risk_bin=_pollen_risk_bin,
    )


def _fetch_environment_hour(
    dt: datetime, lat: float, lon: float
) -> tuple[dict, list[str]]:
    return handle_fetch_environment_hour(
        dt,
        lat,
        lon,
        fetch_environment_day=_fetch_environment_day,
        extract_environment_hour=_extract_environment_hour,
    )


# ── Column auto-detection helpers ─────────────────────────────────────────────

_CANDIDATE_PARTICIPANT = [
    "participant_id",
    "subject_id",
    "participant",
    "subject",
    "id",
    "prolific_pid",
    "workerid",
    "worker_id",
    "responseid",
    "response_id",
]
_CANDIDATE_SESSION = [
    "session_id",
    "session",
    "ses",
    "wave",
    "timepoint",
    "visit",
]
_CANDIDATE_TIMESTAMP = [
    "timestamp",
    "datetime",
    "date_time",
    "startdate",
    "start_date",
    "enddate",
    "end_date",
    "submitdate",
    "submit_date",
    "datestamp",
    "date",
    "time",
    "created_at",
    "date_submitted",
    "submission_date",
    "assessment_date",
    "interview_date",
]
_CANDIDATE_LOCATION = [
    "location",
    "site",
    "location_label",
    "study_site",
    "country",
    "city",
    "place",
    "lab",
    "center",
]
_CANDIDATE_LAT = [
    "lat",
    "latitude",
    "gps_lat",
    "geo_lat",
    "location_lat",
    "site_lat",
]
_CANDIDATE_LON = [
    "lon",
    "long",
    "lng",
    "longitude",
    "gps_lon",
    "geo_lon",
    "location_lon",
    "site_lon",
]


def _detect_col(candidates: list[str], columns: list[str]) -> str | None:
    cols_lower = {c.lower(): c for c in columns}
    for c in candidates:
        if c in cols_lower:
            return cols_lower[c]
    return None


def _compatibility_report(
    df: pd.DataFrame, columns: list[str], timestamp_col: str | None
) -> dict:
    warnings: list[str] = []
    status = "compatible"

    if len(df) == 0:
        warnings.append("File has no rows")
        status = "incompatible"

    if not timestamp_col:
        warnings.append("No timestamp-like column auto-detected")
        status = "needs_attention"

    parse_rate_pct = None
    if timestamp_col and timestamp_col in df.columns:
        probe = df[timestamp_col].astype(str).head(200)
        valid = 0
        non_empty = 0
        for value in probe:
            text = str(value).strip()
            if not text or text.lower() in {"nan", "none", "n/a"}:
                continue
            non_empty += 1
            if _parse_timestamp(text) is not None:
                valid += 1
        parse_rate_pct = (100.0 * valid / non_empty) if non_empty else 0.0
        if non_empty == 0:
            warnings.append("Timestamp column has no non-empty values in sampled rows")
            status = "incompatible"
        elif parse_rate_pct < 70.0:
            warnings.append("Timestamp format parse rate is low (<70%)")
            if status != "incompatible":
                status = "needs_attention"

    has_lat = _detect_col(_CANDIDATE_LAT, columns) is not None
    has_lon = _detect_col(_CANDIDATE_LON, columns) is not None
    has_location = _detect_col(_CANDIDATE_LOCATION, columns) is not None
    if not ((has_lat and has_lon) or has_location):
        warnings.append(
            "No geo columns auto-detected (lat/lon or location); provide global fallback coordinates."
        )
        if status == "compatible":
            status = "needs_attention"

    return {
        "status": status,
        "rows": int(len(df)),
        "columns": int(len(columns)),
        "timestamp_parse_rate_pct": parse_rate_pct,
        "geo_candidates": {
            "has_lat_column": has_lat,
            "has_lon_column": has_lon,
            "has_location_column": has_location,
        },
        "warnings": warnings,
    }


def _coerce_coord(value: str | None, *, lat: bool) -> float | None:
    text = str(value or "").strip().replace(",", ".")
    if not text or text.lower() in {"nan", "none", "n/a"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if lat:
        return number if -90.0 <= number <= 90.0 else None
    return number if -180.0 <= number <= 180.0 else None


# DICOM InstitutionAddress is free text but commonly formatted as
# "Street,City,State,Country,PostalCode" (e.g. heudiconv/dcm2niix output).
# Open-Meteo's geocoder is a place-name search, not a structured address
# geocoder: it returns zero results for a full address string, and even for
# "City, ST"-style 2-letter state qualifiers — only a bare place name (and
# full country names) work reliably. Strip postal codes / short
# state-or-country-code tokens and any street-like (digit-containing) part to
# recover a city name worth searching.
_ADDRESS_TRAILING_CODE_RE = re.compile(r"^(\d{3,10}|[A-Za-z]{2,3})$")


def _address_geocoding_fallback_candidates(label: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[,;]", label) if p.strip()]
    if len(parts) <= 1:
        return []

    while parts and _ADDRESS_TRAILING_CODE_RE.match(parts[-1]):
        parts.pop()

    return [part for part in reversed(parts) if not re.search(r"\d", part)]


def _geocode_place_name(
    name: str,
) -> tuple[float, float] | None:
    params: dict[str, str | int] = {
        "name": name,
        "count": 1,
        "language": "en",
        "format": "json",
    }
    response = requests.get(
        GEOCODING_URL,
        params=params,
        timeout=GEOCODING_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    first = (payload.get("results") or [None])[0]
    if not first:
        return None
    lat = first.get("latitude")
    lon = first.get("longitude")
    if lat is None or lon is None:
        return None
    return (float(lat), float(lon))


def _geocode_location(
    label: str, cache: dict[str, tuple[float, float] | None]
) -> tuple[float, float] | None:
    key = (label or "").strip().lower()
    if not key:
        return None
    if key in cache:
        return cache[key]

    try:
        coords = _geocode_place_name(label)
        if coords is None:
            for candidate in _address_geocoding_fallback_candidates(label):
                coords = _geocode_place_name(candidate)
                if coords is not None:
                    break
        cache[key] = coords
        return coords
    except requests.RequestException:
        cache[key] = None
        return None


def _preview_value(value: object) -> str:
    if value is None:
        return "n/a"
    text = str(value).strip()
    if not text:
        return "n/a"
    return text


def _load_environment_dataframe(
    input_path: Path,
    *,
    suffix: str,
    separator_option: str,
) -> pd.DataFrame:
    kind = infer_tabular_kind(input_path)
    if kind is None:
        raise ValueError(
            "Unsupported file type. Use .xlsx, .csv, .tsv, .sav, .rds, .rdata, or .rda"
        )
    delimiter = expected_delimiter_for_suffix(suffix, separator_option)
    result = read_tabular_file(
        input_path,
        kind=kind,
        separator=delimiter,
    )
    return result.df


def _build_environment_preview(rows_out: list[dict], window_columns: list[str] = ()) -> dict:
    preview_columns = [
        "subject_id",
        "session_id",
        "elevation_m",
        "heatwave_status",
        "temp_c",
        "humidity_pct",
        "pressure_hpa",
        "weather_regime",
        "aqi",
        "pm25_ug_m3",
        "o3_ug_m3",
        "pollen_total",
        "pollen_risk_bin",
        *window_columns,
    ]
    preview_rows = [
        [_preview_value(row.get(col)) for col in preview_columns]
        for row in rows_out[:4]
    ]
    return {
        "columns": preview_columns,
        "rows": preview_rows,
    }


def _build_environment_sidecar(windows: Sequence[WindowSpec] = ()) -> dict[str, Any]:
    """environment 2.0.0: every value column points to its official term (looked up by alias)."""
    registry = load_registry("environment")
    sidecar: dict[str, Any] = {
        "Technical": {
            "Source": "open-meteo",
            "SpatialResolution": "city",
            "TemporalResolution": "hourly",
        },
        "Study": {
            "EnvironmentName": "weather",
            "Description": "Weather, air quality, pollen and sun/moon context at each session (Open-Meteo)",
        },
        "Metadata": {
            "SchemaVersion": "2.0.0",
            "CreationDate": datetime.now(timezone.utc).date().isoformat(),
            "Creator": "PRISM Environment Converter",
        },
        "subject_id": {"Description": "BIDS subject identifier", "Units": "n/a"},
        "session_id": {"Description": "BIDS session identifier", "Units": "n/a"},
    }
    for column in OUTPUT_COLUMNS:
        if column in sidecar:
            continue
        found = find_term(registry, column)
        if found is None:
            raise ValueError(f"environment column {column!r} has no official term")
        sidecar[column] = {"Term": found[1]["TermID"]}
    for spec in windows:
        sidecar[window_column_name(spec)] = {
            "Term": sidecar[spec.column]["Term"],
            # a count is a number of hours, not a value in the term's unit
            **({"Units": "1"} if spec.statistic == "count" else {}),
            "Window": {"Start": spec.duration, "End": "PT0S"},
            "Statistic": spec.statistic,
        }
    return sidecar


def _write_environment_tsv(rows: list[dict], path: Path, columns: list[str] = OUTPUT_COLUMNS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_environment_sidecar(path: Path, windows: Sequence[WindowSpec] = ()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_payload = _build_environment_sidecar(windows)
    path.write_text(json.dumps(sidecar_payload, indent=2), encoding="utf-8")


def preview_environment_file(input_path: Path, separator_option: str) -> dict[str, Any]:
    """Columns, sample rows, compatibility report and auto-detected mappings."""
    df = _load_environment_dataframe(
        input_path,
        suffix=input_path.suffix.lower(),
        separator_option=separator_option,
    )
    columns = list(df.columns)
    auto_timestamp = _detect_col(_CANDIDATE_TIMESTAMP, columns)
    return {
        "columns": columns,
        "sample": df.head(5).fillna("").values.tolist(),
        "compatibility": _compatibility_report(df, columns, auto_timestamp),
        "auto_detected": {
            "participant_id": _detect_col(_CANDIDATE_PARTICIPANT, columns),
            "session": _detect_col(_CANDIDATE_SESSION, columns),
            "timestamp": auto_timestamp,
            "location": _detect_col(_CANDIDATE_LOCATION, columns),
            "lat": _detect_col(_CANDIDATE_LAT, columns),
            "lon": _detect_col(_CANDIDATE_LON, columns),
        },
    }


def _project_session_id(project_path, label, cache, warnings):
    """ses-<n> the project's Timepoints rule gives a source label, None without a project.json
    (the caller keeps its legacy naming). An unmapped label raises before anything is written."""
    if label not in cache:
        target, warning = resolve_import_session(project_path, label) if project_path else (None, None)
        cache[label] = None if target is None else f"ses-{target}"
        if warning:
            warnings.append(warning)
    return cache[label]


def _move_retired_environment_pin(project_root, log_callback) -> str | None:
    """A pin below 2.0.0 names the retired format this run just replaced: move it to the current version (Ruling 14)."""
    from src.modality_versions import read_pins, update_modality
    from src.schema_manager import parse_version

    try:
        pinned = read_pins(project_root)[0].get("environment")
        if not pinned or parse_version(pinned) >= parse_version("2.0.0"):
            return None
        message = f"environment schema pin {pinned} -> {update_modality(project_root, 'environment')}"
    except Exception as exc:  # noqa: BLE001 - the data is written; say what is left to do
        log_callback(f"Could not update the environment schema pin in project.json: {exc}; run: "
                     "prism_tools modality-version update <project> environment", "warning")
        return None
    log_callback(message, "info")
    return message


def perform_environment_conversion(
    *,
    input_path: Path,
    filename: str,
    suffix: str,
    separator_option: str,
    timestamp_col: str | None,
    participant_col: str | None,
    participant_override: str | None,
    session_col: str | None,
    session_override: str | None,
    location_col: str | None,
    lat_col: str | None,
    lon_col: str | None,
    location_label_override: str,
    lat_manual: float | None,
    lon_manual: float | None,
    project_path: str,
    pilot_random_subject: bool,
    log_callback,
    progress_callback=None,
    cancel_check=None,
    windows: Sequence[WindowSpec] = (),
) -> dict:
    def should_cancel() -> bool:
        return bool(cancel_check is not None and cancel_check())

    def resolve_active_project_root() -> Path:
        return require_existing_project_root(
            project_path,
            missing_message="No active project selected. Open a project before converting.",
            missing_path_message="The selected project path no longer exists. Reopen the project and retry environment conversion.",
        )

    def raise_if_cancelled(message: str = "Conversion cancelled by user") -> None:
        if should_cancel():
            log_callback("⏹️ Conversion cancelled by user", "warning")
            raise EnvironmentConversionCancelledError(message)

    windows = tuple(dict.fromkeys(windows))  # a repeated window (parse_window upper-cases the duration) is one column
    conversion_started_at = perf_counter()
    df = _load_environment_dataframe(
        input_path,
        suffix=suffix,
        separator_option=separator_option,
    )

    df = df.fillna("")
    log_callback(f"Loaded {len(df)} rows, {len(df.columns)} columns from '{filename}'")
    handle_validate_environment_conversion_inputs(
        df=df,
        timestamp_col=timestamp_col,
        participant_col=participant_col,
        participant_override=participant_override,
        session_col=session_col,
        session_override=session_override,
        location_col=location_col,
        lat_col=lat_col,
        lon_col=lon_col,
        location_label_override=location_label_override,
        lat_manual=lat_manual,
        lon_manual=lon_manual,
        bids_label=_bids_label,
        log_callback=log_callback,
    )

    project_sessions: dict[str, str | None] = {}
    session_warnings: list[str] = []
    rows_out: list[dict] = []
    skipped = 0
    fallback_idx = 1
    env_day_cache: dict[tuple[str, float, float], dict[str, dict]] = {}
    geocode_cache: dict[str, tuple[float, float] | None] = {}

    source_df = df
    pilot_subject_label: str | None = None
    progress_total_rows = max(1, int(len(df)))
    last_progress_pct = -1

    project_root_path = resolve_active_project_root()
    persistent_cache_path = (
        project_root_path / ".prism" / "environment_provider_cache.json"
    )
    persistent_cache = _load_environment_provider_cache(persistent_cache_path)
    persistent_cache_dirty = False
    cache_hits = 0
    if pilot_random_subject:
        if participant_col and participant_col in df.columns:
            participants = [
                str(value).strip()
                for value in df[participant_col].tolist()
                if str(value).strip()
                and str(value).strip().lower() not in {"nan", "none", "n/a"}
            ]
            unique_participants = sorted(set(participants))
            if unique_participants:
                pilot_subject_label = random.choice(  # noqa: S311 - pilot sample pick, not security-sensitive
                    unique_participants
                )
                df = df[
                    df[participant_col].astype(str).str.strip() == pilot_subject_label
                ]
                log_callback(
                    f"Pilot mode: selected random subject '{pilot_subject_label}' ({len(df)} row(s) of {len(source_df)} total)",
                    "info",
                )
            else:
                random_index = random.choice(  # noqa: S311 - pilot sample pick, not security-sensitive
                    list(df.index)
                )
                df = df.loc[[random_index]]
                pilot_subject_label = "row-fallback"
                log_callback(
                    "Pilot mode: participant column had no usable values; selected 1 random row",
                    "warning",
                )
        elif len(df) > 0:
            random_index = random.choice(  # noqa: S311 - pilot sample pick, not security-sensitive
                list(df.index)
            )
            df = df.loc[[random_index]]
            pilot_subject_label = "row-fallback"
            log_callback(
                "Pilot mode: no participant column configured; selected 1 random row",
                "warning",
            )

    progress_total_rows = max(1, int(len(df)))
    if progress_callback is not None and not pilot_random_subject:
        progress_callback(0)

    raise_if_cancelled()

    inherited_sidecar_path: Path | None = None
    provider_failures: set[str] = set()

    def day_payloads(day: datetime, lat: float, lon: float, row_idx) -> dict[str, dict]:
        """Provider data of one day at one place; each day is fetched once per location (memory + project cache)."""
        nonlocal cache_hits, persistent_cache_dirty
        date_str = day.strftime("%Y-%m-%d")
        day_key = (date_str, round(lat, 4), round(lon, 4))
        if day_key not in env_day_cache:
            try:
                cache_key = _cache_key_for_day(date_str, lat, lon)
                cached_payloads = persistent_cache.get(cache_key)
                if cached_payloads:
                    cache_hits += 1
                provider_payloads, env_warnings = _fetch_environment_day(
                    day,
                    lat,
                    lon,
                    cached_payloads=cached_payloads,
                )
                env_day_cache[day_key] = provider_payloads
                if not cached_payloads or provider_payloads != cached_payloads:
                    persistent_cache[cache_key] = provider_payloads
                    persistent_cache_dirty = True
                for warning in env_warnings:
                    # Extract provider name from warning string for summary tracking
                    provider_failures.add(
                        warning.split(" API")[0] if " API" in warning else "unknown"
                    )
                    log_callback(
                        f"Row {row_idx + 1}: {warning} — continuing with partial enrichment",
                        "warning",
                    )
            except Exception as exc:
                log_callback(
                    f"Row {row_idx + 1}: environment enrichment failed unexpectedly ({exc}) — keeping core temporal fields",
                    "warning",
                )
                env_day_cache[day_key] = {
                    "weather": {},
                    "air": {},
                    "pollen": {},
                }
        return env_day_cache[day_key]

    window_problems = {
        window_column_name(w): {"column": window_column_name(w), "empty_rows": 0, "partial_rows": 0} for w in windows
    }
    longest_window = max((duration_to_timedelta(w.duration) for w in windows), default=timedelta(0))
    id_pairs: list[tuple[str, str]] = []
    ses_pairs: list[tuple[str, str]] = []
    day_first_unsure = 0

    for processed_idx, (row_idx, row) in enumerate(df.iterrows(), start=1):
        raise_if_cancelled()

        if progress_callback is not None and not pilot_random_subject:
            pct = int(round((processed_idx / progress_total_rows) * 100.0))
            pct = max(0, min(100, pct))
            if pct != last_progress_pct:
                progress_callback(pct)
                last_progress_pct = pct

        ts_raw = str(row.get(timestamp_col, "")).strip() if timestamp_col else ""
        if not ts_raw:
            log_callback(f"Row {row_idx + 1}: empty timestamp — skipped", "warning")
            skipped += 1
            continue

        dt = _parse_timestamp(ts_raw)
        if dt is None:
            log_callback(
                f"Row {row_idx + 1}: cannot parse timestamp '{ts_raw}' — skipped",
                "warning",
            )
            skipped += 1
            continue

        slash_date = re.match(r"^(\d{1,2})/(\d{1,2})/\d{4}", ts_raw)
        if slash_date and int(slash_date[1]) <= 12 and int(slash_date[2]) <= 12 and slash_date[1] != slash_date[2]:
            day_first_unsure += 1

        if participant_col and participant_col in df.columns:
            raw_pid = str(row.get(participant_col, "")).strip()
            if raw_pid:
                subject_id = _bids_label(raw_pid, "sub")
            elif participant_override:
                subject_id = _bids_label(participant_override, "sub")
            else:
                subject_id = f"sub-{fallback_idx:02d}"
        elif participant_override:
            subject_id = _bids_label(participant_override, "sub")
        else:
            subject_id = f"sub-{fallback_idx:02d}"
        if not subject_id:  # an ID with no letters or digits
            subject_id = f"sub-{fallback_idx:02d}"
        if raw_pid_for_note := (str(row.get(participant_col, "")).strip() if participant_col else ""):
            id_pairs.append((raw_pid_for_note, subject_id))
        fallback_idx += 1

        if session_col and session_col in df.columns:
            session_label = str(row.get(session_col, "")).strip() or session_override or ""
        else:
            session_label = session_override or ""
        project_session = _project_session_id(project_path, session_label, project_sessions, session_warnings)
        if project_session is not None:  # the project's Timepoints decide
            session_id = project_session
        elif session_col and session_col in df.columns:
            session_id = _bids_label(session_label or "1", "ses") or "ses-1"
        elif session_override:
            session_id = _bids_label(session_override, "ses")
        else:
            session_id = "ses-1"
        raw_session_for_note = str(row.get(session_col, "")).strip() if session_col else ""
        if raw_session_for_note:
            ses_pairs.append((raw_session_for_note, session_id))

        location_label = location_label_override or "survey-site"
        if location_col and location_col in df.columns:
            col_val = str(row.get(location_col, "")).strip()
            if col_val:
                location_label = col_val

        row_lat = None
        row_lon = None
        if lat_col and lon_col:
            row_lat = _coerce_coord(str(row.get(lat_col, "")), lat=True)
            row_lon = _coerce_coord(str(row.get(lon_col, "")), lat=False)

        if row_lat is None or row_lon is None:
            if lat_manual is not None and lon_manual is not None:
                row_lat, row_lon = lat_manual, lon_manual

        if (row_lat is None or row_lon is None) and location_label:
            geocoded = _geocode_location(location_label, geocode_cache)
            if geocoded is not None:
                row_lat, row_lon = geocoded

        if row_lat is None or row_lon is None:
            log_callback(
                f"Row {row_idx + 1}: missing/invalid geolocation (lat/lon or resolvable location) — skipped",
                "warning",
            )
            skipped += 1
            continue

        base_row = _compute_row(
            dt=dt,
            subject_id=subject_id,
            session_id=session_id,
            lat=row_lat,
        )

        base_row.update(_extract_environment_hour(dt, day_payloads(dt, row_lat, row_lon, row_idx)))
        if windows:
            first_day = (dt - longest_window).date()
            # ponytail: each day's weather request reaches 2 days back (heat status), so neighbouring window
            # days download overlapping hours; fetch the whole range in one request if volume matters.
            days = [
                day_payloads(datetime.combine(first_day + timedelta(days=n), dt.time()), row_lat, row_lon, row_idx)
                for n in range((dt.date() - first_day).days + 1)
            ]
            for spec in windows:
                name = window_column_name(spec)
                series = handle_hourly_series(days, spec.column)
                base_row[name] = compute_window(series, dt, spec)
                if base_row[name] is None:
                    window_problems[name]["empty_rows"] += 1
                elif missing_hours(series, dt, spec):
                    window_problems[name]["partial_rows"] += 1
        rows_out.append(base_row)

    if rows_out:
        for note in (
            cleaning_note([r for r, _ in id_pairs], [c for _, c in id_pairs], "participant ID", "sub-"),
            cleaning_note([r for r, _ in ses_pairs], [c for _, c in ses_pairs], "session label", "ses-"),
            *session_warnings,
        ):
            if note:
                log_callback(note, "warning")
        if day_first_unsure:
            log_callback(
                f"{day_first_unsure} timestamp(s) like 03/04/2025 were read as month/day/year; "
                "write them as 2025-04-03 or 03.04.2025 if they are day-first.",
                "warning",
            )
        for spec in windows:
            problem = window_problems[window_column_name(spec)]
            if problem["empty_rows"] or problem["partial_rows"]:
                log_callback(
                    f"{problem['column']} ({spec.column} over {spec.duration}): "
                    f"{problem['empty_rows']} row(s) left empty (no value in the window), "
                    f"{problem['partial_rows']} row(s) computed from a partial window (hours missing: not available "
                    "that far back, a failed fetch or gaps)",
                    "warning",
                )
        log_callback(f"Processed {len(rows_out)} rows ({skipped} skipped)", "success")
    else:
        log_callback(f"No rows processed ({skipped} skipped)", "warning")
        raise ValueError(
            "No valid rows could be processed — check timestamp column and format."
        )

    if persistent_cache_dirty:
        project_root_path = resolve_active_project_root()
        _save_environment_provider_cache(persistent_cache_path, persistent_cache)
        log_callback("Updated persistent environment provider cache", "info")
    elif cache_hits > 0:
        log_callback(
            f"Reused persistent cache for {cache_hits} date/location key(s)", "info"
        )

    raise_if_cancelled()
    window_columns = [window_column_name(spec) for spec in windows]
    project_root_path = resolve_active_project_root()
    written_project_paths, inherited_sidecar_path = handle_persist_environment_outputs(
        input_path=input_path,
        rows_out=rows_out,
        project_root_path=project_root_path,
        write_environment_tsv=lambda rows, path: _write_environment_tsv(rows, path, OUTPUT_COLUMNS + window_columns),
        write_environment_sidecar=lambda path: _write_environment_sidecar(path, windows),
        environment_conversion_cancelled_error_cls=EnvironmentConversionCancelledError,
        check_and_update_bidsignore=check_and_update_bidsignore,
        log_callback=log_callback,
        raise_if_cancelled=raise_if_cancelled,
    )

    # Writes sub-*/ses-*/environment/ straight into the project root (CLI and Studio).
    from src.modality_versions import pin_after_import

    pin_after_import(project_root_path)
    schema_pin_change = _move_retired_environment_pin(project_root_path, log_callback)

    elapsed_seconds = max(0.0, perf_counter() - conversion_started_at)
    estimated_total_seconds = None
    if pilot_random_subject and len(df) > 0 and len(source_df) > len(df):
        estimated_total_seconds = round(elapsed_seconds * (len(source_df) / len(df)), 2)
        log_callback(
            f"Pilot estimate: full run may take ~{estimated_total_seconds:.2f}s for {len(source_df)} source row(s)",
            "info",
        )

    return {
        "row_count": len(rows_out),
        "skipped": skipped,
        "provider_failures": sorted(provider_failures),
        "window_problems": [p for p in window_problems.values() if p["empty_rows"] or p["partial_rows"]],
        "project_environment_path": (
            written_project_paths[0] if written_project_paths else ""
        ),
        "project_environment_paths": written_project_paths,
        "project_environment_sidecar_path": str(inherited_sidecar_path),
        "output_preview": _build_environment_preview(rows_out, window_columns),
        "pilot_mode": pilot_random_subject,
        "pilot_subject": pilot_subject_label,
        "elapsed_seconds": round(elapsed_seconds, 2),
        "estimated_total_seconds": estimated_total_seconds,
        "source_row_count": int(len(source_df)),
        "schema_pin_change": schema_pin_change,
    }
