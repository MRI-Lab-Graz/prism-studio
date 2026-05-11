from pathlib import Path
from typing import Any

from src.survey_workflow_service import (
    SUPPORTED_SURVEY_INPUT_MESSAGE,
    SUPPORTED_SURVEY_INPUT_SUFFIXES,
    SUPPORTED_SURVEY_TABULAR_SUFFIXES,
    SurveyWorkflowStageOptions,
    SurveyWorkflowStageService,
)


def test_run_stage_preserves_list_template_version_overrides() -> None:
    service = SurveyWorkflowStageService(tabular_suffixes={".csv"})
    captured: dict[str, Any] = {}

    def workflow_runner(converter: Any, **kwargs: Any) -> dict[str, Any]:
        captured["converter"] = converter
        captured.update(kwargs)
        return kwargs

    overrides = [
        {
            "task": "tsdz",
            "session": "ses-1",
            "run": "run-base-7-likert",
            "version": "v1",
        }
    ]

    options = SurveyWorkflowStageOptions(
        suffix=".csv",
        input_path=Path("input.csv"),
        library_dir=Path("/tmp/library"),
        output_root=Path("/tmp/output"),
        template_version_overrides=overrides,
    )

    result = service.run_stage(
        workflow_runner=workflow_runner,
        tabular_converter=object(),
        lsa_converter=None,
        options=options,
    )

    assert isinstance(result.get("template_version_overrides"), list)
    assert result["template_version_overrides"] == overrides


def test_run_stage_copies_dict_template_version_overrides() -> None:
    service = SurveyWorkflowStageService(tabular_suffixes={".csv"})

    def workflow_runner(converter: Any, **kwargs: Any) -> dict[str, Any]:
        return kwargs

    overrides = {"tsdz": "v1"}

    options = SurveyWorkflowStageOptions(
        suffix=".csv",
        input_path=Path("input.csv"),
        library_dir=Path("/tmp/library"),
        output_root=Path("/tmp/output"),
        template_version_overrides=overrides,
    )

    result = service.run_stage(
        workflow_runner=workflow_runner,
        tabular_converter=object(),
        lsa_converter=None,
        options=options,
    )

    assert result["template_version_overrides"] == {"tsdz": "v1"}
    assert result["template_version_overrides"] is not overrides


def test_parse_stage_form_fields_normalizes_values() -> None:
    service = SurveyWorkflowStageService(tabular_suffixes={".csv"})

    parsed = service.parse_stage_form_fields(
        form={
            "id_column": " participant_id ",
            "session_column": " session ",
            "run_column": " run ",
            "session": " all ",
            "sheet": " 2 ",
            "unknown": " keep ",
            "dataset_name": " study dataset ",
            "language": " de ",
            "strict_levels": "YES",
            "allow_near_item_match": "on",
            "duplicate_handling": "sessions",
        }
    )

    assert parsed.id_column == "participant_id"
    assert parsed.session_column == "session"
    assert parsed.run_column == "run"
    assert parsed.session_override == "all"
    assert parsed.sheet == "2"
    assert parsed.unknown == "keep"
    assert parsed.dataset_name == "study dataset"
    assert parsed.language == "de"
    assert parsed.strict_levels is True
    assert parsed.allow_near_item_match is True
    assert parsed.duplicate_handling == "sessions"


def test_parse_stage_form_fields_applies_defaults_and_duplicate_fallback() -> None:
    service = SurveyWorkflowStageService(tabular_suffixes={".csv"})

    parsed = service.parse_stage_form_fields(
        form={
            "id_column": " ",
            "session_column": "",
            "run_column": None,
            "session": " ",
            "sheet": " ",
            "unknown": " ",
            "dataset_name": " ",
            "language": " ",
            "strict_levels": "0",
            "allow_near_item_match": "false",
            "duplicate_handling": "invalid",
        }
    )

    assert parsed.id_column is None
    assert parsed.session_column is None
    assert parsed.run_column is None
    assert parsed.session_override is None
    assert parsed.sheet == 0
    assert parsed.unknown == "warn"
    assert parsed.dataset_name is None
    assert parsed.language is None
    assert parsed.strict_levels is False
    assert parsed.allow_near_item_match is False
    assert parsed.duplicate_handling == "error"


def test_build_near_match_confirmation_payload() -> None:
    payload = SurveyWorkflowStageService.build_near_match_confirmation_payload(
        near_match_candidates=[{"task": "pss"}, {"task": "ads"}],
    )

    assert payload["error"] == "near_item_match_confirmation_required"
    assert "Exact matching left item-like columns unmapped." in payload["message"]
    assert payload["near_match_candidates"] == [{"task": "pss"}, {"task": "ads"}]
    assert payload["near_match_count"] == 2


def test_build_template_completion_required_payload() -> None:
    payload = SurveyWorkflowStageService.build_template_completion_required_payload(
        workflow_gate={
            "blocked": True,
            "message": "Complete project templates first.",
            "tasks": ["pss"],
        },
        template_issues=[{"file": "survey-pss.json", "message": "missing"}],
    )

    assert payload["error"] == "project_template_completion_required"
    assert payload["message"] == "Complete project templates first."
    assert payload["workflow_gate"] == {
        "blocked": True,
        "message": "Complete project templates first.",
        "tasks": ["pss"],
    }
    assert payload["template_issues"] == [
        {"file": "survey-pss.json", "message": "missing"}
    ]


def test_format_workflow_preparation_stale_response_wraps_blockers() -> None:
    payload = SurveyWorkflowStageService.format_workflow_preparation_stale_response(
        payload={
            "error": "near_item_match_confirmation_required",
            "message": "Confirm near matches.",
        },
        prepared_workflow=True,
    )

    assert payload["error"] == "workflow_preparation_stale"
    assert payload["blocking_error"] == "near_item_match_confirmation_required"
    assert "Run Preview again" in payload["message"]


def test_format_workflow_preparation_stale_response_keeps_non_prepared_payload() -> None:
    payload = SurveyWorkflowStageService.format_workflow_preparation_stale_response(
        payload={"error": "project_template_completion_required", "message": "Fill templates."},
        prepared_workflow=False,
        log_messages=[{"message": "blocked", "level": "error"}],
    )

    assert payload["error"] == "project_template_completion_required"
    assert "blocking_error" not in payload
    assert payload["log"] == [{"message": "blocked", "level": "error"}]


def test_parse_prepared_workflow_flag_truthy_values() -> None:
    for value in ["1", "true", "yes", "on", " TRUE ", "Yes"]:
        assert SurveyWorkflowStageService.parse_prepared_workflow_flag(value) is True


def test_parse_prepared_workflow_flag_falsey_values() -> None:
    for value in [None, "", "0", "false", "off", "no", " preview "]:
        assert SurveyWorkflowStageService.parse_prepared_workflow_flag(value) is False


def test_supported_survey_input_constants_are_canonical() -> None:
    assert ".xlsx" in SUPPORTED_SURVEY_TABULAR_SUFFIXES
    assert ".lsa" not in SUPPORTED_SURVEY_TABULAR_SUFFIXES
    assert ".lsa" in SUPPORTED_SURVEY_INPUT_SUFFIXES
    assert "Supported formats:" in SUPPORTED_SURVEY_INPUT_MESSAGE
