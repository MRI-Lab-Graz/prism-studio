import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from src.limesurvey_exporter import generate_lss_from_customization


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
