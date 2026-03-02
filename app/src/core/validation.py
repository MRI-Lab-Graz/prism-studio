"""Stable validation boundary for PRISM core.

This module intentionally keeps a narrow interface that downstream layers
consume instead of importing runner internals directly.
"""

import os
from typing import Any, Dict, Iterable, List, Tuple

try:
    from src.runner import validate_dataset as _validate_dataset
except ImportError:
    from runner import validate_dataset as _validate_dataset

try:
    from src.issues import tuple_to_issue, issues_to_dict, summarize_issues
except ImportError:
    from issues import tuple_to_issue, issues_to_dict, summarize_issues


def validate_dataset(*args, **kwargs):
    """Validate a dataset using the canonical runner implementation."""
    return _validate_dataset(*args, **kwargs)


def _issue_is_error(issue: Any) -> bool:
    """Return True when an issue represents an error severity."""
    if isinstance(issue, tuple) and issue:
        return str(issue[0]).upper() == "ERROR"

    severity = getattr(issue, "severity", None)
    if severity is None:
        return False

    severity_value = getattr(severity, "value", severity)
    return str(severity_value).upper() == "ERROR"


def determine_exit_code(issues: Iterable[Any]) -> int:
    """Map validation issues to process exit code.

    Contract:
    - 0: no validation errors
    - 1: validation errors present
    """
    return 1 if any(_issue_is_error(issue) for issue in issues) else 0


def build_validation_report(
    dataset_path: str,
    schema_version: str,
    structured_issues: List[Any],
    stats: Any,
) -> Dict[str, Any]:
    """Create a stable machine-readable validation report."""
    normalized_issues = normalize_issues(structured_issues)
    return {
        "dataset": os.path.abspath(dataset_path),
        "schema_version": schema_version,
        "valid": determine_exit_code(normalized_issues) == 0,
        "summary": summarize_issues(normalized_issues),
        "issues": issues_to_dict(normalized_issues),
        "statistics": {
            "total_files": getattr(stats, "total_files", 0),
            "subjects": list(getattr(stats, "subjects", set())),
            "sessions": list(getattr(stats, "sessions", set())),
            "tasks": list(getattr(stats, "tasks", set())),
            "modalities": dict(getattr(stats, "modalities", {})),
            "surveys": list(getattr(stats, "surveys", set())),
            "biometrics": list(getattr(stats, "biometrics", set())),
        },
    }


def normalize_issues(issues: Iterable[Any]) -> List[Any]:
    """Convert tuple issues to structured Issue objects when needed."""
    return [tuple_to_issue(issue) if isinstance(issue, tuple) else issue for issue in issues]
