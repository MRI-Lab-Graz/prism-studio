import pandas as pd

from src.converters.survey_participants_logic import _determine_participant_output_columns


def test_no_mapping_file_uses_only_template_columns(tmp_path):
    df = pd.DataFrame({"id": ["001"], "age": ["25"], "unrelated_col": ["x"]})

    plan = _determine_participant_output_columns(
        df=df,
        output_root=tmp_path,
        id_col="id",
        ses_col=None,
        participant_template={"age": {"Description": "Age"}},
        lsa_col_renames=None,
    )

    assert plan.extra_cols == ["age"]
    assert "unrelated_col" not in plan.extra_cols


def test_mapping_file_restricts_to_explicitly_mapped_columns(tmp_path):
    (tmp_path / "participants_mapping.json").write_text(
        """
        {
          "mappings": {
            "sociodem_income": {
              "source_column": "income",
              "standard_variable": "sociodem_income"
            }
          }
        }
        """
    )
    df = pd.DataFrame({"id": ["001"], "income": ["high"], "age": ["25"]})

    plan = _determine_participant_output_columns(
        df=df,
        output_root=tmp_path,
        id_col="id",
        ses_col=None,
        participant_template={"age": {"Description": "Age"}},
        lsa_col_renames=None,
    )

    assert plan.extra_cols == ["income"]
    assert "age" not in plan.extra_cols


def test_id_and_session_columns_are_never_included_as_extra_cols(tmp_path):
    df = pd.DataFrame({"id": ["001"], "ses": ["1"], "age": ["25"]})

    plan = _determine_participant_output_columns(
        df=df,
        output_root=tmp_path,
        id_col="id",
        ses_col="ses",
        participant_template={"id": {}, "ses": {}, "age": {"Description": "Age"}},
        lsa_col_renames=None,
    )

    assert "id" not in plan.extra_cols
    assert "ses" not in plan.extra_cols


def test_lsa_col_renames_fallback_finds_mangled_column_name(tmp_path):
    # No mapping file, template expects "age" but the LSA-mangled source
    # column is "AGEQ1" -- lsa_col_renames says AGEQ1 -> age.
    df = pd.DataFrame({"id": ["001"], "AGEQ1": ["25"]})

    plan = _determine_participant_output_columns(
        df=df,
        output_root=tmp_path,
        id_col="id",
        ses_col=None,
        participant_template={"age": {"Description": "Age"}},
        lsa_col_renames={"AGEQ1": "age"},
    )

    assert plan.extra_cols == ["AGEQ1"]
    assert plan.col_output_names["AGEQ1"] == "age"


from src.converters.survey_participants_logic import (
    ParticipantColumnPlan,
    _build_participant_output_dataframe,
)


def _identity_normalize_sub(val):
    return f"sub-{val}"


def _never_missing(val):
    return False


def test_builds_participant_id_column_from_normalized_id():
    df = pd.DataFrame({"id": ["001", "002"]})
    column_plan = ParticipantColumnPlan(
        extra_cols=[], col_output_names={}, mapping_descriptions={},
        value_mappings={}, template_norm=None,
    )

    result = _build_participant_output_dataframe(
        df=df, id_col="id", normalize_sub_fn=_identity_normalize_sub,
        is_missing_fn=_never_missing, missing_token="n/a", column_plan=column_plan,
    )

    assert list(result["participant_id"]) == ["sub-001", "sub-002"]


def test_extra_columns_are_included_and_renamed():
    df = pd.DataFrame({"id": ["001"], "income": ["high"]})
    column_plan = ParticipantColumnPlan(
        extra_cols=["income"], col_output_names={"income": "sociodem_income"},
        mapping_descriptions={}, value_mappings={}, template_norm=None,
    )

    result = _build_participant_output_dataframe(
        df=df, id_col="id", normalize_sub_fn=_identity_normalize_sub,
        is_missing_fn=_never_missing, missing_token="n/a", column_plan=column_plan,
    )

    assert list(result["sociodem_income"]) == ["high"]


def test_missing_values_become_the_missing_token():
    df = pd.DataFrame({"id": ["001"], "income": [""]})
    column_plan = ParticipantColumnPlan(
        extra_cols=["income"], col_output_names={"income": "income"},
        mapping_descriptions={}, value_mappings={}, template_norm=None,
    )

    result = _build_participant_output_dataframe(
        df=df, id_col="id", normalize_sub_fn=_identity_normalize_sub,
        is_missing_fn=lambda v: v == "", missing_token="n/a", column_plan=column_plan,
    )

    assert list(result["income"]) == ["n/a"]


