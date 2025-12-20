"""
Runner module exposing the canonical validate_dataset function.
This is a refactor target so other tools (web UI) can import the function
without executing the top-level CLI script.
"""

import os
import sys
import subprocess
import json
from typing import Callable, Optional

from jsonschema import validate, ValidationError

from schema_manager import load_all_schemas
from schema_manager import validate_schema_version
from validator import DatasetValidator, MODALITY_PATTERNS, BIDS_MODALITIES, resolve_sidecar_path
from stats import DatasetStats
from system_files import filter_system_files
from bids_integration import check_and_update_bidsignore

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)


# Type alias for progress callback
# callback(current: int, total: int, message: str, file_path: Optional[str])
ProgressCallback = Callable[[int, int, str, Optional[str]], None]


def validate_dataset(
    root_dir,
    verbose=False,
    schema_version=None,
    run_bids=False,
    run_prism=True,
    progress_callback: Optional[ProgressCallback] = None,
):
    """Main dataset validation function (refactored from prism.py)

    Args:
        root_dir: Root directory of the dataset
        verbose: Enable verbose output
        schema_version: Schema version to use (e.g., 'stable', 'v0.1', '0.1')
        run_bids: Whether to run the standard BIDS validator
        run_prism: Whether to run PRISM-specific validation
        progress_callback: Optional callback for progress updates.
                           Called as callback(current, total, message, file_path)

    Returns: (issues, stats)
    """
    issues = []
    stats = DatasetStats()

    def report_progress(
        current: int, total: int, message: str, file_path: Optional[str] = None
    ):
        """Report progress if callback is provided"""
        if progress_callback:
            progress_callback(current, total, message, file_path)

    report_progress(0, 100, "Loading schemas...")

    # Load schemas with specified version
    schema_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schemas")
    schemas = load_all_schemas(schema_dir, version=schema_version)

    if verbose:
        version_tag = schema_version or "stable"
        print(f"📋 Loaded {len(schemas)} schemas (version: {version_tag})")
        print(f"📁 Validating PRISM modalities: {list(MODALITY_PATTERNS.keys())}")
        print(f"📁 Pass-through BIDS modalities: anat, func, fmap, dwi, eeg (use BIDS validator for these)")


    # Initialize validator
    validator = DatasetValidator(schemas)

    report_progress(5, 100, "Checking dataset description...")

    # Check for dataset description
    dataset_desc_path = os.path.join(root_dir, "dataset_description.json")
    if not os.path.exists(dataset_desc_path):
        if run_prism:
            issues.append(("ERROR", "Missing dataset_description.json", dataset_desc_path))
    else:
        # Validate dataset_description.json against the dataset_description schema (if present)
        try:
            with open(dataset_desc_path, "r", encoding="utf-8") as f:
                dataset_desc = json.load(f)

            if run_prism:
                dataset_schema = schemas.get("dataset_description")
                if dataset_schema:
                    version_issues = validate_schema_version(dataset_desc, dataset_schema)
                    for level, msg in version_issues:
                        issues.append((level, msg, dataset_desc_path))
                    
                    validate(instance=dataset_desc, schema=dataset_schema)
        except json.JSONDecodeError as e:
            if run_prism:
                issues.append(("ERROR", f"dataset_description.json is not valid JSON: {e}", dataset_desc_path))
        except ValidationError as e:
            if run_prism:
                issues.append(("ERROR", f"dataset_description.json schema error: {e.message}", dataset_desc_path))
        except Exception as e:
            if run_prism:
                issues.append(("ERROR", f"Error processing dataset_description.json: {e}", dataset_desc_path))

    report_progress(10, 100, "Checking BIDS compatibility...")

    # Check and update .bidsignore for BIDS-App compatibility
    try:
        added_rules = check_and_update_bidsignore(
            root_dir, list(MODALITY_PATTERNS.keys())
        )
        if added_rules and verbose:
            print("ℹ️  Updated .bidsignore for BIDS-App compatibility:")
            for rule in added_rules:
                print(f"   + {rule}")
    except Exception as e:
        if verbose:
            print(f"⚠️  Failed to update .bidsignore: {e}")

    report_progress(15, 100, "Scanning subjects...")

    # Walk through subject directories
    all_items = os.listdir(root_dir)
    filtered_items = filter_system_files(all_items)

    if verbose and len(all_items) != len(filtered_items):
        ignored_count = len(all_items) - len(filtered_items)
        print(f"🗑️  Ignored {ignored_count} system files (.DS_Store, Thumbs.db, etc.)")

    # Find all subject directories
    subject_dirs = [
        (item, os.path.join(root_dir, item))
        for item in filtered_items
        if os.path.isdir(os.path.join(root_dir, item)) and item.startswith("sub-")
    ]

    total_subjects = len(subject_dirs)

    for idx, (item, item_path) in enumerate(subject_dirs):
        # Progress from 20% to 90% during subject validation
        progress_pct = 20 + int((idx / max(total_subjects, 1)) * 70)
        report_progress(progress_pct, 100, f"Validating {item}...", item_path)

        subject_issues = _validate_subject(item_path, item, validator, stats, root_dir, run_prism=run_prism)
        issues.extend(subject_issues)

    report_progress(90, 100, "Checking consistency...")

    # Check cross-subject consistency
    consistency_warnings = stats.check_consistency()
    issues.extend(consistency_warnings)

    # If no subjects were discovered, this usually means the user pointed
    # the validator at the wrong directory (or the dataset is empty).
    # Treat this as an error so users get a non-zero exit status.
    if len(stats.subjects) == 0:
        issues.append(
            (
                "ERROR",
                "No subjects found in dataset. Did you point the validator at the dataset root?",
            )
        )

    # Run standard BIDS validator if requested
    if run_bids:
        report_progress(92, 100, "Running BIDS validator...")
        bids_issues = _run_bids_validator(root_dir, verbose)
        issues.extend(bids_issues)

    report_progress(100, 100, "Validation complete")
    return issues, stats


