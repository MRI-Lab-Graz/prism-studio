from __future__ import annotations

import argparse
import csv
import math
import re
from pathlib import Path
from typing import Callable, Iterable

from .aggregator import collect
from .cache import EnvironmentCache
from .dicom_bridge import read_prism_time_anchor
from .providers import fetch_weather, fetch_pollen, fetch_air_quality

ANCHOR_HOUR_RE = re.compile(r"H(\d{1,2})$")
ANCHOR_DOY_RE = re.compile(r"DOY(\d{1,3})")

CORE_COLUMNS = [
    "subject_id",
    "session_id",
    "filename",
    "relative_time",
    "hour_bin",
    "season_code",
    "sun_phase",
    "sun_hours_today",
    "hours_since_sun",
    "temp_c",
    "humidity_pct",
    "pressure_hpa",
    "precip_mm",
    "wind_speed_ms",
    "cloud_cover_pct",
    "weather_regime",
    "aqi",
    "pm25_ug_m3",
    "pm10_ug_m3",
    "no2_ug_m3",
    "o3_ug_m3",
    "pollen_total",
    "pollen_birch",
    "pollen_grass",
    "pollen_risk_bin",
]


def hour_to_bin(hour: int | None) -> str:
    if hour is None:
        return "unknown"
    if 0 <= hour <= 5:
        return "night"
    if 6 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 17:
        return "afternoon"
    return "evening"


def parse_hour_from_anchor(anchor: str) -> int | None:
    match = ANCHOR_HOUR_RE.search(anchor)
    if not match:
        return None
    hour = int(match.group(1))
    if 0 <= hour <= 23:
        return hour
    return None


def parse_day_of_year_from_anchor(anchor: str) -> int | None:
    match = ANCHOR_DOY_RE.search(anchor)
    if not match:
        return None
    day_of_year = int(match.group(1))
    if 1 <= day_of_year <= 366:
        return day_of_year
    return None


def season_code(day_of_year: int | None) -> str:
    if day_of_year is None:
        return "unknown"
    if 80 <= day_of_year <= 171:
        return "spring"
    if 172 <= day_of_year <= 263:
        return "summer"
    if 264 <= day_of_year <= 354:
        return "autumn"
    return "winter"


def estimate_daylight_hours(day_of_year: int | None, lat: float) -> float:
    if day_of_year is None:
        return 10.0
    baseline = 12.0
    seasonal = 4.0 * math.sin((2 * math.pi * (day_of_year - 80)) / 365.0)
    latitude_factor = min(max(abs(lat) / 90.0, 0.0), 1.0)
    return round(max(4.0, min(20.0, baseline + seasonal * (0.5 + latitude_factor))), 1)


def sun_window(daylight_hours: float) -> tuple[float, float]:
    sunrise = 12.0 - (daylight_hours / 2.0)
    sunset = 12.0 + (daylight_hours / 2.0)
    return sunrise, sunset


def sun_phase(hour: int | None, daylight_hours: float) -> str:
    if hour is None:
        return "unknown"
    sunrise, sunset = sun_window(daylight_hours)
    if hour < sunrise or hour > sunset:
        return "night"
    if sunrise <= hour < sunrise + 1.5:
        return "dawn"
    if sunset - 1.5 < hour <= sunset:
        return "dusk"
    return "day"


def hours_since_sun(hour: int | None, daylight_hours: float) -> float:
    if hour is None:
        return -1.0
    sunrise, sunset = sun_window(daylight_hours)
    if sunrise <= hour <= sunset:
        return 0.0
    if hour > sunset:
        return round(hour - sunset, 1)
    return round((24.0 - sunset) + hour, 1)


def pollen_risk_bin(total: float) -> str:
    if total < 50:
        return "low"
    if total < 150:
        return "medium"
    if total < 300:
        return "high"
    return "very_high"


