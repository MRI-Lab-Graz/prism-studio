# Biosample Modality — Phase 1 (Schema + Validation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `prism.py` / the GUI validator understand a new `biosample` modality: filename grammar, JSON schema, template lookup, censored-value codes, and recommended-field warnings.

**Architecture:** `biosample` is registered once in `app/schemas/stable/entities.schema.json` (which already drives `MODALITY_PATTERNS`, `PRISM_MODALITIES`, `.bidsignore` folder rules and project modalities). A new `biosample.schema.json` is auto-loaded by `load_all_schemas` because it iterates the entity registry. `app/src/validator.py` gets three small additions (template lookup, censored codes, recommended warnings + label cross-check). Hard-coded `{"survey","biometrics"}` membership checks in the lines this phase touches move to one shared tuple in `app/src/constants.py`.

**Tech Stack:** Python 3, jsonschema, pytest. No new dependencies. No pandas on the validator path (see `tests/` validator-image regression).

**Spec:** `docs/superpowers/specs/2026-10-15-biosample-modality-design.md`

## Global Constraints

- Filename: `sub-<label>[_ses-<label>]_biosample-<label>[_run-<index>]_biosample.<tsv|json>`; regex produced by the entity registry is `.+_biosample\.(tsv|json)$`.
- Session labels are free-form strings; never normalize (`"1"` ≠ `"01"`).
- Required template fields: `Technical.SpecimenType`, `Study.BiosampleName`, `Metadata.SchemaVersion`, `Metadata.CreationDate`; per column `Description` and `Units`. Nothing else is required (`FileFormat`, `OriginalName`, `Category` are NOT part of this schema).
- `SpecimenType` enum: `whole-blood, serum, plasma, dried-blood-spot, saliva, urine, hair, stool, csf, other`.
- Censored codes accepted in `biosample` data columns (exact strings): `n/a` (already handled), `<LOD`, `<LLOQ`, `>ULOQ`. Other modalities must still reject them. They are skipped by all per-value checks, except for columns that define `Levels` or `AllowedValues` (categorical columns still reject them).
- Recommended `Technical` fields (missing → one WARNING per sidecar, never an error): `CollectionMethod, Anticoagulant, FastingRequired, ProcessingProtocol, StorageTemperature, Laboratory, AssayMethod, AssayKit`.
- Dual-tree rule (CLAUDE.md): `validator.py`, `constants.py`, `bids_integration.py`, `runner.py` exist only under `app/src/` (verified with `find src app/src -name <file>`); no mirrored copy to update. Re-run the `find` before editing if the tree changed.
- TDD: every task starts with a failing test, watched failing, then the fix.
- Collection time is clock time only (`hh:mm`), never a date (documented in the example template).
- Commit trailer on every commit: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Before merging the branch: run `/ponytail:ponytail-audit`, apply what is worth it, re-run tests (CLAUDE.md standing rule).

## Review Focus

- A `biosample` file whose participant column mixes `<LOD` with an invalid word (`"low"`) must still error — only the four codes pass. (Task 3)
- `<LOD` in a `fasting` column with `Levels` must error (categorical column). (Task 3)
- Lower-case / spaced variants (`<lod`, `< LOD`) are NOT accepted — exact codes only; the error message should be the normal "not a valid float" one. (Task 3)
- `biometrics` / `survey` numeric columns still reject `<LOD`. (Task 3)
- Template whose `BiosampleName` differs from the filename label (`biosample-lipids` file, template says `inflammation`) → ERROR naming both. (Task 4)
- Data file with no `biosample-<label>` entity at all must give the filename error, not crash the template lookup. (Task 2)
- 10 data files sharing one incomplete template must produce the recommended-field warning once, not 10×. (Task 4)
- Dataset-level (inherited) template `biosample-inflammation_biosample.json` at the project root and a subject-level override both resolve. (Task 2)

---

### Task 1: Register `biosample` in the entity registry

**Files:**
- Modify: `app/schemas/stable/entities.schema.json` (add after the `biometrics` entry, ~line 34)
- Modify: `app/src/constants.py` (add shared tuple, ~line 15)
- Test: `tests/test_entity_rules.py` (update pinned sets, add new tests)

