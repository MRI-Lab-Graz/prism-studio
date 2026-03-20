"""
Environment conversion handlers for the Prism Web UI.

Accepts a tabular file (xlsx/csv/tsv) from a survey export, maps columns for
timestamp, participant ID, session, and optional location, then derives
privacy-safe environmental context metadata (time-based anchors, sun/moon
phase, season) and writes a PRISM-compatible environment.tsv.

The converter enriches rows with live Open-Meteo lookups when coordinates are
available. Provider failures are treated as partial-enrichment warnings so
conversion can still finish with the core temporal fields intact.
"""

from __future__ import annotations

import csv
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from time import sleep
from time import perf_counter
from typing import Any

import pandas as pd
import requests
from flask import request, jsonify, session
from werkzeug.utils import secure_filename

from src.system_files import filter_system_files  # noqa: F401 – available if needed
from src.bids_integration import check_and_update_bidsignore
from .conversion_utils import (
    read_tabular_dataframe_robust,
    expected_delimiter_for_suffix,
    normalize_separator_option,
)

logger = logging.getLogger(__name__)

_environment_jobs_lock = threading.Lock()
_environment_jobs: dict[str, dict[str, Any]] = {}
_environment_detached_jobs_lock = threading.Lock()
_environment_detached_jobs: dict[str, dict[str, Any]] = {}

ALLOWED_SUFFIXES = {".xlsx", ".csv", ".tsv"}
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
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    values = hourly.get(key) or []
    if not times or not values:
        return None
    try:
        idx = times.index(timestamp_iso)
    except ValueError:
        return None
    if idx >= len(values):
        return None
    value = values[idx]
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pollen_risk_bin(total: float | None) -> str:
    if total is None:
        return "unknown"
    if total < 50:
        return "low"
    if total < 150:
        return "medium"
    if total < 300:
        return "high"
    return "very_high"


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
    if not isinstance(payload, dict):
        return False
    hourly = payload.get("hourly")
    return isinstance(hourly, dict) and bool(hourly)


def _cache_key_for_day(date_str: str, lat: float, lon: float) -> str:
    return f"{date_str}|{round(lat, 4):.4f}|{round(lon, 4):.4f}"


def _load_environment_provider_cache(cache_path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    if not cache_path.exists():
        return {}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, dict):
        return {}
    cleaned: dict[str, dict[str, dict[str, Any]]] = {}
    for key, value in entries.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        cleaned[key] = {
            "weather": value.get("weather") if isinstance(value.get("weather"), dict) else {},
            "air": value.get("air") if isinstance(value.get("air"), dict) else {},
            "pollen": value.get("pollen") if isinstance(value.get("pollen"), dict) else {},
        }
    return cleaned


def _save_environment_provider_cache(
    cache_path: Path,
    entries: dict[str, dict[str, dict[str, Any]]],
) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "entries": entries,
    }
    cache_path.write_text(json.dumps(payload), encoding="utf-8")


def _fetch_environment_day(
    dt: datetime,
    lat: float,
    lon: float,
    *,
    cached_payloads: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, dict], list[str]]:
    date_str = dt.strftime("%Y-%m-%d")
    weather_start_date = (dt - timedelta(days=2)).strftime("%Y-%m-%d")
    warnings: list[str] = []

    weather_params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": weather_start_date,
        "end_date": date_str,
        "hourly": ",".join(
            [
                "temperature_2m",
                "apparent_temperature",
                "dew_point_2m",
                "relative_humidity_2m",
                "surface_pressure",
                "precipitation",
                "wind_speed_10m",
                "cloud_cover",
                "uv_index",
                "shortwave_radiation",
            ]
        ),
        "timezone": "auto",
    }
    air_params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": ",".join(["european_aqi", "pm2_5", "pm10", "nitrogen_dioxide", "ozone"]),
        "timezone": "auto",
    }
    pollen_params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": ",".join(["birch_pollen", "grass_pollen", "mugwort_pollen", "ragweed_pollen"]),
        "timezone": "auto",
    }
    provider_payloads: dict[str, dict] = {
        "weather": dict((cached_payloads or {}).get("weather") or {}),
        "air": dict((cached_payloads or {}).get("air") or {}),
        "pollen": dict((cached_payloads or {}).get("pollen") or {}),
    }

    provider_requests = [
        ("Weather archive", "weather", WEATHER_ARCHIVE_URL, weather_params, WEATHER_TIMEOUT_SECONDS),
        ("Air quality", "air", AIR_QUALITY_URL, air_params, AIR_QUALITY_TIMEOUT_SECONDS),
        ("Pollen", "pollen", AIR_QUALITY_URL, pollen_params, POLLEN_TIMEOUT_SECONDS),
    ]

    missing_requests = [
        (provider_name, payload_key, url, params, timeout)
        for provider_name, payload_key, url, params, timeout in provider_requests
        if not _payload_has_hourly_data(provider_payloads.get(payload_key))
    ]

    if not missing_requests:
        return {
            "weather": provider_payloads["weather"],
            "air": provider_payloads["air"],
            "pollen": provider_payloads["pollen"],
        }, warnings

    with ThreadPoolExecutor(max_workers=len(missing_requests)) as pool:
        futures = {
            pool.submit(_fetch_provider_json, url, params, timeout): (provider_name, payload_key)
            for provider_name, payload_key, url, params, timeout in missing_requests
        }
        for future in as_completed(futures):
            provider_name, payload_key = futures[future]
            try:
                provider_payloads[payload_key] = future.result()
            except requests.RequestException as exc:
                warnings.append(_provider_warning(provider_name, exc))

    return {
        "weather": provider_payloads["weather"],
        "air": provider_payloads["air"],
        "pollen": provider_payloads["pollen"],
    }, warnings


