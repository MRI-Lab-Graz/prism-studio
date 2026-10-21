"""processing_summary: scoring recipes and software versions of a project."""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "app"))

from src.methods_processing import processing_summary  # noqa: E402


def _recipe(root, name, task, scores):
    d = root / "code" / "recipes" / "survey"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"recipe-{name}.json").write_text(
        json.dumps({"Survey": {"TaskName": task}, "Scores": [{"Name": s} for s in scores]}),
        encoding="utf-8",
    )


def test_recipes_listed_with_scores(tmp_path):
    _recipe(tmp_path, "dass21", "dass21", ["Depression", "Anxiety"])
    s = processing_summary(tmp_path)
    assert s["recipes"] == [{"task": "dass21", "scores": ["Depression", "Anxiety"]}]
    assert s["software"]["prism_version"]


def test_no_recipes(tmp_path):
    assert processing_summary(tmp_path)["recipes"] == []


def test_schema_pins_surface(tmp_path):
    (tmp_path / "project.json").write_text(
        json.dumps({"SchemaVersions": {"survey": "1.2.0"}}), encoding="utf-8"
    )
    assert processing_summary(tmp_path)["software"]["modality_schemas"] == {"survey": "1.2.0"}


def test_unreadable_recipe_is_skipped(tmp_path):
    d = tmp_path / "code" / "recipes" / "survey"
    d.mkdir(parents=True)
    (d / "recipe-bad.json").write_text("{", encoding="utf-8")
    assert processing_summary(tmp_path)["recipes"] == []
