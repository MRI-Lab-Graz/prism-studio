"""
BIDS integration utilities for prism.
Handles compatibility with standard BIDS tools and apps.
"""

import os

# Standard BIDS modalities (folders)
# Based on BIDS Specification v1.9.0
STANDARD_BIDS_FOLDERS = {
    "anat",
    "func",
    "dwi",
    "fmap",  # MRI
    "beh",  # Behavior
    "eeg",
    "ieeg",
    "meg",  # Electrophysiology
    "pet",  # PET
    "micr",  # Microscopy
    "nirs",  # fNIRS
    "motion",  # Motion
}


# Extra non-BIDS artifacts that can confuse BIDS apps/validators.
EXTRA_BIDSIGNORE_RULES = {
    "*_report_*.txt",
    "prism_summary.json",
    "validation_report.json",
    ".upload_manifest.json",
    "project.json",
    "contributors.json",
    "CITATION.cff",
    ".prismrc.json",
    "survey/",  # Root survey definition folder
    "derivatives/",  # Explicitly ignore derivatives if needed
    "*_survey.*",  # Ignore any survey related data/sidecars
    "*_biometrics.*",  # Ignore any biometrics related data/sidecars
    "*_physio.*",  # Ignore any custom physio data/sidecars
    "*_eyetrack.*",  # Ignore any custom eyetracking data/sidecars
    "task-*_survey.json",  # Root task templates
    "task-*_biometrics.json",
    "task-*_physio.json",
    "task-*_eyetrack.json",
}


def check_and_update_bidsignore(dataset_root, supported_modalities):
    """
    Ensure that custom modalities are listed in .bidsignore
    to prevent standard BIDS validators/apps from crashing.

    Args:
        dataset_root (str): Path to dataset root
        supported_modalities (list): List of modality names supported by prism

    Returns:
        list: List of rules added to .bidsignore
    """
    # Skip creating .bidsignore in special directories (library folders, not datasets)
    dataset_root_name = os.path.basename(os.path.normpath(dataset_root))
    skip_folders = {
        "official",
        "library",
        "survey_library",
        "templates",
        "reference_templates",
    }

    if dataset_root_name in skip_folders:
        return []

    # Also skip if path contains these folders (e.g., /path/to/official/something)
    normalized_path = os.path.normpath(dataset_root)
    if any(
        f"/{folder}/" in f"/{normalized_path}/"
        or normalized_path.endswith(f"/{folder}")
        for folder in skip_folders
    ):
        return []

    bidsignore_path = os.path.join(dataset_root, ".bidsignore")

    # Determine which modalities are non-standard
    non_standard = [m for m in supported_modalities if m not in STANDARD_BIDS_FOLDERS]

    # Always ensure we include these common PRISM/non-BIDS folders just in case
    # they are not in the current supported_modalities list
    prism_folders = {
        "eyetracking",
        "physiological",
        "physio",
        "survey",
        "biometrics",
        "eeg",
        "metadata",
        "events",
    }
    for pf in prism_folders:
        if pf not in STANDARD_BIDS_FOLDERS and pf not in non_standard:
            non_standard.append(pf)

    # Read existing .bidsignore
    existing_rules = set()
    if os.path.exists(bidsignore_path):
        try:
            with open(bidsignore_path, "r") as f:
                existing_rules = {line.strip() for line in f if line.strip()}
        except IOError:
            pass  # Can't read, maybe permission?

    # Check what needs to be added
    added_rules = []

    # We use the pattern "modality/" to match directories of that name anywhere.
    # This is standard .gitignore syntax which .bidsignore follows.
    # We also add "**/modality/" as a fallback for some validator versions.
    needed_rules = set(EXTRA_BIDSIGNORE_RULES)
    for m in non_standard:
        needed_rules.add(f"{m}/")
        needed_rules.add(f"**/{m}/")

    if not needed_rules:
        return []

    # Filter out rules that already exist
    rules_to_add = [r for r in needed_rules if r not in existing_rules]

    if rules_to_add:
        try:
            mode = "a" if os.path.exists(bidsignore_path) else "w"

            # Check if we need a newline prefix
            needs_newline = False
            if mode == "a" and os.path.getsize(bidsignore_path) > 0:
                with open(bidsignore_path, "rb") as rb:
                    try:
                        rb.seek(-1, 2)
                        last_char = rb.read(1)
                        if last_char != b"\n":
                            needs_newline = True
                    except OSError:
                        # File might be empty or other issue
                        pass

            with open(bidsignore_path, mode) as f:
                # Add header if creating new
                if mode == "w":
                    f.write("# .bidsignore created by prism\n")
                    f.write(
                        "# Ignores custom modalities to ensure BIDS-App compatibility\n"
                    )
                elif needs_newline:
                    f.write("\n")

                if mode == "a":
                    f.write("\n# Added by prism\n")

                for rule in sorted(rules_to_add):
                    f.write(f"{rule}\n")
                    added_rules.append(rule)

        except IOError as e:
            print(f"⚠️ Warning: Could not update .bidsignore: {e}")

    return added_rules
