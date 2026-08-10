import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from src.limesurvey_exporter import generate_lss, generate_lss_from_customization


def _mandatory_by_title(xml_text):
    """Map LSS question <title> -> <mandatory> ('Y'/'N') for every question row."""
    root = ET.fromstring(xml_text)
    result = {}
    for row in root.findall(".//questions/rows/row"):
        title = row.findtext("title")
        mandatory = row.findtext("mandatory")
        if title is not None:
            result[title] = mandatory
    return result


def test_generate_lss_from_customization_builds_xml_with_defusedxml_installed(
    tmp_path,
):
    template_path = tmp_path / "survey-template.json"
    template_path.write_text(
        json.dumps(
            {
                "Study": {
                    "OriginalName": "Template Survey",
                    "Instructions": {"en": "Please answer all questions."},
                },
                "Questions": {
                    "q1": {
                        "Description": {"en": "How are you today?"},
                        "InputType": "radio",
                        "Levels": {
                            "1": "Not at all",
                            "2": "Somewhat",
                            "3": "Very much",
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    groups = [
        {
            "id": "group-1",
            "name": "Template Survey",
            "order": 0,
            "sourceFile": str(template_path),
            "questions": [
                {
                    "id": "question-1",
                    "sourceFile": str(template_path),
                    "questionCode": "q1",
                    "description": "How are you today?",
                    "displayOrder": 0,
                    "mandatory": True,
                    "enabled": True,
                    "runNumber": 1,
                    "levels": {
                        "1": "Not at all",
                        "2": "Somewhat",
                        "3": "Very much",
                    },
                    "originalData": {
                        "Description": {"en": "How are you today?"},
                        "InputType": "radio",
                        "Levels": {
                            "1": "Not at all",
                            "2": "Somewhat",
                            "3": "Very much",
                        },
                    },
                }
            ],
        }
    ]

    xml_text = generate_lss_from_customization(
        groups,
        language="en",
        languages=["en"],
        base_language="en",
        ls_version="6",
        matrix_mode=False,
        matrix_global=False,
        survey_title="Customized Survey",
    )

    root = ET.fromstring(xml_text)

    assert root.tag == "document"
    assert root.findtext("LimeSurveyDocType") == "Survey"
    assert "Customized Survey" in xml_text
    assert "How are you today?" in xml_text


def test_generate_lss_single_question_respects_mandatory_false(tmp_path):
    """Regression test: Quick Export (generate_lss) previously hardcoded every
    question's <mandatory> to "Y", silently ignoring the PRISM `Mandatory`
    field. See app/schemas/stable/survey.schema.json for the field
    definition (defaults to true, but explicit false must be honored)."""
    template_path = tmp_path / "task-optional_beh.json"
    template_path.write_text(
        json.dumps(
            {
                "Study": {"OriginalName": "Optional Question Survey"},
                "comments": {
                    "Description": "Any additional comments?",
                    "InputType": "text",
                    "Mandatory": False,
                },
            }
        ),
        encoding="utf-8",
    )

    xml_text = generate_lss(
        [str(template_path)], language="en", languages=["en"], ls_version="6"
    )

    mandatory = _mandatory_by_title(xml_text)
    comments_mandatory = next(v for k, v in mandatory.items() if "comments" in k.lower())
    assert comments_mandatory == "N"


def test_generate_lss_single_question_defaults_mandatory_true(tmp_path):
    template_path = tmp_path / "task-required_beh.json"
    template_path.write_text(
        json.dumps(
            {
                "Study": {"OriginalName": "Required Question Survey"},
                "age": {"Description": "Age", "InputType": "text"},
            }
        ),
        encoding="utf-8",
    )

    xml_text = generate_lss(
        [str(template_path)], language="en", languages=["en"], ls_version="6"
    )

    mandatory = _mandatory_by_title(xml_text)
    age_mandatory = next(v for k, v in mandatory.items() if "age" in k.lower())
    assert age_mandatory == "Y"


def test_generate_lss_matrix_question_mandatory_reflects_any_true(tmp_path):
    """Matrix (array) parent question should be mandatory if ANY subquestion
    is mandatory — mirrors generate_lss_from_customization's any_mandatory
    logic, which generate_lss previously did not have at all."""
    template_path = tmp_path / "task-matrix_beh.json"
    levels = {"0": "Not at all", "1": "A little", "2": "Extremely"}
    template_path.write_text(
        json.dumps(
            {
                "Study": {"OriginalName": "Matrix Survey"},
                "mood_1": {
                    "Description": "Sadness",
                    "Levels": levels,
                    "Mandatory": False,
                },
                "mood_2": {
                    "Description": "Anxiety",
                    "Levels": levels,
                    "Mandatory": True,
                },
            }
        ),
        encoding="utf-8",
    )

    xml_text = generate_lss(
        [{"path": str(template_path), "matrix": True, "matrix_global": True}],
        language="en",
        languages=["en"],
        ls_version="6",
    )

    mandatory = _mandatory_by_title(xml_text)
    matrix_mandatory = next(v for k, v in mandatory.items() if k.startswith("M"))
    assert matrix_mandatory == "Y"


def test_generate_lss_matrix_question_mandatory_false_when_all_false(tmp_path):
    template_path = tmp_path / "task-matrix-optional_beh.json"
    levels = {"0": "Not at all", "1": "A little", "2": "Extremely"}
    template_path.write_text(
        json.dumps(
            {
                "Study": {"OriginalName": "Matrix Survey"},
                "mood_1": {
                    "Description": "Sadness",
                    "Levels": levels,
                    "Mandatory": False,
                },
                "mood_2": {
                    "Description": "Anxiety",
                    "Levels": levels,
                    "Mandatory": False,
                },
            }
        ),
        encoding="utf-8",
    )

    xml_text = generate_lss(
        [{"path": str(template_path), "matrix": True, "matrix_global": True}],
        language="en",
        languages=["en"],
        ls_version="6",
    )

    mandatory = _mandatory_by_title(xml_text)
    matrix_mandatory = next(v for k, v in mandatory.items() if k.startswith("M"))
    assert matrix_mandatory == "N"


def test_generate_lss_default_groups_same_levels_questions_into_matrix(tmp_path):
    """Regression test: Quick Export (plain string file paths, as used by both
    the CLI's `survey export-lss` and the Studio GUI's "Quick Export" button)
    previously never grouped same-Levels questions into a LimeSurvey
    array/matrix question at all -- matrix_mode/matrix_global silently
    defaulted to False for that call shape, while generate_lss_from_customization
    defaulted both to True. generate_lss now defaults matrix_mode=True,
    matrix_global=True to match, so the two export paths produce the same
    structure for the same data unless a caller opts out."""
    template_path = tmp_path / "task-battery_beh.json"
    levels = {"0": "Not at all", "1": "A little", "2": "Extremely"}
    template_path.write_text(
        json.dumps(
            {
                "Study": {"OriginalName": "Battery Survey"},
                "mood_1": {"Description": "Sadness", "Levels": levels},
                "mood_2": {"Description": "Anxiety", "Levels": levels},
            }
        ),
        encoding="utf-8",
    )

    xml_text = generate_lss(
        [str(template_path)], language="en", languages=["en"], ls_version="6"
    )

    root = ET.fromstring(xml_text)
    titles = [row.findtext("title") for row in root.findall(".//questions/rows/row")]
    matrix_titles = [t for t in titles if t and t.startswith("M")]
    assert matrix_titles, f"Expected a grouped matrix question, got titles: {titles}"


def test_generate_lss_matrix_mode_false_keeps_questions_standalone(tmp_path):
    """A caller can still opt out of the new default via matrix_mode=False
    (e.g. round-trip/library-matching tests that need per-question code
    fidelity -- see tests/test_lsa_import_integration.py)."""
    template_path = tmp_path / "task-battery_beh.json"
    levels = {"0": "Not at all", "1": "A little", "2": "Extremely"}
    template_path.write_text(
        json.dumps(
            {
                "Study": {"OriginalName": "Battery Survey"},
                "mood_1": {"Description": "Sadness", "Levels": levels},
                "mood_2": {"Description": "Anxiety", "Levels": levels},
            }
        ),
        encoding="utf-8",
    )

    xml_text = generate_lss(
        [str(template_path)],
        language="en",
        languages=["en"],
        ls_version="6",
        matrix_mode=False,
    )

    root = ET.fromstring(xml_text)
    titles = [row.findtext("title") for row in root.findall(".//questions/rows/row")]
    matrix_titles = [t for t in titles if t and t.startswith("M")]
    assert not matrix_titles, f"Expected no matrix grouping, got titles: {titles}"
