"""LimeSurvey stores question, answer and help texts as HTML. The import turns them into
plain text without losing words or content: entities decoded (real exports carry
`&lt; 5`, `&gt;&gt; Kommentarfeld`), line and paragraph breaks kept as breaks, and a
`<` that is not a tag left alone (`{if(a<3, 1, b>2)}` used to become `{if(a2)}`)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))


@pytest.mark.parametrize(
    "html, text",
    [
        ("Wert &gt; 5 &amp; mehr", "Wert > 5 & mehr"),
        ("Gr&ouml;&szlig;e&nbsp;in cm", "Größe in cm"),
        ("Zeile1<br>Zeile2<br/>Zeile3", "Zeile1\nZeile2\nZeile3"),
        ("<p>Satz eins.</p><p>Satz zwei.</p>", "Satz eins.\nSatz zwei."),
        ('<p style="font-size:22px"><strong>Wie</strong> geht es?</p>', "Wie geht es?"),
        ("{if(a<3, 1, b>2)}", "{if(a<3, 1, b>2)}"),
        ("{if(a<b, 1, c>2)}", "{if(a<b, 1, c>2)}"),
        ("x < 3 and y > 2", "x < 3 and y > 2"),
        ("&lt;b&gt;literal&lt;/b&gt;", "<b>literal</b>"),
        ("Text<script>alert(1)</script><style>p{}</style><!-- note --> end", "Text end"),
        ("  viel    Platz \n\n  hier  ", "viel Platz\nhier"),
        ("", ""),
        (None, ""),
    ],
)
def test_html_to_text(html, text):
    from src.text_sanitizer import html_to_text

    assert html_to_text(html) == text


def _row(**fields):
    return "<row>" + "".join(f"<{k}><![CDATA[{v}]]></{k}>" for k, v in fields.items()) + "</row>"


# LimeSurvey 3 shape (inline text, one language), texts as LimeSurvey writes them
LSS = f"""<?xml version="1.0" encoding="UTF-8"?>
<document>
 <LimeSurveyDocType>Survey</LimeSurveyDocType>
 <DBVersion>366</DBVersion>
 <surveys><rows>{_row(sid=1, language="de")}</rows></surveys>
 <groups><rows>{_row(gid=1, group_name="Schlaf &amp; Sport", group_order=1, language="de")}</rows></groups>
 <questions><rows>
  {_row(qid=10, parent_qid=0, gid=1, type="L", title="sleep", question="<p>Satz eins.</p><p>Wie lange&nbsp;schlafen Sie?</p>", help="Nur&nbsp;Werktage", question_order=1, language="de")}
  {_row(qid=20, parent_qid=0, gid=1, type="*", title="score", question="{if(sleep<3, 1, sleep>2)}", question_order=2, language="de")}
 </rows></questions>
 <answers><rows>
  {_row(qid=10, code="1", answer="&lt; 5", sortorder=1, language="de", scale_id=0)}
  {_row(qid=10, code="2", answer="&gt; 8 Stunden<br>(lang)", sortorder=2, language="de", scale_id=0)}
 </rows></answers>
</document>""".encode()


def _template():
    from src.converters.limesurvey import _build_questionnaires

    _parsed, results = _build_questionnaires(LSS, "group")
    return results[0][1]


def test_imported_template_has_plain_text_descriptions_and_help():
    template = _template()
    assert template["sleep"]["Description"] == {"de": "Satz eins.\nWie lange schlafen Sie?"}
    assert template["sleep"]["Help"] == {"de": "Nur Werktage"}


def test_imported_template_has_plain_text_answer_labels():
    assert _template()["sleep"]["Levels"] == {
        "1": {"de": "< 5"},
        "2": {"de": "> 8 Stunden\n(lang)"},
    }


def test_equation_is_an_export_setting_not_kept():
    assert "LimeSurvey" not in _template()["score"]


def test_group_name_is_plain_text():
    from src.converters.limesurvey import list_limesurvey_questionnaires

    assert list_limesurvey_questionnaires(LSS)[0]["name"] == "Schlaf & Sport"
