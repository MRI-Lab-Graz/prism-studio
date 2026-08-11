import json
import tempfile
from pathlib import Path

import pandas as pd

from src.web.blueprints.conversion_participants_mapping import (
    _resolve_additional_preview_columns,
)


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

        result = _resolve_additional_preview_columns(
            _df(), project_root, {"site"}, ""
        )

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
