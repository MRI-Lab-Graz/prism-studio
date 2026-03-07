from pathlib import Path

import pandas as pd

from src.recipes_surveys import (
    _build_combined_output_metadata,
    _coerce_value_labeled_columns_for_sav,
    _load_participants_data,
    _participant_join_key,
    _normalize_participant_id_for_join,
)


def test_normalize_participant_id_for_join_variants() -> None:
    assert _normalize_participant_id_for_join("001") == "sub-001"
    assert _normalize_participant_id_for_join("sub-002") == "sub-002"
    assert _normalize_participant_id_for_join("sub_003") == "sub-003"
    assert _normalize_participant_id_for_join(" sub004 ") == "sub-004"
    assert _normalize_participant_id_for_join("") is None


def test_load_participants_data_normalizes_ids(tmp_path: Path) -> None:
    participants_tsv = tmp_path / "participants.tsv"
    participants_tsv.write_text(
        "participant_id\tage\n"
        "001\t20\n"
        "sub-002\t21\n"
        "sub_003\t22\n"
        "\t23\n",
        encoding="utf-8",
    )

    participants_df, _participants_meta = _load_participants_data(tmp_path)

    assert participants_df is not None
    assert list(participants_df["participant_id"]) == ["sub-001", "sub-002", "sub-003"]
    assert list(participants_df["age"]) == ["20", "21", "22"]


def test_participant_join_key_matches_padded_and_plain_ids() -> None:
    assert _participant_join_key("sub-001") == "1"
    assert _participant_join_key("001") == "1"
    assert _participant_join_key("1") == "1"
    assert _participant_join_key("sub_0007") == "7"
    assert _participant_join_key("SUB-ABC") == "abc"


def test_build_combined_output_metadata_includes_participants_and_scores() -> None:
    columns = ["participant_id", "age", "sex", "pss_Total"]
    participants_meta = {
        "age": {"Description": "Age in years"},
        "sex": {
            "Description": "Biological sex",
            "Levels": {"1": "female", "2": "male"},
        },
    }
    recipe_by_id = {
        "pss": {
            "Scores": [
                {
                    "Name": "Total",
                    "Description": "Perceived stress total score",
                    "Interpretation": {"0-13": "low", "14-26": "moderate"},
                }
            ]
        }
    }

    variable_labels, value_labels, score_details = _build_combined_output_metadata(
        columns=columns,
        participants_meta=participants_meta,
        recipe_by_id=recipe_by_id,
        lang="en",
    )

    assert variable_labels["participant_id"] == "Participant identifier"
    assert variable_labels["age"] == "Age in years"
    assert variable_labels["sex"] == "Biological sex"
    assert value_labels["sex"] == {"1": "female", "2": "male"}
    assert variable_labels["pss_Total"] == "Perceived stress total score"
    assert "pss_Total" in score_details


def test_coerce_value_labeled_columns_for_sav_numeric_cast() -> None:
    df = pd.DataFrame(
        {
            "participant_id": ["sub-001", "sub-002", "sub-003"],
            "sex": ["1", "2", "n/a"],
            "education": ["5", "4", "3"],
        }
    )
    value_labels = {
        "sex": {"1": "female", "2": "male"},
        "education": {"1": "a", "2": "b", "3": "c", "4": "d", "5": "e"},
    }

    out = _coerce_value_labeled_columns_for_sav(df, value_labels)

    assert str(out["sex"].dtype) == "Int64"
    assert str(out["education"].dtype) == "Int64"
    assert out.loc[0, "sex"] == 1
    assert out.loc[1, "sex"] == 2
    assert pd.isna(out.loc[2, "sex"])
