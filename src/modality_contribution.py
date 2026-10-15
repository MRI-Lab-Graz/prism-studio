"""Build minimal valid PRISM datasets for a proposed modality or template.

Shared by the CI contribution-contract check and the Issue-Form-to-draft-PR
bot (spec: docs/superpowers/specs/2026-09-11-modality-contribution-workflow-design.md,
section 1.2 item 3) so the manual and guided contribution paths produce and
are held to the exact same dataset shape.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


def write_minimal_dataset(
    dest_dir: Path,
    *,
    suffix: str,
    extension: str,
    sidecar: dict,
    data_content: str,
    task_name: str = "demo",
) -> Path:
    """Write a minimal valid PRISM dataset for one subject/modality.

    Creates dataset_description.json and sub-01/<suffix>/ containing the
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

    modality_dir = dest_dir / "sub-01" / suffix
    modality_dir.mkdir(parents=True, exist_ok=True)

    stem = f"sub-01_task-{task_name}_{suffix}"
    data_path = modality_dir / f"{stem}.{extension}"
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
