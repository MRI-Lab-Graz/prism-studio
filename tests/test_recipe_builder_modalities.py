"""The Recipe Builder lists only the project's modalities: `recipes modalities` and the Studio route give the same list."""

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from flask import Flask  # noqa: E402

from src import recipe_builder as rb  # noqa: E402

SURVEY = {"value": "survey", "label": "Survey"}
BIOMETRICS = {"value": "biometrics", "label": "Biometrics"}


def _tsv(root, modality):
    folder = root / "sub-01" / "ses-1" / modality
    folder.mkdir(parents=True)
    (folder / f"sub-01_ses-1_task-x_{modality}.tsv").write_text("a\n1\n", encoding="utf-8")


def _template(root, modality):
    folder = root / "code" / "library" / modality
    folder.mkdir(parents=True)
    (folder / f"{modality}-x.json").write_text(json.dumps({"Technical": {}, "Study": {}}), encoding="utf-8")


@pytest.fixture(params=["survey_data", "biometrics_template", "both", "neither"])
def case(request, tmp_path):
    root = tmp_path / "study"
    root.mkdir()
    if request.param == "survey_data":
        _tsv(root, "survey")
        return root, [SURVEY]
    if request.param == "biometrics_template":
        _template(root, "biometrics")
        return root, [BIOMETRICS]
    if request.param == "both":
        _tsv(root, "beh")
        _template(root, "biometrics")
        return root, [SURVEY, BIOMETRICS]
    return root, []


def test_modalities_come_from_data_or_templates(case):
    root, expected = case
    assert rb.list_builder_modalities(root) == expected


def test_cli_and_studio_list_the_same_modalities(case, capsys):
    import src.cli.commands.recipes as commands

    root, expected = case
    commands.cmd_recipes_modalities(SimpleNamespace(project=str(root), json=True))
    cli = json.loads(capsys.readouterr().out)
    handlers = importlib.import_module("src.web.blueprints.tools")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.register_blueprint(handlers.tools_bp)
    studio = app.test_client().get("/api/recipe-builder/modalities", query_string={"dataset_path": str(root)}).get_json()
    assert cli == studio == {"modalities": expected}


def test_the_page_has_no_hard_coded_modality_options():
    html = (Path(__file__).resolve().parents[1] / "app" / "templates" / "recipe_builder.html").read_text(encoding="utf-8")
    assert '<option value="survey" selected>' not in html and '<option value="biometrics">' not in html


def test_a_new_supported_modality_gets_a_label_and_data_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(rb, "_SUPPORTED_MODALITIES", ("survey", "eyetrack"))
    _tsv(tmp_path, "eyetrack")
    assert rb.list_builder_modalities(tmp_path) == [{"value": "eyetrack", "label": "Eyetrack"}]


def test_the_run_page_detector_uses_the_same_labels():
    handlers = importlib.import_module("src.web.blueprints.tools_pages_handlers")
    assert "modality_labels" not in Path(handlers.__file__).read_text(encoding="utf-8")


def test_cli_and_studio_offer_the_same_modalities_to_run(tmp_path, capsys):
    """The Recipes page: modalities with data and recipes. THE RULE: `recipes modalities --for-run` decides."""
    import src.cli.commands.recipes as commands
    from src.cli.parser import build_prism_tools_parsers

    _tsv(tmp_path, "biometrics")
    (tmp_path / "code" / "recipes" / "biometrics").mkdir(parents=True)
    (tmp_path / "code" / "recipes" / "biometrics" / "recipe-x.json").write_text("{}", encoding="utf-8")
    parser, _ = build_prism_tools_parsers(Path(__file__).resolve().parents[1])
    args = parser.parse_args(["recipes", "modalities", "--project", str(tmp_path), "--for-run"])
    commands.cmd_recipes_modalities(args)
    cli = json.loads(capsys.readouterr().out)

    handlers = importlib.import_module("src.web.blueprints.tools_pages_handlers")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    with app.app_context():
        response, status = handlers.handle_api_recipes_modalities(str(tmp_path))
    assert status == 200
    assert cli == response.get_json()
    assert cli["default"] in [m["value"] for m in cli["modalities"]]
    assert "biometrics" in [m["value"] for m in cli["modalities"]]
