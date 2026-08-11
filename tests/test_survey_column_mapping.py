import pandas as pd

from src.converters.survey_column_mapping import ColumnMapping, _match_columns_to_templates


def test_exact_match_maps_column_to_task():
    df = pd.DataFrame({"id": ["001"], "panas_1": ["3"]})

    col_to_mapping, unknown_cols, task_run_tracker = _match_columns_to_templates(
        df=df,
        item_to_task={"panas_1": "panas"},
        participant_columns_lower=set(),
        id_col="id",
        ses_col=None,
        run_col=None,
    )

    assert col_to_mapping["panas_1"] == ColumnMapping(task="panas", run=None, base_item="panas_1")
    assert unknown_cols == []
    assert task_run_tracker == {"panas": {None}}


def test_run_suffixed_column_matches_base_item():
    df = pd.DataFrame({"id": ["001"], "panas_1_run-02": ["3"]})

    col_to_mapping, unknown_cols, task_run_tracker = _match_columns_to_templates(
        df=df,
        item_to_task={"panas_1": "panas"},
        participant_columns_lower=set(),
        id_col="id",
        ses_col=None,
        run_col=None,
    )

    assert col_to_mapping["panas_1_run-02"] == ColumnMapping(task="panas", run=2, base_item="panas_1")
    assert task_run_tracker == {"panas": {2}}


def test_unmatched_column_becomes_unknown():
    df = pd.DataFrame({"id": ["001"], "mystery_col": ["x"]})

    col_to_mapping, unknown_cols, task_run_tracker = _match_columns_to_templates(
        df=df,
        item_to_task={},
        participant_columns_lower=set(),
        id_col="id",
        ses_col=None,
        run_col=None,
    )

    assert col_to_mapping == {}
    assert unknown_cols == ["mystery_col"]


def test_participant_column_is_skipped_not_treated_as_unknown():
    df = pd.DataFrame({"id": ["001"], "age": ["25"]})

    col_to_mapping, unknown_cols, task_run_tracker = _match_columns_to_templates(
        df=df,
        item_to_task={},
        participant_columns_lower={"age"},
        id_col="id",
        ses_col=None,
        run_col=None,
    )

    assert col_to_mapping == {}
    assert unknown_cols == []


def test_id_and_session_and_run_columns_are_excluded_from_matching():
    df = pd.DataFrame({"id": ["001"], "ses": ["1"], "run": ["1"], "panas_1": ["3"]})

    col_to_mapping, unknown_cols, task_run_tracker = _match_columns_to_templates(
        df=df,
        item_to_task={"panas_1": "panas"},
        participant_columns_lower=set(),
        id_col="id",
        ses_col="ses",
        run_col="run",
    )

    assert "id" not in col_to_mapping and "id" not in unknown_cols
    assert "ses" not in col_to_mapping and "ses" not in unknown_cols
    assert "run" not in col_to_mapping and "run" not in unknown_cols