def test_value_mapping_transforms_values():
    df = pd.DataFrame({"id": ["001"], "sex": ["1"]})
    column_plan = ParticipantColumnPlan(
        extra_cols=["sex"], col_output_names={"sex": "sex"},
        mapping_descriptions={}, value_mappings={"sex": {"1": "male", "2": "female"}},
        template_norm=None,
    )

    result = _build_participant_output_dataframe(
        df=df, id_col="id", normalize_sub_fn=_identity_normalize_sub,
        is_missing_fn=_never_missing, missing_token="n/a", column_plan=column_plan,
    )

    assert list(result["sex"]) == ["male"]


def test_duplicate_participant_ids_are_deduplicated():
    df = pd.DataFrame({"id": ["001", "001"], "income": ["high", "low"]})
    column_plan = ParticipantColumnPlan(
        extra_cols=["income"], col_output_names={"income": "income"},
        mapping_descriptions={}, value_mappings={}, template_norm=None,
    )

    result = _build_participant_output_dataframe(
        df=df, id_col="id", normalize_sub_fn=_identity_normalize_sub,
        is_missing_fn=_never_missing, missing_token="n/a", column_plan=column_plan,
    )

    assert len(result) == 1


from src.converters.survey_participants_logic import _merge_with_existing_participants_tsv


def test_no_existing_file_returns_df_part_unchanged(tmp_path):
    df_part = pd.DataFrame({"participant_id": ["sub-001"], "age": ["25"]})
    result = _merge_with_existing_participants_tsv(
        df_part=df_part, participants_tsv_path=tmp_path / "participants.tsv"
    )
    assert result.equals(df_part)


def test_new_values_preferred_over_existing_for_overlapping_participant(tmp_path):
    tsv_path = tmp_path / "participants.tsv"
    tsv_path.write_text("participant_id\tage\nsub-001\t25\n")
    df_part = pd.DataFrame({"participant_id": ["sub-001"], "age": ["26"]})

    result = _merge_with_existing_participants_tsv(
        df_part=df_part, participants_tsv_path=tsv_path
    )

    row = result[result["participant_id"] == "sub-001"].iloc[0]
    assert row["age"] == "26"


def test_existing_participants_not_in_new_data_are_kept(tmp_path):
    tsv_path = tmp_path / "participants.tsv"
    tsv_path.write_text("participant_id\tage\nsub-999\t40\n")
    df_part = pd.DataFrame({"participant_id": ["sub-001"], "age": ["25"]})

    result = _merge_with_existing_participants_tsv(
        df_part=df_part, participants_tsv_path=tsv_path
    )

    assert "sub-999" in list(result["participant_id"])
    assert "sub-001" in list(result["participant_id"])


def test_existing_file_without_participant_id_column_is_left_unmerged(tmp_path):
    tsv_path = tmp_path / "participants.tsv"
    tsv_path.write_text("subject\tage\nsub-001\t25\n")
    df_part = pd.DataFrame({"participant_id": ["sub-002"], "age": ["30"]})

    result = _merge_with_existing_participants_tsv(
        df_part=df_part, participants_tsv_path=tsv_path
    )

    assert result.equals(df_part)


def test_unreadable_existing_file_falls_back_to_df_part(tmp_path, capsys, monkeypatch):
    # NOTE: the brief's original fixture used a file with an embedded null
    # byte, on the theory that it would fail pandas' C parser. Verified on
    # this pandas version that it does NOT raise (pandas parses it as a
    # normal, if odd, TSV row). A follow-up chmod(0o000)-based fixture was
    # also tried and rejected on review: root ignores permission bits, so
    # under a root-executed CI container pd.read_csv would silently succeed
    # instead of raising, making the test's outcome depend on which user
    # runs pytest. Monkeypatching pandas.read_csv to raise directly forces
    # the except-Exception fallback path deterministically on every OS/user.
    tsv_path = tmp_path / "participants.tsv"
    tsv_path.write_text("participant_id\tage\nsub-001\t25\n")
    df_part = pd.DataFrame({"participant_id": ["sub-001"], "age": ["25"]})

    def _raise(*args, **kwargs):
        raise ValueError("simulated read_csv failure")

    monkeypatch.setattr("pandas.read_csv", _raise)

    result = _merge_with_existing_participants_tsv(
        df_part=df_part, participants_tsv_path=tsv_path
    )

    assert result.equals(df_part)
    assert "Could not merge" in capsys.readouterr().out
