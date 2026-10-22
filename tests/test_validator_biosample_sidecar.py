"""biosample sidecar checks: filename label vs BiosampleName, recommended fields."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from schema_manager import load_all_schemas
from validator import DatasetValidator, BIOSAMPLE_RECOMMENDED_TECHNICAL

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "schemas")

FULL_TECHNICAL = {
    "SpecimenType": "serum", "CollectionMethod": "venipuncture", "Anticoagulant": "none",
    "FastingRequired": True, "ProcessingProtocol": "x", "StorageTemperature": -80,
    "Laboratory": "lab", "AssayMethod": "ELISA", "AssayKit": "kit",
}


def _validator():
    return DatasetValidator(load_all_schemas(SCHEMA_DIR))


def _template(technical, name="inflammation"):
    return {
        "Technical": technical,
        "Study": {"BiosampleName": name},
        "Metadata": {"SchemaVersion": "1.1.0", "CreationDate": "2026-10-15"},
        "crp": {"Description": "CRP", "Units": "mg/L"},
    }


def _write(root: Path, files: dict):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")


def _msgs(issues, level):
    return [m for lvl, m in issues if lvl == level]


def test_complete_template_has_no_issues(tmp_path):
    base = "sub-01/ses-1/biosample/sub-01_ses-1_biosample-inflammation_biosample"
    _write(tmp_path, {f"{base}.tsv": "crp\n1\n", f"{base}.json": _template(FULL_TECHNICAL)})
    assert _validator().validate_sidecar(str(tmp_path / f"{base}.tsv"), "biosample", str(tmp_path)) == []


def test_missing_recommended_fields_warn_once_per_sidecar(tmp_path):
    root_sidecar = _template({"SpecimenType": "serum"})
    files = {"biosample-inflammation_biosample.json": root_sidecar}
    tsvs = []
    for sub in ("01", "02", "03"):
        rel = f"sub-{sub}/biosample/sub-{sub}_biosample-inflammation_biosample.tsv"
        files[rel] = "crp\n1\n"
        tsvs.append(tmp_path / rel)
    _write(tmp_path, files)
    v = _validator()
    all_issues = [i for t in tsvs for i in v.validate_sidecar(str(t), "biosample", str(tmp_path))]
    warnings = _msgs(all_issues, "WARNING")
    assert len(warnings) == 1
    for field in BIOSAMPLE_RECOMMENDED_TECHNICAL:
        assert field in warnings[0]
    assert _msgs(all_issues, "ERROR") == []


def test_only_missing_fields_are_listed(tmp_path):
    technical = {**FULL_TECHNICAL}
    del technical["AssayKit"]
    base = "sub-01/biosample/sub-01_biosample-inflammation_biosample"
    _write(tmp_path, {f"{base}.tsv": "crp\n1\n", f"{base}.json": _template(technical)})
    (warning,) = _msgs(_validator().validate_sidecar(str(tmp_path / f"{base}.tsv"), "biosample", str(tmp_path)), "WARNING")
    assert "AssayKit" in warning and "AssayMethod" not in warning


def test_label_mismatch_is_an_error_naming_both(tmp_path):
    base = "sub-01/biosample/sub-01_biosample-lipids_biosample"
    _write(tmp_path, {f"{base}.tsv": "crp\n1\n", f"{base}.json": _template(FULL_TECHNICAL, name="inflammation")})
    errors = _msgs(_validator().validate_sidecar(str(tmp_path / f"{base}.tsv"), "biosample", str(tmp_path)), "ERROR")
    assert len(errors) == 1 and "lipids" in errors[0] and "inflammation" in errors[0]


def test_missing_specimen_type_is_schema_error(tmp_path):
    technical = {k: v for k, v in FULL_TECHNICAL.items() if k != "SpecimenType"}
    base = "sub-01/biosample/sub-01_biosample-inflammation_biosample"
    _write(tmp_path, {f"{base}.tsv": "crp\n1\n", f"{base}.json": _template(technical)})
    errors = _msgs(_validator().validate_sidecar(str(tmp_path / f"{base}.tsv"), "biosample", str(tmp_path)), "ERROR")
    assert any("SpecimenType" in e for e in errors)


def test_other_modalities_get_no_biosample_warnings(tmp_path):
    base = "sub-01/biometrics/sub-01_biometrics-fitness_biometrics"
    _write(tmp_path, {f"{base}.tsv": "x\n1\n", f"{base}.json": {"Technical": {}}})
    issues = _validator().validate_sidecar(str(tmp_path / f"{base}.tsv"), "biometrics", str(tmp_path))
    assert not any("CollectionMethod" in m for _, m in issues)


def test_filename_without_biosample_label_is_an_error(tmp_path):
    issues = _validator().validate_filename(
        "sub-05_biosample.tsv", "biosample", subject_id="sub-05", session_id=None
    )
    assert any(lvl == "ERROR" and "biosample-<label>" in msg for lvl, msg in issues)


def test_filename_with_biosample_label_and_run_is_clean(tmp_path):
    issues = _validator().validate_filename(
        "sub-05_ses-1_biosample-cortisol_run-2_biosample.tsv",
        "biosample", subject_id="sub-05", session_id="ses-1",
    )
    assert issues == []
