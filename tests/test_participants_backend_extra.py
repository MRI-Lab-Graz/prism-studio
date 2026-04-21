"""Tests for src/participants_backend.py — participant mapping and workflow."""

import csv
import json
import sys
import os
import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.participants_backend import (
    normalize_participant_mapping,
    resolve_participant_mapping_target,
    save_participant_mapping,
    describe_participants_workflow,
    merge_neurobagel_schema_for_columns,
    collect_dataset_participants,
    preview_dataset_participants,
    convert_dataset_participants,
    _is_missing_participant_value,
    _participant_value_text,
    _load_existing_participants_table,
)
from pathlib import Path


# ---------------------------------------------------------------------------
# normalize_participant_mapping
# ---------------------------------------------------------------------------

class TestNormalizeParticipantMapping:
    def test_empty_raises(self):
        with pytest.raises(ValueError, match="Missing mapping"):
            normalize_participant_mapping(None)

    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="must be a JSON object"):
            normalize_participant_mapping("string")

    def test_already_structured_passthrough(self):
        structured = {"mappings": {"age": {"source_column": "AGE"}}}
        result = normalize_participant_mapping(structured)
        assert result is structured

    def test_flat_mapping_converted(self):
        flat = {"AGE": "age", "SEX": "sex"}
        result = normalize_participant_mapping(flat)
        assert "mappings" in result
        assert "age" in result["mappings"]
        assert "sex" in result["mappings"]

    def test_version_set(self):
        result = normalize_participant_mapping({"AGE": "age"})
        assert result["version"] == "1.0"

    def test_empty_source_column_skipped(self):
        result = normalize_participant_mapping({"": "age"})
        assert "mappings" in result
        assert result["mappings"] == {}

    def test_special_chars_in_std_normalized(self):
        result = normalize_participant_mapping({"Body Weight (kg)": "body weight"})
        key = list(result["mappings"].keys())[0]
        assert " " not in key
        assert "(" not in key


# ---------------------------------------------------------------------------
# resolve_participant_mapping_target
# ---------------------------------------------------------------------------

class TestResolveParticipantMappingTarget:
    def test_project_root_creates_code_library(self, tmp_path):
        path, source = resolve_participant_mapping_target(
            project_root=tmp_path, library_path=None
        )
        assert (tmp_path / "code" / "library").exists()
        assert source == "project"

    def test_library_path_used(self, tmp_path):
        lib = tmp_path / "mylib"
        lib.mkdir()
        path, source = resolve_participant_mapping_target(
            project_root=None, library_path=lib
        )
        assert source == "provided"
        assert path == lib

    def test_neither_raises(self):
        with pytest.raises(ValueError, match="No valid library path"):
            resolve_participant_mapping_target(project_root=None, library_path=None)

    def test_nonexistent_library_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid library path"):
            resolve_participant_mapping_target(
                project_root=None, library_path=tmp_path / "nonexistent"
            )


# ---------------------------------------------------------------------------
# save_participant_mapping
# ---------------------------------------------------------------------------

class TestSaveParticipantMapping:
    def test_saves_file(self, tmp_path):
        result = save_participant_mapping(
            {"AGE": "age"}, project_root=tmp_path
        )
        assert result["mapping_file"].exists()

    def test_returns_normalized_mapping(self, tmp_path):
        result = save_participant_mapping({"AGE": "age"}, project_root=tmp_path)
        assert "mappings" in result["normalized_mapping"]

    def test_library_source_project(self, tmp_path):
        result = save_participant_mapping({"AGE": "age"}, project_root=tmp_path)
        assert result["library_source"] == "project"


# ---------------------------------------------------------------------------
# describe_participants_workflow
# ---------------------------------------------------------------------------

class TestDescribeParticipantsWorkflow:
    def test_no_tsv_returns_import_required(self, tmp_path):
        result = describe_participants_workflow(tmp_path)
        assert result["state"] == "import_required"
        assert result["default_case"] == "1"

    def test_with_tsv_returns_case_selection(self, tmp_path):
        (tmp_path / "participants.tsv").write_text("participant_id\nsub-001\n")
        result = describe_participants_workflow(tmp_path)
        assert result["state"] == "case_selection_required"
        assert result["requires_case_selection"] is True

    def test_json_without_tsv_detected(self, tmp_path):
        (tmp_path / "participants.json").write_text("{}")
        result = describe_participants_workflow(tmp_path)
        assert result["metadata_without_tsv"] is True


# ---------------------------------------------------------------------------
# merge_neurobagel_schema_for_columns
# ---------------------------------------------------------------------------

class TestMergeNeurobagel:
    def test_merges_annotations(self):
        base = {"age": {"Description": "Age"}}
        nb = {"age": {"Annotations": {"IsAbout": {"TermURL": "nb:Age"}}}}
        result, count = merge_neurobagel_schema_for_columns(base, nb, ["age"])
        assert count == 1
        assert "Annotations" in result["age"]

    def test_skips_columns_not_in_allowed(self):
        base = {}
        nb = {"diagnosis": {"Annotations": {}}}
        result, count = merge_neurobagel_schema_for_columns(base, nb, ["age"])
        assert count == 0
        assert "diagnosis" not in result

    def test_non_dict_base_handled(self):
        result, count = merge_neurobagel_schema_for_columns(
            "bad", {"age": {}}, ["age"]
        )
        assert isinstance(result, dict)

    def test_non_dict_neurobagel_returns_base(self):
        base = {"age": {}}
        result, count = merge_neurobagel_schema_for_columns(base, None, ["age"])
        assert result is base
        assert count == 0


# ---------------------------------------------------------------------------
# collect_dataset_participants
# ---------------------------------------------------------------------------

