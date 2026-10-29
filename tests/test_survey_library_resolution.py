"""One answer to "which survey template library?" for the CLI and the GUI."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src import survey_library_resolution as slr

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = {
    "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "Language": "en"},
    "Study": {"TaskName": "pss", "OriginalName": "pss", "LicenseID": "Other", "License": ""},
    "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2026-10-01", "Creator": "t"},
    "PSS1": {"Description": "Q1", "Levels": {"0": "never", "1": "often"}},
}


READY_PROJECT = {
    "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
    "StudyDesign": {"Timepoints": "single"},
}


def _template(folder: Path):
    folder.mkdir(parents=True)
    (folder / "survey-pss.json").write_text(json.dumps(TEMPLATE), encoding="utf-8")
    return folder


@pytest.fixture(autouse=True)
def no_global_library(monkeypatch):
    monkeypatch.setattr(slr, "get_effective_library_paths", lambda app_root=None: {})


def test_project_code_library_comes_first(tmp_path):
    project = tmp_path / "proj"
    _template(project / "code" / "library" / "survey")
    _template(project / "official" / "library" / "survey")
    assert slr.resolve_survey_library(project, tmp_path / "app") == project / "code" / "library"


def test_project_official_library_when_there_is_no_code_library(tmp_path):
    project = tmp_path / "proj"
    _template(project / "official" / "library" / "survey")
    assert slr.resolve_survey_library(project, tmp_path / "app") == project / "official" / "library"


def test_a_project_json_path_means_its_folder(tmp_path):
    project = tmp_path / "proj"
    _template(project / "code" / "library" / "survey")
    (project / "project.json").write_text("{}", encoding="utf-8")
    assert slr.resolve_survey_library(project / "project.json", tmp_path / "app") == project / "code" / "library"


def test_without_a_project_the_configured_global_library_is_used(tmp_path, monkeypatch):
    shared = _template(tmp_path / "shared")
    monkeypatch.setattr(slr, "get_effective_library_paths", lambda app_root=None: {"global_library_path": str(shared)})
    assert slr.resolve_survey_library(None, tmp_path / "app") == shared


def test_no_library_anywhere_says_where_to_put_templates(tmp_path):
    with pytest.raises(FileNotFoundError, match="code/library"):
        slr.resolve_survey_library(tmp_path / "proj", tmp_path / "app")


def test_templates_dir_is_the_survey_subfolder_when_there_is_one(tmp_path):
    with_sub = tmp_path / "a"
    (with_sub / "survey").mkdir(parents=True)
    flat = tmp_path / "b"
    flat.mkdir()
    assert slr.survey_templates_dir(with_sub) == with_sub / "survey"
    assert slr.survey_templates_dir(flat) == flat


def test_cli_convert_without_library_uses_the_projects_own_templates(tmp_path):
    project = tmp_path / "proj"
    _template(project / "code" / "library" / "survey")
    (project / "project.json").write_text(json.dumps(READY_PROJECT), encoding="utf-8")
    table = tmp_path / "pss.csv"
    table.write_text("ID,PSS1\nsub-001,0\nsub-002,1\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ROOT / "prism_tools.py"), "survey", "convert", "--input", str(table),
         "--output", str(project), "--id-column", "ID", "--lang", "en", "--dry-run", "--force"],
        capture_output=True, text=True, timeout=180, cwd=ROOT,
    )

    assert "Could not find a survey template library" not in result.stdout
    assert f"project {(project / 'code' / 'library' / 'survey').resolve()}" in result.stdout
