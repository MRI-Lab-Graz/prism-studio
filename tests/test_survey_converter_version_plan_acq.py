"""Regression tests for template Study.Version -> acq filename behavior."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure app package is importable as `src.*`
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

import pandas as pd

from src.converters.survey import (
    _build_task_context_maps,
    _load_and_preprocess_templates,
    convert_survey_xlsx_to_prism_dataset,
)
from src.converters.survey_templates import _apply_template_version_selection


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

    _, task_context_acq_map = _build_task_context_maps(
        tasks_with_data={"wellbeing-multi"},
        df=pd.DataFrame(),
        res_ses_col=None,
        session=None,
        res_run_col=None,
        task_run_columns={},
        templates=templates,
        template_version_overrides=None,
        normalize_ses_fn=lambda value: f"ses-{value}",
    )

    assert task_context_acq_map[("wellbeing-multi", None, None)] == "10-likert"
    assert templates["wellbeing-multi"]["json"]["Study"]["Version"] == "10-likert"


def test_template_version_used_when_no_project_mapping():
    templates = _make_templates(active_version="10-likert")

    _, task_context_acq_map = _build_task_context_maps(
        tasks_with_data={"wellbeing-multi"},
        df=pd.DataFrame(),
        res_ses_col=None,
        session=None,
        res_run_col=None,
        task_run_columns={},
        templates=templates,
        template_version_overrides=None,
        normalize_ses_fn=lambda value: f"ses-{value}",
    )

    assert task_context_acq_map[("wellbeing-multi", None, None)] == "10-likert"


def test_invalid_template_version_raises():
    templates = _make_templates(active_version="nonexistent")

    with pytest.raises(ValueError, match="Template version mismatch"):
        _build_task_context_maps(
            tasks_with_data={"wellbeing-multi"},
            df=pd.DataFrame(),
            res_ses_col=None,
            session=None,
            res_run_col=None,
            task_run_columns={},
            templates=templates,
            template_version_overrides=None,
            normalize_ses_fn=lambda value: f"ses-{value}",
        )


def test_selected_template_version_filters_applicable_items(tmp_path):
    library_dir = tmp_path / "survey"
    library_dir.mkdir()
    (library_dir / "survey-wellbeing-multi.json").write_text(
        """
        {
            "Study": {
                "TaskName": "wellbeing-multi",
                "Version": "10-likert",
                "Versions": ["10-likert", "7-likert"]
            },
            "WB01": {"Description": "Shared item"},
            "WB02": {"Description": "10 item", "ApplicableVersions": ["10-likert"]},
            "WB03": {"Description": "7 item", "ApplicableVersions": ["7-likert"]}
        }
        """.strip(),
        encoding="utf-8",
    )

    templates, item_to_task, duplicates, warnings = _load_and_preprocess_templates(
        library_dir=library_dir,
        canonical_aliases=None,
        compare_with_global=False,
        template_version_overrides={"wellbeing-multi": "7-likert"},
    )

    template = templates["wellbeing-multi"]["json"]
    assert template["Study"]["Version"] == "7-likert"
    assert "WB01" in template
    assert "WB02" not in template
    assert "WB03" in template
    assert item_to_task["WB03"] == "wellbeing-multi"
    assert "WB02" not in item_to_task
    assert duplicates == {}
    assert warnings == {}


def test_run_specific_template_versions_build_distinct_acq_maps():
    templates = {
        "wellbeing-multi": {
            "json": {
                "Study": {
                    "TaskName": "wellbeing-multi",
                    "Version": "10-likert",
                    "Versions": ["10-likert", "10-vas"],
                },
                "WB01": {"Description": "Shared item"},
                "WB02": {
                    "Description": "Likert-only",
                    "ApplicableVersions": ["10-likert"],
                },
                "WB03": {
                    "Description": "VAS-only",
                    "ApplicableVersions": ["10-vas"],
                },
            }
        }
    }

    task_context_templates, task_context_acq_map = _build_task_context_maps(
        tasks_with_data={"wellbeing-multi"},
        df=pd.DataFrame({"run": [1, 2]}),
        res_ses_col=None,
        session=None,
        res_run_col="run",
        task_run_columns={("wellbeing-multi", None): ["WB01", "WB02", "WB03"]},
        templates=templates,
        template_version_overrides=[
            {"task": "wellbeing-multi", "run": 2, "version": "10-vas"}
        ],
        normalize_ses_fn=lambda value: f"ses-{value}",
    )

    assert task_context_acq_map[("wellbeing-multi", None, "run-1")] == "10-likert"
    assert task_context_acq_map[("wellbeing-multi", None, "run-2")] == "10-vas"
    assert "WB02" in task_context_templates[("wellbeing-multi", None, "run-1")]
    assert "WB03" not in task_context_templates[("wellbeing-multi", None, "run-1")]
    assert "WB02" not in task_context_templates[("wellbeing-multi", None, "run-2")]
    assert "WB03" in task_context_templates[("wellbeing-multi", None, "run-2")]


def test_session_and_run_specific_template_versions_build_distinct_context_maps():
    templates = {
        "wellbeing-multi": {
            "json": {
                "Study": {
                    "TaskName": "wellbeing-multi",
                    "Version": "10-likert",
                    "Versions": ["10-likert", "10-vas"],
                },
                "WB01": {"Description": "Shared item"},
                "WB02": {
                    "Description": "Likert-only",
                    "ApplicableVersions": ["10-likert"],
                },
                "WB03": {
                    "Description": "VAS-only",
                    "ApplicableVersions": ["10-vas"],
                },
            }
        }
    }

    task_context_templates, task_context_acq_map = _build_task_context_maps(
        tasks_with_data={"wellbeing-multi"},
        df=pd.DataFrame(
            {
                "session": ["pre", "post"],
                "run": [1, 2],
            }
        ),
        res_ses_col="session",
        session="all",
        res_run_col="run",
        task_run_columns={("wellbeing-multi", None): ["WB01", "WB02", "WB03"]},
        templates=templates,
        template_version_overrides=[
            {
                "task": "wellbeing-multi",
                "session": "ses-post",
                "run": 2,
                "version": "10-vas",
            }
        ],
        normalize_ses_fn=lambda value: (
            f"ses-{value}" if not str(value).startswith("ses-") else str(value)
        ),
    )

    assert task_context_acq_map[("wellbeing-multi", "ses-pre", "run-1")] == "10-likert"
    assert task_context_acq_map[("wellbeing-multi", "ses-post", "run-2")] == "10-vas"
    assert "WB02" in task_context_templates[("wellbeing-multi", "ses-pre", "run-1")]
    assert "WB03" not in task_context_templates[("wellbeing-multi", "ses-pre", "run-1")]
    assert "WB02" not in task_context_templates[("wellbeing-multi", "ses-post", "run-2")]
    assert "WB03" in task_context_templates[("wellbeing-multi", "ses-post", "run-2")]


def test_session_and_run_specific_template_versions_accept_language_map_values():
    templates = {
        "wellbeing-multi": {
            "json": {
                "Study": {
                    "TaskName": "wellbeing-multi",
                    "Version": "10-likert",
                    "Versions": ["10-likert", "10-vas"],
                },
                "WB01": {"Description": "Shared item"},
                "WB02": {
                    "Description": "Likert-only",
                    "ApplicableVersions": ["10-likert"],
                },
                "WB03": {
                    "Description": "VAS-only",
                    "ApplicableVersions": ["10-vas"],
                },
            }
        }
    }

    task_context_templates, task_context_acq_map = _build_task_context_maps(
        tasks_with_data={"wellbeing-multi"},
        df=pd.DataFrame(
            {
                "session": ["pre", "post"],
                "run": [1, 2],
            }
        ),
        res_ses_col="session",
        session="all",
        res_run_col="run",
        task_run_columns={("wellbeing-multi", None): ["WB01", "WB02", "WB03"]},
        templates=templates,
        template_version_overrides=[
            {
                "task": "wellbeing-multi",
                "session": "ses-pre",
                "run": 1,
                "version": {"en": "10-likert", "de": "10-likert"},
            },
            {
                "task": "wellbeing-multi",
                "session": "ses-post",
                "run": 2,
                "version": {"en": "10-vas", "de": "10-vas"},
            },
        ],
        normalize_ses_fn=lambda value: (
            f"ses-{value}" if not str(value).startswith("ses-") else str(value)
        ),
    )

    assert task_context_acq_map[("wellbeing-multi", "ses-pre", "run-1")] == "10-likert"
    assert task_context_acq_map[("wellbeing-multi", "ses-post", "run-2")] == "10-vas"
    assert "WB02" in task_context_templates[("wellbeing-multi", "ses-pre", "run-1")]
    assert "WB03" not in task_context_templates[("wellbeing-multi", "ses-pre", "run-1")]
    assert "WB02" not in task_context_templates[("wellbeing-multi", "ses-post", "run-2")]
    assert "WB03" in task_context_templates[("wellbeing-multi", "ses-post", "run-2")]


def test_selected_template_version_applies_variant_scales_to_shared_items():
    template = {
        "Study": {
            "TaskName": "wellbeing-multi",
            "Version": "10-likert",
            "Versions": ["10-likert", "10-vas"],
        },
        "WB01": {
            "Description": "Shared item",
            "MinValue": 1,
            "MaxValue": 5,
            "Levels": {str(index): str(index) for index in range(1, 6)},
            "VariantScales": [
                {
                    "VariantID": "10-vas",
                    "MinValue": 0,
                    "MaxValue": 100,
                    "Levels": {str(index): str(index) for index in range(0, 101)},
                }
            ],
        },
    }

    selected_template = _apply_template_version_selection(
        template,
        task="wellbeing-multi",
        requested_version="10-vas",
    )
    assert selected_template["Study"]["Version"] == "10-vas"
    assert selected_template["WB01"]["MinValue"] == 0
    assert selected_template["WB01"]["MaxValue"] == 100
    assert "70" in selected_template["WB01"]["Levels"]


def test_long_format_run_column_reports_max_run_for_multiversion_contexts(tmp_path):
    library_dir = tmp_path / "survey"
    library_dir.mkdir()

    template = {
        "Study": {
            "TaskName": "wellbeing-multi",
            "Version": "10-likert",
            "Versions": ["10-likert", "10-vas"],
        }
    }
    for index in range(1, 11):
        item_id = f"WBM{index:02d}"
        template[item_id] = {
            "Description": f"Item {index}",
            "ApplicableVersions": ["10-likert", "10-vas"],
            "DataType": "integer",
            "MinValue": 1,
            "MaxValue": 5,
            "Levels": {str(level): str(level) for level in range(1, 6)},
        }

    (library_dir / "survey-wellbeing-multi.json").write_text(
        json.dumps(template),
        encoding="utf-8",
    )

    input_path = tmp_path / "scenario.csv"
    input_path.write_text(
        """session,Code,Geschlecht,Alter,Händigkeit,WBM01,WBM02,WBM03,WBM04,WBM05,WBM06,WBM07,WBM08,WBM09,WBM10,run
