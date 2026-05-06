from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

from flask import Flask


def _import_tools_pages_module():
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))
    return importlib.import_module("src.web.blueprints.tools_pages_handlers")


def _build_app() -> Flask:
    app_root = Path(__file__).resolve().parents[1] / "app"
    return Flask(__name__, root_path=str(app_root))


def test_detect_available_recipe_modalities_requires_prefixed_recipe_files(
    tmp_path: Path,
) -> None:
    handlers = _import_tools_pages_module()
    app = _build_app()

    project_root = tmp_path / "project"
    (project_root / "sub-01" / "survey").mkdir(parents=True)
    (project_root / "sub-01" / "survey" / "task-ads.tsv").write_text(
        "participant_id\tscore\nsub-01\t1\n",
        encoding="utf-8",
    )
    (project_root / "sub-01" / "biometrics").mkdir(parents=True)
    (project_root / "sub-01" / "biometrics" / "hrv.tsv").write_text(
        "participant_id\tvalue\nsub-01\t1\n",
        encoding="utf-8",
    )

    survey_recipe_dir = project_root / "code" / "recipes" / "survey"
    survey_recipe_dir.mkdir(parents=True)
    (survey_recipe_dir / "ads.json").write_text("{}", encoding="utf-8")

    biometrics_recipe_dir = project_root / "code" / "recipes" / "biometrics"
    biometrics_recipe_dir.mkdir(parents=True)
    (biometrics_recipe_dir / "recipe-hrv.json").write_text("{}", encoding="utf-8")

    with app.app_context(), patch.object(handlers, "_global_recipes_root", return_value=None):
        available, default_modality = handlers._detect_available_recipe_modalities(
            project_root
        )

    assert available == [{"value": "biometrics", "label": "Biometrics"}]
    assert default_modality == "biometrics"