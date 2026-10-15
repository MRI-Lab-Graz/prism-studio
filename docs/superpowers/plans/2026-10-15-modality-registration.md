# Modality Registration Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a researcher propose a new PRISM modality by filling in an Excel workbook (plus a small synthetic sample file); one backend function validates it and generates the schema, example sidecar, fixture dataset and maintainer registration instructions, exposed through `prism_tools.py modality propose` and a GitHub Issue-Form bot that opens a draft PR.

**Architecture:** `src/modality_contribution.py` (already holds `write_minimal_dataset`) gains readers (`.xlsx`/`.yml`/`.json` into one dict), `check_proposal` (names, BIDS/PRISM collisions, columns), `check_sample`, and `build_modality_artifacts`. A thin CLI command in `app/src/cli/commands/modality.py` calls them. A GitHub Action calls the same CLI. Registration stays manual; an end-to-end test applies the generated `REGISTRATION.md` edits to a copy of the repo and proves the validator then accepts the fixture.

**Tech Stack:** Python 3.10, pytest, pandas + openpyxl (already runtime deps), PyYAML, `bidsschematools` (already a runtime dep), `jsonschema`, GitHub Actions + `gh`.

**Spec:** `docs/superpowers/specs/2026-10-15-modality-registration-design.md`

Work in the worktree `.claude/worktrees/modality-contribution-workflow` (branch `worktree-modality-contribution-workflow`). Use its `.venv` (`.venv/bin/python -m pytest ...`). CLAUDE.md applies: TDD (write the test, watch it fail, then implement), and run `/ponytail:ponytail-audit` before merging (Task 11).

## Global Constraints

- One implementation: all logic lives in `src/modality_contribution.py`; `app/src/cli/commands/modality.py` and the bot script only call it. No logic copies in the CLI, the bot or tests.
- `src/modality_contribution.py` exists only under top-level `src/` (verified: no `app/src/` mirror). Do not create a mirror. Import it as `src.modality_contribution`.
- Reuse the biometrics workbook parsing helpers (`ID_ALIASES`, `DESC_ALIASES`, `UNITS_ALIASES`, `DTYPE_ALIASES`, `MIN_ALIASES`, `MAX_ALIASES`, `ALLOWED_ALIASES`, `_clean_key`, `_parse_float`, `_parse_allowed_values`, `_infer_datatype` from `src/converters/excel_to_biometrics.py`; `find_column_idx` from `app/src/converters/excel_base.py`). Import them lazily inside functions (pandas is heavy). Do not copy them.
- Session IDs and other labels are never normalised (CLAUDE.md). The fixture uses the fixed subject `sub-01` only; no session entity.
- `entities.schema.json`, `schema_manager.py`, `tests/verify_repo.py` registration edits are **manual** and only described in `REGISTRATION.md`. The generator never writes to core files.
- The per-column vocabulary property is named `Type` (as in `physio.schema.json`); `other` is the reserved escape value and is never listed in a proposal.
- Sample limits: at most 50 data rows, at most 1,000,000 bytes (`SAMPLE_MAX_ROWS`, `SAMPLE_MAX_BYTES`).
- A taken name is any key in `entities.schema.json` `modalities`, any listed `suffixes`, any `aliases` key, any BIDS suffix, any BIDS datatype (read live from `bidsschematools`, never hardcoded).
- GitHub Actions: pin actions by commit SHA with a version comment, as `ci.yml` does (`actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`, `actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7`). Issue-derived text reaches steps only via `env:`, never interpolated into `run:` (zizmor `actions-security` check).
- Commit trailer on every commit: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Notes on the spec (differences found while planning)

1. **Where the column dictionary lives.** In the real schemas (`biometrics.schema.json`) the schema only defines the *shape* of a column definition (`Description`, `Units`, `MinValue`, `MaxValue`, `AllowedValues`, `DataType`); the actual per-column definitions live in each template/sidecar. So the proposal's `Columns` sheet fills the **example sidecar**, and the generated schema is the generic envelope plus that column-definition shape. Task 10 clarifies the spec wording.
2. **Bot output folder.** The bot knows the issue number before it knows the modality name, so it writes to `proposals/issue-<n>/`, not `proposals/<name>/`. `REGISTRATION.md` uses paths relative to its own folder.
3. **Two attachment fields.** A GitHub Issue Form cannot say "attach two typed files" in one textarea unambiguously. The form has one textarea for the proposal file and one for the sample file; the bot requires exactly one upload in each.
4. **Registration confirmed.** Verified on a copy of the repo (2026-10-15): adding a `modalities` entry to `entities.schema.json` plus `<name>.schema.json` in `app/schemas/stable/` makes `validate_dataset` recognise the new modality and validate its sidecar against the new schema. `schema_manager.load_all_schemas` derives its list from `entities.schema.json`. `check_schema_sync` additionally requires both to exist. `COMMUNITY_MODALITY_SCHEMAS` in `tests/verify_repo.py` is where the convention check learns about the new schema.
6. **Controlled vocabulary and example columns (added during execution, after Task 6).** Column names stay free per study, but a modality may carry an optional `Type` vocabulary (the `physio` pattern: enum plus `other`), and the `Columns` sheet is documented as the columns of the *sample file*, an example and not a contract. Task 7 adds it; the spec sections "Controlled vocabulary (`Type`)" and the Inputs wording are written there.
5. **Column scale (added after plan review).** Each column may carry an optional `Scale` (`categorical`, `continuous`, `boolean`), written as `MeasurementScale` in the sidecar. It is never guessed and is checked for consistency with `DataType` and `AllowedValues`. The spec section "Column scale" describes it.

## Review Focus

Inputs the spec implies but that are easy to get wrong, each pinned by a test in the task that owns the code:

1. **YAML booleans.** Unquoted `yes`/`no`/`on`/`off` in `allowed_values` become `True`/`False`; the reader must reject them with a hint to use quotes (Task 1).
2. **Excel-saved TSV.** A sample with a UTF-8 BOM and CRLF line endings must not produce a header mismatch (Task 3).
3. **Missing values.** Empty cells and `n/a` in a numeric column are not type errors (Task 3).
4. **Compressed and upper-case samples.** `sample.tsv.gz` is read through gzip and a `SAMPLE.TSV` file matches the declared `tsv` (Task 3).
5. **Bad issue bodies.** Zero or two uploads in a field, a non-`user-attachments` URL, an unchecked privacy checkbox: each produces a clear error, never a crash or a download from another host (Task 9).

---

### Task 1: Proposal readers, Problem type and the example inputs

**Files:**
- Modify: `src/modality_contribution.py`
- Create: `examples/modality_proposal/biosample.yml`
- Create: `examples/modality_proposal/biosample_sample.tsv`
- Create: `tests/test_modality_proposal_reader.py`

**Interfaces:**
- Produces:
  - `ProposalError(ValueError)`: the file itself cannot be read.
  - `Problem(severity: str, where: str, message: str)`: frozen dataclass; `severity` is `"error"` or `"warning"`; `str(p)` is `"ERROR: <where>: <message>"`.
  - `errors_only(problems: list[Problem]) -> list[Problem]`
  - `read_proposal(path) -> dict` with keys `modality`, `suffix`, `extensions` (list of lowercase strings without dots), `description`, `rationale`, `columns` (list of `{"id", "description", "units", "datatype", "scale", "min", "max", "allowed_values"}`; `units` defaults to `"n/a"`, `datatype` is one of `string|integer|float`, `scale` is `"categorical"|"continuous"|"boolean"|None` (lower-cased as given, never guessed), `min`/`max` are `float|None`, `allowed_values` is `list|None`).
  - `write_proposal_workbook(proposal: dict, path) -> None` writes sheets `Modality` and `Columns` readable by `read_proposal` (round trip).

- [ ] **Step 1: Create the example inputs**

`examples/modality_proposal/biosample.yml` (the quotes around `"yes"`/`"no"` are deliberate, see Review Focus 1):

```yaml
modality: biosample
suffix: bloodchem
extensions: [tsv]
description: Venous blood samples drawn alongside MRI
rationale: Blood is drawn at each MRI session; this keeps the analyte values next to the imaging data.
columns:
  - id: sample_id
    description: Laboratory sample identifier
  - id: draw_time
    description: Time of the blood draw (HH:MM)
  - id: fasting
    description: Whether the participant had fasted at the time of the draw
    scale: boolean
    allowed_values: ["yes", "no"]
  - id: crp
    description: C-reactive protein
    scale: continuous
    units: mg/L
    min: 0
  - id: glucose
    description: Blood glucose
    scale: continuous
    units: mmol/L
    min: 0
  - id: cortisol
    description: Serum cortisol
    scale: continuous
    units: nmol/L
    min: 0
```

`examples/modality_proposal/biosample_sample.tsv` (tab-separated; synthetic values):

```
sample_id	draw_time	fasting	crp	glucose	cortisol
S001	08:15	yes	1.2	5.1	310
S002	10:40	no	0.8	6.0	280
```

- [ ] **Step 2: Write the failing tests**

`tests/test_modality_proposal_reader.py`:

```python
import json
import os
import sys
from pathlib import Path

import openpyxl
import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.modality_contribution import (  # noqa: E402
    Problem,
    ProposalError,
    errors_only,
    read_proposal,
    write_proposal_workbook,
)

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "modality_proposal"
EXAMPLE_YAML = EXAMPLE_DIR / "biosample.yml"


def test_read_yaml_example_normalizes_columns() -> None:
    p = read_proposal(EXAMPLE_YAML)
    assert (p["modality"], p["suffix"], p["extensions"]) == ("biosample", "bloodchem", ["tsv"])
    assert [c["id"] for c in p["columns"]] == [
        "sample_id", "draw_time", "fasting", "crp", "glucose", "cortisol",
    ]
    assert p["columns"][3] == {
        "id": "crp",
        "description": "C-reactive protein",
        "units": "mg/L",
        "datatype": "float",
        "scale": "continuous",
        "min": 0.0,
        "max": None,
        "allowed_values": None,
    }
    fasting = p["columns"][2]
    assert fasting["scale"] == "boolean"
    assert p["columns"][0]["scale"] is None  # blank stays 'not stated'
    assert fasting["allowed_values"] == ["yes", "no"]
    assert fasting["datatype"] == "string"
    assert fasting["units"] == "n/a"


def test_json_proposal_equals_yaml_proposal(tmp_path: Path) -> None:
    as_json = tmp_path / "p.json"
    as_json.write_text(
        json.dumps(yaml.safe_load(EXAMPLE_YAML.read_text(encoding="utf-8"))),
        encoding="utf-8",
    )
    assert read_proposal(as_json) == read_proposal(EXAMPLE_YAML)


def test_extensions_string_is_split_and_normalized(tmp_path: Path) -> None:
    f = tmp_path / "p.yml"
    f.write_text(
        EXAMPLE_YAML.read_text(encoding="utf-8").replace(
            "extensions: [tsv]", 'extensions: ".TSV, tsv.gz"'
        ),
        encoding="utf-8",
    )
    assert read_proposal(f)["extensions"] == ["tsv", "tsv.gz"]


def test_yaml_boolean_allowed_values_are_rejected_with_a_hint(tmp_path: Path) -> None:
    f = tmp_path / "p.yml"
    f.write_text(
        EXAMPLE_YAML.read_text(encoding="utf-8").replace(
            'allowed_values: ["yes", "no"]', "allowed_values: [yes, no]"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProposalError, match="quotes"):
        read_proposal(f)


def test_workbook_round_trip(tmp_path: Path) -> None:
    p = read_proposal(EXAMPLE_YAML)
    path = tmp_path / "p.xlsx"
    write_proposal_workbook(p, path)
    assert read_proposal(path) == p


def test_workbook_skips_blank_rows_and_ignores_extra_sheets(tmp_path: Path) -> None:
    p = read_proposal(EXAMPLE_YAML)
    path = tmp_path / "p.xlsx"
    write_proposal_workbook(p, path)
    wb = openpyxl.load_workbook(path)
    wb["Columns"].insert_rows(3)  # blank row inside the table
    wb.create_sheet("Notes")["A1"] = "scratch"
    wb.save(path)
    assert read_proposal(path) == p


def test_workbook_without_columns_sheet_is_a_clear_error(tmp_path: Path) -> None:
    wb = openpyxl.Workbook()
    wb.active.title = "Modality"
    path = tmp_path / "p.xlsx"
    wb.save(path)
    with pytest.raises(ProposalError, match="Columns"):
        read_proposal(path)


def test_unsupported_file_type_is_a_clear_error(tmp_path: Path) -> None:
    f = tmp_path / "p.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ProposalError, match="unsupported"):
        read_proposal(f)


def test_scale_is_lowercased_and_never_guessed(tmp_path: Path) -> None:
    f = tmp_path / "p.yml"
    f.write_text(
        EXAMPLE_YAML.read_text(encoding="utf-8").replace("scale: boolean", "scale: Boolean"),
        encoding="utf-8",
    )
    cols = {c["id"]: c for c in read_proposal(f)["columns"]}
    assert cols["fasting"]["scale"] == "boolean"
    assert cols["sample_id"]["scale"] is None


def test_workbook_scale_cell_is_a_dropdown(tmp_path: Path) -> None:
    path = tmp_path / "p.xlsx"
    write_proposal_workbook(read_proposal(EXAMPLE_YAML), path)
    validations = openpyxl.load_workbook(path)["Columns"].data_validations.dataValidation
    assert any("continuous" in (v.formula1 or "") for v in validations)


def test_problem_str_and_errors_only() -> None:
    err = Problem("error", "Modality.Name", "bad")
    warn = Problem("warning", "x", "hmm")
    assert str(err) == "ERROR: Modality.Name: bad"
    assert errors_only([err, warn]) == [err]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_modality_proposal_reader.py -v`
Expected: collection FAILS with `ImportError: cannot import name 'Problem'`.

- [ ] **Step 4: Implement**

In `src/modality_contribution.py`, add to the imports `import re`, `from dataclasses import dataclass`, and add below the existing code:

