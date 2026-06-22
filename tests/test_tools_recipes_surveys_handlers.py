from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from src.recipes_surveys import SurveyRecipesResult


def _import_handlers_module():
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))
    return importlib.import_module("src.web.blueprints.tools_recipes_surveys_handlers")


def _build_app() -> Flask:
    app_root = Path(__file__).resolve().parents[1] / "app"
    return Flask(__name__, root_path=str(app_root))


def test_combined_output_check_ignores_single_file_exports(tmp_path: Path) -> None:
    handlers = _import_handlers_module()

    out_dir = tmp_path / "derivatives" / "survey" / "long_en"
    out_dir.mkdir(parents=True)
    (out_dir / "ads.csv").write_text(
        "participant_id,score\nsub-001,1\n", encoding="utf-8"
    )
    (out_dir / "ads_codebook.json").write_text("{}", encoding="utf-8")

    existing = handlers._find_existing_recipe_output_files(
        derivatives_dir=out_dir,
        out_format="sav",
        merge_all=True,
        modality="survey",
        pyreadstat_available=True,
    )

    assert existing == []


def test_combined_output_check_only_flags_combined_targets(tmp_path: Path) -> None:
    handlers = _import_handlers_module()

    out_dir = tmp_path / "derivatives" / "survey" / "long_en"
    out_dir.mkdir(parents=True)
    combined_sav = out_dir / "combined_survey.sav"
    combined_codebook = out_dir / "combined_survey_codebook.tsv"
    combined_sav.write_text("sav", encoding="utf-8")
    combined_codebook.write_text("variable\tlabel\n", encoding="utf-8")
    (out_dir / "ads.sav").write_text("single", encoding="utf-8")

    existing = handlers._find_existing_recipe_output_files(
        derivatives_dir=out_dir,
        out_format="sav",
        merge_all=True,
        modality="survey",
        pyreadstat_available=True,
    )

    assert existing == [combined_sav, combined_codebook]


def test_recipes_template_defaults_to_spss_output() -> None:
    template_path = (
        Path(__file__).resolve().parents[1] / "app" / "templates" / "recipes.html"
    )
    content = template_path.read_text(encoding="utf-8")

    assert '<option value="sav" selected>' in content
    assert '<option value="csv" selected>' not in content


def test_recipes_ui_uses_analysis_outputs_labeling() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    recipes_template = (repo_root / "app" / "templates" / "recipes.html").read_text(
        encoding="utf-8"
    )
    base_template = (repo_root / "app" / "templates" / "base.html").read_text(
        encoding="utf-8"
    )

    assert "Analysis Outputs" in recipes_template
    assert "Create Output" in recipes_template
    assert "Analysis Outputs" in base_template


def test_handle_api_recipes_surveys_rejects_non_object_payload() -> None:
    handlers = _import_handlers_module()
    app = _build_app()

    with app.app_context():
        response, status_code = handlers.handle_api_recipes_surveys(None)

    assert status_code == 400
    payload = response.get_json()
    assert "invalid json payload" in payload["error"].lower()


def test_handle_api_recipes_surveys_rejects_invalid_id_length() -> None:
    handlers = _import_handlers_module()
    app = _build_app()

    with app.app_context():
        response, status_code = handlers.handle_api_recipes_surveys(
            {"id_length": "not-a-number"}
        )

    assert status_code == 400
    payload = response.get_json()
    assert "invalid id_length" in payload["error"].lower()


