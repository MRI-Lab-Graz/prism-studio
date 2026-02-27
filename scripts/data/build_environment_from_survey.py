#!/usr/bin/env python3
"""
Build one environment TSV row from survey timestamp + location.

This script is intended for international survey workflows where location is not
scanner-bound. It queries Open-Meteo hourly APIs and writes one-row
*_environment.tsv with the same environmental context fields as the DICOM script.

Usage:
  source .venv/bin/activate
    python scripts/data/build_environment_from_survey.py \
    --timestamp 2026-02-26T14:30:00 \
    --lat 47.0707 \
    --lon 15.4395 \
    --output /path/to/sub-01_ses-01_environment.tsv \
    --subject-id sub-01 \
    --session-id ses-01
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

WEATHER_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


@dataclass
class EnvironmentRow:
    subject_id: str
    session_id: str
    filename: str
    relative_time: str
    hour_bin: str
    season_code: str
    sun_phase: str
    sun_hours_today: float
    hours_since_sun: float
    moon_phase: str
    moon_illumination_pct: float
    temp_c: float | None
    apparent_temp_c: float | None
    dew_point_c: float | None
    humidity_pct: float | None
    pressure_hpa: float | None
    precip_mm: float | None
    wind_speed_ms: float | None
    cloud_cover_pct: float | None
    uv_index: float | None
    shortwave_radiation_wm2: float | None
    weather_regime: str
    aqi: float | None
    pm25_ug_m3: float | None
    pm10_ug_m3: float | None
    no2_ug_m3: float | None
    o3_ug_m3: float | None
    pollen_birch: float | None
    pollen_grass: float | None
    pollen_mugwort: float | None
    pollen_ragweed: float | None
    pollen_total: float | None
    pollen_risk_bin: str
    location_label: str
    source_weather: str
    source_air_quality: str
    source_pollen: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build one *_environment.tsv row from survey timestamp + location"
    )
    parser.add_argument(
        "--timestamp",
        required=True,
        help="Acquisition/assessment timestamp in ISO format (e.g. 2026-02-26T14:30:00)",
    )
    parser.add_argument("--lat", required=True, type=float, help="Latitude")
    parser.add_argument("--lon", required=True, type=float, help="Longitude")
    parser.add_argument(
        "--location-label",
        default="survey-site",
        help="Non-identifying location label stored in output",
    )
    parser.add_argument("--output", required=True, help="Output TSV path")
    parser.add_argument("--subject-id", default="", help="BIDS subject label")
    parser.add_argument("--session-id", default="", help="BIDS session label")
    parser.add_argument(
        "--source-filename",
        default="survey",
        help="Source filename token stored in environment TSV",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP timeout in seconds for API requests (default: 20)",
    )
    return parser.parse_args()


def _validate_bids_label(value: str, prefix: str) -> str:
    if not value:
        return ""
    if value.startswith(prefix + "-"):
        return value
    return f"{prefix}-{value}"


def parse_timestamp(timestamp_text: str) -> datetime:
    normalized = timestamp_text.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def to_relative_time(dt: datetime) -> str:
    return f"{dt.year}-DOY{dt.timetuple().tm_yday:03d}-H{dt.hour:02d}"


def hour_bin(hour: int) -> str:
    if 0 <= hour <= 5:
        return "night"
    if 6 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 17:
        return "afternoon"
    return "evening"


def season_code(day_of_year: int) -> str:
    if 80 <= day_of_year <= 171:
        return "spring"
    if 172 <= day_of_year <= 263:
        return "summer"
    if 264 <= day_of_year <= 354:
        return "autumn"
    return "winter"


def estimate_daylight_hours(day_of_year: int, lat: float) -> float:
    baseline = 12.0
    seasonal = 4.0 * math.sin((2 * math.pi * (day_of_year - 80)) / 365.0)
    latitude_factor = min(max(abs(lat) / 90.0, 0.0), 1.0)
    return round(max(4.0, min(20.0, baseline + seasonal * (0.5 + latitude_factor))), 1)


def sun_phase(acq_hour: int, daylight_hours: float) -> str:
    sunrise = 12.0 - daylight_hours / 2.0
    sunset = 12.0 + daylight_hours / 2.0
    if acq_hour < sunrise or acq_hour > sunset:
        return "night"
    if sunrise <= acq_hour < sunrise + 1.5:
        return "dawn"
    if sunset - 1.5 < acq_hour <= sunset:
        return "dusk"
    return "day"


def hours_since_sun(acq_hour: int, daylight_hours: float) -> float:
    sunrise = 12.0 - daylight_hours / 2.0
    sunset = 12.0 + daylight_hours / 2.0
    if sunrise <= acq_hour <= sunset:
        return 0.0
    if acq_hour > sunset:
        return round(acq_hour - sunset, 1)
    return round((24.0 - sunset) + acq_hour, 1)


def moon_status(dt: datetime) -> tuple[str, float]:
    epoch = datetime(2001, 1, 1)
    days = (dt - epoch).total_seconds() / 86400.0
    synodic_month = 29.53058867
    age = days % synodic_month
    phase_fraction = age / synodic_month

    illumination = (1 - math.cos(2 * math.pi * phase_fraction)) / 2
    illumination_pct = round(illumination * 100.0, 1)

    if phase_fraction < 0.03 or phase_fraction >= 0.97:
        phase = "new_moon"
    elif phase_fraction < 0.22:
        phase = "waxing_crescent"
    elif phase_fraction < 0.28:
        phase = "first_quarter"
    elif phase_fraction < 0.47:
        phase = "waxing_gibbous"
    elif phase_fraction < 0.53:
        phase = "full_moon"
    elif phase_fraction < 0.72:
        phase = "waning_gibbous"
    elif phase_fraction < 0.78:
        phase = "last_quarter"
    else:
        phase = "waning_crescent"

    return phase, illumination_pct


def _hourly_value(payload: dict[str, Any], key: str, timestamp_iso: str) -> float | None:
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    values = hourly.get(key) or []
    if not times or not values:
        return None
    try:
        idx = times.index(timestamp_iso)
        value = values[idx]
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def query_weather(dt: datetime, lat: float, lon: float, timeout: int) -> dict[str, float | str | None]:
    date_str = dt.strftime("%Y-%m-%d")
    hour_iso = dt.strftime("%Y-%m-%dT%H:00")

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
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

    response = requests.get(WEATHER_ARCHIVE_URL, params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    pressure = _hourly_value(data, "surface_pressure", hour_iso)
    weather_regime = "frontal"
    if pressure is not None:
        if pressure >= 1020.0:
            weather_regime = "hochdruck"
        elif pressure <= 1000.0:
            weather_regime = "tiefdruck"

    return {
        "temp_c": _hourly_value(data, "temperature_2m", hour_iso),
        "apparent_temp_c": _hourly_value(data, "apparent_temperature", hour_iso),
        "dew_point_c": _hourly_value(data, "dew_point_2m", hour_iso),
        "humidity_pct": _hourly_value(data, "relative_humidity_2m", hour_iso),
        "pressure_hpa": pressure,
        "precip_mm": _hourly_value(data, "precipitation", hour_iso),
        "wind_speed_ms": _hourly_value(data, "wind_speed_10m", hour_iso),
        "cloud_cover_pct": _hourly_value(data, "cloud_cover", hour_iso),
        "uv_index": _hourly_value(data, "uv_index", hour_iso),
        "shortwave_radiation_wm2": _hourly_value(data, "shortwave_radiation", hour_iso),
        "weather_regime": weather_regime,
    }


def query_air_quality(dt: datetime, lat: float, lon: float, timeout: int) -> dict[str, float | None]:
    date_str = dt.strftime("%Y-%m-%d")
    hour_iso = dt.strftime("%Y-%m-%dT%H:00")

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": ",".join(
            ["european_aqi", "pm2_5", "pm10", "nitrogen_dioxide", "ozone"]
        ),
        "timezone": "auto",
    }

    response = requests.get(AIR_QUALITY_URL, params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    return {
        "aqi": _hourly_value(data, "european_aqi", hour_iso),
        "pm25_ug_m3": _hourly_value(data, "pm2_5", hour_iso),
        "pm10_ug_m3": _hourly_value(data, "pm10", hour_iso),
        "no2_ug_m3": _hourly_value(data, "nitrogen_dioxide", hour_iso),
        "o3_ug_m3": _hourly_value(data, "ozone", hour_iso),
    }


def query_pollen(dt: datetime, lat: float, lon: float, timeout: int) -> dict[str, float | None]:
    date_str = dt.strftime("%Y-%m-%d")
    hour_iso = dt.strftime("%Y-%m-%dT%H:00")

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": ",".join(
            ["birch_pollen", "grass_pollen", "mugwort_pollen", "ragweed_pollen"]
        ),
        "timezone": "auto",
    }

    try:
        response = requests.get(AIR_QUALITY_URL, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        birch = _hourly_value(data, "birch_pollen", hour_iso)
        grass = _hourly_value(data, "grass_pollen", hour_iso)
        mugwort = _hourly_value(data, "mugwort_pollen", hour_iso)
        ragweed = _hourly_value(data, "ragweed_pollen", hour_iso)
    except Exception:
        birch = None
        grass = None
        mugwort = None
        ragweed = None

    values = [v for v in [birch, grass, mugwort, ragweed] if v is not None]
    total = float(sum(values)) if values else None

    return {
        "pollen_birch": birch,
        "pollen_grass": grass,
        "pollen_mugwort": mugwort,
        "pollen_ragweed": ragweed,
        "pollen_total": total,
    }


def pollen_risk_bin(pollen_total: float | None) -> str:
    if pollen_total is None:
        return "unknown"
    if pollen_total < 50:
        return "low"
    if pollen_total < 150:
        return "medium"
    if pollen_total < 300:
        return "high"
    return "very_high"


def _format_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def write_environment_tsv(output_path: Path, row: EnvironmentRow) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    headers = [
        "subject_id",
        "session_id",
        "filename",
        "relative_time",
        "hour_bin",
        "season_code",
        "sun_phase",
        "sun_hours_today",
        "hours_since_sun",
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
        "location_label",
        "source_weather",
        "source_air_quality",
        "source_pollen",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, delimiter="\t")
        writer.writeheader()
        writer.writerow({k: _format_value(getattr(row, k)) for k in headers})


def main() -> int:
    args = _parse_args()

    try:
        ts = parse_timestamp(args.timestamp)
    except Exception as exc:
        print(f"❌ Invalid --timestamp value: {exc}")
        return 1

    output_path = Path(args.output)

    relative = to_relative_time(ts)
    hbin = hour_bin(ts.hour)
    season = season_code(ts.timetuple().tm_yday)
    daylight = estimate_daylight_hours(ts.timetuple().tm_yday, args.lat)
    phase = sun_phase(ts.hour, daylight)
    since_sun = hours_since_sun(ts.hour, daylight)
    moon_phase_name, moon_illumination_pct = moon_status(ts)

    try:
        weather = query_weather(ts, args.lat, args.lon, args.timeout)
        air_quality = query_air_quality(ts, args.lat, args.lon, args.timeout)
        pollen = query_pollen(ts, args.lat, args.lon, args.timeout)
    except requests.RequestException as exc:
        print(f"❌ API query failed: {exc}")
        return 2

    total_pollen = pollen.get("pollen_total")

    row = EnvironmentRow(
        subject_id=_validate_bids_label(args.subject_id.strip(), "sub"),
        session_id=_validate_bids_label(args.session_id.strip(), "ses"),
        filename=args.source_filename,
        relative_time=relative,
        hour_bin=hbin,
        season_code=season,
        sun_phase=phase,
        sun_hours_today=daylight,
        hours_since_sun=since_sun,
        moon_phase=moon_phase_name,
        moon_illumination_pct=moon_illumination_pct,
        temp_c=weather.get("temp_c"),
        apparent_temp_c=weather.get("apparent_temp_c"),
        dew_point_c=weather.get("dew_point_c"),
        humidity_pct=weather.get("humidity_pct"),
        pressure_hpa=weather.get("pressure_hpa"),
        precip_mm=weather.get("precip_mm"),
        wind_speed_ms=weather.get("wind_speed_ms"),
        cloud_cover_pct=weather.get("cloud_cover_pct"),
        uv_index=weather.get("uv_index"),
        shortwave_radiation_wm2=weather.get("shortwave_radiation_wm2"),
        weather_regime=str(weather.get("weather_regime") or "frontal"),
        aqi=air_quality.get("aqi"),
        pm25_ug_m3=air_quality.get("pm25_ug_m3"),
        pm10_ug_m3=air_quality.get("pm10_ug_m3"),
        no2_ug_m3=air_quality.get("no2_ug_m3"),
        o3_ug_m3=air_quality.get("o3_ug_m3"),
        pollen_birch=pollen.get("pollen_birch"),
        pollen_grass=pollen.get("pollen_grass"),
        pollen_mugwort=pollen.get("pollen_mugwort"),
        pollen_ragweed=pollen.get("pollen_ragweed"),
        pollen_total=total_pollen,
        pollen_risk_bin=pollen_risk_bin(total_pollen),
        location_label=args.location_label,
        source_weather="open-meteo archive",
        source_air_quality="open-meteo air-quality",
        source_pollen="open-meteo pollen",
    )

    write_environment_tsv(output_path, row)

    print(f"✅ Survey timestamp: {ts.isoformat()}")
    print(f"✅ Queried Open-Meteo at ({args.lat}, {args.lon})")
    print(f"✅ Wrote TSV: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
