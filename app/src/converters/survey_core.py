"""Core utilities and logic components for survey conversion.

This module consolidates shared logic for:
1. Basic constants and helpers (structure extraction, BIDS filenames).
2. Schema/Library loading (`load_survey_library`).
3. Task selection and filtering (`_resolve_selected_tasks`).
4. Session detection and duplicate handling.
5. Alias mapping and canonicalization.
6. Technical metadata overrides.
7. Mapping result reporting.
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    import pandas as pd
except ImportError:
    pd = None


# =============================================================================
# CONSTANTS & STRUCTURE HELPERS (from survey_helpers.py)
# =============================================================================

_NON_ITEM_TOPLEVEL_KEYS = {
    "Technical",
    "Study",
    "Metadata",
    "Normative",
    "Scoring",
    # Template metadata (not survey response columns)
    "I18n",
    "LimeSurvey",
    "_aliases",
    "_reverse_aliases",
    "_prismmeta",
}


# Keys that are considered "styling" or metadata, not structural
_STYLING_KEYS = {
    "Description",
    "Levels",
    "MinValue",
    "MaxValue",
    "Units",
    "HelpText",
    "Aliases",
    "AliasOf",
    "Derivative",
    "TermURL",
}


def _extract_template_structure(template: dict) -> set[str]:
    """Extract the structural signature of a template (item keys only)."""
    return {
        k
        for k in template.keys()
        if k not in _NON_ITEM_TOPLEVEL_KEYS and isinstance(template.get(k), dict)
    }


def _compare_template_structures(
    template_a: dict, template_b: dict
) -> tuple[bool, set[str], set[str]]:
    """Compare two templates structurally."""
    struct_a = _extract_template_structure(template_a)
    struct_b = _extract_template_structure(template_b)

    only_in_a = struct_a - struct_b
    only_in_b = struct_b - struct_a

    return (len(only_in_a) == 0 and len(only_in_b) == 0), only_in_a, only_in_b


def _build_bids_survey_filename(
    sub_id: str, ses_id: str, task: str, run: int | None = None, extension: str = "tsv"
) -> str:
    """Build a BIDS-compliant survey filename."""
    parts = [sub_id, ses_id, f"task-{task}"]
    if run is not None:
        parts.append(f"run-{run:02d}")
    parts.append("survey")  # Add suffix without extension
    return "_".join(parts) + f".{extension}"


def _determine_task_runs(
    tasks_with_data: set[str], task_occurrences: dict[str, int]
) -> dict[str, int | None]:
    """Determine which tasks need run numbers based on occurrence count."""
    task_runs: dict[str, int | None] = {}
    for task in tasks_with_data:
        count = task_occurrences.get(task, 1)
        if count > 1:
            task_runs[task] = count
        else:
            task_runs[task] = None
    return task_runs


# =============================================================================
# BASE UTILITIES (from survey_base.py)
# =============================================================================


def load_survey_library(library_path: str) -> Dict[str, Dict[str, Any]]:
    """Load all survey JSONs from the library."""
    schemas = {}
    if not os.path.exists(library_path):
        return schemas

    for f in os.listdir(library_path):
        if f.endswith(".json") and f.startswith("survey-"):
            # Extract task name: survey-ads.json -> ads
            task_name = f.replace("survey-", "").replace(".json", "")
            filepath = os.path.join(library_path, f)
            try:
                with open(filepath, "r", encoding="utf-8") as jf:
                    schemas[task_name] = json.load(jf)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
    return schemas


def get_allowed_values(col_def: Any) -> Optional[List[str]]:
    """Return allowed values for a column, expanding numeric level endpoints to full range."""
    if not isinstance(col_def, dict):
        return None

    if "AllowedValues" in col_def:
        return [str(x) for x in col_def["AllowedValues"]]

    if "Levels" in col_def:
        level_keys = list(col_def["Levels"].keys())
        try:
            numeric_levels = [int(float(k)) for k in level_keys]
        except (ValueError, TypeError):
            numeric_levels = []

        if numeric_levels:
            min_level = min(numeric_levels)
            max_level = max(numeric_levels)
            # Only expand if it looks like a continuous range
            if max_level - min_level < 100:
                full_range = [str(i) for i in range(min_level, max_level + 1)]
                return full_range
            # Otherwise return explicit levels
            return level_keys
            
    return None


# =============================================================================
# ALIAS HANDLING (from survey_aliases.py)
# =============================================================================


def _read_alias_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            parts = [
                p.strip() for p in (line.split("\t") if "\t" in line else line.split())
            ]
            parts = [p for p in parts if p]
            if len(parts) < 2:
                continue
            rows.append(parts)
    if rows:
        first = [p.lower() for p in rows[0]]
        if first[0] in {"canonical", "canonical_id", "canonicalid", "id"}:
            rows = rows[1:]
    return rows


def _build_alias_map(rows: Iterable[list[str]]) -> dict[str, str]:
    """Return mapping alias -> canonical (canonical maps to itself)."""
    out: dict[str, str] = {}
    for parts in rows:
        canonical = str(parts[0]).strip()
        if not canonical:
            continue
        out.setdefault(canonical, canonical)
        for alias in parts[1:]:
            a = str(alias).strip()
            if not a:
                continue
            if a in out and out[a] != canonical:
                raise ValueError(
                    f"Alias '{a}' maps to multiple canonical IDs: {out[a]} vs {canonical}"
                )
            out[a] = canonical
    return out


def _build_canonical_aliases(rows: Iterable[list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for parts in rows:
        canonical = str(parts[0]).strip()
        if not canonical:
            continue
        aliases = [str(p).strip() for p in parts[1:] if str(p).strip()]
        if not aliases:
            continue
        out.setdefault(canonical, [])
        for a in aliases:
            if a not in out[canonical]:
                out[canonical].append(a)
    return out


def _apply_alias_file_to_dataframe(*, df, alias_file: str | Path) -> "object":
    """Apply alias mapping to dataframe columns."""
    path = Path(alias_file).resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"Alias file not found: {path}")

    rows = _read_alias_rows(path)
    if not rows:
        return df
    alias_map = _build_alias_map(rows)

    return _apply_alias_map_to_dataframe(df=df, alias_map=alias_map)


def _apply_alias_map_to_dataframe(*, df, alias_map: dict[str, str]) -> "object":
    """Apply an alias->canonical mapping to dataframe columns."""
    canonical_to_cols: dict[str, list[str]] = {}
    for c in list(df.columns):
        canonical = alias_map.get(str(c), str(c))
        if canonical != str(c):
            canonical_to_cols.setdefault(canonical, []).append(str(c))

    if not canonical_to_cols:
        return df

    df = df.copy()

    def _as_na(series):
        if series.dtype == object:
            s = series.astype(str)
            s = s.map(lambda v: v.strip() if isinstance(v, str) else v)
            s = s.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
            return s
        return series

    for canonical, cols in canonical_to_cols.items():
        cols_present = [c for c in cols if c in df.columns]
        if not cols_present:
            continue

        if canonical in df.columns and canonical not in cols_present:
            cols_present = [canonical] + cols_present

        if len(cols_present) == 1:
            src = cols_present[0]
            if src != canonical:
                if canonical not in df.columns:
                    df = df.rename(columns={src: canonical})
            continue

        combined = _as_na(df[cols_present[0]])
        for c in cols_present[1:]:
            combined = combined.combine_first(_as_na(df[c]))

        df[canonical] = combined
        for c in cols_present:
            if c != canonical and c in df.columns:
                df = df.drop(columns=[c])

    return df


def _canonicalize_template_items(
    *, sidecar: dict, canonical_aliases: dict[str, list[str]]
) -> dict:
    """Remove/merge alias item IDs inside a survey template (in-memory)."""
    out = dict(sidecar)
    for canonical, aliases in (canonical_aliases or {}).items():
        for alias in aliases:
            if alias not in out:
                continue
            if canonical not in out:
                out[canonical] = out[alias]
            try:
                del out[alias]
            except Exception:
                pass
    return out


# =============================================================================
# TASK SELECTION (from survey_selection.py)
# =============================================================================


def _resolve_selected_tasks(
    *,
    survey_filter: str | None,
    templates: dict,
) -> set[str] | None:
    """Parse and validate survey filter into selected normalized task names."""
    selected_tasks: set[str] | None = None
    if survey_filter:
        parts = [p.strip() for p in str(survey_filter).replace(";", ",").split(",")]
        parts = [p for p in parts if p]
        selected = {p.lower().replace("survey-", "") for p in parts}
        unknown_surveys = sorted([t for t in selected if t not in templates])
        if unknown_surveys:
            raise ValueError(
                "Unknown surveys: "
                + ", ".join(unknown_surveys)
                + ". Available: "
                + ", ".join(sorted(templates.keys()))
            )
        selected_tasks = selected

    return selected_tasks


# =============================================================================
# SESSION HANDLING (from survey_session_handling.py)
# =============================================================================


def _detect_sessions(*, df, res_ses_col: str | None) -> list[str]:
    """Detect session values from the selected session column."""
    detected_sessions: list[str] = []
    if res_ses_col:
        detected_sessions = sorted(
            [
                str(v).strip()
                for v in df[res_ses_col].dropna().unique()
                if str(v).strip()
            ]
        )
        print(f"[PRISM INFO] Sessions detected in {res_ses_col}: {detected_sessions}")
    else:
        print(
            f"[PRISM DEBUG] No session column detected (res_ses_col is None). Available columns: {list(df.columns)[:20]}"
        )
    return detected_sessions


def _filter_rows_by_selected_session(
    *,
    df,
    res_ses_col: str | None,
    session: str | None,
    duplicate_handling: str,
    detected_sessions: list[str],
):
    """Filter rows according to selected session policy."""
    rows_before_filter = len(df)
    if res_ses_col and session and session != "all":
        session_normalized = str(session).strip()
        df_filtered = df[df[res_ses_col].astype(str).str.strip() == session_normalized]
        if len(df_filtered) == 0:
            raise ValueError(
                f"No rows found with session '{session}' in column '{res_ses_col}'. "
                f"Available values: {', '.join(detected_sessions if detected_sessions else ['none'])}"
            )
        df = df_filtered
        print(
            f"[PRISM INFO] Filtered {rows_before_filter} rows → {len(df)} rows for session '{session}'"
        )
    elif (
        res_ses_col
        and not session
        and detected_sessions
        and duplicate_handling == "error"
    ):
        first_session = detected_sessions[0]
        df_filtered = df[df[res_ses_col].astype(str).str.strip() == first_session]
        if len(df_filtered) > 0:
            df = df_filtered
            print(
                f"[PRISM INFO] Auto-filtering to first session '{first_session}' for preview ({rows_before_filter} rows → {len(df)} rows)"
            )
    elif session == "all" and res_ses_col:
        print(f"[PRISM INFO] Processing all sessions from '{res_ses_col}'")

    return df


def _handle_duplicate_ids(
    *,
    df,
    res_id_col: str,
    duplicate_handling: str,
    normalize_sub_fn,
) -> tuple[object, str | None, list[str]]:
    """Handle duplicate participant IDs according to duplicate_handling policy."""
    warnings: list[str] = []
    res_ses_col_override: str | None = None

    normalized_ids = df[res_id_col].astype(str).map(normalize_sub_fn)
    if normalized_ids.duplicated().any():
        dup_ids = sorted(set(normalized_ids[normalized_ids.duplicated()]))
        dup_count = len(dup_ids)

        if duplicate_handling == "error":
            raise ValueError(
                f"Duplicate participant_id values after normalization: {', '.join(dup_ids[:5])}"
            )
        elif duplicate_handling == "keep_first":
            df = df[~normalized_ids.duplicated(keep="first")].copy()
            warnings.append(
                f"Duplicate IDs found ({dup_count} duplicates). Kept first occurrence for: {', '.join(dup_ids[:5])}"
            )
        elif duplicate_handling == "keep_last":
            df = df[~normalized_ids.duplicated(keep="last")].copy()
            warnings.append(
                f"Duplicate IDs found ({dup_count} duplicates). Kept last occurrence for: {', '.join(dup_ids[:5])}"
            )
        elif duplicate_handling == "sessions":
            df = df.copy()
            df["_dup_session_num"] = df.groupby(normalized_ids.values).cumcount() + 1
            res_ses_col_override = "_dup_session_num"
            warnings.append(
                f"Duplicate IDs found ({dup_count} duplicates). Created multiple sessions for: {', '.join(dup_ids[:5])}"
            )

    return df, res_ses_col_override, warnings


# =============================================================================
# TECHNICAL OVERRIDES (from survey_technical.py)
# =============================================================================


def _inject_missing_token(sidecar: dict, *, token: str) -> dict:
    """Ensure every item Levels includes the missing-value token."""
    if not isinstance(sidecar, dict):
        return sidecar

    for key, item in sidecar.items():
        if key in _NON_ITEM_TOPLEVEL_KEYS:
            continue
        if not isinstance(item, dict):
            continue

        levels = item.get("Levels")
        if isinstance(levels, dict):
            if token not in levels:
                levels[token] = "Missing/Not provided"
                item["Levels"] = levels

    return sidecar


def _apply_technical_overrides(sidecar: dict, overrides: dict) -> dict:
    """Apply best-effort technical metadata without breaking existing templates."""
    out = deepcopy(sidecar)
    tech = out.get("Technical")
    if not isinstance(tech, dict):
        tech = {}
        out["Technical"] = tech

    for k, v in overrides.items():
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        tech[k] = v

    return out


# =============================================================================
# MAPPING RESULTS (from survey_mapping_results.py)
# =============================================================================


def _resolve_tasks_with_warnings(
    *,
    col_to_mapping: dict,
    selected_tasks: set[str] | None,
    template_warnings_by_task: dict[str, list[str]],
) -> tuple[set[str], list[str]]:
    """Resolve tasks included in conversion and collect relevant warnings."""
    tasks_with_data = {m.task for m in col_to_mapping.values()}
    if selected_tasks is not None:
        tasks_with_data = tasks_with_data.intersection(selected_tasks)
    if not tasks_with_data:
        raise ValueError("No survey item columns matched the selected templates.")

    warnings: list[str] = []
    for task_name in sorted(tasks_with_data):
        warnings.extend(template_warnings_by_task.get(task_name, []))

    return tasks_with_data, warnings


def _build_col_to_task_and_task_runs(
    *,
    col_to_mapping: dict,
) -> tuple[dict[str, str], dict[tuple[str, int | None], list[str]]]:
    """Build compatibility col->task map and grouped task/run columns."""
    col_to_task = {col: m.task for col, m in col_to_mapping.items()}

    task_run_columns: dict[tuple[str, int | None], list[str]] = {}
    for col, mapping in col_to_mapping.items():
        key = (mapping.task, mapping.run)
        if key not in task_run_columns:
            task_run_columns[key] = []
        task_run_columns[key].append(col)

    return col_to_task, task_run_columns

def _build_template_matches_payload(*, lsa_analysis: dict | None) -> dict | None:
    """Build template match payload for API responses."""
    template_matches: dict | None = None
    if lsa_analysis:
        template_matches = {}
        for group_name, group_info in lsa_analysis["groups"].items():
            match = group_info.get("match")
            template_matches[group_name] = match.to_dict() if match else None
    return template_matches
