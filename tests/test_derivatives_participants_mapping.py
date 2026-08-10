"""Tests for app/src/derivatives/participants_mapping.py's apply_participants_mapping.

This is the live implementation reached both by the CLI (app/prism.py imports it
directly via `derivatives.participants_mapping`) and by the web app
(app/src/web/validation.py._resolve_participants_mapping tries
"src.derivatives.participants_mapping" first, which always ModuleNotFoundErrors
because src/derivatives is a real package without that submodule, then falls
back to the bare "derivatives.participants_mapping" import used here). It is a
distinct function from src/participants_converter.py's apply_participants_mapping
(different signature, different return type) -- not a drifted copy of it.
"""

import json
from unittest.mock import patch

import pytest

from derivatives.participants_mapping import apply_participants_mapping

VALID_MAPPING = {
    "version": "1.0",
    "mappings": {
        "participant_id": {
            "source_column": "participant_id",
            "standard_variable": "participant_id",
            "type": "string",
        },
        "age": {
            "source_column": "age",
            "standard_variable": "age",
            "type": "number",
        },
    },
}

INVALID_MAPPING = {
    "version": "1.0",
    "mappings": {
        # missing required "source_column"
        "age": {"standard_variable": "age", "type": "number"},
    },
}

SOURCE_TSV = "participant_id\tage\n001\t25\n002\t30\n"


def _write_mapping(path, mapping=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping or VALID_MAPPING), encoding="utf-8")


def _write_source_tsv(path, content=SOURCE_TSV):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestNoMappingFile:
    def test_returns_default_result_when_nothing_found(self, tmp_path):
        dataset_path = tmp_path / "study" / "rawdata"
        dataset_path.mkdir(parents=True)

        result = apply_participants_mapping(str(dataset_path))

        assert result == {
            "applied": False,
            "mapping_file": None,
            "rows": None,
            "reason": None,
        }

    def test_progress_callback_not_called_when_nothing_found(self, tmp_path):
        dataset_path = tmp_path / "study" / "rawdata"
        dataset_path.mkdir(parents=True)
        calls = []

        apply_participants_mapping(str(dataset_path), progress_callback=calls.append)

        assert calls == []


class TestMappingFileDiscovery:
    def test_found_in_code_library(self, tmp_path):
        dataset_path = tmp_path / "study" / "rawdata"
        dataset_path.mkdir(parents=True)
        _write_mapping(tmp_path / "study" / "code" / "library" / "participants_mapping.json")
        _write_source_tsv(tmp_path / "study" / "raw_data" / "wellbeing.tsv")

        result = apply_participants_mapping(str(dataset_path))

        assert result["applied"] is True
        assert result["mapping_file"].endswith(
            str(tmp_path / "study" / "code" / "library" / "participants_mapping.json")[-40:]
        )
        assert result["rows"] == 2
        assert result["reason"] is None

    def test_found_in_sourcedata(self, tmp_path):
        dataset_path = tmp_path / "study" / "rawdata"
        dataset_path.mkdir(parents=True)
        _write_mapping(tmp_path / "study" / "sourcedata" / "participants_mapping.json")
        _write_source_tsv(tmp_path / "study" / "raw_data" / "wellbeing.tsv")

        result = apply_participants_mapping(str(dataset_path))

        assert result["applied"] is True
        assert "sourcedata" in result["mapping_file"]

    def test_found_in_grandparent_code_library(self, tmp_path):
        # dataset_path.parent.parent is the third search candidate.
        dataset_path = tmp_path / "outer" / "inner" / "rawdata"
        dataset_path.mkdir(parents=True)
        _write_mapping(tmp_path / "outer" / "code" / "library" / "participants_mapping.json")
        _write_source_tsv(tmp_path / "outer" / "inner" / "raw_data" / "wellbeing.tsv")

        result = apply_participants_mapping(str(dataset_path))

        assert result["applied"] is True
        assert str(tmp_path / "outer" / "code" / "library") in result["mapping_file"]

    def test_first_matching_path_wins(self, tmp_path):
        # code/library is checked before sourcedata; put a valid mapping in
        # both but only the code/library one should be reported as used.
        dataset_path = tmp_path / "study" / "rawdata"
        dataset_path.mkdir(parents=True)
        code_lib = tmp_path / "study" / "code" / "library" / "participants_mapping.json"
        sourcedata = tmp_path / "study" / "sourcedata" / "participants_mapping.json"
        _write_mapping(code_lib)
        _write_mapping(sourcedata)
        _write_source_tsv(tmp_path / "study" / "raw_data" / "wellbeing.tsv")

        result = apply_participants_mapping(str(dataset_path))

        assert result["mapping_file"] == str(code_lib)


class TestMappingLoadAndValidationFailures:
    def test_unreadable_mapping_file_sets_reason(self, tmp_path):
        dataset_path = tmp_path / "study" / "rawdata"
        dataset_path.mkdir(parents=True)
        mapping_path = tmp_path / "study" / "code" / "library" / "participants_mapping.json"
        mapping_path.parent.mkdir(parents=True)
        mapping_path.write_text("{not valid json", encoding="utf-8")
        calls = []

        result = apply_participants_mapping(
            str(dataset_path), progress_callback=lambda *args: calls.append(args)
        )

        assert result["applied"] is False
        assert result["reason"] == "Could not load participants mapping"
        assert any("Could not load participants mapping" in msg for _, msg in calls)

    def test_invalid_mapping_schema_sets_reason(self, tmp_path):
        dataset_path = tmp_path / "study" / "rawdata"
        dataset_path.mkdir(parents=True)
        _write_mapping(
            tmp_path / "study" / "code" / "library" / "participants_mapping.json",
            mapping=INVALID_MAPPING,
        )
        calls = []

        result = apply_participants_mapping(
            str(dataset_path), progress_callback=lambda *args: calls.append(args)
        )

        assert result["applied"] is False
        assert result["reason"].startswith("Mapping validation failed")
        assert any("Mapping validation failed" in msg for _, msg in calls)


