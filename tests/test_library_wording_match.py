"""Library matching by wording (spec 2026-10-07-limesurvey-library-match)."""

from __future__ import annotations

import json

import pytest

from src.converters import library_wording_match as lwm
from src.converters import survey_templates as st

TEXTS = ["war ich bedrückt", "war ich müde", "konnte ich nicht schlafen", "fühlte ich mich einsam"]
LEVELS = {"0": "selten", "1": "manchmal", "2": "meistens"}


def imported(texts=TEXTS, codes=None, levels=LEVELS, lang="de"):
    """A questionnaire as the LimeSurvey import builds it (multilingual dicts)."""
    codes = codes or [f"ADS1_{i}" for i in range(1, len(texts) + 1)]
    template = {"Technical": {"Language": lang}, "Study": {"TaskName": "ads", "OriginalName": "ADS"}}
    for code, text in zip(codes, texts):
        item = {"Description": {lang: text}}
        if levels:
            item["Levels"] = {k: {lang: v} for k, v in levels.items()}
        template[code] = item
    return template


def library_file(directory, name="ads", texts=TEXTS, codes=None, levels=LEVELS, bilingual=False):
    """A library template file (plain strings, like the global library)."""
    codes = codes or [f"ads_{i:02d}" for i in range(1, len(texts) + 1)]
    template = {"Technical": {"Language": "de"}, "Study": {"TaskName": name}}
    for code, text in zip(codes, texts):
        item = {"Description": {"de": text, "en": "english " + text} if bilingual else text}
        if levels:
            item["Levels"] = {k: ({"de": v, "en": "e " + v} if bilingual else v) for k, v in levels.items()}
        template[code] = item
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"survey-{name}.json"
    path.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def libs(tmp_path, monkeypatch):
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    project = tmp_path / "project"
    project_dir = project / "code" / "library" / "survey"
    project_dir.mkdir(parents=True)
    monkeypatch.setattr(st, "_load_global_library_path", lambda: global_dir)
    return {"global": global_dir, "project_dir": project_dir, "project": project}


def test_wording_is_compared_without_html_case_or_punctuation():
    assert lwm.normalize_wording("<p>… War ich  bedrückt!</p>") == "war ich bedrückt"


def test_same_wording_with_different_ids_is_exact_and_maps_every_item(libs):
    library_file(libs["global"])

    match = lwm.best_library_match(imported())

    assert match["confidence"] == "exact" and match["adoptable"] is True
    assert match["source"] == "global" and match["template_key"] == "ads"
    assert match["paired"] == match["imported_items"] == match["library_items"] == 4
    assert match["ids_identical"] is False
    assert match["id_map"] == {"ADS1_1": "ads_01", "ADS1_2": "ads_02", "ADS1_3": "ads_03", "ADS1_4": "ads_04"}
    assert match["reworded"] == [] and match["levels_ok"] is True


def test_identical_ids_are_reported_as_identical(libs):
    codes = ["ADS1_1", "ADS1_2", "ADS1_3", "ADS1_4"]
    library_file(libs["global"], codes=codes)

    assert lwm.best_library_match(imported())["ids_identical"] is True


def test_slightly_reworded_items_are_high_not_exact(libs):
    texts = ["war ich sehr bedrückt"] + TEXTS[1:]
    library_file(libs["global"], texts=texts)

    match = lwm.best_library_match(imported())

    assert match["confidence"] == "high" and match["adoptable"] is True
    [reworded] = match["reworded"]
    assert reworded["imported"] == "ADS1_1" and reworded["library"] == "ads_01"
    assert 0.85 <= reworded["similarity"] < 0.97


def test_unrelated_library_template_is_no_match(libs):
    other = ["das Wetter war schön", "wir gingen spazieren", "es gab Kuchen", "am Abend regnete es"]
    library_file(libs["global"], texts=other)

    assert lwm.best_library_match(imported()) is None


def test_partial_coverage_is_medium_and_not_adoptable(libs):
    library_file(libs["global"], texts=TEXTS[:3])

    match = lwm.best_library_match(imported())

    assert match["confidence"] == "medium" and match["adoptable"] is False
    assert match["unpaired_imported"] == ["ADS1_4"]


def test_less_than_seventy_percent_covered_is_no_match(libs):
    library_file(libs["global"], texts=TEXTS[:2])

    assert lwm.best_library_match(imported()) is None


def test_identical_wording_twice_stays_one_to_one_by_position(libs):
    texts = ["ich war müde", "ich war müde", "ich war froh"]
    library_file(libs["global"], texts=texts)

    match = lwm.best_library_match(imported(texts=texts, codes=["a1", "a2", "a3"]))

    assert match["id_map"] == {"a1": "ads_01", "a2": "ads_02", "a3": "ads_03"}


