#!/usr/bin/env python3
"""
Generate a hybrid BIDS/PRISM demo dataset for prism-validator testing.
"""

import os
import json

import shutil
import gzip
import csv
import random

ROOT_DIR = "prism_demo"


def create_directory(path):
    os.makedirs(path, exist_ok=True)


def create_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def create_tsv(filepath, headers, rows):
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(headers)
        writer.writerows(rows)


def create_dummy_gzip(filepath):
    """Create a dummy gzipped TSV file"""
    content = "onset\tduration\tvalue\n0\t1\t0.5\n"
    with gzip.open(filepath, "wt", encoding="utf-8") as f:
        f.write(content)


def main():
    print(f"🚀 Creating demo dataset in '{ROOT_DIR}'...")

    # 1. Clean up existing directory
    if os.path.exists(ROOT_DIR):
        print(f"   - Removing existing {ROOT_DIR}...")
        shutil.rmtree(ROOT_DIR)
    create_directory(ROOT_DIR)

    # 2. Dataset Description (BIDS Standard)
    dataset_description = {
        "Name": "PRISM Demo Dataset",
        "BIDSVersion": "1.6.0",
        "DatasetType": "raw",
        "License": "CC0",
        "Authors": ["Prism-Validator Team", "Another Author"],
        "Acknowledgements": "Created for testing purposes",
        "HowToAcknowledge": "Please cite this dataset",
        "Funding": ["Grant 123"],
        "ReferencesAndLinks": ["https://github.com/MRI-Lab-Graz/prism-validator"],
        "DatasetDOI": "10.0.0.0/prism-demo",
    }
    create_json(os.path.join(ROOT_DIR, "dataset_description.json"), dataset_description)

    # Create README
    with open(os.path.join(ROOT_DIR, "README"), "w") as f:
        f.write("This is a demo dataset for PRISM validator testing.")

    # 3. Participants
    participants_headers = ["participant_id", "age", "sex", "group"]
    participants_rows = [
        ["sub-01", "25", "M", "control"],
        ["sub-02", "30", "F", "experimental"],
        ["sub-03", "22", "F", "control"],
    ]
    create_tsv(
        os.path.join(ROOT_DIR, "participants.tsv"),
        participants_headers,
        participants_rows,
    )

    participants_json = {
        "age": {"Description": "Age of the participant", "Units": "years"},
        "sex": {
            "Description": "Sex of the participant",
            "Levels": {"M": "male", "F": "female"},
        },
        "group": {
            "Description": "Experimental group",
            "Levels": {
                "control": "Control Group",
                "experimental": "Experimental Group",
            },
        },
    }
    create_json(os.path.join(ROOT_DIR, "participants.json"), participants_json)

    # 4. Create Subjects
    subjects = ["sub-01", "sub-02", "sub-03"]

    for sub in subjects:
        print(f"   - Processing {sub}...")

        # Define paths
        ses = "ses-01"
        base_dir = os.path.join(ROOT_DIR, sub, ses)
        beh_dir = os.path.join(base_dir, "beh")
        survey_dir = os.path.join(base_dir, "survey")

        # Derivatives path
        deriv_dir = os.path.join(ROOT_DIR, "derivatives", "cubios", sub, ses, "beh")

        create_directory(beh_dir)
        create_directory(survey_dir)
        create_directory(deriv_dir)

        # --- A. Physiological Data (BIDS Standard in 'beh') ---
        # File: sub-XX_ses-01_task-rest_physio.tsv.gz
        physio_filename = f"{sub}_{ses}_task-rest_physio"
        create_dummy_gzip(os.path.join(beh_dir, f"{physio_filename}.tsv.gz"))

        # Sidecar: sub-XX_ses-01_task-rest_physio.json
        physio_metadata = {
            "TaskName": "rest",
            "SamplingFrequency": 1000,
            "StartTime": 0,
            "Columns": ["cardiac", "trigger"],
            "Manufacturer": "Biopac",
            "ManufacturerModelName": "MP160",
        }
        create_json(os.path.join(beh_dir, f"{physio_filename}.json"), physio_metadata)

        # --- B. Survey Data (PRISM Specific) ---
        # File: sub-XX_ses-01_task-questionnaire_survey.tsv
        survey_filename = f"{sub}_{ses}_task-questionnaire_survey"
        # Wide format: one row per subject
        survey_headers = [
            "q1",
            "q1_responseTime",
            "q2",
            "q2_responseTime",
            "q3",
            "q3_responseTime",
        ]
        survey_rows = [["5", "1.2", "3", "0.8", "4", "1.5"]]
        create_tsv(
            os.path.join(survey_dir, f"{survey_filename}.tsv"),
            survey_headers,
            survey_rows,
        )

        # Sidecar: sub-XX_ses-01_task-questionnaire_survey.json (PRISM Schema)
        survey_metadata = {
            "Technical": {
                "StimulusType": "Questionnaire",
                "FileFormat": "tsv",
                "SoftwarePlatform": "LimeSurvey",
                "Language": "en",
                "Respondent": "self",
            },
            "Study": {
                "TaskName": "questionnaire",
                "OriginalName": "Demographics Questionnaire",
                "StudyID": "PRISM_001",
            },
            "Metadata": {
                "SchemaVersion": "1.0.0",
                "CreationDate": "2025-01-01",
                "Creator": "Script",
            },
            "q1": {
                "Description": "Question 1",
                "DataType": "integer",
                "MinValue": 1,
                "MaxValue": 5,
            },
            "q1_responseTime": {"Description": "Response time for q1", "Units": "s"},
            "q2": {
                "Description": "Question 2",
                "DataType": "integer",
                "MinValue": 1,
                "MaxValue": 5,
            },
            "q2_responseTime": {"Description": "Response time for q2", "Units": "s"},
            "q3": {
                "Description": "Question 3",
                "DataType": "integer",
                "MinValue": 1,
                "MaxValue": 5,
            },
            "q3_responseTime": {"Description": "Response time for q3", "Units": "s"},
        }
        create_json(
            os.path.join(survey_dir, f"{survey_filename}.json"), survey_metadata
        )

        # --- C. Derivatives (HRV Analysis) ---
        # File: sub-XX_ses-01_task-rest_desc-hrv_physio.tsv
        hrv_filename = f"{sub}_{ses}_task-rest_desc-hrv_physio"
        hrv_headers = ["mean_rr", "sdnn", "rmssd", "lf_hf_ratio"]
        hrv_rows = [
            [
                f"{random.uniform(800, 1000):.2f}",
                f"{random.uniform(30, 100):.2f}",
                f"{random.uniform(20, 80):.2f}",
                f"{random.uniform(0.5, 2.0):.2f}",
            ]
        ]
        create_tsv(
            os.path.join(deriv_dir, f"{hrv_filename}.tsv"), hrv_headers, hrv_rows
        )

        # Sidecar
        hrv_metadata = {
            "Description": "Heart Rate Variability metrics derived from ECG",
            "Sources": [
                os.path.join(
                    f"sub-{sub}", f"ses-{ses}", "beh", f"{physio_filename}.tsv.gz"
                )
            ],
            "Software": {"Name": "Cubios", "Version": "3.0"},
        }
        create_json(os.path.join(deriv_dir, f"{hrv_filename}.json"), hrv_metadata)

    print("✅ Demo dataset created successfully!")
    print(f"📂 Location: {os.path.abspath(ROOT_DIR)}")


if __name__ == "__main__":
    main()