**Interfaces:**
- Produces: modality name `"biosample"` in `load_entity_rules().prism_modalities`, `.project_modalities`, `.modalities`; pattern `r".+_biosample\.(tsv|json)$"`; `app.src.constants.TABULAR_MODALITIES: tuple[str, ...] = ("survey", "biometrics", "biosample")`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_entity_rules.py` add `"biosample": r".+_biosample\.(tsv|json)$",` to `_EXPECTED_PATTERNS` (after the `biometrics` line), add `"biosample"` to the three pinned sets (`test_prism_modalities_matches_hardcoded_constant`, `test_project_modalities_matches_project_manager_hardcoded_list`, `test_prism_modalities_matches_bids_integration_prism_folders_intent`), and append:

```python
def test_biosample_is_registered_with_tsv_json_suffix():
    rules = load_entity_rules()
    rule = rules.modalities["biosample"]
    assert rule.kind == "prism"
    assert rule.suffixes == ("biosample",)
    assert rules.pattern_for("biosample") == r".+_biosample\.(tsv|json)$"


def test_tabular_modalities_constant_includes_biosample():
    from src.constants import TABULAR_MODALITIES

    assert TABULAR_MODALITIES == ("survey", "biometrics", "biosample")
```

(The docstring of `test_modalities_with_suffixes_matches_original_pattern_dict_keys` says "7 modalities"; update it to say 8.)

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_entity_rules.py -v`
Expected: FAIL (`KeyError: 'biosample'`, set mismatches, `ImportError: TABULAR_MODALITIES`).

- [ ] **Step 3: Implement**

`app/schemas/stable/entities.schema.json`, after the `biometrics` block:

```json
    "biosample": {
      "kind": "prism",
      "suffixes": ["biosample"],
      "extensions": ["tsv", "json"]
    },
```

`app/src/constants.py` (append after `SUPPORTED_MODALITIES`):

```python
# Modalities whose data files are validated cell-by-cell against column
# definitions in their sidecar (validator.validate_data_content and the strict
# filename-pattern check). Add new tabular modalities here, not at each call site.
TABULAR_MODALITIES: tuple[str, ...] = ("survey", "biometrics", "biosample")
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_entity_rules.py -v`
Expected: PASS.

- [ ] **Step 5: Find other tests that pin modality lists**

Run: `python3 -m pytest tests -q -x --ignore=tests/e2e -k "modalit or bidsignore or project_manager or entity"` ; then the full unit suite `python3 -m pytest tests -q --ignore=tests/e2e`.
Expected: failures only where a test pins the exact modality list (new projects now offer/create `biosample`). Update each such expectation to include `biosample`; do not change production code to hide it. If a failure is NOT a pinned-list failure, stop and investigate.

- [ ] **Step 6: Commit**

```bash
git add app/schemas/stable/entities.schema.json app/src/constants.py tests
git commit -m "feat(biosample): register modality in entity rules

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: JSON schema, example template, template lookup

**Files:**
- Create: `app/schemas/stable/biosample.schema.json`
- Create: `official/library/biosample/biosample-inflammation.json`
- Modify: `app/src/validator.py` — `resolve_sidecar_path` (~line 204-263) and `_find_inherited_root_sidecar` (~line 280-345)
- Test: `tests/test_biosample_schema.py` (create)

**Interfaces:**
- Consumes: `load_schema("biosample")` from `src.schema_manager` (auto-works once the file exists).
- Produces: schema `$id` `https://prism.org/schemas/biosample/v1.0.0`, `version` `1.0.0`; sidecar lookup returns `<dir>/biosample-<label>_biosample.json` from `root`, `root/biosample`, `<library>`, `<library>/biosample`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_biosample_schema.py`:

```python
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


def test_only_minimal_set_is_required(schema, template):
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
```

