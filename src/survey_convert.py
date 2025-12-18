"""Survey conversion utilities.

This module provides a programmatic API for converting wide survey tables (e.g. .xlsx)
into a PRISM/BIDS-style survey dataset.

It is extracted from the CLI implementation in `prism_tools.py` so the Web UI and
GUI can call the same logic without invoking subprocesses or relying on `sys.exit`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import json


@dataclass(frozen=True)
class SurveyConvertResult:
    tasks_included: list[str]
    unknown_columns: list[str]
    missing_items_by_task: dict[str, int]
    id_column: str
    session_column: str | None


def sanitize_id(id_str: str) -> str:
    """Sanitize IDs by replacing German umlauts and special characters."""
    if not id_str:
        return id_str
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
    for char, repl in replacements.items():
        id_str = id_str.replace(char, repl)
    return id_str


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, obj: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _load_participants_template(library_dir: Path) -> dict | None:
    """Load a participant template from the survey library, if present.

    The repo currently ships `survey-participant.json` (singular). Some users may
    refer to `survey-participants.json` (plural), so we accept both.
    """

    for name in ("survey-participants.json", "survey-participant.json"):
        p = library_dir / name
        if p.exists() and p.is_file():
            try:
                return _read_json(p)
            except Exception:
                return None
    return None


def _is_participant_template(path: Path) -> bool:
    stem = path.stem.lower()
    return stem in {"survey-participant", "survey-participants"}


def _participants_json_from_template(*, columns: list[str], template: dict | None) -> dict:
    """Create a BIDS-style participants.json for the given TSV columns."""

    out: dict[str, dict] = {}

    def _template_meta(col: str) -> dict:
        if not template:
            return {}
        if col not in template:
            return {}
        v = template.get(col)
        if not isinstance(v, dict):
            return {}
        meta: dict[str, object] = {}
        desc = v.get("Description")
        if desc:
            meta["Description"] = desc
        levels = v.get("Levels")
        if isinstance(levels, dict) and levels:
            meta["Levels"] = levels
        unit = v.get("Units") or v.get("Unit")
        if unit:
            meta["Units"] = unit
        return meta

    for col in columns:
        if col == "participant_id":
            out[col] = {
                "Description": "Participant identifier (BIDS subject label)",
            }
            continue

        meta = _template_meta(col)
        if not meta:
            # Minimal, valid fallback.
            meta = {"Description": col}
            if col == "age":
                meta["Description"] = "Age"
                meta["Units"] = "years"

        out[col] = dict(meta)

    return out


def convert_survey_xlsx_to_prism_dataset(
    *,
    input_path: str | Path,
    library_dir: str | Path,
    output_root: str | Path,
    survey: str | None = None,
    id_column: str | None = None,
    session_column: str | None = None,
    sheet: str | int = 0,
    unknown: str = "warn",
    dry_run: bool = False,
    force: bool = False,
    name: str | None = None,
    authors: list[str] | None = None,
) -> SurveyConvertResult:
    """Convert a wide survey Excel table into a PRISM dataset.

    Parameters mirror `prism_tools.py survey convert`.

    Raises:
        ValueError: for user errors (missing files, invalid columns, etc.)
        RuntimeError: for unexpected conversion failures
    """

    if unknown not in {"error", "warn", "ignore"}:
        raise ValueError("unknown must be one of: error, warn, ignore")

    input_path = Path(input_path).resolve()
    library_dir = Path(library_dir).resolve()
    output_root = Path(output_root).resolve()

    if not input_path.exists():
        raise ValueError(f"Input file does not exist: {input_path}")

    if not library_dir.exists() or not library_dir.is_dir():
        raise ValueError(f"Library folder does not exist or is not a directory: {library_dir}")

    if output_root.exists() and any(output_root.iterdir()) and not force:
        raise ValueError(
            f"Output directory is not empty: {output_root}. Use force=True to write into a non-empty directory."
        )

    if input_path.suffix.lower() not in {".xlsx"}:
        raise ValueError("Currently only .xlsx input is supported.")

    try:
        import pandas as pd
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "pandas is required for Excel conversion. Ensure dependencies are installed via setup.sh"
        ) from e

    # --- Load survey templates ---
    templates: dict[str, dict] = {}
    item_to_task: dict[str, str] = {}
    duplicate_items: dict[str, set[str]] = {}

    for json_path in sorted(library_dir.glob("survey-*.json")):
        # Participant metadata template is not a survey task template.
        if _is_participant_template(json_path):
            continue
        try:
            sidecar = _read_json(json_path)
        except Exception:
            # Skip invalid JSON (best-effort; CLI prints a warning)
            continue

        task_from_name = json_path.stem.replace("survey-", "")
        task = str(sidecar.get("Study", {}).get("TaskName") or task_from_name).strip()
        if not task:
            task = task_from_name
        task_norm = task.lower()
        templates[task_norm] = {"path": json_path, "json": sidecar, "task": task_norm}

        for k in sidecar.keys():
            if k in {"Technical", "Study", "Metadata"}:
                continue
            if k in item_to_task and item_to_task[k] != task_norm:
                duplicate_items.setdefault(k, set()).update({item_to_task[k], task_norm})
            else:
                item_to_task[k] = task_norm

    if not templates:
        raise ValueError(f"No survey templates found in: {library_dir} (expected survey-*.json)")

    if duplicate_items:
        msg_lines = ["Duplicate item IDs found across survey templates (ambiguous mapping):"]
        for item_id, tasks in sorted(duplicate_items.items()):
            msg_lines.append(f"- {item_id}: {', '.join(sorted(tasks))}")
        raise ValueError("\n".join(msg_lines))

    # --- Parse --survey filter ---
    selected_tasks: set[str] | None = None
    if survey:
        parts = [p.strip() for p in str(survey).replace(";", ",").split(",")]
        parts = [p for p in parts if p]
        selected = {p.lower().replace("survey-", "") for p in parts}

        unknown_surveys = sorted([t for t in selected if t not in templates])
        if unknown_surveys:
            raise ValueError(
                "Unknown surveys: " + ", ".join(unknown_surveys) + ". Available: " + ", ".join(sorted(templates.keys()))
            )
        selected_tasks = selected

    # --- Read input table ---
    sheet_arg: str | int = sheet
    if isinstance(sheet_arg, str) and sheet_arg.isdigit():
        sheet_arg = int(sheet_arg)

    try:
        df = pd.read_excel(input_path, sheet_name=sheet_arg)
    except Exception as e:
        raise ValueError(f"Failed to read Excel: {e}") from e

    if df is None or df.empty:
        raise ValueError("Input table is empty.")

    # Normalize headers (conservative)
    df = df.rename(columns={c: str(c).strip() for c in df.columns})

    def _find_col(candidates: set[str]) -> str | None:
        lower_map = {str(c).strip().lower(): str(c).strip() for c in df.columns}
        for c in candidates:
            if c in lower_map:
                return lower_map[c]
        return None

    resolved_id_col = id_column
    if resolved_id_col:
        if resolved_id_col not in df.columns:
            raise ValueError(
                f"id_column '{resolved_id_col}' not found. Columns: {', '.join([str(c) for c in df.columns])}"
            )
    else:
        resolved_id_col = _find_col({"participant_id", "subject", "id", "sub_id", "participant", "code"})
        if not resolved_id_col:
            raise ValueError(
                "Could not determine participant id column. Provide id_column explicitly (e.g., participant_id, CODE)."
            )

    resolved_session_col: str | None
    if session_column:
        if session_column not in df.columns:
            raise ValueError(f"session_column '{session_column}' not found in input columns")
        resolved_session_col = session_column
    else:
        resolved_session_col = _find_col({"session", "ses", "visit", "timepoint"})

    def _normalize_sub_id(val) -> str:
        s = sanitize_id(str(val).strip())
        if not s:
            return s
        if s.startswith("sub-"):
            return s
        if s.isdigit() and len(s) < 3:
            s = s.zfill(3)
        return f"sub-{s}"

    def _normalize_ses_id(val) -> str:
        s = sanitize_id(str(val).strip())
        if not s:
            return "ses-1"
        if s.startswith("ses-"):
            return s
        return f"ses-{s}"

    # --- Determine which columns map to which surveys ---
    cols = [c for c in df.columns if c not in {resolved_id_col} and c != resolved_session_col]
    col_to_task: dict[str, str] = {}
    unknown_cols: list[str] = []
    for c in cols:
        if c in item_to_task:
            col_to_task[c] = item_to_task[c]
        else:
            unknown_cols.append(c)

    tasks_with_data = set(col_to_task.values())
    if selected_tasks is not None:
        tasks_with_data = tasks_with_data.intersection(selected_tasks)

    if not tasks_with_data:
        raise ValueError("No survey item columns matched the selected templates.")

    # Missing-items report
    missing_items_by_task: dict[str, int] = {}
    for task in sorted(tasks_with_data):
        schema = templates[task]["json"]
        expected = [k for k in schema.keys() if k not in {"Technical", "Study", "Metadata"}]
        present = [c for c, t in col_to_task.items() if t == task]
        missing = [k for k in expected if k not in present]
        missing_items_by_task[task] = len(missing)

    if unknown_cols and unknown == "error":
        raise ValueError("Unmapped columns: " + ", ".join(unknown_cols))

    if dry_run:
        return SurveyConvertResult(
            tasks_included=sorted(tasks_with_data),
            unknown_columns=unknown_cols,
            missing_items_by_task=missing_items_by_task,
            id_column=resolved_id_col,
            session_column=resolved_session_col,
        )

    # --- Write output dataset ---
    _ensure_dir(output_root)

    ds_desc = output_root / "dataset_description.json"
    if not ds_desc.exists():
        dataset_description = {
            "Name": name or "PRISM Survey Dataset",
            "BIDSVersion": "1.8.0",
            "DatasetType": "raw",
            "Authors": authors or ["prism-validator"],
        }
        _write_json(ds_desc, dataset_description)

    # participants.tsv
    df_part = pd.DataFrame({"participant_id": df[resolved_id_col].astype(str).map(_normalize_sub_id)})
    lower_to_col = {str(c).strip().lower(): str(c).strip() for c in df.columns}
    extra_part_cols: list[str] = []
    for candidate in ["age", "sex", "gender"]:
        col = lower_to_col.get(candidate)
        if col and col not in {resolved_id_col, resolved_session_col}:
            extra_part_cols.append(col)

    if extra_part_cols:
        df_extra = df[[resolved_id_col] + extra_part_cols].copy()
        for c in extra_part_cols:
            df_extra[c] = df_extra[c].apply(lambda v: "n/a" if pd.isna(v) else v)
        df_extra[resolved_id_col] = df_extra[resolved_id_col].astype(str).map(_normalize_sub_id)
        df_extra = df_extra.groupby(resolved_id_col, dropna=False)[extra_part_cols].first().reset_index()
        df_extra = df_extra.rename(columns={resolved_id_col: "participant_id"})
        df_part = df_part.merge(df_extra, on="participant_id", how="left")

    df_part = df_part.drop_duplicates(subset=["participant_id"]).reset_index(drop=True)
    df_part.to_csv(output_root / "participants.tsv", sep="\t", index=False)

    # participants.json (column metadata)
    participants_json_path = output_root / "participants.json"
    participant_template = _load_participants_template(library_dir)
    participants_json = _participants_json_from_template(
        columns=[str(c) for c in df_part.columns],
        template=participant_template,
    )
    _write_json(participants_json_path, participants_json)

    # inherited sidecars at dataset root (inheritance principle)
    for task in sorted(tasks_with_data):
        sidecar_path = output_root / f"survey-{task}_beh.json"
        if not sidecar_path.exists() or force:
            _write_json(sidecar_path, templates[task]["json"])

    def _normalize_item_value(val) -> str:
        if pd.isna(val):
            return "n/a"
        if isinstance(val, bool):
            return str(val)
        if isinstance(val, int):
            return str(int(val))
        if isinstance(val, float):
            if val.is_integer():
                return str(int(val))
            return str(val)
        return str(val)

    # per-subject TSVs
    for _, row in df.iterrows():
        sub_id = _normalize_sub_id(row[resolved_id_col])
        ses_id = _normalize_ses_id(row[resolved_session_col]) if resolved_session_col else "ses-1"

        modality_dir = _ensure_dir(output_root / sub_id / ses_id / "survey")

        for task in sorted(tasks_with_data):
            if selected_tasks is not None and task not in selected_tasks:
                continue

            schema = templates[task]["json"]
            expected = [k for k in schema.keys() if k not in {"Technical", "Study", "Metadata"}]
            present_cols = [c for c, t in col_to_task.items() if t == task]
            if not present_cols:
                continue

            out: dict[str, str] = {}
            for item_id in expected:
                if item_id in df.columns:
                    out[item_id] = _normalize_item_value(row[item_id])
                else:
                    out[item_id] = "n/a"

            # stable column order
            with open(modality_dir / f"{sub_id}_{ses_id}_task-{task}_beh.tsv", "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=expected, delimiter="\t", lineterminator="\n")
                writer.writeheader()
                writer.writerow(out)

    return SurveyConvertResult(
        tasks_included=sorted(tasks_with_data),
        unknown_columns=unknown_cols,
        missing_items_by_task=missing_items_by_task,
        id_column=resolved_id_col,
        session_column=resolved_session_col,
    )
