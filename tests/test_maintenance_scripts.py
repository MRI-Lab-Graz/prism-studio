"""Tests for src/maintenance scripts — sync_survey_keys, sync_biometrics_keys, catalog."""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.maintenance.sync_survey_keys import sync_survey_keys
from src.maintenance.sync_biometrics_keys import sync_biometrics_keys
from src.maintenance.catalog_survey_library import generate_index


# ---------------------------------------------------------------------------
# sync_survey_keys
# ---------------------------------------------------------------------------

class TestSyncSurveyKeys:
    def _make_library(self, tmp_path, files: dict) -> str:
        lib = tmp_path / "library" / "survey"
        lib.mkdir(parents=True)
        for name, content in files.items():
            (lib / name).write_text(json.dumps(content))
        return str(lib)

    def test_nonexistent_dir_prints_error(self, tmp_path, capsys):
        sync_survey_keys(library_dir=str(tmp_path / "nonexistent"))
        out = capsys.readouterr().out
        assert "Error" in out or "does not exist" in out.lower()

    def test_empty_dir_prints_no_files(self, tmp_path, capsys):
        lib = tmp_path / "lib"
        lib.mkdir()
        sync_survey_keys(library_dir=str(lib))
        out = capsys.readouterr().out
        assert "No JSON" in out or "no json" in out.lower()

    def test_single_file_no_change(self, tmp_path, capsys):
        lib = self._make_library(tmp_path, {
            "survey-bdi.json": {"Study": {"TaskName": "bdi"}, "Technical": {"Version": "1"}}
        })
        sync_survey_keys(library_dir=lib)
        # With only the template file, the loop body never executes — no output expected

    def test_adds_missing_study_key(self, tmp_path, capsys):
        lib = self._make_library(tmp_path, {
            "survey-bdi.json": {
                "Study": {"TaskName": "bdi", "Domain": "mood"},
                "Technical": {"Version": "1"},
            },
            "survey-gad.json": {
                "Study": {"TaskName": "gad"},
                "Technical": {"Version": "1"},
            },
        })
        sync_survey_keys(library_dir=lib)
        result = json.loads((tmp_path / "library" / "survey" / "survey-gad.json").read_text())
        assert "Domain" in result["Study"]
        out = capsys.readouterr().out
        assert "gad" in out

    def test_already_synchronized(self, tmp_path, capsys):
        lib = self._make_library(tmp_path, {
            "survey-bdi.json": {
                "Study": {"TaskName": "bdi", "Domain": "mood"},
                "Technical": {"Version": "1"},
            },
            "survey-gad.json": {
                "Study": {"TaskName": "gad", "Domain": "anxiety"},
                "Technical": {"Version": "1"},
            },
        })
        sync_survey_keys(library_dir=lib)
        out = capsys.readouterr().out
        assert "already synchronized" in out or "ℹ️" in out

    def test_adds_missing_technical_key(self, tmp_path, capsys):
        lib = self._make_library(tmp_path, {
            "survey-bdi.json": {
                "Study": {},
                "Technical": {"Version": "1", "Publisher": "APA"},
            },
            "survey-phq.json": {
                "Study": {},
                "Technical": {"Version": "1"},
            },
        })
        sync_survey_keys(library_dir=lib)
        result = json.loads((tmp_path / "library" / "survey" / "survey-phq.json").read_text())
        assert "Publisher" in result["Technical"]


# ---------------------------------------------------------------------------
# sync_biometrics_keys
# ---------------------------------------------------------------------------

class TestSyncBiometricsKeys:
    def _make_library(self, tmp_path, files: dict) -> str:
        lib = tmp_path / "library" / "biometrics"
        lib.mkdir(parents=True)
        for name, content in files.items():
            (lib / name).write_text(json.dumps(content))
        return str(lib)

    def test_nonexistent_dir(self, tmp_path, capsys):
        sync_biometrics_keys(library_dir=str(tmp_path / "nonexistent"))
        out = capsys.readouterr().out
        assert "Error" in out or "does not exist" in out.lower()

    def test_empty_dir(self, tmp_path, capsys):
        lib = tmp_path / "lib"
        lib.mkdir()
        sync_biometrics_keys(library_dir=str(lib))
        out = capsys.readouterr().out
        assert "No JSON" in out or "no json" in out.lower()

    def test_adds_missing_keys(self, tmp_path, capsys):
        lib = self._make_library(tmp_path, {
            "biometrics-cmj.json": {
                "Study": {"TaskName": "cmj", "Domain": "strength"},
                "Technical": {"Version": "1"},
                "pre_cmj_1": {},
            },
            "biometrics-grip.json": {
                "Study": {"TaskName": "grip"},
                "Technical": {"Version": "1"},
            },
        })
        sync_biometrics_keys(library_dir=lib)
        result = json.loads((tmp_path / "library" / "biometrics" / "biometrics-grip.json").read_text())
        assert "Domain" in result["Study"]

    def test_no_overwrite_measurement_key(self, tmp_path):
        lib = self._make_library(tmp_path, {
            "biometrics-cmj.json": {
                "Study": {},
                "Technical": {},
                "pre_cmj_1": {"unit": "m"},
            },
            "biometrics-grip.json": {
                "Study": {},
                "Technical": {},
            },
        })
        sync_biometrics_keys(library_dir=lib)
        result = json.loads((tmp_path / "library" / "biometrics" / "biometrics-grip.json").read_text())
        # Measurement key from template should NOT be copied
        assert "pre_cmj_1" not in result