def _extract_environment_hour(dt: datetime, provider_payloads: dict[str, dict]) -> dict:
    hour_iso = dt.strftime("%Y-%m-%dT%H:00")
    weather = provider_payloads.get("weather") or {}
    air = provider_payloads.get("air") or {}
    pollen = provider_payloads.get("pollen") or {}

    def _daily_max_temp(date_key: str) -> float | None:
        hourly = weather.get("hourly") or {}
        times = hourly.get("time") or []
        temps = hourly.get("temperature_2m") or []
        if not times or not temps:
            return None
        values: list[float] = []
        for idx, ts in enumerate(times):
            if idx >= len(temps):
                break
            if not str(ts).startswith(date_key):
                continue
            try:
                values.append(float(temps[idx]))
            except (TypeError, ValueError):
                continue
        return max(values) if values else None

    date_0 = dt.strftime("%Y-%m-%d")
    date_m1 = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    date_m2 = (dt - timedelta(days=2)).strftime("%Y-%m-%d")
    max_0 = _daily_max_temp(date_0)
    max_m1 = _daily_max_temp(date_m1)
    max_m2 = _daily_max_temp(date_m2)

    heatwave_status = "unknown"
    if max_0 is not None:
        heatwave_status = "normal"
        if max_0 >= 25.0:
            heatwave_status = "warm_day"
        if max_0 >= 30.0:
            heatwave_status = "hot_day"
        if (
            max_0 >= 30.0
            and max_m1 is not None
            and max_m2 is not None
            and max_m1 >= 30.0
            and max_m2 >= 30.0
        ):
            heatwave_status = "heatwave"

    elevation_m = None
    if weather.get("elevation") is not None:
        try:
            elevation_m = float(weather.get("elevation"))
        except (TypeError, ValueError):
            elevation_m = None

    pressure = _hourly_value(weather, "surface_pressure", hour_iso)
    weather_regime = "frontal"
    if pressure is not None:
        if pressure >= 1020.0:
            weather_regime = "hochdruck"
        elif pressure <= 1000.0:
            weather_regime = "tiefdruck"

    birch = _hourly_value(pollen, "birch_pollen", hour_iso)
    grass = _hourly_value(pollen, "grass_pollen", hour_iso)
    mugwort = _hourly_value(pollen, "mugwort_pollen", hour_iso)
    ragweed = _hourly_value(pollen, "ragweed_pollen", hour_iso)

    pollen_vals = [v for v in (birch, grass, mugwort, ragweed) if v is not None]
    pollen_total = float(sum(pollen_vals)) if pollen_vals else None

    return {
        "temp_c": _hourly_value(weather, "temperature_2m", hour_iso),
        "apparent_temp_c": _hourly_value(weather, "apparent_temperature", hour_iso),
        "dew_point_c": _hourly_value(weather, "dew_point_2m", hour_iso),
        "humidity_pct": _hourly_value(weather, "relative_humidity_2m", hour_iso),
        "pressure_hpa": pressure,
        "precip_mm": _hourly_value(weather, "precipitation", hour_iso),
        "wind_speed_ms": _hourly_value(weather, "wind_speed_10m", hour_iso),
        "cloud_cover_pct": _hourly_value(weather, "cloud_cover", hour_iso),
        "uv_index": _hourly_value(weather, "uv_index", hour_iso),
        "shortwave_radiation_wm2": _hourly_value(weather, "shortwave_radiation", hour_iso),
        "weather_regime": weather_regime,
        "elevation_m": elevation_m,
        "heatwave_status": heatwave_status,
        "aqi": _hourly_value(air, "european_aqi", hour_iso),
        "pm25_ug_m3": _hourly_value(air, "pm2_5", hour_iso),
        "pm10_ug_m3": _hourly_value(air, "pm10", hour_iso),
        "no2_ug_m3": _hourly_value(air, "nitrogen_dioxide", hour_iso),
        "o3_ug_m3": _hourly_value(air, "ozone", hour_iso),
        "pollen_birch": birch,
        "pollen_grass": grass,
        "pollen_mugwort": mugwort,
        "pollen_ragweed": ragweed,
        "pollen_total": pollen_total,
        "pollen_risk_bin": _pollen_risk_bin(pollen_total),
    }