pre,1,2,20,0,3,4,2,5,3,4,2,4,3,5,1
pre,2,2,22,1,2,3,3,4,2,3,2,3,2,4,1
pre,3,2,72,1,1,2,2,3,1,2,1,2,1,2,1
pre,4,1,25,1,2,4,3,4,2,3,3,4,3,4,1
pre,5,2,24,1,3,3,4,5,3,4,4,5,4,5,1
pre,6,1,23,1,2,2,3,3,2,2,3,3,2,3,1
pre,7,1,23,1,1,2,1,2,1,1,2,2,1,2,1
post,1,2,20,0,4,4,3,5,4,4,3,,,,1
post,2,2,22,1,3,3,3,4,3,3,3,,,,1
post,3,2,72,1,2,2,2,3,2,2,2,,,,1
post,4,1,25,1,3,4,3,4,3,4,3,,,,1
post,5,2,24,1,2,3,2,4,2,3,2,,,,1
post,6,1,23,1,4,3,4,4,4,3,4,,,,1
post,7,1,23,1,3,2,3,3,3,2,3,,,,1
pre,1,2,20,0,70,75,60,80,65,70,55,72,68,83,2
pre,2,2,22,1,45,50,40,60,48,52,41,55,49,63,2
pre,3,2,72,1,20,30,25,35,22,28,20,30,24,36,2
pre,4,1,25,1,55,65,58,70,60,62,57,68,61,72,2
pre,5,2,24,1,80,82,78,90,81,84,76,88,83,91,2
pre,6,1,23,1,35,40,32,45,38,41,34,44,39,47,2
pre,7,1,23,1,25,27,23,30,24,26,22,29,25,31,2
post,1,2,20,0,4,5,4,5,4,5,4,5,4,5,2
post,2,2,22,1,2,3,2,4,2,3,2,4,2,3,2
post,3,2,72,1,2,2,1,3,2,2,1,3,2,2,2
post,4,1,25,1,3,4,3,4,3,4,3,4,3,4,2
post,5,2,24,1,2,3,3,4,2,3,3,4,2,3,2
post,6,1,23,1,1,2,2,3,1,2,2,3,1,2,2
post,7,1,23,1,2,2,2,2,2,2,2,2,2,2,2
""",
        encoding="utf-8",
    )

    result = convert_survey_xlsx_to_prism_dataset(
        input_path=input_path,
        library_dir=library_dir,
        output_root=tmp_path / "out",
        survey="wellbeing-multi",
        id_column="Code",
        session_column="session",
        run_column="run",
        dry_run=True,
        force=True,
        separator=",",
        unknown="ignore",
    )

    assert result.task_runs == {"wellbeing-multi": 2}