```python
SAMPLE_MAX_ROWS = 50
SAMPLE_MAX_BYTES = 1_000_000
COLUMN_DATATYPES = {"string", "integer", "float"}
COLUMN_SCALES = ("categorical", "continuous", "boolean")


class ProposalError(ValueError):
    """The proposal file itself cannot be read (not a content problem)."""


@dataclass(frozen=True)
class Problem:
    severity: str  # "error" or "warning"
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.severity.upper()}: {self.where}: {self.message}"


def errors_only(problems: list[Problem]) -> list[Problem]:
    return [p for p in problems if p.severity == "error"]


def _normalize_column(raw: dict) -> dict:
    # Private helpers are reused on purpose: one definition of how a column
    # row is understood, shared with the biometrics workbook converter.
    from src.converters.excel_to_biometrics import (
        _clean_key,
        _infer_datatype,
        _parse_allowed_values,
        _parse_float,
    )

    cid = _clean_key(raw.get("id")) or ""
    allowed_raw = raw.get("allowed_values")
    if isinstance(allowed_raw, (list, tuple)) and any(
        isinstance(v, bool) for v in allowed_raw
    ):
        raise ProposalError(
            f"column '{cid}': allowed_values contains a YAML boolean "
            "(yes/no/on/off/true/false are read as booleans); put the values in quotes"
        )
    units = _clean_key(raw.get("units")) or "n/a"
    allowed = _parse_allowed_values(allowed_raw)
    lo, hi = _parse_float(raw.get("min")), _parse_float(raw.get("max"))
    return {
        "id": cid,
        "description": _clean_key(raw.get("description")) or "",
        "units": units,
        "datatype": _infer_datatype(raw.get("datatype"), units, allowed, lo, hi),
        "scale": (_clean_key(raw.get("scale")) or "").lower() or None,
        "min": lo,
        "max": hi,
        "allowed_values": allowed,
    }


def _finish_proposal(base: dict, rows: list[dict]) -> dict:
    exts = base.get("extensions")
    if isinstance(exts, str):
        exts = exts.split(",")
    proposal = {
        key: str(base.get(key) or "").strip()
        for key in ("modality", "suffix", "description", "rationale")
    }
    proposal["extensions"] = [
        str(e).strip().lstrip(".").lower() for e in (exts or []) if str(e).strip()
    ]
    proposal["columns"] = [_normalize_column(r) for r in rows]
    return proposal


def _read_workbook(path: Path) -> tuple[dict, list[dict]]:
    import pandas as pd

    from src.converters import excel_to_biometrics as eb
    from src.converters.excel_base import find_column_idx

    try:
        sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=str)
    except Exception as exc:  # unreadable or corrupt workbook
        raise ProposalError(f"cannot read workbook {path.name}: {exc}") from exc
    missing = [s for s in ("Modality", "Columns") if s not in sheets]
    if missing:
        raise ProposalError(f"workbook is missing sheet(s): {', '.join(missing)}")

    def cell(row, idx):
        return None if idx is None else eb._clean_key(row.iloc[idx])

    mod = sheets["Modality"]
    if len(mod) < 2:
        raise ProposalError("sheet 'Modality' needs a header row and one data row")
    header = [str(v) for v in mod.iloc[0].tolist()]
    base = {}
    for key, title in (
        ("modality", "Name"),
        ("suffix", "Suffix"),
        ("extensions", "Extensions"),
        ("description", "Description"),
        ("rationale", "Rationale"),
    ):
        idx = find_column_idx(header, {title})
        if idx is None:
            raise ProposalError(f"sheet 'Modality' has no '{title}' column")
        base[key] = cell(mod.iloc[1], idx)

    cols = sheets["Columns"]
    header = [str(v) for v in cols.iloc[0].tolist()] if len(cols) else []
    idx = {
        key: find_column_idx(header, aliases)
        for key, aliases in (
            ("id", eb.ID_ALIASES),
            ("description", eb.DESC_ALIASES),
            ("units", eb.UNITS_ALIASES),
            ("datatype", eb.DTYPE_ALIASES),
            ("scale", {"scale", "measurementscale", "measurement_scale"}),
            ("min", eb.MIN_ALIASES),
            ("max", eb.MAX_ALIASES),
            ("allowed_values", eb.ALLOWED_ALIASES),
        )
    }
    if idx["id"] is None:
        raise ProposalError("sheet 'Columns' has no 'ID' column")
    rows = []
    for i in range(1, len(cols)):
        row = cols.iloc[i]
        raw = {key: cell(row, j) for key, j in idx.items()}
        if raw["id"]:
            rows.append(raw)
    return base, rows


def read_proposal(path) -> dict:
    """Read a modality proposal (.xlsx, .yml/.yaml or .json) into one dict."""
    path = Path(path)
    kind = path.suffix.lower()
    if kind == ".xlsx":
        base, rows = _read_workbook(path)
        return _finish_proposal(base, rows)
    if kind in {".yml", ".yaml", ".json"}:
        import yaml  # JSON is a YAML subset, one reader covers both

        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ProposalError(f"cannot read {path.name}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ProposalError(f"{path.name}: top level must be a mapping")
        rows = raw.get("columns") or []
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise ProposalError(f"{path.name}: 'columns' must be a list of mappings")
        return _finish_proposal(raw, rows)
    raise ProposalError(
        f"unsupported proposal file type '{path.suffix}' (use .xlsx, .yml, .yaml or .json)"
    )


def write_proposal_workbook(proposal: dict, path) -> None:
    """Write a proposal as a two-sheet workbook (the format users fill in)."""
    import openpyxl

    wb = openpyxl.Workbook()
    mod = wb.active
    mod.title = "Modality"
    mod.append(["Name", "Suffix", "Extensions", "Description", "Rationale"])
    mod.append([
        proposal["modality"],
        proposal["suffix"],
        ", ".join(proposal["extensions"]),
        proposal["description"],
        proposal["rationale"],
    ])
    cols = wb.create_sheet("Columns")
    cols.append(["ID", "Description", "Units", "DataType", "Scale", "Min", "Max", "AllowedValues"])
    for c in proposal["columns"]:
        cols.append([
            c["id"],
            c["description"],
            c["units"],
            c["datatype"],
            c["scale"],
            c["min"],
            c["max"],
            "; ".join(str(v) for v in c["allowed_values"]) if c["allowed_values"] else None,
        ])
    from openpyxl.worksheet.datavalidation import DataValidation

    dropdown = DataValidation(
        type="list", formula1='"' + ",".join(COLUMN_SCALES) + '"', allow_blank=True
    )
    cols.add_data_validation(dropdown)
    dropdown.add("E2:E200")  # the Scale column
    wb.save(path)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_modality_proposal_reader.py tests/test_modality_contribution.py -v`
Expected: all PASS (the existing `test_modality_contribution.py` tests still pass).

- [ ] **Step 6: Commit**

```bash
git add src/modality_contribution.py examples/modality_proposal tests/test_modality_proposal_reader.py
git commit -m "feat(modality): read modality proposals from xlsx/yaml/json

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `check_proposal`: names, collisions, columns

**Files:**
- Modify: `src/modality_contribution.py`
- Create: `tests/test_modality_proposal_check.py`

**Interfaces:**
- Consumes: `Problem`, `errors_only`, `read_proposal`, `COLUMN_DATATYPES` from Task 1.
- Produces: `check_proposal(proposal: dict, *, schema_dir: str | None = None) -> list[Problem]`. `schema_dir` defaults to the repo's `app/schemas` (`src.schema_manager.DEFAULT_SCHEMA_DIR`); the `stable` entities file is used.

- [ ] **Step 1: Write the failing tests**

`tests/test_modality_proposal_check.py`:

```python
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.modality_contribution import check_proposal, errors_only, read_proposal  # noqa: E402

EXAMPLE_YAML = Path(__file__).resolve().parents[1] / "examples" / "modality_proposal" / "biosample.yml"


def _proposal(**over) -> dict:
    p = read_proposal(EXAMPLE_YAML)
    p.update(over)
    return p


def _messages(problems) -> str:
    return " | ".join(f"{p.where}: {p.message}" for p in errors_only(problems))


def test_example_proposal_has_no_errors() -> None:
    assert errors_only(check_proposal(_proposal())) == []


@pytest.mark.parametrize(
    "field,value,needle",
    [
        ("suffix", "blood", "BIDS suffix 'blood'"),
        ("modality", "phenotype", "BIDS datatype 'phenotype'"),
        ("suffix", "eyetrack", "PRISM suffix 'eyetrack'"),
        ("modality", "physiological", "PRISM alias 'physiological'"),
        ("modality", "survey", "PRISM modality 'survey'"),
    ],
)
def test_names_taken_in_prism_or_bids_are_rejected(field, value, needle) -> None:
    assert needle in _messages(check_proposal(_proposal(**{field: value})))


def test_blood_message_explains_what_the_bids_suffix_means() -> None:
    assert "Blood recording data" in _messages(check_proposal(_proposal(suffix="blood")))


@pytest.mark.parametrize("bad", ["Biosample", "blood sample", "blood-sample", "1blood", ""])
def test_name_and_suffix_must_be_lowercase_letters_and_digits(bad) -> None:
    assert "lowercase" in _messages(check_proposal(_proposal(modality=bad)))
    assert "lowercase" in _messages(check_proposal(_proposal(suffix=bad)))


def test_extensions_description_and_rationale_are_required() -> None:
    msg = _messages(check_proposal(_proposal(extensions=[], description="", rationale="")))
    assert "Modality.Extensions" in msg
    assert "Modality.Description" in msg
    assert "Modality.Rationale" in msg


def test_bad_extension_is_rejected() -> None:
    assert "Modality.Extensions" in _messages(check_proposal(_proposal(extensions=["t sv"])))


def test_zero_columns_is_an_error() -> None:
    assert "Columns" in _messages(check_proposal(_proposal(columns=[])))


def test_column_problems_are_all_reported() -> None:
    cols = [
        {"id": "a b", "description": "", "units": "n/a", "datatype": "string",
         "min": None, "max": None, "allowed_values": None},
        {"id": "x", "description": "d", "units": "n/a", "datatype": "float",
         "min": 5.0, "max": 1.0, "allowed_values": None},
        {"id": "x", "description": "d", "units": "n/a", "datatype": "blob",
         "min": None, "max": None, "allowed_values": None},
    ]
    msg = _messages(check_proposal(_proposal(columns=cols)))
    assert "letters, digits and underscores" in msg
    assert "Min" in msg and "greater than" in msg
    assert "duplicate" in msg
    assert "datatype" in msg


def _col(**over) -> dict:
    base = {"id": "c", "description": "d", "units": "n/a", "datatype": "string",
            "scale": None, "min": None, "max": None, "allowed_values": None}
    base.update(over)
    return base


@pytest.mark.parametrize(
    "col,needle",
    [
        (_col(scale="ordinal"), "scale must be one of"),
        (_col(scale="continuous", datatype="string"), "continuous column"),
        (_col(scale="continuous", datatype="float", allowed_values=[1, 2]), "continuous column"),
        (_col(scale="categorical"), "categorical column needs AllowedValues"),
        (_col(scale="boolean", allowed_values=["a", "b", "c"]), "exactly two"),
    ],
)
def test_scale_must_agree_with_the_column(col, needle) -> None:
    assert needle in _messages(check_proposal(_proposal(columns=[col])))


@pytest.mark.parametrize(
    "col",
    [
        _col(scale="continuous", datatype="float"),
        _col(scale="categorical", allowed_values=["a", "b", "c"]),
        _col(scale="boolean", allowed_values=[0, 1]),
        _col(),  # no scale stated is fine
    ],
)
def test_consistent_scales_and_no_scale_are_accepted(col) -> None:
    assert errors_only(check_proposal(_proposal(columns=[col]))) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_modality_proposal_check.py -v`
Expected: FAIL with `ImportError: cannot import name 'check_proposal'`.

- [ ] **Step 3: Implement**

Add to `src/modality_contribution.py` (add `from functools import lru_cache` to the imports):

```python
_NAME_RE = re.compile(r"^[a-z][a-z0-9]*$")
_EXT_RE = re.compile(r"^[a-z0-9]+(\.[a-z0-9]+)*$")
_COLUMN_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")


@lru_cache(maxsize=None)
def _bids_names() -> tuple[dict[str, str], dict[str, str]]:
    from bidsschematools.schema import load_schema

    objects = load_schema().objects
    suffixes = {
        v["value"]: f"BIDS suffix '{v['value']}' ({v.get('display_name', '')})"
        for v in objects.suffixes.values()
    }
    datatypes = {
        v["value"]: f"BIDS datatype '{v['value']}'" for v in objects.datatypes.values()
    }
    return suffixes, datatypes


def _taken_names(schema_dir: str | None) -> dict[str, str]:
    """Every name a new modality or suffix may not use, with the reason."""
    from src.schema_manager import DEFAULT_SCHEMA_DIR, load_schema

    entities = load_schema("entities", schema_dir or DEFAULT_SCHEMA_DIR, "stable") or {}
    taken: dict[str, str] = {}
    for name, rule in entities.get("modalities", {}).items():
        taken[name] = f"PRISM modality '{name}'"
        for suffix in rule.get("suffixes", []):
            taken.setdefault(suffix, f"PRISM suffix '{suffix}' (modality '{name}')")
    for alias, target in entities.get("aliases", {}).items():
        taken.setdefault(alias, f"PRISM alias '{alias}' (for '{target}')")
    bids_suffixes, bids_datatypes = _bids_names()
    for name, reason in {**bids_datatypes, **bids_suffixes}.items():
        taken.setdefault(name, reason)
    return taken


