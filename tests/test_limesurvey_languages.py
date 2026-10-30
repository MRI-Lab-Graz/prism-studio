"""A multilingual LimeSurvey survey imports with every language, and the base language's
text is the main one whatever the row order. LimeSurvey 6 keeps texts in *_l10ns tables
(one row per language, in no guaranteed order); LimeSurvey 3 repeats each question,
row and answer once per language."""

import logging
import sys
from pathlib import Path
from tests.template_fixtures import complete, dump_complete

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))


def _row(**fields):
    return "<row>" + "".join(f"<{k}><![CDATA[{v}]]></{k}>" for k, v in fields.items()) + "</row>"


# LimeSurvey 6: base de, additional en; the en rows come FIRST in every l10n table
LS6 = f"""<?xml version="1.0" encoding="UTF-8"?>
<document><LimeSurveyDocType>Survey</LimeSurveyDocType><DBVersion>636</DBVersion>
 <languages><language>de</language><language>en</language></languages>
 <surveys><rows>{_row(sid=1, language="de", additional_languages="en")}</rows></surveys>
 <groups><rows>{_row(gid=1, group_order=1)}</rows></groups>
 <group_l10ns><rows>{_row(gid=1, group_name="Mood", language="en")}{_row(gid=1, group_name="Stimmung", language="de")}</rows></group_l10ns>
 <questions><rows>
  {_row(qid=10, parent_qid=0, gid=1, type="F", title="mood", question_order=1)}
  {_row(qid=20, parent_qid=0, gid=1, type="Y", title="consent", question_order=2)}
 </rows></questions>
 <subquestions><rows>{_row(qid=11, parent_qid=10, gid=1, type="T", title="M1", question_order=1, scale_id=0)}</rows></subquestions>
 <question_l10ns><rows>
  {_row(qid=10, question="How do you feel?", help="Be honest", language="en")}{_row(qid=10, question="Wie fühlen Sie sich?", help="Ehrlich", language="de")}
  {_row(qid=11, question="calm", language="en")}{_row(qid=11, question="ruhig", language="de")}
  {_row(qid=20, question="Agree?", language="en")}{_row(qid=20, question="Einverstanden?", language="de")}
 </rows></question_l10ns>
 <answers><rows>{_row(aid=1, qid=10, code="1", sortorder=1, scale_id=0)}</rows></answers>
 <answer_l10ns><rows>{_row(aid=1, answer="never", language="en")}{_row(aid=1, answer="nie", language="de")}</rows></answer_l10ns>
</document>""".encode()

# LimeSurvey 3: the same survey with inline texts, en rows first
LS3 = f"""<?xml version="1.0" encoding="UTF-8"?>
<document><LimeSurveyDocType>Survey</LimeSurveyDocType><DBVersion>366</DBVersion>
 <languages><language>de</language><language>en</language></languages>
 <surveys><rows>{_row(sid=1, language="de", additional_languages="en")}</rows></surveys>
 <groups><rows>{_row(gid=1, group_name="Mood", group_order=1, language="en")}{_row(gid=1, group_name="Stimmung", group_order=1, language="de")}</rows></groups>
 <questions><rows>
  {_row(qid=10, parent_qid=0, gid=1, type="F", title="mood", question="How do you feel?", help="Be honest", question_order=1, language="en")}
  {_row(qid=10, parent_qid=0, gid=1, type="F", title="mood", question="Wie fühlen Sie sich?", help="Ehrlich", question_order=1, language="de")}
  {_row(qid=20, parent_qid=0, gid=1, type="Y", title="consent", question="Agree?", question_order=2, language="en")}
  {_row(qid=20, parent_qid=0, gid=1, type="Y", title="consent", question="Einverstanden?", question_order=2, language="de")}
 </rows></questions>
 <subquestions><rows>
  {_row(qid=11, parent_qid=10, gid=1, type="T", title="M1", question="calm", question_order=1, scale_id=0, language="en")}
  {_row(qid=11, parent_qid=10, gid=1, type="T", title="M1", question="ruhig", question_order=1, scale_id=0, language="de")}
 </rows></subquestions>
 <answers><rows>
  {_row(qid=10, code="1", answer="never", sortorder=1, scale_id=0, language="en")}
  {_row(qid=10, code="1", answer="nie", sortorder=1, scale_id=0, language="de")}
 </rows></answers>
</document>""".encode()


