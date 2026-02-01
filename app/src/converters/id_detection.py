"""Universal participant ID column detection for PRISM converters."""

PRISM_ID_OUTPUT_COLUMN = "participant_id"

# PRISM identifier names (original + LS-mangled forms)
_PRISM_ID_CANDIDATES = [
    "participant_id",
    "participantid",  # LimeSurvey strips underscores
    "prism_participant_id",
    "prismparticipantid",  # LimeSurvey strips underscores
]

# Additional fallback for LSA files with PRISMMETA signal
_LSA_PRISMMETA_FALLBACK = ["token", "id"]


class IdColumnNotDetectedError(ValueError):
    """Raised when manual ID column selection is required."""

    def __init__(self, available_columns: list[str], source_format: str):
        self.available_columns = available_columns
        self.source_format = source_format
        super().__init__(
            f"Cannot auto-detect participant ID column for {source_format} data. "
            f"Please select the ID column manually. "
            f"Available columns: {', '.join(available_columns[:20])}"
        )


def detect_id_column(
    df_columns: list[str],
    source_format: str,
    explicit_id_column: str | None = None,
    has_prismmeta: bool = False,
) -> str | None:
    """Universal ID column detection.

    Returns column name if detected, None if manual selection required.
    Raises ValueError if explicit_id_column specified but not found.

    Auto-detect priority:
    1. participant_id / participantid (PRISM primary)
    2. prism_participant_id / prismparticipantid (PRISM alternative)
    3. token / id (LSA + PRISMMETA only)
    """
    lower_map = {str(c).strip().lower(): str(c).strip() for c in df_columns}

    # Priority 1: Explicit user selection always wins
    if explicit_id_column:
        if explicit_id_column.lower() in lower_map:
            return lower_map[explicit_id_column.lower()]
        raise ValueError(
            f"ID column '{explicit_id_column}' not found. "
            f"Available: {', '.join(str(c) for c in df_columns)}"
        )

    # Priority 2: PRISM identifier (all formats)
    for candidate in _PRISM_ID_CANDIDATES:
        if candidate in lower_map:
            return lower_map[candidate]

    # Priority 3: LSA + PRISMMETA fallback
    if source_format == "lsa" and has_prismmeta:
        for candidate in _LSA_PRISMMETA_FALLBACK:
            if candidate in lower_map:
                return lower_map[candidate]

    return None


def has_prismmeta_columns(columns: list[str]) -> bool:
    """Check if column list contains PRISMMETA equation columns."""
    return any(str(c).upper().startswith("PRISMMETA") for c in columns)