def _fetch_environment_hour(dt: datetime, lat: float, lon: float) -> tuple[dict, list[str]]:
    provider_payloads, warnings = _fetch_environment_day(dt, lat, lon)
    return _extract_environment_hour(dt, provider_payloads), warnings


# ── Column auto-detection helpers ─────────────────────────────────────────────

_CANDIDATE_PARTICIPANT = [
    "participant_id", "subject_id", "participant", "subject", "id",
    "prolific_pid", "workerid", "worker_id", "responseid", "response_id",
]
_CANDIDATE_SESSION = [
    "session_id", "session", "ses", "wave", "timepoint", "visit",
]
_CANDIDATE_TIMESTAMP = [
    "timestamp", "datetime", "date_time", "startdate", "start_date",
    "enddate", "end_date", "submitdate", "submit_date", "datestamp",
    "date", "time", "created_at", "date_submitted", "submission_date",
    "assessment_date", "interview_date",
]
_CANDIDATE_LOCATION = [
    "location", "site", "location_label", "study_site", "country",
    "city", "place", "lab", "center",
]
_CANDIDATE_LAT = [
    "lat", "latitude", "gps_lat", "geo_lat", "location_lat", "site_lat",
]
_CANDIDATE_LON = [
    "lon", "long", "lng", "longitude", "gps_lon", "geo_lon", "location_lon", "site_lon",
]


def _detect_col(candidates: list[str], columns: list[str]) -> str | None:
    cols_lower = {c.lower(): c for c in columns}
    for c in candidates:
        if c in cols_lower:
            return cols_lower[c]
    return None


def _compatibility_report(df: pd.DataFrame, columns: list[str], timestamp_col: str | None) -> dict:
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
        warnings.append("No geo columns auto-detected (lat/lon or location); provide global fallback coordinates.")
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


