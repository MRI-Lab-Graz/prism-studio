"""
Web interface utilities for prism.
Common helper functions used across web routes.
This module acts as a facade for specialized utility modules.
"""


# Import from specialized modules

# Import system file filtering from core
try:
    from system_files import is_system_file as _is_system_file
except ImportError:
    try:
        from src.system_files import is_system_file as _is_system_file
    except ImportError:
        def _is_system_file(filename: str) -> bool:
            return filename.startswith(".") or filename in {"Thumbs.db", "Desktop.ini"}

# Import error handling from core
try:
    from issues import (
        get_error_description as _get_error_description,
        get_error_documentation_url as _get_error_documentation_url,
        infer_code_from_message as _get_error_code_from_message,
    )
except ImportError:
    try:
        from src.issues import (
            get_error_description as _get_error_description,
            get_error_documentation_url as _get_error_documentation_url,
            infer_code_from_message as _get_error_code_from_message,
        )
    except ImportError:
        def _get_error_description(code): return "Validation error"
        def _get_error_documentation_url(code): return "https://prism-studio.readthedocs.io/"
        def _get_error_code_from_message(msg): return "PRISM999"


def is_system_file(filename: str) -> bool:
    """Check if a file is a system file that should be ignored."""
    return _is_system_file(filename)


def get_error_code_from_message(message: str) -> str:
    """Extract error code from validation message."""
    return _get_error_code_from_message(message)


def get_error_description(error_code: str) -> str:
    """Get user-friendly descriptions for error codes."""
    return _get_error_description(error_code)


def get_error_documentation_url(error_code: str) -> str:
    """Get documentation URL for an error code."""
    return _get_error_documentation_url(error_code)


# Path utilities re-exported from specialized module
from .path_utils import (
    strip_temp_path,
    extract_path_from_message,
    shorten_path,
    get_filename_from_path,
)


# Reporting utilities re-exported from specialized module
from .reporting_utils import (
    sanitize_jsonable,
    format_validation_results,
)


# Survey utilities re-exported from specialized module
from .survey_utils import (
    list_survey_template_languages,
)

