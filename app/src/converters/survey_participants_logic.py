"""Participant ID mapping, resolution, and template logic for survey conversion."""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

from ..participants_paths import participants_mapping_candidates
from ..utils.io import read_json as _read_json, write_json as _write_json
from .id_detection import detect_id_column, IdColumnNotDetectedError
from . import survey_processing as _survey_processing

# =============================================================================
# MAPPING LOADING & COLUMNS
# =============================================================================


def _load_participants_mapping(output_root: Path, log_fn=None) -> dict | None:
    """Load participants_mapping.json from the project."""
    project_root = output_root

    candidates = participants_mapping_candidates(project_root)

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
        matches = len(
            [v for v in unique_vals if str(v).strip().lower() in id_map_lower]
        )
        total = len(unique_vals) if unique_vals else 1
        ratio = matches / total if total else 0.0
        return matches, ratio

    print(f"[PRISM DEBUG] ID map keys sample: {list(id_map_lower.keys())[:5]} ...")
    print(f"[PRISM DEBUG] Dataframe columns: {list(df.columns)}")
    print(f"[PRISM DEBUG] Candidate ID columns: {candidate_cols}")

    best_col = res_id_col
    best_matches, best_ratio = _score_column(res_id_col)
    print(
        f"[PRISM DEBUG] Score {res_id_col}: matches={best_matches}, ratio={best_ratio:.3f}"
    )
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
    missing = sorted(
        [i for i in ids_in_data if str(i).strip().lower() not in id_map_lower]
    )
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
        lambda x: id_map_lower.get(
            str(x).strip().lower(), id_map.get(str(x).strip(), x)
        )
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
    run_column: str | None = None,
) -> tuple[str, str | None, str | None]:
    """Determine participant ID, session, and run columns from dataframe."""

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

    resolved_run: str | None
    if run_column:
        if run_column not in df.columns:
            raise ValueError(f"run_column '{run_column}' not found in input columns")
        resolved_run = run_column
    else:
        resolved_run = _find_col({"run", "run_id", "run_number", "run_nr"})

    return str(resolved_id), resolved_ses, resolved_run


# =============================================================================
# VALUE AUTO-CORRECTION & PARTICIPANTS.TSV WRITING
# =============================================================================


def _find_matching_level_key(value: str, levels: dict) -> str | None:
    """Try to find the original level key for a potentially sanitized value.

    Handles:
    - Direct matches (case-insensitive)
    - LimeSurvey truncated codes (e.g., 'cohng' -> 'cohabiting')
    - Common missing value formats (e.g., 'na' -> 'n/a')

    Returns:
        Original level key if found, None otherwise
    """
    v_lower = value.lower().strip()

    # Direct match (case-insensitive)
    for key in levels:
        if key.lower() == v_lower:
            return key

    # Handle common missing value variations
    if v_lower == "na":
        if "n/a" in levels:
            return "n/a"
        if "N/A" in levels:
            return "N/A"

    # Try reverse LimeSurvey sanitization lookup
    # For each level key, compute what LimeSurvey would truncate it to
    # and see if it matches the input value
    for key in levels:
        sanitized = _survey_processing._sanitize_answer_code_for_ls(key)
        if sanitized == v_lower:
            return key

    return None


