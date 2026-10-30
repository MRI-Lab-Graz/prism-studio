"""Text pasted from Word/PDF can carry control characters that XML 1.0 forbids; the .lss must still import."""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "src"))

from limesurvey_exporter import generate_lss  # noqa: E402
from tests.template_fixtures import complete, dump_complete


def test_control_characters_in_question_texts_do_not_break_the_xml(tmp_path):
    template = {
        "Technical": {"Language": "en"},
        "Study": {"TaskName": "odd", "OriginalName": {"en": "Odd \x0b name"}},
        "Q1": {"Description": {"en": 'He said <b>"hi"</b> & left\x00\x0b\x1f ]]> x'},
               "Levels": {"0": {"en": "no \x08 never"}, "1": {"en": "yes"}}},
        "Q2": {"Description": {"en": "plain"}},
    }
    source = tmp_path / "survey-odd.json"
    source.write_text(dump_complete(template), encoding="utf-8")
    out = tmp_path / "out.lss"

    generate_lss([str(source)], str(out), language="en", languages=["en"], base_language="en")

    root = ET.parse(out).getroot()  # raises if not well-formed
    texts = " ".join(t for el in root.iter() for t in (el.text or "",))
    assert "He said" in texts and "left" in texts and "\x0b" not in texts and "\x00" not in texts


def test_the_word_export_survives_control_characters_too():
    from questionnaire_renderer import render_questionnaire_docx

    template = {
        "Technical": {"Language": "en"},
        "Study": {"TaskName": "odd", "OriginalName": {"en": "Odd \x0b name"}},
        "Q1": {"Description": {"en": "left\x00\x0b\x1f x"}, "Levels": {"0": {"en": "no \x08 never"}, "1": {"en": "yes"}}},
    }
    assert render_questionnaire_docx(complete(template), language="en").getvalue()[:2] == b"PK"  # a zip, i.e. a .docx


def test_the_pavlovia_export_survives_control_characters_too(tmp_path):
    import xml.etree.ElementTree as ET2

    from src.converters.pavlovia import export_to_pavlovia

    template = {
        "Technical": {"Language": "en"},
        "Study": {"TaskName": "odd"},
        "Q1": {"Description": {"en": "left\x00\x0b\x1f x"}, "Levels": {"0": {"en": "no \x08"}, "1": {"en": "yes"}}},
    }
    source = tmp_path / "survey-odd.json"
    source.write_text(dump_complete(template), encoding="utf-8")
    export_to_pavlovia(source, tmp_path / "pav")
    for psyexp in (tmp_path / "pav").rglob("*.psyexp"):
        ET2.parse(psyexp)  # raises if not well-formed
