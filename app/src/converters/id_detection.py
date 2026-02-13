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
        
        # Create helpful error message with context
        format_names = {
            "lsa": "LimeSurvey Archive (.lsa)",
            "xlsx": "Excel file (.xlsx)",
            "csv": "CSV file",
            "tsv": "TSV file"
        }
        format_name = format_names.get(source_format, source_format)
        
        limesurvey_note = "For LimeSurvey: also accepts \"token\" or \"id\" if PRISMMETA columns are present.\n\n" if source_format == 'lsa' else "\n"
        
        super().__init__(
            f"❌ Participant ID column not found in {format_name}.\n\n"
            f"PRISM looks for columns named: 'participant_id', 'prism_participant_id', 'participantid'\n"
            f"{limesurvey_note}"
            f"📋 Available columns in your file ({len(available_columns)} total):\n"
            f"   {', '.join(available_columns[:30])}"
            f"{'...' if len(available_columns) > 30 else ''}\n\n"
            f"💡 Solution: Add a 'participant_id' column to your data, or select the ID column manually in the interface."
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
