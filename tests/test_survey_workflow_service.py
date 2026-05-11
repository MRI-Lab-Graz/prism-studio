from pathlib import Path
from typing import Any

from src.survey_workflow_service import (
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
