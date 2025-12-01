import pandas as pd
import json
import os
import sys
import argparse


def load_schemas(library_path):
    """Load all survey JSONs from the library."""
    schemas = {}
    if not os.path.exists(library_path):
        print(f"Warning: Library path {library_path} does not exist.")
        return schemas

    for f in os.listdir(library_path):
        if f.endswith(".json") and f.startswith("survey-"):
            # Extract task name: survey-ads.json -> ads
            task_name = f.replace("survey-", "").replace(".json", "")
            with open(os.path.join(library_path, f), "r") as jf:
                try:
                    schemas[task_name] = json.load(jf)
                except json.JSONDecodeError:
                    print(f"Error decoding {f}, skipping.")
    return schemas


def process_data(csv_file, schemas, output_root):
    """Convert CSV data to BIDS TSV files based on JSON schemas."""
    print(f"Loading data from {csv_file}...")
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Ensure output directories exist
    rawdata_dir = os.path.join(output_root, "rawdata")
    os.makedirs(rawdata_dir, exist_ok=True)

    # Identify participant ID column
    # Adjust this list based on your CSV conventions
    id_cols = [
        c
        for c in df.columns
        if c.lower() in ["participant_id", "subject", "id", "sub_id", "participant"]
    ]
    if not id_cols:
        # Fallback: check for first column if it looks like an ID
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

    # 0. Handle participants.tsv if participants.json exists
    participants_json_path = os.path.join(args.library, "participants.json")
    if os.path.exists(participants_json_path):
        print("Found participants.json, generating participants.tsv...")
        try:
            with open(participants_json_path, "r") as f:
                part_schema = json.load(f)

            # Identify columns to extract
            # Exclude metadata keys if present
            part_vars = [
                k
                for k in part_schema.keys()
                if k not in ["Technical", "Study", "Metadata"]
            ]
            found_part_vars = [v for v in part_vars if v in df.columns]

            if found_part_vars:
                # Group by ID to ensure one row per subject (taking the first value found)
                # This handles cases where the CSV might have multiple rows per subject (long format)
                df_part = df.groupby(id_col)[found_part_vars].first().reset_index()

                # Rename ID column to BIDS standard 'participant_id'
                df_part = df_part.rename(columns={id_col: "participant_id"})

                # Ensure 'sub-' prefix
                df_part["participant_id"] = df_part["participant_id"].apply(
                    lambda x: f"sub-{x}" if not str(x).startswith("sub-") else x
                )

                # Save TSV
                part_tsv_path = os.path.join(rawdata_dir, "participants.tsv")
                df_part.to_csv(part_tsv_path, sep="\t", index=False)
                print(
                    f"  - Created participants.tsv with {len(df_part)} subjects and {len(found_part_vars)} columns."
                )

                # Copy JSON sidecar
                with open(os.path.join(rawdata_dir, "participants.json"), "w") as f:
                    json.dump(part_schema, f, indent=2)
            else:
                print("  - participants.json found but no matching columns in CSV.")

        except Exception as e:
            print(f"Error processing participants.tsv: {e}")

    # Iterate over each defined survey schema
    for task_name, schema in schemas.items():
        print(f"Processing survey: {task_name}...")

        # 1. Identify variables belonging to this survey
        # Exclude standard metadata sections
        survey_vars = [
            k for k in schema.keys() if k not in ["Technical", "Study", "Metadata"]
        ]

        # 2. Find which of these variables exist in the CSV
        # We check for exact match, but you could add case-insensitive logic here
        found_vars = [v for v in survey_vars if v in df.columns]

        if not found_vars:
            print(
                f"  - No data found for {task_name} (checked {len(survey_vars)} variables). Skipping."
            )
            continue

        print(f"  - Found {len(found_vars)} variables for {task_name}.")

        # 3. Create TSV for each participant
        for _, row in df.iterrows():
            sub_id = str(row[id_col])

            # Normalize subject ID (ensure sub- prefix)
            if not sub_id.startswith("sub-"):
                sub_id = f"sub-{sub_id}"

            # Define session (default to ses-1 or extract from data if available)
            ses_id = "ses-1"
            if "session" in df.columns:
                ses_val = str(row["session"])
                ses_id = f"ses-{ses_val}" if not ses_val.startswith("ses-") else ses_val

            # Create directory structure: sub-XX/ses-YY/survey/
            # Note: PRISM/BIDS usually puts surveys in 'beh' or 'survey' folder?
            # BIDS standard is 'beh' for behavioral, but PRISM might use 'survey' if configured.
            # Using 'survey' based on previous context.
            out_dir = os.path.join(rawdata_dir, sub_id, ses_id, "survey")
            os.makedirs(out_dir, exist_ok=True)

            # Extract data for this task
            task_data = row[found_vars].to_dict()

            # Remove NaNs/empty values if desired, or keep them as "n/a"
            # BIDS prefers "n/a" for missing values in TSVs
            clean_data = {
                k: (v if pd.notna(v) else "n/a") for k, v in task_data.items()
            }

            # Create DataFrame for single row
            df_task = pd.DataFrame([clean_data])

            # Filename: sub-XX_ses-YY_task-NAME_beh.tsv
            tsv_name = f"{sub_id}_{ses_id}_task-{task_name}_beh.tsv"
            tsv_path = os.path.join(out_dir, tsv_name)

            df_task.to_csv(tsv_path, sep="\t", index=False)

        # 4. Ensure the JSON sidecar exists in the root (BIDS inheritance)
        # We copy it from the library to rawdata/survey-NAME.json
        root_json_name = f"survey-{task_name}.json"
        root_json_path = os.path.join(rawdata_dir, root_json_name)
        if not os.path.exists(root_json_path):
            with open(root_json_path, "w") as f:
                json.dump(schema, f, indent=2)

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

    process_data(args.csv, schemas, args.output)