def check_proposal(proposal: dict, *, schema_dir: str | None = None) -> list[Problem]:
    """Check a proposal's names, extensions and column dictionary.

    Returns every problem found rather than stopping at the first.
    """
    problems: list[Problem] = []

    def err(where: str, message: str) -> None:
        problems.append(Problem("error", where, message))

    taken = _taken_names(schema_dir)
    for key, label in (("modality", "Name"), ("suffix", "Suffix")):
        value = proposal.get(key) or ""
        where = f"Modality.{label}"
        if not _NAME_RE.match(value):
            err(where, f"'{value}' must be lowercase letters and digits, starting with a letter")
        elif value in taken:
            err(where, f"'{value}' is already taken: {taken[value]}. Choose another {label.lower()}.")

    extensions = proposal.get("extensions") or []
    if not extensions:
        err("Modality.Extensions", "at least one data file extension is required")
    for ext in extensions:
        if not _EXT_RE.match(ext):
            err("Modality.Extensions", f"'{ext}' is not a valid extension (e.g. tsv, tsv.gz)")

    for key, label in (("description", "Description"), ("rationale", "Rationale")):
        if not (proposal.get(key) or "").strip():
            err(f"Modality.{label}", "must not be empty")

    columns = proposal.get("columns") or []
    if not columns:
        err("Columns", "at least one column is required")
    seen: set[str] = set()
    for n, col in enumerate(columns, start=1):
        cid = col.get("id") or ""
        where = f"Columns.{cid}" if cid else f"Columns row {n}"
        if not cid:
            err(where, "ID is empty")
        elif not _COLUMN_ID_RE.match(cid):
            err(where, f"'{cid}' may only contain letters, digits and underscores")
        if cid in seen:
            err(where, f"duplicate column ID '{cid}'")
        seen.add(cid)
        if col.get("datatype") not in COLUMN_DATATYPES:
            err(where, f"datatype must be one of {sorted(COLUMN_DATATYPES)}, got '{col.get('datatype')}'")
        lo, hi = col.get("min"), col.get("max")
        if lo is not None and hi is not None and lo > hi:
            err(where, f"Min ({lo}) is greater than Max ({hi})")
        scale, allowed = col.get("scale"), col.get("allowed_values")
        if scale is not None and scale not in COLUMN_SCALES:
            err(where, f"scale must be one of {list(COLUMN_SCALES)}, got '{scale}'")
        elif scale == "continuous" and (allowed or col.get("datatype") not in {"integer", "float"}):
            err(where, "a continuous column needs datatype integer or float and no AllowedValues")
        elif scale == "categorical" and not allowed:
            err(where, "a categorical column needs AllowedValues (the categories)")
        elif scale == "boolean" and len(allowed or []) != 2:
            err(where, "a boolean column needs exactly two AllowedValues (for example yes; no)")
    return problems
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_modality_proposal_check.py tests/test_modality_proposal_reader.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/modality_contribution.py tests/test_modality_proposal_check.py
git commit -m "feat(modality): check proposals against PRISM and BIDS names

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `check_sample`

**Files:**
- Modify: `src/modality_contribution.py`
- Create: `tests/test_modality_sample_check.py`

**Interfaces:**
- Consumes: `Problem`, `errors_only`, `read_proposal`, `SAMPLE_MAX_ROWS`, `SAMPLE_MAX_BYTES` from Task 1.
- Produces:
  - `check_sample(proposal: dict, sample_path) -> list[Problem]`
  - `sample_extension(path, extensions: list[str]) -> str | None`: the declared extension the file name ends with, longest first, case-insensitive (Task 4 reuses it).

- [ ] **Step 1: Write the failing tests**

`tests/test_modality_sample_check.py`:

```python
import gzip
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.modality_contribution import (  # noqa: E402
    check_sample,
    errors_only,
    read_proposal,
    sample_extension,
)

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "modality_proposal"
HEADER = "sample_id\tdraw_time\tfasting\tcrp\tglucose\tcortisol"
ROW = "S001\t08:15\tyes\t1.2\t5.1\t310"


def _proposal(**over) -> dict:
    p = read_proposal(EXAMPLE_DIR / "biosample.yml")
    p.update(over)
    return p


def _sample(tmp_path: Path, text: str, name: str = "sample.tsv") -> Path:
    f = tmp_path / name
    f.write_bytes(text.encode("utf-8"))
    return f


def _msgs(problems) -> str:
    return " | ".join(f"{p.where}: {p.message}" for p in errors_only(problems))


def test_example_sample_is_clean() -> None:
    assert check_sample(_proposal(), EXAMPLE_DIR / "biosample_sample.tsv") == []


def test_header_mismatch_lists_missing_and_extra_columns(tmp_path: Path) -> None:
    f = _sample(tmp_path, "sample_id\textra\nS1\tx\n")
    msg = _msgs(check_sample(_proposal(), f))
    assert "missing column(s)" in msg and "draw_time" in msg
    assert "unexpected column(s)" in msg and "extra" in msg


def test_value_problems_name_row_and_column(tmp_path: Path) -> None:
    f = _sample(tmp_path, f"{HEADER}\n{ROW}\nS002\t09:00\tmaybe\t-3\tabc\t1\n")
    msg = _msgs(check_sample(_proposal(), f))
    assert "row 2" in msg and "'fasting'" in msg and "maybe" in msg  # not allowed
    assert "row 2" in msg and "'crp'" in msg and "below Min" in msg
    assert "'glucose'" in msg and "not a number" in msg


def test_row_with_wrong_cell_count_is_reported(tmp_path: Path) -> None:
    f = _sample(tmp_path, f"{HEADER}\nS001\t08:15\n")
    assert "2 cells" in _msgs(check_sample(_proposal(), f))


def test_too_many_rows_is_an_error(tmp_path: Path) -> None:
    f = _sample(tmp_path, HEADER + "\n" + "\n".join([ROW] * 51) + "\n")
    assert "more than 50" in _msgs(check_sample(_proposal(), f))


def test_fifty_rows_is_fine(tmp_path: Path) -> None:
    f = _sample(tmp_path, HEADER + "\n" + "\n".join([ROW] * 50) + "\n")
    assert errors_only(check_sample(_proposal(), f)) == []


def test_file_over_one_megabyte_is_an_error(tmp_path: Path) -> None:
    f = _sample(tmp_path, HEADER + "\n" + ROW + "\n" + "#" * 1_000_001)
    assert "too large" in _msgs(check_sample(_proposal(), f))


def test_excel_style_bom_and_crlf_do_not_break_the_header(tmp_path: Path) -> None:
    f = tmp_path / "sample.tsv"
    f.write_bytes(("﻿" + HEADER + "\r\n" + ROW + "\r\n").encode("utf-8"))
    assert check_sample(_proposal(), f) == []


def test_empty_cells_and_na_are_not_type_errors(tmp_path: Path) -> None:
    f = _sample(tmp_path, f"{HEADER}\nS001\tn/a\t\t\tn/a\t310\n")
    assert errors_only(check_sample(_proposal(), f)) == []


def test_gzip_and_uppercase_extension_are_accepted(tmp_path: Path) -> None:
    p = _proposal(extensions=["tsv", "tsv.gz"])
    gz = tmp_path / "SAMPLE.TSV.GZ"
    gz.write_bytes(gzip.compress((HEADER + "\n" + ROW + "\n").encode("utf-8")))
    assert check_sample(p, gz) == []
    upper = _sample(tmp_path, HEADER + "\n" + ROW + "\n", name="SAMPLE.TSV")
    assert check_sample(p, upper) == []
    assert sample_extension(gz, p["extensions"]) == "tsv.gz"


def test_undeclared_extension_and_missing_file_are_errors(tmp_path: Path) -> None:
    assert "extension must be one of" in _msgs(check_sample(_proposal(), _sample(tmp_path, "x", "s.csv")))
    assert "not found" in _msgs(check_sample(_proposal(), tmp_path / "nope.tsv"))


def test_non_tabular_sample_is_only_checked_for_existence_and_extension(tmp_path: Path) -> None:
    p = _proposal(extensions=["edf"])
    f = tmp_path / "recording.edf"
    f.write_bytes(b"\x00\x01binary")
    assert check_sample(p, f) == []


def test_subject_column_other_than_sub_01_is_an_error(tmp_path: Path) -> None:
    cols = _proposal()["columns"] + [{
        "id": "participant_id", "description": "d", "units": "n/a",
        "datatype": "string", "min": None, "max": None, "allowed_values": None,
    }]
    f = _sample(tmp_path, HEADER + "\tparticipant_id\n" + ROW + "\tsub-17\n")
    msg = _msgs(check_sample(_proposal(columns=cols), f))
    assert "participant_id" in msg and "sub-01" in msg


def test_identifier_like_column_and_email_value_are_warnings(tmp_path: Path) -> None:
    cols = _proposal()["columns"] + [{
        "id": "patient_name", "description": "d", "units": "n/a",
        "datatype": "string", "min": None, "max": None, "allowed_values": None,
    }]
    f = _sample(tmp_path, HEADER + "\tpatient_name\n" + ROW + "\tjane@example.org\n")
    problems = check_sample(_proposal(columns=cols), f)
    assert errors_only(problems) == []
    text = " | ".join(str(p) for p in problems)
    assert "identifier" in text and "e-mail" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_modality_sample_check.py -v`
Expected: FAIL with `ImportError: cannot import name 'check_sample'`.

- [ ] **Step 3: Implement**

Add to `src/modality_contribution.py` (add `import csv`, `import gzip`, `import itertools` to the imports):

```python
TABULAR_EXTENSIONS = {"tsv", "tsv.gz"}
_SUBJECT_COLUMNS = {"participant_id", "subject", "subject_id", "sub", "sub_id"}
_SUBJECT_OK = {"sub-01", "01"}
_IDENTIFIER_COLUMN_RE = re.compile(r"(?:^|_)(name|birth|dob|email|phone|address)(?:$|_)")
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_INTEGER_RE = re.compile(r"[-+]?\d+")


def sample_extension(path, extensions: list[str]) -> str | None:
    """The declared extension the file name ends with (longest first), or None."""
    name = Path(path).name.lower()
    for ext in sorted(extensions, key=len, reverse=True):
        if name.endswith("." + ext):
            return ext
    return None


def _allowed(value: str, allowed: list) -> bool:
    for a in allowed:
        if isinstance(a, (int, float)) and not isinstance(a, bool):
            try:
                if float(value) == float(a):
                    return True
            except ValueError:
                pass
        elif value == str(a):
            return True
    return False


def _read_tabular_rows(path: Path, ext: str) -> list[list[str]]:
    # utf-8-sig drops an Excel BOM; newline="" lets csv handle CRLF. Reading
    # is capped so a decompression bomb cannot exhaust memory.
    opener = gzip.open if ext.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as fh:
        return list(itertools.islice(csv.reader(fh, delimiter="\t"), SAMPLE_MAX_ROWS + 2))


def check_sample(proposal: dict, sample_path) -> list[Problem]:
    """Check the sample data file against the proposal's column dictionary."""
    path = Path(sample_path)
    name = path.name
    if not path.is_file():
        return [Problem("error", name, "sample file not found")]
    extensions = proposal.get("extensions") or []
    ext = sample_extension(path, extensions)
    if ext is None:
        return [Problem("error", name, f"extension must be one of: {', '.join(extensions)}")]
    if path.stat().st_size > SAMPLE_MAX_BYTES:
        return [Problem("error", name, f"file is too large (max {SAMPLE_MAX_BYTES // 1_000_000} MB)")]
    if ext not in TABULAR_EXTENSIONS:
        try:
            with path.open("rb") as fh:
                fh.read(1)
        except OSError as exc:
            return [Problem("error", name, f"cannot read file: {exc}")]
        return []

    try:
        rows = _read_tabular_rows(path, ext)
    except (OSError, UnicodeDecodeError, EOFError, gzip.BadGzipFile) as exc:
        return [Problem("error", name, f"cannot read file as tab-separated text: {exc}")]
    if not rows:
        return [Problem("error", name, "file is empty")]

    problems: list[Problem] = []
    header, data = rows[0], rows[1:]
    columns = {c["id"]: c for c in proposal.get("columns") or []}
    missing = [c for c in columns if c not in header]
    extra = [h for h in header if h not in columns]
    if missing:
        problems.append(Problem("error", name, f"missing column(s): {', '.join(missing)}"))
    if extra:
        problems.append(Problem("error", name, f"unexpected column(s): {', '.join(extra)}"))
    if len(data) > SAMPLE_MAX_ROWS:
        problems.append(Problem("error", name, f"more than {SAMPLE_MAX_ROWS} data rows"))
        data = data[:SAMPLE_MAX_ROWS]

    warned: set[tuple[str, str]] = set()

    def warn(kind: str, column: str, message: str) -> None:
        if (kind, column) not in warned:
            warned.add((kind, column))
            problems.append(Problem("warning", f"{name} column '{column}'", message))

    for column in header:
        if _IDENTIFIER_COLUMN_RE.search(column.lower()):
            warn("identifier", column, "looks like an identifier column; make sure it holds no real personal data")

    for r, row in enumerate(data, start=1):
        if len(row) != len(header):
            problems.append(Problem("error", f"{name} row {r}", f"has {len(row)} cells, header has {len(header)}"))
            continue
        for column, raw in zip(header, row):
            value = raw.strip()
            if _EMAIL_RE.search(value):
                warn("email", column, "contains an e-mail address; sample data must not hold personal data")
            col = columns.get(column)
            if col is None or value == "" or value.lower() == "n/a":
                continue
            where = f"{name} row {r} column '{column}'"
            if column.lower() in _SUBJECT_COLUMNS and value not in _SUBJECT_OK:
                problems.append(Problem("error", where, f"'{value}' must be 'sub-01' in a sample"))
                continue
            datatype = col["datatype"]
            number = None
            if datatype == "integer":
                if not _INTEGER_RE.fullmatch(value):
                    problems.append(Problem("error", where, f"'{value}' is not an integer"))
                    continue
                number = float(value)
            elif datatype == "float":
                try:
                    number = float(value)
                except ValueError:
                    problems.append(Problem("error", where, f"'{value}' is not a number"))
                    continue
            if number is not None:
                if col["min"] is not None and number < col["min"]:
                    problems.append(Problem("error", where, f"{value} is below Min ({col['min']})"))
                if col["max"] is not None and number > col["max"]:
                    problems.append(Problem("error", where, f"{value} is above Max ({col['max']})"))
            if col["allowed_values"] and not _allowed(value, col["allowed_values"]):
                problems.append(Problem("error", where, f"'{value}' is not one of {col['allowed_values']}"))
    return problems
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_modality_sample_check.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/modality_contribution.py tests/test_modality_sample_check.py
git commit -m "feat(modality): check sample data against the column dictionary

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `build_modality_artifacts`

**Files:**
- Modify: `src/modality_contribution.py` (generator functions; `write_minimal_dataset` gains `modality=` and accepts bytes)
- Create: `tests/test_modality_build.py`
- Modify: `tests/test_modality_contribution.py` (one added test for the new `write_minimal_dataset` options)

**Interfaces:**
- Consumes: `read_proposal`, `sample_extension`, `check_sample` from Tasks 1 and 3; the existing `write_minimal_dataset`.
- Produces:
  - `write_minimal_dataset(dest_dir, *, suffix, extension, sidecar, data_content: str | bytes, task_name="demo", modality: str | None = None) -> Path`. `modality` is the folder name under `sub-01/` and defaults to `suffix`, so existing callers are unchanged.
  - `build_schema(proposal: dict) -> dict`
  - `build_example_sidecar(proposal: dict, today: str | None = None) -> dict` (`today` is an ISO date; default is today's date)
  - `registration_entry(proposal: dict) -> dict`: `{"kind": "prism", "suffixes": [suffix], "extensions": [*extensions, "json"]}` without duplicates.
  - `build_registration_md(proposal: dict) -> str`
  - `build_modality_artifacts(proposal: dict, sample_path, proposal_path, out_dir) -> list[Path]`: writes into `out_dir`: `<modality>.schema.json`, `example_sidecar.json`, `fixture/` (via `write_minimal_dataset`, using the sample as data), `REGISTRATION.md`, and copies of the proposal and the sample as `proposal<ext>` / `sample.<ext>`. Returns every written file. Callers must run `check_proposal`/`check_sample` first; this function does not re-check.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_modality_contribution.py`:

