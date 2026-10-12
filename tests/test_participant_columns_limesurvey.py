"""LimeSurvey system columns are platform metadata, never participant data."""

import pandas as pd

from src.participant_columns import _filter_participant_relevant_columns

LS_COLUMNS = [
    "id", "submitdate", "lastpage", "startlanguage", "startdate", "datestamp",
    "token", "Hand", "age",
]


def test_system_columns_are_not_offered_as_participant_columns(tmp_path):
    df = pd.DataFrame([["1"] * len(LS_COLUMNS)], columns=LS_COLUMNS)

    selected = _filter_participant_relevant_columns(df, "token", tmp_path)

    assert selected == ["token", "Hand", "age"]
