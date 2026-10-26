from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from src.environment_temporal import pollen_risk_bin as _shared_pollen_risk_bin


# Converter column -> (provider payload, Open-Meteo hourly variable): the numeric hourly columns.
HOURLY_PROVIDER_COLUMNS: dict[str, tuple[str, str]] = {
    "temp_c": ("weather", "temperature_2m"),
    "apparent_temp_c": ("weather", "apparent_temperature"),
    "dew_point_c": ("weather", "dew_point_2m"),
    "humidity_pct": ("weather", "relative_humidity_2m"),
    "pressure_hpa": ("weather", "surface_pressure"),
    "precip_mm": ("weather", "precipitation"),
    "wind_speed_ms": ("weather", "wind_speed_10m"),
    "cloud_cover_pct": ("weather", "cloud_cover"),
    "uv_index": ("weather", "uv_index"),
    "shortwave_radiation_wm2": ("weather", "shortwave_radiation"),
    "aqi": ("air", "european_aqi"),
    "pm25_ug_m3": ("air", "pm2_5"),
    "pm10_ug_m3": ("air", "pm10"),
    "no2_ug_m3": ("air", "nitrogen_dioxide"),
    "o3_ug_m3": ("air", "ozone"),
    "pollen_birch": ("pollen", "birch_pollen"),
    "pollen_grass": ("pollen", "grass_pollen"),
    "pollen_mugwort": ("pollen", "mugwort_pollen"),
    "pollen_ragweed": ("pollen", "ragweed_pollen"),
}


def _hourly_variables(payload_key: str) -> str:
    return ",".join(var for key, var in HOURLY_PROVIDER_COLUMNS.values() if key == payload_key)


def handle_hourly_series(payloads_by_day: list[dict[str, dict]], column: str) -> dict[str, float | None]:
    """Hour ("YYYY-MM-DDTHH:00") -> value of one converter column, merged over several days' payloads."""
    payload_key, variable = HOURLY_PROVIDER_COLUMNS[column]
    series: dict[str, float | None] = {}
    for payloads in payloads_by_day:
        hourly = (payloads.get(payload_key) or {}).get("hourly") or {}
        for ts, value in zip(hourly.get("time") or [], hourly.get(variable) or []):
            try:
                series[str(ts)] = None if value is None else float(value)
            except (TypeError, ValueError):
                series[str(ts)] = None
    return series


def handle_hourly_value(payload: dict, key: str, timestamp_iso: str) -> float | None:
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


def handle_pollen_risk_bin(total: float | None) -> str:
    return _shared_pollen_risk_bin(total)


def handle_payload_has_hourly_data(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    hourly = payload.get("hourly")
    return isinstance(hourly, dict) and bool(hourly)


def handle_cache_key_for_day(date_str: str, lat: float, lon: float) -> str:
    return f"{date_str}|{round(lat, 4):.4f}|{round(lon, 4):.4f}"


def handle_load_environment_provider_cache(
    cache_path: Path,
) -> dict[str, dict[str, dict[str, Any]]]:
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
        weather_raw = value.get("weather")
        air_raw = value.get("air")
        pollen_raw = value.get("pollen")
        cleaned[key] = {
            "weather": weather_raw if isinstance(weather_raw, dict) else {},
            "air": air_raw if isinstance(air_raw, dict) else {},
            "pollen": pollen_raw if isinstance(pollen_raw, dict) else {},
        }
    return cleaned


def handle_save_environment_provider_cache(
    cache_path: Path,
    entries: dict[str, dict[str, dict[str, Any]]],
) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "entries": entries,
    }
    cache_path.write_text(json.dumps(payload), encoding="utf-8")


