"""Rows identical in every column except the ID are flagged (copy-paste hint)."""

import pandas as pd

from src.participants_backend import (
    find_identical_value_rows,
    format_identical_rows_warning,
    normalize_participant_mapping,
    preview_participants_merge,
)


def _df(rows):
    return pd.DataFrame(rows, columns=["participant_id", "age", "sex", "edu", "date"])


def test_identical_rows_are_grouped():
    df = _df(
        [
            ["sub-020", "41", "2", "6", "2025-01-24"],
            ["sub-021", "41", "2", "6", "2025-01-24"],
            ["sub-022", "30", "1", "4", "2025-02-01"],
        ]
    )

    assert find_identical_value_rows(df) == [["sub-020", "sub-021"]]


def test_a_difference_in_any_cell_is_not_flagged():
    df = _df(
        [
            ["sub-020", "41", "2", "6", "2025-01-24"],
            ["sub-021", "41", "2", "6", "2025-01-25"],
        ]
    )

    assert find_identical_value_rows(df) == []


def test_rows_that_are_mostly_empty_are_not_flagged():
    df = _df(
        [
            ["sub-001", "n/a", "n/a", "n/a", "2025-01-24"],
            ["sub-002", "n/a", "n/a", "n/a", "2025-01-24"],
        ]
    )

    assert find_identical_value_rows(df) == []


def test_warning_text_names_the_ids_and_is_empty_without_groups():
    assert format_identical_rows_warning([]) == ""
    text = format_identical_rows_warning([["sub-020", "sub-021"]])
    assert "sub-020 = sub-021" in text


def test_merge_preview_flags_new_row_that_copies_an_existing_one(tmp_path):
    base = _df(
        [
            ["sub-001", "41", "2", "6", "2025-01-24"],
            ["sub-002", "30", "1", "4", "2025-02-01"],
        ]
    )
    base.to_csv(tmp_path / "participants.tsv", sep="\t", index=False)
    incoming = pd.concat(
        [base, _df([["sub-003", "41", "2", "6", "2025-01-24"]])], ignore_index=True
    )
    src = tmp_path / "incoming.tsv"
    incoming.to_csv(src, sep="\t", index=False)
    mapping = normalize_participant_mapping(
        {c: c for c in ["participant_id", "age", "sex", "edu", "date"]}
    )

    payload = preview_participants_merge(tmp_path, src, mapping)

    assert payload["identical_value_rows"] == [["sub-001", "sub-003"]]
