"""`survey convert` finds templates in the personal library and leaves a copy in the project."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src import config

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = {
    "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "Language": "en"},
    "Study": {"TaskName": "pss", "OriginalName": "pss", "LicenseID": "Other", "License": ""},
    "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2026-10-01", "Creator": "me"},
    "PSS1": {"Description": "Q1", "Levels": {"0": "never", "1": "often"}},
}
READY_PROJECT = {
    "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
    "StudyDesign": {"Timepoints": "single"},
}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    home = tmp_path / "home"
    for var in ("HOME", "XDG_CONFIG_HOME", "APPDATA"):
        monkeypatch.setenv(var, str(home))
    mine = tmp_path / "mine"
    (mine / "library" / "survey").mkdir(parents=True)
    (mine / "library" / "survey" / "survey-pss.json").write_text(json.dumps(TEMPLATE), encoding="utf-8")
    settings_dir = config._get_user_app_settings_dir()
    settings_dir.mkdir(parents=True)
    (settings_dir / config.APP_SETTINGS_FILENAME).write_text(json.dumps({"personalLibraryRoot": str(mine)}), encoding="utf-8")

    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text(json.dumps(READY_PROJECT), encoding="utf-8")
    table = tmp_path / "pss.csv"
    table.write_text("ID,PSS1\nsub-001,0\nsub-002,1\n", encoding="utf-8")
    return project, table


def _convert(project, table, *extra):
    return subprocess.run(
        [sys.executable, str(ROOT / "prism_tools.py"), "survey", "convert", "--input", str(table), "--output", str(project),
         "--id-column", "ID", "--lang", "en", "--force", *extra],
        capture_output=True, text=True, timeout=180, cwd=ROOT,
    )


def test_conversion_uses_the_personal_template_and_leaves_a_copy_in_the_project(setup):
    project, table = setup
    result = _convert(project, table)

    assert "Survey conversion complete" in result.stdout, result.stdout + result.stderr
    assert "personal " in result.stdout  # the report names the library it used
    copied = project / "code" / "library" / "survey" / "survey-pss.json"
    assert json.loads(copied.read_text(encoding="utf-8"))["PSS1"]["Levels"] == {"0": "never", "1": "often"}


def test_a_dry_run_leaves_the_project_untouched(setup):
    project, table = setup
    result = _convert(project, table, "--dry-run")

    assert "No files were created" in result.stdout, result.stdout + result.stderr
    assert not (project / "code").exists()
