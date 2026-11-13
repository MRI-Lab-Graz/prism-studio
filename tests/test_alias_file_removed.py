"""The --alias file is gone: the project item map (code/item_maps) is the only item-name mapping."""

import inspect
import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src.cli.parser import build_prism_tools_parsers  # noqa: E402
from src.converters import survey as survey_module  # noqa: E402
from src.converters import survey_core  # noqa: E402
from src.survey_workflow_service import SurveyWorkflowStageOptions  # noqa: E402
from src.web.blueprints import (  # noqa: E402
    conversion_survey_convert_handlers as convert_h,
    conversion_survey_convert_validate_handlers as validate_h,
    conversion_survey_preview_handlers as preview_h,
)

GONE = "The alias file is gone; use the project item map (survey item-map)"


def test_survey_convert_rejects_the_alias_flag(capsys):
    _root, parsers = build_prism_tools_parsers(Path(__file__).resolve().parents[1] / "app")
    with pytest.raises(SystemExit):
        parsers["survey"].parse_args(["convert", "--input", "x.csv", "--output", "o", "--alias", "x.tsv"])
    assert "unrecognized arguments" in capsys.readouterr().err


def test_no_converter_function_takes_alias_file():
    for fn in (survey_module.convert_survey_lsa_to_prism_dataset, survey_module.convert_survey_file_to_prism_dataset,
               survey_core._load_survey_aliases_and_templates):
        assert "alias_file" not in inspect.signature(fn).parameters, fn.__name__
    assert "alias_file" not in {f.name for f in __import__("dataclasses").fields(SurveyWorkflowStageOptions)}
    for gone in ("_read_alias_rows", "_build_alias_map", "_build_canonical_aliases", "_apply_alias_file_to_dataframe", "_canonicalize_template_items"):
        assert not hasattr(survey_core, gone)


def _call(handler, field, **extra):
    kwargs = {name: MagicMock() for name, p in inspect.signature(handler).parameters.items()
              if p.default is inspect.Parameter.empty}
    app = Flask(__name__)
    with app.test_request_context("/x", method="POST", content_type="multipart/form-data",
                                  data={field: (io.BytesIO(b"A\tB\n"), "alias.tsv")}):
        response = handler(**kwargs)
    return response


@pytest.mark.parametrize("handler", [convert_h.handle_api_survey_convert, preview_h.handle_api_survey_convert_preview,
                                     validate_h.handle_api_survey_convert_validate,
                                     validate_h.handle_api_survey_convert_validate_start])
@pytest.mark.parametrize("field", ["alias", "alias_file"])
def test_routes_answer_400_for_an_alias_upload(handler, field):
    response, status = _call(handler, field)
    assert status == 400
    assert response.get_json()["error"] == GONE


def test_a_template_with_aliases_still_matches_its_aliased_columns(tmp_path):
    from tests.template_fixtures import dump_complete

    template = {"ads_01": {"Description": {"en": "x"}, "Levels": {"1": "a"}, "Aliases": ["ADS1_1"]}}
    (tmp_path / "survey-ads.json").write_text(dump_complete(template, "ads"), encoding="utf-8")
    templates, _items, _dups, _warn = survey_module._load_and_preprocess_templates(tmp_path, compare_with_global=False)
    assert templates["ads"]["json"]["_aliases"] == {"ADS1_1": "ads_01"}
    assert templates["ads"]["json"]["_reverse_aliases"] == {"ads_01": ["ADS1_1"]}