def _template(xml):
    from src.converters.limesurvey import _build_questionnaires

    parsed, results = _build_questionnaires(xml, "group")
    return parsed, results[0][0], results[0][1]


def _check_both_languages(xml):
    parsed, info, template = _template(xml)
    assert parsed["default_language"] == "de"
    assert template["I18n"] == {"Languages": ["de", "en"], "DefaultLanguage": "de"}
    assert info["name"] == "Stimmung"
    assert template["M1"]["Description"] == {"de": "ruhig", "en": "calm"}
    assert template["M1"]["Levels"] == {"1": {"de": "nie", "en": "never"}}
    assert template["M1"]["Help"] == {"de": "Ehrlich", "en": "Be honest"}
    assert template["Study"]["Instructions"] == {"de": "Wie fühlen Sie sich?", "en": "How do you feel?"}
    assert template["consent"]["Description"] == {"de": "Einverstanden?", "en": "Agree?"}
    assert template["consent"]["Levels"] == {"Y": {"de": "Ja", "en": "Yes"}, "N": {"de": "Nein", "en": "No"}}


def test_limesurvey6_survey_imports_every_language_with_base_language_first():
    _check_both_languages(LS6)


def test_limesurvey3_survey_imports_every_language_with_base_language_first():
    _check_both_languages(LS3)


def test_single_sidecar_converter_uses_base_language_text():
    from src.converters.limesurvey import parse_lss_xml

    assert parse_lss_xml(LS6, check_collisions=False)["consent"]["Description"] == "Einverstanden?"


def test_lsq_language_comes_from_the_file():
    from src.converters.limesurvey import parse_lsq_xml

    lsq = f"""<?xml version="1.0" encoding="UTF-8"?>
<document><LimeSurveyDocType>Question</LimeSurveyDocType><DBVersion>636</DBVersion>
 <languages><language>de</language></languages>
 <questions><rows>{_row(qid=20, parent_qid=0, gid=1, type="S", title="name", question_order=1)}</rows></questions>
 <question_l10ns><rows>{_row(qid=20, question="Ihr Name?", language="de")}</rows></question_l10ns>
</document>""".encode()
    template = parse_lsq_xml(lsq)
    assert template["name"]["Description"] == {"de": "Ihr Name?"}
    assert template["Technical"]["Language"] == "de"


def test_export_reports_a_missing_translation(tmp_path, caplog):
    import json

    from src.limesurvey_exporter import generate_lss

    path = tmp_path / "survey-half.json"
    path.write_text(dump_complete({
        "Study": {"OriginalName": "Half"},
        "q1": {"Description": {"de": "Nur deutsch"}, "LimeSurvey": {"questionType": "S"}},
    }), encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="src.limesurvey_exporter"):
        generate_lss([str(path)], languages=["de", "en"], base_language="de")
    assert any("q1" in r.getMessage() and "'en'" in r.getMessage() for r in caplog.records)


def _with_titles(xml):
    """The survey's language settings with the additional language (en) listed first."""
    settings = ("<surveys_languagesettings><rows>"
                + _row(surveyls_language="en", surveyls_title="Mood study", surveyls_description="About mood")
                + _row(surveyls_language="de", surveyls_title="Stimmungsstudie", surveyls_description="Über Stimmung")
                + "</rows></surveys_languagesettings>")
    return xml.replace(b"</document>", settings.encode() + b"</document>")


def test_survey_title_comes_from_the_base_language():
    from src.converters.limesurvey import list_limesurvey_questionnaires

    [found] = list_limesurvey_questionnaires(_with_titles(LS6), split="survey")
    assert found["name"] == "Stimmungsstudie"


def test_single_sidecar_converter_title_and_description_come_from_the_base_language():
    from src.converters.limesurvey import parse_lss_xml

    study = parse_lss_xml(_with_titles(LS6), check_collisions=False)["Study"]
    assert study["OriginalName"] == "Stimmungsstudie"
    assert study["Description"] == "Über Stimmung"