```python
def test_write_minimal_dataset_modality_folder_and_bytes(tmp_path: Path) -> None:
    from src.modality_contribution import write_minimal_dataset

    data_path = write_minimal_dataset(
        tmp_path,
        modality="biosample",
        suffix="bloodchem",
        extension="tsv.gz",
        sidecar={"Study": {}},
        data_content=b"\x1f\x8bbytes",
        task_name="biosample",
    )
    assert data_path == tmp_path / "sub-01" / "biosample" / "sub-01_task-biosample_bloodchem.tsv.gz"
    assert data_path.read_bytes() == b"\x1f\x8bbytes"
    assert (data_path.parent / "sub-01_task-biosample_bloodchem.json").is_file()
```

`tests/test_modality_build.py`:

```python
import importlib.util
import json
import os
import sys
from pathlib import Path

import jsonschema

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.modality_contribution import (  # noqa: E402
    build_example_sidecar,
    build_modality_artifacts,
    build_registration_md,
    build_schema,
    read_proposal,
    registration_entry,
)

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "modality_proposal"
PROPOSAL = EXAMPLE_DIR / "biosample.yml"
SAMPLE = EXAMPLE_DIR / "biosample_sample.tsv"


def _load_verify_repo_module():
    module_path = Path(__file__).with_name("verify_repo.py")
    spec = importlib.util.spec_from_file_location("verify_repo", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_schema_passes_the_modality_conventions_check(tmp_path: Path, capsys) -> None:
    p = read_proposal(PROPOSAL)
    schema_dir = tmp_path / "app" / "schemas" / "stable"
    schema_dir.mkdir(parents=True)
    (schema_dir / "biosample.schema.json").write_text(json.dumps(build_schema(p)), encoding="utf-8")

    verify_repo = _load_verify_repo_module()
    verify_repo.COMMUNITY_MODALITY_SCHEMAS = {"biosample"}
    verify_repo.check_modality_schema_conventions(str(tmp_path))
    out = capsys.readouterr().out

    assert "[✗]" not in out
    assert "follow PRISM conventions" in out


def test_example_sidecar_validates_against_generated_schema() -> None:
    p = read_proposal(PROPOSAL)
    sidecar = build_example_sidecar(p, today="2026-10-15")
    jsonschema.Draft7Validator(build_schema(p)).validate(sidecar)
    assert sidecar["Technical"]["FileFormat"] == "tsv"
    assert sidecar["Study"]["TaskName"] == "biosample"
    assert sidecar["Metadata"]["CreationDate"] == "2026-10-15"
    assert sidecar["crp"] == {
        "Description": "C-reactive protein",
        "Units": "mg/L",
        "MinValue": 0.0,
        "DataType": "float",
        "MeasurementScale": "continuous",
    }
    assert sidecar["fasting"]["AllowedValues"] == ["yes", "no"]
    assert sidecar["fasting"]["MeasurementScale"] == "boolean"
    assert "MeasurementScale" not in sidecar["sample_id"]


def test_schema_rejects_a_sidecar_column_without_units() -> None:
    p = read_proposal(PROPOSAL)
    sidecar = build_example_sidecar(p, today="2026-10-15")
    del sidecar["crp"]["Units"]
    errors = list(jsonschema.Draft7Validator(build_schema(p)).iter_errors(sidecar))
    assert errors


def test_schema_rejects_an_unknown_measurement_scale() -> None:
    p = read_proposal(PROPOSAL)
    sidecar = build_example_sidecar(p, today="2026-10-15")
    sidecar["crp"]["MeasurementScale"] = "ordinal"
    assert list(jsonschema.Draft7Validator(build_schema(p)).iter_errors(sidecar))


def test_registration_entry_and_markdown() -> None:
    p = read_proposal(PROPOSAL)
    assert registration_entry(p) == {
        "kind": "prism",
        "suffixes": ["bloodchem"],
        "extensions": ["tsv", "json"],
    }
    md = build_registration_md(p)
    assert "app/schemas/stable/biosample.schema.json" in md
    assert "entities.schema.json" in md
    assert "COMMUNITY_MODALITY_SCHEMAS" in md
    assert '"biosample"' in md and '"bloodchem"' in md
    assert "fixture" in md


def test_build_writes_every_artifact(tmp_path: Path) -> None:
    p = read_proposal(PROPOSAL)
    out = tmp_path / "out"
    written = build_modality_artifacts(p, SAMPLE, PROPOSAL, out)

    assert (out / "biosample.schema.json").is_file()
    assert (out / "example_sidecar.json").is_file()
    assert (out / "REGISTRATION.md").is_file()
    assert (out / "proposal.yml").is_file()
    assert (out / "sample.tsv").is_file()
    data = out / "fixture" / "sub-01" / "biosample" / "sub-01_task-biosample_bloodchem.tsv"
    assert data.read_bytes() == SAMPLE.read_bytes()
    assert data.with_suffix(".json").is_file()
    assert (out / "fixture" / "dataset_description.json").is_file()
    assert all(w.is_file() for w in written)
    assert data in written
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_modality_build.py tests/test_modality_contribution.py -v`
Expected: FAIL (`ImportError: cannot import name 'build_example_sidecar'`; the new `write_minimal_dataset` test fails with `TypeError: unexpected keyword argument 'modality'`).

- [ ] **Step 3: Implement**

Change `write_minimal_dataset` in `src/modality_contribution.py`: add the parameter `modality: str | None = None` after `task_name`, change `data_content: str` to `data_content: str | bytes`, and replace the folder and data-writing lines:

```python
    modality_dir = dest_dir / "sub-01" / (modality or suffix)
    modality_dir.mkdir(parents=True, exist_ok=True)

    stem = f"sub-01_task-{task_name}_{suffix}"
    data_path = modality_dir / f"{stem}.{extension}"
    if isinstance(data_content, bytes):
        data_path.write_bytes(data_content)
    else:
        data_path.write_text(data_content, encoding="utf-8")
```

(Update the docstring first line of that function to mention `modality` being the folder name, default `suffix`.)

Add (add `import datetime` and `import shutil` to the imports):

```python
def _column_definition(col: dict) -> dict:
    out = {"Description": col["description"], "Units": col["units"]}
    if col["min"] is not None:
        out["MinValue"] = col["min"]
    if col["max"] is not None:
        out["MaxValue"] = col["max"]
    if col["allowed_values"]:
        out["AllowedValues"] = col["allowed_values"]
    out["DataType"] = col["datatype"]
    if col.get("scale"):
        out["MeasurementScale"] = col["scale"]
    return out


def build_schema(proposal: dict) -> dict:
    """The modality schema: PRISM envelope plus the column-definition shape."""
    name, suffix, exts = proposal["modality"], proposal["suffix"], proposal["extensions"]
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": f"https://prism.org/schemas/{name}/v1.0.0",
        "version": "1.0.0",
        "title": f"{name.capitalize()} Metadata",
        "description": (
            f"{proposal['description']}. Files should be named: "
            f"sub-<label>[_ses-<label>]_task-<label>[_run-<index>]_{suffix}.<{'|'.join(exts)}>"
        ),
        "type": "object",
        "properties": {
            "Technical": {
                "type": "object",
                "description": "Technical properties of the data",
                "properties": {
                    "FileFormat": {"type": "string", "enum": [*exts, ""]},
                    "Equipment": {"type": ["string", "object"]},
                    "Location": {"type": "string"},
                },
                "required": ["FileFormat"],
            },
            "Study": {
                "type": "object",
                "description": "Study-specific parameters",
                "properties": {
                    "TaskName": {"type": "string", "pattern": "^[a-zA-Z0-9]*$"},
                    "OriginalName": {"type": ["string", "object"]},
                    "Description": {"type": ["string", "object"]},
                    "Citation": {"type": "string"},
                },
                "required": ["TaskName", "OriginalName"],
            },
            "Metadata": {
                "type": "object",
                "description": "Administrative metadata",
                "properties": {
                    "SchemaVersion": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
                    "CreationDate": {"type": "string", "pattern": r"^(\d{4}-\d{2}-\d{2})?$"},
                    "Creator": {"type": "string"},
                },
                "required": ["SchemaVersion", "CreationDate"],
            },
        },
        "required": ["Technical", "Study", "Metadata"],
        "additionalProperties": {
            "type": "object",
            "description": "Definition of one data-file column",
            "properties": {
                "Description": {"type": ["string", "object"]},
                "Units": {"type": "string"},
                "MinValue": {"type": ["number", "null"]},
                "MaxValue": {"type": ["number", "null"]},
                "AllowedValues": {"type": "array"},
                "DataType": {"type": "string", "enum": sorted(COLUMN_DATATYPES)},
                "MeasurementScale": {"type": "string", "enum": list(COLUMN_SCALES)},
            },
            "required": ["Description", "Units"],
        },
    }


def build_example_sidecar(proposal: dict, today: str | None = None) -> dict:
    name = proposal["modality"]
    sidecar = {
        "Technical": {"FileFormat": proposal["extensions"][0]},
        "Study": {
            "TaskName": name,
            "OriginalName": name,
            "Description": proposal["description"],
        },
        "Metadata": {
            "SchemaVersion": "1.0.0",
            "CreationDate": today or datetime.date.today().isoformat(),
        },
    }
    for col in proposal["columns"]:
        sidecar[col["id"]] = _column_definition(col)
    return sidecar


def registration_entry(proposal: dict) -> dict:
    exts = list(dict.fromkeys([*proposal["extensions"], "json"]))
    return {"kind": "prism", "suffixes": [proposal["suffix"]], "extensions": exts}


def build_registration_md(proposal: dict) -> str:
    name = proposal["modality"]
    snippet = json.dumps({name: registration_entry(proposal)}, indent=2)
    return f"""# Registering the `{name}` modality (maintainer steps)

PRISM does not register modalities automatically. Do these steps by hand in the
pull request, then let CI validate the fixture in this folder.

1. Copy `{name}.schema.json` to `app/schemas/stable/{name}.schema.json`.
2. In `app/schemas/stable/entities.schema.json`, add this entry under
   `"modalities"`:

```json
{snippet}
```

3. Add `"{name}"` to `COMMUNITY_MODALITY_SCHEMAS` in `tests/verify_repo.py`.
4. Check the registration:
   `python tests/verify_repo.py --check schema-sync` and
   `python tests/verify_repo.py --check modality-schema-conventions`.
5. Validate the generated dataset: `python prism.py fixture` run from this
   folder. It must pass without errors.

Review by hand what no check can judge: units, a modality that duplicates an
existing one under another name, and whether the sample holds any real
participant data.
"""


def build_modality_artifacts(proposal: dict, sample_path, proposal_path, out_dir) -> list[Path]:
    """Write schema, example sidecar, fixture, REGISTRATION.md and input copies.

    Call check_proposal() and check_sample() first; this does not re-check.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sample, source = Path(sample_path), Path(proposal_path)
    name = proposal["modality"]
    ext = sample_extension(sample, proposal["extensions"])

    schema_path = out / f"{name}.schema.json"
    schema_path.write_text(json.dumps(build_schema(proposal), indent=2) + "\n", encoding="utf-8")
    sidecar = build_example_sidecar(proposal)
    sidecar_path = out / "example_sidecar.json"
    sidecar_path.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
    write_minimal_dataset(
        out / "fixture",
        modality=name,
        suffix=proposal["suffix"],
        extension=ext,
        sidecar=sidecar,
        data_content=sample.read_bytes(),
        task_name=name,
    )
    registration_path = out / "REGISTRATION.md"
    registration_path.write_text(build_registration_md(proposal), encoding="utf-8")
    proposal_copy = out / f"proposal{source.suffix.lower()}"
    shutil.copyfile(source, proposal_copy)
    sample_copy = out / f"sample.{ext}"
    shutil.copyfile(sample, sample_copy)

    fixture = out / "fixture"
    fixture_files = [p for p in sorted(fixture.rglob("*")) if p.is_file()]
    return [schema_path, sidecar_path, registration_path, proposal_copy, sample_copy, *fixture_files]
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_modality_build.py tests/test_modality_contribution.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/modality_contribution.py tests/test_modality_build.py tests/test_modality_contribution.py
git commit -m "feat(modality): generate schema, sidecar, fixture and registration notes

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: End-to-end registration test

Proves that following `REGISTRATION.md` makes the validator accept the generated fixture. It fails if the instructions are wrong or incomplete. The validator finds `schemas/` relative to its own file, so the test works on a copy of the repo in a subprocess.

**Files:**
- Create: `tests/test_modality_registration_e2e.py`
- Modify (only if the test shows the instructions are incomplete): `src/modality_contribution.py` (`build_registration_md`, `write_minimal_dataset`)

**Interfaces:**
- Consumes: `read_proposal`, `build_modality_artifacts` (Tasks 1 and 4).

- [ ] **Step 1: Write the test**

```python
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = REPO / "examples" / "modality_proposal"

