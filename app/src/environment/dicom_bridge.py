from __future__ import annotations

from datetime import datetime
from typing import Mapping

FORBIDDEN_OUTPUT_FIELDS = {
    "date",
    "datetime",
    "timestamp",
    "acquisition_datetime",
    "acquisition_time",
}


def _datetime_to_anchor(value: str) -> str:
    normalized = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    return f"{dt.year}-DOY{dt.timetuple().tm_yday:03d}-H{dt.hour:02d}"


def _date_time_to_anchor(date_value: str, time_value: str) -> str:
    combined = f"{date_value.strip()}T{time_value.strip()}"
    return _datetime_to_anchor(combined)


def read_prism_time_anchor(row: Mapping[str, str]) -> str:
    anchor = row.get("prism_time_anchor", "").strip()
    if anchor:
        return anchor

    acquisition_datetime = row.get("acquisition_datetime", "").strip()
    if acquisition_datetime:
        return _datetime_to_anchor(acquisition_datetime)

    acquisition_date = row.get("acquisition_date", "").strip()
    acquisition_time = row.get("acquisition_time", "").strip()
    if acquisition_date and acquisition_time:
        return _date_time_to_anchor(acquisition_date, acquisition_time)

    relative_hour = row.get("session_relative_hour", "").strip()
    if relative_hour:
        return f"relative-hour-{relative_hour}"

    raise ValueError(
        "Missing temporal input. Provide prism_time_anchor, acquisition_datetime, "
        "acquisition_date+acquisition_time, or session_relative_hour."
    )
