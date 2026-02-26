#!/usr/bin/env python3
"""
Build one environment TSV row directly from one DICOM file.

Workflow:
1) Read acquisition timestamp from DICOM (pydicom preferred, dcmdump fallback)
2) Use hardcoded site location for API queries
3) Query Open-Meteo weather + air-quality (+ pollen where available)
4) Write one-row *_environment.tsv

Usage:
  source .venv/bin/activate
    python scripts/data/build_environment_from_dicom.py \
    --dicom /path/to/file.dcm \
        --dataset-root /path/to/bids_dataset \
    --subject-id sub-01 \
    --session-id ses-01
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

# Hardcoded site location (as requested)
SITE_LABEL = "mri-lab-graz"
SITE_LAT = 47.0707
SITE_LON = 15.4395

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
        description="Build one *_environment.tsv row from one DICOM timestamp"
    )
    parser.add_argument("--dicom", required=True, help="Path to one DICOM file")
    parser.add_argument(
        "--dataset-root",
        default="",
        help="Dataset root where sub-*/ses-*/environment should be created",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional explicit output TSV path (overrides --dataset-root layout)",
    )
    parser.add_argument(
        "--subject-id", default="", help="BIDS subject label (e.g. sub-01)"
    )
    parser.add_argument("--session-id", default="", help="BIDS session label (e.g. ses-01)")
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


def resolve_output_path(args: argparse.Namespace) -> Path:
    if args.output:
        return Path(args.output)

    if not args.dataset_root:
        raise ValueError("Provide --dataset-root when --output is not set")

    subject_id = _validate_bids_label(args.subject_id.strip(), "sub")
    if not subject_id:
        raise ValueError("--subject-id is required when using --dataset-root")

    session_id = _validate_bids_label(args.session_id.strip(), "ses")

    dataset_root = Path(args.dataset_root)
    if session_id:
        env_dir = dataset_root / subject_id / session_id / "environment"
        filename = f"{subject_id}_{session_id}_environment.tsv"
    else:
        env_dir = dataset_root / subject_id / "environment"
        filename = f"{subject_id}_environment.tsv"

    return env_dir / filename


def ensure_bidsignore(dataset_root: Path) -> None:
    bidsignore_path = dataset_root / ".bidsignore"
    required_rules = [
        "environment/",
        "**/environment/",
        "*_environment.*",
    ]

    existing: set[str] = set()
    if bidsignore_path.exists():
        existing = {
            line.strip()
            for line in bidsignore_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    to_add = [rule for rule in required_rules if rule not in existing]
    if not to_add:
        return

    lines: list[str] = []
    if not bidsignore_path.exists():
        lines.append("# .bidsignore created by build_environment_from_dicom.py")
    lines.append("# Added by environment enrichment script")
    lines.extend(to_add)

    mode = "a" if bidsignore_path.exists() else "w"
    with bidsignore_path.open(mode, encoding="utf-8") as handle:
        if mode == "a" and bidsignore_path.stat().st_size > 0:
            handle.write("\n")
        handle.write("\n".join(lines) + "\n")


def _parse_dicom_date_time(date_text: str, time_text: str) -> datetime:
    date_clean = re.sub(r"[^0-9]", "", date_text)
    time_clean = re.sub(r"[^0-9.]", "", time_text)

    if len(date_clean) < 8:
        raise ValueError(f"Invalid DICOM date: {date_text}")

    year = int(date_clean[0:4])
    month = int(date_clean[4:6])
    day = int(date_clean[6:8])

    hh = int(time_clean[0:2]) if len(time_clean) >= 2 else 0
    mm = int(time_clean[2:4]) if len(time_clean) >= 4 else 0
    ss = int(time_clean[4:6]) if len(time_clean) >= 6 else 0

    microsecond = 0
    if "." in time_clean:
        frac = time_clean.split(".", 1)[1]
        frac = (frac + "000000")[:6]
        microsecond = int(frac)

    return datetime(year, month, day, hh, mm, ss, microsecond)


def _parse_dicom_datetime(dt_text: str) -> datetime:
    clean = dt_text.strip()
    main = clean.split("+")[0].split("-")[0]

    year = int(main[0:4])
    month = int(main[4:6])
    day = int(main[6:8])
    hh = int(main[8:10]) if len(main) >= 10 else 0
    mm = int(main[10:12]) if len(main) >= 12 else 0
    ss = int(main[12:14]) if len(main) >= 14 else 0

    microsecond = 0
    if "." in main:
        frac = main.split(".", 1)[1]
        frac = (frac + "000000")[:6]
        microsecond = int(frac)

    return datetime(year, month, day, hh, mm, ss, microsecond)


def _extract_datetime_with_pydicom(dicom_path: Path) -> datetime | None:
    try:
        import pydicom  # type: ignore
    except Exception:
        return None

    ds = pydicom.dcmread(str(dicom_path), stop_before_pixels=True, force=True)

    if getattr(ds, "AcquisitionDateTime", None):
        return _parse_dicom_datetime(str(ds.AcquisitionDateTime))

    for date_key, time_key in [
        ("AcquisitionDate", "AcquisitionTime"),
        ("ContentDate", "ContentTime"),
        ("SeriesDate", "SeriesTime"),
        ("StudyDate", "StudyTime"),
    ]:
        date_val = getattr(ds, date_key, None)
        time_val = getattr(ds, time_key, None)
        if date_val and time_val:
            return _parse_dicom_date_time(str(date_val), str(time_val))

    return None


def _extract_datetime_with_dcmdump(dicom_path: Path) -> datetime | None:
    try:
        result = subprocess.run(
            ["dcmdump", "+P", "0008,002A", "+P", "0008,0022", "+P", "0008,0032", str(dicom_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None

    text = result.stdout

    dt_match = re.search(r"\(0008,002a\).*?\[(.*?)\]", text, flags=re.IGNORECASE)
    if dt_match and dt_match.group(1).strip():
        return _parse_dicom_datetime(dt_match.group(1).strip())

    date_match = re.search(r"\(0008,0022\).*?\[(.*?)\]", text, flags=re.IGNORECASE)
    time_match = re.search(r"\(0008,0032\).*?\[(.*?)\]", text, flags=re.IGNORECASE)
    if date_match and time_match:
        return _parse_dicom_date_time(date_match.group(1).strip(), time_match.group(1).strip())

    return None


def extract_dicom_datetime(dicom_path: Path) -> datetime:
    dt = _extract_datetime_with_pydicom(dicom_path)
    if dt is not None:
        return dt

    dt = _extract_datetime_with_dcmdump(dicom_path)
    if dt is not None:
        return dt

    raise RuntimeError(
        "Could not extract DICOM timestamp. Install pydicom via setup.sh or provide dcmdump."
    )


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
    # Simple approximation based on synodic month from a known new moon epoch.
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


def query_weather(dt: datetime, timeout: int) -> dict[str, float | None]:
    date_str = dt.strftime("%Y-%m-%d")
    hour_iso = dt.strftime("%Y-%m-%dT%H:00")

    params = {
        "latitude": SITE_LAT,
        "longitude": SITE_LON,
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


def query_air_quality(dt: datetime, timeout: int) -> dict[str, float | None]:
    date_str = dt.strftime("%Y-%m-%d")
    hour_iso = dt.strftime("%Y-%m-%dT%H:00")

    params = {
        "latitude": SITE_LAT,
        "longitude": SITE_LON,
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


def query_pollen(dt: datetime, timeout: int) -> dict[str, float | None]:
    # Open-Meteo pollen fields are forecast-oriented; this call may return
    # missing values for older dates depending on provider availability.
    date_str = dt.strftime("%Y-%m-%d")
    hour_iso = dt.strftime("%Y-%m-%dT%H:00")

    params = {
        "latitude": SITE_LAT,
        "longitude": SITE_LON,
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

    dicom_path = Path(args.dicom)
    try:
        output_path = resolve_output_path(args)
    except Exception as exc:
        print(f"❌ Invalid output configuration: {exc}")
        return 1

    if not dicom_path.exists() or not dicom_path.is_file():
        print(f"❌ DICOM file not found: {dicom_path}")
        return 1

    try:
        acq_dt = extract_dicom_datetime(dicom_path)
    except Exception as exc:
        print(f"❌ Failed to extract DICOM timestamp: {exc}")
        return 2

    relative = to_relative_time(acq_dt)
    hbin = hour_bin(acq_dt.hour)
    season = season_code(acq_dt.timetuple().tm_yday)
    daylight = estimate_daylight_hours(acq_dt.timetuple().tm_yday, SITE_LAT)
    phase = sun_phase(acq_dt.hour, daylight)
    since_sun = hours_since_sun(acq_dt.hour, daylight)
    moon_phase_name, moon_illumination_pct = moon_status(acq_dt)

    try:
        weather = query_weather(acq_dt, args.timeout)
        air_quality = query_air_quality(acq_dt, args.timeout)
        pollen = query_pollen(acq_dt, args.timeout)
    except requests.RequestException as exc:
        print(f"❌ API query failed: {exc}")
        return 3

    total_pollen = pollen.get("pollen_total")

    row = EnvironmentRow(
        subject_id=_validate_bids_label(args.subject_id.strip(), "sub"),
        session_id=_validate_bids_label(args.session_id.strip(), "ses"),
        filename=dicom_path.name,
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
        location_label=SITE_LABEL,
        source_weather="open-meteo archive",
        source_air_quality="open-meteo air-quality",
        source_pollen="open-meteo pollen",
    )

    write_environment_tsv(output_path, row)

    if args.dataset_root:
        dataset_root = Path(args.dataset_root)
        try:
            ensure_bidsignore(dataset_root)
        except Exception as exc:
            print(f"⚠️ Could not update .bidsignore: {exc}")

    print(f"✅ Extracted DICOM timestamp: {acq_dt.isoformat()}")
    print(f"✅ Queried APIs at hardcoded location: {SITE_LABEL} ({SITE_LAT}, {SITE_LON})")
    print(f"✅ Wrote TSV: {output_path}")
    if args.dataset_root:
        print(f"✅ Updated .bidsignore in dataset root: {Path(args.dataset_root) / '.bidsignore'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