_VALIDATE = (
    "import json, sys\n"
    "sys.path.insert(0, 'app/src'); sys.path.insert(1, '.')\n"
    "from runner import validate_dataset\n"
    "issues = validate_dataset(sys.argv[1], run_bids=False)[0]\n"
    "print(json.dumps([i[1] for i in issues if i[0] == 'ERROR']))\n"
)


def _copy_repo(dest: Path) -> Path:
    ignore = shutil.ignore_patterns("__pycache__")
    shutil.copytree(REPO / "app" / "src", dest / "app" / "src", ignore=ignore)
    shutil.copytree(REPO / "app" / "schemas", dest / "app" / "schemas")
    shutil.copytree(REPO / "src", dest / "src", ignore=ignore)
    return dest


def _validator_errors(repo: Path, dataset: Path) -> list[str]:
    run = subprocess.run(
        [sys.executable, "-c", _VALIDATE, str(dataset)],
        cwd=repo, capture_output=True, text=True, check=True,
    )
    return json.loads(run.stdout.strip().splitlines()[-1])


def test_following_registration_md_makes_the_fixture_validate(tmp_path: Path) -> None:
    sys.path.insert(0, str(REPO / "app" / "src"))
    from src.modality_contribution import build_modality_artifacts, read_proposal

    proposal = read_proposal(EXAMPLE_DIR / "biosample.yml")
    out = tmp_path / "proposal"
    build_modality_artifacts(
        proposal, EXAMPLE_DIR / "biosample_sample.tsv", EXAMPLE_DIR / "biosample.yml", out
    )
    repo = _copy_repo(tmp_path / "repo")
    fixture = out / "fixture"

    # Before registration the modality is unknown to the validator.
    assert _validator_errors(repo, fixture)

    # Apply the maintainer steps exactly as REGISTRATION.md prints them.
    md = (out / "REGISTRATION.md").read_text(encoding="utf-8")
    snippet = json.loads(re.search(r"```json\n(.*?)\n```", md, re.S).group(1))
    stable = repo / "app" / "schemas" / "stable"
    shutil.copyfile(out / "biosample.schema.json", stable / "biosample.schema.json")
    entities_path = stable / "entities.schema.json"
    entities = json.loads(entities_path.read_text(encoding="utf-8"))
    entities["modalities"].update(snippet)
    entities_path.write_text(json.dumps(entities, indent=2), encoding="utf-8")

    assert _validator_errors(repo, fixture) == []
```

- [ ] **Step 2: Run it**

Run: `.venv/bin/python -m pytest tests/test_modality_registration_e2e.py -v`
Expected: PASS if the generator and the instructions are right. If it fails at the final assertion, the printed error list says what the validator still wants (for example a missing sidecar key or `dataset_description.json` field). Fix the generator or `build_registration_md` (and its Task 4 test), never the test's assertion, then re-run. If it fails at the first `assert _validator_errors(...)` (no errors before registration), the test no longer proves anything and the premise needs re-checking before going on.

- [ ] **Step 3: Commit**

```bash
git add tests/test_modality_registration_e2e.py src/modality_contribution.py
git commit -m "test(modality): prove REGISTRATION.md steps make the fixture validate

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: CLI command `modality propose`

**Files:**
- Create: `app/src/cli/commands/modality.py`
- Modify: `app/src/cli/parser.py` (new subparser after `template-export`, parsers dict entry)
- Modify: `app/src/cli/dispatch.py`
- Modify: `app/src/cli/entrypoint.py`
- Modify: `tests/test_cli_dispatch_routing.py` (one case)
- Create: `tests/test_cli_modality.py`

**Interfaces:**
- Consumes: `read_proposal`, `check_proposal`, `check_sample`, `errors_only`, `build_modality_artifacts`, `ProposalError`, `Problem` (Tasks 1-4).
- Produces: `cmd_modality_propose(args)`. Arguments: `proposal` (positional path), `--sample` (required), `--out`, `--check`, `--json`. Exit code 0 on success; 1 if any error; 2 if `--out` is missing without `--check`.

- [ ] **Step 1: Write the failing tests**

`tests/test_cli_modality.py`:

```python
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.cli.commands.modality as modality_cmds  # noqa: E402
from src.cli.parser import build_prism_tools_parsers  # noqa: E402

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "modality_proposal"
PROPOSAL = EXAMPLE_DIR / "biosample.yml"
SAMPLE = EXAMPLE_DIR / "biosample_sample.tsv"


def _args(**over) -> SimpleNamespace:
    values = dict(proposal=str(PROPOSAL), sample=str(SAMPLE), out=None, check=False, json=False)
    values.update(over)
    return SimpleNamespace(**values)


def test_parser_accepts_modality_propose() -> None:
    parser, parsers = build_prism_tools_parsers(APP_ROOT)
    args = parser.parse_args(["modality", "propose", "p.yml", "--sample", "s.tsv", "--check"])
    assert (args.command, args.action, args.proposal, args.check) == ("modality", "propose", "p.yml", True)
    assert "modality" in parsers


def test_propose_writes_all_artifacts(tmp_path: Path, capsys) -> None:
    out = tmp_path / "out"
    modality_cmds.cmd_modality_propose(_args(out=str(out)))
    assert (out / "biosample.schema.json").is_file()
    assert (out / "REGISTRATION.md").is_file()
    assert "REGISTRATION.md" in capsys.readouterr().out


def test_check_writes_nothing(tmp_path: Path, capsys) -> None:
    out = tmp_path / "out"
    modality_cmds.cmd_modality_propose(_args(out=str(out), check=True))
    assert not out.exists()
    assert "OK" in capsys.readouterr().out


def test_invalid_proposal_exits_1_and_lists_every_problem(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.yml"
    bad.write_text(
        PROPOSAL.read_text(encoding="utf-8")
        .replace("suffix: bloodchem", "suffix: blood")
        .replace("modality: biosample", "modality: Bio Sample"),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as exc:
        modality_cmds.cmd_modality_propose(_args(proposal=str(bad), out=str(tmp_path / "o")))
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Modality.Name" in out and "Modality.Suffix" in out
    assert not (tmp_path / "o").exists()


def test_missing_out_without_check_exits_2(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        modality_cmds.cmd_modality_propose(_args())
    assert exc.value.code == 2


def test_unreadable_proposal_exits_1(tmp_path: Path, capsys) -> None:
    f = tmp_path / "p.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        modality_cmds.cmd_modality_propose(_args(proposal=str(f), check=True))
    assert exc.value.code == 1
    assert "unsupported" in capsys.readouterr().out


def test_json_output(tmp_path: Path, capsys) -> None:
    modality_cmds.cmd_modality_propose(_args(out=str(tmp_path / "o"), json=True))
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["modality"] == "biosample"
    assert any(f.endswith("REGISTRATION.md") for f in payload["files"])
```

In `tests/test_cli_dispatch_routing.py`, add this tuple to `DISPATCH_CASES`, directly after the `template-export` line:

```python
    (dict(command="modality", action="propose"), "modality_propose"),
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_cli_modality.py tests/test_cli_dispatch_routing.py -v`
Expected: FAIL (`ModuleNotFoundError: src.cli.commands.modality`; the routing case fails with `KeyError`/unhandled).

- [ ] **Step 3: Implement**

`app/src/cli/commands/modality.py`:

```python
"""Modality proposal command handler for prism_tools CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.modality_contribution import (
    Problem,
    ProposalError,
    build_modality_artifacts,
    check_proposal,
    check_sample,
    errors_only,
    read_proposal,
)


def _report(args, problems: list[Problem], modality: str = "", files: list[str] | None = None) -> None:
    failed = bool(errors_only(problems))
    if bool(getattr(args, "json", False)):
        print(json.dumps({
            "success": not failed,
            "modality": modality,
            "problems": [
                {"severity": p.severity, "where": p.where, "message": p.message}
                for p in problems
            ],
            "files": files or [],
        }, ensure_ascii=False))
    else:
        for p in problems:
            print(p)
    if failed:
        sys.exit(1)


def cmd_modality_propose(args) -> None:
    """Check a modality proposal and generate its schema, sidecar, fixture and notes."""
    proposal_path = Path(args.proposal).expanduser()
    sample_path = Path(args.sample).expanduser()
    try:
        proposal = read_proposal(proposal_path)
    except (ProposalError, OSError) as exc:
        _report(args, [Problem("error", proposal_path.name, str(exc))])
        return

    problems = check_proposal(proposal) + check_sample(proposal, sample_path)
    if errors_only(problems):
        _report(args, problems, proposal["modality"])
        return

    if args.check:
        _report(args, problems, proposal["modality"])
        if not bool(getattr(args, "json", False)):
            print(f"OK: proposal '{proposal['modality']}' and its sample are valid")
        return

    if not args.out:
        print("Error: --out is required unless --check is given")
        sys.exit(2)
    written = build_modality_artifacts(proposal, sample_path, proposal_path, Path(args.out).expanduser())
    out_dir = Path(args.out).expanduser()
    files = [str(p) for p in written]
    _report(args, problems, proposal["modality"], files)
    if not bool(getattr(args, "json", False)):
        print(f"Wrote {len(files)} files to {out_dir}")
        print(f"Next: a maintainer follows {out_dir / 'REGISTRATION.md'}")
```

`app/src/cli/parser.py`: insert after the `parser_template_export` block (before `parser_survey_validate` code that follows it), and add the dict entry:

```python
    parser_modality = subparsers.add_parser(
        "modality",
        help="Propose a new PRISM modality",
    )
    modality_subparsers = parser_modality.add_subparsers(
        dest="action", help="Modality actions"
    )
    parser_modality_propose = modality_subparsers.add_parser(
        "propose",
        help="Check a modality proposal (workbook, YAML or JSON) plus a sample "
        "data file and generate schema, example sidecar, fixture dataset and "
        "REGISTRATION.md",
    )
    parser_modality_propose.add_argument(
        "proposal", help="Proposal file (.xlsx, .yml, .yaml or .json)"
    )
    parser_modality_propose.add_argument(
        "--sample", required=True, help="Synthetic sample data file in the modality's format"
    )
    parser_modality_propose.add_argument(
        "--out", help="Output folder for the generated files (required unless --check)"
    )
    parser_modality_propose.add_argument(
        "--check", action="store_true", help="Validate only; write nothing"
    )
    parser_modality_propose.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )
```

and in the final `return parser, {...}` dict add `"modality": parser_modality,`.

`app/src/cli/dispatch.py`: after the `template-export` branch add:

```python
    elif args.command == "modality":
        if args.action == "propose":
            handlers["modality_propose"](args)
        else:
            parsers["modality"].print_help()
```

`app/src/cli/entrypoint.py`: add `from src.cli.commands.modality import cmd_modality_propose` next to the other command imports (alphabetical position before `template_export`), and `"modality_propose": cmd_modality_propose,` in the handlers dict after `"template_export"`.

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_cli_modality.py tests/test_cli_dispatch_routing.py tests/test_cli_command_import_boundaries.py tests/test_cli_parity_commands.py -v`
Expected: all PASS. Then a real run:

Run: `.venv/bin/python prism_tools.py modality propose examples/modality_proposal/biosample.yml --sample examples/modality_proposal/biosample_sample.tsv --out <scratchpad>/modality-smoke`
Expected: `Wrote N files to ...`, exit 0.

- [ ] **Step 5: Commit**

```bash
git add app/src/cli tests/test_cli_modality.py tests/test_cli_dispatch_routing.py
git commit -m "feat(cli): add 'prism_tools modality propose'

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Controlled vocabulary (`Type`) and "example columns" framing

Column names are free (each study names its own columns in its sidecar). To keep columns comparable across studies, a modality can carry a controlled vocabulary, the same pattern `physio.schema.json` uses for channels (`Channels.<name>.Type` with an `enum` ending in `OTHER`): every column definition may have a `Type` from a fixed list plus `other` as the escape hatch. This task adds it to the code from Tasks 1-4 and records the design in the spec. The `Columns` sheet is also reframed as the columns of the **sample file**, an example and not a contract (wording changes land in Tasks 8-10).

**Files:**
- Modify: `src/modality_contribution.py`
- Modify: `examples/modality_proposal/biosample.yml`
- Modify (one expected value each): `tests/test_modality_proposal_reader.py`, `tests/test_modality_build.py`
- Create: `tests/test_modality_types.py`
- Modify: `docs/superpowers/specs/2026-10-15-modality-registration-design.md`

**Interfaces:**
- Consumes: everything from Tasks 1-4 (`read_proposal`, `write_proposal_workbook`, `check_proposal`, `build_schema`, `build_example_sidecar`, `_column_definition`, `_normalize_column`, `_finish_proposal`, `_read_workbook`).
- Produces:
  - Proposal dict gains `types`: list of `{"value": str, "description": str}` (default `[]`); each column dict gains `type`: `str | None` (case-sensitive, as written).
  - Constant `TYPE_OTHER = "other"` (the reserved escape value).
  - Workbook: optional sheet `Types` with columns `Value`, `Description`; the `Columns` sheet gains an optional `Type` column placed after `Scale`. A workbook without a `Types` sheet reads as `types == []`.
  - YAML/JSON: optional top-level `types:` (a list of `{value, description}` mappings, or plain strings) and optional `type:` per column.
  - Generated schema: when `types` is non-empty, the column-definition shape gets `"Type": {"type": "string", "enum": [<values>, "other"], "description": ...}`; with no `types` there is no `Type` property. The example sidecar writes `"Type"` for columns that state one.
  - `check_proposal` rules: type values non-empty, unique, matching `^[A-Za-z0-9][A-Za-z0-9_-]*$`, not `other`; a column `Type` must be in the list or be `other`; a column `Type` while the proposal lists no types is an error.

