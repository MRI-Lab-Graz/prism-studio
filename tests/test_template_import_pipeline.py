"""The step every template source (Excel, LimeSurvey, Pavlovia) goes through after building a template:
library match, optional adoption of the library template, and the payload the Template Editor reads."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from flask import Flask

from src.converters import survey_templates as st
from src.converters.template_import import finish_import
from test_library_wording_match import library_file

FIXTURE_LSS = Path(__file__).parent / "data" / "limesurvey_four_questionnaires.lss"
FIXTURE_PAVLOVIA = Path(__file__).parent / "data" / "pavlovia_survey.json"
ADS = ["war ich bedrückt", "war ich müde"]
ADS_LEVELS = {"0": "selten", "1": "meistens"}


def _template(task="ads", texts=ADS, **extra):
    template = {
        "Technical": {"StimulusType": "Questionnaire", "Language": "de"},
        "Study": {"TaskName": task},
        "Metadata": {"SchemaVersion": "1.1.1"},
    }
    for i, text in enumerate(texts, 1):
        template[f"ADS1_{i}"] = {"Description": {"de": text}, "Levels": {k: {"de": v} for k, v in ADS_LEVELS.items()}}
    template.update(extra)
    return template


@pytest.fixture
def no_library(tmp_path, monkeypatch):
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    monkeypatch.setattr(st, "_load_global_library_path", lambda: global_dir)
    return global_dir


@pytest.fixture
def library(tmp_path, monkeypatch):
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    project = tmp_path / "project"
    (project / "code" / "library" / "survey").mkdir(parents=True)
    monkeypatch.setattr(st, "_load_global_library_path", lambda: global_dir)
    library_file(project / "code" / "library" / "survey", texts=ADS, levels=ADS_LEVELS)
    return str(project)


def test_payload_has_what_the_editor_reads(no_library):
    payload = finish_import(_template(), "ADS")

    assert set(payload) == {"template", "suggested_filename", "item_count", "languages", "library_match"}
    assert payload["suggested_filename"] == "survey-ads.json"
    assert payload["item_count"] == 2
    assert payload["languages"] == ["de"]
    assert payload["library_match"] is None


def test_a_template_without_a_language_reports_none(no_library):
    template = _template()
    template["Technical"]["Language"] = ""

    assert finish_import(template, "ADS")["languages"] == []


def test_languages_come_from_i18n_when_it_lists_several(no_library):
    template = _template(I18n={"Languages": ["de", "en"], "DefaultLanguage": "de"})

    assert finish_import(template, "ADS")["languages"] == ["de", "en"]


def test_item_count_ignores_the_sections_around_the_items(no_library):
    template = _template(LimeSurvey={"x": 1}, Scoring={}, Normative={}, I18n={"Languages": ["de"]})

    assert finish_import(template, "ADS")["item_count"] == 2


def test_editor_internal_keys_are_stripped(no_library):
    template = _template(_aliases={"a": "b"}, _reverse_aliases={"b": "a"})

    assert not {"_aliases", "_reverse_aliases"} & set(finish_import(template, "ADS")["template"])


def test_a_matching_library_template_is_reported_without_its_local_path(library):
    payload = finish_import(_template(), "ADS", project_path=library)

    assert payload["library_match"]["confidence"] == "exact"
    assert "template_path" not in payload["library_match"] and library not in json.dumps(payload["library_match"])
    assert "ADS1_1" in payload["template"]  # imported as is unless the user asks for the library version


def test_use_library_returns_the_library_template_under_its_own_file_name(library):
    payload = finish_import(_template(), "ADS", project_path=library, use_library=True)

    assert payload["template"]["ads_01"]["Aliases"] == ["ADS1_1"]
    assert payload["suggested_filename"] == "survey-ads.json"
    assert payload["item_count"] == 2


def test_use_library_without_a_one_to_one_match_is_a_value_error(no_library):
    with pytest.raises(ValueError):
        finish_import(_template(), "ADS", use_library=True)


# --- every source reports the same payload -----------------------------------------------------------


def _client():
    import importlib

    module = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    app.register_blueprint(module.tools_template_editor_bp)
    return app.test_client()


def _xlsx():
    rows = [["Variable name", "Description_de", "Scaling"],
            ["ads1_1", ADS[0], "0=selten;1=meistens"], ["ads1_2", ADS[1], "0=selten;1=meistens"]]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, index=False, header=False)
    return buf.getvalue()


def _post(path, content, name, data):
    form = {"file": (io.BytesIO(content), name), **data}
    return _client().post(f"/api/template-editor/{path}", data=form, content_type="multipart/form-data")


def test_every_source_returns_the_same_payload_keys(no_library):
    lss = _post("import-limesurvey", FIXTURE_LSS.read_bytes(), "s.lss", {"split": "group", "key": "g30"})
    pavlovia = _post("import-pavlovia", FIXTURE_PAVLOVIA.read_bytes(), "s.json", {"key": "p2"})
    excel = _post("import-excel", _xlsx(), "c.xlsx", {"group": "ads"})

    assert [r.status_code for r in (lss, pavlovia, excel)] == [200, 200, 200]
    keys = [set(r.get_json()) for r in (lss, pavlovia, excel)]
    assert keys[0] == keys[1] == keys[2] == {"template", "suggested_filename", "item_count", "languages", "library_match"}


def test_an_excel_import_without_a_library_match_reports_null_so_the_editor_offers_to_share(no_library):
    body = _post("import-excel", _xlsx(), "c.xlsx", {"group": "ads"}).get_json()

    assert "library_match" in body and body["library_match"] is None


def test_an_excel_import_finds_the_matching_library_template(library):
    body = _post("import-excel", _xlsx(), "c.xlsx", {"group": "ads", "project_path": library}).get_json()

    assert body["library_match"]["confidence"] == "exact"


# --- CLI: survey import-codebook ---------------------------------------------------------------------

from src.cli.commands.survey import cmd_survey_import_codebook  # noqa: E402


def _args(tmp_path, **kw):
    path = tmp_path / "codebook.xlsx"
    path.write_bytes(_xlsx())
    values = dict(input=str(path), list=False, select=None, output=None, project=None)
    values.update(kw)
    return SimpleNamespace(**values)


def test_codebook_cli_lists_groups_with_their_library_match(no_library, tmp_path, capsys):
    cmd_survey_import_codebook(_args(tmp_path))

    out = capsys.readouterr().out
    assert "ads" in out and "Library match for 'ads': none" in out


def test_codebook_cli_writes_the_selected_group(no_library, tmp_path):
    out_dir = tmp_path / "out"
    cmd_survey_import_codebook(_args(tmp_path, select=["ads"], output=str(out_dir)))

    written = json.loads((out_dir / "survey-ads.json").read_text(encoding="utf-8"))
    assert written["Study"]["TaskName"] == "ads" and "ads1_1" in written


def test_codebook_cli_uses_the_project_library(library, tmp_path, capsys):
    cmd_survey_import_codebook(_args(tmp_path, project=library))

    assert "Library match for 'ads': ads (project) exact" in capsys.readouterr().out


def test_codebook_cli_output_without_select_fails(no_library, tmp_path):
    with pytest.raises(SystemExit):
        cmd_survey_import_codebook(_args(tmp_path, output=str(tmp_path / "o")))
