"""Censored-value codes in biosample data columns."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from validator import DatasetValidator

TEMPLATE = {
    "Technical": {"SpecimenType": "serum"},
    "Study": {"BiosampleName": "inflammation"},
    "Metadata": {"SchemaVersion": "1.1.0", "CreationDate": "2026-10-15"},
    "fasting": {"Description": "fasted", "Units": "n/a", "Levels": {"0": "no", "1": "yes"}},
    "crp": {"Description": "CRP", "Units": "mg/L", "DataType": "float", "MinValue": 0, "WarnMaxValue": 10},
}


def _project(tmp_path: Path, rows: str, modality="biosample", label="inflammation"):
    root = tmp_path / "proj"
    folder = root / "sub-01" / "ses-1" / modality
    folder.mkdir(parents=True)
    stem = f"sub-01_ses-1_{modality}-{label}_{modality}"
    data = folder / f"{stem}.tsv"
    data.write_text(rows, encoding="utf-8")
    (folder / f"{stem}.json").write_text(json.dumps(TEMPLATE), encoding="utf-8")
    return root, data


def _check(tmp_path, rows, modality="biosample"):
    root, data = _project(tmp_path, rows, modality)
    return DatasetValidator().validate_data_content(str(data), modality, str(root))


def _levels(issues):
    return [lvl for lvl, _ in issues]


@pytest.mark.parametrize("code", ["<LOD", "<LLOQ", ">ULOQ", "n/a"])
def test_censored_codes_accepted_in_numeric_column(tmp_path, code):
    assert _check(tmp_path, f"fasting\tcrp\n1\t{code}\n") == []


def test_normal_range_checks_still_apply_next_to_codes(tmp_path):
    issues = _check(tmp_path, "fasting\tcrp\n1\t<LOD\n1\t-3\n1\t12\n")
    assert _levels(issues) == ["ERROR", "WARNING"]


def test_other_words_still_rejected(tmp_path):
    issues = _check(tmp_path, "fasting\tcrp\n1\tlow\n")
    assert set(_levels(issues)) == {"ERROR"}
    assert any("not a valid float" in msg for _, msg in issues)


@pytest.mark.parametrize("variant", ["<lod", "< LOD", "<LOD ", "LOD"])
def test_code_variants_are_not_accepted(tmp_path, variant):
    issues = _check(tmp_path, f"fasting\tcrp\n1\t{variant}\n")
    assert "ERROR" in _levels(issues)


def test_categorical_column_rejects_code(tmp_path):
    issues = _check(tmp_path, "fasting\tcrp\n<LOD\t1.0\n")
    assert _levels(issues) == ["ERROR"]


def test_biometrics_numeric_column_still_rejects_code(tmp_path):
    issues = _check(tmp_path, "fasting\tcrp\n1\t<LOD\n", modality="biometrics")
    assert "ERROR" in _levels(issues)
