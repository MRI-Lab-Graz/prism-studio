"""LimeSurvey import + library match (spec 2026-10-07-limesurvey-library-match)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.converters import library_wording_match as lwm
from src.converters import limesurvey as ls
from src.converters import survey_templates as st
from test_library_wording_match import library_file

FIXTURE = Path(__file__).parent / "data" / "limesurvey_four_questionnaires.lss"
XML = FIXTURE.read_bytes()
ADS = ["war ich bedrückt", "war ich müde"]
ADS_LEVELS = {"0": "selten", "1": "meistens"}


@pytest.fixture
def libs(tmp_path, monkeypatch):
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    project = tmp_path / "project"
    (project / "code" / "library" / "survey").mkdir(parents=True)
    monkeypatch.setattr(st, "_load_global_library_path", lambda: global_dir)
    library_file(global_dir, texts=ADS, levels=ADS_LEVELS)
    return {"global": global_dir, "project": project, "project_dir": project / "code" / "library" / "survey"}


def test_matching_is_opt_in():
    assert all("library_match" not in q for q in ls.list_limesurvey_questionnaires(XML))


def test_listing_reports_the_match_per_questionnaire_and_logs_it(libs, capsys):
    found = {q["key"]: q for q in ls.list_limesurvey_questionnaires(XML, match_library=True)}

    ads = found["g30"]["library_match"]
    assert ads["template_key"] == "ads" and ads["confidence"] == "exact" and ads["adoptable"] is True
    assert ads["id_map"] == {"ADS1_1": "ads_01", "ADS1_2": "ads_02"}
    assert "template_path" not in ads
    assert found["g20"]["library_match"] is None
    out = capsys.readouterr().out
    assert "[PRISM] Library match for 'ADS': ads (global) exact — 2/2 items paired, levels equal, IDs differ (ADS1_1->ads_01, ADS1_2->ads_02)" in out
    assert "[PRISM] Library match for 'WHO-5': none" in out


def test_match_for_one_questionnaire_returns_template_and_match(libs):
    template, match = ls.limesurvey_questionnaire_match(XML, "g30")

    assert "ADS1_1" in template and match["template_key"] == "ads"


def test_library_template_carries_the_survey_codes_as_aliases(libs):
    template, match = ls.limesurvey_library_template(XML, "g30")

    assert template["ads_01"]["Aliases"] == ["ADS1_1"] and match["adoptable"] is True


def test_library_template_refuses_when_nothing_matches(libs):
    with pytest.raises(ValueError, match="one-to-one"):
        ls.limesurvey_library_template(XML, "g20")


def test_a_matching_failure_never_blocks_the_import(libs, monkeypatch, capsys):
    def boom(*_a, **_k):
        raise RuntimeError("library unreadable")

    monkeypatch.setattr(lwm, "best_library_match", boom)

    found = ls.list_limesurvey_questionnaires(XML, match_library=True)

    assert len(found) == 4 and all(q["library_match"] is None for q in found)
    assert "[PRISM] Library match skipped: library unreadable" in capsys.readouterr().out


def test_project_library_is_searched_when_a_project_path_is_given(libs):
    for path in libs["global"].iterdir():
        path.unlink()
    library_file(libs["project_dir"], texts=ADS, levels=ADS_LEVELS)

    without = {q["key"]: q for q in ls.list_limesurvey_questionnaires(XML, match_library=True)}
    with_project = {
        q["key"]: q
        for q in ls.list_limesurvey_questionnaires(XML, match_library=True, project_path=libs["project"])
    }

    assert without["g30"]["library_match"] is None
    assert with_project["g30"]["library_match"]["source"] == "project"


def test_a_prism_template_round_trips_to_its_own_library_entry(libs, tmp_path):
    from src.limesurvey_exporter import generate_lss

    texts = ["erstes Item hier", "zweites Item dort"]
    original = {
        "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "SoftwarePlatform": "LimeSurvey",
                      "Language": "de", "Respondent": "self", "AdministrationMethod": "online"},
        "Study": {"TaskName": "rts", "OriginalName": "Round Trip Scale", "ShortName": "RTS",
                  "Citation": "c", "LicenseID": "CC-BY-4.0", "Category": "other"},
        "RTS01": {"Description": texts[0], "Levels": {"1": "nie", "2": "oft"}},
        "RTS02": {"Description": texts[1], "Levels": {"1": "nie", "2": "oft"}},
    }
    source = libs["project_dir"] / "survey-rts.json"
    source.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
    lss = tmp_path / "rts.lss"
    generate_lss([str(source)], output_path=str(lss), language="de")

    [entry] = ls.list_limesurvey_questionnaires(lss.read_bytes(), match_library=True, project_path=libs["project"])

    assert entry["library_match"]["template_key"] == "rts"
    assert entry["library_match"]["confidence"] == "exact"
    assert entry["library_match"]["ids_identical"] is True
