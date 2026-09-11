"""Tests for the generic Presentation (.log) parser.

Uses a small synthetic log rather than the real study fixtures under
.pytest_cache/data/ -- those cover the task-specific decoder instead
(tests/test_presentation_tasks_nemo_nid.py).
"""

import pandas as pd
import pytest

from src.converters.presentation_log import (
    extract_subject_id,
    parse_presentation_log,
    parse_sce_metadata,
)

SAMPLE_LOG = """Scenario -\t
Logfile written - 05/04/2012 13:58:56

Subject\tTrial\tEvent Type\tCode\tTime\tTTime\tUncertainty\tDuration\tUncertainty\tReqTime\tReqDur\tStim Type\tPair Index

nemo_01\t1\tPulse\t55\t100000\t0\t1
nemo_01\t2\tPicture\tfixation\t100500\t0\t2\t50000\t3\t0\t50000\tother\t0
nemo_01\t2\tPulse\t55\t130000\t29500\t1
nemo_01\t3\tPicture\tItem_1_1\t150500\t0\t1\t20000\t2\t0\t600000\tfalse_alarm\t11
nemo_01\t3\tResponse\t44\t155500\t5000\t1
"""


def test_onset_aligned_to_first_pulse():
    df = parse_presentation_log(SAMPLE_LOG)
    assert df.iloc[0]["onset"] == pytest.approx(0.05)


def test_pulse_rows_are_excluded_from_output():
    df = parse_presentation_log(SAMPLE_LOG)
    assert len(df) == 2
    assert list(df["raw_code"]) == ["fixation", "Item_1_1"]


def test_duration_converted_to_seconds():
    df = parse_presentation_log(SAMPLE_LOG)
    assert df.iloc[0]["duration"] == pytest.approx(5.0)


def test_response_merged_onto_preceding_stimulus_row():
    df = parse_presentation_log(SAMPLE_LOG)
    item_row = df.iloc[1]
    assert item_row["raw_code"] == "Item_1_1"
    assert item_row["response_time_ms"] == pytest.approx(500.0)
    assert item_row["response_button_code"] == "44"


def test_row_without_response_has_null_response_fields():
    df = parse_presentation_log(SAMPLE_LOG)
    fixation_row = df.iloc[0]
    assert pd.isna(fixation_row["response_time_ms"])
    assert pd.isna(fixation_row["response_button_code"])


def test_trial_number_is_carried_through():
    df = parse_presentation_log(SAMPLE_LOG)
    assert list(df["trial_number"]) == [2, 3]


def test_parse_sce_metadata_extracts_pulse_and_button_codes():
    sce_text = "active_buttons = 3;\nbutton_codes = 1,2,44;\npulse_code = 55;\n"
    meta = parse_sce_metadata(sce_text)
    assert meta["pulse_code"] == 55
    assert meta["button_codes"] == [1, 2, 44]
    assert meta["active_buttons"] == 3


def test_parse_sce_metadata_missing_fields_are_none():
    meta = parse_sce_metadata("scenario_type = fMRI;\n")
    assert meta["pulse_code"] is None
    assert meta["button_codes"] == []
    assert meta["active_buttons"] is None


def test_extract_subject_id_reads_first_data_row():
    # NID.pcl's customLog files are named "<this exact string>.txt"
    # (customLog.open("log\\" + subjectId + ".txt")) -- this is the join key
    # for attaching that ground-truth data back onto the parsed events.
    assert extract_subject_id(SAMPLE_LOG) == "nemo_01"


def test_extract_subject_id_missing_returns_none():
    assert extract_subject_id("Subject\tTrial\tEvent Type\tCode\tTime\tTTime\n") is None


def test_quit_event_excluded_and_warns():
    # Real data: an experimenter can abort a session early (Presentation's
    # "Quit" system event, e.g. sub-NEMO67), leaving an empty-Code row that
    # is not a stimulus event -- exclude it like Pulse, but don't let a
    # truncated run go unnoticed.
    log_text = SAMPLE_LOG + "nemo_01\t4\tQuit\t\t200000\t605250\n"
    with pytest.warns(UserWarning, match="Quit"):
        df = parse_presentation_log(log_text)
    assert len(df) == 2
