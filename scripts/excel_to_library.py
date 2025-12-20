#!/usr/bin/env python3
"""
Excel to JSON Library Converter
-------------------------------
Converts a data dictionary (Excel) into a library of PRISM-compliant JSON sidecars.

Usage:
    python scripts/excel_to_library.py --excel metadata.xlsx --output survey_library

Excel Format Requirements:
    - Column 1: Variable Name (e.g., ADS1, BDI_1)
    - Column 2: Question/Description (e.g., "I feel sad")
    - Column 3: Scale/Levels (e.g., "1=Not at all; 2=Very much")

The script groups variables into surveys based on their prefix (e.g., ADS1 -> ads).
"""

import argparse
import json
import os
import re
import sys

import pandas as pd

# Standard metadata for known instruments
# You can extend this dictionary or load it from an external file
SURVEY_METADATA = {
    "ads": {
        "OriginalName": "Allgemeine Depressionsskala (ADS)",
        "Citation": "Hautzinger, M., & Bailer, M. (1993). Allgemeine Depressionsskala (ADS). Göttingen: Hogrefe.",
    },
    "bdi": {
        "OriginalName": "Beck Depression Inventory (BDI-II)",
        "Citation": "Beck, A. T., Steer, R. A., & Brown, G. K. (1996). Manual for the Beck Depression Inventory-II. San Antonio, TX: Psychological Corporation.",
    },
    # Add more here...
}


ID_ALIASES = {"item_id", "id", "code", "variable", "var", "name", "variablename"}
QUESTION_ALIASES = {"item", "question", "description", "text"}
SCALE_ALIASES = {"scale", "scaling", "levels", "options", "answers"}
GROUP_ALIASES = {"group", "survey", "section", "domain", "category"}
ALIAS_ALIASES = {"alias_of", "alias", "canonical", "duplicate_of", "merge_into"}
SESSION_ALIASES = {"session", "visit", "wave", "timepoint"}
RUN_ALIASES = {"run", "repeat"}


def clean_variable_name(name):
    """Clean variable name to be used as a key."""
    return str(name).strip()


def extract_prefix(var_name):
    """
    Extract prefix from variable name to group surveys.
    Example: ADS1 -> ADS, BDI_1 -> BDI
    """
    match = re.match(r"([a-zA-Z]+)", var_name)
    if match:
        return match.group(1)
    return "unknown"


def parse_levels(scale_str):
    """
    Parse scale string into a dictionary.
    Format expected: "1=Label A; 2=Label B" or "1=Label A, 2=Label B"
    """
    if pd.isna(scale_str):
        return None

    levels = {}
    parts = re.split(r"[;,]\s*", str(scale_str))
    for part in parts:
        if "=" in part:
            val, label = part.split("=", 1)
            levels[val.strip()] = label.strip()
    return levels if levels else None


def detect_language(texts):
    """Tiny heuristic: flag German if umlauts/ß or common tokens are present."""
    combined = " ".join([t for t in texts if isinstance(t, str)]).lower()
    if not combined.strip():
        return "en"

    if re.search(r"[\u00e4\u00f6\u00fc\u00df]", combined):
        return "de"

    german_tokens = [
        " nicht ",
        " oder ",
        " keine ",
        " w\u00e4hrend ",
        " immer ",
        " selten ",
    ]
    padded = f" {combined} "
    if any(tok in padded for tok in german_tokens):
        return "de"

    return "en"


