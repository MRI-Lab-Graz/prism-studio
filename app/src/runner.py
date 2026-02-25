"""
Runner module exposing the canonical validate_dataset function.
This is a refactor target so other tools (web UI) can import the function
without executing the top-level CLI script.
"""

import os
import sys
import json
from typing import Callable, Optional

from jsonschema import validate, ValidationError

from schema_manager import load_all_schemas
from schema_manager import validate_schema_version
from validator import (
    DatasetValidator,
    MODALITY_PATTERNS,
    BIDS_MODALITIES,
    resolve_sidecar_path,
)
from stats import DatasetStats
from system_files import filter_system_files
from bids_integration import check_and_update_bidsignore
from bids_validator import run_bids_validator as _run_bids_validator_cli

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
    library_path=None,
    progress_callback: Optional[ProgressCallback] = None,
):
    """Main dataset validation function (refactored from prism.py)

    Args:
        root_dir: Root directory of the dataset
        verbose: Enable verbose output
        schema_version: Schema version to use (e.g., 'stable', 'v0.1', '0.1')
        run_bids: Whether to run the standard BIDS validator
        run_prism: Whether to run PRISM-specific validation
        library_path: Optional path to a template library for sidecar resolution
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

    # Canonical PRISM location: BIDS root is the provided project folder.
    root_dir = os.path.abspath(root_dir)

    report_progress(0, 100, "Loading schemas...")

    # Load schemas with specified version
    schema_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schemas")
    schemas = load_all_schemas(schema_dir, version=schema_version)

    if verbose:
        version_tag = schema_version or "stable"
        print(f"📋 Loaded {len(schemas)} schemas (version: {version_tag})")
        print(f"📁 Validating PRISM modalities: {list(MODALITY_PATTERNS.keys())}")
        print(
            "📁 Pass-through BIDS modalities: anat, func, fmap, dwi, eeg (use BIDS validator for these)"
        )

    # Initialize validator
    validator = DatasetValidator(schemas, library_path=library_path)

    report_progress(5, 100, "Checking dataset description...")

    # Check for dataset description
    dataset_desc_path = os.path.join(root_dir, "dataset_description.json")
    if not os.path.exists(dataset_desc_path):
        if run_prism:
            issues.append(
                ("ERROR", "Missing dataset_description.json", dataset_desc_path)
            )
    else:
        # Register file in stats
        stats.register_file("dataset_description.json")

        # Validate dataset_description.json against the dataset_description schema (if present)
        try:
            with open(dataset_desc_path, "r", encoding="utf-8") as f:
                dataset_desc = json.load(f)

            if run_prism:
                dataset_schema = schemas.get("dataset_description")
                if dataset_schema:
                    version_issues = validate_schema_version(
                        dataset_desc, dataset_schema
                    )
                    for level, msg in version_issues:
                        issues.append((level, msg, dataset_desc_path))

                    validate(instance=dataset_desc, schema=dataset_schema)
        except json.JSONDecodeError as e:
            if run_prism:
                issues.append(
                    (
                        "ERROR",
                        f"dataset_description.json is not valid JSON: {e}",
                        dataset_desc_path,
                    )
                )
        except ValidationError as e:
            if run_prism:
                # Format message to be more descriptive (include field path)
                field_path = " -> ".join([str(p) for p in e.path])
                prefix = f"{field_path}: " if field_path else ""
                issues.append(
                    (
                        "ERROR",
                        f"dataset_description.json schema error: {prefix}{e.message}",
                        dataset_desc_path,
                    )
                )
        except Exception as e:
            if run_prism:
                issues.append(
                    (
                        "ERROR",
                        f"Error processing dataset_description.json: {e}",
                        dataset_desc_path,
                    )
                )

    # Check for other top-level files
    for top_file in [
        "participants.tsv",
        "participants.json",
        "README",
        "README.md",
        "CHANGES",
    ]:
        if os.path.exists(os.path.join(root_dir, top_file)):
            stats.register_file(top_file)

    # Check for recipes/derivatives (BIDS-derivatives style)
    for folder_name in ["recipes", "derivatives"]:
        folder_dir = os.path.join(root_dir, folder_name)
        if os.path.exists(folder_dir) and os.path.isdir(folder_dir):
            for sub in sorted(os.listdir(folder_dir)):
                sub_path = os.path.join(folder_dir, sub)
                if os.path.isdir(sub_path) and not sub.startswith("."):
                    sub_desc = os.path.join(sub_path, "dataset_description.json")
                    if not os.path.exists(sub_desc):
                        issues.append(
                            (
                                "WARNING",
                                f"{folder_name.capitalize()} dataset '{sub}' is missing dataset_description.json. "
                                f"BIDS-{folder_name} should have their own description file.",
                                sub_path,
                            )
                        )

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

        subject_issues = _validate_subject(
            item_path, item, validator, stats, root_dir, run_prism=run_prism
        )
        issues.extend(subject_issues)

    report_progress(90, 100, "Checking consistency...")

    # Check cross-subject consistency
    consistency_warnings = stats.check_consistency()
    issues.extend(consistency_warnings)

    # Procedure validation: cross-check declared sessions/tasks vs. on-disk data
    if run_prism:
        project_json = os.path.join(root_dir, "project.json")
        if os.path.exists(project_json):
            from procedure_validator import validate_procedure
            from pathlib import Path as _Path

            procedure_issues = validate_procedure(_Path(root_dir), _Path(root_dir))
            issues.extend(procedure_issues)

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
    # Load placeholders to filter out content-related issues (expected in structure-only uploads)
    manifest = _get_upload_manifest(root_dir)
    upload_type = (manifest or {}).get("upload_type")
    structure_only = upload_type == "structure_only"
    placeholders = _get_placeholder_files(root_dir)

    return _run_bids_validator_cli(
        root_dir,
        verbose=verbose,
        placeholders=placeholders,
        structure_only=structure_only,
    )


def _validate_subject(
    subject_dir, subject_id, validator, stats, root_dir, run_prism=True
):
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
                    issues.append(
                        ("ERROR", f"Empty directory found: {item}", item_path)
                    )
                continue

            if item.startswith("ses-"):
                issues.extend(
                    _validate_session(
                        item_path,
                        subject_id,
                        item,
                        validator,
                        stats,
                        root_dir,
                        run_prism=run_prism,
                    )
                )
            elif item in MODALITY_PATTERNS or item in BIDS_MODALITIES:
                issues.extend(
                    _validate_modality_dir(
                        item_path,
                        subject_id,
                        None,
                        item,
                        validator,
                        stats,
                        root_dir,
                        run_prism=run_prism,
                    )
                )

    return issues


def _validate_session(
    session_dir, subject_id, session_id, validator, stats, root_dir, run_prism=True
):
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
                    issues.append(
                        ("ERROR", f"Empty directory found: {item}", item_path)
                    )
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
    modality_dir,
    subject_id,
    session_id,
    modality,
    validator,
    stats,
    root_dir,
    run_prism=True,
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
                    sidecar_issue_path = resolve_sidecar_path(
                        file_path, root_dir, validator.library_path
                    )
                    for level, msg in sidecar_issues:
                        issues.append((level, msg, sidecar_issue_path))

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
                                elif modality == "eyetracking" and task:
                                    stats.add_description(
                                        "eyetracking", task, original_name
                                    )
                                elif modality in ["physio", "physiological"] and task:
                                    stats.add_description("physio", task, original_name)
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
