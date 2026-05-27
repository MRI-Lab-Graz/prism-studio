"""Survey-recipes computation.

This module implements the logic behind `prism_tools.py recipes surveys` as a
reusable API, so both the CLI and the Web/GUI can call the same code.

It reads recipes from the repository's `recipe/survey/*.json`
folder and writes outputs into the target dataset under:

- `derivatives/survey/<recipe_id>/sub-*/ses-*/survey/*_desc-scores_beh.tsv` (format="prism")
- or `derivatives/survey/survey_scores.tsv` (format="flat")

Additionally, it creates `derivatives/survey/dataset_description.json` in the
output dataset.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import csv
import re
import json
from typing import Any, Dict, Optional

from src.recipes_formula_engine import (
    _calculate_derived_variables,
    _calculate_scores,
    _format_numeric_cell,
    _get_item_value,
    _map_value_to_bucket,
    _parse_numeric_cell,
    _safe_eval_formula_expression,
)
from src.reporting import _pick_references

RECIPE_FILENAME_GLOB = "recipe-*.json"

_MISSING_TEXT_TOKENS = {"", "n/a", "na", "nan", "none", "null"}


@dataclass(frozen=True)
class SurveyRecipesResult:
    processed_files: int
    written_files: int
    out_format: str
    out_root: Path
    flat_out_path: Path | None
    fallback_note: str | None = None
    nan_report: dict[str, list[str]] | None = None
    boilerplate_path: Path | None = None
    boilerplate_html_path: Path | None = None
    recipes_dir: Path | None = None
    """Actual directory recipes were loaded from."""
    recipes_seeded: int = 0
    """Number of recipe files newly copied into the project."""
    written_recipe_ids: tuple[str, ...] = ()
    """Recipe IDs that produced output in this run."""
    missing_input_tasks: tuple[str, ...] = ()
    """Input tasks detected in data files without a matching loaded recipe."""
    raw_only_tasks: tuple[str, ...] = ()
    """Input tasks exported as raw-only because no matching recipe was available."""


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, obj: dict) -> None:
    _ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _copy_recipes_to_project(
    *, recipes: dict[str, dict], dataset_root: Path, modality: str
) -> int:
    """Copy used recipes to project's code/recipes/{modality}/ for reproducibility.

    Returns the number of recipe files newly written (not pre-existing).
    """
    recipes_dir = dataset_root / "code" / "recipes" / modality
    recipes_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for recipe_id, rec in recipes.items():
        output_path = recipes_dir / f"recipe-{recipe_id}.json"
        if not output_path.exists():
            _write_json(output_path, rec.get("json") or {})
            copied += 1
    return copied


def _ensure_bidsignore_prism_rules(dataset_root: Path, modality: str) -> None:
    """Ensure .bidsignore contains PRISM-only and legacy project rules."""
    bidsignore_path = dataset_root / ".bidsignore"
    rules = {
        "derivatives/",
        "code/",
        "code/recipes/",
        "code/library/",
        "recipes/",
        "recipe/",
        "library/",
        "survey/",
        "*_survey.*",
        "*_biometrics.*",
    }
    if modality:
        rules.add(f"{modality}/")
        rules.add(f"**/{modality}/")

    existing_rules: set[str] = set()
    if bidsignore_path.exists():
        existing_rules = {
            line.strip()
            for line in bidsignore_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }

    missing_rules = sorted(r for r in rules if r not in existing_rules)
    if not missing_rules:
        return

    if not bidsignore_path.exists():
        bidsignore_path.write_text(
            "# .bidsignore created by prism\n"
            "# Ignores custom modalities to ensure BIDS-App compatibility\n",
            encoding="utf-8",
        )

    with open(bidsignore_path, "a", encoding="utf-8") as f:
        f.write("\n# Added by prism recipe conversion\n")
        for rule in missing_rules:
            f.write(f"{rule}\n")


def _get_sidecar_for_task(dataset_path: Path, prefix: str, name: str) -> dict:
    """Find and load sidecar JSON for a given task/biometric."""
    candidates = [
        dataset_path
        / "code"
        / "library"
        / prefix
        / f"{prefix}-{name}.json",  # project library (main source)
        dataset_path / f"{prefix}-{name}.json",
        dataset_path / f"{prefix}s" / f"{prefix}-{name}.json",
        dataset_path / f"{name}.json",
        dataset_path / f"task-{name}_{prefix}.json",  # BIDS-style sidecar
    ]
    for p in candidates:
        if p.exists():
            try:
                return _read_json(p)
            except Exception:
                continue
    return {}


def _normalize_output_format(out_format: str | None) -> str:
    """Normalize user-facing format names to canonical internal keys."""
    normalized = str(out_format or "").strip().lower()
    if normalized in {"save", "spss"}:
        return "sav"
    return normalized


def _read_tsv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        header = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    return header, rows


def _write_tsv_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    _ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=header, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in header})


def get_i18n_text(obj: Any, lang: str = "en") -> str:
    """Get localized text from a string or a dictionary of translations."""
    if isinstance(obj, dict):
        # Try requested language, then English, then first available
        return str(obj.get(lang, obj.get("en", next(iter(obj.values()), ""))))
    return str(obj or "")


def _sanitize_value_labels(levels: Any, lang: str = "en") -> dict[str, str]:
    """Return cleaned categorical labels, dropping invalid endpoint-only maps."""
    if not isinstance(levels, dict) or not levels:
        return {}

    labels: dict[str, str] = {
        str(k): get_i18n_text(v, lang).strip() for k, v in levels.items()
    }

    # Incomplete codebooks (empty labels) should not be exported as categorical maps.
    if any(not label for label in labels.values()):
        return {}

    # Endpoint-only sparse maps (e.g., 0/100 VAS anchors) are scale anchors, not levels.
    numeric_keys: list[float] = []
    for key in labels.keys():
        try:
            numeric_keys.append(float(key))
        except (TypeError, ValueError):
            numeric_keys = []
            break
    if len(labels) == 2 and numeric_keys:
        if min(numeric_keys) == 0.0 and max(numeric_keys) == 100.0:
            return {}

    return labels


def _build_variable_metadata(
    columns: list[str],
    participants_meta: dict,
    recipe: dict,
    sidecar_meta: Optional[dict] = None,
    lang: str = "en",
) -> tuple[dict[str, str], dict[str, dict], dict[str, dict]]:
    """Build variable labels and value labels from metadata sources.

    Returns:
            - variable_labels: {column_name: description}
            - value_labels: {column_name: {code: label}}
            - score_details: {column_name: {method, range, items, note, ...}}
    """
    variable_labels: dict[str, str] = {}
    value_labels: dict[str, dict] = {}
    score_details: dict[str, dict] = {}

    # Standard columns
    variable_labels["participant_id"] = "Participant identifier"
    variable_labels["session"] = "Session identifier"

    # From sidecar (survey-*.json)
    if sidecar_meta:
        for col in columns:
            # Try exact match first, then strip session suffix (e.g. ADS01_ses_01 -> ADS01)
            sidecar_key = (
                col if col in sidecar_meta else re.sub(r"_ses[_-]\w+$", "", col)
            )
            col_meta = sidecar_meta.get(sidecar_key)
            if isinstance(col_meta, dict):
                desc = col_meta.get("Description") or col_meta.get("description") or ""
                if desc:
                    variable_labels[col] = get_i18n_text(desc, lang)
                levels = col_meta.get("Levels") or col_meta.get("levels") or {}
                sanitized = _sanitize_value_labels(levels, lang)
                if sanitized:
                    value_labels[col] = sanitized

    # From participants.json
    for col in columns:
        if col in participants_meta:
            col_meta = participants_meta[col]
            if isinstance(col_meta, dict):
                # Description/variable label
                desc = col_meta.get("Description") or col_meta.get("description") or ""
                if desc:
                    variable_labels[col] = get_i18n_text(desc, lang)
                # Levels/value labels
                levels = col_meta.get("Levels") or col_meta.get("levels") or {}
                sanitized = _sanitize_value_labels(levels, lang)
                if sanitized:
                    value_labels[col] = sanitized

    # From recipe Scores - extract full details
    scores = recipe.get("Scores") or []
    for score in scores:
        name = score.get("Name")
        if name and name in columns:
            desc = score.get("Description") or ""
            if desc:
                variable_labels[name] = get_i18n_text(desc, lang)
            # Add interpretation as value labels if present
            interp = score.get("Interpretation")
            if interp and isinstance(interp, dict):
                value_labels[name] = {
                    str(k): get_i18n_text(v, lang) for k, v in interp.items()
                }

            # Build detailed score info
            details = {}
            if score.get("Method"):
                details["method"] = score["Method"]
            if score.get("Items"):
                details["items"] = score["Items"]
            if score.get("Range"):
                details["range"] = score["Range"]
            if score.get("Note"):
                details["note"] = get_i18n_text(score["Note"], lang)
            if score.get("Missing"):
                details["missing_handling"] = score["Missing"]
            if score.get("MinValid") is not None:
                details["min_valid"] = score["MinValid"]
            if score.get("Interpretation"):
                details["interpretation"] = score["Interpretation"]
            if details:
                score_details[name] = details

    return variable_labels, value_labels, score_details


def _build_survey_metadata(recipe: dict, lang: str = "en") -> dict:
    """Extract survey-level metadata from recipe for inclusion in codebook."""
    meta = {}

    # Recipe version and kind
    if recipe.get("RecipeVersion"):
        meta["recipe_version"] = recipe["RecipeVersion"]
    if recipe.get("Kind"):
        meta["kind"] = recipe["Kind"]

    # Survey info block
    survey_info = recipe.get("Survey") or {}
    if survey_info.get("Name"):
        meta["survey_name"] = get_i18n_text(survey_info["Name"], lang)
    if survey_info.get("TaskName"):
        meta["task_name"] = survey_info["TaskName"]
    if survey_info.get("Description"):
        meta["survey_description"] = get_i18n_text(survey_info["Description"], lang)
    if survey_info.get("Version"):
        meta["survey_version"] = survey_info["Version"]
    if survey_info.get("Authors"):
        meta["authors"] = survey_info["Authors"]
    if survey_info.get("Citation"):
        meta["citation"] = survey_info["Citation"]
    if survey_info.get("License"):
        meta["license"] = survey_info["License"]
    if survey_info.get("URL"):
        meta["url"] = survey_info["URL"]

    # Transforms info (e.g., which items were reverse-coded)
    transforms = recipe.get("Transforms") or {}
    if transforms.get("Invert"):
        invert = transforms["Invert"]
        inverted_items = invert.get("Items") or []
        if inverted_items:
            meta["reverse_coded_items"] = inverted_items
            scale = invert.get("Scale") or {}
            if scale:
                meta["reverse_code_scale"] = scale

    return meta


def _clean_export_context_value(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or text.lower() in {"", "n/a", "na", "nan", "none", "null"}:
        return None
    return text


def _distinct_export_context_values(values: Any) -> list[str]:
    if values is None:
        return []

    if hasattr(values, "dropna"):
        try:
            iterable = values.dropna().tolist()
        except Exception:
            iterable = list(values)
    else:
        iterable = list(values)

    cleaned: list[str] = []
    seen: set[str] = set()
    for value in iterable:
        text = _clean_export_context_value(value)
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return cleaned


def _build_export_context_key(
    *, session: Any = None, run: Any = None, include_session: bool, include_run: bool
) -> str:
    parts: list[str] = []

    if include_session:
        session_text = _clean_export_context_value(session)
        if session_text:
            parts.append(session_text)

    if include_run:
        run_text = _clean_export_context_value(run)
        if run_text:
            parts.append(run_text)

    return "_".join(parts)


def _prefixed_recipe_column_name(recipe_id: str, column: str) -> str:
    column_text = str(column)
    if column_text.lower().startswith(recipe_id.lower()):
        return column_text
    return f"{recipe_id}_{column_text}"


def _strip_export_context_suffix(column: str) -> str:
    return re.sub(r"_(?:ses[_-][^_]+(?:_run-[^_]+)?|run-[^_]+)$", "", str(column))


def _plan_merge_all_column_renames(
    recipe_frames: list[tuple[str, Any]],
    *,
    merge_keys: set[str],
    include_recipe_prefix: bool,
) -> dict[str, dict[str, str]]:
    desired_by_owner: dict[tuple[str, str], str] = {}
    owners_by_name: dict[str, list[tuple[str, str]]] = {}

    for recipe_id, frame in recipe_frames:
        for column in frame.columns:
            column_text = str(column)
            if column_text in merge_keys:
                continue

            desired = (
                _prefixed_recipe_column_name(recipe_id, column_text)
                if include_recipe_prefix
                else column_text
            )
            owner = (recipe_id, column_text)
            desired_by_owner[owner] = desired
            owners_by_name.setdefault(desired, []).append(owner)

    rename_maps: dict[str, dict[str, str]] = {}
    for (recipe_id, column_text), desired in desired_by_owner.items():
        final_name = desired
        if len(owners_by_name.get(desired, [])) > 1:
            final_name = _prefixed_recipe_column_name(recipe_id, column_text)
        if final_name != column_text:
            rename_maps.setdefault(recipe_id, {})[column_text] = final_name

    return rename_maps


def _build_combined_output_metadata(
    columns: list[str],
    participants_meta: dict,
    recipe_by_id: dict[str, dict],
    lang: str = "en",
    dataset_path: Optional[Path] = None,
    modality: str = "survey",
) -> tuple[dict[str, str], dict[str, dict], dict[str, dict]]:
    """Build metadata for combined outputs with recipe prefixes when needed."""
    variable_labels: dict[str, str] = {
        "participant_id": "Participant identifier",
        "session": "Session identifier",
    }
    value_labels: dict[str, dict] = {}
    score_details: dict[str, dict] = {}

    # Participant metadata from participants.json (sociodemographics)
    for col in columns:
        if col in participants_meta and isinstance(participants_meta[col], dict):
            col_meta = participants_meta[col]
            desc = col_meta.get("Description") or col_meta.get("description") or ""
            if desc:
                variable_labels[col] = get_i18n_text(desc, lang)
            levels = col_meta.get("Levels") or col_meta.get("levels") or {}
            if levels and isinstance(levels, dict):
                value_labels[col] = {
                    str(k): get_i18n_text(v, lang) for k, v in levels.items()
                }

    # Per-recipe sidecar item labels (e.g. ADS01 -> selten/manchmal/...)
    col_set = set(columns)
    for recipe_id in recipe_by_id:
        if dataset_path:
            sidecar = _get_sidecar_for_task(dataset_path, modality, recipe_id)
            for sidecar_key, col_meta in sidecar.items():
                if not isinstance(col_meta, dict):
                    continue
                candidate_names = {
                    sidecar_key,
                    _prefixed_recipe_column_name(recipe_id, sidecar_key),
                }
                # Match bare column OR stripped session-suffix variant
                for col in col_set:
                    bare = _strip_export_context_suffix(col)
                    if bare not in candidate_names:
                        continue
                    desc = (
                        col_meta.get("Description") or col_meta.get("description") or ""
                    )
                    if desc and col not in variable_labels:
                        variable_labels[col] = get_i18n_text(desc, lang)
                    levels = col_meta.get("Levels") or col_meta.get("levels") or {}
                    if levels and isinstance(levels, dict) and col not in value_labels:
                        value_labels[col] = {
                            str(k): get_i18n_text(v, lang) for k, v in levels.items()
                        }
    for recipe_id, recipe in recipe_by_id.items():
        for score in recipe.get("Scores") or []:
            score_name = str(score.get("Name", "")).strip()
            if not score_name:
                continue
            score_candidate_names = [
                score_name,
                _prefixed_recipe_column_name(recipe_id, score_name),
            ]
            for candidate in dict.fromkeys(score_candidate_names):
                if candidate not in columns:
                    continue

                desc = score.get("Description") or ""
                if desc:
                    variable_labels[candidate] = get_i18n_text(desc, lang)

                interp = score.get("Interpretation")
                if interp and isinstance(interp, dict):
                    value_labels[candidate] = {
                        str(k): get_i18n_text(v, lang) for k, v in interp.items()
                    }

                details: dict[str, Any] = {}
                if score.get("Method"):
                    details["method"] = score["Method"]
                if score.get("Items"):
                    details["items"] = score["Items"]
                if score.get("Range"):
                    details["range"] = score["Range"]
                if score.get("Note"):
                    details["note"] = get_i18n_text(score["Note"], lang)
                if score.get("Missing"):
                    details["missing_handling"] = score["Missing"]
                if score.get("MinValid") is not None:
                    details["min_valid"] = score["MinValid"]
                if score.get("Interpretation"):
                    details["interpretation"] = score["Interpretation"]
                if details:
                    score_details[candidate] = details

    return variable_labels, value_labels, score_details


# SPSS / SAV / codebook export helpers have been extracted to
# ``src.recipes_export_helpers``. They are re-exported below so existing
# imports (and tests) that reference them on this module keep working.
from src.recipes_export_helpers import (  # noqa: E402
    _apply_declared_datatypes,
    _apply_missing_export_policy,
    _build_sav_value_labels,
    _build_sav_variable_measure,
    _build_spss_rename_map,
    _coerce_value_labeled_columns_for_sav,
    _normalize_declared_data_type,
    _prepare_dataframe_for_sav,
    _sanitize_spss_variable_name,
    _write_codebook_json,
    _write_codebook_tsv,
)

# Path / filename / participant-ID utilities have been extracted to
# ``src.recipes_path_utils``. They are re-exported below so existing
# imports (and tests) that reference them on this module keep working.
from src.recipes_path_utils import (  # noqa: E402
    _extract_acq_from_filename,
    _extract_task_from_survey_filename,
    _infer_run_from_path,
    _infer_sub_ses_from_path,
    _is_missing_cell_value,
    _normalize_participant_id_for_join,
    _normalize_survey_key,
    _participant_join_key,
    _strip_acq_from_task,
    _strip_suffix,
)


def _build_participant_value_lookup(participants_df: Any) -> dict[str, dict[str, str]]:
    """Return participant values keyed by normalized participant join key."""
    lookup: dict[str, dict[str, str]] = {}
    if participants_df is None:
        return lookup
    if "participant_id" not in participants_df.columns:
        return lookup

    participant_cols = [c for c in participants_df.columns if c != "participant_id"]
    if not participant_cols:
        return lookup

    for _index, row in participants_df.iterrows():
        key = _participant_join_key(row.get("participant_id"))
        if not key or key in lookup:
            continue
        values: dict[str, str] = {}
        for col in participant_cols:
            raw = row.get(col)
            if _is_missing_cell_value(raw):
                continue
            values[col] = str(raw).strip()
        lookup[key] = values

    return lookup


def _participant_export_columns(participants_df: Any) -> list[str]:
    """Return participant.tsv columns to carry into exported outputs."""
    if participants_df is None or "participant_id" not in participants_df.columns:
        return []
    return [str(col) for col in participants_df.columns if str(col) != "participant_id"]


def _build_participant_export_frame(participants_df: Any) -> Any:
    """Build a one-row-per-participant frame for post-merge enrichment."""
    if participants_df is None:
        return None
    if "participant_id" not in participants_df.columns:
        return None

    export_cols = ["participant_id"] + _participant_export_columns(participants_df)
    if len(export_cols) <= 1:
        return None

    frame = participants_df.loc[:, [c for c in export_cols if c in participants_df.columns]].copy()
    if frame.empty:
        return None

    frame = frame.dropna(subset=["participant_id"]).drop_duplicates(
        subset=["participant_id"], keep="first"
    )
    return frame


def _participants_categorical_columns(participants_meta: dict) -> set[str]:
    """Return participant columns declared as categorical in participants.json."""
    categorical: set[str] = set()
    if not isinstance(participants_meta, dict):
        return categorical

    for col, meta in participants_meta.items():
        if not isinstance(meta, dict):
            continue
        variable_type = str(
            meta.get("VariableType") or meta.get("variable_type") or ""
        ).strip().lower()
        if variable_type in {"categorical", "nominal", "category"}:
            categorical.add(str(col))
    return categorical


def _participant_raw_exclude_columns(participants_df: Any) -> set[str]:
    """Columns to hide from raw survey export rows.

    Participant-level sociodemographic fields may be injected for scoring formulas,
    but they must never leak into survey output columns.
    """
    if participants_df is None:
        return set()
    return {str(col) for col in participants_df.columns if str(col) != "participant_id"}


def _resolve_recipe_scores(recipe: dict, resolved_version: str | None) -> list[dict]:
    """Resolve the active score block, accounting for VersionedScores."""
    versioned_scores = recipe.get("VersionedScores") or {}
    if resolved_version and resolved_version in versioned_scores:
        return versioned_scores[resolved_version] or []
    return recipe.get("Scores") or []


def _resolve_recipe_score_names(recipe: dict, resolved_version: str | None) -> set[str]:
    """Return score variable names for the active recipe/version."""
    names: set[str] = set()
    for score in _resolve_recipe_scores(recipe, resolved_version):
        name = str((score or {}).get("Name", "")).strip()
        if name:
            names.add(name)
    return names


def _merge_all_output_column_name(
    recipe_id: str,
    column: str,
    *,
    score_names: set[str],
    include_recipe_prefix: bool,
) -> str:
    """Pick a merge-all column name with score columns always recipe-prefixed."""
    col = str(column)
    if col in score_names:
        return _prefixed_recipe_column_name(recipe_id, col)
    if include_recipe_prefix:
        return _prefixed_recipe_column_name(recipe_id, col)
    return col


def _inject_participant_values_into_rows(
    rows: list[dict[str, str]], participant_values: dict[str, str]
) -> list[dict[str, str]]:
    """Return row copies with participant-level values filled where missing."""
    if not participant_values:
        return rows

    out_rows: list[dict[str, str]] = []
    for row in rows:
        merged = row.copy()
        for col, val in participant_values.items():
            if col not in merged or _is_missing_cell_value(merged.get(col)):
                merged[col] = val
        out_rows.append(merged)
    return out_rows


def _apply_survey_derivative_recipe_to_rows(
    recipe: dict,
    rows: list[dict[str, str]],
    include_raw: bool = False,
    resolved_version: str | None = None,
    raw_exclude_columns: set[str] | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    transforms = recipe.get("Transforms", {}) or {}
    invert_cfg = transforms.get("Invert") or {}
    invert_items = set(invert_cfg.get("Items") or [])
    invert_scale = invert_cfg.get("Scale") or {}
    invert_min = invert_scale.get("min")
    invert_max = invert_scale.get("max")
    # Per-item ranges override the global scale for each item
    item_scales: dict = invert_cfg.get("ItemScales") or {}

    # Support for Derived variables (e.g. best of trials)
    derived_cfg = transforms.get("Derived") or []

    # VersionedScores: if recipe defines per-variant score lists and a version is
    # resolved for this file, use that variant's scores; fall back to top-level Scores.
    scores = _resolve_recipe_scores(recipe, resolved_version)
    score_names = [
        str(s.get("Name", "")).strip() for s in scores if str(s.get("Name", "")).strip()
    ]

    out_header = []
    if include_raw and rows:
        excluded = {str(c) for c in (raw_exclude_columns or set())}
        # Include source columns except participant-level sociodemographics.
        out_header.extend([str(col) for col in rows[0].keys() if str(col) not in excluded])

    out_header.extend(score_names)
    out_rows: list[dict[str, str]] = []

    for row in rows:
        # We work on a copy to allow derived variables to be used in scores
        current_row = row.copy()

        # 1) Compute Derived variables first
        _calculate_derived_variables(
            derived_cfg, current_row, invert_items, invert_min, invert_max, item_scales
        )

        # 2) Compute Scores
        out = _calculate_scores(
            scores, current_row, invert_items, invert_min, invert_max, item_scales
        )

        if include_raw:
            # Merge original row with scores
            final_row = row.copy()
            final_row.update(out)
            out_rows.append(final_row)
        else:
            out_rows.append(out)

    return out_header, out_rows


def _write_recipes_dataset_description(
    *, out_root: Path, modality: str, prism_root: Path
) -> None:
    """Create a dataset_description.json under derivatives/<modality>/."""

    desc_path = out_root / "dataset_description.json"
    if desc_path.exists():
        return

    # Try to inherit some metadata from the root dataset_description.json
    root_desc_path = prism_root / "dataset_description.json"

    root_meta: dict = {}
    if root_desc_path.exists():
        try:
            root_meta = _read_json(root_desc_path)
        except Exception:
            pass

    modality_label = modality.capitalize()
    obj = {
        "Name": f"{root_meta.get('Name', 'PRISM')} {modality_label} Recipes",
        "BIDSVersion": "1.8.0",
        "DatasetType": "derivative",
        "GeneratedBy": [
            {
                "Name": "prism-tools",
                "Description": f"{modality_label} recipe scoring (reverse coding, subscales, formulas)",
                "Version": "1.0.0",
                "CodeURL": "https://github.com/MRI-Lab-Graz/prism-studio",
            }
        ],
        "SourceDatasets": [
            {
                "URL": "local",
                "DOI": root_meta.get("DatasetDOI", "n/a"),
            }
        ],
        "GeneratedOn": datetime.now().isoformat(timespec="seconds"),
    }

    # Copy relevant fields from root
    for field in ["Authors", "License", "HowToAcknowledge", "Funding"]:
        if field in root_meta:
            obj[field] = root_meta[field]

    _write_json(desc_path, obj)


def _generate_recipes_boilerplate_sections(
    applied_recipes: list[dict], lang: str = "en"
) -> list[str]:
    """Build text sections for the boilerplate."""
    sections = []

    # 1. General PRISM/BIDS Section
    if lang == "de":
        sections.append("## Datenstandardisierung und Validierung\n")
        sections.append(
            "Die Daten wurden nach dem PRISM-Standard (Psychological Research Information System Model) organisiert und validiert. "
            "Dieser Standard erweitert die Brain Imaging Data Structure (BIDS) auf die psychologische Forschung. "
            "Die Datenverarbeitung und Berechnung der Scores erfolgte automatisiert mit dem PRISM-System, "
            "wobei die in den JSON-Rezepten definierten Scoring-Logiken angewendet wurden.\n"
        )
    else:
        sections.append("## Data Standardization and Validation\n")
        sections.append(
            "Data were organized and validated according to the PRISM (Psychological Research Information System Model) "
            "standard, which extends the Brain Imaging Data Structure (BIDS) to psychological research. "
            "Data processing and score calculation were performed automatically using the PRISM system, "
            "applying the scoring logic defined in machine-readable JSON recipes.\n"
        )

    # 2. Psychological Assessments Section
    if lang == "de":
        sections.append("## Psychologische Testverfahren\n")
        sections.append(
            f"Insgesamt wurden {len(applied_recipes)} psychologische Instrumente ausgewertet. "
            "Für jedes Instrument wurden die Scoring-Prozeduren (Invertierung, Skalenbildung) in Rezept-Dateien dokumentiert."
        )
    else:
        sections.append("## Psychological Assessments\n")
        sections.append(
            f"A total of {len(applied_recipes)} psychological instruments were processed. "
            "For each instrument, scoring procedures including item inversions and subscale calculations "
            "were documented in machine-readable recipe files."
        )

    for recipe in applied_recipes:
        survey_info = recipe.get("Survey") or recipe.get("Study") or {}
        name = get_i18n_text(
            survey_info.get("Name")
            or survey_info.get("OriginalName")
            or survey_info.get("TaskName"),
            lang,
        )
        desc = get_i18n_text(survey_info.get("Description"), lang)
        refs = _pick_references(survey_info, lang)

        sections.append(f"\n### {name}\n")

        text_parts = []
        if desc:
            text_parts.append(desc)

        if refs["primary"]:
            if lang == "de":
                text_parts.append(f"Das Instrument basiert auf {refs['primary']}.")
            else:
                text_parts.append(f"The instrument is based on {refs['primary']}.")

        if refs["translation"]:
            if lang == "de":
                text_parts.append(
                    f"Die verwendete Übersetzung ist {refs['translation']}."
                )
            else:
                text_parts.append(f"The translation used is {refs['translation']}.")

        if text_parts:
            sections.append(" ".join(text_parts) + "\n")

        # Scoring details (brief)
        transforms = recipe.get("Transforms", {})
        invert = transforms.get("Invert", {})
        has_invert = invert and invert.get("Items")
        scores = recipe.get("Scores", [])

        if has_invert or scores:
            sections.append("**Scoring**:")
            if has_invert:
                if lang == "de":
                    sections.append(
                        "- Negative gepolte Items wurden for der Skalenbildung invertiert."
                    )
                else:
                    sections.append(
                        "- Negatively keyed items were reverse-coded prior to score calculation."
                    )

            for s in scores:
                s_name = s.get("Name")
                s_method = s.get("Method", "sum")
                s_items = s.get("Items", [])
                s_source = s.get("Source")

                method_desc = s_method
                if s_method == "sum":
                    method_desc = "sum score" if lang == "en" else "Summenwert"
                elif s_method == "mean":
                    method_desc = "mean score" if lang == "en" else "Mittelwert"
                elif s_method == "map":
                    method_desc = (
                        "categorical mapping"
                        if lang == "en"
                        else "kategorisierte Zuordnung"
                    )

                item_count = len(s_items)
                if item_count > 0:
                    if lang == "de":
                        sections.append(
                            f"- `{s_name}`: {method_desc} ({item_count} Items)."
                        )
                    else:
                        sections.append(
                            f"- `{s_name}`: {method_desc} ({item_count} items)."
                        )
                elif s_source:
                    if lang == "de":
                        sections.append(
                            f"- `{s_name}`: {method_desc} basierend auf `{s_source}`."
                        )
                    else:
                        sections.append(
                            f"- `{s_name}`: {method_desc} based on `{s_source}`."
                        )
                else:
                    sections.append(f"- `{s_name}`: {method_desc}.")
    return sections


def _generate_recipes_boilerplate_html(sections: list[str]) -> str:
    """Convert sections list to a standalone HTML string."""
    html_content = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        '<meta charset="utf-8">',
        "<style>",
        "body { font-family: sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }",
        "h2 { color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px; margin-top: 40px; }",
        "h3 { color: #16a085; margin-top: 30px; }",
        "code { background: #f4f4f4; padding: 2px 4px; border-radius: 4px; font-family: monospace; }",
        "ul { padding-left: 20px; margin-bottom: 15px; }",
        "li { margin-bottom: 5px; }",
        "p { margin-bottom: 15px; }",
        "</style>",
        "</head>",
        "<body>",
    ]

    in_list = False
    for line in sections:
        line = line.strip()
        if not line:
            continue

        if line.startswith("- "):
            if not in_list:
                html_content.append("<ul>")
                in_list = True

            li_text = line[2:]
            while "`" in li_text:
                li_text = li_text.replace("`", "<code>", 1).replace("`", "</code>", 1)
            html_content.append(f"  <li>{li_text}</li>")
            continue

        # If we were in a list and the line doesn't start with "- ", close the list
        if in_list:
            html_content.append("</ul>")
            in_list = False

        if line.startswith("## "):
            html_content.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            html_content.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("**"):
            bold_text = line.replace("**", "").strip().strip(":")
            html_content.append(f"<p><strong>{bold_text}:</strong></p>")
        else:
            p_text = line
            while "`" in p_text:
                p_text = p_text.replace("`", "<code>", 1).replace("`", "</code>", 1)
            html_content.append(f"<p>{p_text}</p>")

    if in_list:
        html_content.append("</ul>")

    html_content.extend(["</body>", "</html>"])
    return "\n".join(html_content)


def _generate_recipes_boilerplate(
    applied_recipes: list[dict], out_path: Path, lang: str = "en"
) -> None:
    """Generate a formal methods section boilerplate based on applied recipes (MD and HTML)."""
    sections = _generate_recipes_boilerplate_sections(applied_recipes, lang)

    # Write Markdown
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sections))

    # Write HTML
    html_path = out_path.with_suffix(".html")
    html_string = _generate_recipes_boilerplate_html(sections)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_string)


def _load_and_validate_recipes(
    repo_root: Path,
    modality: str,
    survey_ids: str | None = None,
    recipe_dir: str | Path | None = None,
    prism_root: Path | None = None,
    allow_empty_recipes: bool = False,
) -> tuple[dict[str, dict], Path | None]:
    """Locate, load and validate recipe JSON files.

    Discovery order when recipe_dir is not specified:
      1. <prism_root>/code/recipes/<modality>/   (project YODA, preferred)
      2. <prism_root>/recipe/<modality>/          (project legacy)
      3. <repo_root>/code/recipes/<modality>/     (repo-level YODA)
      4. <repo_root>/recipe/<modality>/            (repo-level legacy)
      5. <repo_root>/official/recipes/<modality>/ (official, plural)
      6. <repo_root>/official/recipe/<modality>/  (official, singular)
    """
    if recipe_dir:
        recipes_dir = Path(recipe_dir).resolve()

        # Smart detection: if the provided dir has no JSONs but has modality subfolders, descend.
        # This helps if the user selects the top-level 'recipes' folder of a project.
        if recipes_dir.is_dir() and not list(recipes_dir.glob(RECIPE_FILENAME_GLOB)):
            if modality == "survey":
                if (recipes_dir / "survey").is_dir():
                    recipes_dir = recipes_dir / "survey"
                elif (recipes_dir / "surveys").is_dir():
                    recipes_dir = recipes_dir / "surveys"
            elif modality == "biometrics":
                if (recipes_dir / "biometric").is_dir():
                    recipes_dir = recipes_dir / "biometric"
                elif (recipes_dir / "biometrics").is_dir():
                    recipes_dir = recipes_dir / "biometrics"

        expected = str(recipes_dir / RECIPE_FILENAME_GLOB)
    elif modality == "survey":
        recipes_dir = None

        # 1. Project-level YODA (prism_root takes priority over repo_root)
        if prism_root and prism_root.resolve() != repo_root.resolve():
            candidate = (prism_root / "code" / "recipes" / "survey").resolve()
            if candidate.exists():
                recipes_dir = candidate
            else:
                candidate = (prism_root / "recipe" / "survey").resolve()
                if candidate.exists():
                    recipes_dir = candidate

        # 2. Repo-root chain: YODA → legacy → official (plural then singular)
        if recipes_dir is None:
            recipes_dir = (repo_root / "code" / "recipes" / "survey").resolve()
        if not recipes_dir.exists():
            recipes_dir = (repo_root / "recipe" / "survey").resolve()
        if not recipes_dir.exists():
            recipes_dir = (repo_root / "official" / "recipes" / "survey").resolve()
        if not recipes_dir.exists():
            recipes_dir = (repo_root / "official" / "recipe" / "survey").resolve()

        expected = (
            "code/recipes/survey/recipe-*.json (or legacy recipe/survey/recipe-*.json "
            "or official/recipe/survey/recipe-*.json)"
        )
    elif modality == "biometrics":
        recipes_dir = None

        # 1. Project-level YODA
        if prism_root and prism_root.resolve() != repo_root.resolve():
            candidate = (prism_root / "code" / "recipes" / "biometrics").resolve()
            if candidate.exists():
                recipes_dir = candidate
            else:
                candidate = (prism_root / "recipe" / "biometrics").resolve()
                if candidate.exists():
                    recipes_dir = candidate

        # 2. Repo-root chain: YODA → legacy → official (plural then singular)
        if recipes_dir is None:
            recipes_dir = (repo_root / "code" / "recipes" / "biometrics").resolve()
        if not recipes_dir.exists():
            recipes_dir = (repo_root / "recipe" / "biometrics").resolve()
        if not recipes_dir.exists():
            recipes_dir = (repo_root / "official" / "recipes" / "biometrics").resolve()
        if not recipes_dir.exists():
            recipes_dir = (repo_root / "official" / "recipe" / "biometrics").resolve()

        expected = (
            "code/recipes/biometrics/recipe-*.json (or legacy recipe/biometrics/recipe-*.json "
            "or official/recipe/biometrics/recipe-*.json)"
        )
    else:
        raise ValueError("modality must be one of: survey, biometrics")

    assert recipes_dir is not None, "recipes_dir must be assigned by this point"
    if not recipes_dir.exists() or not recipes_dir.is_dir():
        raise ValueError(f"Missing recipe folder: {recipes_dir}. Expected {expected}")

    recipe_paths = sorted(recipes_dir.glob(RECIPE_FILENAME_GLOB))
    if not recipe_paths:
        if allow_empty_recipes:
            return {}, recipes_dir
        raise ValueError(
            f"No derivative recipes found in: {recipes_dir}. Expected {RECIPE_FILENAME_GLOB}"
        )

    all_recipes: dict[str, dict] = {}
    for p in recipe_paths:
        try:
            recipe_json = _read_json(p)
            recipe_id = _normalize_survey_key(p.stem)
            all_recipes[recipe_id] = {"path": p, "json": recipe_json}
        except Exception:
            continue

    if not all_recipes:
        raise ValueError("No valid recipes could be loaded.")

    # Validate recipe structure before executing.
    try:
        from .recipe_validation import validate_recipe
    except (ImportError, ValueError):
        try:
            from recipe_validation import validate_recipe
        except ImportError:
            validate_recipe = None

    if validate_recipe is not None:
        recipe_errors: list[str] = []
        for recipe_id, rec in sorted(all_recipes.items()):
            errs = validate_recipe(rec.get("json") or {}, recipe_id=recipe_id)
            rec_path = rec.get("path")
            rec_name = rec_path.name if isinstance(rec_path, Path) else str(recipe_id)
            recipe_errors.extend([f"{rec_name}: {e}" for e in errs])

        if recipe_errors:
            raise ValueError(
                "Invalid derivative recipe(s):\n- " + "\n- ".join(recipe_errors)
            )

    if not survey_ids:
        return all_recipes, recipes_dir

    # Filter by selected IDs
    requested = [p.strip() for p in str(survey_ids).replace(";", ",").split(",")]
    requested = [_normalize_survey_key(p) for p in requested if p.strip()]
    selected_set = set([p for p in requested if p])

    unknown = sorted([s for s in selected_set if s not in all_recipes])
    if unknown:
        raise ValueError(
            f"Unknown {modality} recipe names: "
            + ", ".join(unknown)
            + ". Available: "
            + ", ".join(sorted(all_recipes.keys()))
        )

    return {k: v for k, v in all_recipes.items() if k in selected_set}, recipes_dir


def _find_tsv_files(prism_root: Path, modality: str) -> list[Path]:
    """Scan dataset for TSV files based on modality."""
    search_roots = [prism_root]

    tsv_files: list[Path] = []
    for root in search_roots:
        if modality == "survey":
            # Search in survey/ and beh/ (BIDS standard)
            for folder in ("survey", "beh"):
                tsv_files.extend(root.glob(f"sub-*/ses-*/{folder}/*.tsv"))
                tsv_files.extend(root.glob(f"sub-*/{folder}/*.tsv"))
        elif modality == "biometrics":
            tsv_files.extend(root.glob("sub-*/ses-*/biometrics/*.tsv"))
            tsv_files.extend(root.glob("sub-*/biometrics/*.tsv"))
        else:
            # Fallback: search both
            tsv_files.extend(root.glob("sub-*/ses-*/*/*.tsv"))
            tsv_files.extend(root.glob("sub-*/*/*.tsv"))

    return sorted(set([p for p in tsv_files if p.is_file()]))


def _load_participants_data(prism_root: Path) -> tuple[Any, dict]:
    """Load participants.tsv (as DataFrame) and participants.json (as dict)."""
    participants_df = None
    participants_json_meta = {}

    participants_tsv = prism_root / "participants.tsv"
    participants_json = prism_root / "participants.json"

    if participants_tsv.is_file():
        try:
            import pandas as pd

            df = pd.read_csv(participants_tsv, sep="\t", dtype=str)
            if "participant_id" in df.columns:
                df["participant_id"] = (
                    df["participant_id"]
                    .map(_normalize_participant_id_for_join)
                    .astype("string")
                )
                df = df[df["participant_id"].notna()].copy()
                participants_df = df
        except Exception:
            pass

    if participants_json.is_file():
        try:
            participants_json_meta = _read_json(participants_json)
        except Exception:
            pass

    return participants_df, participants_json_meta


def _handle_wide_pivot(
    df: Any, out_header: list[str]
) -> tuple[Any, list[str], str | None]:
    """Pivot a long-format DataFrame to wide-format.

    When multiple run values are present, the composite key 'session_run' is
    used so that columns such as ``total_score_ses-1_run-01`` are produced.
    """
    import pandas as pd

    try:
        valid_sessions = (
            _distinct_export_context_values(df["session"])
            if "session" in df.columns
            else []
        )
        valid_runs = (
            _distinct_export_context_values(df["run"])
            if "run" in df.columns
            else []
        )

        include_session = len(valid_sessions) > 1
        include_run = "run" in df.columns and len(valid_runs) > 1

        df = df.copy()
        if include_session and include_run:
            df["_pivot_key"] = (
                df["session"].astype(str) + "_" + df["run"].fillna("").astype(str)
            ).str.rstrip("_")
        elif include_session:
            df["_pivot_key"] = df["session"].astype(str)
        elif include_run:
            df["_pivot_key"] = df["run"].fillna("").astype(str)
        else:
            df["_pivot_key"] = ""

        pivot_col = "_pivot_key"

        # Pivot the score columns
        df_wide = df.pivot(index="participant_id", columns=pivot_col, values=out_header)
        # Flatten multi-index columns: "total_score_ses-1", "total_score_run-01",
        # or "total_score_ses-1_run-01" depending on the exported context.
        if isinstance(df_wide.columns, pd.MultiIndex):
            df_wide.columns = [
                val if not key else f"{val}_{key}" for val, key in df_wide.columns
            ]
        else:
            df_wide.columns = [
                out_header[0] if not key else f"{out_header[0]}_{key}"
                for key in df_wide.columns
            ]

        df = df_wide.reset_index().fillna("n/a")
        # Update out_header to reflect new columns for metadata building
        new_header = [c for c in df.columns if c != "participant_id"]
        return df, new_header, None
    except Exception as e:
        return df, out_header, f"Could not create wide layout: {e}"


def _normalize_sessions(sessions: str | list[str] | None) -> list[str] | None:
    """Normalize user-provided sessions to ['ses-<id>', ...] or None for all."""
    if sessions is None:
        return None
    if isinstance(sessions, list):
        raw = sessions
    else:
        raw = [s for s in str(sessions).replace(";", ",").split(",")]

    cleaned: list[str] = []
    for s in raw:
        token = str(s).strip()
        if not token:
            continue
        if token.lower() == "all":
            return None
        if not token.startswith("ses-"):
            token = f"ses-{token}"
        cleaned.append(token)

    if not cleaned:
        return None
    return sorted(set(cleaned))


def _filter_tsv_files_by_sessions(
    tsv_files: list[Path], sessions: list[str] | None
) -> list[Path]:
    if not sessions:
        return tsv_files
    selected = set(sessions)
    filtered: list[Path] = []
    for p in tsv_files:
        _sub_id, ses_id = _infer_sub_ses_from_path(p)
        if not ses_id:
            ses_id = "ses-1"
        if ses_id in selected:
            filtered.append(p)
    return filtered


def _make_project_prefix(prism_root: Path) -> str:
    """Return a slugified project-name prefix (e.g. 'mystudy_') or '' if unavailable."""
    try:
        meta = _read_json(prism_root / "dataset_description.json")
        name = str(meta.get("Name", "")).strip()
        if name:
            slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:30].rstrip("_")
            if slug:
                return f"{slug}_"
    except Exception:
        pass
    return ""


def _export_recipe_aggregated(
    recipe_id: str,
    recipe: dict,
    matching: list[Path],
    out_root: Path,
    out_format: str,
    modality: str,
    lang: str,
    layout: str,
    include_raw: bool,
    participants_df: Optional[Any],
    participants_meta: dict,
    output_prism_root: Path,
    survey_task: str,
    selected_sessions: list[str] | None,
    missing_policy: str,
    missing_numeric_value: float | None,
) -> tuple[int, int, Path | None, str | None, list[str]]:
    """Process all files for one recipe and write a single aggregated output file."""
    import pandas as pd

    rows_accum: list[dict[str, Any]] = []
    processed_count = 0
    final_header = []
    participant_lookup = _build_participant_value_lookup(participants_df)
    participant_columns = _participant_export_columns(participants_df)
    raw_exclude_columns = _participant_raw_exclude_columns(participants_df)

    for in_path in matching:
        processed_count += 1
        sub_id, ses_id = _infer_sub_ses_from_path(in_path)
        if not sub_id:
            continue
        sub_id = _normalize_participant_id_for_join(sub_id)
        if not sub_id:
            continue
        if not ses_id:
            ses_id = "ses-1"
        run_id = _infer_run_from_path(in_path)

        in_header, in_rows = _read_tsv_rows(in_path)
        if not in_header or not in_rows:
            continue

        participant_key = _participant_join_key(sub_id)
        participant_values = (
            participant_lookup.get(participant_key, {}) if participant_key else {}
        )
        scoring_rows = _inject_participant_values_into_rows(in_rows, participant_values)

        resolved_ver = _resolve_variant_for_path(
            output_prism_root,
            survey_task,
            in_path,
            modality=modality,
        )
        out_header, out_rows = _apply_survey_derivative_recipe_to_rows(
            recipe,
            scoring_rows,
            include_raw=include_raw,
            resolved_version=resolved_ver,
            raw_exclude_columns=raw_exclude_columns,
        )
        if not out_header:
            continue

        final_header = out_header  # Keep track of last valid header
        for row_index, score_row in enumerate(out_rows):
            merged: dict[str, Any] = {"participant_id": sub_id, "session": ses_id}
            if run_id is not None:
                merged["run"] = run_id
            for participant_col in participant_columns:
                merged[participant_col] = participant_values.get(participant_col, "n/a")
            for col in out_header:
                merged[col] = score_row.get(col, "n/a")
            rows_accum.append(merged)

    if not rows_accum:
        return processed_count, 0, None, None, []

    df = pd.DataFrame(rows_accum)
    # Ensure column order: participant_id, session, [run], participant columns, then score columns
    _run_col = ["run"] if "run" in df.columns else []
    ordered_participant_cols = [c for c in participant_columns if c in df.columns]
    cols = [
        c
        for c in (
            ["participant_id", "session"]
            + _run_col
            + ordered_participant_cols
            + [c for c in final_header]
        )
        if c in df.columns
    ]
    df = df.loc[:, cols]

    fallback_note = None
    if layout == "wide":
        df, final_header, fallback_note = _handle_wide_pivot(df, final_header)

    # Detect columns with all missing values (excluding ids)
    nan_cols = []
    try:
        df_nan = df.replace("n/a", pd.NA)
        nan_cols = [
            c
            for c in df_nan.columns
            if c not in {"participant_id", "session", "run"} and df_nan[c].isna().all()
        ]
    except Exception:
        pass

    # Metadata building
    sidecar_meta = _get_sidecar_for_task(output_prism_root, modality, survey_task)
    var_labels, val_labels, score_details = _build_variable_metadata(
        list(df.columns),
        participants_meta,
        recipe,
        sidecar_meta=sidecar_meta,
        lang=lang,
    )
    survey_meta = _build_survey_metadata(recipe, lang=lang)

    prefix = _make_project_prefix(output_prism_root)
    out_fname: Path | None = None
    _ensure_dir(out_root)
    df_for_write = _apply_missing_export_policy(
        df,
        missing_policy=missing_policy,
        missing_numeric_value=missing_numeric_value,
    )

    if out_format == "csv":
        out_fname = out_root / f"{prefix}{recipe_id}.csv"
        df_for_write.to_csv(out_fname, index=False)
        _write_codebook_json(
            out_root / f"{prefix}{recipe_id}_codebook.json",
            var_labels,
            val_labels,
            score_details,
            survey_meta,
        )
        _write_codebook_tsv(
            out_root / f"{prefix}{recipe_id}_codebook.tsv",
            var_labels,
            val_labels,
            score_details,
        )
        _write_jamovi_r_helper(
            out_root / f"{prefix}{recipe_id}_jamovi_helper.R",
            f"{prefix}{recipe_id}.csv",
            var_labels,
            val_labels,
        )
    elif out_format == "xlsx":
        out_fname = out_root / f"{prefix}{recipe_id}.xlsx"
        try:
            with pd.ExcelWriter(out_fname, engine="openpyxl") as writer:
                df_for_write.to_excel(writer, sheet_name="Data", index=False)
                # Codebook sheet
                cb_rows = []
                for var in df_for_write.columns:
                    v_labels = val_labels.get(var, {})
                    v_str = (
                        "; ".join(
                            f"{k}={v}"
                            for k, v in sorted(
                                v_labels.items(), key=lambda x: str(x[0])
                            )
                        )
                        if v_labels
                        else ""
                    )
                    det_str = ""
                    if var in score_details:
                        d = score_details[var]
                        parts = []
                        if d.get("method"):
                            parts.append(f"method={d['method']}")
                        if d.get("items"):
                            parts.append(f"items={'+'.join(d['items'])}")
                        if d.get("range"):
                            r = d["range"]
                            parts.append(
                                f"range={r.get('min', '?')}-{r.get('max', '?')}"
                            )
                        det_str = "; ".join(parts)
                    cb_rows.append(
                        {
                            "variable": var,
                            "label": var_labels.get(var, ""),
                            "values": v_str,
                            "score_details": det_str,
                        }
                    )
                pd.DataFrame(cb_rows).to_excel(
                    writer, sheet_name="Codebook", index=False
                )
                if survey_meta:
                    s_rows = [
                        {"property": k, "value": str(v)} for k, v in survey_meta.items()
                    ]
                    pd.DataFrame(s_rows).to_excel(
                        writer, sheet_name="Survey Info", index=False
                    )
        except Exception:
            df_for_write.to_excel(out_fname, index=False)
    elif out_format == "sav":
        out_fname = out_root / f"{prefix}{recipe_id}.sav"
        codebook_json_path = out_root / f"{prefix}{recipe_id}_codebook.json"
        codebook_tsv_path = out_root / f"{prefix}{recipe_id}_codebook.tsv"
        try:
            import pyreadstat

            participant_categorical_cols = _participants_categorical_columns(participants_meta)
            df_for_sav = _prepare_dataframe_for_sav(df_for_write)
            for participant_col in participant_categorical_cols:
                if participant_col in df_for_sav.columns:
                    df_for_sav[participant_col] = df_for_sav[participant_col].astype("string")
            df_for_sav = _coerce_value_labeled_columns_for_sav(
                df_for_sav,
                val_labels,
                skip_numeric_coercion_columns=participant_categorical_cols,
            )

            # Sanitize SPSS variable names (illegal chars + leading digit names).
            spss_rename_map = _build_spss_rename_map(df_for_sav.columns)
            if spss_rename_map:
                df_for_sav = df_for_sav.rename(columns=spss_rename_map)

            # Update var_labels and val_labels keys to use sanitized names
            sav_var_labels: dict[str, str] = {}
            for col, label in var_labels.items():
                new_col = spss_rename_map.get(col, col)
                sav_var_labels[new_col] = label

            sav_val_labels = _build_sav_value_labels(
                df=df_for_sav,
                value_labels=val_labels,
                rename_map=spss_rename_map,
            )

            sav_variable_measure = _build_sav_variable_measure(
                list(df_for_write.columns),
                participants_meta=participants_meta,
            )
            sav_variable_measure = {
                spss_rename_map.get(col, col): measure
                for col, measure in sav_variable_measure.items()
            }

            pyreadstat.write_sav(
                df_for_sav,
                str(out_fname),
                column_labels=sav_var_labels if sav_var_labels else None,
                variable_value_labels=sav_val_labels if sav_val_labels else None,
                variable_measure=sav_variable_measure if sav_variable_measure else None,
            )
            _write_codebook_json(
                codebook_json_path,
                var_labels,
                val_labels,
                score_details,
                survey_meta,
            )
            _write_codebook_tsv(
                codebook_tsv_path,
                var_labels,
                val_labels,
                score_details,
            )
        except Exception as e:
            # Clean up potential 0-byte .sav file left by failed write
            if out_fname.exists() and out_fname.stat().st_size == 0:
                out_fname.unlink()
            out_fname = out_root / f"{prefix}{recipe_id}.csv"
            df_for_write.to_csv(out_fname, index=False)
            _write_codebook_json(
                codebook_json_path,
                var_labels,
                val_labels,
                score_details,
                survey_meta,
            )
            _write_codebook_tsv(
                codebook_tsv_path,
                var_labels,
                val_labels,
                score_details,
            )
            fallback_note = f"SPSS export failed ({e}); wrote CSV instead"
    return processed_count, 1, out_fname, fallback_note, nan_cols


def _export_recipe_legacy(
    recipe_id: str,
    recipe: dict,
    matching: list[Path],
    out_root: Path,
    out_format: str,
    modality: str,
    include_raw: bool,
    flat_rows: list[dict],
    flat_key_to_idx: dict[tuple, int],
    participants_df: Optional[Any] = None,
    output_prism_root: Path | None = None,
) -> tuple[int, int]:
    """Process all files for one recipe using legacy (PRISM/Flat) per-file logic."""
    processed_count = 0
    written_count = 0
    participant_lookup = _build_participant_value_lookup(participants_df)
    raw_exclude_columns = _participant_raw_exclude_columns(participants_df)

    # Extract task name for version resolution
    task_key = "BiometricName" if modality == "biometrics" else "TaskName"
    info_key = "Biometrics" if modality == "biometrics" else "Survey"
    survey_task = _normalize_survey_key(
        (recipe.get(info_key, {}) or {}).get(task_key) or recipe_id
    )

    for in_path in matching:
        processed_count += 1
        sub_id, ses_id = _infer_sub_ses_from_path(in_path)
        if not sub_id:
            continue
        sub_id = _normalize_participant_id_for_join(sub_id)
        if not sub_id:
            continue
        if not ses_id:
            ses_id = "ses-1"
        run_id = _infer_run_from_path(in_path)

        in_header, in_rows = _read_tsv_rows(in_path)
        if not in_header or not in_rows:
            continue

        participant_key = _participant_join_key(sub_id)
        participant_values = (
            participant_lookup.get(participant_key, {}) if participant_key else {}
        )
        scoring_rows = _inject_participant_values_into_rows(in_rows, participant_values)

        resolved_ver = (
            _resolve_variant_for_path(
                output_prism_root,
                survey_task,
                in_path,
                modality=modality,
            )
            if output_prism_root is not None
            else None
        )
        out_header, out_rows = _apply_survey_derivative_recipe_to_rows(
            recipe,
            scoring_rows,
            include_raw=include_raw,
            resolved_version=resolved_ver,
            raw_exclude_columns=raw_exclude_columns,
        )
        if not out_header:
            break

        if out_format == "flat":
            prefix_lower = recipe_id.lower()
            for row_index, score_row in enumerate(out_rows):
                key = (sub_id, ses_id, run_id, recipe_id, row_index)
                if key in flat_key_to_idx:
                    merged = flat_rows[flat_key_to_idx[key]]
                else:
                    merged = {
                        "participant_id": sub_id,
                        "session": ses_id,
                        "survey": recipe_id,
                    }
                    if run_id is not None:
                        merged["run"] = run_id
                    flat_key_to_idx[key] = len(flat_rows)
                    flat_rows.append(merged)

                for col in out_header:
                    # Only add prefix if column doesn't already start with recipe_id
                    # (e.g., avoid "ads_ADS01" when "ADS01" already has the prefix)
                    col_lower = col.lower()
                    if col_lower.startswith(prefix_lower):
                        prefixed_col = col  # Already has prefix
                    else:
                        prefixed_col = f"{recipe_id}_{col}"
                    merged[prefixed_col] = score_row.get(col, "n/a")
            written_count += 1
        else:
            # PRISM format: sub-*/ses-*/survey/*.tsv
            out_dir = out_root / recipe_id / sub_id / ses_id / modality
            stem = in_path.stem
            base_stem, _in_suffix = _strip_suffix(stem)
            new_stem = f"{base_stem}_desc-scores_{modality}"
            out_path = out_dir / f"{new_stem}.tsv"
            _write_tsv_rows(out_path, out_header, out_rows)
            written_count += 1

    return processed_count, written_count


def _finalize_flat_output(
    flat_rows: list[dict],
    modality: str,
    layout: str,
    output_prism_root: Path,
    fallback_note: str | None,
) -> tuple[Path, str | None, list[str]]:
    """Assemble the global flat_rows into a single TSV file (long or wide)."""
    import pandas as pd

    has_run = any("run" in r for r in flat_rows)
    fixed_set = {"participant_id", "session", modality, "run"}
    fixed = ["participant_id", "session"] + (["run"] if has_run else []) + [modality]
    score_cols = sorted({k for r in flat_rows for k in r.keys() if k not in fixed_set})
    out_root = (
        output_prism_root
        / "derivatives"
        / ("survey" if modality == "survey" else "biometrics")
    )
    prefix = _make_project_prefix(output_prism_root)
    flat_out_path = out_root / f"{prefix}{modality}_scores.tsv"

    if layout == "wide":
        try:
            df_flat = pd.DataFrame(flat_rows)
            # Melt and Pivot to handle session-specific columns
            _run_id_vars = ["run"] if has_run else []
            id_vars = ["participant_id", "session"] + _run_id_vars + ["survey"]
            df_melt = df_flat.melt(id_vars=id_vars, value_vars=score_cols).dropna()
            if has_run:
                df_melt["col_name"] = (
                    df_melt["variable"]
                    + "_"
                    + df_melt["session"]
                    + "_"
                    + df_melt["run"].fillna("").astype(str)
                ).str.rstrip("_")
            else:
                df_melt["col_name"] = df_melt["variable"] + "_" + df_melt["session"]

            df_wide = df_melt.pivot(
                index="participant_id", columns="col_name", values="value"
            )
            df_flat = df_wide.reset_index().fillna("n/a")

            flat_header = ["participant_id"] + sorted(
                [c for c in df_flat.columns if c != "participant_id"]
            )
            final_rows = df_flat.to_dict("records")
        except Exception as e:
            if fallback_note is None:
                fallback_note = f"Could not create wide flat layout: {e}"
            flat_header = fixed + score_cols
            final_rows = flat_rows
    else:
        flat_header = fixed + score_cols
        final_rows = flat_rows

    _write_tsv_rows(flat_out_path, flat_header, final_rows)

    # Detect all-NA columns for report
    nan_cols = []
    try:
        df_chk = pd.DataFrame(final_rows).replace("n/a", pd.NA)
        ignore_cols = {"participant_id", "session", modality, "survey"}
        nan_cols = [
            c for c in df_chk.columns if c not in ignore_cols and df_chk[c].isna().all()
        ]
    except Exception:
        pass

    return flat_out_path, fallback_note, nan_cols


def _resolve_variant_for_path(
    prism_root: Path,
    task_name: str,
    in_path: Path,
    *,
    modality: str = "survey",
) -> str | None:
    """Resolve variant from filename acq, then from template Study.Version."""
    acq_value = _extract_acq_from_filename(in_path)
    if acq_value:
        return acq_value

    if prism_root and task_name:
        metadata = _get_sidecar_for_task(prism_root, modality, task_name)
        if isinstance(metadata, dict):
            study = metadata.get("Study", {})
            if isinstance(study, dict):
                version = study.get("Version")
                if version:
                    return str(version)
    return None


def compute_survey_recipes(
    *,
    prism_root: str | Path,
    repo_root: str | Path,
    recipe_dir: str | Path | None = None,
    survey: str | None = None,
    sessions: str | list[str] | None = None,
    out_format: str = "flat",
    modality: str = "survey",
    lang: str = "en",
    layout: str = "long",
    include_raw: bool = False,
    boilerplate: bool = False,
    merge_all: bool = False,
    include_recipe_prefix: bool = True,
    anonymized: bool = False,
    missing_policy: str = "system-missing",
    missing_numeric_value: float | None = None,
) -> SurveyRecipesResult:
    """Compute survey scores in a PRISM dataset using recipes.

    Args:
            prism_root: Target PRISM dataset root (must exist).
            repo_root: Repository root (used to locate recipe JSONs).
            recipe_dir: Optional custom folder containing recipe JSONs.
            survey: Optional comma-separated recipe ids to apply.
            sessions: Optional comma-separated session ids (e.g., "ses-1,ses-2").
            out_format: "flat" (default), "prism", "csv", "xlsx", "sav".
            lang: Language for metadata labels (e.g., "en", "de").
            layout: "long" (default) or "wide" for repeated measures.
            include_raw: If True, include original columns in the output.
            boilerplate: If True, generate a methods boilerplate.
            merge_all: If True, combine all surveys into one output file.
            include_recipe_prefix: If True, prefix combined-export columns with the
                recipe name when possible.
            anonymized: If True, append '_anon' to output subfolder name.
            missing_policy: Missing-value export policy for csv/xlsx/sav
                (system-missing, text-na, text-nan, numeric-sentinel).
            missing_numeric_value: Numeric sentinel used when policy is
                ``numeric-sentinel``.

    Raises:
            ValueError: For user errors (missing paths, unknown recipes, etc.).
            RuntimeError: For unexpected failures.
    """

    prism_root = Path(prism_root).resolve()
    repo_root = Path(repo_root).resolve()

    if not prism_root.exists() or not prism_root.is_dir():
        raise ValueError(f"--prism is not a directory: {prism_root}")

    # output root is always the prism root
    output_prism_root = prism_root

    modality = str(modality or "survey").strip().lower()
    out_format = _normalize_output_format(out_format or "prism")
    final_format = out_format

    if out_format not in {"prism", "flat", "csv", "xlsx", "sav"}:
        raise ValueError("--format must be one of: prism, flat, csv, xlsx, sav")

    layout = str(layout or "long").strip().lower()
    if layout not in {"long", "wide"}:
        raise ValueError("--layout must be one of: long, wide")

    missing_policy = str(missing_policy or "system-missing").strip().lower()
    if missing_policy not in {"system-missing", "text-na", "text-nan", "numeric-sentinel"}:
        raise ValueError(
            "missing_policy must be one of: system-missing, text-na, text-nan, numeric-sentinel"
        )
    if missing_policy == "numeric-sentinel" and missing_numeric_value is None:
        raise ValueError(
            "missing_numeric_value is required when missing_policy is numeric-sentinel"
        )

    # 1. Scan dataset for TSV files based on modality
    tsv_files = _find_tsv_files(prism_root, modality)
    selected_sessions = _normalize_sessions(sessions)
    if selected_sessions:
        tsv_files = _filter_tsv_files_by_sessions(tsv_files, selected_sessions)
    if not tsv_files:
        if selected_sessions:
            raise ValueError(
                f"No {modality} TSV files found for sessions {', '.join(selected_sessions)} under: {prism_root}"
            )
        raise ValueError(f"No {modality} TSV files found under: {prism_root}")

    observed_task_ids = {
        task for task in (_extract_task_from_survey_filename(p) for p in tsv_files) if task
    }

    # 2. Load and validate recipes — project first, official fallback
    allow_empty_recipes = bool(include_raw and modality == "survey" and not survey)
    recipes, _loaded_recipes_dir = _load_and_validate_recipes(
        repo_root,
        modality,
        survey,
        recipe_dir=recipe_dir,
        prism_root=prism_root,
        allow_empty_recipes=allow_empty_recipes,
    )

    # 3. Load participants data (for merging demographic data)
    participants_df, participants_meta = _load_participants_data(output_prism_root)

    # Build config-based subfolder: {layout}_{lang} or {layout}_{lang}_anon
    subfolder_name = f"{layout}_{lang}"
    if anonymized:
        subfolder_name += "_anon"

    # Output scores into BIDS derivatives folders; recipes remain the instruction set in the repo.
    out_root = (
        output_prism_root
        / "derivatives"
        / ("survey" if modality == "survey" else "biometrics")
        / subfolder_name
    )
    flat_rows: list[dict] = []
    flat_key_to_idx: dict[tuple, int] = {}
    nan_report: dict[str, list[str]] = {}
    applied_recipes_list: list[dict] = []
    boilerplate_path: Path | None = None
    boilerplate_html_path: Path | None = None

    processed_files = 0
    written_files = 0
    applied_recipe_ids: set[str] = set()
    written_recipe_ids: set[str] = set()
    raw_only_tasks: set[str] = set()
    matched_task_ids: set[str] = set()

    flat_out_path: Path | None = None
    fallback_note: str | None = None

    # For merge_all mode, collect per-recipe frames and merge them once at the end.
    merge_all_frames: list[tuple[str, Any]] = []
    merge_all_recipe_by_id: dict[str, dict] = {}

    # If modality=survey/biometrics we will write one flat file per survey/biometric (recipe)
    for recipe_id, rec in sorted(recipes.items()):
        recipe = rec["json"]
        # For biometrics, we might use BiometricName instead of TaskName
        task_key = "BiometricName" if modality == "biometrics" else "TaskName"
        info_key = "Biometrics" if modality == "biometrics" else "Survey"

        survey_info = recipe.get(info_key, {}) or {}
        survey_task = _normalize_survey_key(survey_info.get(task_key) or recipe_id)
        survey_acq = _normalize_survey_key(
            survey_info.get("Acq") or survey_info.get("Version") or ""
        )
        survey_key = f"{survey_task}_acq-{survey_acq}" if survey_acq else survey_task

        matching = []
        for p in tsv_files:
            task = _extract_task_from_survey_filename(p)
            if (survey_acq and task == survey_key) or (
                not survey_acq and _strip_acq_from_task(task) == survey_task
            ):
                matching.append(p)
                if task:
                    matched_task_ids.add(task)
        if not matching:
            continue

        applied_recipe_ids.add(recipe_id)
        applied_recipes_list.append(recipe)

        if out_format in ("csv", "xlsx", "sav"):
            if merge_all:
                import pandas as pd

                rows_accum: list[dict[str, Any]] = []
                participant_lookup = _build_participant_value_lookup(participants_df)
                raw_exclude_columns = _participant_raw_exclude_columns(participants_df)

                for in_path in matching:
                    processed_files += 1
                    sub_id, ses_id = _infer_sub_ses_from_path(in_path)
                    if not sub_id:
                        continue
                    sub_id = _normalize_participant_id_for_join(sub_id)
                    if not sub_id:
                        continue
                    if not ses_id:
                        ses_id = "ses-1"
                    run_id = _infer_run_from_path(in_path)

                    in_header, in_rows = _read_tsv_rows(in_path)
                    if not in_header or not in_rows:
                        continue

                    participant_key = _participant_join_key(sub_id)
                    participant_values = (
                        participant_lookup.get(participant_key, {})
                        if participant_key
                        else {}
                    )
                    scoring_rows = _inject_participant_values_into_rows(
                        in_rows, participant_values
                    )

                    resolved_ver = _resolve_variant_for_path(
                        output_prism_root,
                        survey_task,
                        in_path,
                        modality=modality,
                    )
                    out_header, out_rows = _apply_survey_derivative_recipe_to_rows(
                        recipe,
                        scoring_rows,
                        include_raw=include_raw,
                        resolved_version=resolved_ver,
                        raw_exclude_columns=raw_exclude_columns,
                    )
                    if not out_header:
                        continue

                    score_names = _resolve_recipe_score_names(recipe, resolved_ver)

                    for score_row in out_rows:
                        merged = {"participant_id": sub_id, "session": ses_id}
                        if run_id is not None:
                            merged["run"] = run_id
                        for col in out_header:
                            prefixed_col = _merge_all_output_column_name(
                                recipe_id,
                                col,
                                score_names=score_names,
                                include_recipe_prefix=include_recipe_prefix,
                            )
                            merged[prefixed_col] = score_row.get(col, "n/a")
                        rows_accum.append(merged)

                if rows_accum:
                    df = pd.DataFrame(rows_accum)
                    merge_all_frames.append((recipe_id, df))
                    merge_all_recipe_by_id[recipe_id] = recipe
                    written_recipe_ids.add(recipe_id)
            else:
                (
                    p_count,
                    w_count,
                    o_path,
                    f_note,
                    n_cols,
                ) = _export_recipe_aggregated(
                    recipe_id=recipe_id,
                    recipe=recipe,
                    matching=matching,
                    out_root=out_root,
                    out_format=out_format,
                    modality=modality,
                    lang=lang,
                    layout=layout,
                    include_raw=include_raw,
                    participants_df=participants_df,
                    participants_meta=participants_meta,
                    output_prism_root=output_prism_root,
                    survey_task=survey_task,
                    selected_sessions=selected_sessions,
                    missing_policy=missing_policy,
                    missing_numeric_value=missing_numeric_value,
                )
                processed_files += p_count
                written_files += w_count
                if w_count > 0:
                    written_recipe_ids.add(recipe_id)
                    if written_files == 1:
                        flat_out_path = o_path
                    else:
                        flat_out_path = out_root
                if f_note:
                    fallback_note = f_note
                if n_cols:
                    nan_report[recipe_id] = n_cols

        else:
            # legacy behaviour (prism/flat per-participant outputs)
            p_count, w_count = _export_recipe_legacy(
                recipe_id=recipe_id,
                recipe=recipe,
                matching=matching,
                out_root=out_root,
                out_format=out_format,
                modality=modality,
                include_raw=include_raw,
                flat_rows=flat_rows,
                flat_key_to_idx=flat_key_to_idx,
                participants_df=participants_df,
            )
            processed_files += p_count
            written_files += w_count
            if w_count > 0:
                written_recipe_ids.add(recipe_id)

    missing_input_tasks: tuple[str, ...] = ()
    if modality == "survey" and not survey and observed_task_ids:
        missing_input_tasks = tuple(sorted(observed_task_ids - matched_task_ids))

    # If raw output is requested, export unmatched input tasks as raw-only outputs
    # rather than skipping them.
    if include_raw and modality == "survey" and missing_input_tasks:
        for missing_task in missing_input_tasks:
            matching = [
                path
                for path in tsv_files
                if _extract_task_from_survey_filename(path) == missing_task
            ]
            if not matching:
                continue

            raw_only_recipe = {
                "Kind": "survey",
                "Survey": {"TaskName": missing_task},
                "Scores": [],
            }

            if out_format in ("csv", "xlsx", "sav"):
                if merge_all:
                    import pandas as pd

                    raw_rows_accum: list[dict[str, Any]] = []
                    raw_exclude_columns = _participant_raw_exclude_columns(participants_df)

                    for in_path in matching:
                        processed_files += 1
                        sub_id, ses_id = _infer_sub_ses_from_path(in_path)
                        if not sub_id:
                            continue
                        sub_id = _normalize_participant_id_for_join(sub_id)
                        if not sub_id:
                            continue
                        if not ses_id:
                            ses_id = "ses-1"
                        run_id = _infer_run_from_path(in_path)

                        in_header, in_rows = _read_tsv_rows(in_path)
                        if not in_header or not in_rows:
                            continue

                        out_header, out_rows = _apply_survey_derivative_recipe_to_rows(
                            raw_only_recipe,
                            in_rows,
                            include_raw=True,
                            resolved_version=None,
                            raw_exclude_columns=raw_exclude_columns,
                        )
                        if not out_header:
                            continue

                        score_names = _resolve_recipe_score_names(
                            raw_only_recipe,
                            None,
                        )

                        for raw_row in out_rows:
                            merged = {"participant_id": sub_id, "session": ses_id}
                            if run_id is not None:
                                merged["run"] = run_id
                            for col in out_header:
                                prefixed_col = _merge_all_output_column_name(
                                    missing_task,
                                    col,
                                    score_names=score_names,
                                    include_recipe_prefix=include_recipe_prefix,
                                )
                                merged[prefixed_col] = raw_row.get(col, "n/a")
                            raw_rows_accum.append(merged)

                    if raw_rows_accum:
                        df = pd.DataFrame(raw_rows_accum)
                        merge_all_frames.append((missing_task, df))
                        merge_all_recipe_by_id[missing_task] = raw_only_recipe
                        raw_only_tasks.add(missing_task)
                else:
                    (
                        p_count,
                        w_count,
                        o_path,
                        f_note,
                        n_cols,
                    ) = _export_recipe_aggregated(
                        recipe_id=missing_task,
                        recipe=raw_only_recipe,
                        matching=matching,
                        out_root=out_root,
                        out_format=out_format,
                        modality=modality,
                        lang=lang,
                        layout=layout,
                        include_raw=True,
                        participants_df=participants_df,
                        participants_meta=participants_meta,
                        output_prism_root=output_prism_root,
                        survey_task=missing_task,
                        selected_sessions=selected_sessions,
                        missing_policy=missing_policy,
                        missing_numeric_value=missing_numeric_value,
                    )
                    processed_files += p_count
                    written_files += w_count
                    if w_count > 0:
                        raw_only_tasks.add(missing_task)
                        if written_files == 1:
                            flat_out_path = o_path
                        else:
                            flat_out_path = out_root
                    if f_note:
                        fallback_note = f_note
                    if n_cols:
                        nan_report[f"{missing_task}_raw"] = n_cols
            else:
                p_count, w_count = _export_recipe_legacy(
                    recipe_id=missing_task,
                    recipe=raw_only_recipe,
                    matching=matching,
                    out_root=out_root,
                    out_format=out_format,
                    modality=modality,
                    include_raw=True,
                    flat_rows=flat_rows,
                    flat_key_to_idx=flat_key_to_idx,
                    participants_df=participants_df,
                    output_prism_root=output_prism_root,
                )
                processed_files += p_count
                written_files += w_count
                if w_count > 0:
                    raw_only_tasks.add(missing_task)

    # In merge_all mode, combine per-recipe frames into a single output file.
    if merge_all and merge_all_frames:
        import pandas as pd

        merge_all_rename_maps = _plan_merge_all_column_renames(
            merge_all_frames,
            merge_keys={"participant_id", "session", "run"},
            include_recipe_prefix=include_recipe_prefix,
        )

        include_run_in_merge = False
        has_any_run_in_merge = False
        for _recipe_id, _df in merge_all_frames:
            if "run" not in _df.columns:
                continue
            has_any_run_in_merge = True
            runs = _df["run"].dropna().astype(str).str.strip()
            runs = runs[~runs.str.lower().isin({"", "n/a", "na", "nan", "none", "null"})]
            if runs.nunique() > 1:
                include_run_in_merge = True
                break

        if layout == "long" and has_any_run_in_merge:
            include_run_in_merge = True

        prepared_frames: list[Any] = []
        for recipe_id, _df in merge_all_frames:
            working = _df.copy()
            rename_map = merge_all_rename_maps.get(recipe_id, {})
            if rename_map:
                working = working.rename(columns=rename_map)
            if include_run_in_merge:
                if "run" not in working.columns:
                    working["run"] = "n/a"
            else:
                if "run" in working.columns:
                    working = working.drop(columns=["run"])
            prepared_frames.append(working)

        merge_keys = ["participant_id", "session"] + (["run"] if include_run_in_merge else [])

        combined_df = prepared_frames[0]
        for df in prepared_frames[1:]:
            combined_df = combined_df.merge(
                df, on=merge_keys, how="outer", suffixes=("", "_dup")
            )

        _ensure_dir(out_root)
        out_stem = f"combined_{modality}"
        ext_map = {"csv": ".csv", "xlsx": ".xlsx", "sav": ".sav"}
        out_path = out_root / f"{out_stem}{ext_map.get(out_format, '.csv')}"

        if layout == "wide":
            try:
                import pandas as pd

                id_cols = ["participant_id", "session"]
                include_run_in_wide = False
                if "run" in combined_df.columns:
                    run_values = _distinct_export_context_values(combined_df["run"])
                    include_run_in_wide = len(run_values) > 1

                session_values = _distinct_export_context_values(combined_df["session"])
                include_session_in_wide = len(session_values) > 1

                if include_run_in_wide:
                    id_cols = ["participant_id", "session", "run"]

                score_cols = [
                    c for c in combined_df.columns if c not in set(id_cols) | {"run"}
                ]

                if score_cols:
                    df_melt = combined_df.melt(
                        id_vars=id_cols,
                        value_vars=score_cols,
                        var_name="variable",
                        value_name="value",
                    ).dropna(subset=["value"])
                    if include_session_in_wide and include_run_in_wide:
                        df_melt["col_name"] = (
                            df_melt["variable"].astype(str)
                            + "_"
                            + df_melt["session"].astype(str)
                            + "_"
                            + df_melt["run"].fillna("").astype(str)
                        ).str.rstrip("_")
                    elif include_session_in_wide:
                        df_melt["col_name"] = (
                            df_melt["variable"].astype(str)
                            + "_"
                            + df_melt["session"].astype(str)
                        )
                    elif include_run_in_wide:
                        df_melt["col_name"] = (
                            df_melt["variable"].astype(str)
                            + "_"
                            + df_melt["run"].fillna("").astype(str)
                        ).str.rstrip("_")
                    else:
                        df_melt["col_name"] = df_melt["variable"].astype(str)

                    pivot_index = ["participant_id"]
                    df_wide = df_melt.pivot(
                        index=pivot_index,
                        columns="col_name",
                        values="value",
                    )
                    combined_df = df_wide.reset_index().fillna("n/a")

                    ordered_cols = ["participant_id"] + sorted(
                        [
                            c
                            for c in combined_df.columns
                            if c != "participant_id"
                        ]
                    )
                    combined_df = combined_df.loc[
                        :, [c for c in ordered_cols if c in combined_df.columns]
                    ]
            except Exception as e:
                if fallback_note is None:
                    fallback_note = f"Could not create wide combined layout: {e}"

        participant_export_df = _build_participant_export_frame(participants_df)
        if (
            participant_export_df is not None
            and not participant_export_df.empty
            and "participant_id" in combined_df.columns
        ):
            combined_df = combined_df.merge(
                participant_export_df,
                on="participant_id",
                how="left",
            )

            ordered_prefix_cols = [
                col for col in ["participant_id", "session", "run"] if col in combined_df.columns
            ]
            participant_cols = [
                col
                for col in participant_export_df.columns
                if col != "participant_id" and col in combined_df.columns
            ]
            remaining_cols = [
                col
                for col in combined_df.columns
                if col not in set(ordered_prefix_cols + participant_cols)
            ]
            combined_df = combined_df.loc[
                :,
                ordered_prefix_cols + participant_cols + remaining_cols,
            ]

        combined_var_labels, combined_value_labels, combined_score_details = (
            _build_combined_output_metadata(
                columns=list(combined_df.columns),
                participants_meta=participants_meta,
                recipe_by_id=merge_all_recipe_by_id,
                lang=lang,
                dataset_path=output_prism_root,
                modality=modality,
            )
        )

        if out_format in {"csv", "sav"}:
            _write_codebook_json(
                out_root / f"{out_stem}_codebook.json",
                combined_var_labels,
                combined_value_labels,
                combined_score_details,
            )
            _write_codebook_tsv(
                out_root / f"{out_stem}_codebook.tsv",
                combined_var_labels,
                combined_value_labels,
                combined_score_details,
            )

        if out_format == "csv":
            combined_for_write = _apply_missing_export_policy(
                combined_df,
                missing_policy=missing_policy,
                missing_numeric_value=missing_numeric_value,
            )
            combined_for_write.to_csv(out_path, index=False)
        elif out_format == "xlsx":
            combined_for_write = _apply_missing_export_policy(
                combined_df,
                missing_policy=missing_policy,
                missing_numeric_value=missing_numeric_value,
            )
            combined_for_write.to_excel(out_path, index=False)
        elif out_format == "sav":
            try:
                import pyreadstat

                participant_categorical_cols = _participants_categorical_columns(participants_meta)
                combined_for_write = _apply_missing_export_policy(
                    combined_df,
                    missing_policy=missing_policy,
                    missing_numeric_value=missing_numeric_value,
                )
                combined_for_sav = _prepare_dataframe_for_sav(combined_for_write)
                for participant_col in participant_categorical_cols:
                    if participant_col in combined_for_sav.columns:
                        combined_for_sav[participant_col] = combined_for_sav[
                            participant_col
                        ].astype("string")
                combined_for_sav = _coerce_value_labeled_columns_for_sav(
                    combined_for_sav,
                    combined_value_labels,
                    skip_numeric_coercion_columns=participant_categorical_cols,
                )

                # Sanitize SPSS variable names (illegal chars + leading digit names).
                rename_map_sav = _build_spss_rename_map(combined_for_sav.columns)
                if rename_map_sav:
                    combined_for_sav = combined_for_sav.rename(columns=rename_map_sav)

                # Update var_labels and val_labels keys to use sanitized names
                sav_var_labels: dict[str, str] = {}
                for col, label in combined_var_labels.items():
                    new_col = rename_map_sav.get(col, col)
                    sav_var_labels[new_col] = label

                sav_val_labels = _build_sav_value_labels(
                    df=combined_for_sav,
                    value_labels=combined_value_labels,
                    rename_map=rename_map_sav,
                )

                sav_variable_measure = _build_sav_variable_measure(
                    list(combined_df.columns),
                    participants_meta=participants_meta,
                )
                sav_variable_measure = {
                    rename_map_sav.get(col, col): measure
                    for col, measure in sav_variable_measure.items()
                }

                pyreadstat.write_sav(
                    combined_for_sav,
                    str(out_path),
                    column_labels=sav_var_labels if sav_var_labels else None,
                    variable_value_labels=sav_val_labels if sav_val_labels else None,
                    variable_measure=sav_variable_measure if sav_variable_measure else None,
                )
            except Exception as e:
                # Clean up potential 0-byte .sav file left by failed write
                if out_path.exists() and out_path.stat().st_size == 0:
                    out_path.unlink()
                out_path = out_path.with_suffix(".csv")
                combined_for_write = _apply_missing_export_policy(
                    combined_df,
                    missing_policy=missing_policy,
                    missing_numeric_value=missing_numeric_value,
                )
                combined_for_write.to_csv(out_path, index=False)
                fallback_note = f"SPSS export failed ({e}); wrote CSV instead"
        written_files = 1
        flat_out_path = out_path
        print(f"✓ Combined {len(merge_all_frames)} surveys into: {out_path.name}")

    if written_files == 0:
        raise ValueError(f"No matching {modality} recipes applied.")

    # Copy only recipes that were actually matched to data files in this project.
    recipes_seeded = _copy_recipes_to_project(
        recipes={k: recipes[k] for k in sorted(applied_recipe_ids)},
        dataset_root=output_prism_root,
        modality=modality,
    )

    if out_format == "flat":
        flat_out_path, fallback_note, flat_nan_cols = _finalize_flat_output(
            flat_rows=flat_rows,
            modality=modality,
            layout=layout,
            output_prism_root=output_prism_root,
            fallback_note=fallback_note,
        )
        if flat_nan_cols:
            nan_report["flat_output"] = flat_nan_cols

    _ensure_dir(out_root)
    _write_recipes_dataset_description(
        out_root=out_root, modality=modality, prism_root=output_prism_root
    )
    _ensure_bidsignore_prism_rules(output_prism_root, modality)

    if boilerplate and applied_recipes_list:
        boilerplate_path = out_root / "methods_boilerplate.md"
        _generate_recipes_boilerplate(
            applied_recipes=applied_recipes_list, out_path=boilerplate_path, lang=lang
        )
        boilerplate_html_path = boilerplate_path.with_suffix(".html")

    return SurveyRecipesResult(
        processed_files=processed_files,
        written_files=written_files,
        out_format=final_format,
        out_root=out_root,
        flat_out_path=flat_out_path,
        fallback_note=fallback_note,
        nan_report=nan_report if nan_report else None,
        boilerplate_path=boilerplate_path,
        boilerplate_html_path=boilerplate_html_path,
        recipes_dir=_loaded_recipes_dir,
        recipes_seeded=recipes_seeded,
        written_recipe_ids=tuple(sorted(written_recipe_ids)),
        missing_input_tasks=missing_input_tasks,
        raw_only_tasks=tuple(sorted(raw_only_tasks)),
    )


def _write_jamovi_r_helper(
    path: Path,
    data_filename: str,
    variable_labels: dict[str, str],
    value_labels: dict[str, dict],
) -> None:
    """Generate an R script that applies factors and labels for Jamovi/R."""
    lines = [
        "# PRISM Jamovi/R Metadata Helper",
        "# -------------------------------------------------------------------------",
        "# OPTION A: Using Jamovi's 'Rj' Editor module",
        "# 1. Install 'RjEditor' from the Jamovi library (Analyses -> jamovi library).",
        "# 2. Paste this script into the Rj editor window.",
        "# 3. Change 'df <- read.csv(...)' to 'df <- data' to use Jamovi's active sheet.",
        "# -------------------------------------------------------------------------",
        "# OPTION B: Standalone R / RStudio",
        "# 1. Ensure the CSV and this script are in the same folder.",
        "# 2. Run the script to create a labeled 'df' object for analysis.",
        "# -------------------------------------------------------------------------",
        "",
        "# 1. Load the data",
        f"df <- read.csv('{data_filename}', check.names=FALSE, stringsAsFactors=FALSE)",
        "# df <- data  # Uncomment this to use the Jamovi spreadsheet directly",
        "",
        "# 2. Apply Value Labels (Factors)",
    ]

    for var in sorted(value_labels.keys()):
        levels = value_labels[var]
        if not levels:
            continue

        # Prepare levels: if they look like numbers, we'll try to keep them flexible
        # but in R c('0','1') is safest for CSV-imported data.
        r_levels = ", ".join([f"'{k}'" for k in levels.keys()])

        # Avoid backslashes inside f-string expressions (Python < 3.12 compatibility)
        processed_labels = [str(v).replace("'", "\\'") for v in levels.values()]
        r_labels = ", ".join([f"'{v}'" for v in processed_labels])

        lines.append(f"if ('{var}' %in% colnames(df)) {{")
        lines.append(
            f"  df[['{var}']] <- factor(df[['{var}']], levels=c({r_levels}), labels=c({r_labels}))"
        )
        lines.append("}")

    lines.append("")
    lines.append("# 3. Variable Descriptions (Reference)")
    for var, label in sorted(variable_labels.items()):
        if label:
            clean_label = label.replace("\n", " ").strip()
            lines.append(f"# {var}: {clean_label}")

    lines.append("")
    lines.append("# Display structure")
    lines.append("str(df)")
    lines.append("head(df)")

    _ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
