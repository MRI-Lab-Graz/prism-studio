# Web interface modules for prism
"""
This package contains modular Flask blueprints and utilities
for the prism web interface.
"""

from .utils import (
    is_system_file,
    strip_temp_path,
    extract_path_from_message,
    format_validation_results,
    get_error_description,
    get_error_documentation_url,
    get_fix_tool_info,
    shorten_path,
    get_filename_from_path,
)

from .validation import (
    run_validation,
    validation_progress,
    update_progress,
    get_progress,
    clear_progress,
    SimpleStats,
)

from .upload import (
    process_folder_upload,
    process_zip_upload,
    find_dataset_root,
    create_placeholder_content,
    detect_dataset_prefix,
    normalize_relative_path,
    METADATA_EXTENSIONS,
    SKIP_EXTENSIONS,
)

__all__ = [
    # Utils
    "is_system_file",
    "strip_temp_path",
    "extract_path_from_message",
    "format_validation_results",
    "get_error_description",
    "get_error_documentation_url",
    "get_fix_tool_info",
    "shorten_path",
    "get_filename_from_path",
    # Validation
    "run_validation",
    "validation_progress",
    "update_progress",
    "get_progress",
    "clear_progress",
    "SimpleStats",
    # Upload
    "process_folder_upload",
    "process_zip_upload",
    "find_dataset_root",
    "create_placeholder_content",
    "detect_dataset_prefix",
    "normalize_relative_path",
    "METADATA_EXTENSIONS",
    "SKIP_EXTENSIONS",
]
