import io
import json
import os
from pathlib import Path

import pytest
from flask import Flask, session

from src.converters.survey import (
    SurveyResponsesConverter,
    SurveyValueOutOfBoundsError,
    sync_project_survey_recipe_offsets,
)
from src.web.blueprints.conversion_survey_preview_handlers import (
    handle_api_survey_convert_preview,
)


def _write_basic_survey_template(library_root: Path, task: str = "pss") -> None:
    library_root.mkdir(parents=True, exist_ok=True)
    (library_root / f"survey-{task}.json").write_text(
        json.dumps(
            {
                "Study": {"TaskName": task},
                "PSS01": {
                    "Levels": {
                        "0": "never",
                        "1": "almost never",
                        "2": "sometimes",
                        "3": "fairly often",
                        "4": "very often",
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_survey_converter_raises_structured_error_for_out_of_bounds_value(tmp_path):
    input_path = tmp_path / "survey.csv"
    input_path.write_text("ID,PSS01\nsub-001,5\n", encoding="utf-8")

    library_root = tmp_path / "library"
    _write_basic_survey_template(library_root, task="pss")

    with pytest.raises(SurveyValueOutOfBoundsError) as error_info:
        SurveyResponsesConverter().convert_xlsx(
            input_path=input_path,
            library_dir=library_root,
            output_root=tmp_path / "out",
            id_column="ID",
            session="all",
            dry_run=False,
            force=True,
            skip_participants=True,
            separator=",",
        )

    error = error_info.value
    assert error.task == "pss"
    assert error.item_id == "PSS01"
    assert error.raw_value == "5"
    assert -1 in error.suggested_offsets
    evidence = getattr(error, "offset_evidence", None)
    assert isinstance(evidence, dict)
    assert evidence.get("classification") == "item_issues_likely"
    assert evidence.get("invalid_without_offset") == 1
    assert evidence.get("sampled_numeric_values") == 1
    assert evidence.get("invalid_without_offset_percent") == pytest.approx(100.0)
    assert evidence.get("corrected_by_best_offset_percent") == pytest.approx(100.0)


def test_survey_converter_infers_structural_task_offset_evidence(tmp_path):
    input_path = tmp_path / "survey.csv"
    input_path.write_text(
        "ID,PSS01\nsub-001,5\nsub-002,5\nsub-003,5\nsub-004,5\n",
        encoding="utf-8",
    )

    library_root = tmp_path / "library"
    _write_basic_survey_template(library_root, task="pss")

    with pytest.raises(SurveyValueOutOfBoundsError) as error_info:
        SurveyResponsesConverter().convert_xlsx(
            input_path=input_path,
            library_dir=library_root,
            output_root=tmp_path / "out",
            id_column="ID",
            session="all",
            dry_run=False,
            force=True,
            skip_participants=True,
            separator=",",
        )

    error = error_info.value
    evidence = getattr(error, "offset_evidence", None)
    assert isinstance(evidence, dict)
    assert evidence.get("scope") == "task"
    assert evidence.get("classification") == "structural_offset_likely"
    assert evidence.get("best_offset") == -1
    assert evidence.get("corrected_by_best_offset") == evidence.get(
        "invalid_without_offset"
    )
    assert evidence.get("sampled_numeric_values") == 4
    assert evidence.get("invalid_without_offset") == 4
    assert evidence.get("invalid_without_offset_percent") == pytest.approx(100.0)
    assert evidence.get("corrected_by_best_offset_percent") == pytest.approx(100.0)
    assert evidence.get("invalid_with_best_offset") == 0
    assert evidence.get("invalid_with_best_offset_percent") == pytest.approx(0.0)


def test_survey_converter_applies_explicit_value_offset_and_tracks_usage(tmp_path):
    input_path = tmp_path / "survey.csv"
    input_path.write_text("ID,PSS01\nsub-001,5\nsub-002,4\n", encoding="utf-8")

    library_root = tmp_path / "library"
    _write_basic_survey_template(library_root, task="pss")

    result = SurveyResponsesConverter().convert_xlsx(
        input_path=input_path,
        library_dir=library_root,
        output_root=tmp_path / "out",
        id_column="ID",
        session="all",
        dry_run=False,
        force=True,
        skip_participants=True,
        separator=",",
        task_value_offsets={"pss": -1},
    )

    assert result.applied_value_offsets == {"pss": -1.0}
    assert result.value_offset_application_counts.get("pss") == 2


def test_survey_converter_rejects_offset_when_allowed_values_conflict(tmp_path):
    input_path = tmp_path / "survey.csv"
    input_path.write_text("ID,PSS01\nsub-001,1\n", encoding="utf-8")

    library_root = tmp_path / "library"
    library_root.mkdir(parents=True, exist_ok=True)
    (library_root / "survey-pss.json").write_text(
        json.dumps(
            {
                "Study": {"TaskName": "pss"},
                "PSS01": {
                    "AllowedValues": [1, 2, 3, 4, 5],
                    "Levels": {
                        "0": "never",
                        "1": "almost never",
                        "2": "sometimes",
                        "3": "fairly often",
                        "4": "very often",
                    },
                    "MinValue": 0,
                    "MaxValue": 4,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SurveyValueOutOfBoundsError) as error_info:
        SurveyResponsesConverter().convert_xlsx(
            input_path=input_path,
            library_dir=library_root,
            output_root=tmp_path / "out",
            id_column="ID",
            session="all",
            dry_run=False,
            force=True,
            skip_participants=True,
            separator=",",
            task_value_offsets={"pss": -1},
        )

    error = error_info.value
    assert error.task == "pss"
    assert error.item_id == "PSS01"
    assert error.configured_offset == -1.0
    assert "did not resolve this value" in str(error)
    assert error.expected_levels == ["1", "2", "3", "4", "5"]


def test_survey_converter_suggests_offset_from_allowed_values_when_levels_conflict(tmp_path):
    input_path = tmp_path / "survey.csv"
    input_path.write_text("ID,PSS01\nsub-001,6\n", encoding="utf-8")

    library_root = tmp_path / "library"
    library_root.mkdir(parents=True, exist_ok=True)
    (library_root / "survey-pss.json").write_text(
        json.dumps(
            {
                "Study": {"TaskName": "pss"},
                "PSS01": {
                    "AllowedValues": [1, 2, 3, 4, 5],
                    "Levels": {
                        "0": "never",
                        "1": "almost never",
                        "2": "sometimes",
                        "3": "fairly often",
                        "4": "very often",
                    },
                    "MinValue": 0,
                    "MaxValue": 4,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SurveyValueOutOfBoundsError) as error_info:
        SurveyResponsesConverter().convert_xlsx(
            input_path=input_path,
            library_dir=library_root,
            output_root=tmp_path / "out",
            id_column="ID",
            session="all",
            dry_run=False,
            force=True,
            skip_participants=True,
            separator=",",
        )

    error = error_info.value
    assert error.expected_levels == ["1", "2", "3", "4", "5"]
    assert error.suggested_offsets == [-1]


def test_survey_converter_clears_unsafe_task_wide_offset_suggestion(tmp_path):
    input_path = tmp_path / "survey.csv"
    input_path.write_text("ID,PSS01,PSS02\nsub-001,5,1\n", encoding="utf-8")

    library_root = tmp_path / "library"
    library_root.mkdir(parents=True, exist_ok=True)
    (library_root / "survey-pss.json").write_text(
        json.dumps(
            {
                "Study": {"TaskName": "pss"},
                "PSS01": {
                    "Levels": {
                        "0": "never",
                        "1": "almost never",
                        "2": "sometimes",
                        "3": "fairly often",
                        "4": "very often",
                    },
                    "MinValue": 0,
                    "MaxValue": 4,
                },
                "PSS02": {
                    "AllowedValues": [1, 2, 3, 4, 5],
                    "Levels": {
                        "0": "never",
                        "1": "almost never",
                        "2": "sometimes",
                        "3": "fairly often",
                        "4": "very often",
                    },
                    "MinValue": 0,
                    "MaxValue": 4,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SurveyValueOutOfBoundsError) as error_info:
        SurveyResponsesConverter().convert_xlsx(
            input_path=input_path,
            library_dir=library_root,
            output_root=tmp_path / "out",
            id_column="ID",
            session="all",
            dry_run=False,
            force=True,
            skip_participants=True,
            separator=",",
        )

    error = error_info.value
    evidence = getattr(error, "offset_evidence", None)
    assert isinstance(evidence, dict)
    assert evidence.get("best_offset") == -1
    assert evidence.get("invalid_with_best_offset") == 1
    assert evidence.get("newly_invalid_with_best_offset") == 1
    assert error.suggested_offsets == []


def test_sync_project_survey_recipe_offsets_updates_metadata(tmp_path):
    project_root = tmp_path / "project"
    recipe_dir = project_root / "code" / "recipes" / "survey"
    recipe_dir.mkdir(parents=True, exist_ok=True)
    recipe_path = recipe_dir / "recipe-pss.json"
    recipe_path.write_text(
        json.dumps(
            {
                "RecipeVersion": "1.0",
                "Kind": "survey",
                "Survey": {"Name": "Perceived Stress Scale", "TaskName": "pss"},
                "Scores": [],
            }
        ),
        encoding="utf-8",
    )

    summary = sync_project_survey_recipe_offsets(
        project_root=project_root,
        task_value_offsets={"pss": -1},
        offset_application_counts={"pss": 3},
    )

    assert summary["updated_tasks"] == ["pss"]
    assert summary["missing_tasks"] == []
    updated = json.loads(recipe_path.read_text(encoding="utf-8"))
    survey_section = updated.get("Survey", {})
    assert survey_section.get("ImportValueOffset") == -1
    assert survey_section.get("ImportValueOffsetSource") == "survey-import"
    history = survey_section.get("ImportValueOffsetHistory") or []
    assert history
    assert history[-1].get("offset") == -1


def test_survey_preview_returns_value_offset_confirmation_payload(tmp_path):
    app = Flask(__name__)
    app.secret_key = os.urandom(32)

    project_root = tmp_path / "project"
    project_root.mkdir()
    library_root = tmp_path / "library"
    _write_basic_survey_template(library_root, task="pss")

    def fake_run_survey_with_official_fallback(_converter, **_kwargs):
        raise SurveyValueOutOfBoundsError(
            task="pss",
            item_id="PSS01",
            sub_id="sub-001",
            raw_value="5",
            expected_levels=["0", "1", "2", "3", "4"],
            suggested_offsets=[-1],
            message="Item PSS01 for task pss has value 5 outside expected levels",
        )

    with app.test_request_context(
        "/api/survey-convert-preview",
        method="POST",
        data={
            "file": (io.BytesIO(b"ID,PSS01\nsub-001,5\n"), "demo.csv"),
            "id_column": "ID",
            "validate": "false",
            "value_offsets": '{"pss": -1}',
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
            build_template_completion_gate=lambda _issues: None,
            format_unmatched_groups_response=lambda _error: {},
            id_column_not_detected_error_cls=ValueError,
            unmatched_groups_error_cls=RuntimeError,
            survey_value_out_of_bounds_error_cls=SurveyValueOutOfBoundsError,
            format_value_offset_confirmation_response=lambda error: {
                "error": "value_offset_manual_review_required",
                "task": error.task,
                "item_id": error.item_id,
                "suggested_offsets": list(error.suggested_offsets),
            },
        )

    if isinstance(response, tuple):
        flask_response, status_code = response
    else:
        flask_response = response
        status_code = response.status_code

    payload = flask_response.get_json()
    assert status_code == 409
    assert payload["error"] == "value_offset_manual_review_required"
    assert payload["task"] == "pss"
    assert payload["item_id"] == "PSS01"
    assert payload["suggested_offsets"] == [-1]


def test_survey_preview_passes_value_offsets_to_converter(tmp_path):
    app = Flask(__name__)
    app.secret_key = os.urandom(32)

    project_root = tmp_path / "project"
    project_root.mkdir()
    library_root = tmp_path / "library"
    _write_basic_survey_template(library_root, task="pss")

    calls = []

    def fake_run_survey_with_official_fallback(_converter, **kwargs):
        calls.append(kwargs)
        return type(
            "Result",
            (),
            {
                "dry_run_preview": {
                    "summary": {
                        "total_participants": 1,
                        "unique_participants": 1,
                        "tasks": ["pss"],
                        "session_column": None,
                        "run_column": None,
                        "total_files": 1,
                        "total_files_to_create": 1,
                    },
                    "participants": [],
                    "files_to_create": [],
                    "data_issues": [],
                    "column_mapping": {},
                },
                "tasks_included": ["pss"],
                "unknown_columns": [],
                "missing_items_by_task": {},
                "id_column": "ID",
                "session_column": None,
                "run_column": None,
                "detected_sessions": [],
                "conversion_warnings": [],
                "task_runs": {},
                "template_matches": None,
                "tool_columns": [],
                "near_match_candidates": [],
                "near_match_applied": False,
                "applied_value_offsets": {"pss": -1.0},
                "value_offset_application_counts": {},
            },
        )()

    with app.test_request_context(
        "/api/survey-convert-preview",
        method="POST",
        data={
            "file": (io.BytesIO(b"ID,PSS01\nsub-001,5\n"), "demo.csv"),
            "id_column": "ID",
            "validate": "false",
            "value_offsets": '{"pss": -1}',
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
            build_template_completion_gate=lambda _issues: None,
            format_unmatched_groups_response=lambda _error: {},
            id_column_not_detected_error_cls=ValueError,
            unmatched_groups_error_cls=RuntimeError,
        )

    payload = response.get_json()
    assert calls
    assert calls[0]["task_value_offsets"] == {"pss": -1.0}
    assert payload["applied_value_offsets"] == {"pss": -1.0}


def test_survey_preview_merges_selected_tasks_filter(tmp_path):
    app = Flask(__name__)
    app.secret_key = os.urandom(32)

    project_root = tmp_path / "project"
    project_root.mkdir()
    library_root = tmp_path / "library"
    _write_basic_survey_template(library_root, task="pss")

    calls = []

    def fake_run_survey_with_official_fallback(_converter, **kwargs):
        calls.append(kwargs)
        return type(
            "Result",
            (),
            {
                "dry_run_preview": {
                    "summary": {
                        "total_participants": 1,
                        "unique_participants": 1,
                        "tasks": ["pss"],
                        "session_column": None,
                        "run_column": None,
                        "total_files": 1,
                        "total_files_to_create": 1,
                    },
                    "participants": [],
                    "files_to_create": [],
                    "data_issues": [],
                    "column_mapping": {},
                },
                "tasks_included": ["pss"],
                "unknown_columns": [],
                "missing_items_by_task": {},
                "id_column": "ID",
                "session_column": None,
                "run_column": None,
                "detected_sessions": [],
                "conversion_warnings": [],
                "task_runs": {},
                "template_matches": None,
                "tool_columns": [],
                "near_match_candidates": [],
                "near_match_applied": False,
                "applied_value_offsets": {},
                "value_offset_application_counts": {},
            },
        )()

    with app.test_request_context(
        "/api/survey-convert-preview",
        method="POST",
        data={
            "file": (io.BytesIO(b"ID,PSS01\nsub-001,5\n"), "demo.csv"),
            "id_column": "ID",
            "validate": "false",
            "survey": "pss,gad",
            "selected_tasks": '["pss"]',
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
            build_template_completion_gate=lambda _issues: None,
            format_unmatched_groups_response=lambda _error: {},
            id_column_not_detected_error_cls=ValueError,
            unmatched_groups_error_cls=RuntimeError,
        )

    payload = response.get_json()
    assert calls
    assert calls[0]["survey"] == "pss"
    assert payload["survey_tasks"][0]["task"] == "pss"
    assert payload["survey_tasks"][0]["selected"] is True


def test_survey_preview_validate_path_returns_task_review_summary(tmp_path):
    app = Flask(__name__)
    app.secret_key = os.urandom(32)

    project_root = tmp_path / "project"
    project_root.mkdir()
    library_root = tmp_path / "library"
    _write_basic_survey_template(library_root, task="pss")

    call_count = {"count": 0}

    def fake_run_survey_with_official_fallback(_converter, **_kwargs):
        call_count["count"] += 1
        if call_count["count"] == 1:
            return type(
                "Result",
                (),
                {
                    "dry_run_preview": {
                        "summary": {
                            "total_participants": 1,
                            "unique_participants": 1,
                            "tasks": ["pss"],
                            "session_column": None,
                            "run_column": None,
                            "total_files": 1,
                            "total_files_to_create": 1,
                        },
                        "participants": [],
                        "files_to_create": [],
                        "data_issues": [],
                        "column_mapping": {},
                    },
                    "tasks_included": ["pss"],
                    "unknown_columns": [],
                    "missing_items_by_task": {},
                    "id_column": "ID",
                    "session_column": None,
                    "run_column": None,
                    "detected_sessions": [],
                    "conversion_warnings": [],
                    "task_runs": {},
                    "template_matches": None,
                    "tool_columns": [],
                    "near_match_candidates": [],
                    "near_match_applied": False,
                    "applied_value_offsets": {},
                    "value_offset_application_counts": {},
                },
            )()

        raise SurveyValueOutOfBoundsError(
            task="pss",
            item_id="PSS01",
            sub_id="sub-001",
            raw_value="5",
            expected_levels=["0", "1", "2", "3", "4"],
            suggested_offsets=[-1],
            message="Item PSS01 for task pss has value 5 outside expected levels",
        )

    with app.test_request_context(
        "/api/survey-convert-preview",
        method="POST",
        data={
            "file": (io.BytesIO(b"ID,PSS01\nsub-001,5\n"), "demo.csv"),
            "id_column": "ID",
            "validate": "true",
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
            build_template_completion_gate=lambda _issues: None,
            format_unmatched_groups_response=lambda _error: {},
            id_column_not_detected_error_cls=ValueError,
            unmatched_groups_error_cls=RuntimeError,
            survey_value_out_of_bounds_error_cls=SurveyValueOutOfBoundsError,
            format_value_offset_confirmation_response=lambda error: {
                "error": "value_offset_manual_review_required",
                "task": error.task,
                "item_id": error.item_id,
                "suggested_offsets": list(error.suggested_offsets),
            },
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert call_count["count"] == 2
    assert payload["tasks_included"] == ["pss"]
    assert payload["survey_tasks"][0]["task"] == "pss"
    assert payload["survey_tasks"][0]["manual_review_required"] is True
    assert payload["survey_tasks"][0]["out_of_range"]["item_id"] == "PSS01"
    assert payload["survey_tasks"][0]["out_of_range"]["suggested_offsets"] == [-1]
