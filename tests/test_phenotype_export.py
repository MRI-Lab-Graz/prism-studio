from __future__ import annotations

import json

import pandas as pd

from src.converters.phenotype_export import (
    build_phenotype_sidecar,
    collect_phenotype_bridge_files,
)


def _write_survey_tsv(base, subject, session, task, variant, values):
    survey_dir = base / f"sub-{subject}" / f"ses-{session}" / "survey"
    survey_dir.mkdir(parents=True, exist_ok=True)
    acq_part = f"_acq-{variant}" if variant else ""
    filename = f"sub-{subject}_ses-{session}_task-{task}{acq_part}_survey.tsv"
    df = pd.DataFrame([values])
    df.to_csv(survey_dir / filename, sep="\t", index=False, lineterminator="\n")


def _write_sidecar(base, name, content):
    (base / name).write_text(json.dumps(content), encoding="utf-8")


def test_collect_phenotype_bridge_files_single_variant(tmp_path):
    _write_survey_tsv(tmp_path, "01", "01", "wellbeing", None, {"WB01": 3, "WB02": 4})
    _write_survey_tsv(tmp_path, "02", "01", "wellbeing", None, {"WB01": 5, "WB02": 2})
    _write_sidecar(
        tmp_path,
        "task-wellbeing_survey.json",
        {
            "WB01": {"Description": "Item 1", "Levels": {"1": "Low", "5": "High"}},
            "WB02": {"Description": "Item 2"},
        },
    )

    result = collect_phenotype_bridge_files(tmp_path)

    assert result.warnings == []
    assert len(result.files) == 1
    phenotype_file = result.files[0]
    assert phenotype_file.name == "wellbeing"
    assert list(phenotype_file.dataframe.columns) == [
        "participant_id",
        "session_id",
        "WB01",
        "WB02",
    ]
    rows = phenotype_file.dataframe.set_index("participant_id")
    assert rows.loc["sub-01", "WB01"] == "3"
    assert rows.loc["sub-02", "WB02"] == "2"
    assert phenotype_file.sidecar["WB01"]["Description"] == "Item 1"
    assert phenotype_file.sidecar["WB01"]["Levels"] == {"1": "Low", "5": "High"}


def test_collect_phenotype_bridge_files_separates_variants(tmp_path):
    _write_survey_tsv(tmp_path, "01", "01", "wellbeing", "10-likert", {"WB01": 3})
    _write_survey_tsv(tmp_path, "01", "01", "wellbeing", "7-likert", {"WB01": 4})

    result = collect_phenotype_bridge_files(tmp_path)

    names = sorted(f.name for f in result.files)
    assert names == ["wellbeing-10-likert", "wellbeing-7-likert"]


def test_collect_phenotype_bridge_files_skips_duplicate_runs(tmp_path):
    survey_dir = tmp_path / "sub-01" / "ses-01" / "survey"
    survey_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"WB01": 1}]).to_csv(
        survey_dir / "sub-01_ses-01_task-wellbeing_run-1_survey.tsv",
        sep="\t",
        index=False,
        lineterminator="\n",
    )
    pd.DataFrame([{"WB01": 2}]).to_csv(
        survey_dir / "sub-01_ses-01_task-wellbeing_run-2_survey.tsv",
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    result = collect_phenotype_bridge_files(tmp_path)

    assert len(result.files) == 1
    assert any("run" in warning.lower() for warning in result.warnings)


def test_collect_phenotype_bridge_files_respects_exclusions(tmp_path):
    _write_survey_tsv(tmp_path, "01", "01", "wellbeing", None, {"WB01": 1})
    _write_survey_tsv(tmp_path, "02", "01", "wellbeing", None, {"WB01": 2})

    result = collect_phenotype_bridge_files(tmp_path, exclude_subjects={"sub-02"})

    assert len(result.files) == 1
    participant_ids = set(result.files[0].dataframe["participant_id"])
    assert participant_ids == {"sub-01"}


def test_collect_phenotype_bridge_files_no_surveys_returns_empty(tmp_path):
    result = collect_phenotype_bridge_files(tmp_path)
    assert result.files == []
    assert result.warnings == []


def test_build_phenotype_sidecar_drops_prism_specific_fields():
    variant_sidecar = {
        "WB01": {
            "Description": "Item 1",
            "Reversed": True,
            "MinValue": 1,
            "MaxValue": 5,
            "Levels": {"1": "Low"},
        }
    }
    sidecar = build_phenotype_sidecar(
        variant_sidecar,
        ["participant_id", "session_id", "WB01"],
        task="wellbeing",
        variant=None,
    )

    assert sidecar["WB01"] == {"Description": "Item 1", "Levels": {"1": "Low"}}
    assert "Reversed" not in sidecar["WB01"]
    assert "MinValue" not in sidecar["WB01"]
    assert sidecar["participant_id"] == {"Description": "Participant identifier"}
    assert sidecar["MeasurementToolMetadata"] == {
        "PrismTaskName": "wellbeing",
        "PrismVariantID": None,
    }