Note for the implementer: `_find_inherited_root_sidecar` returns the path of the first candidate that exists; confirm the return shape (str path vs None) against the function body (~line 345 onward) and adjust the two assertions if it returns a different type; do not change production behavior.

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_biosample_schema.py -v`
Expected: FAIL (`biosample.schema.json must be loadable`; example file missing; lookup tests fail).

- [ ] **Step 3: Create the schema**

`app/schemas/stable/biosample.schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://prism.org/schemas/biosample/v1.0.0",
  "version": "1.0.0",
  "title": "Biosample Metadata",
  "description": "Schema for assay results on biological specimens (blood, serum, plasma, saliva, urine, hair, stool, CSF). One TSV per subject/session/run, one row per sample, one column per analyte. Files are named: sub-<label>[_ses-<label>]_biosample-<label>[_run-<index>]_biosample.<tsv|json>. The <label> names the assay panel (e.g. inflammation), not the specimen. In numeric data columns the codes n/a, <LOD, <LLOQ and >ULOQ are accepted.",
  "type": "object",
  "properties": {
    "Technical": {
      "type": "object",
      "description": "Specimen, collection, storage and assay properties",
      "properties": {
        "SpecimenType": {
          "type": "string",
          "enum": ["whole-blood", "serum", "plasma", "dried-blood-spot", "saliva", "urine", "hair", "stool", "csf", "other"],
          "description": "Type of biological specimen the assay was run on"
        },
        "CollectionMethod": {
          "type": "string",
          "enum": ["venipuncture", "capillary", "passive-drool", "swab", "other", ""],
          "description": "How the specimen was collected"
        },
        "Anticoagulant": {
          "type": "string",
          "enum": ["EDTA", "heparin", "citrate", "none", "other", ""],
          "description": "Anticoagulant in the collection tube (blood specimens)"
        },
        "FastingRequired": {
          "type": "boolean",
          "description": "Whether participants were required to fast before collection"
        },
        "ProcessingProtocol": {
          "type": "string",
          "description": "Free-text processing steps (clotting, centrifugation, aliquoting)"
        },
        "StorageTemperature": {
          "type": "number",
          "description": "Storage temperature in degrees Celsius (e.g. -80)"
        },
        "Laboratory": {
          "type": "string",
          "description": "Laboratory that ran the assay"
        },
        "AssayMethod": {
          "type": "string",
          "description": "Assay method (e.g. ELISA, CLIA, LC-MS/MS)"
        },
        "AssayKit": {
          "type": "string",
          "description": "Assay kit name, manufacturer and lot"
        }
      },
      "required": ["SpecimenType"]
    },
    "Study": {
      "type": "object",
      "description": "Panel-level information",
      "properties": {
        "BiosampleName": {
          "type": "string",
          "pattern": "^[a-zA-Z0-9]+$",
          "description": "Assay panel identifier; must equal the biosample-<label> in the filename (e.g. inflammation)"
        },
        "Description": {
          "type": ["string", "object"],
          "description": "What this panel measures"
        },
        "Citation": {"type": "string", "description": "Citation for the assay protocol"},
        "DOI": {"type": "string", "description": "DOI for the assay protocol"},
        "Keywords": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Keywords describing the panel"
        }
      },
      "required": ["BiosampleName"]
    },
    "Metadata": {
      "type": "object",
      "description": "Administrative metadata",
      "properties": {
        "SchemaVersion": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
        "CreationDate": {"type": "string", "pattern": "^(\\d{4}-\\d{2}-\\d{2})?$", "description": "Date of creation"},
        "Creator": {"type": "string"}
      },
      "required": ["SchemaVersion", "CreationDate"]
    }
  },
  "required": ["Technical", "Study", "Metadata"],
  "additionalProperties": {
    "type": "object",
    "description": "Column definition (one per TSV column)",
    "properties": {
      "Description": {"type": ["string", "object"], "description": "Description of the column"},
      "Units": {"type": "string", "description": "Unit of measurement (e.g. mg/L, pg/mL); n/a for non-numeric columns"},
      "AliasOf": {"type": "string", "description": "Column name of the canonical definition this is an alias for"},
      "Aliases": {"type": "array", "items": {"type": "string"}, "description": "Alternative column names that use this same definition"},
      "DataType": {"type": "string", "enum": ["string", "integer", "float", ""], "description": "Expected data type"},
      "MinValue": {"type": ["number", "null"], "description": "Minimum allowed value (error below)"},
      "MaxValue": {"type": ["number", "null"], "description": "Maximum allowed value (error above)"},
      "WarnMinValue": {"type": ["number", "null"], "description": "Warning threshold below"},
      "WarnMaxValue": {"type": ["number", "null"], "description": "Warning threshold above"},
      "AllowedValues": {"type": "array", "items": {"type": ["string", "number"]}, "description": "Allowed values"},
      "Levels": {
        "type": "object",
        "description": "Mapping of coded values to labels",
        "patternProperties": {"^.*$": {"type": ["string", "object"]}}
      },
      "LOINC": {"type": "string", "pattern": "^\\d+-\\d$", "description": "LOINC code of the analyte (loinc.org)"},
      "LowerLimitOfDetection": {"type": "number", "description": "Limit of detection (LOD) in Units"},
      "LowerLimitOfQuantification": {"type": "number", "description": "Lower limit of quantification (LLOQ) in Units"},
      "UpperLimitOfQuantification": {"type": "number", "description": "Upper limit of quantification (ULOQ) in Units"},
      "ReferenceRange": {
        "type": "object",
        "description": "Clinical reference range (informational; use WarnMin/MaxValue for warnings)",
        "properties": {
          "min": {"type": ["number", "null"]},
          "max": {"type": ["number", "null"]}
        },
        "additionalProperties": false
      },
      "IntraAssayCV": {"type": "number", "description": "Intra-assay coefficient of variation in percent"},
      "InterAssayCV": {"type": "number", "description": "Inter-assay coefficient of variation in percent"}
    },
    "required": ["Description", "Units"]
  }
}
```

- [ ] **Step 4: Create the example template**

`official/library/biosample/biosample-inflammation.json` (TNF-α LOINC is deliberately omitted until verified on loinc.org — spec follow-up; hsCRP `30522-7` and IL-6 `26881-3` must also be verified on loinc.org before this ships, note the check in the commit body):

```json
{
  "Technical": {
    "SpecimenType": "serum",
    "CollectionMethod": "venipuncture",
    "Anticoagulant": "none",
    "FastingRequired": true,
    "ProcessingProtocol": "Clotted 30 min at room temperature, centrifuged 10 min at 2000 g, aliquoted",
    "StorageTemperature": -80,
    "Laboratory": "Example central laboratory",
    "AssayMethod": "ELISA",
    "AssayKit": "Example high-sensitivity multiplex kit"
  },
  "Study": {
    "BiosampleName": "inflammation",
    "Description": "Serum markers of low-grade systemic inflammation (example template)."
  },
  "Metadata": {"SchemaVersion": "1.0.0", "CreationDate": "2026-10-15"},
  "sample_id": {"Description": "Lab tube ID (pseudonymous)", "Units": "n/a", "DataType": "string"},
  "collection_time": {"Description": "Clock time of the blood draw, hh:mm only (never a date)", "Units": "hh:mm", "DataType": "string"},
  "fasting": {"Description": "Participant fasted for at least 8 h", "Units": "n/a", "Levels": {"0": "no", "1": "yes"}},
  "crp": {"Description": "High-sensitivity C-reactive protein", "Units": "mg/L", "DataType": "float", "LOINC": "30522-7", "LowerLimitOfDetection": 0.1, "MinValue": 0, "WarnMaxValue": 10},
  "il6": {"Description": "Interleukin-6", "Units": "pg/mL", "DataType": "float", "LOINC": "26881-3", "LowerLimitOfDetection": 0.5, "MinValue": 0},
  "tnfa": {"Description": "Tumor necrosis factor alpha", "Units": "pg/mL", "DataType": "float", "LowerLimitOfDetection": 0.7, "MinValue": 0}
}
```

- [ ] **Step 5: Implement template lookup in `app/src/validator.py`**

In `resolve_sidecar_path`: after `biometrics_value = ...` add `biosample_value = _extract_entity_value(stem, "biosample")`; after the biometrics loop add

```python
    for biosample_candidate in _value_candidates(biosample_value, acq_value):
        label_candidates.append(("biosample", biosample_candidate))