def test_handle_api_recipes_surveys_returns_user_error_for_missing_recipes(
    tmp_path: Path,
) -> None:
    handlers = _import_handlers_module()
    app = _build_app()

    dataset_path = tmp_path / "dataset"
    dataset_path.mkdir()

    recipe_dir = tmp_path / "recipes"
    recipe_dir.mkdir()

    error_message = (
        f"No derivative recipes found in: {recipe_dir}. Expected recipe-*.json"
    )

    with app.app_context(), patch(
        "src.web.validation.run_validation", return_value=([], {})
    ), patch(
        "src.cli.commands.recipes.run_recipes_job",
        side_effect=ValueError(error_message),
    ):
        response, status_code = handlers.handle_api_recipes_surveys(
            {
                "dataset_path": str(dataset_path),
                "recipe_dir": str(recipe_dir),
                "modality": "survey",
                "format": "sav",
            }
        )

    assert status_code == 400
    payload = response.get_json()
    assert payload["error"] == error_message
    assert "traceback" not in payload["error"].lower()


def test_handle_api_recipes_surveys_forwards_recipe_prefix_flag(
    tmp_path: Path,
) -> None:
    handlers = _import_handlers_module()
    app = _build_app()

    dataset_path = tmp_path / "dataset"
    dataset_path.mkdir()
    out_root = dataset_path / "derivatives" / "survey" / "wide_en"

    result = SurveyRecipesResult(
        processed_files=1,
        written_files=1,
        out_format="csv",
        out_root=out_root,
        flat_out_path=out_root / "combined_survey.csv",
    )

    with app.app_context(), patch(
        "src.web.validation.run_validation", return_value=([], {})
    ), patch(
        "src.cli.commands.recipes.run_recipes_job", return_value=result
    ) as run_job:
        response = handlers.handle_api_recipes_surveys(
            {
                "dataset_path": str(dataset_path),
                "modality": "survey",
                "format": "csv",
                "merge_all": True,
                "include_recipe_prefix": False,
            }
        )

    assert response.status_code == 200
    assert run_job.call_args.kwargs["include_recipe_prefix"] is False


def test_handle_api_recipes_surveys_emits_cmd_prefix_for_backend_styling(
    tmp_path: Path,
) -> None:
    handlers = _import_handlers_module()
    app = _build_app()

    dataset_path = tmp_path / "dataset"
    dataset_path.mkdir()
    out_root = dataset_path / "derivatives" / "survey" / "wide_en"

    result = SurveyRecipesResult(
        processed_files=1,
        written_files=1,
        out_format="csv",
        out_root=out_root,
        flat_out_path=out_root / "combined_survey.csv",
    )

    with app.app_context(), patch(
        "src.web.validation.run_validation", return_value=([], {})
    ), patch(
        "src.cli.commands.recipes.run_recipes_job", return_value=result
    ), patch(
        "src.web.blueprints.tools_recipes_surveys_handlers.emit_backend_action"
    ) as emit_action:
        response = handlers.handle_api_recipes_surveys(
            {
                "dataset_path": str(dataset_path),
                "modality": "survey",
                "format": "csv",
                "merge_all": True,
            }
        )

    assert response.status_code == 200
    assert emit_action.call_count >= 1
    first_message = str(emit_action.call_args_list[0].args[0])
    assert "cmd=python prism_tools.py recipes survey" in first_message


def test_handle_api_recipes_surveys_rejects_invalid_missing_policy(
    tmp_path: Path,
) -> None:
    handlers = _import_handlers_module()
    app = _build_app()

    dataset_path = tmp_path / "dataset"
    dataset_path.mkdir()

    with app.app_context(), patch(
        "src.web.validation.run_validation", return_value=([], {})
    ):
        response, status_code = handlers.handle_api_recipes_surveys(
            {
                "dataset_path": str(dataset_path),
                "modality": "survey",
                "format": "csv",
                "missing_policy": "bad-policy",
            }
        )

    assert status_code == 400
    payload = response.get_json()
    assert "missing_policy" in payload["error"]


def test_handle_api_recipes_surveys_rejects_missing_numeric_without_sentinel_policy(
    tmp_path: Path,
) -> None:
    handlers = _import_handlers_module()
    app = _build_app()

    dataset_path = tmp_path / "dataset"
    dataset_path.mkdir()

    with app.app_context(), patch(
        "src.web.validation.run_validation", return_value=([], {})
    ):
        response, status_code = handlers.handle_api_recipes_surveys(
            {
                "dataset_path": str(dataset_path),
                "modality": "survey",
                "format": "csv",
                "missing_policy": "numeric-sentinel",
            }
        )

    assert status_code == 400
    payload = response.get_json()
    assert "missing_numeric_value is required" in payload["error"]


