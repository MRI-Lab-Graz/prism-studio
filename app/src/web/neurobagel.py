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
        "session_id": "session_id",
        "age": "age",
        "sex": "biological_sex",
        "gender": "biological_sex",
        "group": "participant_group",
        "diagnosis": "diagnosis",
        "handedness": "handedness",
        "education": "education_level",
        "education_level": "education_level",
    }

    # Categorical value mappings with controlled vocabulary URIs (SNOMED CT, NCIT, and PATO)
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
        "group": {
            "CTRL": {
                "label": "Healthy Control",
                "description": "Healthy control participant",
                "uri": "ncit:C94342",
            },
            "HC": {
                "label": "Healthy Control",
                "description": "Healthy control participant",
                "uri": "ncit:C94342",
            },
            "CONTROL": {
                "label": "Healthy Control",
                "description": "Healthy control participant",
                "uri": "ncit:C94342",
            },
            "PAT": {
                "label": "Patient",
                "description": "Patient group (diagnosis unspecified)",
                "uri": "ncit:C16960",
            },
            "PATIENT": {
                "label": "Patient",
                "description": "Patient group (diagnosis unspecified)",
                "uri": "ncit:C16960",
            },
            "ADHD": {
                "label": "ADHD",
                "description": "Attention deficit hyperactivity disorder",
                "uri": "snomed:406506008",
            },
            "ASD": {
                "label": "Autism Spectrum Disorder",
                "description": "Autism spectrum disorder",
                "uri": "snomed:408856003",
            },
            "MDD": {
                "label": "Major Depressive Disorder",
                "description": "Major depressive disorder",
                "uri": "snomed:370143000",
            },
            "SZ": {
                "label": "Schizophrenia",
                "description": "Schizophrenia",
                "uri": "snomed:58214004",
            },
            "SCZ": {
                "label": "Schizophrenia",
                "description": "Schizophrenia",
                "uri": "snomed:58214004",
            },
            "BD": {
                "label": "Bipolar Disorder",
                "description": "Bipolar disorder",
                "uri": "snomed:13746004",
            },
            "PD": {
                "label": "Parkinson's Disease",
                "description": "Parkinson's disease",
                "uri": "snomed:49049000",
            },
            "AD": {
                "label": "Alzheimer's Disease",
                "description": "Alzheimer's disease",
                "uri": "snomed:26929004",
            },
            "MCI": {
                "label": "Mild Cognitive Impairment",
                "description": "Mild cognitive impairment",
                "uri": "snomed:386806002",
            },
            "OCD": {
                "label": "Obsessive-Compulsive Disorder",
                "description": "Obsessive-compulsive disorder",
                "uri": "snomed:191736004",
            },
            "PTSD": {
                "label": "Post-Traumatic Stress Disorder",
                "description": "Post-traumatic stress disorder",
                "uri": "snomed:47505003",
            },
            "GAD": {
                "label": "Generalized Anxiety Disorder",
                "description": "Generalized anxiety disorder",
                "uri": "snomed:21897009",
            },
        },
        "diagnosis": {
            # Same as group - use the same controlled vocabulary
            "CTRL": {
                "label": "Healthy Control",
                "description": "Healthy control participant",
                "uri": "ncit:C94342",
            },
            "HC": {
                "label": "Healthy Control",
                "description": "Healthy control participant",
                "uri": "ncit:C94342",
            },
            "ADHD": {
                "label": "ADHD",
                "description": "Attention deficit hyperactivity disorder",
                "uri": "snomed:406506008",
            },
            "ASD": {
                "label": "Autism Spectrum Disorder",
                "description": "Autism spectrum disorder",
                "uri": "snomed:408856003",
            },
            "MDD": {
                "label": "Major Depressive Disorder",
                "description": "Major depressive disorder",
                "uri": "snomed:370143000",
            },
            "SZ": {
                "label": "Schizophrenia",
                "description": "Schizophrenia",
                "uri": "snomed:58214004",
            },
            "SCZ": {
                "label": "Schizophrenia",
                "description": "Schizophrenia",
                "uri": "snomed:58214004",
            },
            "BD": {
                "label": "Bipolar Disorder",
                "description": "Bipolar disorder",
                "uri": "snomed:13746004",
            },
            "PD": {
                "label": "Parkinson's Disease",
                "description": "Parkinson's disease",
                "uri": "snomed:49049000",
            },
            "AD": {
                "label": "Alzheimer's Disease",
                "description": "Alzheimer's disease",
                "uri": "snomed:26929004",
            },
            "MCI": {
                "label": "Mild Cognitive Impairment",
                "description": "Mild cognitive impairment",
                "uri": "snomed:386806002",
            },
            "OCD": {
                "label": "Obsessive-Compulsive Disorder",
                "description": "Obsessive-compulsive disorder",
                "uri": "snomed:191736004",
            },
            "PTSD": {
                "label": "Post-Traumatic Stress Disorder",
                "description": "Post-traumatic stress disorder",
                "uri": "snomed:47505003",
            },
            "GAD": {
                "label": "Generalized Anxiety Disorder",
                "description": "Generalized anxiety disorder",
                "uri": "snomed:21897009",
            },
        },
        "education_level": {
            "1": {
                "label": "Less than High School",
                "description": "Did not complete high school",
                "uri": "ncit:C17781",
            },
            "2": {
                "label": "High School Diploma",
                "description": "Completed high school or equivalent",
                "uri": "ncit:C17782",
            },
            "3": {
                "label": "Some College",
                "description": "Some college or associate degree",
                "uri": "ncit:C17783",
            },
            "4": {
                "label": "Bachelor's Degree",
                "description": "Bachelor's degree",
                "uri": "ncit:C17784",
            },
            "5": {
                "label": "Graduate Degree",
                "description": "Master's, doctoral, or professional degree",
                "uri": "ncit:C17785",
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
            if "Unit" in col_data:
                aug_col["unit"] = col_data["Unit"]
            elif "Units" in col_data:  # Legacy support
                aug_col["unit"] = col_data["Units"]
        else:
            aug_col["data_type"] = "text"

        augmented["properties"][col_name] = aug_col

    return augmented
