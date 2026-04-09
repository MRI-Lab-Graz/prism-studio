import io
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from flask import Flask, session

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = REPO_ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


from src.converters.survey import ColumnMapping
from src.converters.survey import SurveyResponsesConverter
from src.converters.survey_io import _generate_dry_run_preview
from src.web.blueprints.conversion_survey_preview_handlers import (
    handle_api_survey_convert_preview,
)


def test_generate_dry_run_preview_returns_structured_files_and_column_mapping(
    tmp_path,
):
    df = pd.DataFrame(
        {
            "participant_id": [1, 1],
            "session": ["pre", "post"],
            "run": [1, 2],
            "ADS01": [3, 4],
        }
    )

    preview = _generate_dry_run_preview(
        df=df,
        tasks_with_data={"ads"},
        task_run_columns={("ads", None): ["ADS01"]},
        col_to_mapping={
            "ADS01": ColumnMapping(task="ads", run=None, base_item="ADS01")
        },
        templates={"ads": {"json": {"ADS01": {"Levels": {"1": "low"}}}}},
        res_id_col="participant_id",
        res_ses_col="session",
        res_run_col="run",
        session=None,
        selected_tasks=None,
        normalize_sub_fn=lambda value: f"sub-{int(value):03d}",
        normalize_ses_fn=lambda value: f"ses-{value}",
        is_missing_fn=lambda value: value is None,
        ls_system_cols=[],
        participant_template=None,
        skip_participants=True,
        output_root=tmp_path / "rawdata",
        dataset_root=tmp_path,
        task_runs={"ads": 2},
        task_acq_map={},
    )

    assert preview["summary"]["total_files"] == 2
    assert preview["summary"]["total_files_to_create"] == 2
    assert sorted(item["run_id"] for item in preview["participants"]) == [1, 2]
    assert all(isinstance(item, dict) for item in preview["files_to_create"])
    assert all(item["type"] == "data" for item in preview["files_to_create"])
    assert any(
        item["path"].endswith("sub-001_ses-pre_task-ads_run-01_survey.tsv")
        for item in preview["files_to_create"]
    )
    assert preview["column_mapping"]["ADS01"] == {
        "task": "ads",
        "run": None,
        "base_item": "ADS01",
        "missing_count": 0,
        "missing_percent": 0.0,
        "has_unexpected_values": False,
        "expected_levels": ["1"],
    }


def test_survey_preview_validation_rerun_keeps_run_column(monkeypatch, tmp_path):
    app = Flask(__name__)
    app.secret_key = os.urandom(32)

    project_root = tmp_path / "project"
    project_root.mkdir()
    library_root = tmp_path / "library"
    library_root.mkdir()
    (library_root / "survey-ads.json").write_text("{}", encoding="utf-8")

    calls = []

    def fake_run_survey_with_official_fallback(_converter, **kwargs):
        calls.append(kwargs.copy())
        if kwargs.get("dry_run"):
            return SimpleNamespace(
                dry_run_preview={
                    "summary": {
                        "total_participants": 1,
                        "unique_participants": 1,
                        "tasks": ["ads"],
                        "session_column": "session",
                        "run_column": "run",
                        "total_files": 1,
                        "total_files_to_create": 1,
                    },
                    "participants": [
                        {
                            "participant_id": "sub-001",
                            "session_id": "ses-pre",
                            "run_id": 1,
                            "raw_id": "1",
                            "missing_values": 0,
                            "total_items": 1,
                            "completeness_percent": 100.0,
                        }
                    ],
                    "files_to_create": [
                        {
                            "type": "data",
                            "path": str(
                                tmp_path
                                / "rawdata"
                                / "sub-001"
                                / "ses-pre"
                                / "survey"
                                / "sub-001_ses-pre_task-ads_run-01_survey.tsv"
                            ),
                            "description": "Survey data for task ads, run 01",
                        }
                    ],
                    "data_issues": [],
                    "column_mapping": {
                        "ADS01": {
                            "task": "ads",
                            "run": None,
                            "base_item": "ADS01",
                            "missing_count": 0,
                            "missing_percent": 0.0,
                            "has_unexpected_values": False,
                            "expected_levels": [],
                        }
                    },
                },
                tasks_included=["ads"],
                unknown_columns=[],
                missing_items_by_task={},
                id_column="ID",
                session_column="session",
                run_column="run",
                detected_sessions=["pre"],
                conversion_warnings=[],
                task_runs={"ads": 1},
                template_matches=[],
                tool_columns=[],
            )
        return SimpleNamespace(tasks_included=["ads"])

    def fake_run_validation(*_args, **_kwargs):
        return (
            [],
            SimpleNamespace(
                total_files=1,
                subjects=set(),
                sessions=set(),
                tasks=set(),
                modalities={},
                surveys=set(),
                biometrics=set(),
            ),
        )

    monkeypatch.setattr(
        "src.web.blueprints.conversion_survey_preview_handlers.run_validation",
        fake_run_validation,
    )

    with app.test_request_context(
        "/api/survey-convert-preview",
        method="POST",
        data={
            "file": (io.BytesIO(b"ID,session,run,ADS01\n1,pre,1,3\n"), "demo.csv"),
            "id_column": "ID",
            "session_column": "session",
            "run_column": "run",
            "template_versions": '{"ads":"short"}',
        },
        content_type="multipart/form-data",
    ):
        session["current_project_path"] = str(project_root)

        response = handle_api_survey_convert_preview(
            convert_survey_xlsx_to_prism_dataset=object(),
            convert_survey_lsa_to_prism_dataset=object(),
            resolve_effective_library_path=lambda: library_root,
            run_survey_with_official_fallback=fake_run_survey_with_official_fallback,
            validate_project_templates_for_tasks=lambda **_kwargs: [],
            format_unmatched_groups_response=lambda _error: {},
            id_column_not_detected_error_cls=ValueError,
            unmatched_groups_error_cls=RuntimeError,
        )

    payload = response.get_json()

    assert len(calls) == 2
    assert calls[0]["run_column"] == "run"
    assert calls[1]["run_column"] == "run"
    assert calls[0]["template_version_overrides"] == {"ads": "short"}
    assert calls[1]["template_version_overrides"] == {"ads": "short"}
    assert payload["preview"]["summary"]["run_column"] == "run"
    assert payload["preview"]["summary"]["total_files"] == 1
    assert payload["multivariant_tasks"] == {}


def test_survey_converter_preserves_numeric_subject_ids_as_strings(tmp_path):
    input_path = tmp_path / "demo.csv"
    input_path.write_text(
        "Code,session,run,ADS01\n1,pre,1,3\n",
        encoding="utf-8",
    )

    library_root = tmp_path / "library"
    library_root.mkdir()
    (library_root / "survey-ads.json").write_text(
        """
        {
            "Study": {
                "TaskName": "ads"
            },
            "ADS01": {
                "Levels": {"1": "low", "2": "mid", "3": "high"}
            }
        }
        """.strip(),
        encoding="utf-8",
    )

    result = SurveyResponsesConverter().convert_xlsx(
        input_path=input_path,
        library_dir=library_root,
        output_root=tmp_path / "out",
        id_column="Code",
        session_column="session",
        run_column="run",
        session="all",
        dry_run=True,
        skip_participants=True,
        separator=",",
    )

    preview = result.dry_run_preview
    assert preview is not None
    assert preview["participants"][0]["participant_id"] == "sub-1"
    assert preview["participants"][0]["raw_id"] == "1"
    assert preview["files_to_create"][0]["path"].endswith(
        "sub-1/ses-pre/survey/sub-1_ses-pre_task-ads_run-01_survey.tsv"
    )
