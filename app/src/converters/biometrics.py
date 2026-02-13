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


from ..utils.io import read_json as _read_json, write_json as _write_json
from ..utils.naming import norm_key as _norm_key

_NON_ITEM_TOPLEVEL_KEYS: set[str] = {
    "Technical",
    "Study",
    "Metadata",
    "I18n",
    "LimeSurvey",
    "Scoring",
    "Normative",
}


@dataclass
class BiometricsConvertResult:
    id_column: str
    session_column: str | None
    tasks_included: list[str]
    unknown_columns: list[str]


def _norm_col(s: str) -> str:
    return _norm_key(s)


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


def _normalize_ses_id(value: Any, *, default_session: str = "ses-01") -> str:
    import re

    ses = str(value).strip() if value is not None else ""
    if not ses or ses.lower() == "nan":
        return default_session

    # Strip ses- prefix if present, then re-normalize
    num_part = ses[4:] if ses.startswith("ses-") else ses

    # Check for numeric values (including t1/visit1 patterns)
    m = re.match(r"^(?:t|visit)?\s*(\d+)\s*$", num_part, flags=re.IGNORECASE)
    if m:
        return f"ses-{int(m.group(1)):02d}"

    # Non-numeric labels pass through (e.g., "baseline")
    return f"ses-{num_part}"


def _debug_print_file_head(input_path: Path, num_lines: int = 4):
    """Print the first few lines of a text file for debugging/visibility in terminal."""
    try:
        # Avoid binary files
        if input_path.suffix.lower() in {".xlsx", ".xls", ".lsa", ".zip", ".gz"}:
            return

        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            print(f"\n[DEBUG] --- First {num_lines} lines of {input_path.name} ---")
            for i in range(num_lines):
                line = f.readline()
                if not line:
                    break
                print(f"L{i + 1}: {line.rstrip()}")
            header_len = 26 + len(input_path.name)
            print("-" * header_len + "\n")
    except Exception:
        # Silently fail if we can't read/print
        pass


def _read_table_as_dataframe(
    *, input_path: Path, sheet: str | int | None = None
) -> "Any":
    # Print head for visibility in terminal
    _debug_print_file_head(input_path)

    try:
        import pandas as pd
    except Exception as e:  # pragma: no cover
        raise RuntimeError("pandas is required for biometrics conversion") from e

    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(input_path)
    if suffix == ".tsv":
        return pd.read_csv(input_path, sep="\t")
    if suffix == ".xlsx":
        sheet_name: str | int | None = sheet
        if sheet_name is None:
            sheet_name = 0
        if isinstance(sheet_name, str) and sheet_name.isdigit():
            sheet_name = int(sheet_name)
        return pd.read_excel(input_path, sheet_name=sheet_name)

    raise ValueError("Supported formats: .csv, .xlsx, .tsv")


def _load_biometrics_library(
    library_dir: Path,
) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]]]:
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


def detect_biometrics_in_table(
    *,
    input_path: str | Path,
    library_dir: str | Path,
    sheet: str | int | None = None,
) -> list[str]:
    """Detect which biometrics tasks are present in the input table."""
    input_path = Path(input_path).resolve()
    library_dir = Path(library_dir).resolve()

    df = _read_table_as_dataframe(input_path=input_path, sheet=sheet)
    task_to_items, _ = _load_biometrics_library(library_dir)

    df_cols_norm = {_norm_col(c) for c in df.columns}

    detected_tasks: list[str] = []
    for task, items in task_to_items.items():
        # A task is detected if at least one of its items is present in the table (case-insensitive)
        if any(_norm_col(item) in df_cols_norm for item in items):
            detected_tasks.append(task)

    return sorted(detected_tasks)


