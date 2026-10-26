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


def _in_window(hourly: dict[str, float | None], end: datetime, spec: WindowSpec):
    end = end.replace(tzinfo=None)  # provider hours are local wall-clock, like the session timestamp
    start = end - duration_to_timedelta(spec.duration)
    for key, value in hourly.items():
        if start <= datetime.fromisoformat(key) <= end:
            yield value


def window_covered(hourly: dict[str, float | None], end: datetime, spec: WindowSpec) -> bool:
    """False when the provider returned no hours at the window's start or end (e.g. no history that far back)."""
    end = end.replace(tzinfo=None)
    start = end - duration_to_timedelta(spec.duration)
    first = start.replace(minute=0, second=0, microsecond=0)
    if first < start:
        first += timedelta(hours=1)
    last = end.replace(minute=0, second=0, microsecond=0)
    return first > last or (first.strftime("%Y-%m-%dT%H:00") in hourly and last.strftime("%Y-%m-%dT%H:00") in hourly)


def compute_window(hourly: dict[str, float | None], end: datetime, spec: WindowSpec) -> float | None:
    values = [float(v) for v in _in_window(hourly, end, spec) if v is not None]
    if not values:
        return None
    if spec.statistic == "count":
        return len(values)
    statistic = {"mean": lambda v: sum(v) / len(v), "min": min, "max": max, "sum": sum}[spec.statistic]
    return round(statistic(values), 4)
