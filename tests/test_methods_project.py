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
    assert result.warnings == []
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
