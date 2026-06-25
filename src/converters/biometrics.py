"""Biometrics data conversion helpers.

This module converts a tabular biometrics export (CSV/XLSX) into a minimal
PRISM/BIDS-style dataset structure that remains compatible with BIDS tools.

Assumptions (kept intentionally simple):
- Input data is "wide": one row per participant (optionally with a session column)
  and one column per biometrics variable.
- Biometrics templates exist in a library folder as `biometrics-<task>.json`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import re
import unicodedata


from src.cross_platform import describe_case_insensitive_id_collisions
from src.converters.file_reader import (
    infer_tabular_kind as _infer_tabular_kind,
    read_tabular_file as _read_tabular_file,
)
from src.subject_id_matching import build_subject_id_matcher
from src.utils.io import read_json as _read_json, write_json as _write_json
from src.utils.naming import norm_key as _norm_key

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
    detected_sessions: list[str] = field(default_factory=list)


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
    if pid.lower() == "nan":
        return ""
    # Normalize to NFC before stripping non-ASCII chars so a name like
    # "José" sanitizes the same way regardless of which Unicode
    # normalization form the source system used (see
    # ParticipantsConverter._normalize_participant_id for the full
    # rationale).
    pid = unicodedata.normalize("NFC", pid)
    label = pid[4:] if pid[:4].lower() == "sub-" else pid
    label = re.sub(r"[^A-Za-z0-9]+", "", label)
    if not label:
        return ""
    return f"sub-{label}"


def _normalize_ses_id(value: Any, *, default_session: str = "ses-1") -> str:
    ses = str(value).strip() if value is not None else ""
    if not ses or ses.lower() == "nan":
        return default_session
    label = ses[4:] if ses[:4].lower() == "ses-" else ses
    label = re.sub(r"[^A-Za-z0-9]+", "", label)
    if not label:
        return default_session
    return f"ses-{label}"


def _read_table_as_dataframe(
    *, input_path: Path, sheet: str | int | None = None
) -> "Any":
    kind = _infer_tabular_kind(input_path)
    if kind not in {"csv", "tsv", "xlsx", "sav", "rds", "rdata"}:
        raise ValueError(
            "Supported formats: .csv, .xlsx, .tsv, .sav, .rds, .rdata, .rda"
        )
    resolved_sheet: str | int = sheet if sheet is not None else 0
    result = _read_tabular_file(input_path, kind=kind, sheet=resolved_sheet)
    for w in result.warnings:
        import logging

        logging.getLogger(__name__).warning(w)
    return result.df


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


def extract_raw_identities(
    *,
    input_path: str | Path,
    id_column: str | None = None,
    session_column: str | None = None,
    sheet: str | int | None = None,
) -> tuple[list[str], list[str], str, str | None]:
    """Read a biometrics table just far enough to return the distinct raw
    participant ids and raw session labels it contains, without performing a
    full conversion. Used to validate ids/sessions against a project's
    ground truth (participants.tsv, existing session directories) before
    committing to a conversion.

    Returns (raw_ids, raw_sessions, id_column_used, session_column_used).
    """
    input_path = Path(input_path).resolve()
    df = _read_table_as_dataframe(input_path=input_path, sheet=sheet)

    col_pid = id_column or _find_col(
        df, {"participant_id", "participant", "subject", "sub"}
    )
    if not col_pid:
        raise ValueError(
            "Missing participant id column. Provide --id-column or include 'participant_id'."
        )
    col_ses = session_column or _find_col(df, {"session", "ses", "visit", "timepoint"})

    raw_ids = sorted({rid for rid in df[col_pid].astype(str).map(_normalize_sub_id) if rid})
    raw_sessions = (
        sorted({sid for sid in df[col_ses].astype(str).map(_normalize_ses_id) if sid})
        if col_ses
        else []
    )
    return raw_ids, raw_sessions, col_pid, col_ses


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
    existing_participant_ids: set[str] | None = None,
    id_overrides: dict[str, str] | None = None,
) -> BiometricsConvertResult:
    """Convert biometrics CSV/XLSX (wide format) into a PRISM/BIDS-style dataset.

    Writes:
    - dataset_description.json
    - participants.tsv (optional, can be skipped with skip_participants=True)
    - task-<task>_biometrics.json (inherited sidecar, copied from library template)
    - sub-*/ses-*/biometrics/sub-*_ses-*_task-<task>_biometrics.tsv

    Args:
        skip_participants: If True, skip creating participants.tsv (default: False)
        existing_participant_ids: Canonical participant_id values already
            present in the target project's own participants.tsv (the
            ground truth). When a raw incoming id numerically matches
            exactly one of these after stripping leading zeros, the
            existing canonical id is used instead of building a new,
            differently-formatted subject folder for the same person.
            Unmatched ids fall back to the normal (uncoerced) id-building
            behavior -- this never invents padding for a participant that
            isn't already known to the project.

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
    col_pid = id_column or _find_col(
        df, {"participant_id", "participant", "subject", "sub"}
    )
    if not col_pid:
        raise ValueError(
            "Missing participant id column. Provide --id-column or include 'participant_id'."
        )

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

    subject_id_match = build_subject_id_matcher(existing_participant_ids or set())

    def _resolve_sub_id(raw_value) -> str:
        normalized = _normalize_sub_id(raw_value)
        if not normalized:
            return normalized
        return subject_id_match(normalized) or normalized

    # Two participant ids differing only by case (e.g. 'sub-Ab'/'sub-ab')
    # would resolve to the identical on-disk directory on a case-insensitive
    # filesystem (default macOS/Windows): the second one written silently
    # overwrites the first's biometrics files with no error. Fail fast,
    # before any output is written, rather than allow that.
    normalized_ids = df[col_pid].astype(str).map(_resolve_sub_id)
    collision_message = describe_case_insensitive_id_collisions(
        [sid for sid in normalized_ids if sid]
    )
    if collision_message:
        raise ValueError(collision_message)

    # Root files
    output_root.mkdir(parents=True, exist_ok=True)
    dataset_description = {
        "Name": name or "PRISM Biometrics Dataset",
        "BIDSVersion": "1.8.0",
        "DatasetType": "raw",
        "Authors": authors or ["prism-studio"],
        "Keywords": ["psychology", "biometrics", "PRISM"],
        "GeneratedBy": [
            {
                "Name": "PRISM Biometrics Converter",
            }
        ],
    }
    _write_json(output_root / "dataset_description.json", dataset_description)

    try:
        import pandas as pd
    except Exception as e:  # pragma: no cover
        raise RuntimeError("pandas is required for biometrics conversion") from e

    # participants.tsv (optional)
    if not skip_participants:
        participants = (
            df[col_pid]
            .astype(str)
            .map(_resolve_sub_id)
            .loc[lambda s: s.astype(str).str.len() > 0]
            .drop_duplicates()
            .sort_values()
        )
        pd.DataFrame({"participant_id": participants}).to_csv(
            output_root / "participants.tsv", sep="\t", index=False
        )

    tasks_included: list[str] = []
    sessions_written: list[str] = []

    # "all" is a sentinel meaning "auto-detect per row" (same convention as the
    # survey converter), not a literal session label.
    effective_session = (
        None if session and str(session).strip().lower() == "all" else session
    )

    # Write inherited sidecars (dataset-level)
    for task, template in task_to_template.items():
        sidecar_path = output_root / f"task-{task}_biometrics.json"
        _write_json(sidecar_path, template)

    # Write per-row TSVs
    for _, row in df.iterrows():
        pid_raw = row.get(col_pid)
        sub_id = _resolve_sub_id(pid_raw)
        if not sub_id:
            continue

        if effective_session:
            ses_id = _normalize_ses_id(effective_session)
        else:
            ses_id = _normalize_ses_id(
                row.get(col_ses) if col_ses else None, default_session=default_session
            )
        if ses_id not in sessions_written:
            sessions_written.append(ses_id)

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
        detected_sessions=sorted(sessions_written),
    )
