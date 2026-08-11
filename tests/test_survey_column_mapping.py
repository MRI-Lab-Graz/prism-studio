import pandas as pd

from src.converters.survey_column_mapping import ColumnMapping, _match_columns_to_templates
from src.converters.survey_column_mapping import _find_near_match_candidates


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


def _panas_template():
    return {
        "panas": {
            "json": {
                "panas_1": {"Description": "item 1"},
                "panas_2": {"Description": "item 2"},
            }
        }
    }


def test_single_near_match_candidate_is_found_when_it_completes_full_item_set():
    # panas has 2 primary items; panas_1 is exactly mapped already, panas-2
    # (hyphen instead of underscore) is unmapped but near-matches panas_2 --
    # applying it would give a full 1:1 item-count match, so it's approved.
    col_to_mapping = {"panas_1": ColumnMapping(task="panas", run=None, base_item="panas_1")}

    candidates, warnings = _find_near_match_candidates(
        filtered_unknown=["panas-2"],
        templates=_panas_template(),
        selected_tasks=None,
        col_to_mapping=col_to_mapping,
    )

    assert len(candidates) == 1
    assert candidates[0]["source_column"] == "panas-2"
    assert candidates[0]["target_item"] == "panas_2"
    assert candidates[0]["task"] == "panas"
    assert warnings == []


def test_partial_item_count_match_is_rejected_with_a_warning():
    # panas has 2 primary items, neither exactly mapped. Only one near-match
    # candidate exists (panas-1) -- proposing 1 item when 2 are missing is
    # not a full 1:1 match, so it's rejected.
    candidates, warnings = _find_near_match_candidates(
        filtered_unknown=["panas-1"],
        templates=_panas_template(),
        selected_tasks=None,
        col_to_mapping={},
    )

    assert candidates == []
    assert len(warnings) == 1
    assert "ignored" in warnings[0]


def test_no_templates_returns_no_candidates():
    candidates, warnings = _find_near_match_candidates(
        filtered_unknown=["panas-2"],
        templates=None,
        selected_tasks=None,
        col_to_mapping={},
    )
    assert candidates == []
    assert warnings == []


def test_selected_tasks_scopes_which_templates_are_considered():
    col_to_mapping = {"panas_1": ColumnMapping(task="panas", run=None, base_item="panas_1")}

    candidates, _ = _find_near_match_candidates(
        filtered_unknown=["panas-2"],
        templates=_panas_template(),
        selected_tasks={"phq9"},  # panas excluded from scope
        col_to_mapping=col_to_mapping,
    )

    assert candidates == []
