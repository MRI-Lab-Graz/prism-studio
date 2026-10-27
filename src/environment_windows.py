"""Environment time windows: a statistic over the hours before the session (environment 2.0.0
column ``Window {Start, End}`` + ``Statistic``). The window ends at the session (``End`` = PT0S)
and starts ``duration`` before it. Used by the converter and ``environment convert --window``."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.environment_provider_helpers import HOURLY_PROVIDER_COLUMNS

# The converter columns with hourly numeric provider data; the GUI reads this list.
WINDOW_COLUMNS: tuple[str, ...] = tuple(HOURLY_PROVIDER_COLUMNS)
STATISTICS = ("mean", "min", "max", "sum", "count")

# The ISO 8601 duration pattern of the environment 2.0.0 schema (Window.Start/End).
_DURATION = re.compile(r"^P(?!$)(\d+Y)?(\d+M)?(\d+W)?(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+S)?)?$")


@dataclass(frozen=True)
class WindowSpec:
    column: str
    duration: str
    statistic: str


def duration_to_timedelta(duration: str) -> timedelta:
    match = _DURATION.fullmatch(duration or "")
    if match is None:
        raise ValueError(f"{duration!r} is not an ISO 8601 duration such as P3D, PT6H or P1W")
    years, months, weeks, days, _, hours, minutes, seconds = match.groups()
    if years or months:
        raise ValueError(f"{duration!r}: years and months are not a fixed length; use weeks or days (e.g. P30D)")
    n = lambda part: int(part[:-1]) if part else 0
    return timedelta(weeks=n(weeks), days=n(days), hours=n(hours), minutes=n(minutes), seconds=n(seconds))


def parse_window(text: str) -> WindowSpec:
    parts = str(text or "").strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"window {text!r} must be written VAR:DURATION:STAT, e.g. temp_c:P3D:max")
    column, duration, statistic = (p.strip() for p in parts)
    if column not in WINDOW_COLUMNS:
        raise ValueError(f"{column!r} has no hourly data for a window; choose one of: {', '.join(WINDOW_COLUMNS)}")
    duration = duration.upper()
    duration_to_timedelta(duration)
    if statistic not in STATISTICS:
        raise ValueError(f"statistic {statistic!r} is not one of: {', '.join(STATISTICS)}")
    return WindowSpec(column, duration, statistic)


def window_column_name(spec: WindowSpec) -> str:
    return f"{spec.column}_{spec.statistic}_{spec.duration.lower()}"


def _bounds(end: datetime, spec: WindowSpec) -> tuple[datetime, datetime]:
    """The half-open window (start, last]: last = the session's hour, start = last - duration."""
    last = end.replace(tzinfo=None, minute=0, second=0, microsecond=0)
    return last - duration_to_timedelta(spec.duration), last


def missing_hours(hourly: dict[str, float | None], end: datetime, spec: WindowSpec) -> int:
    """Hours of the window without a value: hours with None, plus the in-window hours of days the provider
    returned nothing for (a failed fetch, no history that far back). Expected hours of a day that has data are
    the provider's own timeline, so a local hour that does not exist (spring DST) is not missing."""
    start, last = _bounds(end, spec)
    missing, days_with_data = 0, set()
    for key, value in hourly.items():
        days_with_data.add(key[:10])
        if value is None and start < datetime.fromisoformat(key) <= last:
            missing += 1
    t = last
    while t > start:  # wall-clock hours, only for days without any provider data
        if t.strftime("%Y-%m-%d") not in days_with_data:
            missing += 1
        t -= timedelta(hours=1)
    return missing


def compute_window(hourly: dict[str, float | None], end: datetime, spec: WindowSpec) -> float | None:
    """The statistic over the hours in (end - duration, end] (session hour in, start hour out), gaps and
    missing hours skipped; None when nothing is left. Hours are local wall-clock time (Open-Meteo
    timezone=auto, like the session timestamp), so a P1D window spanning a DST change covers 23 or 25 real hours."""
    start, last = _bounds(end, spec)
    values = [float(v) for key, v in hourly.items() if v is not None and start < datetime.fromisoformat(key) <= last]
    if not values:
        return None
    if spec.statistic == "count":
        return len(values)
    statistic = {"mean": lambda v: sum(v) / len(v), "min": min, "max": max, "sum": sum}[spec.statistic]
    return round(statistic(values), 4)
