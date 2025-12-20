"""
NeuroBagel integration for PRISM.
Handles fetching and augmenting NeuroBagel participants dictionary.
"""

import requests
from functools import lru_cache
from typing import Any, Dict

@lru_cache(maxsize=8)
def fetch_neurobagel_participants() -> Any:
    """Fetch NeuroBagel participants dictionary and cache it."""
    url = "https://neurobagel.org/data_models/dictionaries/participants.json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None

def augment_neurobagel_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Augment raw NeuroBagel data with standardized variable mappings and categorical details.

    Transforms flat NeuroBagel data into a hierarchical structure with:
    - Standardized variable mappings (e.g., sex -> biological_sex)
    - Data type classification (categorical vs continuous)
    - Categorical level details with URIs and descriptions
    - Column-level metadata
    """
    if not raw_data or not raw_data.get("properties"):
        return raw_data

    # Mapping of column names to standardized variables
    standardized_mappings = {
        "participant_id": "participant_id",
        "age": "age",
        "sex": "biological_sex",
        "group": "participant_group",
        "handedness": "handedness",
    }

    # Categorical value mappings with controlled vocabulary URIs (SNOMED CT and PATO)
    # URIs are stored in shortened form for export (e.g., 'snomed:248153007')
    categorical_vocabularies = {
        "sex": {
            "M": {
                "label": "Male",
                "description": "Male biological sex",
                "uri": "snomed:248153007",
            },
            "F": {
                "label": "Female",
                "description": "Female biological sex",
                "uri": "snomed:248152002",
            },
            "O": {
                "label": "Other",
                "description": "Other biological sex",
                "uri": "snomed:447964000",
            },
        },
        "handedness": {
            "L": {
                "label": "Left",
                "description": "Left-handed",
                "uri": "snomed:87622008",
            },
            "R": {
                "label": "Right",
                "description": "Right-handed",
                "uri": "snomed:78791000",
            },
            "A": {
                "label": "Ambidextrous",
                "description": "Ambidextrous",
                "uri": "snomed:16022009",
            },
        },
    }

    # Augmented structure
    augmented = {"properties": {}}

    for col_name, col_data in raw_data.get("properties", {}).items():
        aug_col = {
            "description": col_data.get("description", ""),
            "original_data": col_data,
        }

        # Add standardized variable mapping
        if col_name in standardized_mappings:
            aug_col["standardized_variable"] = standardized_mappings[col_name]

        # Infer data type from Levels (if present, it's categorical)
        if "Levels" in col_data and isinstance(col_data["Levels"], dict):
            aug_col["data_type"] = "categorical"

            # Augment with vocabulary if available
            if col_name in categorical_vocabularies:
                aug_col["levels"] = {}
                for level_key, level_label in col_data["Levels"].items():
                    if level_key in categorical_vocabularies[col_name]:
                        aug_col["levels"][level_key] = categorical_vocabularies[
                            col_name
                        ][level_key]
                    else:
                        # Fallback: use provided label (no URI)
                        aug_col["levels"][level_key] = {
                            "label": (
                                level_label
                                if isinstance(level_label, str)
                                else str(level_key)
                            ),
                            "description": f"Value: {level_key}",
                            "uri": None,
                        }
            else:
                # No vocabulary available, use raw levels (no URIs)
                aug_col["levels"] = {
                    k: {"label": v, "description": f"Value: {k}", "uri": None}
                    for k, v in col_data["Levels"].items()
                }
        elif col_name in ["age"]:
            aug_col["data_type"] = "continuous"
            if "Units" in col_data:
                aug_col["unit"] = col_data["Units"]
        else:
            aug_col["data_type"] = "text"

        augmented["properties"][col_name] = aug_col

    return augmented
