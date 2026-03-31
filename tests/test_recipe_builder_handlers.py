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

    handlers = importlib.import_module("src.web.blueprints.tools_recipe_builder_handlers")
    app = Flask(__name__, root_path=str(app_root))
    return app, handlers


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
                        "MinValue": 0,
                        "MaxValue": 3,
                    },
                    "ADS02": {
                        "Description": "I had trouble sleeping.",
                        "MinValue": 0,
                        "MaxValue": 3,
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
    assert data["items"] == ["ADS01", "ADS02"]
    assert data["item_descriptions"] == {
        "ADS01": "I felt sad.",
        "ADS02": "I had trouble sleeping.",
    }