```

add `safe_path_join(root_dir, "biosample"),` to `search_dirs` and `search_dirs.append(str(library_root / "biosample"))` to the library block. (Do not add `biosample` to the `task`-fallback branch; biosample has no task.)

In `_find_inherited_root_sidecar`: add `biosample_value = _extract_entity_value(stem, "biosample")` and, after the biometrics loop,

```python
    for biosample_candidate in _value_candidates(biosample_value, acq_value):
        candidate_names.append(f"biosample-{biosample_candidate}_{suffix}.json")
```

- [ ] **Step 6: Run to verify pass**

Run: `python3 -m pytest tests/test_biosample_schema.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/schemas/stable/biosample.schema.json official/library/biosample app/src/validator.py tests/test_biosample_schema.py
git commit -m "feat(biosample): schema, example template, sidecar lookup

Verify LOINC codes in the example template on loinc.org before release.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Censored value codes and shared tabular-modality tuple in the validator

**Files:**
- Modify: `app/src/validator.py` — imports (~line 16), `validate_data_content` (~line 905 and ~line 1013), `validate_filename` (~line 1278)
- Test: `tests/test_validator_biosample_content.py` (create)

**Interfaces:**
- Consumes: `src.constants.TABULAR_MODALITIES`; `DatasetValidator.validate_data_content(file_path, modality, root_dir) -> list[(level, msg)]`.
- Produces: module constant `BIOSAMPLE_CENSORED_CODES = frozenset({"<LOD", "<LLOQ", ">ULOQ"})` in `validator.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_validator_biosample_content.py`:

