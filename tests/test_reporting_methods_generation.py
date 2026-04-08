import os
import sys
import importlib

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

generate_full_methods = importlib.import_module("src.reporting").generate_full_methods


def test_generate_full_methods_normalizes_markdownish_dataset_description():
    project_data = {}
    dataset_desc = {
        "Name": "PRISM Survey Dataset",
        "Description": '"Krea"-Rohdaten beinhalten\n\n# sex\n\n# age\n\n# handedness\n\nauf Einzeltitem-Basis.',
    }

    md_text, _ = generate_full_methods(
        project_data=project_data,
        dataset_desc=dataset_desc,
        template_data={},
        lang="en",
        detail_level="standard",
        continuous=True,
    )

    assert "# sex" not in md_text
    assert "sex, age, and handedness" in md_text
    assert "auf Einzeltitem-Basis" in md_text


def test_generate_full_methods_enriches_survey_details_from_template():
    project_data = {
        "TaskDefinitions": {
            "ads": {
                "modality": "survey",
            }
        }
    }
    template_data = {
        "ads": {
            "Study": {
                "TaskName": {"en": "Affective Distress Scale"},
                "Description": {"en": "Measures distress symptoms."},
                "References": [
                    {"Type": "primary", "Citation": "Smith et al. (2020)"},
                    {"Type": "validation", "Citation": "Doe et al. (2021)"},
                ],
            },
            "q1": {
                "Levels": {
                    "1": {"en": "not at all"},
                    "2": {"en": "somewhat"},
                    "3": {"en": "very much"},
                }
            },
            "q2": {
                "Levels": {
                    "1": {"en": "not at all"},
                    "2": {"en": "somewhat"},
                    "3": {"en": "very much"},
                }
            },
        }
    }

    md_text, _ = generate_full_methods(
        project_data=project_data,
        dataset_desc=None,
        template_data=template_data,
        lang="en",
        detail_level="detailed",
        continuous=True,
    )

    assert "Affective Distress Scale" in md_text
    assert "comprises 2 items and a 3-point Likert scale" in md_text
    assert "Smith et al. (2020)" in md_text
    assert "Validation evidence: Doe et al. (2021)." in md_text


def test_generate_full_methods_uses_clean_fallback_for_short_task_codes():
    project_data = {
        "TaskDefinitions": {
            "ads": {
                "modality": "survey",
                "description": "ads",
            }
        }
    }

    md_text, _ = generate_full_methods(
        project_data=project_data,
        dataset_desc=None,
        template_data={},
        lang="en",
        detail_level="standard",
        continuous=True,
    )

    assert "The ADS was administered." in md_text
    assert "The ads." not in md_text


def test_generate_full_methods_skips_instruction_like_descriptions():
    project_data = {
        "TaskDefinitions": {
            "ribs": {
                "modality": "survey",
            }
        }
    }
    template_data = {
        "ribs": {
            "Study": {
                "TaskName": {"de": "Runco Ideational Behavior Scale"},
                "Description": {
                    "de": (
                        "Dieser Fragebogen umfasst Aussagen, welche sich zur Beschreibung "
                        "Ihrer Kreativität eignen könnten. Lesen Sie bitte jede dieser Aussagen "
                        "aufmerksam durch und entscheiden Sie, wie sehr die jeweilige Aussage "
                        "auf Sie zutrifft."
                    )
                },
            },
            "item_01": {
                "Levels": {
                    "1": {"de": "Trifft nicht zu"},
                    "2": {"de": "Trifft völlig zu"},
                }
            },
        }
    }

    md_text, _ = generate_full_methods(
        project_data=project_data,
        dataset_desc=None,
        template_data=template_data,
        lang="de",
        detail_level="standard",
        continuous=True,
    )

    assert "Lesen Sie bitte" not in md_text
    assert "entscheiden Sie" not in md_text


def test_generate_full_methods_does_not_fallback_to_other_i18n_language():
    project_data = {
        "TaskDefinitions": {
            "ribs": {
                "modality": "survey",
            }
        }
    }
    template_data = {
        "ribs": {
            "Study": {
                "TaskName": {"de": "Runco Ideational Behavior Scale"},
                "Description": {"de": "Nur deutsch verfuegbar."},
            },
            "item_01": {
                "Levels": {
                    "1": {"de": "Trifft nicht zu"},
                    "2": {"de": "Trifft voellig zu"},
                }
            },
        }
    }

    md_text, _ = generate_full_methods(
        project_data=project_data,
        dataset_desc=None,
        template_data=template_data,
        lang="en",
        detail_level="standard",
        continuous=True,
    )

    # No German fallback labels in English output when only German i18n entries exist.
    assert "Trifft nicht zu" not in md_text
    assert "Trifft voellig zu" not in md_text
