"""Survey-recipes computation.

This module implements the logic behind `prism_tools.py recipes surveys` as a
reusable API, so both the CLI and the Web/GUI can call the same code.

It reads recipes from the repository's `recipes/surveys/*.json`
folder and writes outputs into the target dataset under:

- `recipes/surveys/<recipe_id>/sub-*/ses-*/survey/*_desc-scores_beh.tsv` (format="prism")
- or `recipes/survey_scores.tsv` (format="flat")

Additionally, it creates `recipes/surveys/dataset_description.json` in the
output dataset.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import csv
import json
from typing import Any, Dict, List, Optional

from src.reporting import get_i18n_text, _pick_references


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


def _build_variable_metadata(
    columns: list[str],
    participants_meta: dict,
    recipe: dict,
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
                if levels and isinstance(levels, dict):
                    # Convert to {code: label} format
                    value_labels[col] = {
                        str(k): get_i18n_text(v, lang) for k, v in levels.items()
                    }

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


def _write_codebook_json(
    path: Path,
    variable_labels: dict,
    value_labels: dict,
    score_details: Optional[dict] = None,
    survey_meta: Optional[dict] = None,
) -> None:
    """Write a companion codebook JSON file with all metadata."""
    codebook: Dict[str, Any] = {
        "_description": "Codebook for derivative output - variable and value labels",
    }

    # Include survey-level metadata
    if survey_meta:
        codebook["survey"] = survey_meta

    codebook["variables"] = {}
    all_vars = (
        set(variable_labels.keys())
        | set(value_labels.keys())
        | set(score_details.keys() if score_details else [])
    )
    for var in sorted(all_vars):
        entry = {}
        if var in variable_labels:
            entry["label"] = variable_labels[var]
        if var in value_labels:
            entry["values"] = value_labels[var]
        if score_details and var in score_details:
            entry["score_info"] = score_details[var]
        if entry:
            codebook["variables"][var] = entry
    _write_json(path, codebook)


def _write_codebook_tsv(
    path: Path,
    variable_labels: dict,
    value_labels: dict,
    score_details: Optional[dict] = None,
) -> None:
    """Write a companion codebook TSV file with all metadata."""
    rows = []
    all_vars = (
        set(variable_labels.keys())
        | set(value_labels.keys())
        | set(score_details.keys() if score_details else [])
    )
    for var in sorted(all_vars):
        label = variable_labels.get(var, "")
        values = value_labels.get(var, {})
        if values:
            values_str = "; ".join(
                f"{k}={v}" for k, v in sorted(values.items(), key=lambda x: str(x[0]))
            )
        else:
            values_str = ""
        # Add score details as extra info
        details_str = ""
        if score_details and var in score_details:
            d = score_details[var]
            parts = []
            if d.get("method"):
                parts.append(f"method={d['method']}")
            if d.get("items"):
                parts.append(f"items={'+'.join(d['items'])}")
            if d.get("range"):
                r = d["range"]
                parts.append(f"range={r.get('min', '?')}-{r.get('max', '?')}")
            details_str = "; ".join(parts)
        rows.append(
            {
                "variable": var,
                "label": label,
                "values": values_str,
                "score_details": details_str,
            }
        )

    _ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["variable", "label", "values", "score_details"],
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _normalize_survey_key(raw: str) -> str:
    s = str(raw or "").strip().lower()
    if not s:
        return s
    for prefix in ("survey-", "task-"):
        if s.startswith(prefix):
            s = s[len(prefix) :]
    return s


def _extract_task_from_survey_filename(path: Path) -> str | None:
    stem = path.stem
    # Examples:
    # sub-001_ses-1_task-ads_survey.tsv
    # sub-001_ses-1_survey-ads_survey.tsv
    # (legacy) sub-001_ses-1_task-ads_beh.tsv
    # (legacy) sub-001_ses-1_survey-ads_beh.tsv
    for token in stem.split("_"):
        if token.startswith("task-"):
            return _normalize_survey_key(token)
        if token.startswith("survey-"):
            return _normalize_survey_key(token)
    return None


def _strip_suffix(stem: str) -> tuple[str, str | None]:
    for suffix in ("_survey", "_beh"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)], suffix
    return stem, None


def _infer_sub_ses_from_path(path: Path) -> tuple[str | None, str | None]:
    sub_id = None
    ses_id = None
    for part in path.parts:
        # Avoid treating the TSV filename (e.g. "sub-001_ses-1_task-ads_beh.tsv")
        # as a subject/session folder.
        if sub_id is None and part.startswith("sub-") and Path(part).suffix == "":
            sub_id = part
        if ses_id is None and part.startswith("ses-") and Path(part).suffix == "":
            ses_id = part
    return sub_id, ses_id


def _parse_numeric_cell(val: str | None) -> float | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == "n/a":
        return None
    # Support common clock-time inputs (e.g., "22:30"), interpreted as hours.
    # This is primarily used for PSQI time-in-bed calculations.
    if ":" in s:
        parts = s.split(":")
        if 2 <= len(parts) <= 3:
            try:
                hh = int(parts[0])
                mm = int(parts[1])
                ss = int(parts[2]) if len(parts) == 3 else 0
                if 0 <= hh <= 48 and 0 <= mm < 60 and 0 <= ss < 60:
                    return float(hh) + float(mm) / 60.0 + float(ss) / 3600.0
            except Exception:
                pass
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def _format_numeric_cell(val: Any) -> str:
    if val is None:
        return "n/a"
    try:
        fval = float(val)
        if fval.is_integer():
            return str(int(fval))
        return str(fval)
    except (ValueError, TypeError):
        return str(val)


def _apply_survey_derivative_recipe_to_rows(
    recipe: dict, rows: list[dict[str, str]], include_raw: bool = False
) -> tuple[list[str], list[dict[str, str]]]:
    transforms = recipe.get("Transforms", {}) or {}
    invert_cfg = transforms.get("Invert") or {}
    invert_items = set(invert_cfg.get("Items") or [])
    invert_scale = invert_cfg.get("Scale") or {}
    invert_min = invert_scale.get("min")
    invert_max = invert_scale.get("max")

    # Support for Derived variables (e.g. best of trials)
    derived_cfg = transforms.get("Derived") or []

    scores = recipe.get("Scores") or []
    score_names = [
        str(s.get("Name", "")).strip() for s in scores if str(s.get("Name", "")).strip()
    ]

    out_header = []
    if include_raw and rows:
        # Include all original columns from the first row
        out_header.extend(list(rows[0].keys()))

    out_header.extend(score_names)
    out_rows: list[dict[str, str]] = []

    for row in rows:
        # We work on a copy to allow derived variables to be used in scores
        current_row = row.copy()

        def _get_item_value(item_id: str, data: dict) -> float | None:
            raw = data.get(item_id)
            v = _parse_numeric_cell(raw)
            if v is None:
                return None
            if (
                item_id in invert_items
                and invert_min is not None
                and invert_max is not None
            ):
                try:
                    return float(invert_max) + float(invert_min) - float(v)
                except Exception:
                    return v
            return v

        def _map_value_to_bucket(val: float, mapping: dict) -> Any:
            for range_str, mapped in mapping.items():
                if "-" in str(range_str):
                    try:
                        low, high = map(float, str(range_str).split("-"))
                        if low <= val <= high:
                            return mapped
                    except Exception:
                        continue
                else:
                    try:
                        if float(val) == float(range_str):
                            return mapped
                    except Exception:
                        continue
            return None

        # 1) Compute Derived variables first
        for d in derived_cfg:
            d_name = d.get("Name")
            if not d_name:
                continue
            d_method = str(d.get("Method", "max")).strip().lower()
            d_items = [str(i).strip() for i in (d.get("Items") or []) if str(i).strip()]

            d_result = None
            if d_method in {"max", "min", "mean", "avg", "sum"}:
                d_values = []
                for item_id in d_items:
                    v = _get_item_value(item_id, current_row)
                    if v is not None:
                        d_values.append(v)

                if d_values:
                    if d_method == "max":
                        d_result = max(d_values)
                    elif d_method == "min":
                        d_result = min(d_values)
                    elif d_method in ("mean", "avg"):
                        d_result = sum(d_values) / float(len(d_values))
                    elif d_method == "sum":
                        d_result = sum(d_values)

            elif d_method == "map":
                mapping = d.get("Mapping") or {}
                source = d.get("Source")
                if not source and d_items:
                    source = d_items[0]
                v = _get_item_value(str(source).strip(), current_row) if source else None
                if v is not None and isinstance(mapping, dict) and mapping:
                    d_result = _map_value_to_bucket(v, mapping)

            elif d_method == "formula":
                formula = d.get("Formula")
                if formula:
                    expr = str(formula)
                    any_missing = False
                    for item_id in d_items:
                        v = _get_item_value(item_id, current_row)
                        if v is None:
                            any_missing = True
                            break
                        val_str = str(v)
                        expr = expr.replace(f"{{{item_id}}}", val_str)
                    if not any_missing:
                        try:
                            d_result = eval(expr, {"__builtins__": None}, {})
                        except Exception:
                            d_result = None

            current_row[d_name] = _format_numeric_cell(d_result)

        # 2) Compute Scores
        out: dict[str, str] = {}
        for score in scores:
            name = str(score.get("Name", "")).strip()
            if not name:
                continue
            method = str(score.get("Method", "sum")).strip().lower()
            items = [
                str(i).strip() for i in (score.get("Items") or []) if str(i).strip()
            ]
            missing = str(score.get("Missing", "ignore")).strip().lower()

            values: list[float] = []
            any_missing = False
            for item_id in items:
                v = _get_item_value(item_id, current_row)
                if v is None:
                    any_missing = True
                else:
                    values.append(v)

            result: float | None
            if missing in {"require_all", "all", "strict"} and any_missing:
                result = None
            elif method == "formula":
                formula = score.get("Formula")
                if formula:
                    expr = formula
                    # Replace {item_id} with value from current_row (which includes derived)
                    for item_id in items:
                        v = _get_item_value(item_id, current_row)
                        val_str = str(v) if v is not None else "0.0"
                        expr = expr.replace(f"{{{item_id}}}", val_str)
                    try:
                        # Safe-ish eval for basic math
                        result = eval(expr, {"__builtins__": None}, {})
                    except Exception:
                        result = None
                else:
                    result = None
            elif method == "map":
                source = score.get("Source")
                mapping = score.get("Mapping")
                if source and mapping:
                    val = _get_item_value(source, current_row)
                    result = None
                    if val is not None:
                        for range_str, cat_val in mapping.items():
                            if "-" in str(range_str):
                                try:
                                    low, high = map(float, str(range_str).split("-"))
                                    if low <= val <= high:
                                        result = cat_val
                                        break
                                except Exception:
                                    pass
                            else:
                                try:
                                    if float(val) == float(range_str):
                                        result = cat_val
                                        break
                                except Exception:
                                    pass
                else:
                    result = None
            elif not values:
                result = None
            else:
                if method == "mean":
                    result = sum(values) / float(len(values))
                else:
                    result = sum(values)

            formatted_val = _format_numeric_cell(result)
            out[name] = formatted_val
            # Add to current_row so subsequent scores can reference it (e.g. for 'map' or 'formula')
            current_row[name] = formatted_val

        if include_raw:
            # Merge original row with scores
            final_row = row.copy()
            final_row.update(out)
            out_rows.append(final_row)
        else:
            out_rows.append(out)

    return out_header, out_rows


def _write_recipes_dataset_description(*, out_root: Path, modality: str, prism_root: Path) -> None:
    """Create a dataset_description.json under recipes/<modality>/."""

    desc_path = out_root / "dataset_description.json"
    if desc_path.exists():
        return

    # Try to inherit some metadata from the root dataset_description.json
    root_desc_path = prism_root / "dataset_description.json"
    root_meta = {}
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


def _generate_recipes_boilerplate(
    applied_recipes: list[dict], out_path: Path, lang: str = "en"
) -> None:
    """Generate a formal methods section boilerplate based on applied recipes (MD and HTML)."""
    sections = []

    # 1. General PRISM/BIDS Section
    if lang == "de":
        sections.append("## Datenstandardisierung und Validierung\n")
        sections.append(
            "Die Daten wurden nach dem PRISM-Standard (Psychological Research Information System & Metadata) organisiert und validiert. "
            "Dieser Standard erweitert die Brain Imaging Data Structure (BIDS) auf die psychologische Forschung. "
            "Die Datenverarbeitung und Berechnung der Scores erfolgte automatisiert mit dem PRISM-System, "
            "wobei die in den JSON-Rezepten definierten Scoring-Logiken angewendet wurden.\n"
        )
    else:
        sections.append("## Data Standardization and Validation\n")
        sections.append(
            "Data were organized and validated according to the PRISM (Psychological Research Information System & Metadata) "
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
        # Recipes might use "Survey" or "Study" (for compatibility)
        survey_info = recipe.get("Survey") or recipe.get("Study") or {}
        
        name = get_i18n_text(survey_info.get("Name") or survey_info.get("OriginalName") or survey_info.get("TaskName"), lang)
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
                text_parts.append(f"Die verwendete Übersetzung ist {refs['translation']}.")
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
                    sections.append("- Negativ gepolte Items wurden vor der Skalenbildung invertiert.")
                else:
                    sections.append("- Negatively keyed items were reverse-coded prior to score calculation.")
            
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
                    method_desc = "categorical mapping" if lang == "en" else "kategorisierte Zuordnung"
                
                item_count = len(s_items)
                if item_count > 0:
                    if lang == "de":
                        sections.append(f"- `{s_name}`: {method_desc} ({item_count} Items).")
                    else:
                        sections.append(f"- `{s_name}`: {method_desc} ({item_count} items).")
                elif s_source:
                    if lang == "de":
                        sections.append(f"- `{s_name}`: {method_desc} basierend auf `{s_source}`.")
                    else:
                        sections.append(f"- `{s_name}`: {method_desc} based on `{s_source}`.")
                else:
                    sections.append(f"- `{s_name}`: {method_desc}.")

    # Write Markdown
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sections))

    # Write HTML
    html_path = out_path.with_suffix(".html")
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
        "<body>"
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
            # Handle bold headers like **Scoring**:
            bold_text = line.replace("**", "").strip().strip(":")
            html_content.append(f"<p><strong>{bold_text}:</strong></p>")
        else:
            # Handle backticks in paragraphs
            p_text = line
            while "`" in p_text:
                p_text = p_text.replace("`", "<code>", 1).replace("`", "</code>", 1)
            html_content.append(f"<p>{p_text}</p>")

    if in_list:
        html_content.append("</ul>")

    html_content.extend(["</body>", "</html>"])
    
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html_content))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sections))


def compute_survey_recipes(
    *,
    prism_root: str | Path,
    repo_root: str | Path,
    survey: str | None = None,
    out_format: str = "flat",
    modality: str = "survey",
    lang: str = "en",
    layout: str = "long",
    include_raw: bool = False,
    boilerplate: bool = False,
) -> SurveyRecipesResult:
    """Compute survey scores in a PRISM dataset using recipes.

    Args:
            prism_root: Target PRISM dataset root (must exist).
            repo_root: Repository root (used to locate recipe JSONs).
            survey: Optional comma-separated recipe ids to apply.
            out_format: "flat" (default), "prism", "csv", "xlsx", "save", "r".
            lang: Language for metadata labels (e.g., "en", "de").
            layout: "long" (default) or "wide" for repeated measures.
            include_raw: If True, include original columns in the output.
            boilerplate: If True, generate a methods boilerplate.

    Raises:
            ValueError: For user errors (missing paths, unknown recipes, etc.).
            RuntimeError: For unexpected failures.
    """

    prism_root = Path(prism_root).resolve()
    repo_root = Path(repo_root).resolve()

    if not prism_root.exists() or not prism_root.is_dir():
        raise ValueError(f"--prism is not a directory: {prism_root}")

    # If prism_root points to rawdata, we use the parent as the PRISM root for output
    # but keep prism_root for scanning files.
    output_prism_root = prism_root
    if prism_root.name == "rawdata":
        output_prism_root = prism_root.parent

    modality = str(modality or "survey").strip().lower()
    out_format = str(out_format or "prism").strip().lower()
    final_format = out_format

    if out_format not in {"prism", "flat", "csv", "xlsx", "save", "r"}:
        raise ValueError("--format must be one of: prism, flat, csv, xlsx, save, r")

    layout = str(layout or "long").strip().lower()
    if layout not in {"long", "wide"}:
        raise ValueError("--layout must be one of: long, wide")

    # Locate recipe folder by modality.
    if modality == "survey":
        recipes_dir = (repo_root / "recipes" / "surveys").resolve()
        expected = "recipes/surveys/*.json"
    elif modality == "biometrics":
        recipes_dir = (repo_root / "recipes" / "biometrics").resolve()
        expected = "recipes/biometrics/*.json"
    else:
        raise ValueError("modality must be one of: survey, biometrics")

    if not recipes_dir.exists() or not recipes_dir.is_dir():
        raise ValueError(f"Missing recipe folder: {recipes_dir}. Expected {expected}")

    recipe_paths = sorted(recipes_dir.glob("*.json"))
    if not recipe_paths:
        raise ValueError(f"No derivative recipes found in: {recipes_dir}")

    recipes: dict[str, dict] = {}
    for p in recipe_paths:
        try:
            recipe = _read_json(p)
        except Exception:
            continue
        recipe_id = _normalize_survey_key(p.stem)
        recipes[recipe_id] = {"path": p, "json": recipe}

    if not recipes:
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
        for recipe_id, rec in sorted(recipes.items()):
            errs = validate_recipe(rec.get("json") or {}, recipe_id=recipe_id)
            # Only treat "Scores missing" as a warning-like error if the recipe truly has no scores.
            # We still surface it because it usually indicates a non-functional recipe.
            recipe_errors.extend([f"{rec.get('path').name}: {e}" for e in errs])

        if recipe_errors:
            # Fail-fast: better to abort than to produce partial/wrong outputs.
            raise ValueError(
                "Invalid derivative recipe(s):\n- " + "\n- ".join(recipe_errors)
            )

    selected: set[str] | None = None
    if survey:
        parts = [p.strip() for p in str(survey).replace(";", ",").split(",")]
        parts = [_normalize_survey_key(p) for p in parts if p.strip()]
        selected = set([p for p in parts if p])
        unknown = sorted([s for s in selected if s not in recipes])
        if unknown:
            raise ValueError(
                "Unknown survey recipe names: "
                + ", ".join(unknown)
                + ". Available: "
                + ", ".join(sorted(recipes.keys()))
            )

    # Scan dataset for TSV files based on modality
    tsv_files: list[Path] = []
    if modality == "survey":
        # Search in survey/ and beh/ (BIDS standard)
        for folder in ("survey", "beh"):
            tsv_files.extend(prism_root.glob(f"sub-*/ses-*/{folder}/*.tsv"))
            tsv_files.extend(prism_root.glob(f"sub-*/{folder}/*.tsv"))
    elif modality == "biometrics":
        tsv_files.extend(prism_root.glob("sub-*/ses-*/biometrics/*.tsv"))
        tsv_files.extend(prism_root.glob("sub-*/biometrics/*.tsv"))
    else:
        # Fallback: search both
        tsv_files.extend(prism_root.glob("sub-*/ses-*/*/*.tsv"))
        tsv_files.extend(prism_root.glob("sub-*/*/*.tsv"))

    tsv_files = sorted(set([p for p in tsv_files if p.is_file()]))
    if not tsv_files:
        raise ValueError(f"No {modality} TSV files found under: {prism_root}")

    # Load participants.tsv if available (for merging demographic data)
    participants_df = None
    participants_meta = {}  # Column metadata from participants.json
    participants_tsv = output_prism_root / "participants.tsv"
    participants_json = output_prism_root / "participants.json"
    if participants_tsv.is_file():
        try:
            import pandas as pd

            participants_df = pd.read_csv(participants_tsv, sep="\t", dtype=str)
            # Ensure participant_id column exists
            if "participant_id" not in participants_df.columns:
                participants_df = None
        except Exception:
            participants_df = None

    # Load participants.json for metadata (variable labels, value labels)
    if participants_json.is_file():
        try:
            participants_meta = _read_json(participants_json)
        except Exception:
            participants_meta = {}

    # Output scores into BIDS-recipes folders; recipes remain the instruction set in the repo.
    out_root = output_prism_root / "recipes" / ("surveys" if modality == "survey" else "biometrics")
    flat_rows: list[dict] = []
    flat_key_to_idx: dict[tuple, int] = {}
    nan_report: dict[str, list[str]] = {}
    applied_recipes_list: list[dict] = []
    boilerplate_path: Path | None = None

    processed_files = 0
    written_files = 0

    flat_out_path: Path | None = None
    fallback_note: str | None = None

    # If modality=survey/biometrics we will write one flat file per survey/biometric (recipe)
    for recipe_id, rec in sorted(recipes.items()):
        if selected is not None and recipe_id not in selected:
            continue

        recipe = rec["json"]
        # For biometrics, we might use BiometricName instead of TaskName
        task_key = "BiometricName" if modality == "biometrics" else "TaskName"
        info_key = "Biometrics" if modality == "biometrics" else "Survey"
        
        survey_task = _normalize_survey_key(
            (recipe.get(info_key, {}) or {}).get(task_key) or recipe_id
        )

        matching = []
        for p in tsv_files:
            task = _extract_task_from_survey_filename(p)
            if task == survey_task:
                matching.append(p)
        if not matching:
            continue

        applied_recipes_list.append(recipe)

        if out_format in ("csv", "xlsx", "save", "r"):
            # Aggregated formats (one file per recipe)
            rows_accum: List[Dict[str, Any]] = []
            for in_path in matching:
                processed_files += 1
                sub_id, ses_id = _infer_sub_ses_from_path(in_path)
                if not sub_id:
                    continue
                if not ses_id:
                    ses_id = "ses-1"

                in_header, in_rows = _read_tsv_rows(in_path)
                if not in_header or not in_rows:
                    continue

                out_header, out_rows = _apply_survey_derivative_recipe_to_rows(
                    recipe, in_rows, include_raw=include_raw
                )
                if not out_header:
                    continue

                for row_index, score_row in enumerate(out_rows):
                    merged = {"participant_id": sub_id, "session": ses_id}
                    for col in out_header:
                        merged[col] = score_row.get(col, "n/a")
                    rows_accum.append(merged)

            if not rows_accum:
                continue

            # Write a single file for this recipe
            _ensure_dir(out_root)
            try:
                import pandas as pd
            except Exception:
                raise RuntimeError(
                    f"pandas is required to write flat {modality} outputs (install pandas)"
                )

            df = pd.DataFrame(rows_accum)
            # Ensure column order: participant_id, session, then score columns
            cols = [
                c
                for c in (["participant_id", "session"] + [c for c in out_header])
                if c in df.columns
            ]
            df = df.loc[:, cols]

            if layout == "wide":
                # Pivot so that session is in columns
                # We keep participant_id as index
                try:
                    # Pivot the score columns
                    df_wide = df.pivot(
                        index="participant_id", columns="session", values=out_header
                    )
                    # Flatten multi-index columns: "ses-1_total_score"
                    if isinstance(df_wide.columns, pd.MultiIndex):
                        # df.pivot with multiple values returns MultiIndex (value, session)
                        # We want (session, value)
                        df_wide.columns = [
                            f"{ses}_{val}" for val, ses in df_wide.columns
                        ]
                    else:
                        # Only one score column
                        df_wide.columns = [f"{ses}_{out_header[0]}" for ses in df_wide.columns]
                    
                    df = df_wide.reset_index().fillna("n/a")
                    # Update out_header to reflect new columns for metadata building
                    out_header = [c for c in df.columns if c != "participant_id"]
                except Exception as e:
                    # Fallback to long if pivot fails (e.g. duplicate sub/ses pairs)
                    if fallback_note is None:
                        fallback_note = f"Could not create wide layout: {e}"

            # Detect columns with all missing values (excluding ids)
            try:
                df_nan = df.replace("n/a", pd.NA)
                nan_cols = [
                    c
                    for c in df_nan.columns
                    if c not in {"participant_id", "session"} and df_nan[c].isna().all()
                ]
                if nan_cols:
                    nan_report[recipe_id] = nan_cols
            except Exception:
                pass

            # Merge participant variables (age, sex, etc.) if available
            if participants_df is not None:
                # Get participant columns except participant_id (already in df)
                participant_cols = [
                    c for c in participants_df.columns if c != "participant_id"
                ]
                if participant_cols:
                    df = df.merge(
                        participants_df[["participant_id"] + participant_cols],
                        on="participant_id",
                        how="left",
                    )
                    # Reorder: participant_id, participant vars, session, scores
                    final_cols = (
                        ["participant_id"]
                        + participant_cols
                        + ["session"]
                        + [c for c in out_header if c in df.columns]
                    )
                    df = df.loc[:, [c for c in final_cols if c in df.columns]]

            out_fname = None
            final_format = out_format

            # Build metadata for all export formats
            var_labels, val_labels, score_details = _build_variable_metadata(
                list(df.columns),
                participants_meta,
                recipe,
                lang=lang,
            )
            survey_meta = _build_survey_metadata(recipe, lang=lang)

            if out_format == "csv":
                out_fname = out_root / f"{recipe_id}.csv"
                df.to_csv(out_fname, index=False)
                # Write companion codebook files
                _write_codebook_json(
                    out_root / f"{recipe_id}_codebook.json",
                    var_labels,
                    val_labels,
                    score_details,
                    survey_meta,
                )
                _write_codebook_tsv(
                    out_root / f"{recipe_id}_codebook.tsv",
                    var_labels,
                    val_labels,
                    score_details,
                )
            elif out_format == "xlsx":
                out_fname = out_root / f"{recipe_id}.xlsx"
                # Write data + codebook sheet
                try:
                    with pd.ExcelWriter(out_fname, engine="openpyxl") as writer:
                        df.to_excel(writer, sheet_name="Data", index=False)
                        # Build codebook dataframe with full metadata
                        codebook_rows = []
                        for var in df.columns:
                            label = var_labels.get(var, "")
                            values = val_labels.get(var, {})
                            values_str = (
                                "; ".join(
                                    f"{k}={v}"
                                    for k, v in sorted(
                                        values.items(), key=lambda x: str(x[0])
                                    )
                                )
                                if values
                                else ""
                            )
                            # Include score details
                            details_str = ""
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
                                details_str = "; ".join(parts)
                            codebook_rows.append(
                                {
                                    "variable": var,
                                    "label": label,
                                    "values": values_str,
                                    "score_details": details_str,
                                }
                            )
                        codebook_df = pd.DataFrame(codebook_rows)
                        codebook_df.to_excel(writer, sheet_name="Codebook", index=False)
                        # Add survey info sheet
                        if survey_meta:
                            survey_rows = [
                                {"property": k, "value": str(v)}
                                for k, v in survey_meta.items()
                            ]
                            survey_df = pd.DataFrame(survey_rows)
                            survey_df.to_excel(
                                writer, sheet_name="Survey Info", index=False
                            )
                except Exception:
                    # Fallback: just write data without codebook sheet
                    df.to_excel(out_fname, index=False)
            elif out_format == "save":
                out_fname = out_root / f"{recipe_id}.save"
                try:
                    import pyreadstat

                    # Convert value_labels to pyreadstat format: {col: {numeric_code: label}}
                    # pyreadstat expects numeric keys for value labels
                    sav_value_labels = {}
                    for col, vals in val_labels.items():
                        if col in df.columns:
                            try:
                                # Try to convert keys to float for numeric columns
                                sav_value_labels[col] = {
                                    float(k): v for k, v in vals.items()
                                }
                            except (ValueError, TypeError):
                                # Keep as string if not numeric
                                sav_value_labels[col] = vals

                    pyreadstat.write_sav(
                        df,
                        str(out_fname),
                        column_labels=var_labels if var_labels else None,
                        variable_value_labels=(
                            sav_value_labels if sav_value_labels else None
                        ),
                    )
                    # SPSS doesn't store survey-level metadata, write companion codebook
                    _write_codebook_json(
                        out_root / f"{recipe_id}_codebook.json",
                        var_labels,
                        val_labels,
                        score_details,
                        survey_meta,
                    )
                except Exception:
                    # Fallback to CSV if pyreadstat not available
                    out_fname = out_root / f"{recipe_id}.csv"
                    df.to_csv(out_fname, index=False)
                    _write_codebook_json(
                        out_root / f"{recipe_id}_codebook.json",
                        var_labels,
                        val_labels,
                        score_details,
                        survey_meta,
                    )
                    _write_codebook_tsv(
                        out_root / f"{recipe_id}_codebook.tsv",
                        var_labels,
                        val_labels,
                        score_details,
                    )
                    final_format = "csv"
                    if fallback_note is None:
                        fallback_note = (
                            "pyreadstat not available; wrote CSV instead of SAVE"
                        )
            elif out_format == "r":
                # Try to write a feather file (widely readable by R via arrow)
                out_fname = out_root / f"{recipe_id}.feather"
                try:
                    df.to_feather(out_fname)
                    # Feather doesn't support metadata, write companion codebook
                    _write_codebook_json(
                        out_root / f"{recipe_id}_codebook.json",
                        var_labels,
                        val_labels,
                        score_details,
                        survey_meta,
                    )
                    _write_codebook_tsv(
                        out_root / f"{recipe_id}_codebook.tsv",
                        var_labels,
                        val_labels,
                        score_details,
                    )
                except Exception:
                    # Fallback to CSV
                    out_fname = out_root / f"{recipe_id}.csv"
                    df.to_csv(out_fname, index=False)
                    _write_codebook_json(
                        out_root / f"{recipe_id}_codebook.json",
                        var_labels,
                        val_labels,
                        score_details,
                        survey_meta,
                    )
                    _write_codebook_tsv(
                        out_root / f"{recipe_id}_codebook.tsv",
                        var_labels,
                        val_labels,
                        score_details,
                    )
                    final_format = "csv"
                    if fallback_note is None:
                        fallback_note = "pyarrow/feather not available; wrote CSV instead of R/feather"

            if out_fname and out_fname.exists():
                written_files += 1

        else:
            # legacy behaviour (prism/flat per-participant outputs)
            for in_path in matching:
                processed_files += 1
                sub_id, ses_id = _infer_sub_ses_from_path(in_path)
                if not sub_id:
                    continue
                if not ses_id:
                    ses_id = "ses-1"

                in_header, in_rows = _read_tsv_rows(in_path)
                if not in_header or not in_rows:
                    continue

                out_header, out_rows = _apply_survey_derivative_recipe_to_rows(
                    recipe, in_rows, include_raw=include_raw
                )
                if not out_header:
                    break

                if out_format == "flat":
                    prefix = f"{recipe_id}_"
                    for row_index, score_row in enumerate(out_rows):
                        key = (sub_id, ses_id, recipe_id, row_index)
                        if key in flat_key_to_idx:
                            merged = flat_rows[flat_key_to_idx[key]]
                        else:
                            merged = {
                                "participant_id": sub_id,
                                "session": ses_id,
                                "survey": recipe_id,
                            }
                            flat_key_to_idx[key] = len(flat_rows)
                            flat_rows.append(merged)

                        for col in out_header:
                            merged[prefix + col] = score_row.get(col, "n/a")

                    written_files += 1
                else:
                    out_dir = out_root / recipe_id / sub_id / ses_id / modality
                    stem = in_path.stem
                    base_stem, _in_suffix = _strip_suffix(stem)
                    # Write recipes with the new _survey suffix; legacy _beh inputs are upgraded.
                    new_stem = f"{base_stem}_desc-scores_{modality}"
                    out_path = out_dir / f"{new_stem}.tsv"
                    _write_tsv_rows(out_path, out_header, out_rows)
                    written_files += 1

    if written_files == 0:
        msg = f"No matching {modality} recipes applied."
        if selected:
            msg += f" (No {modality} TSV matched the selected --survey/--biometric.)"
        else:
            msg += f" (No {modality} TSV matched any recipe TaskName/BiometricName.)"
        raise ValueError(msg)

    if out_format == "flat":
        fixed = ["participant_id", "session", modality]
        score_cols = sorted({k for r in flat_rows for k in r.keys() if k not in fixed})
        
        if layout == "wide":
            try:
                import pandas as pd
                df_flat = pd.DataFrame(flat_rows)
                # Pivot
                # We need to handle the case where multiple surveys exist for the same sub/ses
                # The 'survey' column distinguishes them in long format.
                # In wide format, we want to pivot on participant_id, and have columns like ses-1_ads_total, ses-1_pss_total
                
                # First, melt the score columns so we have (participant, session, survey, variable, value)
                id_vars = ["participant_id", "session", "survey"]
                df_melt = df_flat.melt(id_vars=id_vars, value_vars=score_cols).dropna()
                
                # Create a combined column name: {session}_{variable}
                # Note: variable already contains the survey prefix (e.g. ads_total)
                df_melt["col_name"] = df_melt["session"] + "_" + df_melt["variable"]
                
                # Pivot to wide
                df_wide = df_melt.pivot(index="participant_id", columns="col_name", values="value")
                df_flat = df_wide.reset_index().fillna("n/a")
                
                flat_header = ["participant_id"] + sorted([c for c in df_flat.columns if c != "participant_id"])
                flat_out_path = output_prism_root / "recipes" / f"{modality}_scores.tsv"
                # Convert back to rows for _write_tsv_rows
                flat_rows = df_flat.to_dict("records")
            except Exception as e:
                if fallback_note is None:
                    fallback_note = f"Could not create wide flat layout: {e}"
                flat_header = fixed + score_cols
                flat_out_path = output_prism_root / "recipes" / f"{modality}_scores.tsv"
        else:
            flat_header = fixed + score_cols
            flat_out_path = output_prism_root / "recipes" / f"{modality}_scores.tsv"

        _write_tsv_rows(flat_out_path, flat_header, flat_rows)

        # Detect all-NA columns in flat output (long or wide)
        try:
            import pandas as pd

            df_flat_chk = pd.DataFrame(flat_rows)
            df_flat_chk = df_flat_chk.replace("n/a", pd.NA)
            ignore_cols = {"participant_id", "session", modality, "survey"}
            nan_cols = [
                c
                for c in df_flat_chk.columns
                if c not in ignore_cols and df_flat_chk[c].isna().all()
            ]
            if nan_cols:
                nan_report["flat_output"] = nan_cols
        except Exception:
            pass

    _ensure_dir(out_root)
    _write_recipes_dataset_description(
        out_root=out_root, modality=modality, prism_root=output_prism_root
    )

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
    )
