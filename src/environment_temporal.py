"""Shared temporal/astronomy math for environment enrichment.

This module holds the pure, side-effect-free formulas that turn a clock
hour + day-of-year (+ latitude) into season/sun-phase/daylight/pollen-risk
context. It exists because two independent code paths need these exact
formulas and previously each carried its own copy, which had already
silently diverged (see docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P1-1):

- `app/src/environment/builder.py` backs the legacy, privacy-safe
  `prism.py --build-environment` CLI path. It only ever sees de-identified
  temporal anchors (`prism_time_anchor`, e.g. "2026-DOY123-H14") already
  written into `scans.tsv` — never a real calendar date. This is a
  deliberate privacy boundary: raw `date`/`datetime`/`timestamp` keys are
  rejected on input.
- `app/src/web/blueprints/conversion_environment_handlers.py` backs the
  Studio GUI's Converter -> Environment/MRI tab and the `environment
  preview`/`environment convert` CLI commands. It works from a raw
  timestamp column a researcher provides, so it can additionally compute
  things a bare day-of-year can't support (e.g. moon phase, which needs an
  absolute date, not just a day-of-year) and enrich with live weather/air
  quality/pollen API data.

Because the two paths intentionally see different inputs (anchors vs. real
timestamps), they cannot be fully collapsed into one pipeline without
breaking the privacy guarantee of the anchor-only path — the CORE_COLUMNS
outputs are expected to differ (moon phase, elevation, and richer live
weather fields are only available in the raw-timestamp path). What *should*
never differ is the pure math shared by both: season classification, sun
phase/daylight estimation, and pollen risk binning. Both callers import
those functions from here instead of maintaining their own copies.
"""

from __future__ import annotations

import math


def hour_to_bin(hour: int | None) -> str:
    """Bucket an hour-of-day (0-23) into a coarse daypart label."""
    if hour is None:
        return "unknown"
    if 0 <= hour <= 5:
        return "night"
    if 6 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 17:
        return "afternoon"
    return "evening"


def season_code(day_of_year: int | None) -> str:
    """Classify a day-of-year (1-366) into a meteorological-ish season."""
    if day_of_year is None:
        return "unknown"
    if 80 <= day_of_year <= 171:
        return "spring"
    if 172 <= day_of_year <= 263:
        return "summer"
    if 264 <= day_of_year <= 354:
        return "autumn"
    return "winter"


def estimate_daylight_hours(day_of_year: int | None, lat: float = 47.0) -> float:
    """Rough daylight-hours estimate from day-of-year and latitude.

    Not a precise astronomical calculation — a smooth seasonal
    approximation good enough for sun-phase bucketing, not sunrise tables.
    """
    if day_of_year is None:
        return 10.0
    baseline = 12.0
    seasonal = 4.0 * math.sin((2 * math.pi * (day_of_year - 80)) / 365.0)
    latitude_factor = min(max(abs(lat) / 90.0, 0.0), 1.0)
    return round(max(4.0, min(20.0, baseline + seasonal * (0.5 + latitude_factor))), 1)


def sun_window(daylight_hours: float) -> tuple[float, float]:
    """Return (sunrise, sunset) as fractional hours, centered on noon."""
    sunrise = 12.0 - (daylight_hours / 2.0)
    sunset = 12.0 + (daylight_hours / 2.0)
    return sunrise, sunset


def sun_phase(hour: int | None, daylight_hours: float) -> str:
    """Classify an hour into night/dawn/day/dusk given a daylight window."""
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
    """Hours since sunset (0.0 while the sun is still up)."""
    if hour is None:
        return -1.0
    sunrise, sunset = sun_window(daylight_hours)
    if sunrise <= hour <= sunset:
        return 0.0
    if hour > sunset:
        return round(hour - sunset, 1)
    return round((24.0 - sunset) + hour, 1)


def pollen_risk_bin(total: float | None) -> str:
    """Bucket a total pollen count into a coarse risk category."""
    if total is None:
        return "unknown"
    if total < 50:
        return "low"
    if total < 150:
        return "medium"
    if total < 300:
        return "high"
    return "very_high"
