"""
Runner module exposing the canonical validate_dataset function.
This is a refactor target so other tools (web UI) can import the function
without executing the top-level CLI script.
"""
import os

from .schema_manager import load_all_schemas
from .validator import DatasetValidator, MODALITY_PATTERNS
from .stats import DatasetStats
from .reporting import print_dataset_summary, print_validation_results


def validate_dataset(root_dir, verbose=False):
    """Main dataset validation function (refactored from psycho-validator.py)

    Returns: (issues, stats)
    """
    issues = []
    stats = DatasetStats()

    # Load schemas
    schema_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schemas')
    schemas = load_all_schemas(schema_dir)

    if verbose:
        print(f"📋 Loaded {len(schemas)} schemas")
        print(f"📁 Scanning modalities: {list(MODALITY_PATTERNS.keys())}")

    # Initialize validator
    validator = DatasetValidator(schemas)

    # Check for dataset description
    dataset_desc_path = os.path.join(root_dir, "dataset_description.json")
    if not os.path.exists(dataset_desc_path):
        issues.append(("ERROR", "Missing dataset_description.json"))

    # Walk through subject directories
    for item in os.listdir(root_dir):
        item_path = os.path.join(root_dir, item)
        if os.path.isdir(item_path) and item.startswith("sub-"):
            subject_issues = _validate_subject(item_path, item, validator, stats, root_dir)
            issues.extend(subject_issues)

    # Check cross-subject consistency
    consistency_warnings = stats.check_consistency()
    issues.extend(consistency_warnings)

    return issues, stats


def _validate_subject(subject_dir, subject_id, validator, stats, root_dir):
    issues = []

    for item in os.listdir(subject_dir):
        item_path = os.path.join(subject_dir, item)
        if os.path.isdir(item_path):
            if item.startswith("ses-"):
                issues.extend(_validate_session(item_path, subject_id, item, validator, stats, root_dir))
            elif item in MODALITY_PATTERNS:
                issues.extend(_validate_modality_dir(item_path, subject_id, None, item, validator, stats, root_dir))

    return issues


def _validate_session(session_dir, subject_id, session_id, validator, stats, root_dir):
    issues = []

    for item in os.listdir(session_dir):
        item_path = os.path.join(session_dir, item)
        if os.path.isdir(item_path) and item in MODALITY_PATTERNS:
            issues.extend(_validate_modality_dir(item_path, subject_id, session_id, item, validator, stats, root_dir))

    return issues


def _validate_modality_dir(modality_dir, subject_id, session_id, modality, validator, stats, root_dir):
    issues = []

    for fname in os.listdir(modality_dir):
        file_path = os.path.join(modality_dir, fname)
        if os.path.isfile(file_path):
            # Extract task from filename
            task = None
            if "_task-" in fname:
                import re
                task_match = re.search(r'_task-([A-Za-z0-9]+)(?:_|$)', fname)
                if task_match:
                    task = task_match.group(1)

            # Add to stats
            stats.add_file(subject_id, session_id, modality, task, fname)

            # Validate filename
            filename_issues = validator.validate_filename(fname, modality)
            issues.extend(filename_issues)

            # Validate sidecar if not JSON file itself
            if not fname.endswith('.json'):
                sidecar_issues = validator.validate_sidecar(file_path, modality, root_dir)
                issues.extend(sidecar_issues)

    return issues
