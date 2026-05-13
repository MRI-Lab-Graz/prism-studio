from __future__ import annotations


def handle_validate_environment_conversion_inputs(
    *,
    df,
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
    bids_label,
    log_callback,
) -> None:
    if not timestamp_col:
        raise ValueError("Timestamp column is required")
    if not participant_col:
        raise ValueError("Participant ID column is required")
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
        log_callback(
            f"Manual participant ID: '{bids_label(participant_override, 'sub')}'"
        )
    if session_col:
        log_callback(f"Session column: '{session_col}'")
    elif session_override:
        log_callback(f"Manual session: '{session_override}'")
    if location_col:
        log_callback(f"Location column: '{location_col}'")
    if lat_col and lon_col:
        log_callback(f"Per-row coordinates: '{lat_col}' + '{lon_col}'")
    if lat_manual is not None and lon_manual is not None:
        log_callback(
            f"Global fallback coordinates: ({lat_manual:.4f}, {lon_manual:.4f})"
        )