```python
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
    "Metadata": {"SchemaVersion": "1.0.0", "CreationDate": "2026-10-15"},
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
    assert _levels(issues) == ["ERROR"] and "not a valid float" in issues[0][1]


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
```

(If `validate_data_content` for `biometrics` in this fixture resolves the sidecar differently, confirm via `resolve_sidecar_path`; the sidecar sits next to the data file so the subject-level path is found first.)

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_validator_biosample_content.py -v`
Expected: FAIL — `validate_data_content` returns `[]` for modality `biosample` (not in the hard-coded list), so most tests that expect errors fail, and the code-accepted tests may pass for the wrong reason; the error tests are the proof of failure.

- [ ] **Step 3: Implement**

`app/src/validator.py`: add `from src.constants import TABULAR_MODALITIES` with the other `src.` imports, and below `MRI_SUFFIX_REGEX`:

```python
# Raw-data codes for censored assay results; accepted in biosample columns that
# are not categorical (see validate_data_content). Exact strings only.
BIOSAMPLE_CENSORED_CODES = frozenset({"<LOD", "<LLOQ", ">ULOQ"})
```

In `validate_data_content` change `if modality not in ["survey", "biometrics"]:` to `if modality not in TABULAR_MODALITIES:`.

In the value loop, directly after the `# Skip empty values` block, add:

```python
                            # Censored assay results are valid raw data in
                            # numeric biosample columns; categorical columns
                            # (Levels/AllowedValues) still reject them.
                            if (
                                modality == "biosample"
                                and value in BIOSAMPLE_CENSORED_CODES
                                and not (
                                    col_def.get("Levels") or col_def.get("AllowedValues")
                                )
                            ):
                                continue
```

In `validate_filename` change `if modality in {"survey", "biometrics"}:` (the "strict for survey/biometrics" block, ~line 1278) to `if modality in TABULAR_MODALITIES:`.

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_validator_biosample_content.py tests/test_biosample_schema.py tests/test_validator_allowed_values.py tests/test_multiversion_survey.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/src/validator.py tests/test_validator_biosample_content.py
git commit -m "feat(biosample): accept censored assay codes; shared tabular-modality tuple

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Sidecar checks — label cross-check and recommended-field warnings

**Files:**
- Modify: `app/src/validator.py` — `DatasetValidator.__init__` (~line 488) and `validate_sidecar` (~line 1338)
- Test: `tests/test_validator_biosample_sidecar.py` (create)

