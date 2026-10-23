"""Modality registration and contribution helpers.

Reads a modality proposal (workbook, YAML or JSON), checks it and its sample
data file, and generates the schema, example sidecar and registration files.
Also builds minimal valid PRISM datasets, shared by the CI contribution-contract
check and the Issue-Form-to-draft-PR bot. Spec:
docs/superpowers/specs/2026-10-15-modality-registration-design.md
"""

from __future__ import annotations

import csv
import datetime
import gzip
import html
import io
import itertools
import json
import math
import re
import shutil
import zlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


def write_minimal_dataset(
    dest_dir: Path,
    *,
    suffix: str,
    extension: str,
    sidecar: dict,
    data_content: str | bytes,
    task_name: str | None = "demo",
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

    stem = f"sub-01_task-{task_name}_{suffix}" if task_name else f"sub-01_{suffix}"
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
TYPE_OTHER = "other"  # reserved escape value, added to every vocabulary
ENTITY_SUGGESTIONS = ("task", "acq")
NOT_EXTENDABLE = {
    "environment": (
        "'environment' cannot take a new suffix this way: its rules (a fixed column set, the "
        "ses-*/environment/ folder, a required recording entity) cannot be met by a generated "
        "fixture. Propose a new modality instead."
    ),
}


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
    if isinstance(allowed_raw, bool) or isinstance(raw.get("type"), bool):
        raise ProposalError(
            f"column '{cid}': type/allowed_values was read as a YAML boolean "
            "(yes/no/on/off/true/false); put the values in quotes"
        )
    units = _clean_key(raw.get("units")) or "n/a"
    allowed = _parse_allowed_values(allowed_raw)
    bounds = []
    for label in ("min", "max"):
        text = _clean_key(raw.get(label))
        number = _parse_float(raw.get(label))
        if text and number is None:
            raise ProposalError(f"column '{cid}': {label.capitalize()} '{text}' is not a number")
        bounds.append(number)
    lo, hi = bounds
    return {
        "id": cid,
        "description": _clean_key(raw.get("description")) or "",
        "units": units,
        "datatype": _infer_datatype(raw.get("datatype"), units, allowed, lo, hi),
        "scale": (_clean_key(raw.get("scale")) or "").lower() or None,
        "type": _clean_key(raw.get("type")) or None,
        "min": lo,
        "max": hi,
        "allowed_values": allowed,
    }


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


def _normalize_entities(raw) -> list[dict]:
    from src.converters.excel_to_biometrics import _clean_key

    out = []
    for item in raw or []:
        if not isinstance(item, dict):
            raise ProposalError("entities: every entry must be a mapping with entity, value, description")
        if item.get("value") is not None and not isinstance(item.get("value"), str):
            # labels are free-form strings; never coerce (01 would silently become 1)
            raise ProposalError(
                f"entities: value {item.get('value')!r} was read as a number or YAML boolean "
                "(yes/no/on/off/true/false); labels are text, put the values in quotes"
            )
        out.append({
            "entity": (_clean_key(item.get("entity")) or "").lower(),
            "value": _clean_key(item.get("value")) or "",
            "description": _clean_key(item.get("description")) or "",
        })
    return out


def _finish_proposal(base: dict, rows: list[dict], types=None, entities=None) -> dict:
    exts = base.get("extensions")
    if exts is not None and not isinstance(exts, (list, str)):
        raise ProposalError("'extensions' must be a list or a comma-separated string")
    if isinstance(exts, str):
        exts = exts.split(",")
    proposal: dict[str, Any] = {
        key: str(base.get(key) or "").strip()
        for key in ("modality", "suffix", "description")
    }
    proposal["extensions"] = [
        str(e).strip().lstrip(".").lower() for e in (exts or []) if str(e).strip()
    ]
    proposal["columns"] = [_normalize_column(r) for r in rows]
    proposal["types"] = _normalize_types(types)
    proposal["entities"] = _normalize_entities(entities)
    return proposal


def _read_workbook(path: Path) -> tuple[dict, list[dict], list[dict], list[dict]]:
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
            ("datatype", {"datatype", "data_type"}),
            ("scale", {"scale", "measurementscale", "measurement_scale"}),
            ("type", {"type"}),
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
    entities: list[dict] = []
    if "Entities" in sheets and len(sheets["Entities"]):
        esheet = sheets["Entities"]
        eheader = [str(v) for v in esheet.iloc[0].tolist()]
        e_idx = find_column_idx(eheader, {"Entity"})
        v_idx = find_column_idx(eheader, {"Value"})
        d_idx = find_column_idx(eheader, {"Description"})
        if e_idx is None or v_idx is None:
            raise ProposalError("sheet 'Entities' needs 'Entity' and 'Value' columns")
        for i in range(1, len(esheet)):
            row = esheet.iloc[i]
            if cell(row, e_idx) or cell(row, v_idx):
                entities.append({"entity": cell(row, e_idx), "value": cell(row, v_idx), "description": cell(row, d_idx)})
    return base, rows, types, entities


def read_proposal(path) -> dict:
    """Read a modality proposal (.xlsx, .yml/.yaml or .json) into one dict."""
    path = Path(path)
    kind = path.suffix.lower()
    if kind == ".xlsx":
        base, rows, types, entities = _read_workbook(path)
        return _finish_proposal(base, rows, types, entities)
    if kind in {".yml", ".yaml", ".json"}:
        import yaml  # JSON is a YAML subset, one reader covers both

        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            raise ProposalError(f"cannot read {path.name}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ProposalError(f"{path.name}: top level must be a mapping")
        rows = raw.get("columns") or []
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise ProposalError(f"{path.name}: 'columns' must be a list of mappings")
        raw_types = raw.get("types")
        if raw_types is not None and not isinstance(raw_types, list):
            raise ProposalError(f"{path.name}: 'types' must be a list")
        raw_entities = raw.get("entities")
        if raw_entities is not None and not isinstance(raw_entities, list):
            raise ProposalError(f"{path.name}: 'entities' must be a list")
        return _finish_proposal(raw, rows, raw_types, raw_entities)
    raise ProposalError(
        f"unsupported proposal file type '{path.suffix}' (use .xlsx, .yml, .yaml or .json)"
    )


def write_proposal_workbook(proposal: dict, path) -> None:
    """Write a proposal as a two-sheet workbook (the format users fill in)."""
    import openpyxl

    wb = openpyxl.Workbook()
    mod = wb.active
    mod.title = "Modality"
    mod.append(["Name", "Suffix", "Extensions", "Description"])
    mod.append([
        proposal["modality"],
        proposal["suffix"],
        ", ".join(proposal["extensions"]),
        proposal["description"],
    ])
    cols = wb.create_sheet("Columns")
    cols.append(["ID", "Description", "Units", "DataType", "Scale", "Type", "Min", "Max", "AllowedValues"])
    for c in proposal["columns"]:
        cols.append([
            c["id"],
            c["description"],
            c["units"],
            c["datatype"],
            c["scale"],
            c["type"],
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
    types_ws = wb.create_sheet("Types")
    types_ws.append(["Value", "Description"])
    for t in proposal["types"]:
        types_ws.append([t["value"], t["description"] or None])
    ents = wb.create_sheet("Entities")
    ents.append(["Entity", "Value", "Description"])
    for e in proposal["entities"]:
        ents.append([e["entity"], e["value"], e["description"] or None])
    wb.save(path)


_NAME_RE = re.compile(r"^[a-z][a-z0-9]*$")
_EXT_RE = re.compile(r"^[a-z0-9]+(\.[a-z0-9]+)*$")
_COLUMN_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")
_TYPE_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_ENTITY_VALUE_RE = re.compile(r"^[A-Za-z0-9]+$")


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


def _entities_schema(schema_dir: str | None) -> dict:
    from src.schema_manager import DEFAULT_SCHEMA_DIR, load_schema

    return load_schema("entities", schema_dir or DEFAULT_SCHEMA_DIR, "stable") or {}


def proposal_kind(proposal: dict, schema_dir: str | None = None) -> str:
    """'extension' = add a suffix to an existing PRISM modality, else 'new'."""
    rule = _entities_schema(schema_dir).get("modalities", {}).get(proposal.get("modality"), {})
    return "extension" if rule.get("kind") == "prism" else "new"


def _taken_names(schema_dir: str | None) -> dict[str, str]:
    """Every name a new modality or suffix may not use, with the reason."""
    entities = _entities_schema(schema_dir)
    taken: dict[str, str] = {}
    for name, rule in entities.get("modalities", {}).items():
        taken[name] = f"PRISM modality '{name}'"
        for suffix in rule.get("suffixes", []):
            taken.setdefault(suffix, f"PRISM suffix '{suffix}' (modality '{name}')")
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
    entities_schema = _entities_schema(schema_dir)
    kind = proposal_kind(proposal, schema_dir)
    name, suffix = proposal.get("modality") or "", proposal.get("suffix") or ""
    bids_modalities = {
        n for n, r in entities_schema.get("modalities", {}).items() if r.get("kind") != "prism"
    }
    for value, label in ((name, "Name"), (suffix, "Suffix")):
        where = f"Modality.{label}"
        if not _NAME_RE.match(value):
            err(where, f"'{value}' must be lowercase letters and digits, starting with a letter")
    if _NAME_RE.match(name):
        if name in bids_modalities or (name in taken and kind == "new" and taken[name].startswith("BIDS")):
            err(
                "Modality.Name",
                f"{taken.get(name, name)}: BIDS owns this folder; propose the suffix to BIDS upstream "
                "(https://bids.neuroimaging.io), not here.",
            )
        elif kind == "new" and name in taken:
            err("Modality.Name", f"'{name}' is already taken: {taken[name]}. Choose another name.")
    if _NAME_RE.match(suffix) and suffix in taken:
        err("Modality.Suffix", f"'{suffix}' is already taken: {taken[suffix]}. Choose another suffix.")
    if kind == "extension" and name in NOT_EXTENDABLE:
        err("Modality.Name", NOT_EXTENDABLE[name])
    if kind == "extension" and proposal.get("entities"):
        err("Entities", "entity suggestions are not used when adding a suffix to an existing modality; remove them")

    extensions = proposal.get("extensions") or []
    if not extensions:
        err("Modality.Extensions", "at least one data file extension is required")
    for ext in extensions:
        if not _EXT_RE.match(ext):
            err("Modality.Extensions", f"'{ext}' is not a valid extension (e.g. tsv, tsv.gz)")

    if not (proposal.get("description") or "").strip():
        err("Modality.Description", "must not be empty")

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

    seen_entities: set[tuple[str, str]] = set()
    for n, e in enumerate(proposal.get("entities") or [], start=1):
        where = f"Entities.{e['entity']}-{e['value']}" if e["value"] else f"Entities row {n}"
        if e["entity"] not in ENTITY_SUGGESTIONS:
            err(where, f"only {list(ENTITY_SUGGESTIONS)} values can be suggested, got '{e['entity']}'")
        if not _ENTITY_VALUE_RE.match(e["value"]):
            err(where, f"'{e['value']}' may only contain letters and digits")
        if (e["entity"], e["value"]) in seen_entities:
            err(where, f"duplicate suggestion '{e['entity']}-{e['value']}'")
        seen_entities.add((e["entity"], e["value"]))

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
        if cid.lower() in _SIDECAR_BLOCKS:
            err(where, f"'{cid}' is a reserved sidecar block name; choose another column ID")
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
        ctype = col.get("type")
        if ctype is not None:
            if not types:
                err(where, f"Type '{ctype}' is given but the proposal defines no types")
            elif ctype != TYPE_OTHER and ctype not in type_values:
                err(where, f"Type '{ctype}' is not in the vocabulary; use one of {sorted(type_values)} or '{TYPE_OTHER}'")
    if kind == "extension" and not errors_only(problems):  # the fit check needs a well-formed proposal
        problems += check_extension_fit(proposal, schema_dir)
    return problems


_SIDECAR_BLOCKS = {"technical", "study", "metadata"}
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
    header = rows[0]
    data = [r for r in rows[1:] if any(c.strip() for c in r)]
    columns = {c["id"]: c for c in proposal.get("columns") or []}
    duplicated = sorted({h for h in header if header.count(h) > 1})
    if duplicated:
        problems.append(Problem("error", name, f"duplicate column(s): {', '.join(map(repr, duplicated))}"))
    missing = [c for c in columns if c not in header]
    extra = [h for h in header if h not in columns]
    if missing:
        problems.append(Problem("error", name, f"missing column(s): {', '.join(map(repr, missing))}"))
    if extra:
        problems.append(Problem("error", name, f"unexpected column(s): {', '.join(map(repr, extra))}"))
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
                if not math.isfinite(number):
                    problems.append(Problem("error", where, f"'{value}' is not a finite number"))
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
    if col.get("type"):
        out["Type"] = col["type"]
    return out


def build_schema(proposal: dict) -> dict:
    """The modality schema: PRISM envelope plus the column-definition shape."""
    name, suffix, exts = proposal["modality"], proposal["suffix"], proposal["extensions"]
    schema: dict[str, Any] = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": f"https://prism.org/schemas/{name}/v1.0.0",
        "version": "1.0.0",
        "title": f"{name.capitalize()} Metadata",
        "description": (
            f"{proposal['description'].rstrip('.')}. Files should be named: "
            f"sub-<label>[_ses-<label>][_task-<label>][_acq-<label>][_run-<index>]_{suffix}.<{'|'.join(exts)}>"
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
                "required": ["OriginalName"],
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


def build_example_sidecar(proposal: dict, today: str | None = None) -> dict:
    name = proposal["modality"]
    sidecar = {
        "Technical": {"FileFormat": proposal["extensions"][0]},
        "Study": {
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


FIXED_ENTITIES = ["task", "acq", "run"]


def registration_entry(proposal: dict, existing: dict | None = None) -> dict:
    if existing is not None:  # adding a suffix to an existing modality
        entry = dict(existing)
        entry["suffixes"] = [*existing.get("suffixes", []), proposal["suffix"]]
        entry["extensions"] = list(dict.fromkeys([*existing.get("extensions", []), *proposal["extensions"]]))
        return entry
    exts = list(dict.fromkeys([*proposal["extensions"], "json"]))
    entry = {"kind": "prism", "suffixes": [proposal["suffix"]], "extensions": exts,
             "allowedEntities": list(FIXED_ENTITIES)}
    values: dict[str, list[str]] = {}
    for e in proposal.get("entities") or []:
        values.setdefault(e["entity"], []).append(e["value"])
    if values:
        entry["optionalEntityValues"] = {
            k: {"enum": v, "allowOther": True, "otherPattern": "[a-zA-Z0-9]+"} for k, v in values.items()
        }
    return entry


def _pattern(suffix: str) -> str:
    return f"sub-<label>[_ses-<label>][_task-<label>][_acq-<label>][_run-<index>]_{suffix}.<extension>"


def _text(value) -> str:
    """Contributor text for a docs page: HTML-escaped (MyST passes raw HTML through)."""
    return html.escape(str(value), quote=False)


def _cell(value) -> str:
    return _text(value).replace("|", r"\|")


def _purpose(proposal: dict) -> str:
    return f"{_text(proposal['description']).rstrip('.')}."


def _columns_lines(proposal: dict) -> list[str]:
    return ["## Example Columns", "", "Every study defines its own columns in its own sidecar; these are examples.", "",
            "| Column | Description | Units |", "| --- | --- | --- |",
            *(f"| `{c['id']}` | {_cell(c['description'])} | {_cell(c['units'])} |" for c in proposal["columns"]), ""]


def _sidecar_lines(suffix: str) -> list[str]:
    return ["## Sidecar JSON", "",
            f"Each data file needs a JSON sidecar (`*_{suffix}.json`) with `Technical`, `Study` and `Metadata` blocks "
            "and one definition per column (Description, Units, optional MinValue/MaxValue/AllowedValues).", ""]


def build_docs_page(proposal: dict) -> str:
    name, suffix = proposal["modality"], proposal["suffix"]
    exts = ", ".join(f"`.{e}`" for e in proposal["extensions"])
    lines = [
        f"# {name.capitalize()}", "", _purpose(proposal), "",
        "## File Name Structure", "", f"`{_pattern(suffix)}`", "",
        "| Entity | Description |", "| --- | --- |",
        "| `sub` | **Required**. The subject identifier. |",
        "| `ses` | Optional. The session identifier. |",
        "| `task` | Optional. The task or protocol, when the data belong to one. |",
        "| `acq` | Optional. A variant of the acquisition. |",
        "| `run` | Optional. The repeat within a session. |",
        f"| `{suffix}` | **Required**. The suffix indicating the data. |",
        f"| extension | **Required**. One of {exts}. |", "",
    ]
    if proposal.get("entities"):
        lines += ["### Suggested values", "", "Other labels are accepted too.", ""]
        lines += [
            f"- `{e['entity']}-{e['value']}`" + (f": {_text(e['description'])}" if e["description"] else "")
            for e in proposal["entities"]
        ] + [""]
    lines += _columns_lines(proposal)
    if proposal.get("types"):
        lines += ["### Types", "", f"Values for a column's `Type` field (`{TYPE_OTHER}` for anything not listed):", ""]
        lines += [
            f"- `{t['value']}`" + (f": {_text(t['description'])}" if t["description"] else "")
            for t in proposal["types"]
        ] + [""]
    lines += _sidecar_lines(suffix)
    lines += ["Example:", "", "```json", json.dumps(build_example_sidecar(proposal), indent=2), "```", "",
              "To propose a change or a new modality, see the [contribution guide](../MODALITY_PROPOSALS.md).", ""]
    return "\n".join(lines)


def _extension_docs_section(proposal: dict) -> str:
    """The section to add to an existing modality's page; that page's own naming rules apply."""
    suffix = proposal["suffix"]
    exts = ", ".join(f"`_{suffix}.{e}`" for e in proposal["extensions"])
    tail = "\n".join(_columns_lines(proposal) + _sidecar_lines(suffix))
    tail = re.sub(r"(?m)^## ", "### ", tail)
    return (f"## Suffix `_{suffix}`\n\n{_purpose(proposal)}\n\n"
            f"File names follow the naming rules on this page, ending in {exts}.\n\n{tail}")


def build_docs_snippets(proposal: dict) -> dict[str, str]:
    name, suffix = proposal["modality"], proposal["suffix"]
    exts = ", ".join(f"`{e}`" for e in [*proposal["extensions"], "json"])
    return {
        "toctree": f"   specs/{name}",
        "entities_row": f"| `{name}` | prism | `{suffix}` | {exts} | optional `task`, `acq`, `run` |",
        "card": (
            '  <a class="prism-chapter-card" href="specs/%s.html">\n'
            '    <span class="prism-chapter-title">%s</span>\n'
            '    <span class="prism-chapter-outcome">%s</span>\n'
            "  </a>" % (name, name.capitalize(), html.escape(proposal["description"]))
        ),
    }


def _target_schema(proposal: dict, schema_dir: str | None = None) -> dict:
    from src.schema_manager import DEFAULT_SCHEMA_DIR, load_schema

    return load_schema(proposal["modality"], schema_dir or DEFAULT_SCHEMA_DIR, "stable") or {}


def _fit_sidecar(sidecar: dict, schema: dict, label: str) -> dict:
    # ponytail: fills a block's missing required key only with the first enum value or, for a
    # plain string the label fits, the suffix name; other keys are left for the maintainer.
    for block, spec in schema.get("properties", {}).items():
        if block not in sidecar or not isinstance(spec, dict):
            continue
        for key in spec.get("required", []):
            prop = spec.get("properties", {}).get(key)
            if key in sidecar[block] or not isinstance(prop, dict):
                continue
            if prop.get("enum"):
                sidecar[block][key] = prop["enum"][0]
            elif "string" in (prop_type if isinstance(prop_type := prop.get("type"), list) else [prop_type]) \
                    and re.search(prop.get("pattern", ""), label):
                sidecar[block][key] = label
            # anything else stays missing, so check_extension_fit names it instead of a wrong value
    return sidecar


def check_extension_fit(proposal: dict, schema_dir: str | None = None) -> list[Problem]:
    """Warn when the generated example sidecar does not match the target modality's own schema."""
    import jsonschema

    schema = _target_schema(proposal, schema_dir)
    if not schema:
        return []
    sidecar = _fit_sidecar(build_example_sidecar(proposal), schema, proposal["suffix"])
    return [
        Problem("warning", f"{proposal['modality']}.schema.json",
                f"{'/'.join(str(x) for x in e.absolute_path)}: {e.message}" if e.absolute_path else e.message)
        for e in jsonschema.Draft7Validator(schema).iter_errors(sidecar)
    ]


def build_registration_md(proposal: dict, existing: dict | None = None) -> str:
    name, suffix = proposal["modality"], proposal["suffix"]
    snippet = json.dumps({name: registration_entry(proposal, existing)}, indent=2)
    review = """Review by hand what no check can judge: units, a modality that duplicates an
existing one under another name, and whether the sample holds any real
participant data.
"""
    if existing is not None:
        return f"""# Adding the `_{suffix}` suffix to the `{name}` modality (maintainer steps)

PRISM does not register suffixes automatically. Do these steps by hand in the
pull request, then let CI validate the fixture in this folder.

1. In `app/schemas/stable/entities.schema.json`, replace the `"{name}"` entry
   under `"modalities"` with this one (the suffix and any new extensions are
   appended):

```json
{snippet}
```

2. Documentation (CI check `modality-docs` fails without it): add the section
   from `docs/{name}-{suffix}.md` to `docs/specs/{name}.md` (the page must
   mention `_{suffix}`), and add `{suffix}` to the Suffixes column of the
   `{name}` row in `docs/specs/entities.md`.
3. Check the registration:
   `python tests/verify_repo.py --check schema-sync` and
   `python tests/verify_repo.py --check modality-docs`.
4. Validate the generated dataset: from the repository root, run
   `python prism.py <this folder>/fixture`. It must pass without errors.

The example sidecar uses the `{name}` modality's own schema; keys that schema
requires were filled in heuristically, so check them before relying on the
example.

{review}"""
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
4. Documentation (CI check `modality-docs` fails without it):
   - copy `docs/{name}.md` to `docs/specs/{name}.md`;
   - add `   specs/{name}` to the "Schema Specifications" toctree in `docs/index.rst`;
   - add the card from `docs/snippets.md` to `docs/SCHEMA_SPECIFICATIONS.md`;
   - add the row from `docs/snippets.md` to the table in `docs/specs/entities.md`.
5. Check the registration:
   `python tests/verify_repo.py --check schema-sync`,
   `python tests/verify_repo.py --check modality-schema-conventions` and
   `python tests/verify_repo.py --check modality-docs`.
6. Validate the generated dataset: from the repository root, run
   `python prism.py <this folder>/fixture`. It must pass without errors.

{review}"""


def build_modality_artifacts(proposal: dict, sample_path, proposal_path, out_dir) -> list[Path]:
    """Write schema (new modality only), example sidecar, fixture, docs, REGISTRATION.md and input copies.

    Call check_proposal() and check_sample() first; this does not re-check.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sample, source = Path(sample_path), Path(proposal_path)
    name, suffix = proposal["modality"], proposal["suffix"]
    ext = sample_extension(sample, proposal["extensions"]) or ""
    is_new = proposal_kind(proposal) == "new"
    existing = None if is_new else _entities_schema(None)["modalities"][name]

    written: list[Path] = []
    if is_new:
        schema_path = out / f"{name}.schema.json"
        schema_path.write_text(json.dumps(build_schema(proposal), indent=2) + "\n", encoding="utf-8")
        written.append(schema_path)
    sidecar = build_example_sidecar(proposal)
    if not is_new:
        sidecar = _fit_sidecar(sidecar, _target_schema(proposal), suffix)
    sidecar["Technical"]["FileFormat"] = ext
    sidecar_path = out / "example_sidecar.json"
    sidecar_path.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
    write_minimal_dataset(
        out / "fixture",
        modality=name,
        suffix=suffix,
        extension=ext,
        sidecar=sidecar,
        data_content=sample.read_bytes(),
        task_name=None if is_new else ((existing or {}).get("example", {}).get("task") or suffix),
    )
    docs = out / "docs"
    docs.mkdir(exist_ok=True)
    if is_new:
        page = docs / f"{name}.md"
        page.write_text(build_docs_page(proposal), encoding="utf-8")
        snippets_path = docs / "snippets.md"
        s = build_docs_snippets(proposal)
        snippets_path.write_text(
            f"# Docs snippets for `{name}`\n\n"
            f"Toctree line for docs/index.rst:\n\n```\n{s['toctree']}\n```\n\n"
            f"Row for the table in docs/specs/entities.md:\n\n```\n{s['entities_row']}\n```\n\n"
            f"Card for docs/SCHEMA_SPECIFICATIONS.md:\n\n```html\n{s['card']}\n```\n",
            encoding="utf-8",
        )
        written += [page, snippets_path]
    else:
        page = docs / f"{name}-{suffix}.md"
        page.write_text(_extension_docs_section(proposal), encoding="utf-8")
        written.append(page)
    registration_path = out / "REGISTRATION.md"
    registration_path.write_text(build_registration_md(proposal, existing), encoding="utf-8")
    proposal_copy = out / f"proposal{source.suffix.lower()}"
    shutil.copyfile(source, proposal_copy)
    sample_copy = out / f"sample.{ext}"
    shutil.copyfile(sample, sample_copy)

    fixture = out / "fixture"
    fixture_files = [p for p in sorted(fixture.rglob("*")) if p.is_file()]
    return [*written, sidecar_path, registration_path, proposal_copy, sample_copy, *fixture_files]
