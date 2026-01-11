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
        "fix_hint": "Ensure subject folders are named 'sub-<label>' and located at the dataset root",
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
        "message": "Incomplete dataset description",
        "fix_hint": "Add recommended fields to dataset_description.json for FAIR compliance and scientific reproducibility: Description, License, EthicsApprovals, Funding, DataCollection, Keywords.",
    },
    "PRISM007": {
        "message": "Incomplete survey template",
        "fix_hint": "Add recommended fields to survey template for APA methods export: Study.References (primary citation), Study.DOI, Study.Reliability, Study.AdministrationTime, Study.Description.",
    },
    # Filename errors (1xx)
    "PRISM101": {
        "message": "Invalid BIDS filename format",
        "fix_hint": "Ensure filename follows sub-<label>[_ses-<label>]_task-<label>_<suffix>.<ext>",
    },
    "PRISM102": {
        "message": "Filename doesn't match expected pattern for modality",
        "fix_hint": "Check modality-specific naming requirements (e.g., _survey.tsv)",
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
        # Levels errors (PRISM402)
        if code == "PRISM402":
            match = re.search(r"Value '([^']+)' not found in allowed levels: \[(.*)\]", message)
            if match:
                val, levels = match.groups()
                return f"The value '{val}' is not defined in the 'Levels' dictionary in the sidecar JSON. Add it to the sidecar or correct the data."
        
        # Range errors (PRISM403)
        if code == "PRISM403":
            match = re.search(r"Value '([^']+)' is out of range \(([^,]+), ([^)]+)\)", message)
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
    elif "dataset_description.json" in msg_lower:
        if "missing" in msg_lower and "field" not in msg_lower:
            return "PRISM001"
        # Completeness warnings (missing recommended fields)
        if any(x in msg_lower for x in ["recommended", "fair compliance", "too short", "fewer than"]):
            return "PRISM006"
        return "PRISM003"
    elif "survey template" in msg_lower or ("template" in msg_lower and "missing" in msg_lower and "study." in msg_lower):
        return "PRISM007"
    elif "no subjects found" in msg_lower:
        return "PRISM002"
    elif "consistency" in msg_lower or "mislabeled" in msg_lower or "mixed session" in msg_lower:
        return "PRISM601"
    elif "empty" in msg_lower:
        if "tsv" in msg_lower: return "PRISM401"
        return "PRISM204"
    elif "not in allowed values" in msg_lower:
        return "PRISM402"
    elif "less than minvalue" in msg_lower or "greater than maxvalue" in msg_lower:
        return "PRISM403"
    elif "less than warnminvalue" in msg_lower or "greater than warnmaxvalue" in msg_lower:
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