def process_excel(
    excel_file, output_dir, participants_prefix=None, participants_output=None
):
    print(f"Loading metadata from {excel_file}...")
    try:
        df_meta = pd.read_excel(excel_file, header=None)
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        sys.exit(1)

    # Detect header row and column indices
    header_row = df_meta.iloc[0].tolist()
    header_lower = [str(v).strip().lower() for v in header_row]

    def norm(s):
        return str(s).replace(" ", "").replace("_", "").lower()

    def find_idx(aliases):
        aliases_norm = {norm(a) for a in aliases}
        for i, val in enumerate(header_lower):
            if norm(val) in aliases_norm:
                return i
        return None

    id_idx = find_idx(ID_ALIASES)
    question_idx = find_idx(QUESTION_ALIASES)
    scale_idx = find_idx(SCALE_ALIASES)
    group_idx = find_idx(GROUP_ALIASES)
    alias_idx = find_idx(ALIAS_ALIASES)
    session_idx = find_idx(SESSION_ALIASES)
    run_idx = find_idx(RUN_ALIASES)

    header_detected = any(
        idx is not None
        for idx in [
            id_idx,
            question_idx,
            scale_idx,
            group_idx,
            alias_idx,
            session_idx,
            run_idx,
        ]
    )
    if header_detected:
        print("Detected header row (named columns). Using column names.")
        data_rows = df_meta.iloc[1:]
    else:
        data_rows = df_meta
        # Fallback to positional columns
        id_idx = 0
        question_idx = 1
        scale_idx = 2
        group_idx = 3
        alias_idx = 4
        session_idx = 5
        run_idx = 6

    surveys = {}

    def get_val(row, idx):
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    print("Processing metadata...")
    for _, row in data_rows.iterrows():
        var_name = clean_variable_name(get_val(row, id_idx))
        question = get_val(row, question_idx)
        scale = get_val(row, scale_idx)
        manual_group = get_val(row, group_idx)
        alias_of = get_val(row, alias_idx)
        session_hint = get_val(row, session_idx)
        run_hint = get_val(row, run_idx)

        if var_name.lower() == "nan" or not var_name:
            continue

        if pd.notna(manual_group) and str(manual_group).strip():
            manual_clean = clean_variable_name(manual_group).lower()
            if manual_clean in {"disable", "skip", "omit", "ignore"}:
                continue  # Explicitly skip this item
            prefix = manual_clean
        else:
            prefix = extract_prefix(var_name).lower()

        if prefix not in surveys:
            surveys[prefix] = {}

        description = str(question).strip() if pd.notna(question) else var_name
        # Remove brackets [] and their content from description (common in codebooks)
        description = re.sub(r"\[.*?\]", "", description).strip()

        entry = {"Description": description}

        if pd.notna(alias_of) and str(alias_of).strip():
            entry["AliasOf"] = clean_variable_name(alias_of)

        if pd.notna(session_hint) and str(session_hint).strip():
            session_clean = str(session_hint).strip().lower().replace(" ", "")
            session_clean = session_clean.replace("session", "ses-")
            session_clean = session_clean.replace("visit", "ses-")
            if session_clean in {"t1", "wave1", "visit1"}:
                session_clean = "ses-1"
            elif session_clean in {"t2", "wave2", "visit2"}:
                session_clean = "ses-2"
            elif session_clean in {"t3", "wave3", "visit3"}:
                session_clean = "ses-3"
            if not session_clean.startswith("ses-"):
                session_clean = f"ses-{session_clean}"
            entry["SessionHint"] = session_clean

        if pd.notna(run_hint) and str(run_hint).strip():
            run_clean = str(run_hint).strip().lower().replace(" ", "")
            if not run_clean.startswith("run-"):
                run_clean = f"run-{run_clean}"
            entry["RunHint"] = run_clean

        levels = parse_levels(scale)
        if levels:
            entry["Levels"] = levels

        surveys[prefix][var_name] = entry

    # Generate JSON Sidecars
    print(f"Generating JSON sidecars in {output_dir}...")
    os.makedirs(output_dir, exist_ok=True)
    if participants_output and participants_output != output_dir:
        os.makedirs(participants_output, exist_ok=True)

    for prefix, variables in surveys.items():
        is_participants = (
            participants_prefix is not None and prefix == participants_prefix
        )

        texts_for_lang = []
        for item in variables.values():
            desc = item.get("Description") if isinstance(item, dict) else None
            if isinstance(desc, str):
                texts_for_lang.append(desc)
            levels = item.get("Levels") if isinstance(item, dict) else None
            if isinstance(levels, dict):
                texts_for_lang.extend(
                    [v for v in levels.values() if isinstance(v, str)]
                )

        language = detect_language(texts_for_lang)

        if is_participants:
            sidecar = {}
        else:
            meta = SURVEY_METADATA.get(prefix, {})
            original_name = meta.get("OriginalName", f"{prefix} Questionnaire")
            citation = meta.get("Citation", "")
            domain = meta.get("Domain", "")
            keywords = meta.get("Keywords", [])

            sidecar = {
                "Technical": {
                    "StimulusType": "Questionnaire",
                    "FileFormat": "tsv",
                    "SoftwarePlatform": "Legacy/Imported",
                    "Language": language,
                    "Respondent": "self",
                    "ResponseType": ["paper-pencil"],
                },
                "Study": {
                    "TaskName": prefix,
                    "OriginalName": original_name,
                    "Version": "1.0",
                    "Description": f"Imported {prefix} survey data",
                },
                "Metadata": {
                    "SchemaVersion": "1.0.0",
                    "CreationDate": pd.Timestamp.now().strftime("%Y-%m-%d"),
                    "Creator": "excel_to_library.py",
                },
            }

            if citation:
                sidecar["Study"]["Citation"] = citation
            if domain:
                sidecar["Study"]["Domain"] = domain
            if keywords:
                sidecar["Study"]["Keywords"] = keywords

        sidecar.update(variables)

        if is_participants:
            json_filename = "participants.json"
            target_dir = participants_output or output_dir
        else:
            json_filename = f"survey-{prefix}.json"
            target_dir = output_dir

        json_path = os.path.join(target_dir, json_filename)
        with open(json_path, "w") as f:
            json.dump(sidecar, f, indent=2)
            print(f"  - Created {json_path}")

    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert Excel data dictionary to PRISM JSON library."
    )
    parser.add_argument(
        "--excel", required=True, help="Path to the Excel metadata file."
    )
    parser.add_argument(
        "--output", default="survey_library", help="Output directory for JSON files."
    )
    parser.add_argument(
        "--participants-prefix",
        default=None,
        help="Prefix to treat as participants.json (e.g., 'demo').",
    )
    parser.add_argument(
        "--participants-output",
        default=None,
        help="Directory where participants.json should be written (defaults to --output).",
    )

    args = parser.parse_args()
    process_excel(
        args.excel,
        args.output,
        participants_prefix=args.participants_prefix,
        participants_output=args.participants_output,
    )