def test_different_answer_levels_cap_the_match_at_medium(libs):
    library_file(libs["global"], levels={"0": "selten", "1": "manchmal"})

    match = lwm.best_library_match(imported())

    assert match["levels_ok"] is False
    assert match["confidence"] == "medium" and match["adoptable"] is False


def test_crossed_ids_are_a_conflict_and_not_adoptable(libs):
    a, b = TEXTS[0], TEXTS[2]
    library_file(libs["global"], texts=[a, b], codes=["Q2", "Q1"])

    match = lwm.best_library_match(imported(texts=[a, b], codes=["Q1", "Q2"]))

    assert match["ids_conflict"] is True
    assert match["confidence"] == "medium" and match["adoptable"] is False


def test_german_import_matches_a_bilingual_library_template(libs):
    library_file(libs["global"], bilingual=True)

    assert lwm.best_library_match(imported())["confidence"] == "exact"


def test_german_import_does_not_match_an_english_only_template(libs):
    english = ["i was depressed", "i was tired", "i could not sleep", "i felt lonely"]
    library_file(libs["global"], texts=english)

    assert lwm.best_library_match(imported()) is None


def test_project_template_wins_over_the_same_global_one(libs):
    library_file(libs["global"])
    library_file(libs["project_dir"])

    assert lwm.best_library_match(imported(), libs["project"])["source"] == "project"


def test_library_with_far_more_items_is_skipped(libs):
    filler = [f"völlig anderer Satz Nummer {i} über etwas ganz anderes" for i in range(6)]
    library_file(libs["global"], texts=TEXTS + filler)

    assert lwm.best_library_match(imported()) is None


def test_missing_folders_and_alias_only_items_do_not_crash(libs):
    assert lwm.best_library_match(imported(), libs["project"] / "nope") is None  # nothing matches

    path = library_file(libs["global"])
    data = json.loads(path.read_text(encoding="utf-8"))
    data["ads_alias"] = {"AliasOf": "ads_01"}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    assert lwm.best_library_match(imported())["confidence"] == "exact"


def _tree(directory):
    return {p.name: p.read_bytes() for p in sorted(directory.iterdir())}


def test_adopting_adds_the_survey_codes_as_aliases_and_keeps_library_ids(libs):
    path = library_file(libs["global"])
    match = lwm.best_library_match(imported())

    adopted = lwm.apply_library_template(match)

    assert [k for k in adopted if k.startswith("ads_")] == ["ads_01", "ads_02", "ads_03", "ads_04"]
    assert adopted["ads_01"]["Aliases"] == ["ADS1_1"]
    assert adopted["ads_04"]["Aliases"] == ["ADS1_4"]
    assert "Aliases" not in json.loads(path.read_text(encoding="utf-8"))["ads_01"]  # file untouched


def test_aliases_are_deduplicated_and_identical_codes_get_none(libs):
    path = library_file(libs["global"], codes=["ADS1_1", "ads_02", "ads_03", "ads_04"])
    data = json.loads(path.read_text(encoding="utf-8"))
    data["ads_02"]["Aliases"] = ["ADS1_2"]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    adopted = lwm.apply_library_template(lwm.best_library_match(imported()))

    assert "Aliases" not in adopted["ADS1_1"]
    assert adopted["ads_02"]["Aliases"] == ["ADS1_2"]


def test_a_match_that_is_not_one_to_one_cannot_be_adopted(libs):
    library_file(libs["global"], texts=TEXTS[:3])

    with pytest.raises(ValueError, match="one-to-one"):
        lwm.apply_library_template(lwm.best_library_match(imported()))
    with pytest.raises(ValueError, match="one-to-one"):
        lwm.apply_library_template(None)


def test_the_global_library_is_never_written(libs):
    library_file(libs["global"])
    library_file(libs["global"], name="other", texts=["etwas ganz anderes hier", "noch etwas anderes dort"])
    before = _tree(libs["global"])

    match = lwm.best_library_match(imported(), libs["project"])
    lwm.apply_library_template(match)

    assert _tree(libs["global"]) == before


def test_public_view_never_exposes_the_local_path(libs):
    library_file(libs["global"])
    match = lwm.best_library_match(imported())

    public = lwm.public_library_match(match)

    assert "template_path" not in public and public["template_file"] == "survey-ads.json"
    assert public["id_map"] == match["id_map"]
    assert lwm.public_library_match(None) is None