**Interfaces:**
- Consumes: `validate_sidecar(file_path, modality, root_dir) -> list[(level, msg)]`; `_extract_entity_value(stem, key)`; `split_compound_ext`.
- Produces: constant `BIOSAMPLE_RECOMMENDED_TECHNICAL = ("CollectionMethod", "Anticoagulant", "FastingRequired", "ProcessingProtocol", "StorageTemperature", "Laboratory", "AssayMethod", "AssayKit")` in `validator.py`; method `DatasetValidator._check_biosample_sidecar(sidecar_data, sidecar_path, file_path) -> list`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_validator_biosample_sidecar.py`:

```python
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
        "Metadata": {"SchemaVersion": "1.0.0", "CreationDate": "2026-10-15"},
        "crp": {"Description": "CRP", "Units": "mg/L"},
    }


def _write(root: Path, files: dict[str, dict | str]):
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_validator_biosample_sidecar.py -v`
Expected: FAIL (`ImportError: BIOSAMPLE_RECOMMENDED_TECHNICAL`).

- [ ] **Step 3: Implement**

`app/src/validator.py`, next to `BIOSAMPLE_CENSORED_CODES`:

```python
# Not required by biosample.schema.json, but a template without them hides how
# the sample was taken and measured; validate_sidecar warns once per sidecar.
BIOSAMPLE_RECOMMENDED_TECHNICAL = (
    "CollectionMethod",
    "Anticoagulant",
    "FastingRequired",
    "ProcessingProtocol",
    "StorageTemperature",
    "Laboratory",
    "AssayMethod",
    "AssayKit",
)
```

In `DatasetValidator.__init__` add `self._biosample_warned = set()`.

New method on `DatasetValidator` (place before `validate_sidecar`):

```python
    def _check_biosample_sidecar(self, sidecar_data, sidecar_path, file_path) -> list:
        """Filename label must equal Study.BiosampleName; warn (once per sidecar) about missing recommended Technical fields."""
        issues = []
        study = sidecar_data.get("Study") if isinstance(sidecar_data.get("Study"), dict) else {}
        technical = sidecar_data.get("Technical") if isinstance(sidecar_data.get("Technical"), dict) else {}

        stem, _ext = split_compound_ext(os.path.basename(file_path))
        file_label = _extract_entity_value(stem, "biosample")
        declared = study.get("BiosampleName")
        if file_label and declared and file_label != declared:
            issues.append(
                (
                    "ERROR",
                    f"{normalize_path(sidecar_path)}: Study.BiosampleName '{declared}' does not match "
                    f"the biosample-{file_label} label in {os.path.basename(file_path)}",
                )
            )

        key = normalize_path(sidecar_path)
        if key not in self._biosample_warned:
            self._biosample_warned.add(key)
            missing = [
                f for f in BIOSAMPLE_RECOMMENDED_TECHNICAL if technical.get(f) in (None, "")
            ]
            if missing:
                issues.append(
                    (
                        "WARNING",
                        f"{key}: recommended Technical fields missing: {', '.join(missing)}",
                    )
                )
        return issues
```

In `validate_sidecar`, inside the `try:` after `validate(instance=sidecar_data, schema=schema)` add:

```python
                if modality == "biosample":
                    issues.extend(
                        self._check_biosample_sidecar(sidecar_data, sidecar_path, file_path)
                    )
```

(`FastingRequired: false` is a present value: `technical.get(f) in (None, "")` is False for `False`.)

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_validator_biosample_sidecar.py tests/test_validator_biosample_content.py tests/test_biosample_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/src/validator.py tests/test_validator_biosample_sidecar.py
git commit -m "feat(biosample): label cross-check and recommended-field warnings

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: End-to-end through `prism.py`, `.bidsignore`, changelog

**Files:**
- Modify: `app/src/bids_integration.py` (`EXTRA_BIDSIGNORE_RULES`, ~line 46)
- Modify: `CHANGELOG.md`
- Test: `tests/test_biosample_end_to_end.py` (create)

**Interfaces:**
- Consumes: `app/src/runner.py::validate_dataset(root_dir, library_path=...) -> (issues, stats)`; `prism.py <dataset>` CLI.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_biosample_end_to_end.py`:

