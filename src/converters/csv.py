import argparse
import json
import os
import sys

import pandas as pd

try:
    from src.converters.survey_base import (
        load_survey_library as load_schemas,
        get_allowed_values,
    )
except (ImportError, ValueError):
    # Fallbacks for direct script execution.
    from survey_base import (  # type: ignore
        load_survey_library as _load_schemas,
        get_allowed_values as _get_allowed_values,
    )

    load_schemas = _load_schemas
    get_allowed_values = _get_allowed_values


IGNORE_PARTICIPANT_COLS = {
    "submitdate",
    "lastpage",
    "startlanguage",
    "seed",
    "startdate",
    "datestamp",
    "token",
    "language",
}


def _allowed_values(col_def):
    """Return allowed values for a column, expanding numeric level endpoints to full range."""
    return get_allowed_values(col_def)


def _ensure_participants(
    df, id_col, output_root, library_path, candidates=None, participant_schema=None
):
    """Create participants.tsv/json. Prefer explicit participant schema or library participants.json; otherwise infer."""
    os.makedirs(output_root, exist_ok=True)

    participants_json_path = None
    if library_path:
        lib_path_obj = os.path.abspath(library_path)
        candidates_paths = [os.path.join(lib_path_obj, "participants.json")]

        parent = os.path.dirname(lib_path_obj)
        for _ in range(3):
            if not parent:
                break
            candidates_paths.append(os.path.join(parent, "participants.json"))
            next_parent = os.path.dirname(parent)
            if next_parent == parent:
                break
            parent = next_parent

        for p in candidates_paths:
            if os.path.isfile(p):
                participants_json_path = p
                break

    inferred = False
    used_schema = False

    if participant_schema:
        part_schema = participant_schema
        used_schema = True
    elif not participants_json_path:
        cols = candidates or []
        cols = [c for c in cols if c != id_col]
        if not cols:
            return
        part_schema = {
            "participant_id": {"Description": "Participant identifier (sub-<label>)"}
        }
        for col in cols:
            part_schema[col] = {"Description": f"Participant attribute '{col}'"}
        inferred = True
    else:
        with open(participants_json_path, "r", encoding="utf-8") as f:
            part_schema = json.load(f)

    print(
        "Generating participants.tsv using participant schema..."
        if (used_schema or not inferred)
        else "Generating inferred participants.tsv..."
    )
    try:
        part_vars = [
            k
            for k in part_schema.keys()
            if k
            not in ["Technical", "Study", "Metadata", "I18n", "Scoring", "Normative"]
        ]
        found_part_vars = [v for v in part_vars if v in df.columns]

        if id_col in found_part_vars:
            found_part_vars.remove(id_col)

        if found_part_vars:
            df_part = df.groupby(id_col)[found_part_vars].first().reset_index()
            df_part = df_part.rename(columns={id_col: "participant_id"})
            df_part["participant_id"] = df_part["participant_id"].apply(
                lambda x: f"sub-{x}" if not str(x).startswith("sub-") else str(x)
            )

            for col in found_part_vars:
                col_def = part_schema.get(col, {})
                allowed = _allowed_values(col_def)
                if allowed:
                    df_part[col] = df_part[col].apply(
                        lambda v: v if pd.isna(v) or str(v) in allowed else "n/a"
                    )

            part_tsv_path = os.path.join(output_root, "participants.tsv")
            df_part.to_csv(part_tsv_path, sep="\t", index=False)
            print(
                f"  - Created participants.tsv with {len(df_part)} subjects and {len(found_part_vars)} columns."
            )

            with open(
                os.path.join(output_root, "participants.json"), "w", encoding="utf-8"
            ) as f:
                json.dump(part_schema, f, indent=2)
        else:
            if inferred:
                print("  - No participant columns found to infer participants.tsv.")
            else:
                print("  - participants.json found but no matching columns in data.")
    except Exception as e:
        print(f"Error processing participants.tsv: {e}")


