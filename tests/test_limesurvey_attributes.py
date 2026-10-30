"""LimeSurvey design attributes (maximum characters, prefix/suffix, numbers only, matrix
answer width, ...) and the equation attribute are export settings: the import keeps none of them in the
template (only the question text is the equation question's Description). The exporters still write
them when a template carries them."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import defusedxml.ElementTree as DET  # noqa: E402


def _row(**fields):
    return "<row>" + "".join(f"<{k}><![CDATA[{v}]]></{k}>" for k, v in fields.items()) + "</row>"


def _attr(qid, attribute, value, language=""):
    return _row(qid=qid, attribute=attribute, value=value, language=language)


LSS = f"""<?xml version="1.0" encoding="UTF-8"?>
<document><LimeSurveyDocType>Survey</LimeSurveyDocType><DBVersion>636</DBVersion>
 <languages><language>de</language><language>en</language></languages>
 <surveys><rows>{_row(sid=1, language="de", additional_languages="en")}</rows></surveys>
 <groups><rows>{_row(gid=1, group_order=1)}</rows></groups>
 <group_l10ns><rows>{_row(gid=1, group_name="Attrs", language="de")}</rows></group_l10ns>
 <questions><rows>
  {_row(qid=10, parent_qid=0, gid=1, type="N", title="weight", question_order=1)}
  {_row(qid=20, parent_qid=0, gid=1, type="T", title="story", question_order=2)}
  {_row(qid=30, parent_qid=0, gid=1, type="*", title="score", question_order=3)}
 </rows></questions>
 <question_l10ns><rows>
  {_row(qid=10, question="Gewicht?", language="de")}{_row(qid=20, question="Erzählen Sie", language="de")}
  {_row(qid=30, question="Beschreibung der Summe", language="de")}
 </rows></question_l10ns>
 <question_attributes><rows>
  {_attr(10, "suffix", "kg", "de")}{_attr(10, "suffix", "lbs", "en")}{_attr(10, "numbers_only", "1")}
  {_attr(10, "maximum_chars", "")}{_attr(10, "hide_tip", "1")}
  {_attr(20, "maximum_chars", "400")}{_attr(20, "cssclass", "wide")}{_attr(20, "placeholder", "hier", "de")}
  {_attr(30, "equation", "{sum(weight.NAOK, 1)}")}
 </rows></question_attributes>
</document>""".encode()


def _template(keep_export_settings=False):
    from src.converters import limesurvey

    keep = pytest.MonkeyPatch()
    if keep_export_settings:
        keep.setattr(limesurvey, "strip_export_settings", lambda template: (template, []))
    try:
        return limesurvey.limesurvey_questionnaire_template(LSS, "g1")
    finally:
        keep.undo()


def test_design_attributes_are_export_settings_the_import_does_not_keep():
    template = _template()
    assert "LimeSurvey" not in template["weight"] and "LimeSurvey" not in template["story"]


def test_the_equation_attribute_beats_the_question_text():
    assert _template()["score"]["Description"] == {"de": "Beschreibung der Summe"}


def _export(tmp_path, exporter):
    from src.limesurvey_exporter import generate_lss, generate_lss_from_customization
    from src.survey_customizer import build_customizer_groups

    template = _template(keep_export_settings=True)  # a template that carries the settings
    template["I18n"] = {"Languages": ["de"], "DefaultLanguage": "de"}
    path = tmp_path / "survey-attrs.json"
    path.write_text(json.dumps(template), encoding="utf-8")
    if exporter == "quick":
        xml = generate_lss([str(path)], language="de", matrix_mode=False)
    else:
        xml = generate_lss_from_customization(
            build_customizer_groups([{"path": str(path)}], "de"), language="de", matrix_mode=False
        )
    root = DET.fromstring(xml)
    titles = {q.findtext("qid"): q.findtext("title") for q in root.findall("questions/rows/row")}
    return {
        (titles[a.findtext("qid")], a.findtext("attribute")): a.findtext("value")
        for a in root.findall("question_attributes/rows/row")
    }


@pytest.mark.parametrize("exporter", ["quick", "customizer"])
def test_exporters_write_the_design_attributes_back(tmp_path, exporter):
    attributes = _export(tmp_path, exporter)
    assert attributes[("weight", "suffix")] == "kg"
    assert attributes[("weight", "numbers_only")] == "1"
    assert attributes[("story", "maximum_chars")] == "400"
    assert attributes[("story", "cssclass")] == "wide"
    assert attributes[("score", "equation")] == "{sum(weight.NAOK, 1)}"
