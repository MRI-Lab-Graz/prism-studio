"""Make a participants.tsv BIDS-friendly: numeric columns and numeric sex codes."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

DEFAULT_SEX_MAPPING = {1: "M", 2: "F", 3: "O", "1": "M", "2": "F", "3": "O"}
_NUMERIC_COLUMNS = {"age", "height", "weight", "years_of_education"}


def fix_participants_tsv(
    file_path: str | Path,
    sex_mapping: dict | None = None,
    dry_run: bool = False,
) -> dict:
    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if sex_mapping is None:
        sex_mapping = DEFAULT_SEX_MAPPING

    df = pd.read_csv(path, sep="\t", dtype=str)
    changes = []

    for col in df.columns:
        if col.lower() not in _NUMERIC_COLUMNS:
            continue
        try:
            numeric_values = pd.to_numeric(df[col], errors="coerce")
            numeric_count = numeric_values.notna().sum()
            if numeric_count > 0:
                original_sample = df[col].dropna().head(3).tolist()
                df[col] = numeric_values
                new_sample = df[col].dropna().head(3).tolist()
                if str(original_sample) != str(new_sample):
                    changes.append(
                        {
                            "column": col,
                            "type": "numeric_conversion",
                            "before": original_sample,
                            "after": new_sample,
                            "count": int(numeric_count),
                        }
                    )
        except Exception:
            pass

    sex_col = next((col for col in df.columns if col.lower() in ["sex", "gender"]), None)
    if sex_col:
        is_numeric_coded = all(
            str(v).strip() in ["1", "2", "3", "0"] or pd.isna(v) for v in df[sex_col]
        )
        if is_numeric_coded:
            original_values = df[sex_col].copy()

            def convert_sex_code(x):
                if pd.isna(x):
                    return x
                str_key = str(x).strip()
                if str_key in sex_mapping:
                    return sex_mapping[str_key]
                try:
                    int_key = int(x)
                    if int_key in sex_mapping:
                        return sex_mapping[int_key]
                except (ValueError, TypeError):
                    pass
                return x

            df[sex_col] = df[sex_col].map(convert_sex_code)
            changes.append(
                {
                    "column": sex_col,
                    "type": "sex_code_conversion",
                    "mapping": {str(k): v for k, v in sex_mapping.items()},
                    "before": original_values.value_counts().to_dict(),
                    "after": df[sex_col].value_counts().to_dict(),
                }
            )

    if not changes:
        return {
            "success": True,
            "message": "No changes needed - file is already BIDS compliant",
            "changes": [],
        }

    if dry_run:
        return {
            "success": True,
            "message": f"Would fix {len(changes)} issues",
            "changes": changes,
            "dry_run": True,
        }

    df.to_csv(
        path,
        sep="\t",
        index=False,
        na_rep="n/a",
        quoting=csv.QUOTE_NONE,
        escapechar="\\",
    )
    return {
        "success": True,
        "message": f"Fixed {len(changes)} issues in {path.name}",
        "changes": changes,
        "file_path": str(path),
    }