def process_data(csv_file, schemas, output_root, library_path):
    """Convert CSV data to BIDS TSV files based on JSON schemas."""
    print(f"Loading data from {csv_file}...")
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    process_dataframe(df, schemas, output_root, library_path)


def process_dataframe(
    df, schemas, output_root, library_path, session_override=None, run_override=None
):
    """Convert in-memory dataframe to BIDS TSV files based on JSON schemas."""
    os.makedirs(output_root, exist_ok=True)

    desc_path = os.path.join(output_root, "dataset_description.json")
    if not os.path.exists(desc_path):
        dataset_description = {
            "Name": "PRISM Dataset",
            "BIDSVersion": "1.10.1",
            "DatasetType": "raw",
            "License": "CC0",
            "Authors": [],
            "Acknowledgements": "Generated by PRISM Studio tools",
            "HowToAcknowledge": "Please cite the PRISM framework and original data authors.",
            "Funding": [],
            "ReferencesAndLinks": ["https://github.com/MRI-Lab-Graz/prism-studio"],
            "DatasetDOI": "",
            "GeneratedBy": [{"Name": "PRISM CSV Converter", "Version": "1.1.1"}],
            "HEDVersion": "8.2.0",
        }
        with open(desc_path, "w", encoding="utf-8") as f:
            json.dump(dataset_description, f, indent=2)

    id_cols = [
        c
        for c in df.columns
        if c.lower() in ["participant_id", "subject", "id", "sub_id", "participant"]
    ]
    if not id_cols:
        first_col = df.columns[0]
        if "id" in first_col.lower() or "sub" in first_col.lower():
            id_cols = [first_col]
        else:
            print(
                "Error: Could not find a participant ID column (e.g., 'participant_id', 'subject')."
            )
            return
    id_col = id_cols[0]
    print(f"Using '{id_col}' as participant ID column.")

    all_schema_vars = set()
    for schema in schemas.values():
        for k, v in schema.items():
            if k in ["Technical", "Study", "Metadata", "I18n", "Scoring", "Normative"]:
                continue
            all_schema_vars.add(k)
            if isinstance(v, dict):
                if "AliasOf" in v:
                    all_schema_vars.add(v["AliasOf"])
                if "Aliases" in v and isinstance(v["Aliases"], list):
                    for alias in v["Aliases"]:
                        all_schema_vars.add(alias)

    candidate_participant_cols = []
    for col in df.columns:
        lc = col.lower()
        if col == id_col:
            continue
        if col in all_schema_vars:
            continue
        if lc in IGNORE_PARTICIPANT_COLS or lc.startswith("_"):
            continue
        candidate_participant_cols.append(col)

    _ensure_participants(
        df,
        id_col,
        output_root,
        library_path,
        candidates=candidate_participant_cols,
        participant_schema=schemas.get("participant"),
    )

    global_metadata_cols = ["startlanguage"]

    for task_name, schema in schemas.items():
        print(f"Processing survey: {task_name}...")

        if task_name == "participant":
            print(
                "  - Skipping per-subject participants; handled via participants.tsv/json at dataset root."
            )
            continue

        survey_vars = [
            k
            for k in schema.keys()
            if k
            not in ["Technical", "Study", "Metadata", "I18n", "Scoring", "Normative"]
        ]

        canonical_for = {}
        session_hint = {}
        run_hint = {}
        canonical_order = []

        for var in survey_vars:
            alias_of = schema.get(var, {}).get("AliasOf")
            canon = alias_of if alias_of else var
            canonical_for[var] = canon
            if canon not in canonical_order:
                canonical_order.append(canon)
            if "SessionHint" in schema.get(var, {}):
                session_hint[var] = schema[var]["SessionHint"]
            if "RunHint" in schema.get(var, {}):
                run_hint[var] = schema[var]["RunHint"]

        var_session_hint = {}
        for var in survey_vars:
            hint = schema.get(var, {}).get("SessionHint")
            if hint:
                var_session_hint[var] = hint

        found_vars = [v for v in survey_vars if v in df.columns]

        if not found_vars:
            print(
                f"  - No data found for {task_name} (checked {len(survey_vars)} variables). Skipping."
            )
            continue

        print(f"  - Found {len(found_vars)} variables for {task_name}.")

        available_meta_cols = [c for c in global_metadata_cols if c in df.columns]

        for _, row in df.iterrows():
            sub_id = str(row[id_col])

            if not sub_id.startswith("sub-"):
                sub_id = f"sub-{sub_id}"

            base_ses = session_override or "ses-1"
            if "session" in df.columns:
                ses_val = str(row["session"])
                base_ses = f"ses-{ses_val}" if not ses_val.startswith("ses-") else ses_val

            base_run = run_override or "run-1"
            if "run" in df.columns:
                run_val = str(row["run"])
                base_run = f"run-{run_val}" if not run_val.startswith("run-") else run_val

            buckets = {}
            for var in found_vars:
                ses = var_session_hint.get(var, session_hint.get(var, base_ses))
                run = run_hint.get(var, base_run)
                buckets.setdefault((ses, run), []).append(var)

            for (ses_id, run_id), vars_in_bucket in buckets.items():
                out_dir = os.path.join(output_root, sub_id, ses_id, "survey")
                os.makedirs(out_dir, exist_ok=True)

                row_data = row[vars_in_bucket].to_dict()

                merged = {}
                for var, val in row_data.items():
                    canon = canonical_for.get(var, var)
                    if canon not in merged or (pd.isna(merged[canon]) and pd.notna(val)):
                        merged[canon] = val

                ordered_keys = [k for k in canonical_order if k in merged]
                clean_data = {}
                for k in ordered_keys:
                    val = merged[k]
                    if pd.isna(val):
                        clean_data[k] = "n/a"
                        continue

                    col_def = schema.get(k, {})
                    allowed = _allowed_values(col_def)
                    if allowed and str(val) not in allowed:
                        clean_data[k] = "n/a"
                    else:
                        clean_data[k] = val

                for meta_col in available_meta_cols:
                    val = row[meta_col]
                    if pd.notna(val):
                        clean_data[meta_col] = val
                    else:
                        clean_data[meta_col] = "n/a"

                df_task = pd.DataFrame([clean_data])

                run_suffix = ""
                if run_id and run_id != "run-1":
                    part = run_id.split("-", 1)[1] if "-" in run_id else run_id
                    run_suffix = f"_run-{part}"
                tsv_name = f"{sub_id}_{ses_id}_survey-{task_name}{run_suffix}.tsv"
                tsv_path = os.path.join(out_dir, tsv_name)

                df_task.to_csv(tsv_path, sep="\t", index=False)

        legacy_name = f"survey-{task_name}.json"
        legacy_path = os.path.join(output_root, legacy_name)

        for path in [legacy_path]:
            if not os.path.exists(path):
                clean_schema = {
                    k: v
                    for k, v in schema.items()
                    if k
                    in [
                        "Technical",
                        "Study",
                        "Metadata",
                        "I18n",
                        "Scoring",
                        "Normative",
                    ]
                    or (isinstance(v, dict) and "AliasOf" not in v)
                }
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(clean_schema, f, indent=2)

    print("Conversion complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert CSV data to BIDS TSVs using JSON schemas."
    )
    parser.add_argument("--csv", required=True, help="Path to the large CSV data file.")
    parser.add_argument(
        "--library",
        default="survey_library",
        help="Path to the folder containing survey-*.json files.",
    )
    parser.add_argument(
        "--output", default="PK01", help="Root directory of the dataset."
    )

    args = parser.parse_args()

    schemas = load_schemas(args.library)
    if not schemas:
        print("No schemas found. Exiting.")
        sys.exit(1)

    process_data(args.csv, schemas, args.output, args.library)