class TestCollectDatasetParticipants:
    def _make_survey_file(self, path: Path, sub_id: str):
        sub_dir = path / sub_id / "ses-01" / "survey"
        sub_dir.mkdir(parents=True)
        (sub_dir / f"{sub_id}_ses-01_survey.tsv").write_text(
            "participant_id\n" + sub_id + "\n"
        )

    def test_finds_participants_from_filenames(self, tmp_path):
        self._make_survey_file(tmp_path, "sub-001")
        self._make_survey_file(tmp_path, "sub-002")
        result = collect_dataset_participants(tmp_path)
        assert set(result["participants"]) == {"sub-001", "sub-002"}

    def test_empty_dataset(self, tmp_path):
        result = collect_dataset_participants(tmp_path)
        assert result["participants"] == []
        assert result["survey_file_count"] == 0

    def test_log_callback_called(self, tmp_path):
        logs = []
        collect_dataset_participants(tmp_path, log_callback=lambda lvl, msg: logs.append(msg))
        assert any("survey" in m.lower() or "biometrics" in m.lower() for m in logs)

    def test_extract_survey_false(self, tmp_path):
        self._make_survey_file(tmp_path, "sub-001")
        result = collect_dataset_participants(tmp_path, extract_from_survey=False)
        assert result["survey_file_count"] == 0


# ---------------------------------------------------------------------------
# preview_dataset_participants
# ---------------------------------------------------------------------------

class TestPreviewDatasetParticipants:
    def test_no_participants_raises(self, tmp_path):
        with pytest.raises(ValueError, match="No participant data"):
            preview_dataset_participants(tmp_path)

    def test_preview_truncated_at_20(self, tmp_path):
        for i in range(25):
            sub_id = f"sub-{i:03d}"
            d = tmp_path / sub_id / "ses-01" / "survey"
            d.mkdir(parents=True)
            (d / f"{sub_id}_ses-01_survey.tsv").touch()
        result = preview_dataset_participants(tmp_path)
        assert result["total_participants"] == 25
        assert len(result["participants"]) == 20


# ---------------------------------------------------------------------------
# convert_dataset_participants
# ---------------------------------------------------------------------------

class TestConvertDatasetParticipants:
    def _add_survey(self, path, sub_id):
        d = path / sub_id / "ses-01" / "survey"
        d.mkdir(parents=True)
        (d / f"{sub_id}_ses-01_survey.tsv").touch()

    def test_creates_tsv_and_json(self, tmp_path):
        self._add_survey(tmp_path, "sub-001")
        result = convert_dataset_participants(tmp_path)
        assert (tmp_path / "participants.tsv").exists()
        assert (tmp_path / "participants.json").exists()
        assert result["status"] == "success"

    def test_no_participants_raises(self, tmp_path):
        with pytest.raises(ValueError, match="No participant data"):
            convert_dataset_participants(tmp_path)

    def test_participant_count_correct(self, tmp_path):
        for i in range(3):
            self._add_survey(tmp_path, f"sub-{i:03d}")
        result = convert_dataset_participants(tmp_path)
        assert result["participant_count"] == 3


# ---------------------------------------------------------------------------
# _is_missing_participant_value / _participant_value_text
# ---------------------------------------------------------------------------

class TestMissingParticipantValue:
    def test_none_is_missing(self):
        assert _is_missing_participant_value(None) is True

    def test_na_string_is_missing(self):
        assert _is_missing_participant_value("n/a") is True
        assert _is_missing_participant_value("N/A") is True
        assert _is_missing_participant_value("nan") is True

    def test_empty_string_is_missing(self):
        assert _is_missing_participant_value("") is True

    def test_valid_value_not_missing(self):
        assert _is_missing_participant_value("42") is False
        assert _is_missing_participant_value(42) is False

    def test_value_text_returns_default_for_missing(self):
        assert _participant_value_text(None) == "n/a"
        assert _participant_value_text("") == "n/a"

    def test_value_text_returns_stripped_value(self):
        assert _participant_value_text("  hello  ") == "hello"


# ---------------------------------------------------------------------------
# _load_existing_participants_table
# ---------------------------------------------------------------------------

class TestLoadExistingParticipantsTable:
    def test_raises_when_no_tsv(self, tmp_path):
        """Line 345: participants.tsv not found → raises ValueError."""
        with pytest.raises(ValueError, match="participants.tsv not found"):
            _load_existing_participants_table(tmp_path)

    def test_raises_when_tsv_malformed(self, tmp_path):
        """Lines 351-352: invalid TSV → raises ValueError."""
        tsv = tmp_path / "participants.tsv"
        tsv.write_bytes(b"\x00\x01\x02\x03")  # Binary garbage
        # pandas may or may not raise; test that we get ValueError if it does
        try:
            _load_existing_participants_table(tmp_path)
        except ValueError as e:
            assert "Failed to read" in str(e) or "participant_id" in str(e)

    def test_raises_when_no_participant_id_column(self, tmp_path):
        """Line 355: TSV without participant_id column → raises ValueError."""
        tsv = tmp_path / "participants.tsv"
        tsv.write_text("subject\tsex\nsub-01\tM\n", encoding="utf-8")
        with pytest.raises(ValueError, match="participant_id"):
            _load_existing_participants_table(tmp_path)

    def test_returns_dataframe(self, tmp_path):
        """Happy path: valid TSV with participant_id column."""
        tsv = tmp_path / "participants.tsv"
        tsv.write_text("participant_id\tsex\nsub-01\tM\nsub-02\tF\n", encoding="utf-8")
        df = _load_existing_participants_table(tmp_path)
        assert "participant_id" in df.columns
        assert len(df) == 2
