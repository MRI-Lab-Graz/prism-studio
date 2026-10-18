"""Exported tables keep numbers numeric (xlsx) and SPSS names unique (sav)."""

import pandas as pd

from src.recipes_export_helpers import _build_spss_rename_map, numbers_as_numbers


def test_numeric_columns_become_numbers_and_empty_cells_stay_empty():
    df = pd.DataFrame({
        "participant_id": ["sub-1", "sub-2", "sub-3"],
        "session": ["ses-1", "ses-1", "ses-2"],
        "Total": ["9", "11", pd.NA],
        "Mean": ["1.5", "2,5", "-3e2"],
        "Group": ["a", "b", "c"],
        "Code": ["007", "012", "100"],
    })
    out = numbers_as_numbers(df)
    assert out["Total"].tolist()[:2] == [9, 11] and pd.isna(out["Total"].iloc[2])
    assert out["Mean"].tolist() == [1.5, 2.5, -300.0]
    assert out["Group"].tolist() == ["a", "b", "c"]
    assert out["Code"].tolist() == ["007", "012", "100"]  # leading zeros are labels, not numbers
    assert out["participant_id"].tolist() == ["sub-1", "sub-2", "sub-3"]
    assert out["session"].tolist() == ["ses-1", "ses-1", "ses-2"]


def test_a_column_with_a_text_marker_is_left_alone():
    df = pd.DataFrame({"Total": ["9", "n/a", "3"]})
    assert numbers_as_numbers(df)["Total"].tolist() == ["9", "n/a", "3"]


def test_spss_names_differing_only_in_case_are_made_unique():
    renames = _build_spss_rename_map(["Total", "total", "TOTAL"])
    final = [renames.get(c, c) for c in ["Total", "total", "TOTAL"]]
    assert len({n.lower() for n in final}) == 3


def test_long_names_with_the_same_first_64_characters_stay_unique():
    a, b = "x" * 70 + "A", "x" * 70 + "B"
    renames = _build_spss_rename_map([a, b])
    assert len({renames.get(c, c).lower() for c in (a, b)}) == 2
    assert all(len(v) <= 64 for v in renames.values())