- [ ] **Step 1: Extend the example**

In `examples/modality_proposal/biosample.yml`, insert this block directly after the `rationale:` line and before `columns:`:

```yaml
types:
  - value: CRP
    description: C-reactive protein
  - value: glucose
    description: Blood glucose
  - value: cortisol
    description: Serum cortisol
```

and add a `type:` line to the three measurement columns (keep every other line as it is):

```yaml
  - id: crp
    description: C-reactive protein
    type: CRP
    scale: continuous
    units: mg/L
    min: 0
  - id: glucose
    description: Blood glucose
    type: glucose
    scale: continuous
    units: mmol/L
    min: 0
  - id: cortisol
    description: Serum cortisol
    type: cortisol
    scale: continuous
    units: nmol/L
    min: 0
```

- [ ] **Step 2: Write the failing tests**

Update the two existing expectations that now carry the new key:

- `tests/test_modality_proposal_reader.py`, in `test_read_yaml_example_normalizes_columns`: add `"type": "CRP",` to the expected `crp` dict (after `"scale": "continuous",`).
- `tests/test_modality_build.py`, in `test_example_sidecar_validates_against_generated_schema`: add `"Type": "CRP",` to the expected `sidecar["crp"]` dict (after `"MeasurementScale": "continuous",`).

Create `tests/test_modality_types.py`:

```python
import os
import sys
from pathlib import Path

import jsonschema
import openpyxl
import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.modality_contribution import (  # noqa: E402
    ProposalError,
    build_example_sidecar,
    build_schema,
    check_proposal,
    errors_only,
    read_proposal,
    write_proposal_workbook,
)

EXAMPLE_YAML = Path(__file__).resolve().parents[1] / "examples" / "modality_proposal" / "biosample.yml"


def _proposal(**over) -> dict:
    p = read_proposal(EXAMPLE_YAML)
    p.update(over)
    return p


def _no_vocabulary() -> dict:
    p = read_proposal(EXAMPLE_YAML)
    p["types"] = []
    for c in p["columns"]:
        c["type"] = None
    return p


def _messages(problems) -> str:
    return " | ".join(f"{p.where}: {p.message}" for p in errors_only(problems))


def test_example_defines_and_uses_a_vocabulary() -> None:
    p = read_proposal(EXAMPLE_YAML)
    assert p["types"][0] == {"value": "CRP", "description": "C-reactive protein"}
    assert [t["value"] for t in p["types"]] == ["CRP", "glucose", "cortisol"]
    cols = {c["id"]: c for c in p["columns"]}
    assert cols["crp"]["type"] == "CRP"
    assert cols["sample_id"]["type"] is None
    assert errors_only(check_proposal(p)) == []


def test_plain_string_types_are_accepted(tmp_path: Path) -> None:
    data = yaml.safe_load(EXAMPLE_YAML.read_text(encoding="utf-8"))
    data["types"] = ["CRP", "glucose", "cortisol"]
    f = tmp_path / "p.yml"
    f.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert read_proposal(f)["types"] == [
        {"value": "CRP", "description": ""},
        {"value": "glucose", "description": ""},
        {"value": "cortisol", "description": ""},
    ]


def test_types_must_be_a_list_and_not_yaml_booleans(tmp_path: Path) -> None:
    data = yaml.safe_load(EXAMPLE_YAML.read_text(encoding="utf-8"))
    data["types"] = "CRP"
    f = tmp_path / "p.yml"
    f.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ProposalError, match="list"):
        read_proposal(f)
    f.write_text(EXAMPLE_YAML.read_text(encoding="utf-8").replace("value: CRP", "value: yes"), encoding="utf-8")
    with pytest.raises(ProposalError, match="quotes"):
        read_proposal(f)


def test_workbook_round_trip_keeps_types_and_column_types(tmp_path: Path) -> None:
    p = read_proposal(EXAMPLE_YAML)
    path = tmp_path / "p.xlsx"
    write_proposal_workbook(p, path)
    assert read_proposal(path) == p


def test_workbook_without_types_sheet_reads_as_no_vocabulary(tmp_path: Path) -> None:
    p = _no_vocabulary()
    path = tmp_path / "p.xlsx"
    write_proposal_workbook(p, path)
    wb = openpyxl.load_workbook(path)
    del wb["Types"]
    wb.save(path)
    assert read_proposal(path) == p


def test_type_header_is_not_mistaken_for_datatype(tmp_path: Path) -> None:
    p = read_proposal(EXAMPLE_YAML)
    path = tmp_path / "p.xlsx"
    write_proposal_workbook(p, path)
    wb = openpyxl.load_workbook(path)
    ws = wb["Columns"]
    headers = [c.value for c in ws[1]]
    a, b = headers.index("DataType"), headers.index("Type")
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        row[a].value, row[b].value = row[b].value, row[a].value  # 'Type' now left of 'DataType'
    wb.save(path)
    assert read_proposal(path) == p


def test_column_type_must_be_in_the_vocabulary_or_other() -> None:
    p = read_proposal(EXAMPLE_YAML)
    cols = {c["id"]: c for c in p["columns"]}
    cols["crp"]["type"] = "CRPP"
    msg = _messages(check_proposal(p))
    assert "CRPP" in msg and "other" in msg and "not in the vocabulary" in msg
    cols["crp"]["type"] = "other"
    assert errors_only(check_proposal(p)) == []


def test_column_type_without_any_listed_types_is_an_error() -> None:
    p = _no_vocabulary()
    p["columns"][3]["type"] = "CRP"
    assert "defines no types" in _messages(check_proposal(p))


def test_vocabulary_values_are_checked() -> None:
    types = [
        {"value": "CRP", "description": ""},
        {"value": "CRP", "description": ""},
        {"value": "Other", "description": ""},
        {"value": "bad value", "description": ""},
        {"value": "", "description": ""},
    ]
    p = _proposal(types=types)
    for c in p["columns"]:
        c["type"] = None
    msg = _messages(check_proposal(p))
    assert "duplicate type 'CRP'" in msg
    assert "'other' is added automatically" in msg
    assert "letters, digits, underscores and hyphens" in msg
    assert "Value is empty" in msg


def test_schema_restricts_type_to_the_vocabulary_plus_other() -> None:
    p = read_proposal(EXAMPLE_YAML)
    schema = build_schema(p)
    type_prop = schema["additionalProperties"]["properties"]["Type"]
    assert type_prop["enum"] == ["CRP", "glucose", "cortisol", "other"]
    assert "C-reactive protein" in type_prop["description"]

    sidecar = build_example_sidecar(p, today="2026-10-15")
    assert sidecar["crp"]["Type"] == "CRP"
    assert "Type" not in sidecar["sample_id"]
    validator = jsonschema.Draft7Validator(schema)
    validator.validate(sidecar)

    sidecar["crp"]["Type"] = "other"
    validator.validate(sidecar)
    sidecar["crp"]["Type"] = "CRPP"
    assert list(validator.iter_errors(sidecar))


def test_schema_has_no_type_property_without_a_vocabulary() -> None:
    p = _no_vocabulary()
    assert "Type" not in build_schema(p)["additionalProperties"]["properties"]
    assert "Type" not in build_example_sidecar(p, today="2026-10-15")["crp"]
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_modality_types.py tests/test_modality_proposal_reader.py tests/test_modality_build.py -q`
Expected: FAIL (KeyError `'types'`/`'type'`, the two updated expectations, and the schema has no `Type` property).

- [ ] **Step 4: Implement**

All edits are in `src/modality_contribution.py`.

(a) Constants. After `COLUMN_SCALES = (...)` add:

```python
TYPE_OTHER = "other"  # reserved escape value, added to every vocabulary
```

and next to `_COLUMN_ID_RE` add:

```python
_TYPE_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
```

(b) Above `_finish_proposal` add:

```python
def _normalize_types(raw) -> list[dict]:
    from src.converters.excel_to_biometrics import _clean_key

    types = []
    for item in raw or []:
        value, description = (
            (item.get("value"), item.get("description")) if isinstance(item, dict) else (item, None)
        )
        if isinstance(value, bool):
            raise ProposalError(
                "types: a value was read as a YAML boolean (yes/no/on/off/true/false); put the values in quotes"
            )
        types.append({"value": _clean_key(value) or "", "description": _clean_key(description) or ""})
    return types
```

(c) In `_normalize_column`'s returned dict add, directly after the `"scale"` entry:

```python
        "type": _clean_key(raw.get("type")) or None,
```

(d) `_finish_proposal(base, rows, types=None)`: add the parameter and, after `proposal["columns"] = ...`, add `proposal["types"] = _normalize_types(types)`.

(e) `_read_workbook`: change the return annotation to `tuple[dict, list[dict], list[dict]]`. In the `idx` mapping change the `datatype` entry to `("datatype", {"datatype", "data_type"})` (the shared `DTYPE_ALIASES` also contains `"type"`, which would now collide with the new column) and add `("type", {"type"}),` after the `scale` entry. After the loop that builds `rows`, replace `return base, rows` with:

```python
    types: list[dict] = []
    if "Types" in sheets and len(sheets["Types"]):
        tsheet = sheets["Types"]
        theader = [str(v) for v in tsheet.iloc[0].tolist()]
        value_idx = find_column_idx(theader, {"Value"})
        desc_idx = find_column_idx(theader, {"Description"})
        if value_idx is None:
            raise ProposalError("sheet 'Types' has no 'Value' column")
        for i in range(1, len(tsheet)):
            row = tsheet.iloc[i]
            value = cell(row, value_idx)
            if value:
                types.append({"value": value, "description": cell(row, desc_idx)})
    return base, rows, types
```

(f) `read_proposal`: the workbook branch becomes `base, rows, types = _read_workbook(path)` / `return _finish_proposal(base, rows, types)`. In the YAML/JSON branch, after the `rows` validation and before the return, add:

```python
        types = raw.get("types")
        if types is not None and not isinstance(types, list):
            raise ProposalError(f"{path.name}: 'types' must be a list")
        return _finish_proposal(raw, rows, types)
```

(g) `write_proposal_workbook`: the `Columns` header becomes `["ID", "Description", "Units", "DataType", "Scale", "Type", "Min", "Max", "AllowedValues"]` and each row gets `c["type"],` directly after `c["scale"],`. The Scale drop-down range stays `E2:E200` (Scale is still column E). Before `wb.save(path)` add:

```python
    types_ws = wb.create_sheet("Types")
    types_ws.append(["Value", "Description"])
    for t in proposal["types"]:
        types_ws.append([t["value"], t["description"] or None])
```

(h) `check_proposal`: directly before `columns = proposal.get("columns") or []` add:

```python
    types = proposal.get("types") or []
    type_values: set[str] = set()
    for n, t in enumerate(types, start=1):
        value = t.get("value") or ""
        where = f"Types.{value}" if value else f"Types row {n}"
        if not value:
            err(where, "Value is empty")
        elif not _TYPE_VALUE_RE.match(value):
            err(where, f"'{value}' may only contain letters, digits, underscores and hyphens")
        elif value.lower() == TYPE_OTHER:
            err(where, f"'{TYPE_OTHER}' is added automatically as the escape hatch; remove it from the list")
        elif value in type_values:
            err(where, f"duplicate type '{value}'")
        type_values.add(value)
```

and inside the column loop, after the scale checks (before `return problems`), add:

```python
        ctype = col.get("type")
        if ctype is not None:
            if not types:
                err(where, f"Type '{ctype}' is given but the proposal defines no types")
            elif ctype != TYPE_OTHER and ctype not in type_values:
                err(where, f"Type '{ctype}' is not in the vocabulary; use one of {sorted(type_values)} or '{TYPE_OTHER}'")
```

(i) `_column_definition`: before `return out` add `if col.get("type"): out["Type"] = col["type"]`.

(j) `build_schema`: change `return {` to `schema = {` (closing brace unchanged) and finish the function with:

```python
    types = proposal.get("types") or []
    if types:
        listing = "; ".join(
            f"{t['value']}: {t['description']}" if t["description"] else t["value"] for t in types
        )
        schema["additionalProperties"]["properties"]["Type"] = {
            "type": "string",
            "enum": [*(t["value"] for t in types), TYPE_OTHER],
            "description": f"Controlled vocabulary: {listing}; {TYPE_OTHER}: anything not listed",
        }
    return schema
```

- [ ] **Step 5: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_modality_*.py tests/test_cli_modality.py tests/test_verify_repo_modality_schema_conventions.py -q`
Expected: all PASS (this includes the end-to-end registration test: the generated schema now carries the `Type` enum and the fixture sidecar uses it).

- [ ] **Step 6: Record the design in the spec**

In `docs/superpowers/specs/2026-10-15-modality-registration-design.md`:

1. In the "Inputs" section, directly after the paragraph that describes the `Columns` sheet (before the sentence "The template ships pre-filled"), add:

   > The `Columns` sheet describes the **sample file**. It is an example, not a contract on future studies: two or three columns are enough, and every study defines its own columns in its own sidecar, using the generated example sidecar as the pattern. The optional `Types` sheet (see "Controlled vocabulary") is the part that keeps columns comparable across studies.

2. Directly before the heading "### Column dictionary check", add:

   ```markdown
   ### Controlled vocabulary (`Type`)

   Column names are free: each study names its own columns. To make columns
   comparable across studies anyway, a modality can carry a controlled
   vocabulary, the pattern `physio.schema.json` uses for channels: every column
   definition may have a `Type` from a fixed list plus `other` as the escape
   hatch. Harmonisation happens on `Type`, not on the column name.

   - Optional. The proposal lists `types` (value and short description) in the
     workbook sheet `Types` or the `types:` key of the YAML. `other` is added
     automatically and must not be listed.
   - The generated schema restricts `Type` to the list plus `other`; the example
     sidecar sets `Type` on the example columns that are measurements.
   - `Type` is not required per column (identifiers and times are not
     measurements). New values are added later by an upstream pull request that
     bumps the schema version.
   - Checks: values unique, matching `[A-Za-z0-9][A-Za-z0-9_-]*`, not `other`;
     a column `Type` must be in the list or `other`; a column `Type` while the
     proposal lists no types is an error.
   - Out of scope: standard codes (for example LOINC) per type.
   ```

- [ ] **Step 7: Commit**

```bash
git add src/modality_contribution.py examples/modality_proposal tests/test_modality_types.py tests/test_modality_proposal_reader.py tests/test_modality_build.py docs/superpowers/specs/2026-10-15-modality-registration-design.md
git commit -m "feat(modality): optional controlled vocabulary (Type) for columns

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: The downloadable workbook template

