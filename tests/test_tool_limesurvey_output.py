"""Tests for LimeSurvey system variable separation in survey conversion."""
import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))


def test_extract_limesurvey_columns():
    """Verify system column detection identifies LS metadata columns."""
    from src.converters.survey_processing import _extract_limesurvey_columns

    columns = [
        "id", "submitdate", "startdate", "lastpage", "startlanguage",
        "seed", "token", "ipaddr", "interviewtime",
        "grouptime123", "grouptime456",
        "PANAS01", "PANAS02", "participant_id", "session",
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
    """Test individual column detection."""
    from src.converters.survey_processing import _is_limesurvey_system_column

    assert _is_limesurvey_system_column("submitdate") is True
    assert _is_limesurvey_system_column("startdate") is True
    assert _is_limesurvey_system_column("seed") is True
    assert _is_limesurvey_system_column("grouptime123") is True
    assert _is_limesurvey_system_column("duration_42") is True
    assert _is_limesurvey_system_column("PANAS01") is False
    assert _is_limesurvey_system_column("participant_id") is False


def test_write_tool_limesurvey_files(tmp_path):
    """Test that tool-limesurvey TSV files are written correctly."""
    import pandas as pd
    from src.converters.survey_io import _write_tool_limesurvey_files

    df = pd.DataFrame({
        "participant_id": ["sub-01", "sub-02"],
        "submitdate": ["2026-01-15 10:30:00", "2026-01-15 11:00:00"],
        "startdate": ["2026-01-15 10:00:00", "2026-01-15 10:30:00"],
        "seed": ["12345", "67890"],
        "token": ["abc", "def"],
        "ipaddr": ["127.0.0.1", "192.168.1.1"],
        "interviewtime": ["1800", "1200"],
        "PANAS01": [3, 4],  # survey data - should not appear
    })

    output_root = tmp_path / "output"
    output_root.mkdir()

    n = _write_tool_limesurvey_files(
        df=df,
        ls_system_cols=["submitdate", "startdate", "seed", "token", "ipaddr", "interviewtime"],
        res_id_col="participant_id",
        res_ses_col=None,
        session="1",
        output_root=output_root,
        normalize_sub_fn=lambda x: str(x) if str(x).startswith("sub-") else f"sub-{x}",
        normalize_ses_fn=lambda x: f"ses-{x}" if not str(x).startswith("ses-") else str(x),
        ensure_dir_fn=lambda p: (p.mkdir(parents=True, exist_ok=True), p)[-1],
        build_bids_survey_filename_fn=lambda *a, **kw: "dummy.tsv",
    )

    assert n == 2

    # Check files exist
    sub01_dir = output_root / "sub-01" / "ses-1" / "survey"
    sub02_dir = output_root / "sub-02" / "ses-1" / "survey"
    assert sub01_dir.exists()
    assert sub02_dir.exists()

    # Find the tool-limesurvey files
    ls_files_1 = list(sub01_dir.glob("*tool-limesurvey*"))
    ls_files_2 = list(sub02_dir.glob("*tool-limesurvey*"))
    assert len(ls_files_1) == 1
    assert len(ls_files_2) == 1

    # Read and verify content
    with open(ls_files_1[0], "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    assert row["submitdate"] == "2026-01-15 10:30:00"
    assert row["startdate"] == "2026-01-15 10:00:00"
    assert row["seed"] == "12345"
    assert "PANAS01" not in row  # survey data excluded
    assert "SurveyDuration_minutes" in row
    assert float(row["SurveyDuration_minutes"]) == 30.0
    assert row["CompletionStatus"] == "complete"


def test_write_tool_limesurvey_empty_cols(tmp_path):
    """No files written when ls_system_cols is empty."""
    import pandas as pd
    from src.converters.survey_io import _write_tool_limesurvey_files

    df = pd.DataFrame({"participant_id": ["sub-01"], "Q1": [1]})
    output_root = tmp_path / "output"
    output_root.mkdir()

    n = _write_tool_limesurvey_files(
        df=df,
        ls_system_cols=[],
        res_id_col="participant_id",
        res_ses_col=None,
        session="1",
        output_root=output_root,
        normalize_sub_fn=lambda x: str(x),
        normalize_ses_fn=lambda x: f"ses-{x}",
        ensure_dir_fn=lambda p: (p.mkdir(parents=True, exist_ok=True), p)[-1],
        build_bids_survey_filename_fn=lambda *a, **kw: "dummy.tsv",
    )
    assert n == 0
