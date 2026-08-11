import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest
from flask import Flask

from src.web.blueprints.conversion_participants_io import _diagnose_preview_error
from src.web.blueprints.conversion_participants_mapping import (
    _resolve_additional_preview_columns,
)

_app = Flask(__name__)


@pytest.fixture(autouse=True)
def _app_context():
    with _app.app_context():
        yield


def _df():
    return pd.DataFrame({"participant_id": ["sub-001"], "age": [21], "site": ["A"]})


def test_no_project_root_and_no_extra_columns_returns_empty():
    assert _resolve_additional_preview_columns(_df(), None, set(), "") == []


def test_columns_from_saved_mapping_are_included():
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        mapping_path = project_root / "participants_mapping.json"
        mapping_path.write_text(
            json.dumps({"mappings": {"site": {"source_column": "site"}}})
        )

        result = _resolve_additional_preview_columns(_df(), project_root, set(), "")

        assert "site" in result


def test_excluded_column_from_saved_mapping_is_skipped():
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        mapping_path = project_root / "participants_mapping.json"
        mapping_path.write_text(
            json.dumps({"mappings": {"site": {"source_column": "site"}}})
        )

        result = _resolve_additional_preview_columns(_df(), project_root, {"site"}, "")

        assert "site" not in result


def test_columns_from_extra_columns_json_are_included():
    result = _resolve_additional_preview_columns(
        _df(), None, set(), json.dumps(["age"])
    )

    assert result == ["age"]


def test_column_not_present_in_df_is_ignored():
    result = _resolve_additional_preview_columns(
        _df(), None, set(), json.dumps(["not_a_real_column"])
    )

    assert result == []


def test_mixed_time_format_column_produces_400_with_error_code():
    df = pd.DataFrame({"duration": ["10:30", "2h", "10:45", "3h"]})

    response, status_code = _diagnose_preview_error(
        exc=ValueError("boom"),
        df=df,
        input_path=None,
        suffix=None,
        sheet_arg=0,
        separator_option="auto",
        preview_stage="reading input file",
    )

    assert status_code == 400
    body = response.get_json()
    assert body["error_code"] == "mixed_time_formats"
    assert body["problem_columns"][0]["column"] == "duration"


def test_generic_exception_without_df_produces_500_with_message():
    response, status_code = _diagnose_preview_error(
        exc=ValueError("something broke"),
        df=None,
        input_path=None,
        suffix=None,
        sheet_arg=0,
        separator_option="auto",
        preview_stage="detecting participant ID column",
    )

    assert status_code == 500
    body = response.get_json()
    assert body["error"] == "something broke"
    assert body["error_type"] == "ValueError"
    assert body["error_stage"] == "detecting participant ID column"


def test_pattern_mismatch_message_is_rewritten_with_stage():
    response, status_code = _diagnose_preview_error(
        exc=ValueError("The string did not match the expected pattern."),
        df=None,
        input_path=None,
        suffix=None,
        sheet_arg=0,
        separator_option="auto",
        preview_stage="resolving template library",
    )

    assert status_code == 500
    body = response.get_json()
    assert "resolving template library" in body["error"]


def test_missing_preview_stage_defaults_to_unknown_stage():
    response, status_code = _diagnose_preview_error(
        exc=ValueError("boom"),
        df=None,
        input_path=None,
        suffix=None,
        sheet_arg=0,
        separator_option="auto",
        preview_stage=None,
    )

    body = response.get_json()
    assert body["error_stage"] == "unknown stage"
