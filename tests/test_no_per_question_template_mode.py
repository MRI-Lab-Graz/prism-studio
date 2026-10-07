"""The Survey Generator no longer offers one template per single question."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONVERTER_JS = REPO_ROOT / "app" / "static" / "js" / "modules" / "converter"
CONVERTER_PAGE = REPO_ROOT / "app" / "templates" / "converter_survey.html"


def test_converter_page_has_no_individual_questions_export():
    page = CONVERTER_PAGE.read_text(encoding="utf-8")

    assert 'value="questions"' not in page
    assert "Individual questions" not in page
    assert "templateResultQuestions" not in page


def test_converter_scripts_have_no_per_question_result_code():
    leftovers = [
        js.name
        for js in CONVERTER_JS.glob("*.js")
        if any(
            needle in js.read_text(encoding="utf-8")
            for needle in ("displayTemplateQuestions", "templateResultQuestions", "mode === 'questions'")
        )
    ]

    assert leftovers == []


def test_backend_has_no_per_question_parser():
    from src.converters import limesurvey

    assert not hasattr(limesurvey, "parse_lss_xml_by_questions")
