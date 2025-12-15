"""
BIDS integration utilities for prism-validator.
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
#
# `MRI-Lab-Graz/check_repo` is a generic repository QA tool; it doesn't validate
# PRISM/BIDS datasets, but it does write a timestamped report file in the
# working directory (e.g., "<name>_report_<timestamp>.txt"). If users run it in
# a dataset root, that report shouldn't be considered part of the dataset by
# BIDS tooling.
EXTRA_BIDSIGNORE_RULES = {
    "*_report_*.txt",
}


def check_and_update_bidsignore(dataset_root, supported_modalities):
    """
    Ensure that custom modalities are listed in .bidsignore
    to prevent standard BIDS validators/apps from crashing.

    Args:
        dataset_root (str): Path to dataset root
        supported_modalities (list): List of modality names supported by prism-validator

    Returns:
        list: List of rules added to .bidsignore
    """
    bidsignore_path = os.path.join(dataset_root, ".bidsignore")

    # Determine which modalities are non-standard
    non_standard = [m for m in supported_modalities if m not in STANDARD_BIDS_FOLDERS]

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
    needed_rules = set(EXTRA_BIDSIGNORE_RULES)
    needed_rules.update({f"{m}/" for m in non_standard})

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
                    f.write("# .bidsignore created by prism-validator\n")
                    f.write(
                        "# Ignores custom modalities to ensure BIDS-App compatibility\n"
                    )
                elif needs_newline:
                    f.write("\n")

                if mode == "a":
                    f.write("\n# Added by prism-validator\n")

                for rule in sorted(rules_to_add):
                    f.write(f"{rule}\n")
                    added_rules.append(rule)

        except IOError as e:
            print(f"⚠️ Warning: Could not update .bidsignore: {e}")

    return added_rules
