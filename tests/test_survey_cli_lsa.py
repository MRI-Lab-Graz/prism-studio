"""CLI parity: `survey convert` takes a LimeSurvey .lsa like the GUI does."""

import json
import subprocess
import sys
import zipfile
from pathlib import Path

from tests.test_limesurvey_e2e import LSS_XML

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRISM_TOOLS_APP = PROJECT_ROOT / "app" / "prism_tools.py"

FIELDS = ["id", "token", "startdate", "MTESTSQ001", "MTESTSQ002", "MTESTSQ003"]
# Participant "a" answered twice (file order is not date order); "b" once.
ROWS = [
    ["1", "a", "2026-09-01 10:00:00", "4", "3", "5"],
    ["2", "a", "2026-03-01 10:00:00", "2", "4", "3"],
    ["3", "b", "2026-03-02 10:00:00", "1", "2", "3"],
]


def _lsa(tmp_path: Path) -> Path:
    rows = "".join(
        "<row>" + "".join(f"<{f}><![CDATA[{v}]]></{f}>" for f, v in zip(FIELDS, row)) + "</row>"
        for row in ROWS
    )
    lsr = (
        '<?xml version="1.0" encoding="UTF-8"?><document>'
        "<LimeSurveyDocType>Responses</LimeSurveyDocType><DBVersion>636</DBVersion>"
        "<languages><language>en</language></languages><responses><fields>"
        + "".join(f"<fieldname>{f}</fieldname>" for f in FIELDS)
        + f"</fields><rows>{rows}</rows></responses></document>"
    )
    path = tmp_path / "survey_archive.lsa"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("survey_999999.lss", LSS_XML)
        z.writestr("survey_999999_responses.lsr", lsr)
    return path


def _library(tmp_path: Path) -> Path:
    lib = tmp_path / "lib"
    lib.mkdir()
    template = {
        "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "Language": "en", "Respondent": "self",
                      "SoftwarePlatform": "LimeSurvey", "SoftwareVersion": "6", "AdministrationMethod": "online"},
        "Study": {
            "TaskName": "wellbeing", "OriginalName": "Wellbeing", "Authors": ["x"], "Year": 2026,
            "Citation": "x", "Version": "1", "Instructions": "x", "LicenseID": "CC0-1.0",
            "Category": "Well-being & Life Satisfaction",
        },
        "Metadata": {"SchemaVersion": "1.0.0", "CreationDate": "2026-01-01"},
    }
    for i in (1, 2, 3):
        template[f"MTESTSQ00{i}"] = {"Description": f"q{i}", "Levels": {str(k): str(k) for k in range(1, 6)}}
    (lib / "survey-wellbeing.json").write_text(json.dumps(template))
    return lib


def _convert(tmp_path: Path, *extra: str, library: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable, str(PRISM_TOOLS_APP), "survey", "convert",
            "--input", str(_lsa(tmp_path)), "--library", str(library or _library(tmp_path)),
            "--output", str(tmp_path / "out"), "--id-column", "token", "--force", *extra,
        ],
        capture_output=True, text=True, encoding="utf-8", cwd=str(PROJECT_ROOT), timeout=120,
    )


def test_warnings_are_printed(tmp_path):
    result = _convert(tmp_path, "--duplicate-handling", "sessions", "--dry-run")

    assert "WARNING: Uneven session counts" in result.stdout


def test_repeated_ids_become_dated_sessions_with_duplicate_handling_sessions(tmp_path):
    result = _convert(tmp_path, "--duplicate-handling", "sessions")

    assert result.returncode == 0, result.stdout + result.stderr
    sessions = sorted(p.name for p in (tmp_path / "out" / "sub-a").glob("ses-*"))
    assert sessions == ["ses-1", "ses-2"]


def test_skip_existing_keeps_responses_already_in_the_project(tmp_path):
    first = _convert(tmp_path, "--duplicate-handling", "sessions")
    assert first.returncode == 0, first.stdout + first.stderr
    kept = tmp_path / "out" / "sub-a" / "ses-1" / "survey" / "sub-a_ses-1_task-wellbeing_survey.tsv"
    kept.write_text("SENTINEL")

    lib = tmp_path / "lib"
    second = subprocess.run(
        [
            sys.executable, str(PRISM_TOOLS_APP), "survey", "convert",
            "--input", str(_lsa(tmp_path)), "--library", str(lib),
            "--output", str(tmp_path / "out"), "--id-column", "token",
            "--duplicate-handling", "sessions", "--skip-existing",
        ],
        capture_output=True, text=True, encoding="utf-8", cwd=str(PROJECT_ROOT), timeout=120,
    )

    assert second.returncode == 0, second.stdout + second.stderr
    assert kept.read_text() == "SENTINEL"
    assert "Already in project" in second.stdout


def test_lang_auto_writes_the_language_of_the_lsa_not_the_word_auto(tmp_path):
    """--lang auto with a multilingual library used to compile it for "auto" and write
    Technical.Language: auto, which the schema rejects."""
    library = _library(tmp_path)
    path = library / "survey-wellbeing.json"
    template = json.loads(path.read_text())
    for key, item in template.items():
        if key.startswith("MTEST"):
            item["Description"] = {"en": item["Description"], "de": item["Description"]}
    path.write_text(json.dumps(template))

    result = _convert(tmp_path, "--lang", "auto", "--duplicate-handling", "sessions", library=library)

    assert result.returncode == 0, result.stdout + result.stderr
    sidecar = json.loads(next((tmp_path / "out").rglob("task-wellbeing_survey.json")).read_text())
    assert sidecar["Technical"]["Language"] == "en"
