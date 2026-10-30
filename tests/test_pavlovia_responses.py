"""Pavlovia survey responses (the CSV download) -> one clean wide table for `survey convert`.

Shaped after a real download: two experiments in one file (the newer one stores every answer
under `block/`), a question renamed between versions, `_rt` reaction-time columns, rows that
are empty or lack the ID, a hidden ID part (studyID) the new experiment does not store."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src.converters.pavlovia_responses import prepare_pavlovia_responses
from tests.template_fixtures import complete, dump_complete

SURVEY = {
    "pages": [
        {"name": "Basics", "elements": [
            {"type": "text", "name": "studyID", "visible": False, "defaultValue": 144, "inputType": "number"},
            {"type": "text", "name": "subID", "inputType": "number"},
            {"type": "dropdown", "name": "sesID", "choices": [{"value": "Item 1", "text": "1"}, {"value": "Item 2", "text": "2"}]},
            {"type": "rating", "name": "rauchen", "rateValues": [{"value": "viel weniger", "text": "Ja"}, {"value": "weniger", "text": "Nein"}]},
        ]},
        {"name": "ARSQ", "elements": [{"type": "rating", "name": "ARSQ1"}, {"type": "rating", "name": "ARSQ2"}]},
        {"name": "Danke", "elements": [{"type": "boolean", "name": "question1"}]},
    ]
}
COLUMNS = ["surveyId", "responseId", "experimentId", "participant", "responseDate", "isComplete", "ARSQ1", "ARSQ1_rt",
           "ARSQ2", "question1", "question3", "sesID", "studyID", "subID", "block/ARSQ1", "block/ARSQ2", "block/rauchen",
           "block/sesID", "block/subID", "block/question1"]


def _table(*rows):
    df = pd.DataFrame("", index=range(len(rows)), columns=COLUMNS)
    for i, row in enumerate(rows):
        for key, value in row.items():
            df.loc[i, key] = value
    return df


OLD = dict(experimentId="1", studyID="134", subID="14", sesID="Item 1", ARSQ1="2", ARSQ1_rt="1858.1", ARSQ2="3",
           question3="weniger", question1="TRUE", isComplete="FALSE")
NEW = {"experimentId": "2", "block/subID": "153", "block/sesID": "Item 2", "block/ARSQ1": "4", "block/ARSQ2": "1",
       "block/rauchen": "viel weniger", "block/question1": "TRUE", "isComplete": "TRUE"}


def _prepare(*rows, **kw):
    kw = {"id_columns": ["studyID", "subID"], "id_pad": 3, "session_column": "sesID",
          "rename": ["question3=rauchen"], **kw}
    return prepare_pavlovia_responses(_table(*rows), SURVEY, **kw)


def test_block_prefixed_answers_land_in_the_plain_columns_and_the_noise_columns_go():
    df, _notes = _prepare(OLD, NEW)
    assert list(df.loc[:, "ARSQ1"]) == ["2", "4"]
    assert not [c for c in df.columns if c.endswith("_rt") or c.startswith("block/") or c in ("surveyId", "responseId", "isComplete")]


def test_a_renamed_question_is_read_as_the_new_one():
    df, _notes = _prepare(OLD, NEW)
    assert list(df["rauchen"]) == ["weniger", "viel weniger"]


def test_participant_id_is_study_id_plus_sub_id_padded_and_the_survey_default_fills_a_missing_part():
    df, notes = _prepare(OLD, NEW)
    assert list(df["participant_id"]) == ["134014", "144153"]
    assert any("144" in n and "studyID" in n and "1 row" in n and "experiment 2" in n for n in notes)


def test_the_survey_default_only_fills_an_experiment_that_never_stores_the_field():
    """An experiment that does store studyID but lacks it in one row has a missing value, not a hidden field."""
    df, notes = _prepare(OLD, dict(OLD, studyID="", subID="15"), NEW)
    assert list(df["participant_id"]) == ["134014", "144153"]
    assert "1 row(s) dropped: no studyID" in notes


def test_session_is_the_text_the_participant_saw():
    df, _notes = _prepare(OLD, NEW)
    assert list(df["session"]) == ["1", "2"]


def test_rows_without_answers_or_without_an_id_are_dropped_and_counted_but_incomplete_rows_with_answers_stay():
    empty = dict(experimentId="1", studyID="134", subID="14", sesID="Item 1")  # the second, empty duplicate
    no_id = dict(OLD, subID="")
    df, notes = _prepare(OLD, empty, no_id)
    assert list(df["participant_id"]) == ["134014"] and df.loc[0, "ARSQ1"] == "2"  # OLD is isComplete=FALSE and stays
    assert "1 row(s) dropped: no answers" in notes and "1 row(s) dropped: no subID" in notes


def test_a_session_or_id_part_that_cannot_be_read_skips_the_row_with_a_note():
    df, notes = _prepare(OLD, dict(OLD, sesID="Item 7"), dict(OLD, subID="134001"), dict(OLD, subID="x"))
    assert len(df) == 1
    assert any("Item 7" in n for n in notes) and any("134001" in n for n in notes) and any("'x'" in n for n in notes)


def test_two_different_answers_for_one_question_keep_the_plain_column_and_are_reported():
    df, notes = _prepare(dict(OLD, **{"block/ARSQ1": "5"}))
    assert df.loc[0, "ARSQ1"] == "2" and any("ARSQ1" in n and "differ" in n for n in notes)


def test_a_row_whose_answers_are_all_in_another_row_of_the_same_participant_and_session_is_dropped():
    partial = dict(experimentId="1", studyID="134", subID="14", sesID="Item 1", ARSQ1="2", question3="weniger")
    df, notes = _prepare(partial, OLD, dict(OLD))  # a partial, the full row, an identical copy of it
    assert len(df) == 1 and df.loc[0, "ARSQ2"] == "3"
    assert "2 row(s) dropped: all answers are in another row of the same participant and session" in notes


def test_two_attempts_with_different_answers_are_both_kept_and_reported():
    df, notes = _prepare(OLD, dict(OLD, ARSQ1="5"))
    assert len(df) == 2
    assert any("134014" in n and "session 1" in n and "different answers" in n for n in notes)


def test_rows_are_ordered_by_response_date_so_keep_first_and_keep_last_mean_earliest_and_latest():
    df, _notes = _prepare(dict(OLD, responseDate="2025-01-02", ARSQ1="5"), dict(OLD, responseDate="2025-01-01", ARSQ1="1"))
    assert list(df["ARSQ1"]) == ["1", "5"]


def test_booleans_are_written_the_way_the_template_levels_are():
    df, _notes = _prepare(OLD)
    assert df.loc[0, "question1"] == "true"


def test_a_column_the_survey_does_not_know_is_reported_and_dropped():
    table = _table(OLD)
    table["mystery"] = "x"
    df, notes = prepare_pavlovia_responses(table, SURVEY, id_columns=["studyID", "subID"], id_pad=3, session_column="sesID")
    assert "mystery" not in df.columns and any("mystery" in n for n in notes)


def test_unknown_id_column_is_an_error():
    with pytest.raises(ValueError, match="nope"):
        _prepare(OLD, id_columns=["nope"])


# --- the CLI and the whole way into a PRISM dataset ------------------------------


def _write(tmp_path):
    csv = tmp_path / "responses.csv"
    _table(OLD, NEW).to_csv(csv, index=False)
    survey = tmp_path / "survey.json"
    survey.write_text(dump_complete(SURVEY), encoding="utf-8")
    return csv, survey


def test_cli_writes_the_wide_table_and_prints_the_notes(tmp_path, capsys):
    from src.cli.commands.survey import cmd_survey_prepare_pavlovia

    csv, survey = _write(tmp_path)
    out = tmp_path / "wide.csv"
    cmd_survey_prepare_pavlovia(SimpleNamespace(input=str(csv), survey=str(survey), output=str(out), id_columns="studyID,subID",
                                                id_pad=3, session_column="sesID", rename=["question3=rauchen"]))
    assert list(pd.read_csv(out, dtype=str)["participant_id"]) == ["134014", "144153"]
    assert "144" in capsys.readouterr().out


def test_the_wide_table_converts_into_a_prism_dataset(tmp_path):
    from src.converters.pavlovia_import import pavlovia_questionnaire
    from src.converters.survey import convert_survey_file_to_prism_dataset

    csv, survey_file = _write(tmp_path)
    df, _notes = _prepare(OLD, NEW)
    wide = tmp_path / "wide.csv"
    df.to_csv(wide, index=False)
    library = tmp_path / "library"
    library.mkdir()
    for key in ("p1", "p2", "p3"):
        template, _n = pavlovia_questionnaire(SURVEY, key, language="de")
        (library / f"survey-{template['Study']['TaskName']}.json").write_text(dump_complete(template), encoding="utf-8")
    convert_survey_file_to_prism_dataset(input_path=wide, library_dir=library, output_root=tmp_path / "ds",
                                         id_column="participant_id", session_column="session", session="all", unknown="warn")
    names = {p.name for p in (tmp_path / "ds").rglob("*_survey.tsv")}
    assert any(n.startswith("sub-134014_ses-1_") for n in names) and any(n.startswith("sub-144153_ses-2_") for n in names)
