"""A new recipe is pre-filled from the survey template's own Study block."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

from flask import Flask

from src.recipe_builder import extract_template_study_metadata


def _write(tmp_path: Path, payload: dict, name: str = "t.json") -> str:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_survey_template_supplies_name_citation_and_doi(tmp_path):
    path = _write(
        tmp_path,
        {
            "Study": {
                "TaskName": "who5",
                "OriginalName": {"de": "Der WHO-5", "en": "The WHO-5 Well-Being Index"},
                "Citation": "Topp et al. (2015)",
                "DOI": "10.1159/000376585",
            }
        },
    )

    assert extract_template_study_metadata(path, modality="survey") == {
        "name": "The WHO-5 Well-Being Index",
        "description": "",
        "citation": "Topp et al. (2015)",
        "doi": "10.1159/000376585",
    }


def test_a_plain_string_name_is_used_as_is(tmp_path):
    path = _write(tmp_path, {"Study": {"OriginalName": " Wellbeing "}})

    assert extract_template_study_metadata(path, modality="survey")["name"] == "Wellbeing"


def test_a_name_without_english_falls_back_to_another_language(tmp_path):
    path = _write(tmp_path, {"Study": {"OriginalName": {"de": "Nur Deutsch"}}})

    assert extract_template_study_metadata(path, modality="survey")["name"] == "Nur Deutsch"


def test_biometrics_template_supplies_name_and_description(tmp_path):
    path = _write(
        tmp_path,
        {"Study": {"OriginalName": "Fitness battery", "Description": "Resting HR and grip."}},
    )

    result = extract_template_study_metadata(path, modality="biometrics")

    assert result["name"] == "Fitness battery"
    assert result["description"] == "Resting HR and grip."
    assert result["citation"] == "" and result["doi"] == ""


def test_a_template_without_study_metadata_gives_empty_fields(tmp_path):
    path = _write(tmp_path, {"Q1": {"Description": "x"}})
    empty = {"name": "", "description": "", "citation": "", "doi": ""}

    assert extract_template_study_metadata(path, modality="survey") == empty
    assert extract_template_study_metadata(str(tmp_path / "missing.json"), modality="survey") == empty


def test_items_endpoint_returns_the_template_metadata(tmp_path):
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))
    handlers = importlib.import_module("src.web.blueprints.tools_recipe_builder_handlers")

    library = tmp_path / "code" / "library" / "survey"
    library.mkdir(parents=True)
    (library / "survey-wb.json").write_text(
        json.dumps(
            {
                "Study": {"TaskName": "wb", "OriginalName": {"en": "Wellbeing"}, "Citation": "Cite"},
                "WB01": {"Description": "Item", "MinValue": 0, "MaxValue": 5},
            }
        ),
        encoding="utf-8",
    )

    with Flask(__name__, root_path=str(app_root)).test_request_context("/x"):
        response, status = handlers.handle_api_recipe_builder_items(str(tmp_path), "wb")

    assert status == 200
    assert response.get_json()["template_metadata"] == {
        "name": "Wellbeing",
        "description": "",
        "citation": "Cite",
        "doi": "",
    }
