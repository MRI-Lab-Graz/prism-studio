"""Survey column classification and run-parsing helpers.

This module contains low-level, pure helper functions used by survey conversion
to classify LimeSurvey system columns and parse run suffixes from item columns.
"""

from __future__ import annotations

import re


# Patterns to detect run suffix in column names.
# BIDS format:      {QUESTIONNAIRE}_{ITEM}_run-{NN}  e.g. SWLS01_run-02
# LimeSurvey format: {CODE}run{NN}                   e.g. SWLS01run02
# We try the more specific BIDS pattern first, then the LimeSurvey pattern.
_RUN_SUFFIX_PATTERNS = [
    re.compile(r"^(.+)_run-?(\d+)$", re.IGNORECASE),  # BIDS: SWLS01_run-02
    re.compile(r"^(.+?)run(\d{2,})$", re.IGNORECASE),  # LimeSurvey: SWLS01run02
]


# LimeSurvey system columns - these are platform metadata, not questionnaire responses
# They should be extracted to a separate tool-limesurvey file
LIMESURVEY_SYSTEM_COLUMNS = {
    # Core system fields
    "id",  # LimeSurvey response ID
    "submitdate",  # Survey completion timestamp
    "startdate",  # Survey start timestamp
    "datestamp",  # Date stamp
    "lastpage",  # Last page viewed
    "startlanguage",  # Language at start
    "seed",  # Randomization seed
    "token",  # Participant token
    "ipaddr",  # IP address (sensitive)
    "refurl",  # Referrer URL
    # Timing fields
    "interviewtime",  # Total interview time
    # Other common LimeSurvey fields
    "optout",  # Opt-out status
    "emailstatus",  # Email status
    "attribute_1",  # Custom attributes
    "attribute_2",
    "attribute_3",
}


# Pattern for LimeSurvey group timing columns: groupTime123, grouptime456, etc.
_LS_TIMING_PATTERN = re.compile(r"^grouptime\d+$", re.IGNORECASE)


def _is_limesurvey_system_column(column_name: str) -> bool:
    """Check if a column is a LimeSurvey system/metadata column."""
    col_lower = column_name.strip().lower()

    if col_lower in LIMESURVEY_SYSTEM_COLUMNS:
        return True

    if _LS_TIMING_PATTERN.match(col_lower):
        return True

    if col_lower.startswith("duration_"):
        return True

    return False


def _extract_limesurvey_columns(df_columns: list[str]) -> tuple[list[str], list[str]]:
    """Separate LimeSurvey system columns from questionnaire columns."""
    ls_cols = []
    other_cols = []

    for col in df_columns:
        if _is_limesurvey_system_column(col):
            ls_cols.append(col)
        else:
            other_cols.append(col)

    return ls_cols, other_cols


def _parse_run_from_column(column_name: str) -> tuple[str, int | None]:
    """Parse run information from a column name."""
    stripped = column_name.strip()
    for pattern in _RUN_SUFFIX_PATTERNS:
        m = pattern.match(stripped)
        if m:
            base_name = m.group(1)
            run_num = int(m.group(2))
            return base_name, run_num
    return column_name, None


def _group_columns_by_run(columns: list[str]) -> dict[str, dict[int | None, list[str]]]:
    """Group columns by their base name and run number."""
    grouped: dict[str, dict[int | None, list[str]]] = {}
    for col in columns:
        base_name, run_num = _parse_run_from_column(col)
        if base_name not in grouped:
            grouped[base_name] = {}
        if run_num not in grouped[base_name]:
            grouped[base_name][run_num] = []
        grouped[base_name][run_num].append(col)
    return grouped
