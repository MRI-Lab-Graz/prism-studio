"""
BIDS validator integration for PRISM.
Handles running both modern (Deno) and legacy (Node/Python) BIDS validators.
"""

import os
import json
import subprocess
from typing import List, Tuple, Set, Optional


def run_bids_validator(
    root_dir: str, 
    verbose: bool = False,
    placeholders: Optional[Set[str]] = None,
    structure_only: bool = False
) -> List[Tuple[str, str]]:
    """
    Run the standard BIDS validator CLI and return issues.
    
    Args:
        root_dir: Path to the dataset root
        verbose: Enable verbose output
        placeholders: Set of relative paths to placeholder files to ignore content errors for
        structure_only: Whether this is a structure-only upload (suppress content errors)
        
    Returns:
        List of (severity, message) tuples
    """
    issues = []
    print("\n🤖 Running standard BIDS Validator...")

    placeholders = placeholders or set()
    placeholder_basenames = {os.path.basename(p) for p in placeholders}

    # Content-related issues that are expected in structure-only validation.
    content_error_codes = {
        "EMPTY_FILE",
        "NIFTI_HEADER_UNREADABLE",
        "QUICK_TEST_FAILED",
    }
    
    # PRISM modalities that should be ignored by BIDS
    prism_ignore_folders = {
        "eyetracking", "physiological", "physio", "survey", "biometrics", "metadata"
    }

    def _looks_like_content_file(location: str) -> bool:
        if not location:
            return False
        loc = location.replace("\\", "/").lower()
        return loc.endswith(
            (
                ".nii",
                ".nii.gz",
                ".eeg",
                ".fif",
                ".dat",
                ".tsv.gz",
            )
        )

    def _is_placeholder_location(location: str) -> bool:
        if not placeholders or not location:
            return False
        loc = location.replace("\\", "/").lstrip("/")
        if loc in placeholders:
            return True
        # Deno validator sometimes reports only the filename.
        if os.path.basename(loc) in placeholder_basenames:
            return True
        # And sometimes reports a path prefix/suffix; handle partial match.
        return any(loc.endswith(p) or p.endswith(loc) for p in placeholders)

    if verbose and structure_only:
        print("   ℹ️  Detected structure-only upload. Will suppress BIDS data-content checks.")

    if placeholders and verbose:
        print(
            f"   ℹ️  Found {len(placeholders)} placeholder files. Will suppress content errors for these."
        )

    # 1. Try Deno-based validator (modern)
    try:
        # Check if deno is installed
        subprocess.run(
            ["deno", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("   Using Deno-based validator (jsr:@bids/validator)")

        # Run Deno validator
        process = subprocess.run(
            ["deno", "run", "-ERWN", "jsr:@bids/validator", root_dir, "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if process.stdout:
            try:
                bids_report = json.loads(process.stdout)

                # Handle Deno validator structure
                issue_list = []
                if "issues" in bids_report:
                    if (
                        isinstance(bids_report["issues"], dict)
                        and "issues" in bids_report["issues"]
                    ):
                        issue_list = bids_report["issues"]["issues"]
                    elif isinstance(bids_report["issues"], list):
                        issue_list = bids_report["issues"]

                for issue in issue_list:
                    code = issue.get("code", "UNKNOWN_CODE")
                    location = issue.get("location", "")

                    # Suppress content-related errors for placeholders (and for structure-only uploads).
                    if code in content_error_codes:
                        if _is_placeholder_location(location):
                            continue
                        if structure_only and _looks_like_content_file(location):
                            continue

                    # Filter out NOT_INCLUDED for known PRISM modalities
                    if code == "NOT_INCLUDED":
                        is_prism_modality = False
                        loc_lower = location.lower()
                        for folder in prism_ignore_folders:
                            if f"/{folder}/" in loc_lower or loc_lower.endswith(f"/{folder}/"):
                                is_prism_modality = True
                                break
                        if is_prism_modality:
                            if verbose:
                                print(f"   ℹ️  Silencing '{code}' for PRISM modality: {location}")
                            continue

                    severity = issue.get("severity", "warning").upper()
                    level = "ERROR" if severity == "ERROR" else "WARNING"

                    sub_code = issue.get("subCode", "")
                    issue_msg = issue.get("issueMessage", "")

                    msg = f"[BIDS] {code}"
                    if sub_code:
                        msg += f".{sub_code}"

                    if issue_msg:
                        msg += f": {issue_msg}"

                    if location:
                        msg += f"\n    Location: {location}"
                    
                    # Try to extract a specific file path from the location
                    issue_file = None
                    if location:
                        # Deno location starts with /
                        if location.startswith("/"):
                            issue_file = os.path.join(root_dir, location.lstrip("/"))
                        else:
                            issue_file = os.path.join(root_dir, location)
                    
                    if issue_file:
                        issues.append((level, msg, issue_file))
                    else:
                        issues.append((level, msg))

                return issues

            except json.JSONDecodeError:
                print("   ❌ Error: Could not parse Deno BIDS validator JSON output.")
                issues.append(
                    (
                        "ERROR",
                        "BIDS Validator (Deno) ran but output could not be parsed.",
                    )
                )
                return issues
        else:
            print(
                f"   ❌ Error: Deno validator produced no output. Stderr: {process.stderr}"
            )
            issues.append(("ERROR", f"BIDS Validator (Deno) failed: {process.stderr}"))
            return issues

    except (subprocess.CalledProcessError, FileNotFoundError):
        # Deno not found, fall back to legacy
        pass

    # 2. Try legacy Python/Node CLI validator
    print("   ⚠️  Deno not found. Falling back to legacy 'bids-validator' CLI...")
    try:
        # Check if bids-validator is installed
        subprocess.run(
            ["bids-validator", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Run validation
        process = subprocess.run(
            ["bids-validator", root_dir, "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if process.stdout:
            try:
                bids_report = json.loads(process.stdout)

                # Map BIDS issues to our format ("LEVEL", "Message")
                for issue_type in ["errors", "warnings"]:
                    level = "ERROR" if issue_type == "errors" else "WARNING"
                    for issue in bids_report.get("issues", {}).get(issue_type, []):
                        key = issue.get("key", "")
                        
                        # Filter files for this issue
                        filtered_files = []
                        for file in issue.get("files", []):
                            file_obj = file.get("file")
                            if file_obj:
                                file_path = file_obj.get("relativePath", "")
                                # Suppress content-related errors for placeholders
                                if key in content_error_codes and file_path.lstrip("/") in placeholders:
                                    continue
                                if structure_only and key == "EMPTY_FILE" and file_path.lower().endswith((".nii", ".nii.gz", ".tsv.gz")):
                                    continue
                                filtered_files.append(file_path)
                        
                        if not filtered_files and issue.get("files"):
                            continue
                            
                        # Filter out NOT_INCLUDED for known PRISM modalities
                        if key == "NOT_INCLUDED":
                            is_prism_folder = False
                            for f_path in filtered_files:
                                for prism_folder in prism_ignore_folders:
                                    if f"/{prism_folder}/" in f_path.lower() or f_path.lower().endswith(f"/{prism_folder}/"):
                                        is_prism_folder = True
                                        break
                            if is_prism_folder:
                                continue

                        msg = f"[BIDS] {issue.get('reason')} ({key})"
                        first_file = None
                        for f_path in filtered_files:
                            msg += f"\n    File: {f_path}"
                            if not first_file:
                                first_file = os.path.join(root_dir, f_path.lstrip("/"))
                        
                        if first_file:
                            issues.append((level, msg, first_file))
                        else:
                            issues.append((level, msg))

            except json.JSONDecodeError:
                if verbose:
                    print("Warning: Could not parse BIDS validator JSON output.")
                issues.append(
                    (
                        "INFO",
                        "BIDS Validator ran but output could not be parsed. See console for details if verbose.",
                    )
                )

        if process.returncode != 0 and not issues:
            issues.append(("ERROR", f"BIDS Validator failed to run: {process.stderr}"))

    except (subprocess.CalledProcessError, FileNotFoundError):
        issues.append(
            ("WARNING", "bids-validator not found or failed to run. Is it installed?")
        )

    return issues
