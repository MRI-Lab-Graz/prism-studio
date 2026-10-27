"""What the LimeSurvey import cannot represent is reported with the import (notes), not
only in the terminal: the Template Editor shows them in the import summary, the CLI prints
the same list. Nothing is changed silently."""

import io
import os
import sys
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))


def _row(**fields):
    return "<row>" + "".join(f"<{k}><![CDATA[{v}]]></{k}>" for k, v in fields.items()) + "</row>"


def _lss(language="de"):
    """One group with the types the import cannot fully represent."""
    questions = [
        (10, "M", "boxes", "N"), (20, "P", "boxcom", "N"), (30, "R", "rank", "N"),
        (40, ";", "textarr", "N"), (50, "1", "dual", "N"), (60, "L", "edu", "Y"),
        (70, "O", "withcom", "N"), (80, "Z", "mystery", "N"), (90, "Y", "agree", "N"),
        (95, "S", "plain", "N"),
    ]
    with_rows = {10, 20, 30, 40, 50}
    q_rows = "".join(_row(qid=q, parent_qid=0, gid=1, type=t, title=title, other=other, question_order=i)
                     for i, (q, t, title, other) in enumerate(questions))
    sub_rows = "".join(_row(qid=q + 1, parent_qid=q, gid=1, type="T", title="SQ001", question_order=1, scale_id=0)
                       for q, *_ in questions if q in with_rows)
    l10n = "".join(_row(qid=q, question=f"Text {title}", language=language) for q, _t, title, _o in questions)
    l10n += "".join(_row(qid=q + 1, question="row", language=language) for q in with_rows)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<document><LimeSurveyDocType>Survey</LimeSurveyDocType><DBVersion>636</DBVersion>
 <languages><language>{language}</language></languages>
 <surveys><rows>{_row(sid=1, language=language)}</rows></surveys>
 <groups><rows>{_row(gid=1, group_order=1)}</rows></groups>
 <group_l10ns><rows>{_row(gid=1, group_name="Lossy", language=language)}</rows></group_l10ns>
 <questions><rows>{q_rows}</rows></questions>
 <subquestions><rows>{sub_rows}</rows></subquestions>
 <question_l10ns><rows>{l10n}</rows></question_l10ns>
 <answers><rows>{_row(aid=1, qid=60, code="1", sortorder=1, scale_id=0)}{_row(aid=2, qid=70, code="1", sortorder=1, scale_id=0)}</rows></answers>
 <answer_l10ns><rows>{_row(aid=1, answer="Matura", language=language)}{_row(aid=2, answer="ja", language=language)}</rows></answer_l10ns>
</document>""".encode()


def _notes(language="de"):
    from src.converters.limesurvey import limesurvey_questionnaire

    _template, notes = limesurvey_questionnaire(_lss(language), "g1")
    return notes


def _about(notes, title):
    return [n for n in notes if f" / {title}:" in n]


@pytest.mark.parametrize("title", ["boxes", "boxcom", "rank", "textarr", "dual"])
def test_lossy_types_with_rows_are_reported(title):
    [note] = _about(_notes(), title)
    assert note.startswith("Lossy / ")


def test_other_field_is_reported():
    [note] = _about(_notes(), "edu")
    assert "Other" in note


def test_comment_field_is_reported():
    [note] = _about(_notes(), "withcom")
    assert "comment" in note


def test_unknown_type_is_reported():
    [note] = _about(_notes(), "mystery")
    assert "Z" in note


def test_representable_questions_have_no_note():
    notes = _notes()
    assert _about(notes, "agree") == [] and _about(notes, "plain") == []


def test_builtin_labels_in_an_unsupported_language_are_reported_once():
    [note] = [n for n in _notes("fr") if "English" in n]
    assert "fr" in note
    assert not [n for n in _notes("de") if "English" in n]


def test_payload_and_cli_carry_the_notes(capsys):
    from src.converters.limesurvey import limesurvey_questionnaire
    from src.converters.template_import import finish_import

    template, notes = limesurvey_questionnaire(_lss(), "g1")
    payload = finish_import(template, "Lossy", notes=notes)
    assert payload["notes"] == notes and notes
    printed = capsys.readouterr().out
    assert all(f"[PRISM] WARNING {n}" in printed for n in notes)


def test_listing_prints_the_notes_for_cli_users(capsys):
    from src.converters.limesurvey import list_limesurvey_questionnaires

    list_limesurvey_questionnaires(_lss())
    assert "[PRISM] WARNING Lossy / boxes:" in capsys.readouterr().out


def test_route_returns_the_notes():
    import importlib

    module = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    app.register_blueprint(module.tools_template_editor_bp)
    response = app.test_client().post(
        "/api/template-editor/import-limesurvey",
        data={"file": (io.BytesIO(_lss()), "lossy.lss"), "key": "g1"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert any(" / boxes:" in n for n in response.get_json()["notes"])
