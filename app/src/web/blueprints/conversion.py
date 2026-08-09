"""
Conversion Blueprint for PRISM.
Handles survey, biometrics, and physio conversion routes.
"""

from typing import Any
from flask import Blueprint

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
    api_biometrics_convert_start as _api_biometrics_convert_start,
    api_biometrics_convert_status as _api_biometrics_convert_status,
)
from .conversion_physio_handlers import (
    check_sourcedata_physio as _check_sourcedata_physio,
    api_physio_convert as _api_physio_convert,
    api_batch_convert as _api_batch_convert,
    api_batch_convert_start as _api_batch_convert_start,
    api_batch_convert_status as _api_batch_convert_status,
    api_batch_convert_cancel as _api_batch_convert_cancel,
    api_batch_convert_metrics as _api_batch_convert_metrics,
    api_physio_rename as _api_physio_rename,
)
from .conversion_environment_handlers import (
    api_environment_preview as _api_environment_preview,
    api_environment_convert_start as _api_environment_convert_start,
    api_environment_convert_status as _api_environment_convert_status,
    api_environment_convert_cancel as _api_environment_convert_cancel,
    api_environment_convert_metrics as _api_environment_convert_metrics,
    api_environment_location_search as _api_environment_location_search,
    api_environment_scan_mri_acquisition as _api_environment_scan_mri_acquisition,
    api_environment_rescan_mri as _api_environment_rescan_mri,
)

conversion_bp = Blueprint("conversion", __name__)

# Batch conversion job tracking
_batch_convert_jobs: dict[str, Any] = {}


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


@conversion_bp.route("/api/biometrics-convert-start", methods=["POST"])
def api_biometrics_convert_start():
    """Start an async biometrics conversion job."""
    return _api_biometrics_convert_start()


@conversion_bp.route("/api/biometrics-convert-status/<job_id>", methods=["GET"])
def api_biometrics_convert_status(job_id: str):
    """Get async biometrics conversion job status and incremental logs."""
    return _api_biometrics_convert_status(job_id)


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


@conversion_bp.route("/api/batch-convert-start", methods=["POST"])
def api_batch_convert_start():
    """Start async batch conversion job."""
    return _api_batch_convert_start()


@conversion_bp.route("/api/batch-convert-status/<job_id>", methods=["GET"])
def api_batch_convert_status(job_id: str):
    """Get async batch conversion job status and incremental logs."""
    return _api_batch_convert_status(job_id)


@conversion_bp.route("/api/batch-convert-cancel/<job_id>", methods=["POST"])
def api_batch_convert_cancel(job_id: str):
    """Cancel an async batch conversion job."""
    return _api_batch_convert_cancel(job_id)


@conversion_bp.route("/api/batch-convert-metrics", methods=["GET"])
def api_batch_convert_metrics():
    """Get in-memory batch conversion metrics for debugging/monitoring."""
    return _api_batch_convert_metrics()


@conversion_bp.route("/api/physio-rename", methods=["POST"])
def api_physio_rename():
    """Rename uploaded files based on a regex pattern and return a ZIP."""
    return _api_physio_rename()


@conversion_bp.route("/api/environment-preview", methods=["POST"])
def api_environment_preview():
    """Read uploaded tabular file and return column names + sample rows."""
    return _api_environment_preview()


@conversion_bp.route("/api/environment-location-search", methods=["GET"])
def api_environment_location_search():
    """Search place names and return validated coordinate options."""
    return _api_environment_location_search()


@conversion_bp.route("/api/environment-scan-mri", methods=["POST"])
def api_environment_scan_mri_acquisition():
    """Scan the current project's rawdata for MRI acquisition timestamps/location."""
    return _api_environment_scan_mri_acquisition()


@conversion_bp.route("/api/environment-rescan-mri", methods=["POST"])
def api_environment_rescan_mri():
    """One-click rescan: re-discover MRI acquisitions and re-run environment enrichment."""
    return _api_environment_rescan_mri()


@conversion_bp.route("/api/environment-convert-start", methods=["POST"])
def api_environment_convert_start():
    """Start async environment conversion job."""
    return _api_environment_convert_start()


@conversion_bp.route("/api/environment-convert-status/<job_id>", methods=["GET"])
def api_environment_convert_status(job_id: str):
    """Get async environment conversion job status and incremental logs."""
    return _api_environment_convert_status(job_id)


@conversion_bp.route("/api/environment-convert-cancel/<job_id>", methods=["POST"])
def api_environment_convert_cancel(job_id: str):
    """Cancel an async environment conversion job."""
    return _api_environment_convert_cancel(job_id)


@conversion_bp.route("/api/environment-convert-metrics", methods=["GET"])
def api_environment_convert_metrics():
    """Get in-memory environment conversion metrics for debugging/monitoring."""
    return _api_environment_convert_metrics()
