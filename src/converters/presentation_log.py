"""Generic parser for Neurobehavioral Systems Presentation .log files.

Knows nothing about any particular experiment's event-code meaning -- it
only understands Presentation's own log format: tab-delimited rows whose
width depends on Event Type, Time/Duration/TTime in 0.1 ms ticks, and Pulse
rows marking scanner triggers. Task-specific decoding of what a Code string
like "Item_1_1" means belongs in src/converters/presentation_tasks/.
"""

import re
import warnings
from typing import Any, Dict, Optional

import pandas as pd

_TICKS_PER_SECOND = 10000.0
_TICKS_PER_MS = 10.0

_HEADER_FIELDS = ("Subject", "Trial", "Event Type", "Code", "Time", "TTime")


def parse_presentation_log(log_text: str) -> pd.DataFrame:
    """Parse Presentation .log text into a generic intermediate event table.

    Onset/duration are in seconds, aligned so the first Pulse row's Time is
    onset 0 (or the first data row's Time if the log has no Pulse rows).
    Pulse rows themselves are excluded from the output -- they only serve
    as the alignment reference. A Quit row (experimenter aborted the
    session) is also excluded, with a warning, since it carries no stimulus
    data and marks the run as truncated. Each Response row's TTime is the reaction
    time since the row that last reset Presentation's clock, so it is
    merged onto that preceding stimulus row as response_time_ms /
    response_button_code rather than kept as its own row.

    Returns a DataFrame with columns: trial_number, raw_code, onset,
    duration, onset_uncertainty_ms, duration_uncertainty_ms,
    response_time_ms, response_button_code.
    """
    rows = []
    t0_ticks: Optional[int] = None

    for raw_line in log_text.splitlines():
        fields = raw_line.split("\t")
        if len(fields) < len(_HEADER_FIELDS) or fields[0] in _HEADER_FIELDS:
            continue

        event_type = fields[2]
        try:
            time_ticks = int(fields[4])
            ttime_ticks = int(fields[5])
        except (ValueError, IndexError):
            continue

        if event_type == "Pulse":
            if t0_ticks is None:
                t0_ticks = time_ticks
            continue

        if event_type == "Quit":
            warnings.warn(
                f"Presentation log: session aborted early (Quit event at trial "
                f"{fields[1]}) -- data after this point is missing.",
                stacklevel=2,
            )
            continue

        if t0_ticks is None:
            t0_ticks = time_ticks

        if event_type == "Response":
            if rows:
                rows[-1]["response_time_ms"] = ttime_ticks / _TICKS_PER_MS
                rows[-1]["response_button_code"] = fields[3]
            continue

        onset_uncertainty_ticks = int(fields[6]) if len(fields) > 6 and fields[6] else None
        duration_ticks = int(fields[7]) if len(fields) > 7 and fields[7] else 0
        duration_uncertainty_ticks = int(fields[8]) if len(fields) > 8 and fields[8] else None

        rows.append(
            {
                "trial_number": int(fields[1]),
                "raw_code": fields[3],
                "onset": (time_ticks - t0_ticks) / _TICKS_PER_SECOND,
                "duration": duration_ticks / _TICKS_PER_SECOND,
                "onset_uncertainty_ms": (
                    onset_uncertainty_ticks / _TICKS_PER_MS
                    if onset_uncertainty_ticks is not None
                    else None
                ),
                "duration_uncertainty_ms": (
                    duration_uncertainty_ticks / _TICKS_PER_MS
                    if duration_uncertainty_ticks is not None
                    else None
                ),
                "response_time_ms": None,
                "response_button_code": None,
            }
        )

    return pd.DataFrame(rows)


def extract_subject_id(log_text: str) -> Optional[str]:
    """Return the Subject field from a Presentation .log's first data row.

    Presentation experiments commonly write a second, custom per-subject
    log file named after this exact string (e.g. NID.pcl's
    `customLog.open("log\\" + subjectId + ".txt")`); this is the join key
    for attaching that companion file's data back onto the parsed events.
    """
    for raw_line in log_text.splitlines():
        fields = raw_line.split("\t")
        if len(fields) < len(_HEADER_FIELDS) or fields[0] in _HEADER_FIELDS or not fields[0]:
            continue
        return fields[0]
    return None


def parse_sce_metadata(sce_text: str) -> Dict[str, Any]:
    """Extract pulse/button declarations from a Presentation .sce scenario file.

    Returns {"pulse_code": int | None, "button_codes": list[int],
    "active_buttons": int | None} for use as StimulusPresentation provenance
    and for decoding which physical button a response code corresponds to.
    """
    pulse_match = re.search(r"pulse_code\s*=\s*(\d+)", sce_text)
    buttons_match = re.search(r"button_codes\s*=\s*([\d,\s]+);", sce_text)
    active_match = re.search(r"active_buttons\s*=\s*(\d+)", sce_text)

    return {
        "pulse_code": int(pulse_match.group(1)) if pulse_match else None,
        "button_codes": (
            [int(code) for code in buttons_match.group(1).split(",") if code.strip()]
            if buttons_match
            else []
        ),
        "active_buttons": int(active_match.group(1)) if active_match else None,
    }
