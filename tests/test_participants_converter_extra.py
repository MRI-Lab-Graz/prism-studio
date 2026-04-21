"""Additional tests for src/participants_converter.py — static helpers and edge cases."""

import sys
import os
import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.participants_converter import ParticipantsConverter
from src.participants_converter import apply_participants_mapping


# ---------------------------------------------------------------------------
# _normalize_participant_id
# ---------------------------------------------------------------------------

class TestNormalizeParticipantId:
    def test_bare_number(self):
        assert ParticipantsConverter._normalize_participant_id("001") == "sub-001"

    def test_already_sub_prefix(self):
        assert ParticipantsConverter._normalize_participant_id("sub-001") == "sub-001"

    def test_sub_prefix_uppercase(self):
        assert ParticipantsConverter._normalize_participant_id("SUB-01") == "sub-01"

    def test_none_returns_none(self):
        assert ParticipantsConverter._normalize_participant_id(None) is None

    def test_empty_returns_none(self):
        assert ParticipantsConverter._normalize_participant_id("") is None

    def test_nan_returns_none(self):
        assert ParticipantsConverter._normalize_participant_id("nan") is None

    def test_strips_special_chars(self):
        result = ParticipantsConverter._normalize_participant_id("sub-001_extra")
        assert result == "sub-001extra"


# ---------------------------------------------------------------------------
# _find_participant_id_source_column
# ---------------------------------------------------------------------------

class TestFindParticipantIdSourceColumn:
    def test_finds_participant_id(self):
        result = ParticipantsConverter._find_participant_id_source_column(
            ["participant_id", "age", "sex"]
        )
        assert result == "participant_id"

    def test_finds_subject_id(self):
        result = ParticipantsConverter._find_participant_id_source_column(
            ["age", "subject_id", "sex"]
        )
        assert result == "subject_id"

    def test_case_insensitive(self):
        result = ParticipantsConverter._find_participant_id_source_column(
            ["age", "Participant_ID"]
        )
        assert result == "Participant_ID"

    def test_fallback_to_participant_plus_id(self):
        result = ParticipantsConverter._find_participant_id_source_column(
            ["my_participant_id_number"]
        )
        assert result == "my_participant_id_number"

    def test_empty_columns_returns_none(self):
        assert ParticipantsConverter._find_participant_id_source_column([]) is None

    def test_no_match_returns_none(self):
        result = ParticipantsConverter._find_participant_id_source_column(
            ["age", "sex", "score"]
        )
        assert result is None


# ---------------------------------------------------------------------------
# _collapse_to_bids_participants_table
# ---------------------------------------------------------------------------

class TestCollapseToBidsParticipantsTable:
    def test_drops_session_column(self):
        df = pd.DataFrame({
            "participant_id": ["sub-001", "sub-001"],
            "session": ["ses-1", "ses-2"],
            "age": ["25", "25"],
        })
        result, dropped, _ = ParticipantsConverter._collapse_to_bids_participants_table(df)
        assert "session" in dropped
        assert "session" not in result.columns

    def test_collapses_duplicate_rows(self):
        df = pd.DataFrame({
            "participant_id": ["sub-001", "sub-001"],
            "age": ["25", "25"],
        })
        result, _, _ = ParticipantsConverter._collapse_to_bids_participants_table(df)
        assert len(result) == 1

    def test_marks_conflicting_columns(self):
        df = pd.DataFrame({
            "participant_id": ["sub-001", "sub-001"],
            "age": ["25", "30"],  # conflict
        })
        _, _, conflicting = ParticipantsConverter._collapse_to_bids_participants_table(df)
        assert "age" in conflicting

    def test_empty_dataframe_returned_unchanged(self):
        df = pd.DataFrame()
        result, dropped, conflicting = ParticipantsConverter._collapse_to_bids_participants_table(df)
        assert result.empty

    def test_drops_run_column(self):
        df = pd.DataFrame({
            "participant_id": ["sub-001"],
            "run": ["1"],
            "age": ["25"],
        })
        result, dropped, _ = ParticipantsConverter._collapse_to_bids_participants_table(df)
        assert "run" in dropped


# ---------------------------------------------------------------------------
# convert_participant_data — happy paths
# ---------------------------------------------------------------------------

class TestConvertParticipantData:
    def test_value_mapping_deprecated_preserved_as_is(self, tmp_path):
        # value_mapping is deprecated and intentionally ignored; source values are preserved
        df = pd.DataFrame({
            "participant_id": ["001", "002"],
            "sex": ["1", "2"],
        })
        source = tmp_path / "data.csv"
        df.to_csv(source, index=False)

        mapping = {
            "version": "1.0",
            "mappings": {
                "sex": {
                    "source_column": "sex",
                    "standard_variable": "sex",
                    "type": "string",
                    "value_mapping": {"1": "M", "2": "F"},
                }
            },
        }
        converter = ParticipantsConverter(tmp_path)
        success, result_df, messages = converter.convert_participant_data(source, mapping)
        assert success is True
        # Source values are preserved as-is (value_mapping is deprecated)
        assert list(result_df["sex"]) == ["1", "2"]

    def test_missing_source_file_fails_gracefully(self, tmp_path):
        converter = ParticipantsConverter(tmp_path)
        mapping = {"version": "1.0", "mappings": {}}
        success, _, messages = converter.convert_participant_data(
            tmp_path / "missing.csv", mapping
        )
        assert success is False or messages  # Either fails or has messages

    def test_numeric_type_column(self, tmp_path):
        df = pd.DataFrame({
            "participant_id": ["001"],
            "age": ["25"],
        })
        source = tmp_path / "data.csv"
        df.to_csv(source, index=False)
        mapping = {
            "version": "1.0",
            "mappings": {
                "age": {
                    "source_column": "age",
                    "standard_variable": "age",
                    "type": "integer",
                }
            },
        }
        converter = ParticipantsConverter(tmp_path)
        success, result_df, _ = converter.convert_participant_data(source, mapping)
        assert success is True
        # The age column is present (type hints don't force int coercion)
        assert str(result_df["age"].iloc[0]) == "25"


