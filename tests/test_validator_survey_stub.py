"""A survey stub (Study.ItemTextsIncluded false) in a project: warned as 'texts missing', never an error;
its Levels keys still range-check the data (decision 2026-11-18, docs/handouts/2026-11-18-survey-stubs-studio.md)."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from schema_manager import load_all_schemas
from validator import DatasetValidator

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "app" / "schemas"
TSV = "sub-01/ses-1/survey/sub-01_ses-1_task-dass_survey.tsv"


def _project(root: Path, stub: bool, value="1"):
    study = {"TaskName": "dass", "OriginalName": "Mood", "ShortName": "M", "Version": "1",
             "Citation": "Doe 2020", "LicenseID": "Other", "Category": "Other / Uncategorized"}
    item = {"Description": None if stub else "Feeling low", "Levels": {"0": None if stub else "No", "1": None if stub else "Yes"}}
    if stub:
        study["ItemTextsIncluded"] = False
        item["Fingerprint"] = {"en": "sha256:" + "0" * 64}
    (root / "task-dass_survey.json").write_text(json.dumps({
        "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "Language": "en",
                      "SoftwarePlatform": "Other", "SoftwareVersion": "1", "Respondent": "self",
                      "AdministrationMethod": "online"},
        "Metadata": {"SchemaVersion": "2.1.5", "CreationDate": "2026-11-18", "Creator": "test"},
        "I18n": {"Languages": ["en"]},
        "Study": study,
        "dass01": item,
    }), encoding="utf-8")
    tsv = root / TSV
    tsv.parent.mkdir(parents=True)
    tsv.write_text(f"dass01\n{value}\n", encoding="utf-8")
    return tsv


def _run(tmp_path, stub, value="1"):
    tsv = _project(tmp_path, stub, value)
    v = DatasetValidator(load_all_schemas(str(SCHEMA_DIR)))
    return (v.validate_sidecar(str(tsv), "survey", str(tmp_path))
            + v.validate_data_content(str(tsv), "survey", str(tmp_path)))


def test_stub_is_warned_not_errored(tmp_path):
    issues = _run(tmp_path, stub=True)
    assert [m for lvl, m in issues if lvl == "ERROR"] == []
    assert any(lvl == "WARNING" and "texts missing" in m for lvl, m in issues)


def test_stub_that_does_not_map_to_a_prism_id_is_an_error(tmp_path):
    tsv = _project(tmp_path, stub=True)
    path = tmp_path / "task-dass_survey.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["Study"]["TaskName"] = "nosuchtest"  # no official instrument, so no prism:nosuchtest
    path.write_text(json.dumps(data), encoding="utf-8")
    v = DatasetValidator(load_all_schemas(str(SCHEMA_DIR)))
    issues = v.validate_sidecar(str(tsv), "survey", str(tmp_path))
    assert any(lvl == "ERROR" and "prism:nosuchtest" in m for lvl, m in issues)


def test_stub_gets_no_empty_label_noise(tmp_path):
    assert not any("empty Levels label" in m for _, m in _run(tmp_path, stub=True))


def test_stub_levels_still_catch_out_of_range_value(tmp_path):
    issues = _run(tmp_path, stub=True, value="5")
    assert any(lvl == "ERROR" and "not in allowed values" in m for lvl, m in issues)


def test_stub_warned_once_per_sidecar(tmp_path):
    tsv = _project(tmp_path, stub=True)
    v = DatasetValidator(load_all_schemas(str(SCHEMA_DIR)))
    issues = v.validate_sidecar(str(tsv), "survey", str(tmp_path)) + v.validate_sidecar(str(tsv), "survey", str(tmp_path))
    assert sum("texts missing" in m for _, m in issues) == 1


def test_stub_warning_survives_schema_error(tmp_path):
    tsv = _project(tmp_path, stub=True)
    path = tmp_path / "task-dass_survey.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["Study"]["Citation"]  # required
    path.write_text(json.dumps(data), encoding="utf-8")
    v = DatasetValidator(load_all_schemas(str(SCHEMA_DIR)))
    issues = v.validate_sidecar(str(tsv), "survey", str(tmp_path))
    assert any(lvl == "ERROR" for lvl, _ in issues) and any("texts missing" in m for _, m in issues)


def test_full_template_still_warns_on_empty_label(tmp_path):
    tsv = _project(tmp_path, stub=False)
    path = tmp_path / "task-dass_survey.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["dass01"]["Levels"]["1"] = ""
    path.write_text(json.dumps(data), encoding="utf-8")
    v = DatasetValidator(load_all_schemas(str(SCHEMA_DIR)))
    assert any("empty Levels label" in m for _, m in v.validate_data_content(str(tsv), "survey", str(tmp_path)))


def test_full_template_has_no_stub_warning(tmp_path):
    assert not any("texts missing" in m for _, m in _run(tmp_path, stub=False))
