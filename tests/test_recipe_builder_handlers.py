from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

from flask import Flask


def _build_app_and_handlers():
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))

    handlers = importlib.import_module(
        "src.web.blueprints.tools_recipe_builder_handlers"
    )
    app = Flask(__name__, root_path=str(app_root))
    return app, handlers


def _import_recipe_modules():
    app_root = Path(__file__).resolve().parents[1] / "app"
    src_root = app_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

    recipe_validation = importlib.import_module("recipe_validation")
    recipes_surveys = importlib.import_module("recipes_surveys")
    return recipe_validation, recipes_surveys


def _write_recipe_builder_template(dataset_path: Path, task_name: str) -> Path:
    library_dir = dataset_path / "code" / "library" / "survey"
    library_dir.mkdir(parents=True, exist_ok=True)
    template_path = library_dir / f"survey-{task_name}.json"
    template_path.write_text(
        json.dumps({"Study": {"TaskName": task_name}}),
        encoding="utf-8",
    )
    return template_path


def test_recipe_builder_items_include_item_descriptions(tmp_path):
    app, handlers = _build_app_and_handlers()

    library_dir = tmp_path / "code" / "library" / "survey"
    library_dir.mkdir(parents=True)
    template_path = library_dir / "survey-ads.json"
    template_path.write_text(
        json.dumps(
            {
                "Technical": {"Language": "en"},
                "Study": {"Name": "ADS"},
                "Questions": {
                    "ADS01": {
                        "Description": {
                            "en": "I felt sad.",
                            "de": "Ich war traurig.",
                        },
                        "Reversed": True,
                        "MinValue": 0,
                        "MaxValue": 3,
                    },
                    "ADS02": {
                        "Description": "I had trouble sleeping.",
                        "Levels": {
                            "0": {"en": "Never"},
                            "1": {"en": "Sometimes"},
                            "2": {"en": "Often"},
                            "3": {"en": "Always"},
                        },
                    },
                    "ADS04": {
                        "Description": "Range is missing.",
                    },
                    "ADS03": {
                        "Description": "Excluded item.",
                        "_exclude": True,
                        "MinValue": 0,
                        "MaxValue": 3,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    with app.test_request_context("/api/recipe-builder/items"):
        response, status_code = handlers.handle_api_recipe_builder_items(
            str(tmp_path), "ads"
        )

    assert status_code == 200
    data = response.get_json()
    assert data["items"] == ["ADS01", "ADS02", "ADS04"]
    assert data["item_descriptions"] == {
        "ADS01": "I felt sad.",
        "ADS02": "I had trouble sleeping.",
        "ADS04": "Range is missing.",
    }
    assert data["item_descriptions_i18n"] == {
        "ADS01": {
            "en": "I felt sad.",
            "de": "Ich war traurig.",
        },
        "ADS02": {
            "default": "I had trouble sleeping.",
        },
        "ADS04": {
            "default": "Range is missing.",
        },
    }
    assert data["item_description_languages"] == ["de", "en"]
    assert data["template_language"] == "en"
    assert data["template_reversed_items"] == ["ADS01"]
    assert data["items_missing_ranges"] == ["ADS04"]


def test_recipe_builder_save_rejects_invalid_recipe_method(tmp_path):
    app, handlers = _build_app_and_handlers()
    _write_recipe_builder_template(tmp_path, "ads")

    recipe = {
        "RecipeVersion": "1.0",
        "Kind": "survey",
        "Survey": {"TaskName": "ads"},
        "Scores": [
            {
                "Name": "ads_total",
                "Method": "median",
                "Items": ["ADS01", "ADS02"],
            }
        ],
    }

    with app.test_request_context("/api/recipe-builder/save"):
        response, status_code = handlers.handle_api_recipe_builder_save(
            {"dataset_path": str(tmp_path), "recipe": recipe}
        )

    assert status_code == 400
    data = response.get_json()
    assert data["error"] == "Recipe validation failed"
    assert any("Method must be one of" in err for err in data["validation_errors"])
    assert not (tmp_path / "code" / "recipes" / "survey" / "recipe-ads.json").exists()


def test_recipe_builder_save_accepts_versioned_scores_without_top_level_scores(
    tmp_path,
):
    app, handlers = _build_app_and_handlers()
    _write_recipe_builder_template(tmp_path, "ads")

    recipe = {
        "RecipeVersion": "1.0",
        "Kind": "survey",
        "Survey": {"TaskName": "ads"},
        "VersionedScores": {
            "vas": [
                {
                    "Name": "ads_total_vas",
                    "Method": "mean",
                    "Items": ["ADS01", "ADS02"],
                }
            ]
        },
    }

    with app.test_request_context("/api/recipe-builder/save"):
        response, status_code = handlers.handle_api_recipe_builder_save(
            {"dataset_path": str(tmp_path), "recipe": recipe}
        )

    assert status_code == 200
    data = response.get_json()
    assert data["saved"] is True

    saved_path = tmp_path / "code" / "recipes" / "survey" / "recipe-ads.json"
    assert saved_path.exists()
    assert json.loads(saved_path.read_text(encoding="utf-8")) == recipe


def test_recipe_builder_save_ignores_legacy_root_recipe_folder(tmp_path):
    app, handlers = _build_app_and_handlers()
    _write_recipe_builder_template(tmp_path, "ads")

    legacy_path = tmp_path / "recipe" / "survey" / "recipe-ads.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text('{"location": "legacy-root"}', encoding="utf-8")

    recipe = {
        "RecipeVersion": "1.0",
        "Kind": "survey",
        "Survey": {"TaskName": "ads"},
        "Scores": [
            {
                "Name": "ads_total",
                "Method": "mean",
                "Items": ["ADS01", "ADS02"],
            }
        ],
    }

    with app.test_request_context("/api/recipe-builder/save"):
        response, status_code = handlers.handle_api_recipe_builder_save(
            {"dataset_path": str(tmp_path), "recipe": recipe}
        )

    assert status_code == 200
    data = response.get_json()
    assert data["saved"] is True

    saved_path = tmp_path / "code" / "recipes" / "survey" / "recipe-ads.json"
    assert saved_path.exists()
    assert json.loads(saved_path.read_text(encoding="utf-8")) == recipe
    assert json.loads(legacy_path.read_text(encoding="utf-8")) == {
        "location": "legacy-root"
    }


def test_recipe_builder_save_rejects_task_missing_from_target_dataset(tmp_path):
    app, handlers = _build_app_and_handlers()

    recipe = {
        "RecipeVersion": "1.0",
        "Kind": "survey",
        "Survey": {"TaskName": "missing-task-zz9"},
        "Scores": [
            {
                "Name": "missing_task_total",
                "Method": "mean",
                "Items": ["ADS01", "ADS02"],
            }
        ],
    }

    with app.test_request_context("/api/recipe-builder/save"):
        response, status_code = handlers.handle_api_recipe_builder_save(
            {"dataset_path": str(tmp_path), "recipe": recipe}
        )

    assert status_code == 400
    data = response.get_json()
    assert data["error"] == "Survey template not found in the target project or official library"
    assert not (tmp_path / "code" / "recipes" / "survey" / "recipe-missing-task-zz9.json").exists()


def test_validate_recipe_accepts_versioned_scores_without_top_level_scores():
    recipe_validation, _ = _import_recipe_modules()

    recipe = {
        "RecipeVersion": "1.0",
        "Kind": "survey",
        "Survey": {"TaskName": "ads"},
        "VersionedScores": {
            "vas": [
                {
                    "Name": "ads_total_vas",
                    "Method": "mean",
                    "Items": ["ADS01", "ADS02"],
                }
            ]
        },
    }

    assert recipe_validation.validate_recipe(recipe) == []


def test_unknown_score_method_does_not_fall_back_to_sum():
    _, recipes_surveys = _import_recipe_modules()

    recipe = {
        "RecipeVersion": "1.0",
        "Kind": "survey",
        "Survey": {"TaskName": "ads"},
        "Scores": [
            {
                "Name": "ads_total",
                "Method": "median",
                "Items": ["ADS01", "ADS02", "ADS03"],
            }
        ],
    }

    header, out_rows = recipes_surveys._apply_survey_derivative_recipe_to_rows(
        recipe,
        [{"ADS01": "1", "ADS02": "2", "ADS03": "3"}],
    )

    assert header == ["ads_total"]
    assert out_rows == [{"ads_total": "n/a"}]


def test_min_valid_threshold_outputs_na_when_not_enough_items():
    _, recipes_surveys = _import_recipe_modules()

    recipe = {
        "RecipeVersion": "1.0",
        "Kind": "survey",
        "Survey": {"TaskName": "ads"},
        "Scores": [
            {
                "Name": "ads_total",
                "Method": "sum",
                "Items": ["ADS01", "ADS02", "ADS03", "ADS04"],
                "MinValid": 3,
            }
        ],
    }

    header, out_rows = recipes_surveys._apply_survey_derivative_recipe_to_rows(
        recipe,
        [{"ADS01": "1", "ADS02": "2", "ADS03": "n/a", "ADS04": ""}],
    )

    assert header == ["ads_total"]
    assert out_rows == [{"ads_total": "n/a"}]


def test_min_valid_threshold_computes_when_enough_items():
    _, recipes_surveys = _import_recipe_modules()

    recipe = {
        "RecipeVersion": "1.0",
        "Kind": "survey",
        "Survey": {"TaskName": "ads"},
        "Scores": [
            {
                "Name": "ads_mean",
                "Method": "mean",
                "Items": ["ADS01", "ADS02", "ADS03", "ADS04"],
                "MinValid": 2,
            }
        ],
    }

    header, out_rows = recipes_surveys._apply_survey_derivative_recipe_to_rows(
        recipe,
        [{"ADS01": "1", "ADS02": "3", "ADS03": "n/a", "ADS04": ""}],
    )

    assert header == ["ads_mean"]
    assert out_rows == [{"ads_mean": "2"}]


def test_validate_recipe_rejects_invalid_min_valid():
    recipe_validation, _ = _import_recipe_modules()

    recipe = {
        "RecipeVersion": "1.0",
        "Kind": "survey",
        "Survey": {"TaskName": "ads"},
        "Scores": [
            {
                "Name": "ads_total",
                "Method": "sum",
                "Items": ["ADS01", "ADS02"],
                "MinValid": 3,
            }
        ],
    }

    errors = recipe_validation.validate_recipe(recipe)
    assert any("MinValid" in err for err in errors)


def test_recipe_builder_detects_ranges_from_contiguous_numeric_levels(tmp_path):
    app, handlers = _build_app_and_handlers()

    template_path = tmp_path / "survey-bfi.json"
    template_path.write_text(
        json.dumps(
            {
                "Study": {"Name": "BFI"},
                "BFI01": {
                    "Levels": {
                        "0": {"en": "Strongly disagree"},
                        "1": {"en": "Disagree"},
                        "2": {"en": "Neither"},
                        "3": {"en": "Agree"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    with app.app_context():
        assert handlers._detect_scale_ranges(str(template_path)) == {
            "": {"min": 0, "max": 3}
        }
        assert handlers._extract_item_ranges_from_template(str(template_path)) == {
            "BFI01": {"": {"min": 0, "max": 3}}
        }