def _get_placeholder_files(root_dir):
    """Get list of placeholder files from upload manifest if it exists."""
    manifest_path = os.path.join(root_dir, ".upload_manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
                return {f["path"] for f in manifest.get("placeholder_files", [])}
        except Exception:
            pass
    return set()


def _get_upload_manifest(root_dir):
    """Load upload manifest if present (web structure-only uploads)."""
    manifest_path = os.path.join(root_dir, ".upload_manifest.json")
    if not os.path.exists(manifest_path):
        return None
    try:
        with open(manifest_path, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def _run_bids_validator(root_dir, verbose=False):
    """Run the standard BIDS validator CLI"""
    issues = []
    print("\n🤖 Running standard BIDS Validator...")

    # Load placeholders to filter out content-related issues (expected in structure-only uploads)
    manifest = _get_upload_manifest(root_dir)
    upload_type = (manifest or {}).get("upload_type")
    structure_only = upload_type == "structure_only"

    placeholders = _get_placeholder_files(root_dir)
    placeholder_basenames = {os.path.basename(p) for p in placeholders}

    # Content-related issues that are expected in structure-only validation.
    # We keep structural compliance errors, but suppress data-content checks.
    # Note: BVAL/BVEC are excluded here because we now upload them; 
    # they are only suppressed if they are explicitly placeholders.
    content_error_codes = {
        "EMPTY_FILE",
        "NIFTI_HEADER_UNREADABLE",
        "QUICK_TEST_FAILED",
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
    deno_found = False
    try:
        # Check if deno is installed
        subprocess.run(
            ["deno", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deno_found = True
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

                    severity = issue.get("severity", "warning").upper()
                    # Map severity to our levels
                    if severity == "ERROR":
                        level = "ERROR"
                    else:
                        level = "WARNING"

                    sub_code = issue.get("subCode", "")
                    issue_msg = issue.get("issueMessage", "")

                    msg = f"[BIDS] {code}"
                    if sub_code:
                        msg += f".{sub_code}"

                    if issue_msg:
                        msg += f": {issue_msg}"

                    if location:
                        msg += f"\n    Location: {location}"

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
            # Deno ran but produced no output (likely an error)
            print(
                f"   ❌ Error: Deno validator produced no output. Stderr: {process.stderr}"
            )
            issues.append(("ERROR", f"BIDS Validator (Deno) failed: {process.stderr}"))
            return issues

    except (subprocess.CalledProcessError, FileNotFoundError):
        # Deno not found
        pass

    # If we found Deno but crashed, we returned above.
    # If we are here, Deno was not found.

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
                for issue in bids_report.get("issues", {}).get("errors", []):
                    key = issue.get("key", "")
                    
                    # Filter files for this issue
                    filtered_files = []
                    content_error_keys = {"EMPTY_FILE", "NIFTI_HEADER_UNREADABLE", "QUICK_TEST_FAILED"}
                    for file in issue.get("files", []):
                        file_obj = file.get("file")
                        if file_obj:
                            file_path = file_obj.get("relativePath", "")
                            # Suppress content-related errors for placeholders
                            if key in content_error_keys and file_path.lstrip("/") in placeholders:
                                continue
                            if structure_only and key == "EMPTY_FILE" and file_path.lower().endswith((".nii", ".nii.gz", ".tsv.gz")):
                                continue
                            filtered_files.append(file_path)
                    
                    if not filtered_files and issue.get("files"):
                        continue

                    msg = f"[BIDS] {issue.get('reason')} ({key})"
                    for file_path in filtered_files:
                        msg += f"\n    File: {file_path}"
                    issues.append(("ERROR", msg))

                for issue in bids_report.get("issues", {}).get("warnings", []):
                    key = issue.get("key", "")
                    
                    # Filter files for this issue
                    filtered_files = []
                    content_error_keys = {"EMPTY_FILE", "NIFTI_HEADER_UNREADABLE", "QUICK_TEST_FAILED"}
                    for file in issue.get("files", []):
                        file_obj = file.get("file")
                        if file_obj:
                            file_path = file_obj.get("relativePath", "")
                            # Suppress content-related errors for placeholders
                            if key in content_error_keys and file_path.lstrip("/") in placeholders:
                                continue
                            if structure_only and key == "EMPTY_FILE" and file_path.lower().endswith((".nii", ".nii.gz", ".tsv.gz")):
                                continue
                            filtered_files.append(file_path)
                    
                    if not filtered_files and issue.get("files"):
                        continue

                    msg = f"[BIDS] {issue.get('reason')} ({key})"
                    for file_path in filtered_files:
                        msg += f"\n    File: {file_path}"
                    issues.append(("WARNING", msg))

            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
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


def _validate_subject(subject_dir, subject_id, validator, stats, root_dir, run_prism=True):
    issues = []

    all_items = os.listdir(subject_dir)
    filtered_items = filter_system_files(all_items)

    for item in filtered_items:
        item_path = os.path.join(subject_dir, item)
        if os.path.isdir(item_path):
            # Check for empty directory
            dir_contents = os.listdir(item_path)
            filtered_contents = filter_system_files(dir_contents)

            if not filtered_contents:
                if run_prism:
                    issues.append(("ERROR", f"Empty directory found: {item}", item_path))
                continue

            if item.startswith("ses-"):
                issues.extend(
                    _validate_session(
                        item_path, subject_id, item, validator, stats, root_dir, run_prism=run_prism
                    )
                )
            elif item in MODALITY_PATTERNS or item in BIDS_MODALITIES:
                issues.extend(
                    _validate_modality_dir(
                        item_path, subject_id, None, item, validator, stats, root_dir, run_prism=run_prism
                    )
                )

    return issues


def _validate_session(session_dir, subject_id, session_id, validator, stats, root_dir, run_prism=True):
    issues = []

    all_items = os.listdir(session_dir)
    filtered_items = filter_system_files(all_items)

    for item in filtered_items:
        item_path = os.path.join(session_dir, item)
        if os.path.isdir(item_path):
            # Check for empty directory
            dir_contents = os.listdir(item_path)
            filtered_contents = filter_system_files(dir_contents)

            if not filtered_contents:
                if run_prism:
                    issues.append(("ERROR", f"Empty directory found: {item}", item_path))
                continue

            if item in MODALITY_PATTERNS or item in BIDS_MODALITIES:
                issues.extend(
                    _validate_modality_dir(
                        item_path,
                        subject_id,
                        session_id,
                        item,
                        validator,
                        stats,
                        root_dir,
                        run_prism=run_prism,
                    )
                )

    return issues


def _validate_modality_dir(
    modality_dir, subject_id, session_id, modality, validator, stats, root_dir, run_prism=True
):
    issues = []

    def _effective_modality_for_file(dir_modality, filename):
        # In standard BIDS, events live inside func/ as *_events.tsv.
        # Prism extends events metadata requirements via the `events` schema.
        lower = filename.lower()
        if lower.endswith("_events.tsv") or lower.endswith("_events.tsv.gz"):
            return "events"
        return dir_modality

    all_files = os.listdir(modality_dir)
    filtered_files = filter_system_files(all_files)

    for fname in filtered_files:
        file_path = os.path.join(modality_dir, fname)
        if os.path.isfile(file_path):
            # Extract task from filename
            task = None
            if "_task-" in fname:
                import re

                task_match = re.search(r"_task-([A-Za-z0-9]+)(?:_|$)", fname)
                if task_match:
                    task = task_match.group(1)

            # Add to stats
            stats.add_file(subject_id, session_id, modality, task, fname)

            if run_prism:
                # Validate filename
                filename_issues = validator.validate_filename(
                    fname, modality, subject_id=subject_id, session_id=session_id
                )
                for level, msg in filename_issues:
                    issues.append((level, msg, file_path))

                # Validate sidecar if not JSON file itself
                if not fname.endswith(".json"):
                    sidecar_modality = _effective_modality_for_file(modality, fname)
                    sidecar_issues = validator.validate_sidecar(
                        file_path, sidecar_modality, root_dir
                    )
                    for level, msg in sidecar_issues:
                        issues.append((level, msg, file_path))

                # Extract OriginalName for stats
                try:
                    sidecar_path = resolve_sidecar_path(file_path, root_dir)
                    if os.path.exists(sidecar_path):
                        with open(sidecar_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if "Study" in data and "OriginalName" in data["Study"]:
                                original_name = data["Study"]["OriginalName"]
                                if modality == "survey" and task:
                                    stats.add_description("survey", task, original_name)
                                elif modality == "biometrics" and task:
                                    stats.add_description(
                                        "biometrics", task, original_name
                                    )
                                elif task:
                                    stats.add_description("task", task, original_name)
                except Exception:
                    pass  # Don't fail validation if stats extraction fails

                # Validate data content
                content_issues = validator.validate_data_content(
                    file_path, modality, root_dir
                )
                for level, msg in content_issues:
                    issues.append((level, msg, file_path))

    return issues
