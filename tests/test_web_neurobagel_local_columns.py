"""Unit tests for src.web.neurobagel.sample_local_participant_columns.

Extracted from app/src/web/blueprints/neurobagel.py's inline pandas logic
so both the Flask route and the new
`participants neurobagel-schema` CLI command share one implementation.
See docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P2.
"""

import pandas as pd

from src.web.neurobagel import sample_local_participant_columns


def test_returns_empty_dict_when_file_missing(tmp_path):
    assert sample_local_participant_columns(str(tmp_path / "missing.tsv")) == {}


def test_excludes_id_columns(tmp_path):
    tsv_path = tmp_path / "participants.tsv"
    pd.DataFrame({"participant_id": ["001", "002"], "sex": ["F", "M"]}).to_csv(
        tsv_path, sep="\t", index=False
    )

    result = sample_local_participant_columns(str(tsv_path))

    assert "participant_id" not in result
    assert result["sex"] == ["F", "M"]


def test_excludes_summary_columns(tmp_path):
    tsv_path = tmp_path / "participants.tsv"
    pd.DataFrame(
        {
            "participant_id": ["001"],
            "session": ["1"],
            "run": ["1"],
            "sex": ["F"],
        }
    ).to_csv(tsv_path, sep="\t", index=False)

    result = sample_local_participant_columns(str(tsv_path))

    assert "session" not in result
    assert "run" not in result
    assert result["sex"] == ["F"]


def test_caps_unique_values_at_fifty(tmp_path):
    tsv_path = tmp_path / "participants.tsv"
    pd.DataFrame({"participant_id": [str(i) for i in range(60)], "age": list(range(60))}).to_csv(
        tsv_path, sep="\t", index=False
    )

    result = sample_local_participant_columns(str(tsv_path))

    assert len(result["age"]) == 50


def test_values_sorted_and_stringified(tmp_path):
    tsv_path = tmp_path / "participants.tsv"
    pd.DataFrame({"participant_id": ["001", "002", "003"], "group": ["b", "a", "c"]}).to_csv(
        tsv_path, sep="\t", index=False
    )

    result = sample_local_participant_columns(str(tsv_path))

    assert result["group"] == ["a", "b", "c"]
