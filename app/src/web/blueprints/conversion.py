"""
Conversion Blueprint for PRISM.
Handles survey, biometrics, and physio conversion routes.
"""

import io
import re
import shutil
import tempfile
import zipfile
import base64
from pathlib import Path
from typing import Any
from flask import Blueprint, request, jsonify, send_file, session
from werkzeug.utils import secure_filename
from src.web.validation import run_validation

# Import shared utilities
from .conversion_utils import (
    participant_json_candidates,
    log_file_head,
    resolve_effective_library_path,
    normalize_filename,
    should_retry_with_official_library,
    is_project_code_library,
    extract_tasks_from_output,
)
from src.web.services.project_registration import register_session_in_project
from .conversion_survey_handlers import (  # noqa: F401
    _copy_official_templates_to_project,
    _format_unmatched_groups_response,
    _resolve_official_survey_dir,
    _run_survey_with_official_fallback,
    api_save_unmatched_template,
    api_survey_convert,
    api_survey_convert_preview,
    api_survey_convert_validate,
    api_survey_languages,
)
from .conversion_biometrics_handlers import (
    api_biometrics_check_library as _api_biometrics_check_library,
    api_biometrics_detect as _api_biometrics_detect,
    api_biometrics_convert as _api_biometrics_convert,
)
from .conversion_physio_handlers import (
    check_sourcedata_physio as _check_sourcedata_physio,
    api_physio_convert as _api_physio_convert,
    api_batch_convert as _api_batch_convert,
    api_physio_rename as _api_physio_rename,
)


IdColumnNotDetectedError: Any = None
try:
    from src.converters.id_detection import IdColumnNotDetectedError
except ImportError:
    pass

convert_biometrics_table_to_prism_dataset: Any = None
try:
    from src.converters.biometrics import convert_biometrics_table_to_prism_dataset
except ImportError:
    pass

convert_varioport: Any = None
try:
    from helpers.physio.convert_varioport import convert_varioport
except ImportError:
    pass

batch_convert_folder: Any = None
create_dataset_description: Any = None
parse_bids_filename: Any = None
try:
    from src.batch_convert import (
        batch_convert_folder,
        create_dataset_description,
        parse_bids_filename,
    )
except ImportError:
    pass

conversion_bp = Blueprint("conversion", __name__)

# Batch conversion job tracking
_batch_convert_jobs: dict[str, Any] = {}

# Keep backward-compatible wrappers for any internal calls
_participant_json_candidates = participant_json_candidates
_log_file_head = log_file_head
_resolve_effective_library_path = resolve_effective_library_path
_normalize_filename = normalize_filename
_should_retry_with_official_library = should_retry_with_official_library
_is_project_code_library = is_project_code_library
_extract_tasks_from_output = extract_tasks_from_output
_register_session_in_project = register_session_in_project





@conversion_bp.route("/api/biometrics-check-library", methods=["GET"])
def api_biometrics_check_library():
    """Check the structure of a biometrics template library folder."""
    return _api_biometrics_check_library()


@conversion_bp.route("/api/biometrics-detect", methods=["POST"])
def api_biometrics_detect():
    """Detect which biometrics tasks are present in the uploaded file."""
    return _api_biometrics_detect()


@conversion_bp.route("/api/biometrics-convert", methods=["POST"])
def api_biometrics_convert():
    """Convert an uploaded biometrics table (.csv or .xlsx) into a PRISM/BIDS-style dataset ZIP."""
    return _api_biometrics_convert()


@conversion_bp.route("/api/check-sourcedata-physio", methods=["GET"])
def check_sourcedata_physio():
    """Check if sourcedata/physio folder exists in current project."""
    return _check_sourcedata_physio()


@conversion_bp.route("/api/physio-convert", methods=["POST"])
def api_physio_convert():
    """Convert an uploaded Varioport file (.raw/.vpd) into EDF+ (.edf) + sidecar (.json) and return as ZIP."""
    return _api_physio_convert()


@conversion_bp.route("/api/batch-convert", methods=["POST"])
def api_batch_convert():
    """Batch convert physio/eyetracking files from a flat folder structure."""
    return _api_batch_convert()


@conversion_bp.route("/api/physio-rename", methods=["POST"])
def api_physio_rename():
    """Rename uploaded files based on a regex pattern and return a ZIP."""
    return _api_physio_rename()



 
