"""
Structured issue/error handling for prism.

This module provides:
- Issue dataclass for structured error reporting
- Error code definitions with fix hints
- Utility functions for creating issues
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any


class Severity(Enum):
    """Issue severity levels"""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Issue:
    """
    Structured validation issue.

    Attributes:
        code: Unique error code (e.g., "PRISM001")
        severity: ERROR, WARNING, or INFO
        message: Human-readable error message
        file_path: Path to the affected file (optional)
        fix_hint: Suggestion for how to fix the issue (optional)
        details: Additional context (optional)
    """

    code: str
    severity: Severity
    message: str
    file_path: Optional[str] = None
    fix_hint: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "file_path": self.file_path,
            "fix_hint": self.fix_hint,
            "details": self.details,
        }

    def to_tuple(self) -> tuple:
        """Convert to legacy tuple format for backward compatibility"""
        if self.file_path:
            return (self.severity.value, self.message, self.file_path)
        return (self.severity.value, self.message)

    def __str__(self) -> str:
        """Human-readable string representation"""
        parts = [f"[{self.code}] {self.severity.value}: {self.message}"]
        if self.file_path:
            parts.append(f"  File: {self.file_path}")
        if self.fix_hint:
            parts.append(f"  Fix: {self.fix_hint}")
        return "\n".join(parts)


# =============================================================================
# ERROR CODE DEFINITIONS
# =============================================================================
# Format: CODE -> (default_message, fix_hint)
# Codes are organized by category:
#   PRISM0xx: Dataset structure errors
#   PRISM1xx: File naming errors
#   PRISM2xx: Sidecar/metadata errors
#   PRISM3xx: Schema validation errors
#   PRISM4xx: Content validation errors
#   PRISM5xx: BIDS compatibility warnings
#   PRISM6xx: Consistency errors
#   PRISM9xx: Internal/system errors

ERROR_CODES: Dict[str, Dict[str, str]] = {
    # Dataset structure errors (0xx)
    "PRISM001": {
        "message": "Missing dataset_description.json",
        "fix_hint": "Create a dataset_description.json file at the dataset root with required fields: Name, BIDSVersion",
    },
    "PRISM002": {
        "message": "No subjects found in dataset",
        "fix_hint": "Ensure subject folders are named 'sub-<label>' and located at the project dataset root",
    },
    "PRISM003": {
        "message": "Invalid dataset_description.json",
        "fix_hint": "Ensure the file contains valid JSON with required BIDS fields",
    },
    "PRISM004": {
        "message": "Missing participants.tsv",
        "fix_hint": "Create a participants.tsv file listing all subjects with at least a 'participant_id' column",
    },
    "PRISM005": {
        "message": "Schema version mismatch",
        "fix_hint": "The metadata uses an older or newer schema version than the validator. Consider updating the 'SchemaVersion' in your metadata files.",
    },
    "PRISM006": {
        "message": "FAIR compliance issue in dataset_description.json",
        "fix_hint": "Add recommended metadata for FAIR compliance: Description (min 50 chars), License, EthicsApprovals, Funding, Keywords (min 3), Authors with ORCID/affiliation",
    },
    "PRISM007": {
        "message": "Incomplete survey template metadata",
        "fix_hint": "Add recommended fields to the survey template: References, Description, Reliability, AdministrationTime",
    },
    "PRISM008": {
        "message": "Template consistency error",
        "fix_hint": "Check that ItemCount matches actual questions, Subscale items exist, ReverseCodedItems exist, and Levels keys are within MinValue/MaxValue range",
    },
    # Filename errors (1xx)
    "PRISM101": {
        "message": "Invalid BIDS filename format",
        "fix_hint": "Ensure filename follows sub-<label>[_ses-<label>]_task-<label>_<suffix>.<ext>",
    },
    "PRISM102": {
        "message": "Filename doesn't match expected pattern for modality",
        "fix_hint": "Ensure the filename follows the correct suffix for this modality. Use '_survey', '_physio', '_eyetrack', '_biometrics', or '_events' as appropriate.",
    },
    "PRISM103": {
        "message": "Subject ID mismatch",
        "fix_hint": "Ensure the sub-<label> in the filename matches the parent directory",
    },
    "PRISM104": {
        "message": "Session ID mismatch",
        "fix_hint": "Ensure the ses-<label> in the filename matches the parent directory",
    },
    # Sidecar errors (2xx)
    "PRISM201": {
        "message": "Missing JSON sidecar",
        "fix_hint": "Every data file must have a corresponding .json sidecar with metadata",
    },
    "PRISM202": {
        "message": "Invalid JSON syntax in sidecar",
        "fix_hint": "Check for missing commas, quotes, or brackets in the .json file",
    },
    "PRISM203": {
        "message": "Empty sidecar file",
        "fix_hint": "The .json sidecar exists but contains no data",
    },
    "PRISM204": {
        "message": "Empty data file",
        "fix_hint": "The data file exists but contains no content",
    },
    # Schema errors (3xx)
    "PRISM301": {
        "message": "Metadata schema validation failed",
        "fix_hint": "Ensure all required fields for this modality are present in the JSON sidecar",
    },
    "PRISM302": {
        "message": "Invalid field type in sidecar",
        "fix_hint": "Check that field values match the expected type (string, number, etc.)",
    },
    # Content errors (4xx)
    "PRISM401": {
        "message": "TSV file is empty or missing header",
        "fix_hint": "Ensure the TSV file has a tab-separated header row",
    },
    "PRISM402": {
        "message": "Value not in allowed levels",
        "fix_hint": "Check that the value in the TSV matches one of the Levels defined in the sidecar",
    },
    "PRISM403": {
        "message": "Value out of range",
        "fix_hint": "Check if the value is within the MinValue and MaxValue range defined in the sidecar",
    },
    "PRISM404": {
        "message": "Value out of warning range",
        "fix_hint": "The value is within absolute limits but outside the typical warning range",
    },
    # BIDS compatibility (5xx)
    "PRISM501": {
        "message": ".bidsignore needs update",
        "fix_hint": "Add PRISM-specific modalities to .bidsignore to avoid BIDS validator errors",
    },
    "PRISM502": {
        "message": "BIDS validator warning",
        "fix_hint": "Standard BIDS validator reported a warning",
    },
    "PRISM503": {
        "message": "BIDS validator error",
        "fix_hint": "Standard BIDS validator reported an error",
    },
    # Consistency errors (6xx)
    "PRISM601": {
        "message": "Dataset consistency warning",
        "fix_hint": "Check for missing sessions or modalities across subjects",
    },
    # Procedure/Session errors (7xx)
    "PRISM701": {
        "message": "Session on disk not declared in project.json",
        "fix_hint": "Add this session to the Sessions array in project.json, or use the session picker in the converter",
    },
    "PRISM702": {
        "message": "Declared session has no data on disk",
        "fix_hint": "Convert data for this session, or remove it from project.json if it was added by mistake",
    },
    "PRISM703": {
        "message": "Task on disk not declared in session",
        "fix_hint": "Register this task in the session's tasks array in project.json",
    },
    "PRISM704": {
        "message": "Declared non-optional task has no data on disk",
        "fix_hint": "Convert data for this task, mark it as optional, or remove it from the session",
    },
    "PRISM705": {
        "message": "Task references undefined TaskDefinition",
        "fix_hint": "Add this task to the TaskDefinitions object in project.json with at least a modality",
    },
    "PRISM706": {
        "message": "Sessions array is empty — no procedure defined yet",
        "fix_hint": "Define your study procedure in the Sessions array, or convert data with save-to-project to auto-register",
    },
    # Internal/System (9xx)
    "PRISM901": {
        "message": "Internal validation error",
        "fix_hint": "An unexpected error occurred during validation",
    },
    "PRISM999": {
        "message": "General validation error",
        "fix_hint": "Check the error message for details",
    },
}


# =============================================================================
# FIX TOOL MAPPING
# =============================================================================
# Maps error codes to the appropriate tool for fixing the issue.
# Used to show "Fix in [Tool]" buttons in validation results.

FIX_TOOLS: Dict[str, Dict[str, str]] = {
    # Dataset structure - use JSON editor for metadata files
    "PRISM001": {
        "tool": "json-editor",
        "label": "Create in Editor",
        "target": "dataset_description.json",
    },
    "PRISM003": {
        "tool": "json-editor",
        "label": "Edit in JSON Editor",
        "target": "dataset_description.json",
    },
    "PRISM004": {
        "tool": "json-editor",
        "label": "Create in Editor",
        "target": "participants.json",
    },
    "PRISM006": {
        "tool": "json-editor",
        "label": "Edit Metadata",
        "target": "dataset_description.json",
    },
    # Template issues - use template editor
    "PRISM007": {"tool": "template-editor", "label": "Edit Template"},
    "PRISM008": {"tool": "template-editor", "label": "Fix Template"},
    # Sidecar issues - use JSON editor
    "PRISM201": {"tool": "json-editor", "label": "Create Sidecar"},
    "PRISM202": {"tool": "json-editor", "label": "Fix JSON Syntax"},
    "PRISM203": {"tool": "json-editor", "label": "Edit Sidecar"},
    "PRISM301": {"tool": "json-editor", "label": "Fix Schema Error"},
    "PRISM302": {"tool": "json-editor", "label": "Fix Field Type"},
    # Content issues - often need data file or sidecar edit
    "PRISM402": {"tool": "json-editor", "label": "Update Levels"},
    "PRISM403": {"tool": "json-editor", "label": "Update Range"},
    # BIDS compatibility
    "PRISM501": {
        "tool": "json-editor",
        "label": "Edit .bidsignore",
        "target": ".bidsignore",
    },
}


def get_fix_tool(code: str) -> Dict[str, str] | None:
    """
    Get the fix tool info for an error code.

    Returns:
        Dict with 'tool', 'label', and optionally 'target' keys, or None if no fix tool.
    """
    return FIX_TOOLS.get(code)


def get_error_description(code: str) -> str:
    """Get user-friendly description for an error code."""
    if code.startswith("BIDS_"):
        return f"BIDS specification violation: {code[5:]}"

    defaults = ERROR_CODES.get(code, {})
    return defaults.get("message", "Validation error")


def get_fix_hint(code: str, message: str = "") -> str:
    """Get fix hint for an error code, optionally using the message for context."""
    import re

    # Handle specific cases with regex if message is provided
    if message:
        # Modality-specific filename pattern errors (PRISM102)
        if code == "PRISM102":
            modality_match = re.search(r"modality '([^']+)'", message)
            if modality_match:
                modality = modality_match.group(1)
                modality_hints = {
                    "survey": "Ensure the filename ends with '_survey.tsv' or '_survey.json' (e.g., sub-001_task-panas_survey.tsv)",
                    "biometrics": "Ensure the filename ends with '_biometrics.tsv' or '_biometrics.json' (e.g., sub-001_task-rest_biometrics.tsv)",
                    "physio": "Ensure the filename ends with '_physio.<ext>' where <ext> is tsv, tsv.gz, json, or edf (e.g., sub-001_task-rest_recording-ecg_physio.tsv)",
                    "physiological": "Ensure the filename ends with '_physio.<ext>' where <ext> is tsv, tsv.gz, json, or edf (e.g., sub-001_task-rest_recording-ecg_physio.tsv)",
                    "eyetracking": "Ensure the filename ends with '_eyetrack.<ext>' or '_eye.<ext>' or '_gaze.<ext>' where <ext> is tsv, tsv.gz, json, edf, or asc (e.g., sub-001_task-rest_trackedEye-left_eyetrack.tsv)",
                    "events": "Ensure the filename ends with '_events.tsv' (e.g., sub-001_task-rest_events.tsv)",
                }
                return modality_hints.get(
                    modality,
                    f"Ensure the filename ends with '_{modality}.<ext>' appropriate for this modality",
                )

        # Schema validation errors (PRISM301)
        if code == "PRISM301":
            if "licenseid" in message.lower() or "license" in message.lower():
                # Try to extract the survey/task name from the message (e.g. task-danceq_survey.json)
                task_match = re.search(r"task-([a-zA-Z0-9]+)_survey", message)
                survey_name = task_match.group(1) if task_match else "this instrument"
                return f"The PRISM schema requires a valid license for all survey instruments. You must specify a 'LicenseID' (e.g., 'Proprietary' or 'CC-BY-4.0') and a 'License' statement for survey '{survey_name}' in the metadata template."

            if "too short" in message.lower():
                if "keyword" in message.lower():
                    return "PRISM recommends at least 3 keywords to ensure your dataset is discoverable (FAIR compliance). Add more keywords to the 'Keywords' array."
                if "author" in message.lower():
                    return "BIDS requires at least one author in dataset_description.json. Ensure 'Authors' is a non-empty array."
                if "description" in message.lower():
                    return "A descriptive study overview (minimum 50 characters) is required for FAIR compliance. Expand the 'Description' field in dataset_description.json."
                return "A required field or array is too short according to the PRISM schema. Check the schema requirements for this field."

        # Levels errors (PRISM402)
        if code == "PRISM402":
            match = re.search(
                r"Value '([^']+)' not found in allowed levels: \[(.*)\]", message
            )
            if match:
                val, levels = match.groups()
                return f"The value '{val}' is not defined in the 'Levels' dictionary in the sidecar JSON. Add it to the sidecar or correct the data."

        # Range errors (PRISM403)
        if code == "PRISM403":
            match = re.search(
                r"Value '([^']+)' is out of range \(([^,]+), ([^)]+)\)", message
            )
            if match:
                val, min_val, max_val = match.groups()
                return f"The value '{val}' is outside the allowed range [{min_val}, {max_val}]. Check the sidecar JSON for 'MinValue' and 'MaxValue' definitions for this column."

    defaults = ERROR_CODES.get(code, {})
    return defaults.get("fix_hint", "")


def get_error_documentation_url(code: str) -> str:
    """Get documentation URL for an error code."""
    if code.startswith("BIDS"):
        return "https://bids-specification.readthedocs.io/en/stable/"

    base_url = "https://prism-studio.readthedocs.io/en/latest/ERROR_CODES.html"
    if code.startswith("PRISM"):
        return f"{base_url}#{code.lower()}---"

    return base_url


def infer_code_from_message(message: str) -> str:
    """Extract or infer error code from validation message."""
    # Check for explicit PRISM error codes first
    prism_match = re.search(r"(PRISM\d{3})", message)
    if prism_match:
        return prism_match.group(1)

    # Check for BIDS validator messages
    if "[BIDS]" in message:
        bids_code_match = re.search(r"\[BIDS\]\s*([A-Z_]+)", message)
        if bids_code_match:
            return f"BIDS_{bids_code_match.group(1)}"
        return "BIDS_GENERAL"

    # PRISM-specific error detection (legacy patterns)
    msg_lower = message.lower()

    if "invalid bids filename" in msg_lower:
        return "PRISM101"
    elif "missing sidecar" in msg_lower:
        return "PRISM201"
    elif "schema error" in msg_lower or "schema validation failed" in msg_lower:
        return "PRISM301"
    elif "not found in allowed levels" in msg_lower:
        return "PRISM402"
    elif "is out of range" in msg_lower:
        return "PRISM403"
    elif "out of warning range" in msg_lower:
        return "PRISM404"
    elif "not valid json" in msg_lower:
        return "PRISM202"
    elif "doesn't match expected pattern" in msg_lower:
        return "PRISM102"
    elif "does not start with subject id" in msg_lower:
        return "PRISM103"
    elif "does not match session directory" in msg_lower:
        return "PRISM104"
    elif "schema version mismatch" in msg_lower:
        return "PRISM005"
    elif "fair compliance" in msg_lower or "fair principle" in msg_lower:
        return "PRISM006"
    elif "incomplete template" in msg_lower or (
        "template" in msg_lower
        and "missing" in msg_lower
        and (
            "references" in msg_lower
            or "reliability" in msg_lower
            or "administrationtime" in msg_lower
        )
    ):
        return "PRISM007"
    elif (
        "template consistency" in msg_lower
        or "itemcount" in msg_lower
        or ("subscale" in msg_lower and "not found" in msg_lower)
    ):
        return "PRISM008"
    elif "dataset_description.json" in msg_lower:
        if "missing" in msg_lower:
            return "PRISM001"
        return "PRISM003"
    elif "no subjects found" in msg_lower:
        return "PRISM002"
    elif (
        "consistency" in msg_lower
        or "mislabeled" in msg_lower
        or "mixed session" in msg_lower
    ):
        return "PRISM601"
    elif "empty" in msg_lower:
        if "tsv" in msg_lower:
            return "PRISM401"
        return "PRISM204"
    elif "not in allowed values" in msg_lower:
        return "PRISM402"
    elif "less than minvalue" in msg_lower or "greater than maxvalue" in msg_lower:
        return "PRISM403"
    elif (
        "less than warnminvalue" in msg_lower
        or "greater than warnmaxvalue" in msg_lower
    ):
        return "PRISM404"

    return "PRISM999"


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_issue(
    code: str,
    severity: Severity = Severity.ERROR,
    message: Optional[str] = None,
    file_path: Optional[str] = None,
    fix_hint: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Issue:
    """
    Create an Issue with defaults from ERROR_CODES.

    Args:
        code: Error code (e.g., "PRISM001")
        severity: Override default severity
        message: Override default message
        file_path: Path to affected file
        fix_hint: Override default fix hint
        details: Additional context

    Returns:
        Issue instance
    """
    defaults = ERROR_CODES.get(code, {})
    return Issue(
        code=code,
        severity=severity,
        message=message or defaults.get("message", f"Unknown error: {code}"),
        file_path=file_path,
        fix_hint=fix_hint or defaults.get("fix_hint"),
        details=details,
    )


def error(
    code: str, file_path: Optional[str] = None, message: Optional[str] = None, **kwargs
) -> Issue:
    """Shorthand for creating an ERROR issue"""
    return create_issue(
        code, Severity.ERROR, message=message, file_path=file_path, **kwargs
    )


def warning(
    code: str, file_path: Optional[str] = None, message: Optional[str] = None, **kwargs
) -> Issue:
    """Shorthand for creating a WARNING issue"""
    return create_issue(
        code, Severity.WARNING, message=message, file_path=file_path, **kwargs
    )


def info(
    code: str, file_path: Optional[str] = None, message: Optional[str] = None, **kwargs
) -> Issue:
    """Shorthand for creating an INFO issue"""
    return create_issue(
        code, Severity.INFO, message=message, file_path=file_path, **kwargs
    )


# =============================================================================
# CONVERSION UTILITIES
# =============================================================================


def issues_to_dict(issues: List[Issue]) -> List[Dict[str, Any]]:
    """Convert list of Issues to list of dicts for JSON serialization"""
    return [issue.to_dict() for issue in issues]


def issues_to_tuples(issues: List[Issue]) -> List[tuple]:
    """Convert list of Issues to legacy tuple format"""
    return [issue.to_tuple() for issue in issues]


def tuple_to_issue(t: tuple, default_code: str = "PRISM901") -> Issue:
    """
    Convert a legacy (severity, message[, path]) tuple to an Issue.

    Used for backward compatibility during migration.
    """
    if len(t) == 2:
        severity_str, message = t
        file_path = None
    else:
        severity_str, message, file_path = t[:3]

    severity = (
        Severity[severity_str]
        if severity_str in Severity.__members__
        else Severity.ERROR
    )

    # Try to infer code from message patterns
    code = infer_code_from_message(message)
    if code == "PRISM999":
        code = default_code

    return Issue(
        code=code,
        severity=severity,
        message=message,
        file_path=file_path,
    )


def _infer_code_from_message(message: str) -> Optional[str]:
    """Legacy internal helper, now points to infer_code_from_message"""
    code = infer_code_from_message(message)
    return code if code != "PRISM999" else None


# =============================================================================
# SUMMARY UTILITIES
# =============================================================================


def summarize_issues(issues: List[Issue]) -> Dict[str, Any]:
    """
    Create a summary of issues by severity and code.

    Returns:
        Dict with counts, by_severity, and by_code breakdowns
    """
    errors = 0
    warnings = 0
    info_count = 0
    by_code: Dict[str, int] = {}

    for issue in issues:
        if issue.severity == Severity.ERROR:
            errors += 1
        elif issue.severity == Severity.WARNING:
            warnings += 1
        else:
            info_count += 1

        if issue.code not in by_code:
            by_code[issue.code] = 0
        by_code[issue.code] += 1

    return {
        "total": len(issues),
        "errors": errors,
        "warnings": warnings,
        "info": info_count,
        "by_code": by_code,
    }