def _safe_eval_formula(formula: str) -> float | None:
    """Safely evaluate a simple arithmetic formula (e.g., BMI calculation).

    Only allows: numbers, basic arithmetic (+, -, *, /), round(), parentheses.
    Returns None if evaluation fails or formula is unsafe.

    Examples:
        'round(56 / ((145 / 100) * (145 / 100)), 1)' -> 26.6
        '123 + 456' -> 579
    """
    import ast
    import operator

    if not isinstance(formula, str):
        return None

    formula = formula.strip()
    if not formula:
        return None

    # Quick check: must contain at least one digit and an operator
    if not any(c.isdigit() for c in formula):
        return None
    if not any(c in formula for c in "+-*/()"):
        return None

    # Whitelist of safe operations
    safe_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def _eval_node(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Non-numeric constant")
        elif isinstance(node, ast.Num):  # Python 3.7 compatibility
            return node.n
        elif isinstance(node, ast.BinOp):
            if type(node.op) not in safe_operators:
                raise ValueError(f"Unsafe operator: {type(node.op)}")
            left = _eval_node(node.left)
            right = _eval_node(node.right)
            return safe_operators[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp):
            if type(node.op) not in safe_operators:
                raise ValueError(f"Unsafe unary operator: {type(node.op)}")
            operand = _eval_node(node.operand)
            return safe_operators[type(node.op)](operand)
        elif isinstance(node, ast.Call):
            # Only allow round() function
            if isinstance(node.func, ast.Name) and node.func.id == "round":
                args = [_eval_node(arg) for arg in node.args]
                return round(*args)
            raise ValueError("Unsafe function call")
        elif isinstance(node, ast.Expression):
            return _eval_node(node.body)
        else:
            raise ValueError(f"Unsafe node type: {type(node)}")

    try:
        tree = ast.parse(formula, mode="eval")
        result = _eval_node(tree)
        if isinstance(result, (int, float)) and not (result != result):  # not NaN
            return result
        return None
    except Exception:
        return None


def _auto_correct_participant_value(
    value, col_name: str, template: dict | None, missing_token: str
) -> str:
    """Auto-correct a participant data value based on template Levels.

    Handles:
    - LimeSurvey truncated codes -> original level keys
    - 'na' -> 'n/a' for missing values
    - Formula strings -> evaluated numeric values

    Returns the corrected value, or original if no correction needed/possible.
    """
    if template is None:
        return value

    # Get column schema from template
    col_schema = template.get(col_name)
    if not isinstance(col_schema, dict):
        return value

    v_str = str(value).strip() if value is not None else ""

    # Skip empty/missing values
    if not v_str or v_str.lower() in ("", "nan", "none"):
        return missing_token

    # Check for Levels - try to find matching key
    levels = col_schema.get("Levels")
    if isinstance(levels, dict) and levels:
        # Direct match
        if v_str in levels:
            return v_str

        # Try reverse lookup
        matched_key = _find_matching_level_key(v_str, levels)
        if matched_key is not None:
            return matched_key

    # Check for numeric DataType - try to evaluate formulas
    data_type = col_schema.get("DataType", "").lower()
    if data_type in ("number", "integer", "float"):
        # If it's already a valid number, return as-is
        try:
            float(v_str)
            return v_str
        except (ValueError, TypeError):
            pass

        # Try to evaluate as formula
        result = _safe_eval_formula(v_str)
        if result is not None:
            if data_type == "integer":
                return str(int(round(result)))
            else:
                # Round to reasonable precision
                return str(round(result, 2))

    return value


@dataclass
class ParticipantColumnPlan:
    extra_cols: list
    col_output_names: dict
    mapping_descriptions: dict
    value_mappings: dict
    template_norm: dict | None


def _determine_participant_output_columns(
    *,
    df,
    output_root: Path,
    id_col: str,
    ses_col: str | None,
    participant_template: dict | None,
    lsa_col_renames: dict | None,
) -> ParticipantColumnPlan:
    """Decide which source columns go into participants.tsv and under what
    output name.

    Mode 1 (participants_mapping.json exists): only explicitly mapped
    columns, renamed per the mapping.
    Mode 2 (no mapping): only columns present in the official participant
    template, with an LSA-mangled-name fallback lookup.
    """
    lower_to_col = {str(c).strip().lower(): str(c).strip() for c in df.columns}

    participants_mapping = _load_participants_mapping(output_root)
    mapped_cols, col_renames, value_mappings = _get_mapped_columns(participants_mapping)

    if participants_mapping:
        print(
            f"[INFO] Using participants_mapping.json from project ({len(mapped_cols)} mapped columns)"
        )
        if col_renames:
            print(f"[INFO]   Column renames: {col_renames}")
        if value_mappings:
            print(f"[INFO]   Value transformations for: {list(value_mappings.keys())}")
    else:
        print("[INFO] No participants_mapping.json found (using template columns only)")

    template_norm = _normalize_participant_template_dict(participant_template)
    template_cols = set(template_norm.keys()) if template_norm else set()
    non_column_keys = {
        "@context",
        "Technical",
        "I18n",
        "Study",
        "Metadata",
        "_aliases",
        "_reverse_aliases",
    }
    template_cols = template_cols - non_column_keys

    extra_cols: list = []
    col_output_names: dict = {}
    mapping_descriptions: dict = {}

    if participants_mapping and mapped_cols:
        for source_col_lower in mapped_cols:
            if source_col_lower in lower_to_col:
                actual_col = lower_to_col[source_col_lower]
                if actual_col not in {id_col, ses_col}:
                    extra_cols.append(actual_col)
                    output_name = col_renames.get(source_col_lower, source_col_lower)
                    col_output_names[actual_col] = output_name

        for var_name, spec in participants_mapping.get("mappings", {}).items():
            if isinstance(spec, dict):
                standard_var = spec.get("standard_variable", var_name)
                if standard_var not in template_cols and "description" in spec:
                    mapping_descriptions[standard_var] = spec["description"]
    else:
        for col in template_cols:
            if col in lower_to_col:
                actual_col = lower_to_col[col]
                if actual_col not in {id_col, ses_col}:
                    extra_cols.append(actual_col)
                    col_output_names[actual_col] = col
            elif lsa_col_renames:
                mangled = None
                for mangled_name, standard_name in lsa_col_renames.items():
                    if standard_name == col:
                        mangled = mangled_name
                        break
                mangled_lower = mangled.strip().lower() if mangled else None
                if mangled_lower and mangled_lower in lower_to_col:
                    actual_col = lower_to_col[mangled_lower]
                    if actual_col not in {id_col, ses_col}:
                        extra_cols.append(actual_col)
                        col_output_names[actual_col] = col

    return ParticipantColumnPlan(
        extra_cols=extra_cols,
        col_output_names=col_output_names,
        mapping_descriptions=mapping_descriptions,
        value_mappings=value_mappings,
        template_norm=template_norm,
    )


def _build_participant_output_dataframe(
    *,
    df,
    id_col: str,
    normalize_sub_fn,
    is_missing_fn,
    missing_token: str,
    column_plan: ParticipantColumnPlan,
):
    """Build the deduplicated participants dataframe: participant_id plus
    the extra columns column_plan selected, with value mappings, missing-value
    substitution, and template-based auto-correction applied."""
    import pandas as pd

    df_part = pd.DataFrame(
        {"participant_id": df[id_col].astype(str).map(normalize_sub_fn)}
    )

    extra_cols = column_plan.extra_cols
    if extra_cols:
        extra_cols = list(dict.fromkeys(extra_cols))
        df_extra = df[[id_col] + extra_cols].copy()

        for c in extra_cols:
            output_name = column_plan.col_output_names.get(c, c)

            if output_name in column_plan.value_mappings:
                val_map = column_plan.value_mappings[output_name]
                df_extra[c] = (
                    df_extra[c]
                    .astype(str)
                    .map(
                        lambda v, vm=val_map: (
                            vm.get(v, v)
                            if v not in ("nan", "None", "")
                            else missing_token
                        )
                    )
                )
            else:
                df_extra[c] = df_extra[c].apply(
                    lambda v: missing_token if is_missing_fn(v) else v
                )

        df_extra[id_col] = df_extra[id_col].astype(str).map(normalize_sub_fn)
        df_extra = df_extra.rename(columns={id_col: "participant_id"})
        df_extra = (
            df_extra.groupby("participant_id", dropna=False)[extra_cols]
            .first()
            .reset_index()
        )

        rename_map = {c: column_plan.col_output_names.get(c, c) for c in extra_cols}
        df_extra = df_extra.rename(columns=rename_map)

        if column_plan.template_norm:
            for col in df_extra.columns:
                if col == "participant_id":
                    continue
                df_extra[col] = df_extra[col].apply(
                    lambda v, c=col, t=column_plan.template_norm: (
                        _auto_correct_participant_value(v, c, t, missing_token=missing_token)
                    )
                )

        df_part = df_part.merge(df_extra, on="participant_id", how="left")

    df_part = df_part.drop_duplicates(subset=["participant_id"]).reset_index(drop=True)
    return df_part


def _merge_with_existing_participants_tsv(*, df_part, participants_tsv_path: Path):
    """Merge df_part with an existing participants.tsv on disk, if present.
    New values win for overlapping participants/columns; falls back to the
    old value if the new one is missing. Returns df_part unchanged if there's
    no existing file, it has no participant_id column, or the merge fails."""
    import pandas as pd

    if not participants_tsv_path.exists():
        return df_part

    try:
        existing_df = pd.read_csv(participants_tsv_path, sep="\t", dtype=str)
        if "participant_id" not in existing_df.columns:
            return df_part

        merged = pd.merge(
            existing_df,
            df_part,
            on="participant_id",
            how="outer",
            suffixes=("_old", "_new"),
        )

        for col in merged.columns:
            if col.endswith("_new"):
                base_col = col[:-4]
                old_col = base_col + "_old"
                if old_col in merged.columns:
                    merged[base_col] = merged.apply(
                        lambda row: (
                            row[col]
                            if pd.notna(row[col])
                            and str(row[col]) not in ("n/a", "nan", "")
                            else (
                                row[old_col] if pd.notna(row[old_col]) else "n/a"
                            )
                        ),
                        axis=1,
                    )
                    merged = merged.drop(columns=[old_col, col])
                else:
                    merged = merged.rename(columns={col: base_col})

        merged = merged.sort_values("participant_id").reset_index(drop=True)
        print(
            f"[INFO] Merged with existing participants.tsv ({len(existing_df)} existing → {len(merged)} total)"
        )
        return merged
    except Exception as e:
        print(f"[WARNING] Could not merge with existing participants.tsv: {e}")
        return df_part


def _write_survey_participants(
    *,
    df,
    output_root: Path,
    id_col: str,
    ses_col: str | None,
    participant_template: dict | None,
    normalize_sub_fn,
    is_missing_fn,
    missing_token: str,
    lsa_col_renames: dict[str, str] | None = None,
):
    """Write participants.tsv and participants.json.

    Column inclusion logic:
    1. If participants_mapping.json exists in project:
       - Only include columns explicitly defined in the mapping
       - Apply value transformations as specified
       - Rename columns to standard variable names
    2. If no mapping exists:
       - Only include columns that exist in the official participants template
       - No arbitrary extra columns from source data

    All columns in the output must have documentation in participants.json.
    """
    column_plan = _determine_participant_output_columns(
        df=df,
        output_root=output_root,
        id_col=id_col,
        ses_col=ses_col,
        participant_template=participant_template,
        lsa_col_renames=lsa_col_renames,
    )
    df_part = _build_participant_output_dataframe(
        df=df,
        id_col=id_col,
        normalize_sub_fn=normalize_sub_fn,
        is_missing_fn=is_missing_fn,
        missing_token=missing_token,
        column_plan=column_plan,
    )

    participants_tsv_path = output_root / "participants.tsv"
    df_part = _merge_with_existing_participants_tsv(
        df_part=df_part, participants_tsv_path=participants_tsv_path
    )

    df_part.to_csv(participants_tsv_path, sep="\t", index=False)

    # participants.json - all columns must be documented
    parts_json_path = output_root / "participants.json"
    p_json = _participants_json_from_template(
        columns=[str(c) for c in df_part.columns],
        template=participant_template,
        extra_descriptions=column_plan.mapping_descriptions,
    )
    _write_json(parts_json_path, p_json)
