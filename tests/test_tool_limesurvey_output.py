"""Tests for LimeSurvey system variable separation in survey conversion."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))


def test_extract_limesurvey_columns():
    """Verify system column detection identifies LS metadata columns."""
    from src.converters.survey_processing import _extract_limesurvey_columns

    columns = [
        "id",
        "submitdate",
        "startdate",
        "lastpage",
        "startlanguage",
        "seed",
        "token",
        "ipaddr",
        "interviewtime",
        "grouptime123",
        "grouptime456",
        "PANAS01",
        "PANAS02",
        "participant_id",
        "session",
    ]
    ls_cols, other_cols = _extract_limesurvey_columns(columns)

    assert "id" in ls_cols
    assert "submitdate" in ls_cols
    assert "startdate" in ls_cols
    assert "seed" in ls_cols
    assert "token" in ls_cols
    assert "ipaddr" in ls_cols
    assert "interviewtime" in ls_cols
    assert "grouptime123" in ls_cols
    assert "grouptime456" in ls_cols

    assert "PANAS01" in other_cols
    assert "PANAS02" in other_cols
    assert "participant_id" in other_cols


def test_is_limesurvey_system_column():
    """Test individual column detection across all LS versions."""
    from src.converters.survey_processing import _is_limesurvey_system_column

    # Core default columns (always present)
    assert _is_limesurvey_system_column("id") is True
    assert _is_limesurvey_system_column("submitdate") is True
    assert _is_limesurvey_system_column("lastpage") is True
    assert _is_limesurvey_system_column("startlanguage") is True
    assert _is_limesurvey_system_column("completed") is True
    assert _is_limesurvey_system_column("seed") is True
    assert _is_limesurvey_system_column("token") is True

    # Optional columns
    assert _is_limesurvey_system_column("startdate") is True
    assert _is_limesurvey_system_column("datestamp") is True
    assert _is_limesurvey_system_column("ipaddr") is True
    assert _is_limesurvey_system_column("refurl") is True

    # Timing columns
    assert _is_limesurvey_system_column("interviewtime") is True
    assert _is_limesurvey_system_column("grouptime123") is True
    assert _is_limesurvey_system_column("groupTime456") is True  # case insensitive
    assert _is_limesurvey_system_column("questiontime789") is True  # LS 5+
    assert _is_limesurvey_system_column("duration_42") is True

    # Participant attributes
    assert _is_limesurvey_system_column("attribute_1") is True
    assert _is_limesurvey_system_column("attribute_4") is True  # beyond standard 1-3
    assert _is_limesurvey_system_column("attribute_10") is True

    # NOT system columns
    assert _is_limesurvey_system_column("PANAS01") is False
    assert _is_limesurvey_system_column("participant_id") is False
    assert _is_limesurvey_system_column("Q1") is False
