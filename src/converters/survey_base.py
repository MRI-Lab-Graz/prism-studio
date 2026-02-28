"""Base survey library helpers shared by converter modules."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


def load_survey_library(library_path: str) -> Dict[str, Dict[str, Any]]:
    """Load all survey JSONs from the library."""
    schemas: Dict[str, Dict[str, Any]] = {}
    if not os.path.exists(library_path):
        return schemas

    for filename in os.listdir(library_path):
        if filename.endswith(".json") and filename.startswith("survey-"):
            task_name = filename.replace("survey-", "").replace(".json", "")
            filepath = os.path.join(library_path, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as json_file:
                    schemas[task_name] = json.load(json_file)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
    return schemas


def get_allowed_values(col_def: Any) -> Optional[List[str]]:
    """Return allowed values for a column, expanding numeric levels where appropriate."""
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
            if max_level - min_level < 100:
                return [str(i) for i in range(min_level, max_level + 1)]
            return level_keys

    return None


__all__ = ["load_survey_library", "get_allowed_values"]