def convert_biometrics_table_to_prism_dataset(
    *,
    input_path: str | Path,
    library_dir: str | Path,
    output_root: str | Path,
    id_column: str | None = None,
    session_column: str | None = None,
    session: str | None = None,
    sheet: str | int | None = None,
    unknown: str = "warn",
    force: bool = False,
    name: str | None = None,
    authors: list[str] | None = None,
    default_session: str = "ses-1",
    tasks_to_export: list[str] | None = None,
    skip_participants: bool = False,
) -> BiometricsConvertResult:
    """Convert biometrics CSV/XLSX (wide format) into a PRISM/BIDS-style dataset.

    Writes:
    - dataset_description.json
    - participants.tsv (optional, can be skipped with skip_participants=True)
    - task-<task>_biometrics.json (inherited sidecar, copied from library template)
    - sub-*/ses-*/biometrics/sub-*_ses-*_task-<task>_biometrics.tsv

    Args:
        skip_participants: If True, skip creating participants.tsv (default: False)

    unknown:
      - 'ignore': ignore unmapped columns
      - 'warn': collect unmapped columns in result
      - 'error': raise on any unmapped columns
    """

    input_path = Path(input_path).resolve()
    library_dir = Path(library_dir).resolve()
    output_root = Path(output_root).resolve()

    if input_path.suffix.lower() not in {".csv", ".xlsx", ".tsv"}:
        raise ValueError("Biometrics input must be a .csv, .xlsx, or .tsv file")

    if not library_dir.exists() or not library_dir.is_dir():
        raise ValueError(f"Biometrics library path is not a directory: {library_dir}")

    if output_root.exists() and any(output_root.iterdir()):
        if not force:
            raise ValueError(f"Output directory is not empty: {output_root}")

    df = _read_table_as_dataframe(input_path=input_path, sheet=sheet)

    task_to_items, task_to_template = _load_biometrics_library(library_dir)
    if not task_to_items:
        raise ValueError(f"No biometrics-*.json templates found in: {library_dir}")

    # Filter tasks if requested
    if tasks_to_export is not None:
        task_to_items = {t: i for t, i in task_to_items.items() if t in tasks_to_export}
        task_to_template = {
            t: temp for t, temp in task_to_template.items() if t in tasks_to_export
        }

    # Detect columns
    from .id_detection import detect_id_column, IdColumnNotDetectedError

    col_pid = detect_id_column(
        list(df.columns), "biometrics", explicit_id_column=id_column
    )
    if not col_pid:
        raise IdColumnNotDetectedError(list(df.columns), "biometrics")

    col_ses = session_column or _find_col(df, {"session", "ses", "visit", "timepoint"})

    # Build mapping of known item columns (case-insensitive)
    all_item_cols_norm: dict[str, str] = {}
    for items in task_to_items.values():
        for item in items:
            all_item_cols_norm[_norm_col(item)] = item

    unknown_cols: list[str] = []
    for c in list(df.columns):
        c_str = str(c)
        c_norm = _norm_col(c_str)

        if c_str == col_pid or (col_ses and c_str == col_ses):
            continue
        if _norm_col(col_pid) == c_norm or (col_ses and _norm_col(col_ses) == c_norm):
            continue

        if c_norm in all_item_cols_norm:
            continue

        # Also ignore reserved keys
        if any(_norm_col(k) == c_norm for k in _NON_ITEM_TOPLEVEL_KEYS):
            continue
        unknown_cols.append(c_str)

    if unknown_cols and unknown == "error":
        raise ValueError(
            "Unmapped columns (not found in any biometrics template): "
            + ", ".join(unknown_cols)
        )

    # Root files
    output_root.mkdir(parents=True, exist_ok=True)
    dataset_description = {
        "Name": name or "PRISM Biometrics Dataset",
        "BIDSVersion": "1.10.1",
        "DatasetType": "raw",
        "Authors": authors or ["PRISM Biometrics Converter"],
        "GeneratedBy": [
            {
                "Name": "PRISM Biometrics Converter",
                "Version": "1.1.1",
                "Description": "Automated biometrics data conversion to PRISM format.",
            }
        ],
        "HEDVersion": "8.2.0",
    }
    _write_json(output_root / "dataset_description.json", dataset_description)

    # participants.tsv (optional)
    if not skip_participants:
        try:
            import pandas as pd
        except Exception as e:  # pragma: no cover
            raise RuntimeError("pandas is required for biometrics conversion") from e

        # Extract unique participant IDs from the input data
        participant_ids = (
            df[col_pid]
            .astype(str)
            .map(_normalize_sub_id)
            .loc[lambda s: s.astype(str).str.len() > 0]
            .drop_duplicates()
            .tolist()
        )

        # Use the update utility to add/preserve participants
        try:
            from ..utils.io import update_participants_tsv

            update_participants_tsv(
                output_root,
                participant_ids,
                log_fn=None,  # Could pass a logger here if available
            )
        except Exception:
            # Fallback to old behavior if update fails
            pd.DataFrame({"participant_id": sorted(participant_ids)}).to_csv(
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

        if session:
            ses_id = _normalize_ses_id(session)
        else:
            ses_id = _normalize_ses_id(
                row.get(col_ses) if col_ses else None, default_session=default_session
            )

        # Map dataframe columns to normalized names for easier lookup
        df_col_map = {_norm_col(c): c for c in df.columns}

        for task, items in task_to_items.items():
            values: dict[str, Any] = {}
            any_present = False
            for item in items:
                item_norm = _norm_col(item)
                if item_norm in df_col_map:
                    real_col = df_col_map[item_norm]
                    v = row.get(real_col)
                    if v is None or pd.isna(v):
                        values[item] = "n/a"
                    else:
                        values[item] = v
                        if str(v).strip() and str(v).lower() != "nan":
                            any_present = True
                else:
                    values[item] = "n/a"

            # If this task has no columns in the input at all, skip writing.
            if not any_present and not any(
                _norm_col(item) in df_col_map for item in items
            ):
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
