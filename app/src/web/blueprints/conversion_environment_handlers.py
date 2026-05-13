"""
Environment conversion handlers for the Prism Web UI.

Accepts a tabular file (xlsx/csv/tsv/sav/rds/rdata) from a survey export, maps columns for
timestamp, participant ID, session, and optional location, then derives
privacy-safe environmental context metadata (time-based anchors, sun/moon
phase, season) and writes a PRISM-compatible environment.tsv.

The converter enriches rows with live Open-Meteo lookups when coordinates are
available. Provider failures are treated as partial-enrichment warnings so
conversion can still finish with the core temporal fields intact.
"""

from __future__ import annotations

import csv
import io
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
import logging
import threading
from contextlib import redirect_stderr, redirect_stdout
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from time import sleep
from time import perf_counter
from types import SimpleNamespace
from typing import Any

import pandas as pd
from src.converters.file_reader import infer_tabular_kind, read_tabular_file
import requests
from flask import request, jsonify, session
from werkzeug.utils import secure_filename

from src.system_files import filter_system_files  # noqa: F401 – available if needed
from src.bids_integration import check_and_update_bidsignore
from .conversion_job_store import ConversionJobStore
from .conversion_environment_route_handlers import (
    handle_api_environment_convert_cancel,
    handle_api_environment_convert_metrics,
    handle_api_environment_convert_start,
    handle_api_environment_convert_status,
    handle_api_environment_preview,
)
from .conversion_environment_job_handlers import (
    handle_run_environment_detached_job,
    handle_run_environment_job,
    handle_start_environment_detached_job,
)
from .conversion_environment_config_helpers import (
    handle_build_environment_conversion_config_from_request,
)
from .conversion_environment_provider_helpers import (
    handle_cache_key_for_day,
    handle_extract_environment_hour,
    handle_fetch_environment_day,
    handle_fetch_environment_hour,
    handle_hourly_value,
    handle_load_environment_provider_cache,
    handle_payload_has_hourly_data,
    handle_pollen_risk_bin,
    handle_save_environment_provider_cache,
)
from .conversion_environment_result_helpers import (
    handle_persist_environment_outputs,
)
from .conversion_environment_engine_helpers import (
    handle_validate_environment_conversion_inputs,
)
from .conversion_request_helpers import (
    resolve_uploaded_or_source_file as _shared_resolve_uploaded_or_source_file,
)
from .conversion_utils import (
    read_tabular_dataframe_robust,
    expected_delimiter_for_suffix,
    normalize_separator_option,
    require_existing_project_root,
)

logger = logging.getLogger(__name__)

_environment_job_store = ConversionJobStore(log_level_key="type")
_environment_jobs_lock = _environment_job_store.lock
_environment_jobs = _environment_job_store.jobs
_environment_detached_jobs_lock = threading.Lock()
_environment_detached_jobs: dict[str, dict[str, Any]] = {}


class EnvironmentConversionCancelledError(Exception):
    """Raised when an environment conversion is cancelled by the user."""


def _resolve_uploaded_or_source_file(*, field_names: tuple[str, ...]):
    return _shared_resolve_uploaded_or_source_file(
        field_names=field_names,
        missing_input_message="No file provided",
    )


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
    "filename",
    "relative_time",
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
    if 0 <= hour <= 5:
        return "night"
    if 6 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 17:
        return "afternoon"
    return "evening"


def _season_code(doy: int) -> str:
    if 80 <= doy <= 171:
        return "spring"
    if 172 <= doy <= 263:
        return "summer"
    if 264 <= doy <= 354:
        return "autumn"
    return "winter"


def _estimate_daylight(doy: int, lat: float = 47.0) -> float:
    seasonal = 4.0 * math.sin((2 * math.pi * (doy - 80)) / 365.0)
    lat_factor = min(max(abs(lat) / 90.0, 0.0), 1.0)
    return round(max(4.0, min(20.0, 12.0 + seasonal * (0.5 + lat_factor))), 1)