# ─────────────────────────────────────────────────────────────────────────────
# validate_mapping
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateMapping:
    def _converter(self, tmp_path):
        return ParticipantsConverter(tmp_path)

    def test_valid_mapping(self, tmp_path):
        converter = self._converter(tmp_path)
        mapping = {
            "version": "1.0",
            "mappings": {
                "participant_id": {
                    "source_column": "ID",
                    "standard_variable": "participant_id",
                }
            },
        }
        ok, errors = converter.validate_mapping(mapping)
        assert ok is True
        assert errors == []

    def test_missing_version(self, tmp_path):
        converter = self._converter(tmp_path)
        mapping = {"mappings": {}}
        ok, errors = converter.validate_mapping(mapping)
        assert ok is False
        assert any("version" in e.lower() for e in errors)

    def test_missing_mappings(self, tmp_path):
        converter = self._converter(tmp_path)
        mapping = {"version": "1.0"}
        ok, errors = converter.validate_mapping(mapping)
        assert ok is False
        assert any("mappings" in e.lower() for e in errors)

    def test_mappings_not_dict(self, tmp_path):
        converter = self._converter(tmp_path)
        mapping = {"version": "1.0", "mappings": "bad"}
        ok, errors = converter.validate_mapping(mapping)
        assert ok is False

    def test_mapping_entry_not_dict(self, tmp_path):
        converter = self._converter(tmp_path)
        mapping = {"version": "1.0", "mappings": {"pid": "bad"}}
        ok, errors = converter.validate_mapping(mapping)
        assert ok is False
        assert any("must be a dict" in e for e in errors)

    def test_mapping_missing_source_column(self, tmp_path):
        converter = self._converter(tmp_path)
        mapping = {
            "version": "1.0",
            "mappings": {
                "pid": {"standard_variable": "participant_id"}
            },
        }
        ok, errors = converter.validate_mapping(mapping)
        assert ok is False
        assert any("source_column" in e for e in errors)

    def test_mapping_missing_standard_variable(self, tmp_path):
        converter = self._converter(tmp_path)
        mapping = {
            "version": "1.0",
            "mappings": {
                "pid": {"source_column": "ID"}
            },
        }
        ok, errors = converter.validate_mapping(mapping)
        assert ok is False
        assert any("standard_variable" in e for e in errors)


# ─────────────────────────────────────────────────────────────────────────────
# load_mapping_from_file
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadMappingFromFile:
    def test_valid_json_file(self, tmp_path):
        mapping = {"version": "1.0", "mappings": {}}
        f = tmp_path / "mapping.json"
        import json
        f.write_text(json.dumps(mapping), encoding="utf-8")
        converter = ParticipantsConverter(tmp_path)
        result = converter.load_mapping_from_file(f)
        assert result is not None
        assert result["version"] == "1.0"

    def test_nonexistent_file_returns_none(self, tmp_path):
        converter = ParticipantsConverter(tmp_path)
        result = converter.load_mapping_from_file(tmp_path / "nonexistent.json")
        assert result is None

    def test_invalid_json_returns_none(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("NOT JSON", encoding="utf-8")
        converter = ParticipantsConverter(tmp_path)
        result = converter.load_mapping_from_file(f)
        assert result is None


# ---------------------------------------------------------------------------
# load_mapping (default file path)
# ---------------------------------------------------------------------------

class TestLoadMapping:
    def test_returns_none_when_no_file(self, tmp_path):
        converter = ParticipantsConverter(tmp_path)
        result = converter.load_mapping()
        assert result is None

    def test_returns_mapping_when_file_exists(self, tmp_path):
        import json
        mapping = {"version": "1.0", "mappings": {}}
        (tmp_path / "participants_mapping.json").write_text(json.dumps(mapping))
        converter = ParticipantsConverter(tmp_path)
        result = converter.load_mapping()
        assert result is not None


# ---------------------------------------------------------------------------
# collapse_to_bids - no participant_id column
# ---------------------------------------------------------------------------

class TestCollapseNoBidsColumn:
    def test_returns_unchanged_when_no_participant_id(self):
        df = pd.DataFrame({"age": ["25", "30"], "sex": ["M", "F"]})
        result, dropped, conflicting = ParticipantsConverter._collapse_to_bids_participants_table(df)
        assert "participant_id" not in result.columns
        assert conflicting == []


# ---------------------------------------------------------------------------
# convert_participants_from_mapping (module-level helper)
# ---------------------------------------------------------------------------

class TestApplyParticipantsMapping:
    def test_returns_true_when_no_mapping_file(self, tmp_path):
        success, messages = apply_participants_mapping(tmp_path, tmp_path / "source.tsv")
        assert success is True
        assert any("No participants_mapping.json" in m for m in messages)

    def test_runs_conversion_with_mapping(self, tmp_path):
        import json
        # Create a minimal source file
        source = tmp_path / "source.tsv"
        source.write_text("sub_id\tage\nsub-01\t25\n")
        mapping = {
            "version": "1.0",
            "mappings": {
                "participant_id": {"source_column": "sub_id", "standard_variable": "participant_id"},
            }
        }
        (tmp_path / "participants_mapping.json").write_text(json.dumps(mapping))
        success, messages = apply_participants_mapping(tmp_path, source)
        # Should complete, success or failure, without exception
        assert isinstance(success, bool)
        assert isinstance(messages, list)