class TestSourceFileDiscovery:
    def test_no_source_file_sets_reason(self, tmp_path):
        dataset_path = tmp_path / "study" / "rawdata"
        dataset_path.mkdir(parents=True)
        _write_mapping(tmp_path / "study" / "code" / "library" / "participants_mapping.json")
        # no raw_data/ or sourcedata/ tsv anywhere
        calls = []

        result = apply_participants_mapping(
            str(dataset_path), progress_callback=lambda *args: calls.append(args)
        )

        assert result["applied"] is False
        assert result["reason"] == "No source participant data file found - skipping mapping"
        assert any("No source participant data file found" in msg for _, msg in calls)

    def test_falls_back_to_grandparent_raw_data(self, tmp_path):
        dataset_path = tmp_path / "outer" / "inner" / "rawdata"
        dataset_path.mkdir(parents=True)
        _write_mapping(tmp_path / "outer" / "inner" / "code" / "library" / "participants_mapping.json")
        _write_source_tsv(tmp_path / "outer" / "raw_data" / "wellbeing.tsv")

        result = apply_participants_mapping(str(dataset_path))

        assert result["applied"] is True

    def test_falls_back_to_sourcedata_for_source_file(self, tmp_path):
        dataset_path = tmp_path / "study" / "rawdata"
        dataset_path.mkdir(parents=True)
        _write_mapping(tmp_path / "study" / "code" / "library" / "participants_mapping.json")
        _write_source_tsv(tmp_path / "study" / "sourcedata" / "wellbeing.tsv")

        result = apply_participants_mapping(str(dataset_path))

        assert result["applied"] is True

    def test_ignores_dotfiles_when_globbing_for_tsv(self, tmp_path):
        dataset_path = tmp_path / "study" / "rawdata"
        dataset_path.mkdir(parents=True)
        _write_mapping(tmp_path / "study" / "code" / "library" / "participants_mapping.json")
        raw_data = tmp_path / "study" / "raw_data"
        raw_data.mkdir(parents=True)
        (raw_data / ".hidden.tsv").write_text(SOURCE_TSV, encoding="utf-8")
        (raw_data / "wellbeing.tsv").write_text(SOURCE_TSV, encoding="utf-8")

        result = apply_participants_mapping(str(dataset_path))

        assert result["applied"] is True
        assert result["rows"] == 2


class TestConversionOutcomes:
    def test_progress_callback_receives_success_message(self, tmp_path):
        dataset_path = tmp_path / "study" / "rawdata"
        dataset_path.mkdir(parents=True)
        _write_mapping(tmp_path / "study" / "code" / "library" / "participants_mapping.json")
        _write_source_tsv(tmp_path / "study" / "raw_data" / "wellbeing.tsv")
        calls = []

        apply_participants_mapping(
            str(dataset_path), progress_callback=lambda *args: calls.append(args)
        )

        assert any("Applied participants mapping" in msg for _, msg in calls)

    def test_conversion_failure_sets_reason(self, tmp_path):
        dataset_path = tmp_path / "study" / "rawdata"
        dataset_path.mkdir(parents=True)
        _write_mapping(tmp_path / "study" / "code" / "library" / "participants_mapping.json")
        _write_source_tsv(tmp_path / "study" / "raw_data" / "wellbeing.tsv")
        calls = []

        with patch(
            "src.participants_converter.ParticipantsConverter.convert_participant_data",
            return_value=(False, None, ["boom"]),
        ):
            result = apply_participants_mapping(
                str(dataset_path), progress_callback=lambda *args: calls.append(args)
            )

        assert result["applied"] is False
        assert result["reason"] == "Participants mapping partially failed"
        assert any("Participants mapping partially failed" in msg for _, msg in calls)

    def test_exception_during_conversion_is_caught(self, tmp_path):
        dataset_path = tmp_path / "study" / "rawdata"
        dataset_path.mkdir(parents=True)
        _write_mapping(tmp_path / "study" / "code" / "library" / "participants_mapping.json")
        _write_source_tsv(tmp_path / "study" / "raw_data" / "wellbeing.tsv")
        calls = []

        with patch(
            "src.participants_converter.ParticipantsConverter.convert_participant_data",
            side_effect=RuntimeError("disk exploded"),
        ):
            result = apply_participants_mapping(
                str(dataset_path), progress_callback=lambda *args: calls.append(args)
            )

        assert result["applied"] is False
        assert "disk exploded" in result["reason"]
        assert result["reason"].startswith("Participants mapping skipped:")
        assert any("Participants mapping skipped" in msg for _, msg in calls)


class TestImportFallback:
    def test_falls_back_to_bare_participants_converter_import(self, tmp_path, monkeypatch):
        dataset_path = tmp_path / "study" / "rawdata"
        dataset_path.mkdir(parents=True)
        _write_mapping(tmp_path / "study" / "code" / "library" / "participants_mapping.json")
        _write_source_tsv(tmp_path / "study" / "raw_data" / "wellbeing.tsv")

        import importlib

        real_import_module = importlib.import_module

        def fake_import_module(name, *args, **kwargs):
            if name == "src.participants_converter":
                raise ImportError("simulated: src package unavailable")
            return real_import_module(name, *args, **kwargs)

        monkeypatch.setattr(
            "derivatives.participants_mapping.importlib.import_module",
            fake_import_module,
        )

        result = apply_participants_mapping(str(dataset_path))

        assert result["applied"] is True
        assert result["rows"] == 2
