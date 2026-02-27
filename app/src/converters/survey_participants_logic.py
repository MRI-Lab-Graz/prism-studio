"""Participant ID mapping, resolution, and template logic for survey conversion."""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

from ..utils.io import read_json as _read_json
from .id_detection import detect_id_column, IdColumnNotDetectedError


# =============================================================================
# MAPPING LOADING & COLUMNS
# =============================================================================


def _load_participants_mapping(output_root: Path, log_fn=None) -> dict | None:
    """Load participants_mapping.json from the project."""
    project_root = output_root

    candidates = [
        project_root / "participants_mapping.json",
        project_root / "code" / "participants_mapping.json",
        project_root / "code" / "library" / "participants_mapping.json",
        project_root / "code" / "library" / "survey" / "participants_mapping.json",
    ]

    for p in candidates:
        if p.exists() and p.is_file():
            try:
                mapping = _read_json(p)
                if log_fn:
                    log_fn(f"Loaded participants_mapping.json from: {p}")
                return mapping
            except Exception as e:
                if log_fn:
                    log_fn(f"Warning: Failed to load {p}: {e}")
                continue

    if log_fn:
        log_fn("No participants_mapping.json found (using template columns only)")
    return None


def _get_mapped_columns(
    mapping: dict | None,
) -> tuple[set[str], dict[str, str], dict[str, dict]]:
    """Extract column information from participants mapping."""
    if not mapping or "mappings" not in mapping:
        return set(), {}, {}

    allowed_columns: set[str] = set()
    column_renames: dict[str, str] = {}
    value_mappings: dict[str, dict] = {}

    for var_name, spec in mapping.get("mappings", {}).items():
        if not isinstance(spec, dict):
            continue
        source_col = spec.get("source_column")
        standard_var = spec.get("standard_variable", var_name)

        if source_col:
            allowed_columns.add(source_col.lower())
            column_renames[source_col.lower()] = standard_var

            if "value_mapping" in spec:
                value_mappings[standard_var] = spec["value_mapping"]

    return allowed_columns, column_renames, value_mappings


# =============================================================================
# TEMPLATES
# =============================================================================


def _load_participants_template(library_dir: Path) -> dict | None:
    """Load a participant template from the survey library, if present."""

    library_dir = library_dir.resolve()
    candidates: list[Path] = []
    if library_dir.name == "survey":
        candidates.append(library_dir.parent / "participants.json")

    candidates.extend(
        [
            library_dir / "participants.json",
            library_dir / "survey-participants.json",
            library_dir / "survey-participant.json",
        ]
    )

    for ancestor in library_dir.parents[:3]:
        candidates.append(ancestor / "participants.json")

    try:
        app_root = Path(__file__).parent.parent.parent.resolve()  # app/
        repo_root = app_root.parent.resolve()  # prism-studio/
        candidates.append(app_root / "official" / "participants.json")
        candidates.append(repo_root / "official" / "participants.json")
    except Exception:
        pass

    seen: set[Path] = set()
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        if p.exists() and p.is_file():
            try:
                return _read_json(p)
            except Exception:
                return None
    return None


def _is_participant_template(path: Path) -> bool:
    stem = path.stem.lower()
    return stem in {"survey-participant", "survey-participants"}


def _normalize_participant_template_dict(template: dict | None) -> dict | None:
    """Extract column definitions from a participant template structure."""

    if not isinstance(template, dict):
        return None
    if "Columns" in template and isinstance(template.get("Columns"), dict):
        return template.get("Columns")
    return template


def _participants_json_from_template(
    *,
    columns: list[str],
    template: dict | None,
    extra_descriptions: dict[str, str] | None = None,
) -> dict:
    """Create a BIDS/NeuroBagel-compatible participants.json for TSV columns."""
    template = _normalize_participant_template_dict(template)
    extra_descriptions = extra_descriptions or {}
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
        units = v.get("Units") or v.get("Unit")
        if units:
            meta["Units"] = units
        for key in ("DataType", "VariableType", "MinValue", "MaxValue", "Annotations"):
            if key in v:
                meta[key] = v[key]
        return meta

    for col in columns:
        if col == "participant_id":
            out[col] = {
                "Description": "Participant identifier (BIDS subject label)",
            }
            continue

        meta = _template_meta(col)

        if not meta:
            if col in extra_descriptions:
                meta = {"Description": extra_descriptions[col]}
            else:
                meta = {"Description": col}
                if col == "age":
                    meta["Description"] = "Age of participant"
                    meta["Units"] = "years"
                elif col == "sex":
                    meta["Description"] = "Biological sex"
                elif col == "gender":
                    meta["Description"] = "Gender identity"

        out[col] = dict(meta)

    return out


# =============================================================================
# ID MAPPING & RESOLUTION
# =============================================================================


