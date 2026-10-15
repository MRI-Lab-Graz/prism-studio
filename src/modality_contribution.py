"""Build minimal valid PRISM datasets for a proposed modality or template.

Shared by the CI contribution-contract check and the Issue-Form-to-draft-PR
bot (spec: docs/superpowers/specs/2026-09-11-modality-contribution-workflow-design.md,
section 1.2 item 3) so the manual and guided contribution paths produce and
are held to the exact same dataset shape.
"""

from __future__ import annotations

import csv
import datetime
import gzip
import io
import itertools
import json
import re
import shutil
import zlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def write_minimal_dataset(
    dest_dir: Path,
    *,
    suffix: str,
    extension: str,
    sidecar: dict,
    data_content: str | bytes,
    task_name: str = "demo",
    modality: str | None = None,
) -> Path:
    """Write a minimal valid PRISM dataset for one subject/modality.

    Creates dataset_description.json and sub-01/<modality>/ (default <suffix>) containing the
    data file plus its matching JSON sidecar. Returns the path to the
    created data file.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    dataset_description = {
        "Name": "PRISM Contribution Fixture",
        "BIDSVersion": "1.10.1",
        "DatasetType": "raw",
        "Authors": ["prism-contribution-fixture"],
        "Keywords": ["prism", "contribution-fixture", "template"],
    }
    (dest_dir / "dataset_description.json").write_text(
        json.dumps(dataset_description, indent=2), encoding="utf-8"
    )

    modality_dir = dest_dir / "sub-01" / (modality or suffix)
    modality_dir.mkdir(parents=True, exist_ok=True)

    stem = f"sub-01_task-{task_name}_{suffix}"
    data_path = modality_dir / f"{stem}.{extension}"
    if isinstance(data_content, bytes):
        data_path.write_bytes(data_content)
    else:
        data_path.write_text(data_content, encoding="utf-8")

    sidecar_path = modality_dir / f"{stem}.json"
    sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

    return data_path


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
    # utf-8-sig drops an Excel BOM; newline="" lets csv handle CRLF. The read
    # is bounded so a decompression bomb cannot exhaust memory.
    opener = gzip.open if ext.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as fh:
        text = fh.read(SAMPLE_MAX_BYTES + 1)
    if len(text) > SAMPLE_MAX_BYTES:
        raise ValueError("content is larger than 1 MB (after decompression)")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter="\t")
    return list(itertools.islice(reader, SAMPLE_MAX_ROWS + 2))


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
    except (OSError, ValueError, EOFError, gzip.BadGzipFile, csv.Error, zlib.error) as exc:
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