def extract_subject_session(filename: str) -> tuple[str, str]:
    subject = ""
    session = ""

    subject_match = re.search(r"sub-([^_/]+)", filename)
    if subject_match:
        subject = f"sub-{subject_match.group(1)}"

    session_match = re.search(r"ses-([^_/]+)", filename)
    if session_match:
        session = f"ses-{session_match.group(1)}"

    return subject, session


def _provider_registry() -> dict[str, Callable[[float, float, str], dict]]:
    return {
        "weather": fetch_weather,
        "pollen": fetch_pollen,
        "air_quality": fetch_air_quality,
    }


def build_environment_tsv(
    scans_tsv: str | Path,
    output_tsv: str | Path,
    lat: float,
    lon: float,
    enabled_providers: Iterable[str] | None = None,
    cache_path: str | Path | None = None,
) -> Path:
    scans_tsv = Path(scans_tsv)
    output_tsv = Path(output_tsv)
    output_tsv.parent.mkdir(parents=True, exist_ok=True)

    registry = _provider_registry()
    selected = list(enabled_providers or registry.keys())
    provider_functions = [registry[name] for name in selected if name in registry]

    cache = EnvironmentCache(cache_path) if cache_path else None

    rows: list[dict[str, str | int | float]] = []

    with scans_tsv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames:
            raise ValueError("scans TSV is empty or has no header")

        for row in reader:
            filename = (row.get("filename") or "").strip()
            if not filename:
                continue

            anchor = read_prism_time_anchor(row)
            cache_key = f"{lat:.4f}:{lon:.4f}:{anchor}:{','.join(selected)}"

            provider_values = None
            if cache:
                provider_values = cache.get(cache_key)

            if provider_values is None:
                provider_values = collect(lat, lon, anchor, provider_functions)
                if cache:
                    cache.set(cache_key, provider_values)

            hour = parse_hour_from_anchor(anchor)
            day_of_year = parse_day_of_year_from_anchor(anchor)
            daylight_hours = estimate_daylight_hours(day_of_year, lat)
            subject_id, session_id = extract_subject_session(filename)

            result = {
                "subject_id": subject_id,
                "session_id": session_id,
                "filename": filename,
                "relative_time": anchor,
                "hour_bin": hour_to_bin(hour),
                "season_code": season_code(day_of_year),
                "sun_phase": sun_phase(hour, daylight_hours),
                "sun_hours_today": daylight_hours,
                "hours_since_sun": hours_since_sun(hour, daylight_hours),
            }
            result.update(provider_values)
            result["pollen_risk_bin"] = pollen_risk_bin(
                float(result.get("pollen_total", 0.0))
            )
            rows.append(result)

    all_columns = list(CORE_COLUMNS)
    provider_columns = sorted(
        {
            key
            for row in rows
            for key in row.keys()
            if key not in set(CORE_COLUMNS)
        }
    )
    all_columns.extend(provider_columns)

    with output_tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=all_columns, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    if cache:
        cache.flush()

    return output_tsv


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build PRISM environment.tsv from scans.tsv and privacy-safe anchors"
    )
    parser.add_argument("scans_tsv", help="Input scans TSV with filename and prism_time_anchor")
    parser.add_argument("output_tsv", help="Output *_environment.tsv path")
    parser.add_argument("--lat", type=float, required=True, help="Site latitude")
    parser.add_argument("--lon", type=float, required=True, help="Site longitude")
    parser.add_argument(
        "--providers",
        nargs="*",
        default=["weather", "pollen", "air_quality"],
        help="Providers to enable: weather pollen air_quality",
    )
    parser.add_argument(
        "--cache",
        default=".prism/environment_cache.json",
        help="Cache file path for provider results",
    )
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    build_environment_tsv(
        scans_tsv=args.scans_tsv,
        output_tsv=args.output_tsv,
        lat=args.lat,
        lon=args.lon,
        enabled_providers=args.providers,
        cache_path=args.cache,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