# ---------------------------------------------------------------------------
# catalog_survey_library.generate_index
# ---------------------------------------------------------------------------

class TestCatalogSurveyLibrary:
    def _make_survey_json(self, lib_path, filename: str, study: dict):
        (lib_path / filename).write_text(json.dumps({"Study": study}))

    def test_nonexistent_path_prints_error(self, tmp_path, capsys):
        out_file = str(tmp_path / "catalog.md")
        generate_index(str(tmp_path / "nonexistent"), out_file)
        out = capsys.readouterr().out
        assert "Error" in out or "not found" in out.lower()

    def test_no_survey_files_prints_warning(self, tmp_path, capsys):
        lib = tmp_path / "lib"
        lib.mkdir()
        out_file = str(tmp_path / "catalog.md")
        generate_index(str(lib), out_file)
        out = capsys.readouterr().out
        assert "No survey" in out or "not found" in out.lower()

    def test_generates_markdown_catalog(self, tmp_path):
        lib = tmp_path / "lib"
        lib.mkdir()
        self._make_survey_json(lib, "survey-bdi.json", {
            "TaskName": "bdi",
            "OriginalName": "Beck Depression Inventory",
            "Domain": "mood",
            "Keywords": ["depression", "mood"],
            "Citation": "Beck et al. 1961",
        })
        out_file = str(tmp_path / "catalog.md")
        generate_index(str(lib), out_file)
        content = (tmp_path / "catalog.md").read_text()
        assert "Survey Library Catalog" in content
        assert "bdi" in content.lower()

    def test_creates_output_directory(self, tmp_path):
        lib = tmp_path / "lib"
        lib.mkdir()
        self._make_survey_json(lib, "survey-ads.json", {"TaskName": "ads"})
        out_file = str(tmp_path / "subdir" / "catalog.md")
        generate_index(str(lib), out_file)
        assert os.path.exists(out_file)

    def test_malformed_json_skipped(self, tmp_path, capsys):
        lib = tmp_path / "lib"
        lib.mkdir()
        (lib / "survey-bad.json").write_text("NOT JSON")
        self._make_survey_json(lib, "survey-ok.json", {"TaskName": "ok"})
        out_file = str(tmp_path / "catalog.md")
        generate_index(str(lib), out_file)
        out = capsys.readouterr().out
        assert "Error reading" in out or "ok" in (tmp_path / "catalog.md").read_text().lower()


# ---------------------------------------------------------------------------
# sync_survey_keys — missing Scoring/Normative/Metadata keys (lines 47-63)
# ---------------------------------------------------------------------------

class TestSyncSurveyKeysSpecialKeys:
    def _make_library(self, tmp_path, files):
        lib = tmp_path / "library" / "survey"
        lib.mkdir(parents=True)
        for name, data in files.items():
            (lib / name).write_text(json.dumps(data))
        return str(lib)

    def test_adds_scoring_key(self, tmp_path, capsys):
        lib = self._make_library(tmp_path, {
            "survey-bdi.json": {"Study": {}, "Scoring": {"method": "sum"}},
            "survey-gad.json": {"Study": {}},
        })
        sync_survey_keys(library_dir=lib)
        result = json.loads((tmp_path / "library" / "survey" / "survey-gad.json").read_text())
        assert "Scoring" in result

    def test_adds_normative_key(self, tmp_path, capsys):
        lib = self._make_library(tmp_path, {
            "survey-bdi.json": {"Study": {}, "Normative": {"population": "adult"}},
            "survey-gad.json": {"Study": {}},
        })
        sync_survey_keys(library_dir=lib)
        result = json.loads((tmp_path / "library" / "survey" / "survey-gad.json").read_text())
        assert "Normative" in result


# ---------------------------------------------------------------------------
# sync_biometrics_keys — missing keys (lines 56-57)
# ---------------------------------------------------------------------------

class TestSyncBiometricsKeysSpecialKeys:
    def _make_library(self, tmp_path, files):
        lib = tmp_path / "library" / "biometrics"
        lib.mkdir(parents=True)
        for name, data in files.items():
            (lib / name).write_text(json.dumps(data))
        return str(lib)

    def test_adds_scoring_key_from_template(self, tmp_path, capsys):
        lib = self._make_library(tmp_path, {
            "biometrics-cmj.json": {"Study": {}, "Scoring": {"metric": "height"}},
            "biometrics-sj.json": {"Study": {}},
        })
        from src.maintenance.sync_biometrics_keys import sync_biometrics_keys
        sync_biometrics_keys(library_dir=lib)
        result = json.loads((tmp_path / "library" / "biometrics" / "biometrics-sj.json").read_text())
        assert "Scoring" in result
