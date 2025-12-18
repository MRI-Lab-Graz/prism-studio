"""Biometrics data conversion helpers.

This module converts a tabular biometrics export (CSV/XLSX) into a minimal
PRISM/BIDS-style dataset structure that remains compatible with BIDS tools.

Assumptions (kept intentionally simple):
- Input data is "wide": one row per participant (optionally with a session column)
  and one column per biometrics variable.
- Biometrics templates exist in a library folder as `biometrics-<task>.json`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import json


_NON_ITEM_TOPLEVEL_KEYS: set[str] = {"Technical", "Study", "Metadata", "I18n", "LimeSurvey"}


@dataclass
class BiometricsConvertResult:
    id_column: str
    session_column: str | None
    tasks_included: list[str]
    unknown_columns: list[str]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _norm_col(s: str) -> str:
    return str(s).strip().lower().replace(" ", "").replace("_", "")


def _find_col(df: "Any", candidates: set[str]) -> str | None:
    wanted = {_norm_col(c) for c in candidates}
    for c in list(df.columns):
        if _norm_col(c) in wanted:
            return str(c)
    return None


def _normalize_sub_id(pid: str) -> str:
    pid = str(pid).strip()
    if not pid:
        return ""
    return pid if pid.startswith("sub-") else f"sub-{pid}"


def _normalize_ses_id(value: Any, *, default_session: str = "ses-1") -> str:
    ses = str(value).strip() if value is not None else ""
    if not ses or ses.lower() == "nan":
        return default_session
    if ses.startswith("ses-"):
        return ses

    import re

    m = re.match(r"^(?:t|visit)?\s*(\d+)\s*$", ses, flags=re.IGNORECASE)
    if m:
        return f"ses-{int(m.group(1)):02d}"

    return f"ses-{ses}"


def _read_table_as_dataframe(*, input_path: Path, sheet: str | int | None = None) -> "Any":
    try:
        import pandas as pd
    except Exception as e:  # pragma: no cover
        raise RuntimeError("pandas is required for biometrics conversion") from e

    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(input_path)
    if suffix == ".xlsx":
        sheet_name: str | int | None = sheet
        if sheet_name is None:
            sheet_name = 0
        if isinstance(sheet_name, str) and sheet_name.isdigit():
            sheet_name = int(sheet_name)
        return pd.read_excel(input_path, sheet_name=sheet_name)

    raise ValueError("Only .csv and .xlsx files are supported for biometrics conversion")


def _load_biometrics_library(library_dir: Path) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]]]:
    """Return (task->items, task->template_json)."""
    task_to_items: dict[str, list[str]] = {}
    task_to_template: dict[str, dict[str, Any]] = {}

    for p in sorted(library_dir.glob("biometrics-*.json")):
        task = p.stem[len("biometrics-") :]
        if not task:
            continue
        try:
            data = _read_json(p)
        except Exception:
            continue

        items = [k for k in data.keys() if k not in _NON_ITEM_TOPLEVEL_KEYS]
        if not items:
            continue
        task_to_items[task] = items
        task_to_template[task] = data

    return task_to_items, task_to_template


def convert_biometrics_table_to_prism_dataset(
    *,
    input_path: str | Path,
    library_dir: str | Path,
    output_root: str | Path,
    id_column: str | None = None,
    session_column: str | None = None,
    sheet: str | int | None = None,
    unknown: str = "warn",
    force: bool = False,
    name: str | None = None,
    authors: list[str] | None = None,
    default_session: str = "ses-1",
) -> BiometricsConvertResult:
    """Convert biometrics CSV/XLSX (wide format) into a PRISM/BIDS-style dataset.

    Writes:
    - dataset_description.json
    - participants.tsv
    - task-<task>_biometrics.json (inherited sidecar, copied from library template)
    - sub-*/ses-*/biometrics/sub-*_ses-*_task-<task>_biometrics.tsv

    unknown:
      - 'ignore': ignore unmapped columns
      - 'warn': collect unmapped columns in result
      - 'error': raise on any unmapped columns
    """

    input_path = Path(input_path).resolve()
    library_dir = Path(library_dir).resolve()
    output_root = Path(output_root).resolve()

    if input_path.suffix.lower() not in {".csv", ".xlsx"}:
        raise ValueError("Biometrics input must be a .csv or .xlsx file")

    if not library_dir.exists() or not library_dir.is_dir():
        raise ValueError(f"Biometrics library path is not a directory: {library_dir}")

    if output_root.exists() and any(output_root.iterdir()):
        if not force:
            raise ValueError(f"Output directory is not empty: {output_root}")

    df = _read_table_as_dataframe(input_path=input_path, sheet=sheet)

    task_to_items, task_to_template = _load_biometrics_library(library_dir)
    if not task_to_items:
        raise ValueError(f"No biometrics-*.json templates found in: {library_dir}")

    # Detect columns
    col_pid = id_column or _find_col(df, {"participant_id", "participant", "subject", "sub"})
    if not col_pid:
        raise ValueError(
            "Missing participant id column. Provide --id-column or include 'participant_id'."
        )

    col_ses = session_column or _find_col(df, {"session", "ses", "visit", "timepoint"})

    # Build mapping of known item columns
    all_item_cols: set[str] = set()
    for items in task_to_items.values():
        all_item_cols.update(items)

    unknown_cols: list[str] = []
    for c in list(df.columns):
        c_str = str(c)
        if c_str == col_pid or (col_ses and c_str == col_ses):
            continue
        if c_str in all_item_cols:
            continue
        unknown_cols.append(c_str)

    if unknown_cols and unknown == "error":
        raise ValueError(
            "Unmapped columns (not found in any biometrics template): " + ", ".join(unknown_cols)
        )

    # Root files
    output_root.mkdir(parents=True, exist_ok=True)
    dataset_description = {
        "Name": name or "PRISM Biometrics Dataset",
        "BIDSVersion": "1.8.0",
        "DatasetType": "raw",
        "Authors": authors or ["prism-validator-web"],
    }
    _write_json(output_root / "dataset_description.json", dataset_description)

    # participants.tsv
    try:
        import pandas as pd
    except Exception as e:  # pragma: no cover
        raise RuntimeError("pandas is required for biometrics conversion") from e

    participants = (
        df[col_pid]
        .astype(str)
        .map(_normalize_sub_id)
        .loc[lambda s: s.astype(str).str.len() > 0]
        .drop_duplicates()
        .sort_values()
    )
    pd.DataFrame({"participant_id": participants}).to_csv(
        output_root / "participants.tsv", sep="\t", index=False
    )

    tasks_included: list[str] = []

    # Write inherited sidecars (dataset-level)
    for task, template in task_to_template.items():
        sidecar_path = output_root / f"task-{task}_biometrics.json"
        _write_json(sidecar_path, template)

    # Write per-row TSVs
    for _, row in df.iterrows():
        pid_raw = row.get(col_pid)
        sub_id = _normalize_sub_id(pid_raw)
        if not sub_id:
            continue

        ses_id = _normalize_ses_id(row.get(col_ses) if col_ses else None, default_session=default_session)

        for task, items in task_to_items.items():
            values: dict[str, Any] = {}
            any_present = False
            for item in items:
                if item in df.columns:
                    v = row.get(item)
                    if v is None or pd.isna(v):
                        values[item] = "n/a"
                    else:
                        values[item] = v
                        if str(v).strip():
                            any_present = True
                else:
                    values[item] = "n/a"

            # If this task has no columns in the input at all, skip writing.
            if not any_present and not any(item in df.columns for item in items):
                continue

            modality_dir = output_root / sub_id / ses_id / "biometrics"
            modality_dir.mkdir(parents=True, exist_ok=True)
            stem = f"{sub_id}_{ses_id}_task-{task}_biometrics"
            out_tsv = modality_dir / f"{stem}.tsv"
            pd.DataFrame([values], columns=items).to_csv(out_tsv, sep="\t", index=False)

            if task not in tasks_included:
                tasks_included.append(task)

    return BiometricsConvertResult(
        id_column=col_pid,
        session_column=col_ses,
        tasks_included=sorted(tasks_included),
        unknown_columns=(unknown_cols if unknown == "warn" else []),
    )
