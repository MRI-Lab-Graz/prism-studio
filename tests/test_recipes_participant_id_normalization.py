from pathlib import Path

import pandas as pd

from src.recipes_surveys import (
    _build_sav_value_labels,
    _build_spss_rename_map,
    _build_combined_output_metadata,
    _coerce_value_labeled_columns_for_sav,
    _prepare_dataframe_for_sav,
    compute_survey_recipes,
    _load_participants_data,
    _participant_join_key,
    _normalize_participant_id_for_join,
    _sanitize_spss_variable_name,
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
        "participant_id\tage\n001\t20\nsub-002\t21\nsub_003\t22\n\t23\n",
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


def test_prepare_dataframe_for_sav_handles_missing_and_decimal_comma() -> None:
    df = pd.DataFrame(
        {
            "participant_id": ["sub-001", "sub-002", "sub-003"],
            "score": ["3,14", "n/a", "2.5"],
            "age": ["20", "NA", "30"],
            "note": ["ok", "n/a", "hello"],
        }
    )

    out = _prepare_dataframe_for_sav(df)

    assert str(out["score"].dtype) == "float64"
    assert out.loc[0, "score"] == 3.14
    assert pd.isna(out.loc[1, "score"])
    assert out.loc[2, "score"] == 2.5

    assert str(out["age"].dtype) == "Int64"
    assert out.loc[0, "age"] == 20
    assert pd.isna(out.loc[1, "age"])
    assert out.loc[2, "age"] == 30

    assert pd.isna(out.loc[1, "note"])


def test_prepare_dataframe_for_sav_preserves_leading_zero_codes() -> None:
    df = pd.DataFrame({"code": ["001", "010", "200"]})

    out = _prepare_dataframe_for_sav(df)

    assert str(out["code"].dtype) in {"object", "string", "str"}
    assert out["code"].tolist() == ["001", "010", "200"]


def test_prepare_dataframe_for_sav_keeps_mixed_text_numeric_columns_as_text() -> None:
    df = pd.DataFrame({"mixed": ["3,14", "alpha", "2.5"]})

    out = _prepare_dataframe_for_sav(df)

    assert str(out["mixed"].dtype) in {"object", "string", "str"}
    assert out["mixed"].tolist() == ["3,14", "alpha", "2.5"]


def test_sanitize_spss_variable_name_prefixes_leading_digits() -> None:
    assert _sanitize_spss_variable_name("20D_item1") == "v_20D_item1"
    assert _sanitize_spss_variable_name("item-1.2 3") == "item_1_2_3"


def test_sanitize_spss_variable_name_preserves_unicode_letters() -> None:
    assert _sanitize_spss_variable_name("Händigkeit") == "Händigkeit"
    assert _sanitize_spss_variable_name("größe-ä") == "größe_ä"


def test_build_spss_rename_map_handles_collisions() -> None:
    rename_map = _build_spss_rename_map(["a-b", "a.b", "20D_item1", "ok_name"])

    assert rename_map["a-b"] == "a_b"
    assert rename_map["a.b"] == "a_b_2"
    assert rename_map["20D_item1"] == "v_20D_item1"
    assert "ok_name" not in rename_map


def test_build_sav_value_labels_handles_numeric_and_text_columns() -> None:
    df = pd.DataFrame(
        {
            "score": [1.5, 2.0],
            "group": ["low", "high"],
        }
    )

    value_labels = {
        "score": {"1,5": "Low", "2": "High", "n/a": "Missing"},
        "group": {"low": "Lower", "high": "Higher"},
    }

    labels = _build_sav_value_labels(
        df=df,
        value_labels=value_labels,
        rename_map={},
    )

    assert labels["score"] == {1.5: "Low", 2.0: "High"}
    assert labels["group"] == {"low": "Lower", "high": "Higher"}


def _write_minimal_recipe(path: Path, task_name: str) -> None:
    path.write_text(
        (
            "{\n"
            '  "Kind": "survey",\n'
            '  "RecipeVersion": "1.0",\n'
            f'  "Survey": {{"TaskName": "{task_name}"}},\n'
            '  "Scores": [\n'
            '    {"Name": "Total", "Method": "sum", "Items": ["Q1"]}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )


def _write_formula_recipe(path: Path, task_name: str, score_name: str, formula: str, items: list[str]) -> None:
    items_text = ", ".join(f'"{item}"' for item in items)
    path.write_text(
        (
            "{\n"
            '  "Kind": "survey",\n'
            '  "RecipeVersion": "1.0",\n'
            f'  "Survey": {{"TaskName": "{task_name}"}},\n'
            '  "Scores": [\n'
            "    {"
            f'"Name": "{score_name}", '
            '"Method": "formula", '
            f'"Items": [{items_text}], '
            f'"Formula": "{formula}"'
            "}\n"
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )


def test_merge_all_exports_participant_columns(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    recipe_dir = tmp_path / "recipes"
    project_root.mkdir(parents=True)
    recipe_dir.mkdir(parents=True)

    (project_root / "participants.tsv").write_text(
        "participant_id\tage\nsub-001\t20\nsub-002\t30\n",
        encoding="utf-8",
    )

    subject_a_dir = project_root / "sub-001" / "ses-1" / "survey"
    subject_a_dir.mkdir(parents=True)
    (subject_a_dir / "sub-001_ses-1_task-aaa_survey.tsv").write_text(
        "Q1\n1\n",
        encoding="utf-8",
    )

    subject_b_dir = project_root / "sub-002" / "ses-1" / "survey"
    subject_b_dir.mkdir(parents=True)
    (subject_b_dir / "sub-002_ses-1_task-bbb_survey.tsv").write_text(
        "Q1\n2\n",
        encoding="utf-8",
    )

    _write_minimal_recipe(recipe_dir / "recipe-aaa.json", "aaa")
    _write_minimal_recipe(recipe_dir / "recipe-bbb.json", "bbb")

    result = compute_survey_recipes(
        prism_root=project_root,
        repo_root=tmp_path,
        recipe_dir=recipe_dir,
        modality="survey",
        out_format="csv",
        merge_all=True,
    )

    combined_csv = result.out_root / "combined_survey.csv"
    assert combined_csv.exists()

    out_df = pd.read_csv(combined_csv, dtype=str)
    assert "age" in out_df.columns
    assert set(out_df["age"].dropna()) == {"20", "30"}
    assert "aaa_Total" in out_df.columns
    assert "bbb_Total" in out_df.columns


def test_per_recipe_export_includes_participant_columns(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    recipe_dir = tmp_path / "recipes"
    project_root.mkdir(parents=True)
    recipe_dir.mkdir(parents=True)

    (project_root / "participants.tsv").write_text(
        "participant_id\tage\nsub-001\t21\n",
        encoding="utf-8",
    )

    survey_dir = project_root / "sub-001" / "ses-1" / "survey"
    survey_dir.mkdir(parents=True)
    (survey_dir / "sub-001_ses-1_task-aaa_survey.tsv").write_text(
        "Q1\n4\n",
        encoding="utf-8",
    )

    _write_minimal_recipe(recipe_dir / "recipe-aaa.json", "aaa")

    result = compute_survey_recipes(
        prism_root=project_root,
        repo_root=tmp_path,
        recipe_dir=recipe_dir,
        modality="survey",
        out_format="csv",
        merge_all=False,
    )

    out_csv = result.out_root / "aaa.csv"
    out_df = pd.read_csv(out_csv, dtype=str)

    assert "age" in out_df.columns
    assert out_df.loc[0, "age"] == "21"


def test_merge_all_formula_uses_participant_values_from_participants_tsv(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    recipe_dir = tmp_path / "recipes"
    project_root.mkdir(parents=True)
    recipe_dir.mkdir(parents=True)

    (project_root / "participants.tsv").write_text(
        "participant_id\tage\nsub-001\t40\n",
        encoding="utf-8",
    )

    survey_dir = project_root / "sub-001" / "ses-1" / "survey"
    survey_dir.mkdir(parents=True)
    (survey_dir / "sub-001_ses-1_task-aaa_survey.tsv").write_text(
        "Q1\n1\n",
        encoding="utf-8",
    )

    _write_formula_recipe(
        recipe_dir / "recipe-aaa.json",
        task_name="aaa",
        score_name="AgeEcho",
        formula="{age}",
        items=["age"],
    )

    result = compute_survey_recipes(
        prism_root=project_root,
        repo_root=tmp_path,
        recipe_dir=recipe_dir,
        modality="survey",
        out_format="csv",
        merge_all=True,
    )

    combined_csv = result.out_root / "combined_survey.csv"
    assert combined_csv.exists()

    out_df = pd.read_csv(combined_csv, dtype=str)
    assert out_df.loc[0, "aaa_AgeEcho"] == "40"


def test_merge_all_include_raw_exports_missing_recipe_task_as_raw_only(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    recipe_dir = tmp_path / "recipes"
    project_root.mkdir(parents=True)
    recipe_dir.mkdir(parents=True)

    survey_dir = project_root / "sub-001" / "ses-1" / "survey"
    survey_dir.mkdir(parents=True)
    (survey_dir / "sub-001_ses-1_task-aaa_survey.tsv").write_text(
        "Q1\n1\n",
        encoding="utf-8",
    )
    (survey_dir / "sub-001_ses-1_task-ccc_survey.tsv").write_text(
        "Q1\n7\n",
        encoding="utf-8",
    )

    _write_minimal_recipe(recipe_dir / "recipe-aaa.json", "aaa")

    result = compute_survey_recipes(
        prism_root=project_root,
        repo_root=tmp_path,
        recipe_dir=recipe_dir,
        modality="survey",
        out_format="csv",
        include_raw=True,
        merge_all=True,
    )

    combined_csv = result.out_root / "combined_survey.csv"
    out_df = pd.read_csv(combined_csv, dtype=str)

    assert result.written_recipe_ids == ("aaa",)
    assert result.missing_input_tasks == ("ccc",)
    assert result.raw_only_tasks == ("ccc",)
    assert "ccc_Q1" in out_df.columns
    assert out_df.loc[0, "ccc_Q1"] == "7"


def test_include_raw_allows_export_when_recipe_directory_is_empty(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    recipe_dir = tmp_path / "recipes"
    project_root.mkdir(parents=True)
    recipe_dir.mkdir(parents=True)

    survey_dir = project_root / "sub-001" / "ses-1" / "survey"
    survey_dir.mkdir(parents=True)
    (survey_dir / "sub-001_ses-1_task-aaa_survey.tsv").write_text(
        "Q1\n5\n",
        encoding="utf-8",
    )

    result = compute_survey_recipes(
        prism_root=project_root,
        repo_root=tmp_path,
        recipe_dir=recipe_dir,
        modality="survey",
        out_format="csv",
        include_raw=True,
        merge_all=True,
    )

    combined_csv = result.out_root / "combined_survey.csv"
    out_df = pd.read_csv(combined_csv, dtype=str)

    assert combined_csv.exists()
    assert result.written_recipe_ids == ()
    assert result.missing_input_tasks == ("aaa",)
    assert result.raw_only_tasks == ("aaa",)
    assert "aaa_Q1" in out_df.columns
    assert out_df.loc[0, "aaa_Q1"] == "5"