def _sun_phase(hour: int, daylight: float) -> str:
    sunrise = 12.0 - daylight / 2.0
    sunset = 12.0 + daylight / 2.0
    if hour < sunrise or hour > sunset:
        return "night"
    if sunrise <= hour < sunrise + 1.5:
        return "dawn"
    if sunset - 1.5 < hour <= sunset:
        return "dusk"
    return "day"


def _hours_since_sun(hour: int, daylight: float) -> float:
    sunrise = 12.0 - daylight / 2.0
    sunset = 12.0 + daylight / 2.0
    if sunrise <= hour <= sunset:
        return 0.0
    if hour > sunset:
        return round(hour - sunset, 1)
    return round((24.0 - sunset) + hour, 1)


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
    v = str(value or "").strip()
    if not v or v.lower() in ("nan", "none", "n/a"):
        return ""
    if v.startswith(f"{prefix}-"):
        return v
    return f"{prefix}-{v}"


def _compute_row(
    dt: datetime,
    subject_id: str,
    session_id: str,
    filename: str,
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
        "filename": filename,
        "relative_time": f"{dt.year}-DOY{doy:03d}-H{hour:02d}",
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


def _geocode_location(
    label: str, cache: dict[str, tuple[float, float] | None]
) -> tuple[float, float] | None:
    key = (label or "").strip().lower()
    if not key:
        return None
    if key in cache:
        return cache[key]

    params: dict[str, str | int] = {
        "name": label,
        "count": 1,
        "language": "en",
        "format": "json",
    }
    try:
        response = requests.get(
            GEOCODING_URL,
            params=params,
            timeout=GEOCODING_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        first = (payload.get("results") or [None])[0]
        if not first:
            cache[key] = None
            return None
        lat = first.get("latitude")
        lon = first.get("longitude")
        if lat is None or lon is None:
            cache[key] = None
            return None
        coords = (float(lat), float(lon))
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


def _form_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    return default


def _parse_detached_log_lines(
    log_path: Path, cursor: int
) -> tuple[list[dict[str, str]], int]:
    if not log_path.exists():
        return [], cursor

    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    bounded_cursor = max(0, min(cursor, len(lines)))
    new_lines = lines[bounded_cursor:]
    parsed: list[dict[str, str]] = []
    for line in new_lines:
        if "\t" in line:
            level, message = line.split("\t", 1)
            level_norm = level.strip().lower() or "info"
        else:
            level_norm = "info"
            message = line
        parsed.append({"type": level_norm, "message": message})

    return parsed, len(lines)


def _append_environment_job_log(job_id: str, message: str, level: str = "info") -> None:
    _environment_job_store.append_log(job_id, message, level)


def _is_environment_job_cancelled(job_id: str) -> bool:
    """Check if job has been marked for cancellation."""
    return _environment_job_store.is_cancelled(job_id)


def _mark_environment_job_cancelled(job_id: str) -> bool:
    """Mark job as cancelled. Returns True if job existed."""
    return _environment_job_store.cancel(job_id)


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


def _build_environment_preview(rows_out: list[dict]) -> dict:
    preview_columns = [
        "subject_id",
        "session_id",
        "relative_time",
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
    ]
    preview_rows = [
        [_preview_value(row.get(col)) for col in preview_columns]
        for row in rows_out[:4]
    ]
    return {
        "columns": preview_columns,
        "rows": preview_rows,
    }


def _build_environment_sidecar() -> dict[str, Any]:
    return {
        "Metadata": {
            "SchemaVersion": "1.1.0",
            "CreationDate": datetime.now(timezone.utc).date().isoformat(),
            "Creator": "PRISM Environment Converter",
        },
        "Privacy": {
            "AnchorField": "season_code",
            "IncludesRawDatetime": False,
            "IncludesExactGeo": False,
            "Derivation": "Derived from privacy-safe temporal anchors and approximate location context.",
        },
        "Provenance": {
            "Builder": "PRISM Environment Converter",
            "BuilderVersion": "1.1.0",
            "Providers": ["weather", "air_quality", "pollen"],
            "SpatialResolution": "city",
            "TemporalResolution": "hourly",
        },
        "Columns": {
            "subject_id": {"Description": "BIDS subject identifier"},
            "session_id": {"Description": "BIDS session identifier"},
            "filename": {"Description": "Source filename from survey export"},
            "relative_time": {"Description": "Privacy-safe temporal token"},
            "hour_bin": {
                "Description": "Binned hour derived from temporal anchor",
                "Levels": {
                    "night": "00-05",
                    "morning": "06-11",
                    "afternoon": "12-17",
                    "evening": "18-23",
                    "unknown": "not derivable",
                },
            },
            "season_code": {"Description": "Season bin derived from day-of-year"},
            "sun_phase": {"Description": "Solar phase at acquisition"},
            "sun_hours_today": {
                "Description": "Estimated daylight duration",
                "Units": "hours",
            },
            "hours_since_sun": {
                "Description": "Hours since last sunlight",
                "Units": "hours",
            },
            "elevation_m": {
                "Description": "Approximate elevation at resolved coordinate",
                "Units": "m",
                "Source": "weather",
            },
            "heatwave_status": {
                "Description": "Derived heat status from daily max temperatures over current and previous two days",
                "Source": "weather",
            },
            "moon_phase": {"Description": "Moon phase at acquisition"},
            "moon_illumination_pct": {
                "Description": "Estimated moon illumination",
                "Units": "percent",
            },
            "temp_c": {
                "Description": "Ambient temperature",
                "Units": "degC",
                "Source": "weather",
            },
            "apparent_temp_c": {
                "Description": "Apparent temperature",
                "Units": "degC",
                "Source": "weather",
            },
            "dew_point_c": {
                "Description": "Dew point temperature",
                "Units": "degC",
                "Source": "weather",
            },
            "humidity_pct": {
                "Description": "Relative humidity",
                "Units": "percent",
                "Source": "weather",
            },
            "pressure_hpa": {
                "Description": "Surface pressure",
                "Units": "hPa",
                "Source": "weather",
            },
            "precip_mm": {
                "Description": "Precipitation",
                "Units": "mm",
                "Source": "weather",
            },
            "wind_speed_ms": {
                "Description": "Wind speed",
                "Units": "m/s",
                "Source": "weather",
            },
            "cloud_cover_pct": {
                "Description": "Cloud cover",
                "Units": "percent",
                "Source": "weather",
            },
            "uv_index": {"Description": "UV index", "Source": "weather"},
            "shortwave_radiation_wm2": {
                "Description": "Shortwave radiation",
                "Units": "W/m2",
                "Source": "weather",
            },
            "weather_regime": {
                "Description": "Derived weather regime",
                "Source": "weather",
            },
            "aqi": {"Description": "Air quality index", "Source": "air_quality"},
            "pm25_ug_m3": {
                "Description": "PM2.5",
                "Units": "ug/m3",
                "Source": "air_quality",
            },
            "pm10_ug_m3": {
                "Description": "PM10",
                "Units": "ug/m3",
                "Source": "air_quality",
            },
            "no2_ug_m3": {
                "Description": "Nitrogen dioxide",
                "Units": "ug/m3",
                "Source": "air_quality",
            },
            "o3_ug_m3": {
                "Description": "Ozone",
                "Units": "ug/m3",
                "Source": "air_quality",
            },
            "pollen_birch": {"Description": "Birch pollen index", "Source": "pollen"},
            "pollen_grass": {"Description": "Grass pollen index", "Source": "pollen"},
            "pollen_mugwort": {
                "Description": "Mugwort pollen index",
                "Source": "pollen",
            },
            "pollen_ragweed": {
                "Description": "Ragweed pollen index",
                "Source": "pollen",
            },
            "pollen_total": {"Description": "Total pollen index", "Source": "pollen"},
            "pollen_risk_bin": {
                "Description": "Derived pollen risk bin",
                "Source": "pollen",
            },
        },
    }


def _write_environment_tsv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_environment_sidecar(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_payload = _build_environment_sidecar()
    path.write_text(json.dumps(sidecar_payload, indent=2), encoding="utf-8")


def _run_environment_detached_job(config_path: str) -> None:
    handle_run_environment_detached_job(
        config_path=config_path,
        perform_environment_conversion=_perform_environment_conversion,
        environment_conversion_cancelled_error_cls=EnvironmentConversionCancelledError,
        logger=logger,
    )


def _start_environment_detached_job(
    config: dict[str, Any],
) -> tuple[str, int, Path, Path]:
    return handle_start_environment_detached_job(
        config=config,
        environment_detached_jobs_lock=_environment_detached_jobs_lock,
        environment_detached_jobs=_environment_detached_jobs,
    )


def _perform_environment_conversion(
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
    job_id: str | None = None,
    cancel_check=None,
) -> dict:
    def should_cancel() -> bool:
        if cancel_check is not None and cancel_check():
            return True
        return bool(job_id and _is_environment_job_cancelled(job_id))

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
                pilot_subject_label = random.choice(unique_participants)
                df = df[
                    df[participant_col].astype(str).str.strip() == pilot_subject_label
                ]
                log_callback(
                    f"Pilot mode: selected random subject '{pilot_subject_label}' ({len(df)} row(s) of {len(source_df)} total)",
                    "info",
                )
            else:
                random_index = random.choice(list(df.index))
                df = df.loc[[random_index]]
                pilot_subject_label = "row-fallback"
                log_callback(
                    "Pilot mode: participant column had no usable values; selected 1 random row",
                    "warning",
                )
        elif len(df) > 0:
            random_index = random.choice(list(df.index))
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

    written_project_paths_for_cleanup: list[Path] = []
    inherited_sidecar_path: Path | None = None
    provider_failures: set[str] = set()

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
        fallback_idx += 1

        if session_col and session_col in df.columns:
            raw_ses = str(row.get(session_col, "")).strip()
            session_id = _bids_label(raw_ses or session_override or "01", "ses")
        elif session_override:
            session_id = _bids_label(session_override, "ses")
        else:
            session_id = "ses-01"

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
            filename=filename,
            lat=row_lat,
        )

        date_str = dt.strftime("%Y-%m-%d")
        day_key = (date_str, round(row_lat, 4), round(row_lon, 4))
        if day_key not in env_day_cache:
            try:
                cache_key = _cache_key_for_day(date_str, row_lat, row_lon)
                cached_payloads = persistent_cache.get(cache_key)
                if cached_payloads:
                    cache_hits += 1
                provider_payloads, env_warnings = _fetch_environment_day(
                    dt,
                    row_lat,
                    row_lon,
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
        base_row.update(_extract_environment_hour(dt, env_day_cache[day_key]))
        rows_out.append(base_row)

    if rows_out:
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
    project_root_path = resolve_active_project_root()
    written_project_paths, inherited_sidecar_path = handle_persist_environment_outputs(
        input_path=input_path,
        rows_out=rows_out,
        project_root_path=project_root_path,
        write_environment_tsv=_write_environment_tsv,
        write_environment_sidecar=_write_environment_sidecar,
        environment_conversion_cancelled_error_cls=EnvironmentConversionCancelledError,
        check_and_update_bidsignore=check_and_update_bidsignore,
        log_callback=log_callback,
        raise_if_cancelled=raise_if_cancelled,
    )

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
        "project_environment_path": (
            written_project_paths[0] if written_project_paths else ""
        ),
        "project_environment_paths": written_project_paths,
        "project_environment_sidecar_path": str(inherited_sidecar_path),
        "output_preview": _build_environment_preview(rows_out),
        "pilot_mode": pilot_random_subject,
        "pilot_subject": pilot_subject_label,
        "elapsed_seconds": round(elapsed_seconds, 2),
        "estimated_total_seconds": estimated_total_seconds,
        "source_row_count": int(len(source_df)),
    }


def _run_environment_job(job_id: str, config: dict[str, Any]) -> None:
    handle_run_environment_job(
        job_id=job_id,
        config=config,
        is_environment_job_cancelled=_is_environment_job_cancelled,
        append_environment_job_log=_append_environment_job_log,
        environment_job_store=_environment_job_store,
        perform_environment_conversion=_perform_environment_conversion,
        environment_conversion_cancelled_error_cls=EnvironmentConversionCancelledError,
        logger=logger,
    )


def _build_environment_conversion_config_from_request() -> (
    tuple[dict[str, Any], tempfile.TemporaryDirectory | None]
):
    return handle_build_environment_conversion_config_from_request(
        resolve_uploaded_or_source_file=_resolve_uploaded_or_source_file,
        allowed_suffixes=ALLOWED_SUFFIXES,
        normalize_separator_option=normalize_separator_option,
        form_bool=_form_bool,
        coerce_coord=_coerce_coord,
        require_existing_project_root=require_existing_project_root,
    )


# ── API endpoints ──────────────────────────────────────────────────────────────


def api_environment_location_search():
    """Search known locations and return selectable coordinates."""
    query = (request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify({"error": "Query too short"}), 400

    params = {
        "name": query,
        "count": 8,
        "language": "en",
        "format": "json",
    }

    try:
        response = requests.get(
            GEOCODING_URL,
            params=params,
            timeout=GEOCODING_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        raw_results = payload.get("results") or []
        results: list[dict[str, Any]] = []
        for item in raw_results:
            name = (item.get("name") or "").strip()
            admin1 = (item.get("admin1") or "").strip()
            country = (item.get("country") or "").strip()
            label_parts = [part for part in [name, admin1, country] if part]
            label = ", ".join(label_parts) if label_parts else name
            lat = item.get("latitude")
            lon = item.get("longitude")
            if lat is None or lon is None:
                continue
            results.append(
                {
                    "name": name,
                    "display_name": label,
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "timezone": item.get("timezone") or "",
                }
            )
        return jsonify({"results": results})
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502


def api_environment_preview():
    return handle_api_environment_preview(
        resolve_uploaded_or_source_file=_resolve_uploaded_or_source_file,
        allowed_suffixes=ALLOWED_SUFFIXES,
        normalize_separator_option=normalize_separator_option,
    )


def api_environment_convert_start():
    return handle_api_environment_convert_start(
        build_environment_conversion_config_from_request=_build_environment_conversion_config_from_request,
        start_environment_detached_job=_start_environment_detached_job,
        logger=logger,
        environment_job_store=_environment_job_store,
        append_environment_job_log=_append_environment_job_log,
        run_environment_job=_run_environment_job,
    )


def api_environment_convert_cancel(job_id: str):
    return handle_api_environment_convert_cancel(
        job_id=job_id,
        mark_environment_job_cancelled=_mark_environment_job_cancelled,
        append_environment_job_log=_append_environment_job_log,
        environment_detached_jobs_lock=_environment_detached_jobs_lock,
        environment_detached_jobs=_environment_detached_jobs,
    )


def api_environment_convert_metrics():
    return handle_api_environment_convert_metrics(
        environment_job_store=_environment_job_store,
        environment_detached_jobs_lock=_environment_detached_jobs_lock,
        environment_detached_jobs=_environment_detached_jobs,
    )


def api_environment_convert_status(job_id: str):
    return handle_api_environment_convert_status(
        job_id=job_id,
        environment_job_store=_environment_job_store,
        environment_detached_jobs_lock=_environment_detached_jobs_lock,
        environment_detached_jobs=_environment_detached_jobs,
        parse_detached_log_lines=_parse_detached_log_lines,
    )