def _geocode_location(label: str, cache: dict[str, tuple[float, float] | None]) -> tuple[float, float] | None:
    key = (label or "").strip().lower()
    if not key:
        return None
    if key in cache:
        return cache[key]

    params = {
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


def _parse_detached_log_lines(log_path: Path, cursor: int) -> tuple[list[dict[str, str]], int]:
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
    with _environment_jobs_lock:
        job = _environment_jobs.get(job_id)
        if not job:
            return
        job["logs"].append({"message": message, "type": level})


def _load_environment_dataframe(
    input_path: Path,
    *,
    suffix: str,
    separator_option: str,
) -> pd.DataFrame:
    if suffix == ".xlsx":
        return pd.read_excel(input_path, dtype=str)
    delimiter = expected_delimiter_for_suffix(suffix, separator_option)
    return read_tabular_dataframe_robust(
        input_path,
        expected_delimiter=delimiter,
        dtype=str,
    )


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
            "sun_hours_today": {"Description": "Estimated daylight duration", "Units": "hours"},
            "hours_since_sun": {"Description": "Hours since last sunlight", "Units": "hours"},
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
            "moon_illumination_pct": {"Description": "Estimated moon illumination", "Units": "percent"},
            "temp_c": {"Description": "Ambient temperature", "Units": "degC", "Source": "weather"},
            "apparent_temp_c": {"Description": "Apparent temperature", "Units": "degC", "Source": "weather"},
            "dew_point_c": {"Description": "Dew point temperature", "Units": "degC", "Source": "weather"},
            "humidity_pct": {"Description": "Relative humidity", "Units": "percent", "Source": "weather"},
            "pressure_hpa": {"Description": "Surface pressure", "Units": "hPa", "Source": "weather"},
            "precip_mm": {"Description": "Precipitation", "Units": "mm", "Source": "weather"},
            "wind_speed_ms": {"Description": "Wind speed", "Units": "m/s", "Source": "weather"},
            "cloud_cover_pct": {"Description": "Cloud cover", "Units": "percent", "Source": "weather"},
            "uv_index": {"Description": "UV index", "Source": "weather"},
            "shortwave_radiation_wm2": {
                "Description": "Shortwave radiation",
                "Units": "W/m2",
                "Source": "weather",
            },
            "weather_regime": {"Description": "Derived weather regime", "Source": "weather"},
            "aqi": {"Description": "Air quality index", "Source": "air_quality"},
            "pm25_ug_m3": {"Description": "PM2.5", "Units": "ug/m3", "Source": "air_quality"},
            "pm10_ug_m3": {"Description": "PM10", "Units": "ug/m3", "Source": "air_quality"},
            "no2_ug_m3": {"Description": "Nitrogen dioxide", "Units": "ug/m3", "Source": "air_quality"},
            "o3_ug_m3": {"Description": "Ozone", "Units": "ug/m3", "Source": "air_quality"},
            "pollen_birch": {"Description": "Birch pollen index", "Source": "pollen"},
            "pollen_grass": {"Description": "Grass pollen index", "Source": "pollen"},
            "pollen_mugwort": {"Description": "Mugwort pollen index", "Source": "pollen"},
            "pollen_ragweed": {"Description": "Ragweed pollen index", "Source": "pollen"},
            "pollen_total": {"Description": "Total pollen index", "Source": "pollen"},
            "pollen_risk_bin": {"Description": "Derived pollen risk bin", "Source": "pollen"},
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
    config_file = Path(config_path)
    payload = json.loads(config_file.read_text(encoding="utf-8"))

    log_path = Path(payload["log_path"])
    result_path = Path(payload["result_path"])
    config = payload["config"]

    def log_callback(message: str, level: str = "info") -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"{level}\t{message}\n")

    config["input_path"] = Path(config["input_path"])
    log_callback("🌍 Environment conversion job started", "info")

    result_payload: dict[str, Any]
    try:
        result = _perform_environment_conversion(
            input_path=config["input_path"],
            filename=config["filename"],
            suffix=config["suffix"],
            separator_option=config["separator_option"],
            timestamp_col=config["timestamp_col"],
            participant_col=config["participant_col"],
            participant_override=config["participant_override"],
            session_col=config["session_col"],
            session_override=config["session_override"],
            location_col=config["location_col"],
            lat_col=config["lat_col"],
            lon_col=config["lon_col"],
            location_label_override=config["location_label_override"],
            lat_manual=config["lat_manual"],
            lon_manual=config["lon_manual"],
            project_path=config["project_path"],
            pilot_random_subject=bool(config.get("pilot_random_subject", False)),
            log_callback=log_callback,
        )
        result_payload = {
            "done": True,
            "success": True,
            "result": result,
            "error": None,
        }
    except ValueError as exc:
        result_payload = {
            "done": True,
            "success": False,
            "result": None,
            "error": str(exc),
        }
    except Exception as exc:
        logger.exception("Detached environment conversion failed")
        result_payload = {
            "done": True,
            "success": False,
            "result": None,
            "error": str(exc),
        }
    finally:
        tmp_dir = config.get("tmp_dir")
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result_payload), encoding="utf-8")