```python
"""A minimal PRISM project with a biosample modality validates through the real entry points."""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

REPO = Path(__file__).resolve().parent.parent
EXAMPLE = REPO / "official" / "library" / "biosample" / "biosample-inflammation.json"
ROWS = "sample_id\tcollection_time\tfasting\tcrp\til6\ttnfa\nB-0152\t08:40\t0\t0.4\t<LOD\t1.12\n"


def _build(tmp_path: Path, tsv: str = ROWS) -> Path:
    root = tmp_path / "ds"
    folder = root / "sub-02" / "ses-1" / "biosample"
    folder.mkdir(parents=True)
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": "1.10.1", "DatasetType": "raw"}), encoding="utf-8"
    )
    (root / "participants.tsv").write_text("participant_id\nsub-02\n", encoding="utf-8")
    (root / "biosample-inflammation_biosample.json").write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    (folder / "sub-02_ses-1_biosample-inflammation_biosample.tsv").write_text(tsv, encoding="utf-8")
    return root


def test_validate_dataset_clean_project_has_no_biosample_errors(tmp_path):
    from runner import validate_dataset

    issues, stats = validate_dataset(str(_build(tmp_path)))
    biosample_errors = [i for i in issues if i[0] == "ERROR" and "biosample" in str(i[-1]).lower() + str(i[1]).lower()]
    assert biosample_errors == [], biosample_errors


def test_validate_dataset_flags_bad_value_in_biosample_file(tmp_path):
    from runner import validate_dataset

    bad = ROWS.replace("0.4", "-2")
    issues, _ = validate_dataset(str(_build(tmp_path, bad)))
    assert any(i[0] == "ERROR" and "less than MinValue" in i[1] for i in issues)


def test_prism_cli_validates_biosample_project(tmp_path):
    root = _build(tmp_path, ROWS.replace("0.4", "-2"))
    result = subprocess.run(
        [sys.executable, str(REPO / "prism.py"), str(root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert "less than MinValue" in result.stdout + result.stderr


def test_bidsignore_covers_biosample_files():
    from bids_integration import EXTRA_BIDSIGNORE_RULES

    assert "*_biosample.*" in EXTRA_BIDSIGNORE_RULES
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_biosample_end_to_end.py -v`
Expected: the `.bidsignore` test FAILS (`*_biosample.*` missing); the validation tests should already pass from Tasks 1-4 — if a validation test fails, that is a real integration bug: use `superpowers:systematic-debugging`, fix the root cause in production code, and keep the test.

- [ ] **Step 3: Implement**

`app/src/bids_integration.py`, in `EXTRA_BIDSIGNORE_RULES` after `"*_biometrics.*",`:

```python
    "*_biosample.*",  # Ignore any biosample related data/sidecars
```

and after `"task-*_biometrics.json",`:

```python
    "biosample-*_biosample.json",  # Root biosample templates
```

`CHANGELOG.md`: under the unreleased section (create it in the file's existing style if absent) add:

```
- New `biosample` modality (assay results on blood, serum, saliva, urine, ...): schema, validator support, `<LOD`/`<LLOQ`/`>ULOQ` codes, example template. Phase 1 of 5; converter and GUI follow.
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_biosample_end_to_end.py -v`
Expected: PASS.

- [ ] **Step 5: Whole-suite and repo checks**

Run: `python3 -m pytest tests -q --ignore=tests/e2e` — Expected: PASS.
Run: `python3 tests/verify_repo.py --check dual-tree-drift --no-fix` — Expected: no new findings.
Run: `python3 -c "import src.validator as m; print(m.__file__)"` — Expected: path under `app/src/` (confirms edits are live for the CLI).
Run: `python3 -m pytest tests -q -k "pandas or validator_image"` — Expected: PASS (validator path must not import pandas).

- [ ] **Step 6: Commit**

```bash
git add app/src/bids_integration.py CHANGELOG.md tests/test_biosample_end_to_end.py
git commit -m "feat(biosample): bidsignore rules, end-to-end validation test, changelog

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Pre-merge audit (standing rule)**

Run `/ponytail:ponytail-audit` on the branch, apply worthwhile findings (or state why not), re-run Step 5, then use `superpowers:finishing-a-development-branch`.
