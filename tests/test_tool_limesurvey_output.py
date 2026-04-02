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


def test_write_tool_limesurvey_files(tmp_path):
    """Test that tool-limesurvey TSV + JSON sidecar files are written correctly."""
    import json
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
        "grouptime101": ["600", "400"],
        "PANAS01": [3, 4],  # survey data - should not appear
    })

    output_root = tmp_path / "output"
    output_root.mkdir()

    n = _write_tool_limesurvey_files(
        df=df,
        ls_system_cols=["submitdate", "startdate", "seed", "token", "ipaddr", "interviewtime", "grouptime101"],
        res_id_col="participant_id",
        res_ses_col=None,
        session="1",
        output_root=output_root,
        normalize_sub_fn=lambda x: str(x) if str(x).startswith("sub-") else f"sub-{x}",
        normalize_ses_fn=lambda x: f"ses-{x}" if not str(x).startswith("ses-") else str(x),
        ensure_dir_fn=lambda p: (p.mkdir(parents=True, exist_ok=True), p)[-1],
        build_bids_survey_filename_fn=lambda *a, **kw: "dummy.tsv",
        ls_metadata={"survey_id": "999", "survey_title": "Test Survey", "tool_version": "6.0.0"},
    )

    assert n == 2

    # Check files exist
    sub01_dir = output_root / "sub-01" / "ses-1" / "survey"
    sub02_dir = output_root / "sub-02" / "ses-1" / "survey"
    assert sub01_dir.exists()
    assert sub02_dir.exists()

    # Find TSV files
    tsv_files = list(sub01_dir.glob("*tool-limesurvey*.tsv"))
    assert len(tsv_files) == 1

    # Verify TSV content
    with open(tsv_files[0], "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    assert row["submitdate"] == "2026-01-15 10:30:00"
    assert row["startdate"] == "2026-01-15 10:00:00"
    assert row["seed"] == "12345"
    assert row["grouptime101"] == "600"
    assert "PANAS01" not in row  # survey data excluded
    assert "SurveyDuration_minutes" in row
    assert float(row["SurveyDuration_minutes"]) == 30.0
    assert row["CompletionStatus"] == "complete"

    # Find and verify JSON sidecar
    json_files = list(sub01_dir.glob("*tool-limesurvey*.json"))
    assert len(json_files) == 1

    with open(json_files[0], "r", encoding="utf-8") as f:
        sidecar = json.load(f)

    # Metadata
    assert sidecar["Metadata"]["SchemaVersion"] == "1.0.0"
    assert sidecar["Metadata"]["Tool"] == "LimeSurvey"
    assert sidecar["Metadata"]["ToolVersion"] == "6.0.0"
    assert sidecar["Metadata"]["SurveyId"] == "999"
    assert sidecar["Metadata"]["SurveyTitle"] == "Test Survey"

    # SystemFields
    assert "submitdate" in sidecar["SystemFields"]
    assert sidecar["SystemFields"]["submitdate"]["Format"] == "ISO8601"
    assert sidecar["SystemFields"]["token"]["Sensitive"] is True
    assert sidecar["SystemFields"]["ipaddr"]["Sensitive"] is True
    assert "interviewtime" in sidecar["SystemFields"]
    assert sidecar["SystemFields"]["interviewtime"]["Unit"] == "seconds"

    # Timings (grouptime columns)
    assert "Timings" in sidecar
    assert "grouptime101" in sidecar["Timings"]
    assert sidecar["Timings"]["grouptime101"]["Unit"] == "seconds"

    # DerivedFields
    assert "DerivedFields" in sidecar
    assert "SurveyDuration_minutes" in sidecar["DerivedFields"]
    assert "CompletionStatus" in sidecar["DerivedFields"]


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