**Files:**
- Create: `official/create_new_modality/modality_proposal_template.xlsx`
- Create: `official/create_new_modality/README.md`
- Create: `tests/test_modality_template_workbook.py`

**Interfaces:**
- Consumes: `read_proposal`, `write_proposal_workbook`, `check_proposal`, `check_sample` (Tasks 1-3).

The template is the blood example under the placeholder names, so it is both documentation and a working input. It is generated with the existing writer so the format cannot drift from the reader.

- [ ] **Step 1: Write the failing test**

`tests/test_modality_template_workbook.py`:

```python
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.modality_contribution import (  # noqa: E402
    check_proposal,
    check_sample,
    errors_only,
    read_proposal,
)

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "official" / "create_new_modality" / "modality_proposal_template.xlsx"
EXAMPLE_DIR = REPO / "examples" / "modality_proposal"


def test_template_workbook_is_a_valid_proposal_equal_to_the_yaml_example() -> None:
    p = read_proposal(TEMPLATE)
    assert errors_only(check_proposal(p)) == []
    assert errors_only(check_sample(p, EXAMPLE_DIR / "biosample_sample.tsv")) == []
    assert p == read_proposal(EXAMPLE_DIR / "biosample.yml")
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_modality_template_workbook.py -v`
Expected: FAIL (file does not exist).

- [ ] **Step 3: Generate the template and add the README**

Run:

```bash
mkdir -p official/create_new_modality
.venv/bin/python - <<'EOF'
import sys
sys.path[:0] = ["app/src", "."]
from src.modality_contribution import read_proposal, write_proposal_workbook
p = read_proposal("examples/modality_proposal/biosample.yml")
write_proposal_workbook(p, "official/create_new_modality/modality_proposal_template.xlsx")
EOF
```

`official/create_new_modality/README.md`:

```markdown
# Propose a New Modality

Workbook for proposing a new PRISM modality (for example blood samples).

- `modality_proposal_template.xlsx`: fill in both sheets. It ships filled in
  with an example (`biosample`); replace the example values.
  - `Modality`: name, suffix, data file extension(s), description, rationale.
  - `Columns`: the columns of your **sample file** (ID, Description, Units,
    DataType, Scale, Type, Min, Max, AllowedValues). This is an example, not a
    contract: two or three columns are enough, and every study defines its own
    columns later in its own sidecar. `Scale` is optional: choose categorical,
    continuous or boolean from the drop-down.
  - `Types` (optional): a short list of the measurement types your modality
    knows (for example CRP, glucose, cortisol), each with a description. Columns
    can then say which `Type` they are, so the same thing gets the same name
    across studies even when column names differ. `other` is always allowed.
- A small **synthetic** sample data file in the same format as your real
  data (at most 50 rows, 1 MB). Never use real participant data.

Name and suffix must be lowercase letters and digits and must not already be
used by PRISM or BIDS (for example `blood` is a BIDS suffix for PET blood
radioactivity). The tool tells you if a name is taken.

See `docs/MODALITY_PROPOSALS.md` for the full workflow.
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_modality_template_workbook.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add official/create_new_modality tests/test_modality_template_workbook.py
git commit -m "feat(modality): ship the proposal workbook template

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Issue Form and bot

**Files:**
- Modify: `.github/ISSUE_TEMPLATE/propose-modality.yml` (replace the line-per-field form)
- Modify: `tests/test_propose_modality_issue_form.py` (replace; it asserts the old form)
- Create: `scripts/ci/modality_issue_to_files.py`
- Create: `tests/test_modality_issue_to_files.py`
- Create: `.github/workflows/propose-modality.yml`
- Create: `tests/test_propose_modality_workflow.py`
- Create: `tests/test_modality_proposal_fixtures.py`

**Interfaces:**
- Produces in `scripts/ci/modality_issue_to_files.py`:
  - `IssueError(ValueError)`
  - `IssueFiles` (frozen dataclass): `proposal_url`, `proposal_ext`, `sample_url`, `sample_ext`
  - `parse_issue(body: str) -> IssueFiles`
  - `pr_body(issue_number: int, log: str) -> str`
  - `main(argv=None) -> int`: with no argument reads env `ISSUE_BODY` and `WORK_DIR`, writes `proposal.<ext>` and `sample.<ext>` into `WORK_DIR`, returns 1 with the error on stderr; with `pr-body` prints `pr_body(int(ISSUE_NUMBER), <LOG_FILE or propose.log>)`.

**Form design.** A rendered Issue Form body contains `### <label>` sections. The form therefore uses fixed labels: `Proposal file`, `Sample data file`, `Rationale`, `Privacy`. Uploads appear as Markdown links `[name.ext](https://github.com/user-attachments/files/<id>/name.ext)`; a checked checkbox appears as `- [x] <label>`.

- [ ] **Step 1: Replace the form and its test**

`.github/ISSUE_TEMPLATE/propose-modality.yml`:

```yaml
name: Propose a New Modality
description: Propose a new PRISM modality (for example blood samples, skin temperature)
title: "[Modality]: "
labels: ["type: new-modality", "status: needs-triage"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for proposing a new PRISM modality!

        1. Download the workbook
           [modality_proposal_template.xlsx](https://github.com/MRI-Lab-Graz/prism-studio/raw/main/official/create_new_modality/modality_proposal_template.xlsx),
           fill in the sheets: `Modality` (name, suffix, extension), `Columns` (the
           columns of your sample file, as an example) and optionally `Types`
           (a shared vocabulary for your measurements).
        2. Prepare a small **synthetic** sample data file in your modality's format
           (at most 50 rows and 1 MB).
        3. Attach both files below. A bot checks them and opens a draft pull
           request; if something is wrong it comments what to fix.

  - type: textarea
    id: proposal_file
    attributes:
      label: Proposal file
      description: Drag your filled-in workbook (.xlsx, .yml or .json) here. Exactly one file.
    validations:
      required: true

  - type: textarea
    id: sample_file
    attributes:
      label: Sample data file
      description: Drag your synthetic sample data file here. Exactly one file.
    validations:
      required: true

  - type: textarea
    id: rationale
    attributes:
      label: Why this modality?
      description: What kind of study or measurement does this support?
    validations:
      required: true

  - type: checkboxes
    id: privacy
    attributes:
      label: Privacy
      options:
        - label: The sample file contains no real participant data (synthetic or fully de-identified values only).
          required: true
```

`tests/test_propose_modality_issue_form.py` (replace the whole file):

```python
from pathlib import Path

import yaml

FORM = Path(__file__).resolve().parent.parent / ".github" / "ISSUE_TEMPLATE" / "propose-modality.yml"


def test_issue_form_has_the_labels_the_bot_parses():
    form = yaml.safe_load(FORM.read_text(encoding="utf-8"))
    assert "type: new-modality" in form["labels"]
    labels = {item["attributes"]["label"] for item in form["body"] if item.get("type") != "markdown"}
    assert {"Proposal file", "Sample data file", "Privacy"} <= labels


def test_privacy_checkbox_is_required():
    form = yaml.safe_load(FORM.read_text(encoding="utf-8"))
    privacy = next(i for i in form["body"] if i.get("id") == "privacy")
    assert all(o["required"] for o in privacy["attributes"]["options"])
```

- [ ] **Step 2: Write the failing tests for the parser**

`tests/test_modality_issue_to_files.py`:

```python
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "modality_issue_to_files.py"
spec = importlib.util.spec_from_file_location("modality_issue_to_files", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod  # dataclasses looks the module up by name
spec.loader.exec_module(mod)

BASE = "https://github.com/user-attachments/files"


def _body(proposal="[blood.xlsx](%s/1/blood.xlsx)" % BASE,
          sample="[blood.tsv](%s/2/blood.tsv)" % BASE,
          privacy="- [x] The sample file contains no real participant data."):
    return (
        "### Proposal file\n\n" + proposal + "\n\n"
        "### Sample data file\n\n" + sample + "\n\n"
        "### Why this modality?\n\nBecause.\n\n"
        "### Privacy\n\n" + privacy + "\n"
    )


def test_parses_one_upload_per_field():
    files = mod.parse_issue(_body())
    assert files.proposal_url == f"{BASE}/1/blood.xlsx"
    assert files.proposal_ext == "xlsx"
    assert files.sample_url == f"{BASE}/2/blood.tsv"
    assert files.sample_ext == "tsv"


def test_compound_sample_extension_is_kept():
    files = mod.parse_issue(_body(sample="[blood.tsv.gz](%s/2/blood.tsv.gz)" % BASE))
    assert files.sample_ext == "tsv.gz"


@pytest.mark.parametrize(
    "kwargs,needle",
    [
        (dict(proposal="no upload here"), "Proposal file"),
        (dict(sample="_No response_"), "Sample data file"),
        (dict(proposal="[a.xlsx](%s/1/a.xlsx) [b.xlsx](%s/3/b.xlsx)" % (BASE, BASE)), "exactly one"),
        (dict(proposal="[a.xlsx](https://evil.example/a.xlsx)"), "Proposal file"),
        (dict(proposal="[a.exe](%s/1/a.exe)" % BASE), "must be .xlsx"),
        (dict(privacy="- [ ] The sample file contains no real participant data."), "privacy"),
    ],
)
def test_bad_issue_bodies_are_clear_errors(kwargs, needle):
    with pytest.raises(mod.IssueError) as exc:
        mod.parse_issue(_body(**kwargs))
    assert needle.lower() in str(exc.value).lower()


def test_pr_body_links_the_issue_and_carries_warnings():
    text = mod.pr_body(7, "Wrote 9 files\nWARNING: s.tsv column 'patient_name': looks like an identifier\n")
    assert "#7" in text
    assert "patient_name" in text
    assert "draft" in text.lower()
    assert "REGISTRATION.md" in text


def test_pr_body_subcommand_reads_issue_number_and_log(tmp_path, monkeypatch, capsys):
    log = tmp_path / "propose.log"
    log.write_text("WARNING: x\n", encoding="utf-8")
    monkeypatch.setenv("ISSUE_NUMBER", "12")
    monkeypatch.setenv("LOG_FILE", str(log))
    assert mod.main(["pr-body"]) == 0
    out = capsys.readouterr().out
    assert "#12" in out and "WARNING: x" in out
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_propose_modality_issue_form.py tests/test_modality_issue_to_files.py -v`
Expected: the form tests PASS once the form is replaced; the parser tests FAIL (script file missing).

- [ ] **Step 4: Implement the script**

`scripts/ci/modality_issue_to_files.py`:

```python
"""Turn a 'Propose a New Modality' issue into local proposal + sample files.

Used by .github/workflows/propose-modality.yml. The issue body is untrusted
text: it is only parsed here, and only github.com/user-attachments URLs are
ever downloaded. Spec: docs/superpowers/specs/2026-10-15-modality-registration-design.md
"""

from __future__ import annotations

import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = 1_000_000
PROPOSAL_EXTENSIONS = {"xlsx", "yml", "yaml", "json"}
_SECTION_RE = re.compile(r"^### (.+?)\s*$", re.M)
_LINK_RE = re.compile(
    r"\[([^\]]+)\]\((https://github\.com/user-attachments/[A-Za-z0-9/_.\-%]+)\)"
)


class IssueError(ValueError):
    """The issue does not contain what the bot needs."""


@dataclass(frozen=True)
class IssueFiles:
    proposal_url: str
    proposal_ext: str
    sample_url: str
    sample_ext: str


def _sections(body: str) -> dict[str, str]:
    parts = _SECTION_RE.split(body)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def _extension(filename: str) -> str:
    parts = filename.lower().split(".")
    if len(parts) > 2 and parts[-1] == "gz":
        return ".".join(parts[-2:])
    return parts[-1] if len(parts) > 1 else ""


def _single_upload(sections: dict[str, str], label: str) -> tuple[str, str]:
    links = _LINK_RE.findall(sections.get(label, ""))
    if not links:
        raise IssueError(f"'{label}' must contain an uploaded file (drag the file into the field).")
    if len(links) > 1:
        raise IssueError(f"'{label}' must contain exactly one uploaded file, found {len(links)}.")
    name, url = links[0]
    return url, _extension(name)


def parse_issue(body: str) -> IssueFiles:
    sections = _sections(body or "")
    if not re.search(r"- \[[xX]\]", sections.get("Privacy", "")):
        raise IssueError("The privacy confirmation (synthetic data only) must be checked.")
    proposal_url, proposal_ext = _single_upload(sections, "Proposal file")
    if proposal_ext not in PROPOSAL_EXTENSIONS:
        raise IssueError("The proposal file must be .xlsx, .yml, .yaml or .json.")
    sample_url, sample_ext = _single_upload(sections, "Sample data file")
    if not re.fullmatch(r"[a-z0-9]+(\.[a-z0-9]+)*", sample_ext):
        raise IssueError("The sample data file needs a plain extension such as .tsv.")
    return IssueFiles(proposal_url, proposal_ext, sample_url, sample_ext)


def pr_body(issue_number: int, log: str) -> str:
    warnings = [line for line in log.splitlines() if line.startswith("WARNING:")]
    warning_text = "\n".join(f"- {w}" for w in warnings) or "- none"
    return f"""Generated by the modality proposal bot from #{issue_number}. This is a **draft**.

Contents: schema, example sidecar, fixture dataset, the original proposal and
sample, and `REGISTRATION.md` with the manual maintainer steps.

Warnings from the automatic check:
{warning_text}

Maintainer checklist:
- [ ] Sample contains no real participant data
- [ ] Name and suffix are sensible (not a duplicate under another name)
- [ ] Units and ranges are plausible
- [ ] Registration steps applied (see `REGISTRATION.md`) and `prism-validator` passes on `fixture`
"""


def _download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - host checked in parse_issue
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise IssueError(f"{dest.name} is larger than {MAX_BYTES // 1_000_000} MB.")
    dest.write_bytes(data)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["pr-body"]:
        log = Path(os.environ.get("LOG_FILE", "propose.log")).read_text(encoding="utf-8")
        print(pr_body(int(os.environ["ISSUE_NUMBER"]), log))
        return 0
    work = Path(os.environ["WORK_DIR"])
    work.mkdir(parents=True, exist_ok=True)
    try:
        files = parse_issue(os.environ.get("ISSUE_BODY", ""))
        _download(files.proposal_url, work / f"proposal.{files.proposal_ext}")
        _download(files.sample_url, work / f"sample.{files.sample_ext}")
    except IssueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: could not download an attachment: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

(`urlopen` raises `URLError`/`HTTPError`, both `OSError` subclasses.)

- [ ] **Step 5: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_propose_modality_issue_form.py tests/test_modality_issue_to_files.py -v`
Expected: all PASS.

