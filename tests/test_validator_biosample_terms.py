"""Validator x term registry: inheritance, unknown-metric notices, severity table
(docs/superpowers/specs/2026-10-22-biosample-term-registry-design.md)."""

import json
import os
import sys
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from schema_manager import load_all_schemas, load_schema
from src.term_registry import load_registry
from validator import DatasetValidator

REPO = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO / "app" / "schemas"
EXAMPLE = REPO / "official" / "library" / "biosample" / "biosample-inflammation.json"

TECHNICAL = {
    "SpecimenType": "saliva", "CollectionMethod": "passive-drool", "Anticoagulant": "none",
    "FastingRequired": False, "ProcessingProtocol": "x", "StorageTemperature": -80,
    "Laboratory": "lab", "AssayMethod": "ELISA", "AssayKit": "kit",
}
SAMPLE_COLUMNS = {
    "sample_id": {"Description": "Tube ID", "Units": "n/a", "DataType": "string"},
    "collection_time": {"Description": "hh:mm", "Units": "n/a", "DataType": "string"},
    "fasting": {"Description": "Fasting", "Units": "n/a", "Levels": {"0": "no", "1": "yes"}},
}
BASE = "sub-01/ses-1/biosample/sub-01_ses-1_biosample-saliva_biosample"


def _validator(registry=None):
    v = DatasetValidator(load_all_schemas(str(SCHEMA_DIR)))
    if registry is not None:
        v._terms = registry
    return v


def _sidecar(columns, specimen="saliva"):
    return {
        "Technical": {**TECHNICAL, "SpecimenType": specimen},
        "Study": {"BiosampleName": "saliva"},
        "Metadata": {"SchemaVersion": "1.0.0", "CreationDate": "2026-10-22"},
        **columns,
    }


def _project(root: Path, columns, rows="cort\\n1\\n", specimen="saliva", base=BASE):
    (root / "biosample-saliva_biosample.json").write_text(
        json.dumps(_sidecar(columns, specimen)), encoding="utf-8")
    tsv = root / f"{base}.tsv"
    tsv.parent.mkdir(parents=True, exist_ok=True)
    tsv.write_text(rows, encoding="utf-8")
    return tsv


def _msgs(issues, level):
    return [m for lvl, m, *_ in issues if lvl == level]


def _sidecar_issues(tmp_path, columns, specimen="saliva", registry=None):
    tsv = _project(tmp_path, columns, specimen=specimen)
    return _validator(registry).validate_sidecar(str(tsv), "biosample", str(tmp_path))


def test_schema_accepts_term_only_column():
    schema = load_schema("biosample")
    validate(_sidecar({"cort": {"Term": "cortisol"}}), schema)
    with pytest.raises(ValidationError):
        validate(_sidecar({"cort": {"Description": "no units, no term"}}), schema)


def test_term_column_inherits_min_value(tmp_path):
    tsv = _project(tmp_path, {"cort": {"Term": "cortisol"}}, rows="cort\n-1\n")
    issues = _validator().validate_data_content(str(tsv), "biosample", str(tmp_path))
    assert any("less than MinValue" in m for m in _msgs(issues, "ERROR"))


def test_sidecar_value_overrides_term_default(tmp_path):
    tsv = _project(tmp_path, {"cort": {"Term": "cortisol", "MinValue": -5}}, rows="cort\n-1\n")
    issues = _validator().validate_data_content(str(tsv), "biosample", str(tmp_path))
    assert _msgs(issues, "ERROR") == []


def test_unknown_metric_is_info_with_similar_terms(tmp_path):
    issues = _sidecar_issues(tmp_path, {"salivary_cortisol": {"Description": "d", "Units": "nmol/L"}})
    info = _msgs(issues, "INFO")
    assert len(info) == 1 and "not an official metric" in info[0] and "prism:cortisol" in info[0]
    assert _msgs(issues, "ERROR") == [] and _msgs(issues, "WARNING") == []


def test_unknown_notice_once_per_sidecar(tmp_path):
    cols = {"zzz_marker": {"Description": "d", "Units": "x"}}
    v = _validator()
    total = []
    for sub in ("01", "02", "03"):
        tsv = _project(tmp_path, cols, base=f"sub-{sub}/biosample/sub-{sub}_biosample-saliva_biosample")
        total += _msgs(v.validate_sidecar(str(tsv), "biosample", str(tmp_path)), "INFO")
    assert len([m for m in total if "not an official metric" in m]) == 1


def test_non_analyte_columns_get_no_notice(tmp_path):
    assert _msgs(_sidecar_issues(tmp_path, SAMPLE_COLUMNS), "INFO") == []


def test_alias_column_gets_suggestion_info(tmp_path):
    issues = _sidecar_issues(tmp_path, {"cort": {"Description": "d", "Units": "nmol/L"}})
    assert any("prism:cortisol" in m for m in _msgs(issues, "INFO"))


def test_specimen_mismatch_is_error(tmp_path):
    issues = _sidecar_issues(tmp_path, {"cort": {"Term": "prism:cortisol.serum"}})
    assert any("serum" in m for m in _msgs(issues, "ERROR"))


def test_declared_other_unit_is_info_only(tmp_path):
    issues = _sidecar_issues(tmp_path, {"cort": {"Term": "cortisol", "Units": "ug/dL"}})
    assert any("ug/dL" in m for m in _msgs(issues, "INFO"))
    assert _msgs(issues, "ERROR") == [] and _msgs(issues, "WARNING") == []


def test_unresolvable_term_without_units_is_error(tmp_path):
    issues = _sidecar_issues(tmp_path, {"cort": {"Term": "nonsense"}})
    assert any("nonsense" in m for m in _msgs(issues, "ERROR"))


def test_deprecated_term_warns_with_replacement(tmp_path):
    reg = load_registry()
    reg["cortisol"] = {**reg["cortisol"], "Status": "deprecated", "ReplacedBy": "prism:hydrocortisone"}
    issues = _sidecar_issues(tmp_path, {"cort": {"Term": "cortisol"}}, registry=reg)
    assert any("prism:hydrocortisone" in m for m in _msgs(issues, "WARNING"))


def test_empty_registry_does_not_break_validation(tmp_path):
    issues = _sidecar_issues(
        tmp_path, {"zzz_marker": {"Description": "d", "Units": "x"}}, registry={})
    assert issues == []


def test_existing_inflammation_template_unchanged(tmp_path):
    base = "sub-02/ses-1/biosample/sub-02_ses-1_biosample-inflammation_biosample"
    (tmp_path / "biosample-inflammation_biosample.json").write_text(
        EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    tsv = tmp_path / f"{base}.tsv"
    tsv.parent.mkdir(parents=True)
    tsv.write_text("crp\n1\n", encoding="utf-8")
    assert _validator().validate_sidecar(str(tsv), "biosample", str(tmp_path)) == []
