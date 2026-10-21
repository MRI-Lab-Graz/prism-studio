"""build_methods: one backend entry point for the methods section (CLI and GUI)."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "app"))

from src.methods_project import MethodsResult, build_methods  # noqa: E402

TEMPLATE = {
    "Study": {
        "TaskName": {"en": "Affective Distress Scale"},
        "Description": {"en": "Assesses current distress symptoms."},
    },
    "item_01": {"Levels": {"1": {"en": "No"}, "2": {"en": "Yes"}}},
}


def _project(tmp_path, project_json):
    (tmp_path / "project.json").write_text(json.dumps(project_json), encoding="utf-8")
    return tmp_path


def _no_global_library():
    return patch(
        "src.config.get_effective_template_library_path",
        return_value={"effective_external_path": "", "global_library_path": ""},
    )


def test_build_methods_returns_result(tmp_path):
    root = _project(tmp_path, {"StudyDesign": {"Type": "cross-sectional"}})
    with _no_global_library():
        result = build_methods(root)
    assert isinstance(result, MethodsResult)
    assert "cross sectional design" in result.md
    assert "StudyDesign" in result.sections_used
    assert result.warnings and "sample size" in result.warnings[0]
    assert result.template_data == {}


def test_build_methods_without_project_json_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="No project metadata"):
        build_methods(tmp_path)


def test_build_methods_finds_template_in_project_library(tmp_path):
    root = _project(tmp_path, {"TaskDefinitions": {"ads": {"modality": "survey"}}})
    lib = root / "code" / "library" / "survey"
    lib.mkdir(parents=True)
    (lib / "survey-ads.json").write_text(json.dumps(TEMPLATE), encoding="utf-8")
    with _no_global_library():
        result = build_methods(root)
    assert "Affective Distress Scale" in result.md
    assert set(result.template_data) == {"ads"}


def test_build_methods_uses_given_project_data_and_stats(tmp_path):
    root = _project(tmp_path, {})
    with _no_global_library():
        result = build_methods(
            root,
            project_data={"StudyDesign": {"Type": "longitudinal"}},
            compute_participant_stats=lambda path, lang="en": {"n": 12},
        )
    assert "*N* = 12 participants" in result.md


def test_build_methods_reports_warnings(tmp_path):
    p = _project(tmp_path, {"TaskDefinitions": {"ads": {"modality": "survey"}}})
    result = build_methods(p, app_root=str(tmp_path), compute_participant_stats=lambda *a, **k: None)
    assert any("sample size" in w for w in result.warnings)


def test_build_methods_includes_acquisition_from_sidecars(tmp_path):
    p = _project(tmp_path, {"StudyDesign": {"Type": "cross-sectional"}})
    d = p / "sub-01" / "ses-1" / "func"
    d.mkdir(parents=True)
    (d / "sub-01_ses-1_task-x_bold.json").write_text(
        json.dumps({"RepetitionTime": 2.0}), encoding="utf-8"
    )
    result = build_methods(p, app_root=str(tmp_path), compute_participant_stats=lambda *a, **k: None)
    assert "TR = 2000 ms" in result.md
    assert "DataAcquisition" in result.sections_used


def test_build_methods_includes_processing_from_recipes(tmp_path):
    p = _project(tmp_path, {"StudyDesign": {"Type": "cross-sectional"}})
    d = p / "code" / "recipes" / "survey"
    d.mkdir(parents=True)
    (d / "recipe-ads.json").write_text(
        json.dumps({"Survey": {"TaskName": "ads"}, "Scores": [{"Name": "Total"}]}), encoding="utf-8"
    )
    result = build_methods(p, app_root=str(tmp_path), compute_participant_stats=lambda *a, **k: None)
    assert "ads (Total)" in result.md and "DataProcessing" in result.sections_used


def test_build_methods_accepts_project_json_path(tmp_path):
    p = _project(tmp_path, {"StudyDesign": {"Type": "cross-sectional"}})
    result = build_methods(p / "project.json", app_root=str(tmp_path), compute_participant_stats=lambda *a, **k: None)
    assert "cross sectional design" in result.md


def test_build_methods_lists_surveys_found_in_dataset_without_task_definitions(tmp_path):
    root = _project(tmp_path, {"StudyDesign": {"Type": "cross-sectional"}})
    survey = root / "rawdata" / "sub-01" / "ses-1" / "survey"
    survey.mkdir(parents=True)
    (survey / "sub-01_ses-1_task-ads_survey.tsv").write_text("item_01\n1\n", encoding="utf-8")
    lib = root / "code" / "library" / "survey"
    lib.mkdir(parents=True)
    (lib / "survey-ads.json").write_text(json.dumps(TEMPLATE), encoding="utf-8")
    with _no_global_library():
        result = build_methods(root)
    assert "Measures" in result.sections_used
    assert "Affective Distress Scale" in result.md
    assert set(result.template_data) == {"ads"}


def test_methods_cites_prism_studio_zenodo(tmp_path):
    from src.text_export import references_bib

    root = _project(tmp_path, {"StudyDesign": {"Type": "cross-sectional"}})
    with _no_global_library():
        result = build_methods(root)
    assert "https://doi.org/10.5281/zenodo.22809100" in result.md
    assert "10.5281/zenodo.22809100" in references_bib(result.template_data)


def _survey_file(root, sub, ses, task):
    folder = root / "rawdata" / f"sub-{sub}" / (f"ses-{ses}" if ses else "") / "survey"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"sub-{sub}_" + (f"ses-{ses}_" if ses else "") + f"task-{task}_survey.tsv"
    (folder / name).write_text("item_01\n1\n", encoding="utf-8")


def test_discover_sessions_groups_tasks_and_counts(tmp_path):
    from src.methods_project import discover_sessions

    for sub in ("01", "02"):
        _survey_file(tmp_path, sub, "1", "ads")
    _survey_file(tmp_path, "01", "2", "ads")
    _survey_file(tmp_path, "01", "2", "pss")
    sessions = discover_sessions(tmp_path)
    assert [s["label"] for s in sessions] == ["1", "2"]
    assert sessions[0]["id"] == "ses-1"
    assert sessions[0]["tasks"] == [{"task": "ads", "n": 2}]
    assert sessions[1]["tasks"] == [{"task": "ads", "n": 1}, {"task": "pss", "n": 1}]
    assert all(s["ordered"] for s in sessions)


def test_discover_sessions_keeps_1_and_01_distinct(tmp_path):
    from src.methods_project import discover_sessions

    _survey_file(tmp_path, "01", "1", "ads")
    _survey_file(tmp_path, "01", "01", "ads")
    assert sorted(s["label"] for s in discover_sessions(tmp_path)) == ["01", "1"]


def test_discover_sessions_non_numeric_unordered(tmp_path):
    from src.methods_project import discover_sessions

    _survey_file(tmp_path, "01", "pre", "ads")
    _survey_file(tmp_path, "01", "post", "ads")
    sessions = discover_sessions(tmp_path)
    assert [s["label"] for s in sessions] == ["post", "pre"]
    assert not any(s["ordered"] for s in sessions)


def test_discover_sessions_without_session_folders(tmp_path):
    from src.methods_project import discover_sessions

    _survey_file(tmp_path, "01", "", "ads")
    sessions = discover_sessions(tmp_path)
    assert sessions == [{"id": "", "label": "", "tasks": [{"task": "ads", "n": 1}], "ordered": True}]
