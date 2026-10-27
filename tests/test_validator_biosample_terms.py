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
        v._registries = {"biosample": registry}
    return v


def _sidecar(columns, specimen="saliva"):
    return {
        "Technical": {**TECHNICAL, "SpecimenType": specimen},
        "Study": {"BiosampleName": "saliva"},
        "Metadata": {"SchemaVersion": "1.1.0", "CreationDate": "2026-10-22"},
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


def test_parent_term_without_child_and_no_units_is_error(tmp_path):
    issues = _sidecar_issues(tmp_path, {"cort": {"Description": "x", "Term": "prism:cortisol"}}, specimen="urine")
    assert any("Units" in m for m in _msgs(issues, "ERROR"))


def test_parent_term_without_child_but_with_units_is_info_only(tmp_path):
    issues = _sidecar_issues(
        tmp_path, {"cort": {"Description": "x", "Units": "nmol/L", "Term": "prism:cortisol"}}, specimen="urine")
    assert _msgs(issues, "ERROR") == []


def test_deprecated_term_still_inherits_its_range(tmp_path):
    reg = load_registry()
    reg["cortisol.saliva"] = {**reg["cortisol.saliva"], "Status": "deprecated", "ReplacedBy": "prism:cortisol.serum"}
    v = _validator(reg)
    tsv = _project(tmp_path, {"cort": {"Term": "prism:cortisol.saliva"}}, rows="cort\n-5\n")
    assert any("less than MinValue" in m for m in _msgs(v.validate_data_content(str(tsv), "biosample", str(tmp_path)), "ERROR"))
    assert any("prism:cortisol.serum" in m for m in _msgs(v.validate_sidecar(str(tsv), "biosample", str(tmp_path)), "WARNING"))


def test_empty_registry_still_errors_on_term_without_units(tmp_path):
    issues = _sidecar_issues(tmp_path, {"cort": {"Term": "prism:cortisol"}}, registry={})
    assert any("Units" in m for m in _msgs(issues, "ERROR"))


def test_malformed_term_or_technical_does_not_abort_content_validation(tmp_path):
    for columns, technical in (
        ({"cort": {"Term": ["prism:cortisol"], "Description": "d", "Units": "x"}}, None),
        ({"cort": {"Term": 5, "Description": "d", "Units": "x"}}, None),
        ({"cort": {"Description": "d", "Units": "x"}}, "x"),
    ):
        side = _sidecar(columns)
        if technical is not None:
            side["Technical"] = technical
        (tmp_path / "biosample-saliva_biosample.json").write_text(json.dumps(side), encoding="utf-8")
        tsv = tmp_path / f"{BASE}.tsv"
        tsv.parent.mkdir(parents=True, exist_ok=True)
        tsv.write_text("cort\n1\n", encoding="utf-8")
        issues = _validator().validate_data_content(str(tsv), "biosample", str(tmp_path))
        assert not any("Error validating content" in m for m in _msgs(issues, "ERROR")), (columns, technical)


def test_terms_root_points_at_the_shipped_registry():
    from src.term_registry import terms_root

    assert (terms_root() / "biosample").is_dir()


def test_unknown_metric_notice_names_the_propose_command(tmp_path):
    issues = _sidecar_issues(tmp_path, {"salivary_cortisol": {"Description": "d", "Units": "nmol/L"}})
    notice = _msgs(issues, "INFO")[0]
    # both arguments are quoted, so a path with spaces or a column like "Cortisol (nmol/L)" can be pasted
    # the data file is named, not a sidecar: the command resolves root + subject sidecars like the validator does
    assert "terms propose" in notice and '--column "salivary_cortisol"' in notice and '--data "' in notice and ".tsv" in notice


def test_alias_columns_inherit_the_term_definition(tmp_path):
    tsv = _project(tmp_path, {"cortisol_main": {"Term": "cortisol", "Aliases": ["cort"]}}, rows="cort\n-5\n")
    issues = _validator().validate_data_content(str(tsv), "biosample", str(tmp_path))
    assert any("less than MinValue" in m for m in _msgs(issues, "ERROR"))


def test_null_or_empty_sidecar_values_do_not_switch_off_inherited_checks(tmp_path):
    tsv = _project(tmp_path, {"cort": {"Term": "cortisol", "MinValue": None, "Units": ""}}, rows="cort\n-1\n")
    issues = _validator().validate_data_content(str(tsv), "biosample", str(tmp_path))
    assert any("less than MinValue" in m for m in _msgs(issues, "ERROR"))


def test_known_analyte_new_specimen_notice_names_the_propose_command(tmp_path):
    issues = _sidecar_issues(tmp_path, {"cortisol_hair": {"Description": "d", "Units": "pg/mg", "Term": "cortisol"}}, specimen="hair")
    notice = next(m for m in _msgs(issues, "INFO") if "not yet for specimen" in m)
    assert "terms propose" in notice and '--column "cortisol_hair"' in notice
