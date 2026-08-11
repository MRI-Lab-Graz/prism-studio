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