- [ ] **Step 6: Write the workflow test, then the workflow**

`tests/test_propose_modality_workflow.py`:

```python
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "propose-modality.yml"


def _load():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_runs_only_on_new_modality_issues():
    wf = _load()
    assert wf[True]["issues"]["types"] == ["opened"]  # PyYAML reads `on` as True
    job = wf["jobs"]["propose"]
    assert "type: new-modality" in job["if"]


def test_issue_text_never_reaches_a_run_block():
    text = WORKFLOW.read_text(encoding="utf-8")
    for step in _load()["jobs"]["propose"]["steps"]:
        assert "github.event" not in step.get("run", ""), step
    assert "ISSUE_BODY: ${{ github.event.issue.body }}" in text


def test_actions_are_pinned_by_sha():
    for step in _load()["jobs"]["propose"]["steps"]:
        if "uses" in step:
            assert "@" in step["uses"] and len(step["uses"].split("@")[1]) == 40, step["uses"]


def test_permissions_are_explicit_and_minimal():
    wf = _load()
    assert wf["permissions"] == {}
    assert wf["jobs"]["propose"]["permissions"] == {
        "contents": "write", "pull-requests": "write", "issues": "write",
    }
```

`.github/workflows/propose-modality.yml`:

```yaml
name: Propose modality

on:
  issues:
    types: [opened]

permissions: {}

jobs:
  propose:
    if: contains(github.event.issue.labels.*.name, 'type: new-modality')
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
      issues: write
    steps:
      - name: Checkout default branch
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: true

      - name: Set up Python
        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Fetch attachments and check the proposal
        id: propose
        env:
          ISSUE_BODY: ${{ github.event.issue.body }}
          ISSUE_NUMBER: ${{ github.event.issue.number }}
        run: |
          WORK_DIR=work
          export WORK_DIR
          if ! { python scripts/ci/modality_issue_to_files.py \
              && python prism_tools.py modality propose work/proposal.* \
                   --sample work/sample.* --out "proposals/issue-${ISSUE_NUMBER}"; } \
              > propose.log 2>&1; then
            echo "failed=true" >> "$GITHUB_OUTPUT"
          fi
          cat propose.log

      - name: Report problems on the issue
        if: steps.propose.outputs.failed == 'true'
        env:
          GH_TOKEN: ${{ github.token }}
          ISSUE_NUMBER: ${{ github.event.issue.number }}
        run: |
          {
            echo "The automatic check found problems with this proposal:"
            echo
            echo '```'
            cat propose.log
            echo '```'
            echo
            echo "Please open a new issue with the corrected files."
          } > comment.md
          gh issue comment "$ISSUE_NUMBER" --body-file comment.md
          gh issue edit "$ISSUE_NUMBER" --add-label "needs-changes"

      - name: Open draft pull request
        if: steps.propose.outputs.failed != 'true'
        env:
          GH_TOKEN: ${{ github.token }}
          ISSUE_NUMBER: ${{ github.event.issue.number }}
        run: |
          BRANCH="modality/issue-${ISSUE_NUMBER}"
          python scripts/ci/modality_issue_to_files.py pr-body > pr-body.md
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git checkout -b "$BRANCH"
          git add "proposals/issue-${ISSUE_NUMBER}"
          git commit -m "feat(modality): proposal from issue #${ISSUE_NUMBER}"
          git push origin "$BRANCH"
          gh pr create --draft --base main --head "$BRANCH" \
            --title "Propose new modality (issue #${ISSUE_NUMBER})" \
            --body-file pr-body.md
```

Note: `ISSUE_NUMBER` is an integer written by GitHub, passed through `env:` anyway.

- [ ] **Step 7: Add the CI gate for generated fixtures**

This is the "after registration" stage from the spec: while a proposal PR is a draft, this test is red because the modality is not registered yet (the validator skips unknown modality folders without an error, so the test asserts the modality is recognised through `stats.modalities`, not only that there are no errors); it turns green once the maintainer has applied `REGISTRATION.md`. With no `proposals/` folder it is skipped.

`tests/test_modality_proposal_fixtures.py`:

```python
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FIXTURES = sorted((REPO / "proposals").glob("*/fixture"))


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: p.parent.name)
def test_proposal_fixture_validates(fixture: Path) -> None:
    sys.path.insert(0, str(REPO / "app" / "src"))
    from runner import validate_dataset

    issues, stats = validate_dataset(str(fixture), run_bids=False)
    errors = [i[1] for i in issues if i[0] == "ERROR"]
    assert errors == [], f"{fixture.parent.name}: the fixture must validate"
    # The validator silently skips a modality folder it does not know, so
    # "no errors" alone would pass for an unregistered modality.
    modalities = [p.name for p in (fixture / "sub-01").iterdir() if p.is_dir()]
    unregistered = [m for m in modalities if stats.modalities.get(m, 0) < 1]
    assert not unregistered, (
        f"{fixture.parent.name}: modality {unregistered} is not registered yet; "
        f"follow its REGISTRATION.md"
    )
```

Run: `.venv/bin/python -m pytest tests/test_modality_proposal_fixtures.py -v`
Expected: SKIPPED (no `proposals/` folder on this branch).

- [ ] **Step 8: Run to verify pass and audit the workflow**

Run: `.venv/bin/python -m pytest tests/test_propose_modality_workflow.py tests/test_propose_modality_issue_form.py tests/test_modality_issue_to_files.py -v`
Expected: all PASS.

Run: `.venv/bin/python tests/verify_repo.py --check actions-security --no-fix`
Expected: no new findings for `propose-modality.yml`. If `zizmor` is not installed locally the check says so; in that case note it in the PR and rely on CI. If it flags the heredoc or permissions, fix the workflow, not the check.

- [ ] **Step 9: Commit**

```bash
git add .github scripts/ci/modality_issue_to_files.py tests/test_propose_modality_issue_form.py tests/test_modality_issue_to_files.py tests/test_propose_modality_workflow.py tests/test_modality_proposal_fixtures.py
git commit -m "feat(modality): Issue Form and bot that opens a draft PR from a proposal

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Docs, changelog and spec clarifications

**Files:**
- Create: `docs/MODALITY_PROPOSALS.md`
- Modify: `docs/index.rst` (add to the toctree that contains `SCHEMA_SPECIFICATIONS`, same indentation)
- Modify: `docs/CLI_REFERENCE.md` (new section)
- Modify: `CHANGELOG.md`
- Modify: `docs/superpowers/specs/2026-10-15-modality-registration-design.md`

- [ ] **Step 1: Write the user guide**

`docs/MODALITY_PROPOSALS.md`:

```markdown
# Proposing a New Modality

PRISM describes data belonging to a subject as a data file plus a JSON sidecar.
Surveys, biometrics, physiology and the other modalities all follow this
principle, and so can yours (for example blood samples drawn alongside MRI).

New modalities are added to PRISM itself: you propose one, a maintainer
registers it, and it ships with the next release.

## What you need

1. The workbook `official/create_new_modality/modality_proposal_template.xlsx`
   (it opens in Excel, LibreOffice and Numbers).
   - Sheet `Modality`: `Name`, `Suffix`, `Extensions`, `Description`, `Rationale`.
   - Sheet `Types` (optional): a short vocabulary of the measurements your
     modality knows (for example CRP, glucose, cortisol), each with a
     description. A column can then carry a `Type` from this list or `other`, so
     the same measurement gets the same name across studies even when column
     names differ. New types are added later through an upstream pull request.
   - Sheet `Columns`: the columns of your **sample file**, as an example (two or
     three are enough; every study defines its own columns in its own sidecar),
     with `ID`,
     `Description`, `Units`, `DataType` (string, integer or float; guessed if
     empty), `Scale` (optional drop-down: categorical, continuous or boolean;
     leave empty for identifiers, times and free text), `Min`, `Max`,
     `AllowedValues` (separated by `;`). A continuous column must be a number
     without `AllowedValues`, a categorical column needs its categories in
     `AllowedValues`, a boolean column needs exactly two (for example `yes; no`).
2. A small **synthetic** sample data file in the same format as your real data:
   at most 50 rows and 1 MB. Its header must match the `Columns` sheet. Never
   use real participant data.

## Choosing a name and suffix

Both must be lowercase letters and digits, starting with a letter, and must
not already be used by PRISM or BIDS. `blood` for example is a BIDS suffix
(blood radioactivity in PET). The check tells you what a taken name means.

## Submit it

**On GitHub:** open a *Propose a New Modality* issue, drag in the workbook and
the sample file, tick the privacy box. A bot checks both and opens a draft pull
request, or comments what to fix.

**From the command line:**

    python prism_tools.py modality propose my_proposal.xlsx --sample my_sample.tsv --check
    python prism_tools.py modality propose my_proposal.xlsx --sample my_sample.tsv --out my_modality

`--check` only validates. The second command writes the schema, an example
sidecar, a small dataset to test with, and `REGISTRATION.md`. YAML or JSON can
be used instead of the workbook (see `examples/modality_proposal/`).

## What happens next

A maintainer follows `REGISTRATION.md` (copy the schema, add the modality to
`entities.schema.json`, run the checks) and reviews units, ranges and the
sample. After the merge the modality is available in the next PRISM release.
```

- [ ] **Step 2: Wire it into the docs and changelog**

In `docs/index.rst`, add the line `   MODALITY_PROPOSALS` directly after the `   SCHEMA_SPECIFICATIONS` line (same indentation).

In `docs/CLI_REFERENCE.md`, append a section:

```markdown
## modality propose

Check a modality proposal and generate its schema, example sidecar, fixture
dataset and `REGISTRATION.md`.

    python prism_tools.py modality propose <proposal.xlsx|.yml|.json> --sample <file> [--out <dir>] [--check] [--json]

- `--sample`: synthetic sample data file (required).
- `--out`: output folder (required unless `--check`).
- `--check`: validate only, write nothing.
- `--json`: machine-readable output.

Exit code 0 on success, 1 if any problem is an error. See `MODALITY_PROPOSALS.md`.
```

In `CHANGELOG.md`, insert directly under `## [Unreleased]` (before `### Security`):

```markdown
### Added
- **Modality proposals.** A new modality can be proposed with a filled-in Excel workbook and a small synthetic
  sample file: `prism_tools.py modality propose` checks names against PRISM and BIDS, checks the sample against
  the column dictionary, and generates the schema, an example sidecar, a fixture dataset and maintainer
  registration steps. A GitHub Issue Form and bot open a draft pull request from the same files.

```

- [ ] **Step 3: Clarify the spec**

In `docs/superpowers/specs/2026-10-15-modality-registration-design.md`:

1. In the "Generated artifacts" table, replace the `<name>.schema.json` row with:
   `| \`<name>.schema.json\` | draft-07, same envelope as \`biometrics.schema.json\`: the \`Technical\`/\`Study\`/\`Metadata\` blocks plus the shape of a column definition (\`additionalProperties\`); passes the existing \`modality-schema-conventions\` check. The column dictionary itself is written into the example sidecar, as in real templates. |`
2. In the "Bot (GitHub Actions)" section, replace step 1 with: "Read the two upload fields of the form (`Proposal file`, `Sample data file`); each must contain exactly one `https://github.com/user-attachments/` upload", and in step 3 replace `proposals/<name>/` with `proposals/issue-<n>/`.
3. In "Issue Form", replace the second bullet with: "Two textareas, `Proposal file` and `Sample data file`, each for one dragged-in file."

- [ ] **Step 4: Run the related tests**

Run: `.venv/bin/python -m pytest tests -q -k "docs or cli or verify_repo or modality or issue" `
Expected: PASS. If a docs-consistency test complains about the new page or CLI section, fix the docs, not the test.

- [ ] **Step 5: Commit**

```bash
git add docs CHANGELOG.md
git commit -m "docs(modality): user guide, CLI reference, changelog, spec clarifications

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Full verification and pre-merge audit

**Files:** none new.

- [ ] **Step 1: Run the whole test suite and the repo checks**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (report the exact counts; any failure is investigated, not skipped).

Run: `.venv/bin/python tests/verify_repo.py --check dual-tree-drift --no-fix`
Expected: no new drift (the new module exists only under `src/`).

Run: `.venv/bin/python tests/verify_repo.py --no-fix` and read the summary. Expected: no new failures compared with `main`.

- [ ] **Step 2: Try it with the real blood example end to end**

Run: `.venv/bin/python prism_tools.py modality propose official/create_new_modality/modality_proposal_template.xlsx --sample examples/modality_proposal/biosample_sample.tsv --out <scratchpad>/biosample-out`
Expected: files written, exit 0; open `REGISTRATION.md` and confirm the steps read correctly.

Run the same with `--sample` pointing at a copy of the sample with one value changed to `abc` in the `crp` column.
Expected: exit 1 and an error naming the row and column.

- [ ] **Step 3: Run the audit required by CLAUDE.md**

Invoke `/ponytail:ponytail-audit` on the branch. Apply the findings that are worth it (or write down why not), re-run Step 1, and only then merge or open the PR.

- [ ] **Step 4: Hand over**

Report to the user: test counts, anything skipped, and that the first real proposal (blood) can now go through the form once their colleague has chosen the final name and suffix.
