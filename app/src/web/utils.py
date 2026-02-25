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

        def _get_error_description(code):
            return "Validation error"

        def _get_error_documentation_url(code):
            return "https://prism-studio.readthedocs.io/"

        def _get_error_code_from_message(msg):
            return "PRISM999"


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
try:
    from src.web.path_utils import (
        strip_temp_path as _import_strip_temp_path,
        strip_temp_path_from_message as _import_strip_temp_path_from_message,
        extract_path_from_message as _import_extract_path_from_message,
        shorten_path as _import_shorten_path,
        get_filename_from_path as _import_get_filename_from_path,
    )
except ImportError:
    _import_strip_temp_path = None
    _import_strip_temp_path_from_message = None
    _import_extract_path_from_message = None
    _import_shorten_path = None
    _import_get_filename_from_path = None

try:
    from src.web.reporting_utils import (
        format_validation_results as _import_format_validation_results,
        sanitize_jsonable as _import_sanitize_jsonable,
    )
except ImportError:
    _import_format_validation_results = None
    _import_sanitize_jsonable = None

try:
    from src.web.survey_utils import (
        list_survey_template_languages as _import_list_survey_template_languages,
    )
except ImportError:
    _import_list_survey_template_languages = None


def strip_temp_path(path: str) -> str:
    if _import_strip_temp_path is not None:
        return _import_strip_temp_path(path)
    return path


def strip_temp_path_from_message(message: str) -> str:
    if _import_strip_temp_path_from_message is not None:
        return _import_strip_temp_path_from_message(message)
    return message


def extract_path_from_message(message: str) -> str:
    if _import_extract_path_from_message is not None:
        return _import_extract_path_from_message(message)
    return ""


def shorten_path(path: str, max_len: int = 80) -> str:
    if _import_shorten_path is not None:
        return _import_shorten_path(path, max_len=max_len)
    if len(path) <= max_len:
        return path
    return "..." + path[-(max_len - 3) :]


def get_filename_from_path(path: str) -> str:
    if _import_get_filename_from_path is not None:
        return _import_get_filename_from_path(path)
    try:
        import os

        return os.path.basename(path)
    except Exception:
        return path


def format_validation_results(issues, stats, root_dir):
    if _import_format_validation_results is not None:
        return _import_format_validation_results(issues, stats, root_dir)
    return {"issues": issues, "stats": stats, "root_dir": root_dir}


def sanitize_jsonable(obj):
    if _import_sanitize_jsonable is not None:
        return _import_sanitize_jsonable(obj)
    return obj


def list_survey_template_languages(template_data) -> list[str]:
    if _import_list_survey_template_languages is not None:
        return _import_list_survey_template_languages(template_data)
    return ["en"]
