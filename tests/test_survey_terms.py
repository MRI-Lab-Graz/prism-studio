"""src/survey_terms.py: IDs for survey instruments, items and scores, derived from the library and the recipes."""

import collections
import json

import pytest

from src.survey_terms import build_survey_registry, item_local_id, score_local_id

TIPI = {
    "Study": {"TaskName": "tipi", "ShortName": "TIPI", "OriginalName": {"en": "Ten Item Personality Inventory", "de": "Zehn-Item"}},
    "Technical": {"Language": "en"},
    "I18n": {"Languages": ["en"]},
    "Metadata": {},
    "TIPI01": {"Description": {"en": "Extraverted, enthusiastic", "de": "Extravertiert"}, "Levels": {"1": {"en": "no"}, "2": {"en": "yes"}},
               "MinValue": 1, "MaxValue": 2, "DataType": "integer", "Reversed": False},
    "TIPI02": {"Description": {"en": "Critical, quarrelsome"}, "Levels": {"1": {"en": "no"}, "2": {"en": "yes"}},
               "MinValue": 1, "MaxValue": 2, "DataType": "integer", "Reversed": True},
}


def _lib(tmp_path, templates, recipes=None):
    lib, rec = tmp_path / "library", tmp_path / "recipe"
    lib.mkdir(); rec.mkdir()
    for name, data in templates.items():
        (lib / f"survey-{name}.json").write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    for name, data in (recipes or {}).items():
        (rec / f"recipe-{name}.json").write_text(json.dumps(data), encoding="utf-8")
    return lib, rec


def test_ids_follow_the_agreed_shape():
    assert item_local_id("tipi", "TIPI02") == "tipi.tipi02"
    assert item_local_id("ads-k", "ADS_K01") == "ads-k.ads-k01"
    assert score_local_id("tipi", "tipi_extraversion") == "tipi.score-extraversion"
    assert score_local_id("tipi", "Total") == "tipi.score-total"


def test_registry_has_instrument_items_and_scores(tmp_path):
    recipe = {"Scores": [{"Name": "Total", "Items": ["TIPI01"], "Description": "All items"}]}
    reg, problems = build_survey_registry(*_lib(tmp_path, {"tipi": TIPI}, {"tipi": recipe}))
    assert problems == []
    assert reg["tipi"] == {"TermID": "prism:tipi", "Level": "instrument", "Label": "TIPI",
                           "Description": "Ten Item Personality Inventory", "Status": "official"}
    assert reg["tipi.tipi01"] == {"TermID": "prism:tipi.tipi01", "Level": "item", "Parent": "prism:tipi",
                                  "Label": "TIPI01", "Description": "Extraverted, enthusiastic", "Status": "official"}
    assert reg["tipi.score-total"] == {"TermID": "prism:tipi.score-total", "Level": "score", "Parent": "prism:tipi",
                                       "Label": "TIPI Total", "Description": "All items", "Status": "official"}


def test_task_name_falls_back_to_the_file_stem(tmp_path):
    template = {**TIPI, "Study": {"ShortName": "T"}}
    reg, problems = build_survey_registry(*_lib(tmp_path, {"mytask": template}))
    assert problems == [] and "mytask" in reg and "mytask.tipi01" in reg


def test_template_without_recipe_still_gets_ids(tmp_path):
    reg, problems = build_survey_registry(*_lib(tmp_path, {"tipi": TIPI}))
    assert problems == [] and {"tipi", "tipi.tipi01", "tipi.tipi02"} == set(reg)


def test_recipe_without_template_gets_no_ids_and_is_reported(tmp_path):
    reg, problems = build_survey_registry(*_lib(tmp_path, {}, {"psqi": {"Scores": [{"Name": "Total"}]}}))
    assert reg == {} and len(problems) == 1 and "psqi" in problems[0] and "no library template" in problems[0]


def test_alias_items_get_no_id(tmp_path):
    reg, _ = build_survey_registry(*_lib(tmp_path, {"tipi": {**TIPI, "OLD01": {"AliasOf": "TIPI01"}}}))
    assert "tipi.old01" not in reg and "tipi.tipi01" in reg


def test_bad_files_and_names_are_reported_not_raised(tmp_path):
    bad_names = {**TIPI, "Frage 1": {"Description": "x"}, "score-x": {"Description": "x"}}
    templates = {"good": {**bad_names, "Study": {"TaskName": "good"}}, "list": "[1]", "broken": "{", "zdup": {**TIPI, "Study": {"TaskName": "good"}}}
    reg, problems = build_survey_registry(*_lib(tmp_path, templates, {"good": {"Scores": [{"Name": "Ärger"}, {"Name": "Total"}]}}))
    text = " | ".join(problems)
    for expect in ("survey-list.json", "survey-broken.json", "Frage 1", "score-x", "Ärger", "survey-zdup.json"):
        assert expect in text, expect
    assert len(problems) == 6
    assert "good.tipi01" in reg and "good.score-total" in reg
    assert not any("frage" in k or "score-x" in k or "rger" in k for k in reg)
    assert reg["good"]["TermID"] == "prism:good" and reg["good"]["Label"] == "good"   # the second template of the task is ignored


def test_shipped_library_gives_every_item_and_score_an_id():
    reg, problems = build_survey_registry()
    assert all("no library template" in p for p in problems), problems
    levels = collections.Counter(t["Level"] for t in reg.values())
    assert levels["instrument"] >= 103 and levels["item"] >= 1268 and levels["score"] >= 100
    assert all(key == t["TermID"].partition(":")[2] for key, t in reg.items())


# --- released IDs are frozen; one ID names one concept --------------------------

import importlib.util
from pathlib import Path

from src.survey_terms import freeze_problems, released_ids, write_released_ids
from src.term_registry import load_registry

_spec = importlib.util.spec_from_file_location(
    "check_terms", Path(__file__).resolve().parent.parent / "scripts" / "specification" / "check_terms.py")
check_terms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_terms)


def test_a_released_id_that_disappears_is_a_problem():
    assert freeze_problems({"tipi": {"TermID": "prism:tipi"}}, {"prism:tipi", "prism:tipi.tipi01"}) == [
        "prism:tipi.tipi01: released ID is gone (an ID is frozen; restore the item, score or task name)"]
    assert freeze_problems({"tipi": {"TermID": "prism:tipi"}}, {"prism:tipi"}) == []


def test_write_released_ids_only_adds(tmp_path):
    path = tmp_path / "ids.txt"
    path.write_text("prism:old\n\n", encoding="utf-8")
    assert write_released_ids({"tipi": {"TermID": "prism:tipi"}}, path) == ["prism:tipi"]
    assert path.read_text(encoding="utf-8") == "prism:old\nprism:tipi\n"
    assert write_released_ids({"tipi": {"TermID": "prism:tipi"}}, path) == []


def test_released_ids_of_a_missing_file_is_empty(tmp_path):
    assert released_ids(tmp_path / "none.txt") == set()


def test_shipped_released_ids_are_all_still_there():
    reg, _ = build_survey_registry()
    released = released_ids()
    assert released and freeze_problems(reg, released) == []


def test_no_survey_id_exists_in_another_modality():
    reg, _ = build_survey_registry()
    assert check_terms.cross_registry_problems(
        {"biosample": load_registry("biosample"), "environment": load_registry("environment"), "survey": reg}) == []
