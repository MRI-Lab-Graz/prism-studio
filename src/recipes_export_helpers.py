"""SPSS / SAV / codebook export helpers extracted from recipes_surveys.

These helpers handle dataframe shaping, declared-datatype enforcement,
missing-value policy, SPSS variable-name sanitization, and writing
companion codebook files. They are re-exported from
``src.recipes_surveys`` to preserve the historical import surface.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional


_MISSING_TEXT_TOKENS = {"", "n/a", "na", "nan", "none", "null"}

_SPSS_VARIABLE_MAX_LENGTH = 64


def _ensure_dir_local(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json_local(path: Path, obj: dict) -> None:
    _ensure_dir_local(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _coerce_value_labeled_columns_for_sav(
    df: Any,
    value_labels: dict[str, dict],
    *,
    skip_numeric_coercion_columns: set[str] | None = None,
) -> Any:
    """Convert value-labeled columns to numeric where label keys are numeric."""
    import pandas as pd

    if df is None or not value_labels:
        return df

    out = df.copy()
    skip_columns = {str(col) for col in (skip_numeric_coercion_columns or set())}
    for col, labels in value_labels.items():
        if col not in out.columns or not isinstance(labels, dict) or not labels:
            continue
        if str(col) in skip_columns:
            continue

        numeric_keys: list[float] = []
        keys_are_numeric = True
        for key in labels.keys():
            try:
                numeric_keys.append(float(key))
            except (TypeError, ValueError):
                keys_are_numeric = False
                break
        if not keys_are_numeric:
            continue

        cleaned = out[col].replace(
            ["n/a", "N/A", "na", "NA", "", "null", "None"], pd.NA
        )
        numeric = pd.to_numeric(cleaned, errors="coerce")
        if numeric.notna().sum() == 0:
            continue

        non_na = numeric.dropna()
        if not non_na.empty and bool(((non_na % 1) == 0).all()):
            out[col] = numeric.round().astype("Int64")
        else:
            out[col] = numeric.astype(float)

    return out


def _prepare_dataframe_for_sav(df: Any) -> Any:
    """Normalize missing markers and numeric formatting for SPSS export.

    SPSS stores numeric values locale-independently in SAV files. This helper
    converts decimal-comma strings (e.g. "3,14") to numeric values, maps common
    textual NA markers to missing values, and leaves non-numeric columns as text.
    """
    import pandas as pd

    if df is None:
        return df

    out = df.copy()
    missing_tokens = _MISSING_TEXT_TOKENS

    for col in out.columns:
        series = out[col]
        text = series.astype("string").str.strip()
        lower = text.str.lower()
        non_missing_mask = text.notna() & (~lower.isin(missing_tokens))

        # Normalize textual missing markers for every column.
        missing_mask = text.notna() & lower.isin(missing_tokens)
        if bool(missing_mask.any()):
            out.loc[missing_mask, col] = pd.NA

        if int(non_missing_mask.sum()) == 0:
            continue

        # Accept both decimal separators in input while writing canonical numerics.
        numeric = pd.to_numeric(
            text.str.replace(",", ".", regex=False),
            errors="coerce",
        )
        if int(numeric[non_missing_mask].notna().sum()) != int(non_missing_mask.sum()):
            continue

        # Preserve identifier-like text codes (e.g., "001", "010") as strings.
        non_missing_text = text[non_missing_mask]
        if bool(non_missing_text.astype("string").str.match(r"^0\d+$").any()):
            continue

        non_na_numeric = numeric.dropna()
        if not non_na_numeric.empty and bool(((non_na_numeric % 1) == 0).all()):
            out[col] = numeric.round().astype("Int64")
        else:
            out[col] = numeric.astype(float)

    return out


def _normalize_declared_data_type(value: Any) -> str | None:
    """Normalize declared datatype labels to canonical recipe export types."""
    token = str(value or "").strip().lower()
    if not token:
        return None

    mapping = {
        "int": "integer",
        "integer": "integer",
        "long": "integer",
        "numeric": "float",
        "number": "float",
        "float": "float",
        "double": "float",
        "text": "string",
        "string": "string",
        "str": "string",
        "bool": "boolean",
        "boolean": "boolean",
    }
    return mapping.get(token)


def _apply_declared_datatypes(df: Any, declared_datatypes: dict[str, Any]) -> Any:
    """Apply recipe-declared datatypes to dataframe columns when safely coercible."""
    import pandas as pd

    if df is None or not isinstance(declared_datatypes, dict) or not declared_datatypes:
        return df

    out = df.copy()

    for col, declared_type in declared_datatypes.items():
        if col not in out.columns:
            continue

        normalized_type = _normalize_declared_data_type(declared_type)
        if normalized_type is None:
            continue

        if normalized_type == "string":
            out[col] = out[col].astype("string")
            continue

        text = out[col].astype("string").str.strip()
        lower = text.str.lower()
        non_missing_mask = text.notna() & (~lower.isin(_MISSING_TEXT_TOKENS))
        numeric = pd.to_numeric(
            text.str.replace(",", ".", regex=False),
            errors="coerce",
        )

        if int(numeric[non_missing_mask].notna().sum()) != int(non_missing_mask.sum()):
            continue

        if normalized_type == "integer":
            out[col] = numeric.round().astype("Int64")
            continue

        if normalized_type == "float":
            out[col] = numeric.astype(float)
            continue

        if normalized_type == "boolean":
            bool_map = {
                "true": True,
                "false": False,
                "1": True,
                "0": False,
                "yes": True,
                "no": False,
            }
            mapped = lower.map(bool_map)
            valid_mask = text.notna() & (~lower.isin(_MISSING_TEXT_TOKENS))
            if int(mapped[valid_mask].notna().sum()) != int(valid_mask.sum()):
                continue
            out[col] = mapped.astype("boolean")

    return out


def _apply_missing_export_policy(
    df: Any,
    *,
    missing_policy: str,
    missing_numeric_value: float | None,
) -> Any:
    """Apply export-time missing value policy without mutating source data."""
    import pandas as pd

    if df is None:
        return df

    policy = str(missing_policy or "system-missing").strip().lower()
    if policy not in {"system-missing", "text-na", "text-nan", "numeric-sentinel"}:
        raise ValueError(
            "missing_policy must be one of: system-missing, text-na, text-nan, numeric-sentinel"
        )

    out = df.copy()
    text = out.astype("string")
    missing_mask = text.apply(lambda col: col.str.strip().str.lower().isin(_MISSING_TEXT_TOKENS))
    if bool(missing_mask.any().any()):
        out = out.mask(missing_mask, pd.NA)

    if policy == "system-missing":
        return out

    if policy == "text-na":
        return out.fillna("n/a")

    if policy == "text-nan":
        return out.fillna("NaN")

    if missing_numeric_value is None:
        raise ValueError(
            "missing_numeric_value is required when missing_policy is numeric-sentinel"
        )

    sentinel = float(missing_numeric_value)
    for col in out.columns:
        col_series = out[col]
        if not bool(col_series.isna().any()):
            continue

        non_missing = col_series.dropna().astype("string").str.strip()
        if non_missing.empty:
            out[col] = col_series.fillna(sentinel)
            continue

        numeric = pd.to_numeric(non_missing.str.replace(",", ".", regex=False), errors="coerce")
        if int(numeric.notna().sum()) == int(non_missing.size):
            out[col] = pd.to_numeric(
                col_series.astype("string").str.replace(",", ".", regex=False),
                errors="coerce",
            )
            out[col] = out[col].fillna(sentinel)

    return out


def _sanitize_spss_variable_name(name: str) -> str:
    """Return an SPSS-safe variable name.

    SPSS names must not contain punctuation/spaces and must start with a
    letter-like token, so names beginning with digits get a `v_` prefix.
    Preserve Unicode letters such as German umlauts because pyreadstat can
    write and round-trip them correctly in SAV variable names.
    """
    cleaned = "".join(
        char if char.isalnum() or char == "_" else "_"
        for char in str(name or "")
    )
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "var"
    if not cleaned[0].isalpha():
        cleaned = f"v_{cleaned}"
    return cleaned[:_SPSS_VARIABLE_MAX_LENGTH]


def _build_spss_rename_map(columns: Any) -> dict[str, str]:
    """Build a deterministic rename map from raw column names to SPSS-safe names."""
    rename_map: dict[str, str] = {}
    used_names: set[str] = set()

    for col in columns:
        original = str(col)
        base_name = _sanitize_spss_variable_name(original)
        candidate = base_name
        counter = 2

        # Avoid collisions after sanitization (e.g. "a-b" and "a.b" -> "a_b").
        while candidate in used_names:
            suffix = f"_{counter}"
            max_base_len = _SPSS_VARIABLE_MAX_LENGTH - len(suffix)
            candidate = f"{base_name[:max_base_len]}{suffix}"
            counter += 1

        used_names.add(candidate)
        if candidate != original:
            rename_map[original] = candidate

    return rename_map


def _build_sav_value_labels(
    *,
    df: Any,
    value_labels: dict[str, dict],
    rename_map: dict[str, str],
) -> dict[str, dict[Any, str]]:
    """Build SPSS value-label maps with dtype-aware key coercion.

    - Numeric columns: label keys are parsed as numbers (supports comma decimals).
    - Non-numeric columns: label keys are preserved as strings.
    """
    import pandas as pd

    out: dict[str, dict[Any, str]] = {}
    if df is None:
        return out

    for col, vals in value_labels.items():
        if not isinstance(vals, dict) or not vals:
            continue

        new_col = rename_map.get(col, col)
        if new_col not in df.columns:
            continue

        is_numeric_col = pd.api.types.is_numeric_dtype(df[new_col])
        col_labels: dict[Any, str] = {}
        for key, label in vals.items():
            if label is None:
                continue
            if is_numeric_col:
                try:
                    key_num = float(str(key).strip().replace(",", "."))
                except (TypeError, ValueError):
                    continue
                col_labels[key_num] = str(label)
            else:
                key_text = str(key).strip()
                if not key_text:
                    continue
                col_labels[key_text] = str(label)

        if col_labels:
            out[new_col] = col_labels

    return out


def _build_sav_variable_measure(
    columns: list[str],
    *,
    participants_meta: dict,
) -> dict[str, str]:
    """Build SPSS variable_measure metadata for participant variables."""
    measures: dict[str, str] = {}

    for col in columns:
        if col in {"participant_id", "session", "run"}:
            measures[col] = "nominal"
            continue

        col_meta = participants_meta.get(col)
        if not isinstance(col_meta, dict):
            continue

        variable_type = str(
            col_meta.get("VariableType") or col_meta.get("variable_type") or ""
        ).strip().lower()
        declared_type = _normalize_declared_data_type(
            col_meta.get("DataType") or col_meta.get("data_type")
        )

        if variable_type in {"categorical", "nominal", "category"}:
            measures[col] = "nominal"
            continue
        if variable_type == "ordinal":
            measures[col] = "ordinal"
            continue
        if variable_type in {"continuous", "scale"}:
            measures[col] = "scale"
            continue

        if declared_type in {"integer", "float", "boolean"}:
            measures[col] = "scale"
        elif declared_type == "string":
            measures[col] = "nominal"

    return measures


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
    _write_json_local(path, codebook)


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
            if d.get("min_valid") is not None:
                parts.append(f"min_valid={d['min_valid']}")
            details_str = "; ".join(parts)
        rows.append(
            {
                "variable": var,
                "label": label,
                "values": values_str,
                "score_details": details_str,
            }
        )

    _ensure_dir_local(path.parent)
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