def handle_fetch_environment_day(
    dt: datetime,
    lat: float,
    lon: float,
    *,
    cached_payloads: dict[str, dict[str, Any]] | None = None,
    payload_has_hourly_data,
    fetch_provider_json,
    provider_warning,
    weather_archive_url: str,
    air_quality_url: str,
    weather_timeout_seconds: int,
    air_quality_timeout_seconds: int,
    pollen_timeout_seconds: int,
) -> tuple[dict[str, dict], list[str]]:
    date_str = dt.strftime("%Y-%m-%d")
    weather_start_date = (dt - timedelta(days=2)).strftime("%Y-%m-%d")
    warnings: list[str] = []

    weather_params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": weather_start_date,
        "end_date": date_str,
        "hourly": _hourly_variables("weather"),
        "timezone": "auto",
    }
    air_params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": _hourly_variables("air"),
        "timezone": "auto",
    }
    pollen_params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": _hourly_variables("pollen"),
        "timezone": "auto",
    }
    provider_payloads: dict[str, dict] = {
        "weather": dict((cached_payloads or {}).get("weather") or {}),
        "air": dict((cached_payloads or {}).get("air") or {}),
        "pollen": dict((cached_payloads or {}).get("pollen") or {}),
    }

    provider_requests = [
        (
            "Weather archive",
            "weather",
            weather_archive_url,
            weather_params,
            weather_timeout_seconds,
        ),
        (
            "Air quality",
            "air",
            air_quality_url,
            air_params,
            air_quality_timeout_seconds,
        ),
        ("Pollen", "pollen", air_quality_url, pollen_params, pollen_timeout_seconds),
    ]

    missing_requests = [
        (provider_name, payload_key, url, params, timeout)
        for provider_name, payload_key, url, params, timeout in provider_requests
        if not payload_has_hourly_data(provider_payloads.get(payload_key))
    ]

    if not missing_requests:
        return {
            "weather": provider_payloads["weather"],
            "air": provider_payloads["air"],
            "pollen": provider_payloads["pollen"],
        }, warnings

    with ThreadPoolExecutor(max_workers=len(missing_requests)) as pool:
        futures = {
            pool.submit(fetch_provider_json, url, params, timeout): (
                provider_name,
                payload_key,
            )
            for provider_name, payload_key, url, params, timeout in missing_requests
        }
        for future in as_completed(futures):
            provider_name, payload_key = futures[future]
            try:
                provider_payloads[payload_key] = future.result()
            except requests.RequestException as exc:
                warnings.append(provider_warning(provider_name, exc))

    return {
        "weather": provider_payloads["weather"],
        "air": provider_payloads["air"],
        "pollen": provider_payloads["pollen"],
    }, warnings


def handle_extract_environment_hour(
    dt: datetime,
    provider_payloads: dict[str, dict],
    *,
    hourly_value,
    pollen_risk_bin,
) -> dict:
    hour_iso = dt.strftime("%Y-%m-%dT%H:00")
    weather = provider_payloads.get("weather") or {}

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
    elevation_raw = weather.get("elevation")
    if elevation_raw is not None:
        try:
            elevation_m = float(elevation_raw)
        except (TypeError, ValueError):
            elevation_m = None

    values = {
        column: hourly_value(provider_payloads.get(payload_key) or {}, variable, hour_iso)
        for column, (payload_key, variable) in HOURLY_PROVIDER_COLUMNS.items()
    }

    pressure = values["pressure_hpa"]
    weather_regime = "frontal"
    if pressure is not None:
        if pressure >= 1020.0:
            weather_regime = "high-pressure"
        elif pressure <= 1000.0:
            weather_regime = "low-pressure"

    pollen_vals = [
        values[c] for c in ("pollen_birch", "pollen_grass", "pollen_mugwort", "pollen_ragweed") if values[c] is not None
    ]
    pollen_total = float(sum(pollen_vals)) if pollen_vals else None

    return {
        **values,
        "weather_regime": weather_regime,
        "elevation_m": elevation_m,
        "heatwave_status": heatwave_status,
        "pollen_total": pollen_total,
        "pollen_risk_bin": pollen_risk_bin(pollen_total),
    }


def handle_fetch_environment_hour(
    dt: datetime,
    lat: float,
    lon: float,
    *,
    fetch_environment_day,
    extract_environment_hour,
) -> tuple[dict, list[str]]:
    provider_payloads, warnings = fetch_environment_day(dt, lat, lon)
    return extract_environment_hour(dt, provider_payloads), warnings