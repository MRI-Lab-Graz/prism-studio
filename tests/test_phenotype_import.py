from __future__ import annotations

import json

import pandas as pd

from src.converters.phenotype_import import (
    flag_non_item_columns,
    import_phenotype_directory,
    import_phenotype_file,
    sanitize_task_name_from_phenotype_filename,
)


def test_sanitize_task_name_keeps_hyphens_and_lowercases():
    assert sanitize_task_name_from_phenotype_filename("Wellbeing_Multi") == "wellbeing-multi"


def test_sanitize_task_name_strips_desc_suffix():
    assert sanitize_task_name_from_phenotype_filename("demographics_desc-baseline") == "demographics"


def test_sanitize_task_name_strips_disallowed_characters():
    assert sanitize_task_name_from_phenotype_filename("A survey!! (v2)") == "a-survey-v2"


def test_sanitize_task_name_falls_back_when_empty():
    assert sanitize_task_name_from_phenotype_filename("___") == "phenotype"


def test_flag_non_item_columns_matches_stoplist():
    flagged = flag_non_item_columns(["WB01", "age", "WB02", "handedness"])
    assert flagged == ["age", "handedness"]


def test_import_phenotype_file_with_session_column(tmp_path):
    phenotype_dir = tmp_path / "phenotype"
    phenotype_dir.mkdir()
    tsv_path = phenotype_dir / "wellbeing.tsv"
    pd.DataFrame(
        [
            {"participant_id": "sub-01", "session_id": "ses-01", "WB01": 3, "WB02": 4},
            {"participant_id": "sub-02", "session_id": "ses-01", "WB01": 5, "WB02": 2},
        ]
    ).to_csv(tsv_path, sep="\t", index=False, lineterminator="\n")

    project_root = tmp_path / "project"
    project_root.mkdir()

    summary = import_phenotype_file(tsv_path, project_root)

    out_tsv = (
        project_root
        / "sub-01"
        / "ses-01"
        / "survey"
        / "sub-01_ses-01_task-wellbeing_survey.tsv"
    )
    assert out_tsv.is_file()
    out_df = pd.read_csv(out_tsv, sep="\t", dtype=str)
    assert list(out_df.columns) == ["WB01", "WB02"]
    assert out_df.iloc[0]["WB01"] == "3"

    sidecar_path = project_root / "task-wellbeing_survey.json"
    assert sidecar_path.is_file()
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["Study"]["TaskName"] == "wellbeing"
    assert "WB01" in sidecar

    assert summary.imported_task_count == 1


def test_import_phenotype_file_without_session_column_synthesizes_session(tmp_path):
    phenotype_dir = tmp_path / "phenotype"
    phenotype_dir.mkdir()
    tsv_path = phenotype_dir / "demographics.tsv"
    pd.DataFrame([{"participant_id": "sub-01", "age": 30}]).to_csv(
        tsv_path, sep="\t", index=False, lineterminator="\n"
    )

    project_root = tmp_path / "project"
    project_root.mkdir()

    summary = import_phenotype_file(tsv_path, project_root)

    out_tsv = (
        project_root
        / "sub-01"
        / "ses-import"
        / "survey"
        / "sub-01_ses-import_task-demographics_survey.tsv"
    )
    assert out_tsv.is_file()
    assert any("ses-import" in entry["message"] for entry in summary.log)
    assert "age" in summary.flagged_columns


def test_import_phenotype_file_uses_sidecar_description_and_levels(tmp_path):
    phenotype_dir = tmp_path / "phenotype"
    phenotype_dir.mkdir()
    tsv_path = phenotype_dir / "wellbeing.tsv"
    pd.DataFrame(
        [{"participant_id": "sub-01", "session_id": "ses-01", "WB01": 3}]
    ).to_csv(tsv_path, sep="\t", index=False, lineterminator="\n")
    json_path = phenotype_dir / "wellbeing.json"
    json_path.write_text(
        json.dumps({"WB01": {"Description": "How happy are you?", "Levels": {"1": "Low"}}}),
        encoding="utf-8",
    )

    project_root = tmp_path / "project"
    project_root.mkdir()

    import_phenotype_file(tsv_path, project_root, json_path=json_path)

    sidecar = json.loads(
        (project_root / "task-wellbeing_survey.json").read_text(encoding="utf-8")
    )
    assert sidecar["WB01"]["Description"] == "How happy are you?"
    assert sidecar["WB01"]["Levels"] == {"1": "Low"}


def test_import_phenotype_file_skips_rows_with_bad_participant_id(tmp_path):
    phenotype_dir = tmp_path / "phenotype"
    phenotype_dir.mkdir()
    tsv_path = phenotype_dir / "wellbeing.tsv"
    pd.DataFrame(
        [
            {"participant_id": "sub-01", "session_id": "ses-01", "WB01": 3},
            {"participant_id": "not-a-subject", "session_id": "ses-01", "WB01": 9},
        ]
    ).to_csv(tsv_path, sep="\t", index=False, lineterminator="\n")

    project_root = tmp_path / "project"
    project_root.mkdir()

    summary = import_phenotype_file(tsv_path, project_root)

    assert (project_root / "sub-01").is_dir()
    assert not (project_root / "not-a-subject").exists()
    assert any("Skipped row" in entry["message"] for entry in summary.log)


def test_import_phenotype_directory_imports_all_files(tmp_path):
    phenotype_dir = tmp_path / "phenotype"
    phenotype_dir.mkdir()
    pd.DataFrame(
        [{"participant_id": "sub-01", "session_id": "ses-01", "WB01": 1}]
    ).to_csv(phenotype_dir / "wellbeing.tsv", sep="\t", index=False, lineterminator="\n")
    pd.DataFrame(
        [{"participant_id": "sub-01", "session_id": "ses-01", "PHQ01": 2}]
    ).to_csv(phenotype_dir / "phq9.tsv", sep="\t", index=False, lineterminator="\n")

    project_root = tmp_path / "project"
    project_root.mkdir()

    summary = import_phenotype_directory(phenotype_dir, project_root)

    assert summary.imported_task_count == 2
    assert (project_root / "task-wellbeing_survey.json").is_file()
    assert (project_root / "task-phq9_survey.json").is_file()
    assert summary.log[0]["message"].startswith("Detected phenotype/ directory")
