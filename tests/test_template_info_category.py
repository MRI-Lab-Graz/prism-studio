from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


def _import_extract_template_info():
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))
    module = importlib.import_module("src.web.blueprints.tools_template_info_helpers")
    return module.extract_template_info


def test_extract_template_info_passes_through_study_category(tmp_path):
    extract_template_info = _import_extract_template_info()

    template_path = tmp_path / "survey-demo.json"
    template_path.write_text(
        json.dumps(
            {
                "Study": {
                    "OriginalName": "Demo Instrument",
                    "Category": "Well-being & Life Satisfaction",
                }
            }
        ),
        encoding="utf-8",
    )

    info = extract_template_info(str(template_path), template_path.name)

    assert info["study"]["Category"] == "Well-being & Life Satisfaction"


def test_extract_template_info_defaults_category_to_empty_string(tmp_path):
    extract_template_info = _import_extract_template_info()

    template_path = tmp_path / "survey-demo.json"
    template_path.write_text(
        json.dumps({"Study": {"OriginalName": "Demo Instrument"}}),
        encoding="utf-8",
    )

    info = extract_template_info(str(template_path), template_path.name)

    assert info["study"]["Category"] == ""