def _apply_subject_id_mapping(
    *,
    df,
    res_id_col: str,
    id_map: dict[str, str] | None,
    id_map_file,
    suggest_id_matches_fn,
    missing_id_mapping_error_cls,
):
    """Apply optional subject ID mapping and return updated dataframe/ID column."""
    warnings: list[str] = []
    if not id_map:
        return df, res_id_col, warnings

    df = df.copy()

    all_cols_lower = {str(c).strip().lower(): str(c) for c in df.columns}
    preferred_order = [
        res_id_col,
        "participant_id",
        "code",
        "token",
        "id",
        "subject",
        "sub_id",
        "participant",
    ]
    candidate_cols: list[str] = []
    seen = set()
    for name in preferred_order:
        if not name:
            continue
        if name in df.columns and name not in seen:
            candidate_cols.append(name)
            seen.add(name)
            continue
        lower = str(name).strip().lower()
        if lower in all_cols_lower:
            actual = all_cols_lower[lower]
            if actual not in seen:
                candidate_cols.append(actual)
                seen.add(actual)

    id_map_lower = {str(k).strip().lower(): v for k, v in id_map.items()}

    def _score_column(col: str) -> tuple[int, float]:
        col_values = df[col].astype(str).str.strip()
        unique_vals = set(col_values.unique())
        matches = len([v for v in unique_vals if str(v).strip().lower() in id_map_lower])
        total = len(unique_vals) if unique_vals else 1
        ratio = matches / total if total else 0.0
        return matches, ratio

    print(f"[PRISM DEBUG] ID map keys sample: {list(id_map_lower.keys())[:5]} ...")
    print(f"[PRISM DEBUG] Dataframe columns: {list(df.columns)}")
    print(f"[PRISM DEBUG] Candidate ID columns: {candidate_cols}")

    best_col = res_id_col
    best_matches, best_ratio = _score_column(res_id_col)
    print(f"[PRISM DEBUG] Score {res_id_col}: matches={best_matches}, ratio={best_ratio:.3f}")
    for c in candidate_cols:
        matches, ratio = _score_column(c)
        print(f"[PRISM DEBUG] Score {c}: matches={matches}, ratio={ratio:.3f}")
        if (matches > best_matches) or (matches == best_matches and ratio > best_ratio):
            best_col = c
            best_matches, best_ratio = matches, ratio

    if best_matches == 0 and "code" in candidate_cols:
        best_col = "code"
        print("[PRISM DEBUG] No matches; falling back to 'code' column")

    if best_col != res_id_col:
        warnings.append(
            f"Selected id_column '{best_col}' based on ID map overlap ({best_matches} matches)."
        )
        res_id_col = best_col

    print(
        f"[PRISM DEBUG] Selected ID column: {res_id_col}; unique sample: {df[res_id_col].astype(str).unique()[:10]}"
    )

    df[res_id_col] = df[res_id_col].astype(str).str.strip()
    ids_in_data = set(df[res_id_col].unique())
    missing = sorted([i for i in ids_in_data if str(i).strip().lower() not in id_map_lower])
    if missing:
        sample = ", ".join(missing[:20])
        more = "" if len(missing) <= 20 else f" (+{len(missing) - 20} more)"
        map_keys = list(id_map.keys())
        suggestions = suggest_id_matches_fn(missing, map_keys)
        raise missing_id_mapping_error_cls(
            missing,
            suggestions,
            f"ID mapping incomplete: {len(missing)} IDs from data are missing in the mapping: {sample}{more}.",
        )

    df[res_id_col] = df[res_id_col].map(
        lambda x: id_map_lower.get(str(x).strip().lower(), id_map.get(str(x).strip(), x))
    )
    warnings.append(
        f"Applied subject ID mapping from {Path(id_map_file).name} ({len(id_map)} entries)."
    )

    return df, res_id_col, warnings


def _resolve_id_and_session_cols(
    df,
    id_column: str | None,
    session_column: str | None,
    participants_template: dict | None = None,
    source_format: str = "xlsx",
    has_prismmeta: bool = False,
) -> tuple[str, str | None]:
    """Determine participant ID and session columns from dataframe."""
    
    resolved_id = detect_id_column(
        df_columns=list(df.columns),
        source_format=source_format,
        explicit_id_column=id_column,
        has_prismmeta=has_prismmeta,
    )
    if not resolved_id:
        raise IdColumnNotDetectedError(list(df.columns), source_format)

    def _find_col(candidates: set[str]) -> str | None:
        lower_map = {str(c).strip().lower(): str(c).strip() for c in df.columns}
        for c in candidates:
            if c in lower_map:
                return lower_map[c]
        return None

    resolved_ses: str | None
    if session_column:
        if session_column not in df.columns:
            raise ValueError(
                f"session_column '{session_column}' not found in input columns"
            )
        resolved_ses = session_column
    else:
        resolved_ses = _find_col({"session", "ses", "visit", "timepoint"})

    return str(resolved_id), resolved_ses
