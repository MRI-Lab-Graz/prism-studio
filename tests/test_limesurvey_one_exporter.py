"""Quick Export (generate_lss) is the Customizer exporter fed from template files, so the two
cannot drift apart. What Quick Export always offered is carried by the shared exporter:
a group name and survey title per language, matrix grouping per file, the template's own
DisplayOrder, and the run number per file."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import defusedxml.ElementTree as DET  # noqa: E402
from tests.template_fixtures import complete, dump_complete

LEVELS = {"1": {"en": "no", "de": "nein"}, "2": {"en": "yes", "de": "ja"}}
TEMPLATE = {
    "Study": {"OriginalName": {"en": "Mood", "de": "Stimmung"}, "Description": "A mood scale"},
    "I18n": {"Languages": ["en", "de"], "DefaultLanguage": "en"},
    "late": {"Description": {"en": "Late", "de": "Spät"}, "Levels": LEVELS, "DisplayOrder": 2},
    "early": {"Description": {"en": "Early", "de": "Früh"}, "Levels": LEVELS, "DisplayOrder": 1},
    "third": {"Description": {"en": "Third", "de": "Dritte"}, "Levels": LEVELS},
}


@pytest.fixture
def template_path(tmp_path):
    path = tmp_path / "survey-mood.json"
    path.write_text(dump_complete(TEMPLATE), encoding="utf-8")
    return str(path)


def _root(xml):
    return DET.fromstring(xml)


def _group_names(root):
    return {row.findtext("language"): row.findtext("group_name") for row in root.findall("group_l10ns/rows/row")}


def _titles(root):
    return {row.findtext("surveyls_language"): row.findtext("surveyls_title")
            for row in root.findall("surveys_languagesettings/rows/row")}


def test_group_name_and_survey_title_are_written_in_each_language(template_path):
    from src.limesurvey_exporter import generate_lss

    root = _root(generate_lss([template_path], languages=["en", "de"]))
    assert _group_names(root) == {"en": "Mood", "de": "Stimmung"}
    assert _titles(root) == {"en": "Mood", "de": "Stimmung"}


def test_several_files_share_one_combined_survey_title(template_path):
    from src.limesurvey_exporter import generate_lss

    root = _root(generate_lss([template_path, template_path], languages=["en", "de"]))
    assert set(_titles(root).values()) == {"Combined Survey"}


def test_a_group_without_per_language_names_keeps_its_one_name():
    """What the Survey Customizer sends: one (possibly edited) name for every language."""
    from src.limesurvey_exporter import generate_lss_from_customization

    groups = [{"name": "My own name", "order": 0, "questions": [
        {"questionCode": "q", "displayOrder": 0, "enabled": True, "description": "Q", "levels": {},
         "originalData": {"Description": {"en": "Q"}}}]}]
    root = _root(generate_lss_from_customization(groups, languages=["en", "de"]))
    assert _group_names(root) == {"en": "My own name", "de": "My own name"}
    assert _titles(root) == {"en": "My own name", "de": "My own name"}


def test_display_order_of_the_template_decides_the_question_order(template_path):
    from src.limesurvey_exporter import generate_lss

    root = _root(generate_lss([template_path], matrix_mode=False))
    titles = [row.findtext("title") for row in root.findall("questions/rows/row")
              if not row.findtext("title").startswith("PRISMMETA")]
    assert titles == ["early", "late", "third"]


def test_the_customizer_loader_orders_by_display_order_too(template_path):
    from src.survey_customizer import build_customizer_groups

    [group] = build_customizer_groups([{"path": template_path}], "en")
    assert [q["questionCode"] for q in sorted(group["questions"], key=lambda q: q["displayOrder"])] == \
        ["early", "late", "third"]


def test_matrix_grouping_can_be_switched_per_file(template_path):
    from src.limesurvey_exporter import generate_lss

    def types(files):
        root = _root(generate_lss(files, matrix_mode=True))
        return [row.findtext("type") for row in root.findall("questions/rows/row")
                if not row.findtext("title").startswith("PRISMMETA")]

    assert types([template_path]) == ["F"]
    assert types([{"path": template_path, "matrix": False}]) == ["L", "L", "L"]


def test_the_run_number_of_a_file_suffixes_its_codes(template_path):
    from src.limesurvey_exporter import generate_lss

    root = _root(generate_lss([{"path": template_path, "run": 2}], matrix_mode=False))
    titles = [row.findtext("title") for row in root.findall("questions/rows/row")]
    assert "earlyrun02" in titles and "early" not in titles


def test_study_description_is_written_to_the_group(template_path):
    from src.limesurvey_exporter import generate_lss

    root = _root(generate_lss([template_path], languages=["en", "de"]))
    descriptions = {row.findtext("language"): row.findtext("description") for row in root.findall("group_l10ns/rows/row")}
    assert descriptions == {"en": "A mood scale", "de": "A mood scale"}