def _start_environment_detached_job(config: dict[str, Any]) -> tuple[str, int, Path, Path]:
    project_root_path = Path(config["project_path"])
    if project_root_path.is_file():
        project_root_path = project_root_path.parent

    jobs_dir = project_root_path / ".prism" / "environment_jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)

    job_id = uuid.uuid4().hex
    log_path = jobs_dir / f"{job_id}.log"
    result_path = jobs_dir / f"{job_id}.result.json"
    config_path = jobs_dir / f"{job_id}.config.json"

    serializable_config = dict(config)
    serializable_config["input_path"] = str(config["input_path"])

    payload = {
        "config": serializable_config,
        "log_path": str(log_path),
        "result_path": str(result_path),
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    python_exec = sys.executable or "python"
    run_snippet = (
        "from src.web.blueprints.conversion_environment_handlers import _run_environment_detached_job; "
        f"_run_environment_detached_job({repr(str(config_path))})"
    )
    command = [python_exec, "-c", run_snippet]

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"info\tDetached command: {' '.join(command)}\n")
        process = subprocess.Popen(  # noqa: S603,S607
            command,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )

    with _environment_detached_jobs_lock:
        _environment_detached_jobs[job_id] = {
            "pid": int(process.pid),
            "log_path": str(log_path),
            "result_path": str(result_path),
        }

    return job_id, int(process.pid), log_path, result_path


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
) -> dict:
    conversion_started_at = perf_counter()
    df = _load_environment_dataframe(
        input_path,
        suffix=suffix,
        separator_option=separator_option,
    )

    df = df.fillna("")
    log_callback(f"Loaded {len(df)} rows, {len(df.columns)} columns from '{filename}'")

    if not timestamp_col:
        raise ValueError("Timestamp column is required")
    if not session_col and not session_override:
        raise ValueError("Session is required: choose a column or set manual session")
    if lat_col and lat_col not in df.columns:
        raise ValueError(f"Latitude column '{lat_col}' not found in file")
    if lon_col and lon_col not in df.columns:
        raise ValueError(f"Longitude column '{lon_col}' not found in file")
    if bool(lat_col) != bool(lon_col):
        raise ValueError("Select both latitude and longitude columns, or neither.")

    has_geo_source = bool(
        (lat_col and lon_col)
        or (lat_manual is not None and lon_manual is not None)
        or location_col
        or location_label_override
    )
    if not has_geo_source:
        raise ValueError(
            "No geolocation source found. Provide lat/lon columns, location column, or global coordinates."
        )
    if timestamp_col not in df.columns:
        raise ValueError(f"Timestamp column '{timestamp_col}' not found in file")
    if participant_col and participant_col not in df.columns:
        raise ValueError(f"Participant ID column '{participant_col}' not found in file")
    if session_col and session_col not in df.columns:
        raise ValueError(f"Session column '{session_col}' not found in file")

    log_callback(f"Timestamp column: '{timestamp_col}'")
    if participant_col:
        log_callback(f"Participant ID column: '{participant_col}'")
    elif participant_override:
        log_callback(f"Manual participant ID: '{_bids_label(participant_override, 'sub')}'")
    if session_col:
        log_callback(f"Session column: '{session_col}'")
    elif session_override:
        log_callback(f"Manual session: '{session_override}'")
    if location_col:
        log_callback(f"Location column: '{location_col}'")
    if lat_col and lon_col:
        log_callback(f"Per-row coordinates: '{lat_col}' + '{lon_col}'")
    if lat_manual is not None and lon_manual is not None:
        log_callback(f"Global fallback coordinates: ({lat_manual:.4f}, {lon_manual:.4f})")

    rows_out: list[dict] = []
    skipped = 0
    fallback_idx = 1
    env_day_cache: dict[tuple[str, float, float], dict[str, dict]] = {}
    geocode_cache: dict[str, tuple[float, float] | None] = {}

    source_df = df
    pilot_subject_label: str | None = None

    project_root_path = Path(project_path)
    if project_root_path.is_file():
        project_root_path = project_root_path.parent
    persistent_cache_path = project_root_path / ".prism" / "environment_provider_cache.json"
    persistent_cache = _load_environment_provider_cache(persistent_cache_path)
    persistent_cache_dirty = False
    cache_hits = 0
    if pilot_random_subject:
        if participant_col and participant_col in df.columns:
            participants = [
                str(value).strip()
                for value in df[participant_col].tolist()
                if str(value).strip() and str(value).strip().lower() not in {"nan", "none", "n/a"}
            ]
            unique_participants = sorted(set(participants))
            if unique_participants:
                pilot_subject_label = random.choice(unique_participants)
                df = df[df[participant_col].astype(str).str.strip() == pilot_subject_label]
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

    for row_idx, row in df.iterrows():
        ts_raw = str(row.get(timestamp_col, "")).strip() if timestamp_col else ""
        if not ts_raw:
            log_callback(f"Row {row_idx + 1}: empty timestamp — skipped", "warning")
            skipped += 1
            continue

        dt = _parse_timestamp(ts_raw)
        if dt is None:
            log_callback(f"Row {row_idx + 1}: cannot parse timestamp '{ts_raw}' — skipped", "warning")
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
            s = session_override.lstrip("ses-").strip()
            try:
                session_id = f"ses-{int(s):02d}"
            except ValueError:
                session_id = f"ses-{s}"
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
                if (
                    not cached_payloads
                    or provider_payloads != cached_payloads
                ):
                    persistent_cache[cache_key] = provider_payloads
                    persistent_cache_dirty = True
                for warning in env_warnings:
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
        raise ValueError("No valid rows could be processed — check timestamp column and format.")

    if persistent_cache_dirty:
        _save_environment_provider_cache(persistent_cache_path, persistent_cache)
        log_callback("Updated persistent environment provider cache", "info")
    elif cache_hits > 0:
        log_callback(f"Reused persistent cache for {cache_hits} date/location key(s)", "info")

    output_root = input_path.parent / "environment"
    output_root.mkdir()
    output_path = output_root / "recording-weather_environment.tsv"
    _write_environment_tsv(rows_out, output_path)

    log_callback(f"Wrote {len(rows_out)} rows → recording-weather_environment.tsv", "success")

    grouped_rows: dict[tuple[str, str], list[dict]] = {}
    for row in rows_out:
        subject_id = str(row.get("subject_id") or "").strip() or "sub-unknown"
        session_id = str(row.get("session_id") or "").strip() or "ses-01"
        grouped_rows.setdefault((subject_id, session_id), []).append(row)

    written_project_paths: list[str] = []
    for (subject_id, session_id), grouped in grouped_rows.items():
        env_dir = project_root_path / subject_id / session_id / "environment"
        filename = f"{subject_id}_{session_id}_recording-weather_environment.tsv"
        target_path = env_dir / filename
        _write_environment_tsv(grouped, target_path)
        written_project_paths.append(str(target_path))

    inherited_sidecar_path = project_root_path / "recording-weather_environment.json"
    _write_environment_sidecar(inherited_sidecar_path)
    log_callback("Saved inherited root sidecar: recording-weather_environment.json", "success")

    added_bidsignore_rules = check_and_update_bidsignore(str(project_root_path), ["environment"])
    if added_bidsignore_rules:
        log_callback(
            f"Updated .bidsignore for environment outputs ({len(added_bidsignore_rules)} rule(s) added)",
            "info",
        )

    log_callback(
        f"Saved to project: {len(written_project_paths)} environment file(s) under sub-*/ses-*/environment/",
        "success",
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
        "project_environment_path": written_project_paths[0] if written_project_paths else "",
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
    try:
        result = _perform_environment_conversion(
            input_path=config["input_path"],
            filename=config["filename"],
            suffix=config["suffix"],
            separator_option=config["separator_option"],
            timestamp_col=config["timestamp_col"],
            participant_col=config["participant_col"],
            participant_override=config["participant_override"],
            session_col=config["session_col"],
            session_override=config["session_override"],
            location_col=config["location_col"],
            lat_col=config["lat_col"],
            lon_col=config["lon_col"],
            location_label_override=config["location_label_override"],
            lat_manual=config["lat_manual"],
            lon_manual=config["lon_manual"],
            project_path=config["project_path"],
            pilot_random_subject=bool(config.get("pilot_random_subject", False)),
            log_callback=lambda message, level="info": _append_environment_job_log(job_id, message, level),
        )
        with _environment_jobs_lock:
            job = _environment_jobs.get(job_id)
            if job:
                job["done"] = True
                job["success"] = True
                job["result"] = result
                job["error"] = None
    except ValueError as exc:
        with _environment_jobs_lock:
            job = _environment_jobs.get(job_id)
            if job:
                job["done"] = True
                job["success"] = False
                job["result"] = None
                job["error"] = str(exc)
    except Exception as exc:
        logger.exception("Environment conversion failed")
        with _environment_jobs_lock:
            job = _environment_jobs.get(job_id)
            if job:
                job["done"] = True
                job["success"] = False
                job["result"] = None
                job["error"] = str(exc)
    finally:
        shutil.rmtree(config["tmp_dir"], ignore_errors=True)


def _build_environment_conversion_config_from_request() -> tuple[dict[str, Any], tempfile.TemporaryDirectory | None]:
    uploaded = request.files.get("file")
    if not uploaded or not getattr(uploaded, "filename", ""):
        raise ValueError("No file provided")

    filename = secure_filename(uploaded.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"Unsupported file type '{suffix}'")

    separator_option = normalize_separator_option(request.form.get("separator"))

    timestamp_col = (request.form.get("timestamp_col") or "").strip() or None
    participant_col = (request.form.get("participant_col") or "").strip() or None
    participant_override = (request.form.get("participant_override") or "").strip() or None
    session_col = (request.form.get("session_col") or "").strip() or None
    location_col = (request.form.get("location_col") or "").strip() or None
    lat_col = (request.form.get("lat_col") or "").strip() or None
    lon_col = (request.form.get("lon_col") or "").strip() or None
    session_override = (request.form.get("session_override") or "").strip() or None
    location_label_override = (request.form.get("location_label") or "").strip()
    pilot_random_subject = _form_bool(request.form.get("pilot_random_subject"), default=False)
    convert_in_background = _form_bool(request.form.get("convert_in_background"), default=False)

    lat_manual_text = (request.form.get("lat") or "").strip()
    lon_manual_text = (request.form.get("lon") or "").strip()
    has_global_lat = bool(lat_manual_text)
    has_global_lon = bool(lon_manual_text)
    if has_global_lat != has_global_lon:
        raise ValueError("Provide both global latitude and longitude, or leave both empty.")

    lat_manual = _coerce_coord(lat_manual_text, lat=True) if has_global_lat else None
    lon_manual = _coerce_coord(lon_manual_text, lat=False) if has_global_lon else None
    if has_global_lat and (lat_manual is None or lon_manual is None):
        raise ValueError("Global latitude/longitude values are invalid.")

    project_path = session.get("current_project_path")
    if not project_path:
        raise ValueError("No active project selected. Open a project before converting.")

    tmp_dir = tempfile.mkdtemp(prefix="prism_env_convert_")
    input_path = Path(tmp_dir) / filename
    uploaded.save(str(input_path))

    config = {
        "tmp_dir": tmp_dir,
        "input_path": input_path,
        "filename": filename,
        "suffix": suffix,
        "separator_option": separator_option,
        "timestamp_col": timestamp_col,
        "participant_col": participant_col,
        "participant_override": participant_override,
        "session_col": session_col,
        "session_override": session_override,
        "location_col": location_col,
        "lat_col": lat_col,
        "lon_col": lon_col,
        "location_label_override": location_label_override,
        "lat_manual": lat_manual,
        "lon_manual": lon_manual,
        "project_path": project_path,
        "pilot_random_subject": pilot_random_subject,
        "convert_in_background": convert_in_background,
    }
    return config, None


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
    except requests.RequestException as exc:
        return jsonify({"error": f"Location lookup failed: {exc}"}), 502

    results = []
    for item in payload.get("results", []) or []:
        name = (item.get("name") or "").strip()
        admin1 = (item.get("admin1") or "").strip()
        country = (item.get("country") or "").strip()
        label_parts = [p for p in [name, admin1, country] if p]
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


def api_environment_preview():
    """Read an uploaded tabular file and return column names + sample rows."""
    uploaded = request.files.get("file")
    if not uploaded or not getattr(uploaded, "filename", ""):
        return jsonify({"error": "No file provided"}), 400

    filename = secure_filename(uploaded.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        return jsonify({"error": f"Unsupported file type '{suffix}'. Use .xlsx, .csv, or .tsv"}), 400

    try:
        separator_option = normalize_separator_option(request.form.get("separator"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    tmp_dir = tempfile.mkdtemp(prefix="prism_env_preview_")
    try:
        input_path = Path(tmp_dir) / filename
        uploaded.save(str(input_path))

        if suffix == ".xlsx":
            df = pd.read_excel(input_path, dtype=str)
        else:
            delimiter = expected_delimiter_for_suffix(suffix, separator_option)
            df = read_tabular_dataframe_robust(
                input_path, expected_delimiter=delimiter, dtype=str
            )

        columns = list(df.columns)
        sample_rows = df.head(5).fillna("").values.tolist()
        auto_timestamp = _detect_col(_CANDIDATE_TIMESTAMP, columns)
        compatibility = _compatibility_report(df, columns, auto_timestamp)

        return jsonify({
            "columns": columns,
            "sample": sample_rows,
            "compatibility": compatibility,
            "auto_detected": {
                "participant_id": _detect_col(_CANDIDATE_PARTICIPANT, columns),
                "session": _detect_col(_CANDIDATE_SESSION, columns),
                "timestamp": auto_timestamp,
                "location": _detect_col(_CANDIDATE_LOCATION, columns),
                "lat": _detect_col(_CANDIDATE_LAT, columns),
                "lon": _detect_col(_CANDIDATE_LON, columns),
            },
        })
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def api_environment_convert():
    """Convert uploaded tabular survey data into environment.tsv and save to active project."""
    log: list[dict] = []

    def log_msg(msg: str, level: str = "info") -> None:
        log.append({"message": msg, "type": level})

    try:
        config, _ = _build_environment_conversion_config_from_request()
        result = _perform_environment_conversion(
            input_path=config["input_path"],
            filename=config["filename"],
            suffix=config["suffix"],
            separator_option=config["separator_option"],
            timestamp_col=config["timestamp_col"],
            participant_col=config["participant_col"],
            participant_override=config["participant_override"],
            session_col=config["session_col"],
            session_override=config["session_override"],
            location_col=config["location_col"],
            lat_col=config["lat_col"],
            lon_col=config["lon_col"],
            location_label_override=config["location_label_override"],
            lat_manual=config["lat_manual"],
            lon_manual=config["lon_manual"],
            project_path=config["project_path"],
            pilot_random_subject=bool(config.get("pilot_random_subject", False)),
            log_callback=log_msg,
        )
        return jsonify({"log": log, **result})
    except ValueError as exc:
        return jsonify({"error": str(exc), "log": log}), 400
    except Exception as exc:
        import traceback

        logger.exception("Environment conversion failed")
        return jsonify({"error": str(exc), "traceback": traceback.format_exc(), "log": log}), 500
    finally:
        config_obj = locals().get("config")
        if config_obj:
            shutil.rmtree(config_obj["tmp_dir"], ignore_errors=True)


def api_environment_convert_start():
    """Start an async environment conversion job."""
    try:
        config, _ = _build_environment_conversion_config_from_request()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    if bool(config.get("convert_in_background", False)):
        try:
            job_id, pid, log_path, result_path = _start_environment_detached_job(config)
        except Exception as exc:
            shutil.rmtree(config["tmp_dir"], ignore_errors=True)
            logger.exception("Failed to start detached environment conversion")
            return jsonify({"error": str(exc)}), 500

        return jsonify(
            {
                "job_id": job_id,
                "background": True,
                "pid": pid,
                "log_path": str(log_path),
                "result_path": str(result_path),
            }
        ), 200

    job_id = uuid.uuid4().hex
    with _environment_jobs_lock:
        _environment_jobs[job_id] = {
            "logs": [],
            "done": False,
            "success": None,
            "result": None,
            "error": None,
        }

    _append_environment_job_log(job_id, "🌍 Environment conversion job started", "info")

    thread = threading.Thread(target=_run_environment_job, args=(job_id, config), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id}), 200


def api_environment_convert_status(job_id: str):
    """Get incremental status and logs for an async environment conversion job."""
    try:
        cursor = int(request.args.get("cursor", "0"))
    except ValueError:
        cursor = 0

    with _environment_jobs_lock:
        job = _environment_jobs.get(job_id)
        if job:
            logs = job["logs"]
            cursor = max(0, min(cursor, len(logs)))
            payload = {
                "logs": logs[cursor:],
                "next_cursor": len(logs),
                "done": bool(job["done"]),
                "success": job["success"],
                "result": job["result"],
                "error": job["error"],
            }

            if job["done"]:
                _environment_jobs.pop(job_id, None)

            return jsonify(payload), 200

    with _environment_detached_jobs_lock:
        detached_job = _environment_detached_jobs.get(job_id)
        if not detached_job:
            return jsonify({"error": "Job not found"}), 404

    log_path = Path(detached_job["log_path"])
    result_path = Path(detached_job["result_path"])
    logs, next_cursor = _parse_detached_log_lines(log_path, cursor)

    if not result_path.exists():
        return jsonify(
            {
                "logs": logs,
                "next_cursor": next_cursor,
                "done": False,
                "success": None,
                "result": None,
                "error": None,
                "background": True,
                "pid": detached_job.get("pid"),
            }
        ), 200

    try:
        final_state = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception as exc:
        final_state = {
            "done": True,
            "success": False,
            "result": None,
            "error": f"Could not read detached result: {exc}",
        }

    with _environment_detached_jobs_lock:
        _environment_detached_jobs.pop(job_id, None)

    return jsonify(
        {
            "logs": logs,
            "next_cursor": next_cursor,
            "done": bool(final_state.get("done", True)),
            "success": final_state.get("success"),
            "result": final_state.get("result"),
            "error": final_state.get("error"),
            "background": True,
            "pid": detached_job.get("pid"),
        }
    ), 200
