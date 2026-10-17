"""biosample schema + template lookup (phase 1 of docs/superpowers/specs/2026-10-15-biosample-modality-design.md)."""

import copy
import json
import os
import sys
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from schema_manager import load_schema
from validator import resolve_sidecar_path, _find_inherited_root_sidecar

REPO = Path(__file__).resolve().parent.parent
EXAMPLE = REPO / "official" / "library" / "biosample" / "biosample-inflammation.json"


@pytest.fixture(scope="module")
def schema():
    s = load_schema("biosample")
    assert s is not None, "biosample.schema.json must be loadable"
    return s


@pytest.fixture()
def template():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example_template_validates(schema, template):
    validate(instance=template, schema=schema)


@pytest.mark.parametrize(
    "path",
    [("Technical", "SpecimenType"), ("Study", "BiosampleName"), ("Metadata", "SchemaVersion"), ("Metadata", "CreationDate")],
)
def test_required_fields_are_enforced(schema, template, path):
    bad = copy.deepcopy(template)
    del bad[path[0]][path[1]]
    with pytest.raises(ValidationError):
        validate(instance=bad, schema=schema)


def test_only_minimal_set_is_required(schema):
    minimal = {
        "Technical": {"SpecimenType": "saliva"},
        "Study": {"BiosampleName": "cortisol"},
        "Metadata": {"SchemaVersion": "1.0.0", "CreationDate": "2026-10-15"},
        "cortisol": {"Description": "Cortisol", "Units": "nmol/L"},
    }
    validate(instance=minimal, schema=schema)


def test_unknown_specimen_type_rejected(schema, template):
    bad = copy.deepcopy(template)
    bad["Technical"]["SpecimenType"] = "tears"
    with pytest.raises(ValidationError):
        validate(instance=bad, schema=schema)


@pytest.mark.parametrize("name", ["with space", "with_underscore", "with-hyphen", ""])
def test_biosample_name_must_be_alphanumeric(schema, template, name):
    bad = copy.deepcopy(template)
    bad["Study"]["BiosampleName"] = name
    with pytest.raises(ValidationError):
        validate(instance=bad, schema=schema)


def test_column_requires_description_and_units(schema, template):
    for missing in ("Description", "Units"):
        bad = copy.deepcopy(template)
        del bad["crp"][missing]
        with pytest.raises(ValidationError):
            validate(instance=bad, schema=schema)


@pytest.mark.parametrize("loinc,ok", [("30522-7", True), ("26881-3", True), ("abc", False), ("30522", False)])
def test_loinc_pattern(schema, template, loinc, ok):
    t = copy.deepcopy(template)
    t["crp"]["LOINC"] = loinc
    if ok:
        validate(instance=t, schema=schema)
    else:
        with pytest.raises(ValidationError):
            validate(instance=t, schema=schema)


def test_new_column_fields_have_types(schema, template):
    t = copy.deepcopy(template)
    t["crp"]["LowerLimitOfQuantification"] = "high"
    with pytest.raises(ValidationError):
        validate(instance=t, schema=schema)


def _touch(path: Path, text="{}"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_resolve_sidecar_finds_library_template(tmp_path):
    root = tmp_path / "proj"
    data = _touch(root / "sub-01" / "ses-1" / "biosample" / "sub-01_ses-1_biosample-inflammation_biosample.tsv", "")
    lib = root / "code" / "library"
    tmpl = _touch(lib / "biosample" / "biosample-inflammation_biosample.json")
    assert resolve_sidecar_path(str(data), str(root), str(lib)) == str(tmpl)


def test_inherited_root_sidecar_found(tmp_path):
    root = tmp_path / "proj"
    data = _touch(root / "sub-01" / "biosample" / "sub-01_biosample-lipids_run-2_biosample.tsv", "")
    tmpl = _touch(root / "biosample-lipids_biosample.json")
    assert _find_inherited_root_sidecar(str(data), str(root)) == str(tmpl)


def test_file_without_biosample_label_does_not_crash_lookup(tmp_path):
    root = tmp_path / "proj"
    data = _touch(root / "sub-01" / "biosample" / "sub-01_biosample.tsv", "")
    assert resolve_sidecar_path(str(data), str(root), None) == str(data.with_suffix(".json"))
    assert _find_inherited_root_sidecar(str(data), str(root)) is None
