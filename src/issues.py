"""
Structured issue/error handling for prism-validator.

This module provides:
- Issue dataclass for structured error reporting
- Error code definitions with fix hints
- Utility functions for creating issues
"""

from dataclasses import dataclass, field, asdict
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
    
    # File naming errors (1xx)
    "PRISM101": {
        "message": "Invalid filename pattern",
        "fix_hint": "Use BIDS naming: sub-<label>[_ses-<label>][_task-<label>]_<suffix>.<ext>",
    },
    "PRISM102": {
        "message": "Subject ID mismatch between filename and directory",
        "fix_hint": "Ensure the sub-<label> in the filename matches the parent directory name",
    },
    "PRISM103": {
        "message": "Session ID mismatch between filename and directory",
        "fix_hint": "Ensure the ses-<label> in the filename matches the parent directory name",
    },
    "PRISM104": {
        "message": "Invalid characters in filename",
        "fix_hint": "Use only alphanumeric characters, hyphens, and underscores",
    },
    
    # Sidecar/metadata errors (2xx)
    "PRISM201": {
        "message": "Missing sidecar JSON file",
        "fix_hint": "Create a .json sidecar file with the same name as your data file",
    },
    "PRISM202": {
        "message": "Invalid JSON in sidecar file",
        "fix_hint": "Check for syntax errors in your JSON file (missing commas, brackets, etc.)",
    },
    "PRISM203": {
        "message": "Sidecar missing required field",
        "fix_hint": "Add the missing field to your sidecar JSON file",
    },
    "PRISM204": {
        "message": "Empty sidecar file",
        "fix_hint": "Add metadata content to the sidecar file or remove it if not needed",
    },
    
    # Schema validation errors (3xx)
    "PRISM301": {
        "message": "Schema validation failed",
        "fix_hint": "Check that your sidecar matches the expected schema structure",
    },
    "PRISM302": {
        "message": "Invalid field value",
        "fix_hint": "Check the allowed values for this field in the schema",
    },
    "PRISM303": {
        "message": "Schema version mismatch",
        "fix_hint": "Update your metadata to match the expected schema version",
    },
    "PRISM304": {
        "message": "Unknown modality",
        "fix_hint": "Supported modalities: survey, biometrics, events, anat, func, dwi, fmap, eeg",
    },
    
    # Content validation errors (4xx)
    "PRISM401": {
        "message": "TSV file is empty",
        "fix_hint": "Add data to the file or remove it if the data is missing",
    },
    "PRISM402": {
        "message": "TSV column count mismatch",
        "fix_hint": "Ensure all rows have the same number of columns as the header",
    },
    "PRISM403": {
        "message": "TSV missing required column",
        "fix_hint": "Add the required column to your TSV file",
    },
    "PRISM404": {
        "message": "Value out of allowed range",
        "fix_hint": "Check minValue/maxValue constraints in the sidecar",
    },
    "PRISM405": {
        "message": "Value not in allowed list",
        "fix_hint": "Check allowedValues/Levels constraints in the sidecar",
    },
    
    # BIDS compatibility warnings (5xx)
    "PRISM501": {
        "message": "Non-standard modality folder",
        "fix_hint": "This folder will be added to .bidsignore for BIDS-App compatibility",
    },
    "PRISM502": {
        "message": "BIDS validator warning",
        "fix_hint": "See BIDS specification for details",
    },
    "PRISM503": {
        "message": "BIDS validator error",
        "fix_hint": "See BIDS specification for details",
    },
    
    # Internal/system errors (9xx)
    "PRISM901": {
        "message": "Internal validation error",
        "fix_hint": "This may be a bug - please report it",
    },
    "PRISM902": {
        "message": "Schema loading failed",
        "fix_hint": "Check that schema files exist and are valid JSON",
    },
}


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


def error(code: str, file_path: Optional[str] = None, message: Optional[str] = None, **kwargs) -> Issue:
    """Shorthand for creating an ERROR issue"""
    return create_issue(code, Severity.ERROR, message=message, file_path=file_path, **kwargs)


def warning(code: str, file_path: Optional[str] = None, message: Optional[str] = None, **kwargs) -> Issue:
    """Shorthand for creating a WARNING issue"""
    return create_issue(code, Severity.WARNING, message=message, file_path=file_path, **kwargs)


def info(code: str, file_path: Optional[str] = None, message: Optional[str] = None, **kwargs) -> Issue:
    """Shorthand for creating an INFO issue"""
    return create_issue(code, Severity.INFO, message=message, file_path=file_path, **kwargs)


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
    
    severity = Severity[severity_str] if severity_str in Severity.__members__ else Severity.ERROR
    
    # Try to infer code from message patterns
    code = _infer_code_from_message(message) or default_code
    
    return Issue(
        code=code,
        severity=severity,
        message=message,
        file_path=file_path,
    )


def _infer_code_from_message(message: str) -> Optional[str]:
    """Attempt to infer error code from message content"""
    msg_lower = message.lower()
    
    if "dataset_description.json" in msg_lower:
        if "missing" in msg_lower:
            return "PRISM001"
        if "invalid" in msg_lower or "json" in msg_lower:
            return "PRISM003"
    
    if "no subjects found" in msg_lower:
        return "PRISM002"
    
    if "sidecar" in msg_lower or "missing" in msg_lower and ".json" in msg_lower:
        return "PRISM201"
    
    if "schema" in msg_lower:
        return "PRISM301"
    
    if "empty" in msg_lower:
        if "tsv" in msg_lower:
            return "PRISM401"
        return "PRISM204"
    
    if "[bids]" in msg_lower:
        if "error" in msg_lower:
            return "PRISM503"
        return "PRISM502"
    
    return None


# =============================================================================
# SUMMARY UTILITIES
# =============================================================================

def summarize_issues(issues: List[Issue]) -> Dict[str, Any]:
    """
    Create a summary of issues by severity and code.
    
    Returns:
        Dict with counts, by_severity, and by_code breakdowns
    """
    summary = {
        "total": len(issues),
        "errors": 0,
        "warnings": 0,
        "info": 0,
        "by_code": {},
    }
    
    for issue in issues:
        if issue.severity == Severity.ERROR:
            summary["errors"] += 1
        elif issue.severity == Severity.WARNING:
            summary["warnings"] += 1
        else:
            summary["info"] += 1
        
        if issue.code not in summary["by_code"]:
            summary["by_code"][issue.code] = 0
        summary["by_code"][issue.code] += 1
    
    return summary
