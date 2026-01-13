"""
Base utilities for Survey conversion in PRISM.
Shared logic for CSV and LimeSurvey conversion.
"""

import os
import json
from typing import Dict, Any, List, Optional


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
                if set(full_range).issuperset(set(level_keys)):
                    return full_range
        return level_keys

    return None
