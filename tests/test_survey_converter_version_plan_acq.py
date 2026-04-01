"""Regression tests for template Study.Version -> acq filename behavior."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure app package is importable as `src.*`
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from src.converters.survey import _build_task_acq_map


def _make_templates(active_version: str = "10-likert") -> dict[str, dict]:
    return {
        "wellbeing-multi": {
            "json": {
                "Study": {
                    "TaskName": "wellbeing-multi",
                    "Version": active_version,
                    "Versions": ["10-likert", "7-likert", "10-vas"],
                }
            }
        }
    }


def test_template_version_drives_acq_map():
    templates = _make_templates(active_version="10-likert")

    task_acq_map = _build_task_acq_map(
        tasks_with_data={"wellbeing-multi"},
        templates=templates,
        project_path=None,
    )

    assert task_acq_map["wellbeing-multi"] == "10-likert"
    assert templates["wellbeing-multi"]["json"]["Study"]["Version"] == "10-likert"


def test_template_version_used_when_no_project_mapping():
    templates = _make_templates(active_version="10-likert")

    task_acq_map = _build_task_acq_map(
        tasks_with_data={"wellbeing-multi"},
        templates=templates,
        project_path=None,
    )

    assert task_acq_map["wellbeing-multi"] == "10-likert"


def test_invalid_template_version_raises():
    templates = _make_templates(active_version="nonexistent")

    with pytest.raises(ValueError, match="Template version mismatch"):
        _build_task_acq_map(
            tasks_with_data={"wellbeing-multi"},
            templates=templates,
            project_path=None,
        )