def test_handle_api_recipes_surveys_forwards_missing_policy_fields(
    tmp_path: Path,
) -> None:
    handlers = _import_handlers_module()
    app = _build_app()

    dataset_path = tmp_path / "dataset"
    dataset_path.mkdir()
    out_root = dataset_path / "derivatives" / "survey" / "wide_en"

    result = SurveyRecipesResult(
        processed_files=1,
        written_files=1,
        out_format="csv",
        out_root=out_root,
        flat_out_path=out_root / "combined_survey.csv",
    )

    with app.app_context(), patch(
        "src.web.validation.run_validation", return_value=([], {})
    ), patch(
        "src.cli.commands.recipes.run_recipes_job", return_value=result
    ) as run_job:
        response = handlers.handle_api_recipes_surveys(
            {
                "dataset_path": str(dataset_path),
                "modality": "survey",
                "format": "csv",
                "missing_policy": "numeric-sentinel",
                "missing_numeric_value": -99,
            }
        )

    assert response.status_code == 200
    assert run_job.call_args.kwargs["missing_policy"] == "numeric-sentinel"
    assert run_job.call_args.kwargs["missing_numeric_value"] == -99.0


def test_handle_api_recipes_surveys_accepts_text_nan_missing_policy(
    tmp_path: Path,
) -> None:
    handlers = _import_handlers_module()
    app = _build_app()

    dataset_path = tmp_path / "dataset"
    dataset_path.mkdir()
    out_root = dataset_path / "derivatives" / "survey" / "long_en"

    result = SurveyRecipesResult(
        processed_files=1,
        written_files=1,
        out_format="csv",
        out_root=out_root,
        flat_out_path=out_root / "combined_survey.csv",
    )

    with app.app_context(), patch(
        "src.web.validation.run_validation", return_value=([], {})
    ), patch(
        "src.cli.commands.recipes.run_recipes_job", return_value=result
    ) as run_job:
        response = handlers.handle_api_recipes_surveys(
            {
                "dataset_path": str(dataset_path),
                "modality": "survey",
                "format": "csv",
                "missing_policy": "text-nan",
            }
        )

    assert response.status_code == 200
    assert run_job.call_args.kwargs["missing_policy"] == "text-nan"
    assert run_job.call_args.kwargs["missing_numeric_value"] is None


def test_handle_api_recipes_surveys_logs_absolute_formatted_backend_command(
    tmp_path: Path,
) -> None:
    handlers = _import_handlers_module()
    app = _build_app()

    dataset_path = tmp_path / "dataset"
    dataset_path.mkdir()
    out_root = dataset_path / "derivatives" / "survey" / "long_en"

    result = SurveyRecipesResult(
        processed_files=1,
        written_files=1,
        out_format="sav",
        out_root=out_root,
        flat_out_path=out_root / "combined_survey.sav",
    )

    with app.app_context(), patch(
        "src.web.validation.run_validation", return_value=([], {})
    ), patch(
        "src.web.blueprints.tools_recipes_surveys_handlers.emit_backend_action"
    ) as emit_action, patch(
        "src.cli.commands.recipes.run_recipes_job", return_value=result
    ):
        response = handlers.handle_api_recipes_surveys(
            {
                "dataset_path": str(dataset_path),
                "modality": "survey",
                "format": "sav",
            }
        )

    assert response.status_code == 200
    logged_message = emit_action.call_args.args[0]
    assert f'--prism "{dataset_path.resolve().as_posix()}"' in logged_message
    assert '--repo "' in logged_message
    assert "--format sav" in logged_message
    assert "--layout" not in logged_message
    assert "--lang" not in logged_message
