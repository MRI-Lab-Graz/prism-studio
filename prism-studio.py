#!/usr/bin/env python3
"""
Web interface for prism
A simple Flask web app that provides a user-friendly interface for dataset validation

This module has been refactored to use modular components from src/web/:
- src/web/utils.py: Utility functions (path handling, error formatting)
- src/web/validation.py: Validation logic and progress tracking
- src/web/upload.py: File upload processing
"""

import os
import sys
import json
import re
import tempfile
import shutil
import webbrowser
import threading
from pathlib import Path
from datetime import datetime
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    flash,
    redirect,
    url_for,
)
from werkzeug.utils import secure_filename
import zipfile
import io
import requests
from functools import lru_cache

# Ensure we can import core validator logic from src
if getattr(sys, 'frozen', False):
    # Running in a PyInstaller bundle
    BASE_DIR = Path(sys._MEIPASS)
else:
    # Running in a normal Python environment
    BASE_DIR = Path(__file__).resolve().parent

SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Import refactored web modules
try:
    from src.web import (
        # Utils
        is_system_file,
        format_validation_results,
        get_error_description,
        get_error_documentation_url,
        shorten_path,
        get_filename_from_path,
        # Validation
        run_validation,
        update_progress,
        get_progress,
        clear_progress,
        SimpleStats,
        # Upload
        process_folder_upload as _process_folder_upload,
        process_zip_upload as _process_zip_upload,
        find_dataset_root,
        METADATA_EXTENSIONS,
        SKIP_EXTENSIONS,
    )
    print("✓ Web modules loaded from src/web/")
except ImportError as e:
    print(f"⚠️  Could not import web modules: {e}")
    # Fallback definitions will be provided inline if needed

# Legacy alias for backwards compatibility
run_main_validator = run_validation

try:
    from limesurvey_exporter import generate_lss
except Exception as import_error:
    generate_lss = None
    print(f"⚠️  Could not import limesurvey_exporter: {import_error}")

try:
    from survey_manager import SurveyManager
except Exception as import_error:
    SurveyManager = None
    print(f"⚠️  Could not import SurveyManager: {import_error}")

try:
    from survey_convert import (
        convert_survey_xlsx_to_prism_dataset,
        convert_survey_lsa_to_prism_dataset,
        infer_lsa_metadata,
    )
except Exception as import_error:
    convert_survey_xlsx_to_prism_dataset = None
    convert_survey_lsa_to_prism_dataset = None
    infer_lsa_metadata = None
    print(f"⚠️  Could not import survey_convert: {import_error}")

try:
    from biometrics_convert import convert_biometrics_table_to_prism_dataset
except Exception as import_error:
    convert_biometrics_table_to_prism_dataset = None
    print(f"⚠️  Could not import biometrics_convert: {import_error}")

try:
    from helpers.physio.convert_varioport import convert_varioport
except Exception as import_error:
    convert_varioport = None
    print(f"⚠️  Could not import convert_varioport: {import_error}")

try:
    from batch_convert import batch_convert_folder, create_dataset_description, parse_bids_filename
except Exception as import_error:
    batch_convert_folder = None
    create_dataset_description = None
    parse_bids_filename = None
    print(f"⚠️  Could not import batch_convert: {import_error}")


def _list_survey_template_languages(library_path: str) -> tuple[list[str], str | None, int, int]:
    """Return (languages, default_language, template_count, i18n_count) from survey templates in a folder.
    
    Args:
        library_path: Path to the survey template library folder
        
    Returns:
        Tuple of (sorted language list, default language, total template count, templates with I18n count)
    """
    langs: set[str] = set()
    defaults: set[str] = set()
    template_count = 0
    i18n_count = 0

    try:
        root = Path(library_path).resolve()
    except Exception:
        return [], None, 0, 0

    if not root.exists() or not root.is_dir():
        return [], None, 0, 0

    for p in sorted(root.glob("survey-*.json")):
        template_count += 1
        has_i18n = False
        
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        i18n = data.get("I18n")
        if isinstance(i18n, dict):
            i18n_langs = i18n.get("Languages")
            if isinstance(i18n_langs, list) and len(i18n_langs) > 0:
                has_i18n = True
                for v in i18n_langs:
                    if isinstance(v, str) and v.strip():
                        langs.add(v.strip())
            d = i18n.get("DefaultLanguage")
            if isinstance(d, str) and d.strip():
                defaults.add(d.strip())

        tech = data.get("Technical")
        if isinstance(tech, dict):
            tl = tech.get("Language")
            if isinstance(tl, str) and tl.strip():
                langs.add(tl.strip())
        
        if has_i18n:
            i18n_count += 1

    default = None
    if len(defaults) == 1:
        default = next(iter(defaults))
    return sorted(langs), default, template_count, i18n_count

try:
    from derivatives_surveys import compute_survey_derivatives
except Exception as import_error:
    compute_survey_derivatives = None
    print(f"⚠️  Could not import derivatives_surveys: {import_error}")


# Note: run_main_validator is already aliased to run_validation above

# Note: is_system_file is imported from src.web.utils
# simple_is_system_file is kept for backwards compatibility only
def simple_is_system_file(filename):
    """Simple system file detection - use is_system_file from web.utils instead."""
    return is_system_file(filename)


if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

# Secret key for session management
# In production, set PRISM_SECRET_KEY environment variable
app.secret_key = os.environ.get("PRISM_SECRET_KEY", "prism-dev-key-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = (
    1024 * 1024 * 1024
)  # 1GB max file size (metadata only)
app.config["MAX_FORM_PARTS"] = 20000  # Allow up to 20000 files/fields in upload

# Initialize Survey Manager
survey_library_path = BASE_DIR / "survey_library"
survey_manager = None
if SurveyManager:
    survey_manager = SurveyManager(survey_library_path)
    print(f"✓ Survey Manager initialized at {survey_library_path}")

# Register JSON Editor blueprint if available
try:
    from src.json_editor_blueprint import create_json_editor_blueprint

    json_editor_bp = create_json_editor_blueprint(bids_folder=None)
    app.register_blueprint(json_editor_bp)
    print("✓ JSON Editor blueprint registered at /editor")
except ImportError as e:
    print(f"ℹ️  JSON Editor not available: {e}")
except Exception as e:
    print(f"⚠️  Error registering JSON Editor blueprint: {e}")

# Register REST API blueprint
try:
    from src.api import create_api_blueprint

    schema_dir = str(BASE_DIR / "schemas")
    api_bp = create_api_blueprint(schema_dir=schema_dir)
    app.register_blueprint(api_bp)
    print("✓ REST API registered at /api/v1")
except ImportError as e:
    print(f"ℹ️  REST API not available: {e}")
except Exception as e:
    print(f"⚠️  Error registering REST API blueprint: {e}")

# Note: METADATA_EXTENSIONS and SKIP_EXTENSIONS are now imported from src.web.upload
# Note: format_validation_results, get_error_description, get_error_documentation_url 
#       are now imported from src.web.utils


@lru_cache(maxsize=8)
def fetch_neurobagel_participants():
    """Fetch NeuroBagel participants dictionary and cache it."""
    url = "https://neurobagel.org/data_models/dictionaries/participants.json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def augment_neurobagel_data(raw_data):
    """Augment raw NeuroBagel data with standardized variable mappings and categorical details.

    Transforms flat NeuroBagel data into a hierarchical structure with:
    - Standardized variable mappings (e.g., sex -> biological_sex)
    - Data type classification (categorical vs continuous)
    - Categorical level details with URIs and descriptions
    - Column-level metadata
    """
    if not raw_data or not raw_data.get("properties"):
        return raw_data

    # Mapping of column names to standardized variables
    standardized_mappings = {
        "participant_id": "participant_id",
        "age": "age",
        "sex": "biological_sex",
        "group": "participant_group",
        "handedness": "handedness",
    }

    # Categorical value mappings with controlled vocabulary URIs (SNOMED CT and PATO)
    # URIs are stored in shortened form for export (e.g., 'snomed:248153007')
    categorical_vocabularies = {
        "sex": {
            "M": {
                "label": "Male",
                "description": "Male biological sex",
                "uri": "snomed:248153007",
            },
            "F": {
                "label": "Female",
                "description": "Female biological sex",
                "uri": "snomed:248152002",
            },
            "O": {
                "label": "Other",
                "description": "Other biological sex",
                "uri": "snomed:447964000",
            },
        },
        "handedness": {
            "L": {
                "label": "Left",
                "description": "Left-handed",
                "uri": "snomed:87622008",
            },
            "R": {
                "label": "Right",
                "description": "Right-handed",
                "uri": "snomed:78791000",
            },
            "A": {
                "label": "Ambidextrous",
                "description": "Ambidextrous",
                "uri": "snomed:16022009",
            },
        },
    }

    # Augmented structure
    augmented = {"properties": {}}

    for col_name, col_data in raw_data.get("properties", {}).items():
        aug_col = {
            "description": col_data.get("description", ""),
            "original_data": col_data,
        }

        # Add standardized variable mapping
        if col_name in standardized_mappings:
            aug_col["standardized_variable"] = standardized_mappings[col_name]

        # Infer data type from Levels (if present, it's categorical)
        if "Levels" in col_data and isinstance(col_data["Levels"], dict):
            aug_col["data_type"] = "categorical"

            # Augment with vocabulary if available
            if col_name in categorical_vocabularies:
                aug_col["levels"] = {}
                for level_key, level_label in col_data["Levels"].items():
                    if level_key in categorical_vocabularies[col_name]:
                        aug_col["levels"][level_key] = categorical_vocabularies[
                            col_name
                        ][level_key]
                    else:
                        # Fallback: use provided label (no URI)
                        aug_col["levels"][level_key] = {
                            "label": (
                                level_label
                                if isinstance(level_label, str)
                                else str(level_key)
                            ),
                            "description": f"Value: {level_key}",
                            "uri": None,
                        }
            else:
                # No vocabulary available, use raw levels (no URIs)
                aug_col["levels"] = {
                    k: {"label": v, "description": f"Value: {k}", "uri": None}
                    for k, v in col_data["Levels"].items()
                }
        elif col_name in ["age"]:
            aug_col["data_type"] = "continuous"
            if "Units" in col_data:
                aug_col["unit"] = col_data["Units"]
        else:
            aug_col["data_type"] = "text"

        augmented["properties"][col_name] = aug_col

    return augmented


@app.route("/api/neurobagel/participants")
def neurobagel_participants():
    """Return NeuroBagel participants dictionary (cached) with augmented annotations.

    The frontend can call this to populate hierarchical suggestions for participants.json fields.
    Returns augmented data with:
    - Standardized variable mappings
    - Data type classifications
    - Categorical value vocabularies with URIs
    """
    data = fetch_neurobagel_participants()

    # If external fetch fails, use built-in dictionary
    if not data:
        # Use built-in NeuroBagel-compatible dictionary for common phenotypic variables
        data = {
            "properties": {
                "participant_id": {"Description": "A participant ID"},
                "age": {"Description": "Age of the participant", "Units": "years"},
                "sex": {
                    "Description": "Biological sex of the participant",
                    "Levels": {"M": "Male", "F": "Female", "O": "Other"},
                },
                "group": {
                    "Description": "Participant group or experimental condition",
                    "Levels": {},
                },
                "handedness": {
                    "Description": "Participant handedness",
                    "Levels": {"L": "Left", "R": "Right", "A": "Ambidextrous"},
                },
            }
        }

    # Augment raw data with standardized mappings and vocabularies
    augmented = augment_neurobagel_data(data)

    return jsonify(
        {
            "source": "neurobagel",
            "raw": data,
            "augmented": augmented,
            "note": (
                "Using built-in dictionary (external fetch failed)"
                if not fetch_neurobagel_participants()
                else "Using remote NeuroBagel dictionary"
            ),
        }
    )


# Note: shorten_path and get_filename_from_path are now imported from src.web.utils


# Global storage for validation results
validation_results = {}


@app.route("/")
def index():
    """Home page with tool selection"""
    return render_template("home.html")


@app.route("/api/progress/<job_id>")
def get_validation_progress(job_id):
    """Get progress for a validation job (polled by UI)."""
    progress_data = get_progress(job_id)
    return jsonify(progress_data)


@app.route("/validate")
def validate_dataset():
    """Dataset validation page with upload form"""
    # Get available schema versions
    schema_dir = os.path.join(os.path.dirname(__file__), "schemas")
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
    try:
        from schema_manager import get_available_schema_versions

        available_versions = get_available_schema_versions(schema_dir)
    except Exception as e:
        print(f"Warning: Could not load schema versions: {e}")
        available_versions = ["stable"]

    return render_template("index.html", schema_versions=available_versions)


@app.route("/upload", methods=["POST"])
def upload_dataset():
    """Handle dataset upload and validation"""
    if "dataset" not in request.files:
        flash("No dataset uploaded", "error")
        return redirect(url_for("index"))

    files = request.files.getlist("dataset")
    if not files or (len(files) == 1 and files[0].filename == ""):
        flash("No files selected", "error")
        return redirect(url_for("index"))

    # Get schema version from form
    schema_version = request.form.get("schema_version", "stable")

    # Create temporary directory for processing
    temp_dir = tempfile.mkdtemp(prefix="prism_validator_")

    # Try to get metadata paths from JSON first (new method), fall back to list (old method)
    metadata_paths_json = request.form.get("metadata_paths_json")
    if metadata_paths_json:
        try:
            metadata_paths = json.loads(metadata_paths_json)
        except json.JSONDecodeError:
            metadata_paths = []
    else:
        metadata_paths = request.form.getlist("metadata_paths[]")

    try:
        # Check if this is a folder upload (multiple files) or ZIP upload (single file)
        if len(files) > 1 or (
            len(files) == 1 and not files[0].filename.lower().endswith(".zip")
        ):
            # Handle folder upload
            dataset_path = process_folder_upload(files, temp_dir, metadata_paths)
            filename = f"folder_upload_{len(files)}_files"
        else:
            # Handle ZIP upload
            file = files[0]
            filename = secure_filename(file.filename)
            if not filename.lower().endswith(".zip"):
                flash("Please upload a ZIP file or select a folder", "error")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return redirect(url_for("index"))

            dataset_path = process_zip_upload(file, temp_dir, filename)

        # DEBUG: Print dataset_path and sample files (excluding system files)
        print(f"📁 [UPLOAD] Validating dataset at: {dataset_path}")
        for root, dirs, files in os.walk(dataset_path):
            # Filter out system files from debug output
            try:
                filtered_files = [f for f in files if not is_system_file(f)]
            except NameError:
                # Fallback filtering
                filtered_files = [
                    f
                    for f in files
                    if not (
                        f.startswith(".")
                        or f in ["Thumbs.db", "ehthumbs.db", "Desktop.ini"]
                    )
                ]

            for file in filtered_files[:10]:
                print(f"   {os.path.relpath(os.path.join(root, file), dataset_path)}")
            if len(files) != len(filtered_files):
                print(f"   (+ {len(files) - len(filtered_files)} system files ignored)")
            break
        # Get BIDS options
        run_bids = request.form.get("run_bids") == "true"
        show_bids_warnings = request.form.get("bids_warnings") == "true"
        
        # Generate a job ID for progress tracking
        import uuid
        job_id = request.form.get("job_id", str(uuid.uuid4()))
        
        # Create progress callback
        def progress_callback(progress: int, message: str):
            update_progress(job_id, progress, message)

        # Validate the dataset using unified validation function
        issues, dataset_stats = run_validation(
            dataset_path, 
            verbose=True, 
            schema_version=schema_version,
            run_bids=run_bids,
            progress_callback=progress_callback
        )
        
        # Mark progress as complete
        update_progress(job_id, 100, "Validation complete")

        # Filter BIDS warnings if requested
        if not show_bids_warnings:
            issues = [i for i in issues if not (i[0] == "WARNING" and "[BIDS]" in i[1])]

        results = format_validation_results(issues, dataset_stats, dataset_path)

        # Add timestamp, upload type info, and schema version
        from datetime import datetime

        results["timestamp"] = datetime.now().isoformat()
        results["upload_type"] = "structure_only"
        results["schema_version"] = schema_version
        results["job_id"] = job_id

        # Check if manifest exists and add details
        manifest_path = os.path.join(dataset_path, ".upload_manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
            results["upload_manifest"] = {
                "metadata_files": len(manifest.get("uploaded_files", [])),
                "placeholder_files": len(manifest.get("placeholder_files", [])),
                "upload_mode": "DataLad-style (structure + metadata only)",
            }

        # DEBUG: Print summary to console
        print("📊 Validation complete:")
        print(f"   Total files: {results['summary']['total_files']}")
        print(f"   Valid files: {results['summary']['valid_files']}")
        print(f"   Invalid files: {results['summary']['invalid_files']}")
        print(f"   Total errors: {results['summary']['total_errors']}")

        # Store results globally (in production, use a database)
        result_id = f"result_{len(validation_results)}"
        validation_results[result_id] = {
            "results": results,
            "dataset_path": dataset_path,
            "temp_dir": temp_dir,
            "filename": filename,
        }

        return redirect(url_for("show_results", result_id=result_id))

    except Exception as e:
        # Clean up on error
        print(f"❌ [UPLOAD ERROR] {type(e).__name__}: {str(e)}")
        import traceback

        traceback.print_exc()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        flash(f"Error processing dataset: {str(e)}", "error")
        return redirect(url_for("index"))


def create_placeholder_content(file_path, extension):
    """Create informative placeholder content for data files (DataLad-style)"""
    filename = os.path.basename(file_path)

    # For JSON files, create valid JSON placeholders
    if extension.lower() == ".json":
        return json.dumps(
            {
                "_placeholder": True,
                "_upload_mode": "DataLad-style (structure + metadata only)",
                "_original_filename": filename,
                "_created": datetime.now().isoformat(),
                "_note": "This is a placeholder file. Original JSON was not uploaded to reduce transfer size.",
            },
            indent=2,
        )

    # For TSV files, create valid TSV placeholders
    elif extension.lower() == ".tsv":
        return f"# PLACEHOLDER TSV - DataLad-style Upload\n# Original filename: {filename}\n# Created: {datetime.now().isoformat()}\n_placeholder\ttrue\n"

    # For other file types, use text placeholder
    else:
        # Determine file type from extension
        file_type_map = {
            ".nii": "NIfTI neuroimaging data",
            ".nii.gz": "Compressed NIfTI neuroimaging data",
            ".png": "PNG image stimulus",
            ".jpg": "JPEG image stimulus",
            ".jpeg": "JPEG image stimulus",
            ".tiff": "TIFF image data",
            ".mp4": "MP4 video stimulus",
            ".avi": "AVI video data",
            ".mov": "QuickTime video",
            ".eeg": "EEG raw data",
            ".dat": "Binary data file",
            ".fif": "Neuromag/MNE data",
            ".mat": "MATLAB data file",
            ".edf": "European Data Format (EEG/Physio)",
            ".bdf": "BioSemi Data Format",
            ".set": "EEGLAB dataset info",
            ".fdt": "EEGLAB data file",
        }

        file_type = file_type_map.get(extension, f"{extension} data file")

        placeholder = f"""# PLACEHOLDER FILE - DataLad-style Upload
# This is a placeholder for the original data file that was not uploaded
# to reduce transfer size and processing time.

Original filename: {filename}
File type: {file_type}
Upload mode: Structure-only validation
Created: {datetime.now().isoformat()}

# The validator can still check:
# - File naming conventions
# - Directory structure
# - Metadata completeness (via JSON sidecars)
# - BIDS compliance

# Note: Full content validation requires the complete dataset.
"""
        return placeholder


def detect_dataset_prefix(all_paths):
    """Detect a common leading folder that should be stripped from uploaded paths."""
    sanitized_parts = []
    has_root_level_files = False
    for path in all_paths or []:
        if not path:
            continue
        parts = [part for part in path.replace("\\", "/").split("/") if part]
        if not parts:
            continue
        if len(parts) == 1:
            has_root_level_files = True
        sanitized_parts.append(parts)
    if has_root_level_files or not sanitized_parts:
        return None
    first_components = {parts[0] for parts in sanitized_parts}
    if len(first_components) != 1:
        return None
    candidate = first_components.pop()
    restricted_names = {
        "image",
        "audio",
        "movie",
        "survey",
        "eyetracking",
        "physiological",
        "dataset",
    }
    if candidate.startswith(("sub-", "ses-")) or candidate in restricted_names:
        return None
    has_dataset_description = any(
        len(parts) >= 2
        and parts[0] == candidate
        and parts[1] == "dataset_description.json"
        for parts in sanitized_parts
    )
    has_subject_dirs = any(
        len(parts) >= 2 and parts[0] == candidate and parts[1].startswith("sub-")
        for parts in sanitized_parts
    )
    if not (has_dataset_description or has_subject_dirs):
        return None
    return candidate


def normalize_relative_path(path, prefix_to_strip):
    """Normalise an uploaded path so it is safe and relative to the dataset root."""
    if not path:
        return None
    cleaned = path.replace("\\", "/").lstrip("/")
    if prefix_to_strip:
        prefix = prefix_to_strip.strip("/")
        if cleaned.startswith(prefix + "/"):
            cleaned = cleaned[len(prefix) + 1 :]
    normalized = os.path.normpath(cleaned)
    normalized = normalized.replace("\\", "/")
    if normalized in ("", "."):  # Directory only
        return None
    if normalized.startswith(".."):
        return None
    return normalized


def process_folder_upload(files, temp_dir, metadata_paths=None):
    """Process uploaded folder files and recreate directory structure (DataLad-style)

    DataLad-inspired approach: Upload only structure and metadata, create placeholders
    for large data files. This allows full dataset validation without transferring GB of data.
    """
    dataset_root = os.path.join(temp_dir, "dataset")
    os.makedirs(dataset_root, exist_ok=True)

    processed_count = 0
    skipped_count = 0
    manifest = {
        "uploaded_files": [],
        "placeholder_files": [],
        "upload_type": "structure_only",
        "timestamp": datetime.now().isoformat(),
    }

    # Get the list of all files (including skipped ones) from form data
    all_files_json = request.form.get("all_files")
    all_files_list = json.loads(all_files_json) if all_files_json else []
    metadata_paths = metadata_paths or []

    candidate_paths = list(all_files_list or [])
    if metadata_paths:
        candidate_paths.extend(metadata_paths)
    else:
        candidate_paths.extend(
            [f.filename for f in files if getattr(f, "filename", None)]
        )

    prefix_to_strip = detect_dataset_prefix(candidate_paths)
    if prefix_to_strip:
        print(f"📁 [UPLOAD] Stripping leading folder: {prefix_to_strip}")

    # Create a set of uploaded file paths for quick lookup
    uploaded_paths = set()

    if metadata_paths and len(metadata_paths) != len(files):
        print(
            f"⚠️  Metadata path count ({len(metadata_paths)}) does not match uploaded files ({len(files)})."
        )

    for index, file in enumerate(files):
        original_path = (
            metadata_paths[index]
            if index < len(metadata_paths)
            else getattr(file, "filename", "")
        )
        if not original_path:
            continue
        normalized_path = normalize_relative_path(original_path, prefix_to_strip)
        if not normalized_path:
            continue

        # Skip system files (like .DS_Store, Thumbs.db, etc.)
        filename = os.path.basename(normalized_path)
        try:
            if is_system_file(filename):
                continue
        except NameError:
            if filename.startswith(".") and filename in [
                ".DS_Store",
                "._.DS_Store",
                ".Spotlight-V100",
                ".Trashes",
            ]:
                continue
            if filename in ["Thumbs.db", "ehthumbs.db", "Desktop.ini"]:
                continue

        uploaded_paths.add(normalized_path)
        file_path = os.path.join(dataset_root, *normalized_path.split("/"))
        target_dir = os.path.dirname(file_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        file.save(file_path)
        processed_count += 1

        manifest["uploaded_files"].append(
            {
                "path": normalized_path,
                "size": file.content_length or 0,
                "type": "metadata",
            }
        )

    # Create smart placeholders for all files that weren't uploaded
    for relative_path in all_files_list:
        normalized_path = normalize_relative_path(relative_path, prefix_to_strip)
        if not normalized_path or normalized_path in uploaded_paths:
            continue

        filename = os.path.basename(normalized_path)
        try:
            if is_system_file(filename):
                continue
        except NameError:
            if filename.startswith(".") and filename in [
                ".DS_Store",
                "._.DS_Store",
                ".Spotlight-V100",
                ".Trashes",
            ]:
                continue
            if filename in ["Thumbs.db", "ehthumbs.db", "Desktop.ini"]:
                continue

        file_path = os.path.join(dataset_root, *normalized_path.split("/"))
        target_dir = os.path.dirname(file_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        lower_path = normalized_path.lower()
        if lower_path.endswith(".nii.gz"):
            ext = ".nii.gz"
        else:
            _, ext = os.path.splitext(lower_path)
        placeholder_content = create_placeholder_content(normalized_path, ext)
        with open(file_path, "w") as f:
            f.write(placeholder_content)
        skipped_count += 1

        manifest["placeholder_files"].append(
            {"path": normalized_path, "extension": ext, "type": "placeholder"}
        )

    # Save manifest file for debugging and transparency
    manifest_path = os.path.join(dataset_root, ".upload_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(
        f"📁 Processed {processed_count} metadata files, created {skipped_count} placeholders for data files"
    )
    print("📁 [UPLOAD] File tree in temp_dir after upload:")
    for root, dirs, files in os.walk(dataset_root):
        for file in files:
            rel_path = os.path.relpath(os.path.join(root, file), dataset_root)
            print(f"   {rel_path}")
    return dataset_root


def process_zip_upload(file, temp_dir, filename):
    """Process uploaded ZIP file

    Extracts only metadata files from ZIP to reduce processing time and storage.
    """
    file_path = os.path.join(temp_dir, filename)
    file.save(file_path)

    processed_count = 0
    skipped_count = 0

    # Extract ZIP file selectively
    with zipfile.ZipFile(file_path, "r") as zip_ref:
        for zip_info in zip_ref.namelist():
            # Skip directories
            if zip_info.endswith("/"):
                continue

            # Check file extension
            _, ext = os.path.splitext(zip_info.lower())
            if ext == ".gz" and zip_info.lower().endswith(".nii.gz"):
                ext = ".nii.gz"

            # Extract metadata files, skip large data files
            if ext in METADATA_EXTENSIONS or ext == "":
                zip_ref.extract(zip_info, temp_dir)
                processed_count += 1
            elif ext in SKIP_EXTENSIONS:
                # Create empty placeholder
                extract_path = os.path.join(temp_dir, zip_info)
                os.makedirs(os.path.dirname(extract_path), exist_ok=True)
                with open(extract_path, "w") as f:
                    f.write("")
                skipped_count += 1

    print(
        f"📦 Extracted {processed_count} metadata files, skipped {skipped_count} data files from ZIP"
    )

    # Find the actual dataset directory (might be nested)
    return find_dataset_root(temp_dir)


@app.route("/validate_folder", methods=["POST"])
def validate_folder():
    """Handle local folder validation"""
    folder_path = request.form.get("folder_path", "").strip()

    if not folder_path:
        flash("Please provide a folder path", "error")
        return redirect(url_for("index"))

    if not os.path.exists(folder_path):
        flash("Folder does not exist", "error")
        return redirect(url_for("index"))

    if not os.path.isdir(folder_path):
        flash("Path is not a directory", "error")
        return redirect(url_for("index"))

    # Get schema version from form
    schema_version = request.form.get("schema_version", "stable")

    try:
        # Print validation start info to terminal
        print(f"\n📁 [VALIDATE_FOLDER] Validating local directory: {folder_path}")

        # Count files for debug output
        file_count = 0
        for root, dirs, files in os.walk(folder_path):
            file_count += len([f for f in files if not is_system_file(f)])
        print(f"   Found {file_count} non-system files in directory")

        # Get BIDS options
        run_bids = request.form.get("run_bids") == "true"
        show_bids_warnings = request.form.get("bids_warnings") == "true"
        
        # Generate job ID for progress tracking
        import uuid
        job_id = request.form.get("job_id", str(uuid.uuid4()))
        
        def progress_callback(progress: int, message: str):
            update_progress(job_id, progress, message)

        # Use unified validation function
        issues, stats = run_validation(
            folder_path, 
            verbose=True, 
            schema_version=schema_version,
            run_bids=run_bids,
            progress_callback=progress_callback
        )
        
        # Mark progress as complete
        update_progress(job_id, 100, "Validation complete")

        # Filter BIDS warnings if requested
        if not show_bids_warnings:
            issues = [i for i in issues if not (i[0] == "WARNING" and "[BIDS]" in i[1])]

        # Format results for web display
        formatted_results = format_validation_results(issues, stats, folder_path)
        formatted_results["schema_version"] = schema_version

        # Print validation results to terminal
        print("📊 [VALIDATE_FOLDER] Validation complete:")
        print(f"   Total files: {formatted_results['summary']['total_files']}")
        print(f"   Valid files: {formatted_results['summary']['valid_files']}")
        print(f"   Invalid files: {formatted_results['summary']['invalid_files']}")
        print(f"   Errors: {formatted_results['summary']['total_errors']}")
        print(f"   Warnings: {formatted_results['summary']['total_warnings']}")

        # Store results
        result_id = f"result_{len(validation_results)}"
        validation_results[result_id] = {
            "results": formatted_results,
            "dataset_path": folder_path,
            "temp_dir": None,  # No temp dir for local folders
            "filename": os.path.basename(folder_path),
        }

        return redirect(url_for("show_results", result_id=result_id))

    except Exception as e:
        flash(f"Error validating dataset: {str(e)}", "error")
        return redirect(url_for("index"))


@app.route("/results/<result_id>")
def show_results(result_id):
    """Display validation results"""
    if result_id not in validation_results:
        flash("Results not found", "error")
        return redirect(url_for("index"))

    data = validation_results[result_id]
    results = data["results"]

    # Get dataset stats if available
    dataset_stats = None
    stats_obj = results.get("dataset_stats")
    if stats_obj:
        try:
            session_entries = getattr(stats_obj, "sessions", set()) or set()
            unique_sessions = set()
            for entry in session_entries:
                if isinstance(entry, str) and "/" in entry:
                    unique_sessions.add(entry.split("/", 1)[1])
                elif entry:
                    unique_sessions.add(entry)

            dataset_stats = {
                "total_subjects": len(getattr(stats_obj, "subjects", [])),
                "total_sessions": len(unique_sessions),
                "modalities": getattr(stats_obj, "modalities", {}),
                "tasks": sorted(getattr(stats_obj, "tasks", [])),
                "total_files": getattr(stats_obj, "total_files", 0),
                "sidecar_files": getattr(stats_obj, "sidecar_files", 0),
            }
        except Exception as stats_error:
            print(f"⚠️  Failed to prepare dataset stats for display: {stats_error}")

    return render_template(
        "results.html",
        results=results,
        result_id=result_id,
        filename=data["filename"],
        dataset_stats=dataset_stats,
        shorten_path=shorten_path,
        get_filename_from_path=get_filename_from_path,
        get_error_documentation_url=get_error_documentation_url,
    )


@app.route("/download_report/<result_id>")
def download_report(result_id):
    """Download validation report as JSON"""
    if result_id not in validation_results:
        flash("Results not found", "error")
        return redirect(url_for("index"))

    data = validation_results[result_id]
    results = data["results"]

    # Create JSON report
    report = {
        "dataset": data["filename"],
        "validation_timestamp": results.get("timestamp", ""),
        "summary": {
            "total_files": len(results.get("valid_files", []))
            + len(results.get("invalid_files", [])),
            "valid_files": len(results.get("valid_files", [])),
            "invalid_files": len(results.get("invalid_files", [])),
            "total_errors": len(results.get("errors", [])),
            "total_warnings": len(results.get("warnings", [])),
        },
        "results": results,
    }

    # Create in-memory file
    output = io.BytesIO()
    output.write(json.dumps(report, indent=2).encode("utf-8"))
    output.seek(0)

    return send_file(
        output,
        mimetype="application/json",
        as_attachment=True,
        download_name=f"validation_report_{data['filename']}.json",
    )


@app.route("/cleanup/<result_id>")
def cleanup(result_id):
    """Clean up temporary files"""
    if result_id in validation_results:
        data = validation_results[result_id]
        if data["temp_dir"] and os.path.exists(data["temp_dir"]):
            shutil.rmtree(data["temp_dir"], ignore_errors=True)
        del validation_results[result_id]

    flash("Results cleaned up", "success")
    return redirect(url_for("index"))


@app.route("/api/validate", methods=["POST"])
def api_validate():
    """API endpoint for validation (for programmatic access)"""
    try:
        data = request.get_json()
        if not data or "dataset_path" not in data:
            return jsonify({"error": "Missing dataset_path parameter"}), 400

        dataset_path = data["dataset_path"]
        if not os.path.exists(dataset_path):
            return jsonify({"error": "Dataset path does not exist"}), 400

        # Use unified validation function
        issues, stats = run_validation(dataset_path, verbose=False)
        results = format_validation_results(issues, stats, dataset_path)

        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/api/survey-convert", methods=["POST"])
def api_survey_convert():
    """Convert an uploaded survey file (.xlsx or .lsa) to a PRISM dataset and return it as a zip.

    Note: For .lsa inputs, language=auto will try to infer the language from the archive.
    """
    if not convert_survey_xlsx_to_prism_dataset and not convert_survey_lsa_to_prism_dataset:
        return jsonify({"error": "Survey conversion module not available"}), 500

    uploaded_file = request.files.get("excel") or request.files.get("file")
    alias_upload = request.files.get("alias") or request.files.get("alias_file")
    library_path = (request.form.get("library_path") or "").strip()

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xlsx", ".lsa", ".csv", ".tsv"}:
        return jsonify({"error": "Supported formats: .xlsx, .lsa, .csv, .tsv"}), 400

    alias_filename = None
    alias_suffix = None
    if alias_upload and getattr(alias_upload, "filename", ""):
        alias_filename = secure_filename(alias_upload.filename)
        alias_suffix = Path(alias_filename).suffix.lower()
        if alias_suffix and alias_suffix not in {".tsv", ".txt"}:
            return jsonify({"error": "Alias file must be a .tsv or .txt mapping file"}), 400

    if not library_path:
        return jsonify({"error": "Survey template library path is required. Due to copyright restrictions, templates cannot be distributed with the application."}), 400

    if not os.path.exists(library_path) or not os.path.isdir(library_path):
        return jsonify({"error": f"Library path is not a directory: {library_path}"}), 400
    
    # Check if the library has any survey templates
    # Support both root/survey/ structure and direct survey folder
    library_root = Path(library_path)
    survey_dir = library_root / "survey"
    if survey_dir.is_dir():
        # User selected the root library folder, use survey/ subfolder
        effective_survey_dir = survey_dir
    else:
        # User selected the survey folder directly (backwards compatibility)
        effective_survey_dir = library_root
    
    survey_templates = list(effective_survey_dir.glob("survey-*.json"))
    if not survey_templates:
        return jsonify({"error": f"No survey templates (survey-*.json) found in: {effective_survey_dir}. Expected either {library_path}/survey/ or survey-*.json files directly."}), 400

    survey_filter = (request.form.get("survey") or "").strip() or None
    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    dataset_name = (request.form.get("dataset_name") or "").strip() or None
    language = (request.form.get("language") or "").strip() or None

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_convert_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        alias_path = None
        if alias_filename:
            alias_path = tmp_dir_path / alias_filename
            alias_upload.save(str(alias_path))

        output_root = tmp_dir_path / "prism_dataset"

        detected_language = None
        detected_platform = None
        detected_version = None

        if suffix == ".lsa" and infer_lsa_metadata:
            try:
                meta = infer_lsa_metadata(input_path)
                detected_language = meta.get("language")
                detected_platform = meta.get("software_platform")
                detected_version = meta.get("software_version")
            except Exception:
                pass

        if suffix in {".xlsx", ".csv", ".tsv"}:
            if not convert_survey_xlsx_to_prism_dataset:
                return jsonify({"error": "Tabular data conversion is not available in this build"}), 500
            convert_survey_xlsx_to_prism_dataset(
                input_path=input_path,
                library_dir=str(effective_survey_dir),
                output_root=output_root,
                survey=survey_filter,
                id_column=id_column,
                session_column=session_column,
                sheet=sheet,
                unknown=unknown,
                dry_run=False,
                force=True,
                name=dataset_name,
                authors=["prism-studio"],
                language=language,
                alias_file=alias_path,
            )
        elif suffix == ".lsa":
            if not convert_survey_lsa_to_prism_dataset:
                return jsonify({"error": "LimeSurvey (.lsa) conversion is not available in this build"}), 500
            convert_survey_lsa_to_prism_dataset(
                input_path=input_path,
                library_dir=str(effective_survey_dir),
                output_root=output_root,
                survey=survey_filter,
                id_column=id_column,
                session_column=session_column,
                unknown=unknown,
                dry_run=False,
                force=True,
                name=dataset_name,
                authors=["prism-studio"],
                language=language,
                alias_file=alias_path,
            )

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in output_root.rglob("*"):
                if p.is_file():
                    arcname = p.relative_to(output_root)
                    zf.write(p, arcname.as_posix())
        mem.seek(0)

        resp = send_file(
            mem,
            mimetype="application/zip",
            as_attachment=True,
            download_name="prism_survey_dataset.zip",
        )

        # Lightweight UI feedback: expose inferred metadata via headers.
        # Frontend reads these and shows a message without extra endpoints.
        if detected_language:
            resp.headers["X-Prism-Detected-Language"] = str(detected_language)
        if detected_platform:
            resp.headers["X-Prism-Detected-SoftwarePlatform"] = str(detected_platform)
        if detected_version:
            resp.headers["X-Prism-Detected-SoftwareVersion"] = str(detected_version)

        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


@app.route("/api/survey-convert-validate", methods=["POST"])
def api_survey_convert_validate():
    """Convert survey data and validate the result before allowing download.
    
    Returns JSON with:
    - log: Array of log messages with type (info, success, warning, error)
    - validation: Object with errors, warnings, and summary
    - zip_base64: Base64-encoded ZIP file (only if conversion succeeded)
    """
    import base64
    
    if not convert_survey_xlsx_to_prism_dataset and not convert_survey_lsa_to_prism_dataset:
        return jsonify({"error": "Survey conversion module not available"}), 500

    log_messages = []
    
    def add_log(message, msg_type="info"):
        log_messages.append({"message": message, "type": msg_type})

    uploaded_file = request.files.get("excel") or request.files.get("file")
    alias_upload = request.files.get("alias") or request.files.get("alias_file")
    library_path = (request.form.get("library_path") or "").strip()

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file", "log": log_messages}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xlsx", ".lsa", ".csv", ".tsv"}:
        return jsonify({"error": "Supported formats: .xlsx, .lsa, .csv, .tsv", "log": log_messages}), 400

    add_log(f"Processing file: {filename}", "info")

    if not library_path:
        return jsonify({"error": "Survey template library path is required.", "log": log_messages}), 400

    if not os.path.exists(library_path) or not os.path.isdir(library_path):
        return jsonify({"error": f"Library path is not a directory: {library_path}", "log": log_messages}), 400
    
    # Support both root/survey/ structure and direct survey folder
    library_root = Path(library_path)
    survey_dir = library_root / "survey"
    if survey_dir.is_dir():
        effective_survey_dir = survey_dir
        add_log(f"Using survey subfolder: {survey_dir}", "info")
    else:
        effective_survey_dir = library_root
    
    survey_templates = list(effective_survey_dir.glob("survey-*.json"))
    if not survey_templates:
        return jsonify({"error": f"No survey templates found in: {effective_survey_dir}", "log": log_messages}), 400

    add_log(f"Found {len(survey_templates)} survey template(s) in library", "info")
    
    # Check for participants.json template
    participants_template = library_root / "participants.json"
    if participants_template.exists():
        add_log("Found participants.json template", "info")

    alias_filename = None
    if alias_upload and getattr(alias_upload, "filename", ""):
        alias_filename = secure_filename(alias_upload.filename)
        alias_suffix = Path(alias_filename).suffix.lower()
        if alias_suffix and alias_suffix not in {".tsv", ".txt"}:
            return jsonify({"error": "Alias file must be a .tsv or .txt mapping file", "log": log_messages}), 400

    survey_filter = (request.form.get("survey") or "").strip() or None
    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    dataset_name = (request.form.get("dataset_name") or "").strip() or None
    language = (request.form.get("language") or "").strip() or None

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_convert_validate_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        alias_path = None
        if alias_filename:
            alias_path = tmp_dir_path / alias_filename
            alias_upload.save(str(alias_path))
            add_log(f"Using alias mapping file: {alias_filename}", "step")

        output_root = tmp_dir_path / "prism_dataset"

        add_log("Starting data conversion...", "info")

        # Run conversion
        if suffix in {".xlsx", ".csv", ".tsv"}:
            if not convert_survey_xlsx_to_prism_dataset:
                return jsonify({"error": "Tabular data conversion not available", "log": log_messages}), 500
            convert_survey_xlsx_to_prism_dataset(
                input_path=input_path,
                library_dir=str(effective_survey_dir),
                output_root=output_root,
                survey=survey_filter,
                id_column=id_column,
                session_column=session_column,
                sheet=sheet,
                unknown=unknown,
                dry_run=False,
                force=True,
                name=dataset_name,
                authors=["prism-studio"],
                language=language,
                alias_file=alias_path,
            )
        elif suffix == ".lsa":
            if not convert_survey_lsa_to_prism_dataset:
                return jsonify({"error": "LimeSurvey conversion not available", "log": log_messages}), 500
            convert_survey_lsa_to_prism_dataset(
                input_path=input_path,
                library_dir=str(effective_survey_dir),
                output_root=output_root,
                survey=survey_filter,
                id_column=id_column,
                session_column=session_column,
                unknown=unknown,
                dry_run=False,
                force=True,
                name=dataset_name,
                authors=["prism-studio"],
                language=language,
                alias_file=alias_path,
            )

        add_log("Conversion completed", "success")

        # Count created files
        created_files = list(output_root.rglob("*"))
        file_count = len([f for f in created_files if f.is_file()])
        add_log(f"Created {file_count} files in dataset", "info")

        # Run validation on the converted dataset
        add_log("Running validation on converted dataset...", "info")
        
        validation_result = {
            "errors": [],
            "warnings": [],
            "summary": {
                "files_created": file_count,
            }
        }

        try:
            # Use the same validation function as the main validator
            # run_validation returns a tuple: (messages_list, stats_object)
            result = run_validation(str(output_root), schema_version="stable")
            
            if result and isinstance(result, tuple) and len(result) >= 1:
                messages = result[0] if result[0] else []
                stats = result[1] if len(result) > 1 else None
                
                # Parse messages: each is a tuple like ('ERROR', 'message', 'path')
                for msg in messages:
                    if isinstance(msg, tuple) and len(msg) >= 2:
                        level = msg[0].upper() if msg[0] else "INFO"
                        text = msg[1] if len(msg) > 1 else str(msg)
                        path = msg[2] if len(msg) > 2 else ""
                        
                        # Format the message nicely
                        full_msg = text
                        if path:
                            # Just show filename, not full temp path
                            path_name = Path(path).name if "/" in str(path) else path
                            if path_name and path_name != text:
                                full_msg = f"{text}"
                        
                        if level == "ERROR":
                            validation_result["errors"].append(full_msg)
                        elif level == "WARNING":
                            validation_result["warnings"].append(full_msg)
                    elif isinstance(msg, str):
                        validation_result["warnings"].append(msg)
                
                # Get stats if available
                if stats and hasattr(stats, "__dict__"):
                    for key, value in vars(stats).items():
                        if not key.startswith("_"):
                            # Convert sets to sorted lists for JSON serialization
                            if isinstance(value, set):
                                validation_result["summary"][key] = sorted(value)
                            else:
                                validation_result["summary"][key] = value
                    
        except Exception as val_err:
            add_log(f"Validation error: {str(val_err)}", "warning")
            validation_result["warnings"].append(f"Could not run full validation: {str(val_err)}")

        # Create ZIP file
        add_log("Creating ZIP archive...", "info")
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in output_root.rglob("*"):
                if p.is_file():
                    arcname = p.relative_to(output_root)
                    zf.write(p, arcname.as_posix())
        mem.seek(0)
        
        # Encode ZIP as base64 for JSON response
        zip_base64 = base64.b64encode(mem.read()).decode('utf-8')

        add_log("Dataset package ready", "success")

        return jsonify({
            "success": True,
            "log": log_messages,
            "validation": validation_result,
            "zip_base64": zip_base64,
        })

    except Exception as e:
        add_log(f"Conversion failed: {str(e)}", "error")
        return jsonify({
            "error": str(e),
            "log": log_messages,
            "validation": {"errors": [str(e)], "warnings": [], "summary": {}}
        }), 500
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


@app.route("/api/survey-languages", methods=["GET"])
def api_survey_languages():
    """List available languages for the selected survey template library folder."""
    library_path = (request.args.get("library_path") or "").strip()
    if not library_path:
        preferred = (BASE_DIR / "library" / "survey_i18n").resolve()
        fallback = (BASE_DIR / "survey_library").resolve()
        if preferred.exists() and any(preferred.glob("survey-*.json")):
            library_path = str(preferred)
        else:
            library_path = str(fallback)

    # Check structure of library root
    library_root = Path(library_path)
    structure_info = {
        "has_survey_folder": False,
        "has_biometrics_folder": False,
        "has_participants_json": False,
        "missing_items": []
    }
    
    # Check for expected items
    survey_dir = library_root / "survey"
    biometrics_dir = library_root / "biometrics"
    participants_json = library_root / "participants.json"
    
    structure_info["has_survey_folder"] = survey_dir.is_dir()
    structure_info["has_biometrics_folder"] = biometrics_dir.is_dir()
    structure_info["has_participants_json"] = participants_json.is_file()
    
    # Build missing items list for survey conversion
    if not structure_info["has_survey_folder"]:
        structure_info["missing_items"].append("survey/")
    if not structure_info["has_participants_json"]:
        structure_info["missing_items"].append("participants.json")
    
    # Determine effective survey directory
    if survey_dir.is_dir():
        effective_survey_dir = str(survey_dir)
    else:
        effective_survey_dir = library_path

    langs, default, template_count, i18n_count = _list_survey_template_languages(effective_survey_dir)
    return jsonify({
        "languages": langs, 
        "default": default, 
        "library_path": effective_survey_dir,
        "template_count": template_count,
        "i18n_count": i18n_count,
        "structure": structure_info
    })


@app.route("/api/biometrics-check-library", methods=["GET"])
def api_biometrics_check_library():
    """Check the structure of a biometrics template library folder."""
    library_path = (request.args.get("library_path") or "").strip()
    
    if not library_path:
        return jsonify({"error": "No library path provided"}), 400

    # Check structure of library root
    library_root = Path(library_path)
    structure_info = {
        "has_survey_folder": False,
        "has_biometrics_folder": False,
        "has_participants_json": False,
        "missing_items": [],
        "template_count": 0
    }
    
    # Check for expected items
    survey_dir = library_root / "survey"
    biometrics_dir = library_root / "biometrics"
    participants_json = library_root / "participants.json"
    
    structure_info["has_survey_folder"] = survey_dir.is_dir()
    structure_info["has_biometrics_folder"] = biometrics_dir.is_dir()
    structure_info["has_participants_json"] = participants_json.is_file()
    
    # Build missing items list for biometrics conversion
    if not structure_info["has_biometrics_folder"]:
        structure_info["missing_items"].append("biometrics/")
    if not structure_info["has_participants_json"]:
        structure_info["missing_items"].append("participants.json")
    
    # Count templates in biometrics folder
    if biometrics_dir.is_dir():
        structure_info["template_count"] = len(list(biometrics_dir.glob("biometrics-*.json")))
    
    return jsonify({"structure": structure_info})


@app.route("/api/biometrics-convert", methods=["POST"])
def api_biometrics_convert():
    """Convert an uploaded biometrics table (.csv or .xlsx) into a PRISM/BIDS-style dataset ZIP."""
    if not convert_biometrics_table_to_prism_dataset:
        return jsonify({"error": "Biometrics conversion module not available"}), 500

    uploaded_file = request.files.get("data") or request.files.get("file")
    library_path = (request.form.get("library_path") or "").strip()

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx", ".tsv"}:
        return jsonify({"error": "Supported formats: .csv, .xlsx, .tsv"}), 400

    if not library_path:
        return jsonify({"error": "Biometrics template library path is required. Due to copyright restrictions, templates cannot be distributed with the application."}), 400

    if not os.path.exists(library_path) or not os.path.isdir(library_path):
        return jsonify({"error": f"Library path is not a directory: {library_path}"}), 400
    
    # Support both root/biometrics/ structure and direct biometrics folder
    library_root = Path(library_path)
    biometrics_dir = library_root / "biometrics"
    if biometrics_dir.is_dir():
        effective_biometrics_dir = biometrics_dir
    else:
        effective_biometrics_dir = library_root
    
    biometrics_templates = list(effective_biometrics_dir.glob("biometrics-*.json"))
    if not biometrics_templates:
        return jsonify({"error": f"No biometrics templates (biometrics-*.json) found in: {effective_biometrics_dir}. Expected either {library_path}/biometrics/ or biometrics-*.json files directly."}), 400

    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    dataset_name = (request.form.get("dataset_name") or "").strip() or None

    tmp_dir = tempfile.mkdtemp(prefix="prism_biometrics_convert_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        output_root = tmp_dir_path / "prism_dataset"

        convert_biometrics_table_to_prism_dataset(
            input_path=input_path,
            library_dir=str(effective_biometrics_dir),
            output_root=output_root,
            id_column=id_column,
            session_column=session_column,
            sheet=sheet,
            unknown=unknown,
            force=True,
            name=dataset_name,
            authors=["prism-studio"],
        )

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in output_root.rglob("*"):
                if p.is_file():
                    arcname = p.relative_to(output_root)
                    zf.write(p, arcname.as_posix())
        mem.seek(0)

        return send_file(
            mem,
            mimetype="application/zip",
            as_attachment=True,
            download_name="prism_biometrics_dataset.zip",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


@app.route("/api/physio-convert", methods=["POST"])
def api_physio_convert():
    """Convert an uploaded Varioport file (.raw/.vpd) into EDF+ (.edf) + sidecar (.json) and return as ZIP."""
    if not convert_varioport:
        return jsonify({"error": "Physio conversion (Varioport) not available"}), 500

    uploaded_file = request.files.get("raw") or request.files.get("file")
    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".raw", ".vpd"}:
        return jsonify({"error": "Only Varioport .raw and .vpd files are supported"}), 400

    task = (request.form.get("task") or "rest").strip() or "rest"
    base_freq = (request.form.get("sampling_rate") or "").strip() or None
    try:
        base_freq_val = float(base_freq) if base_freq is not None else None
    except Exception:
        return jsonify({"error": "sampling_rate must be a number"}), 400

    tmp_dir = tempfile.mkdtemp(prefix="prism_physio_convert_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        out_edf = tmp_dir_path / (input_path.stem + ".edf")
        out_json = tmp_dir_path / (input_path.stem + ".json")

        convert_varioport(
            str(input_path),
            str(out_edf),
            str(out_json),
            task_name=task,
            base_freq=base_freq_val,
        )

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            if out_edf.exists():
                zf.write(out_edf, out_edf.name)
            if out_json.exists():
                zf.write(out_json, out_json.name)
        mem.seek(0)

        return send_file(
            mem,
            mimetype="application/zip",
            as_attachment=True,
            download_name="varioport_edfplus.zip",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


# Batch conversion job tracking
_batch_convert_jobs = {}  # job_id -> {"logs": [], "status": "running"|"complete"|"error", "result_path": str|None}


def _get_batch_job(job_id: str) -> dict:
    """Get batch conversion job data."""
    return _batch_convert_jobs.get(job_id, {"logs": [], "status": "unknown"})


def _update_batch_job(job_id: str, **kwargs):
    """Update batch conversion job data."""
    if job_id not in _batch_convert_jobs:
        _batch_convert_jobs[job_id] = {"logs": [], "status": "pending", "result_path": None}
    _batch_convert_jobs[job_id].update(kwargs)


def _add_batch_log(job_id: str, message: str, level: str = "info"):
    """Add a log message to a batch conversion job."""
    if job_id not in _batch_convert_jobs:
        _batch_convert_jobs[job_id] = {"logs": [], "status": "running", "result_path": None}
    _batch_convert_jobs[job_id]["logs"].append({"message": message, "level": level})


@app.route("/api/batch-convert", methods=["POST"])
def api_batch_convert():
    """Batch convert physio/eyetracking files from a flat folder structure.
    
    Expects files uploaded with naming pattern: sub-XXX_ses-YYY_task-ZZZ.<ext>
    Supported extensions: .raw, .vpd (physio), .edf (eyetracking)
    
    Returns a JSON with logs and download URL, or ZIP file directly based on 'format' param.
    """
    if not batch_convert_folder:
        return jsonify({"error": "Batch conversion not available"}), 500

    # Generate job ID
    import uuid
    job_id = str(uuid.uuid4())[:8]
    logs = []
    
    def log_callback(message: str, level: str = "info"):
        logs.append({"message": message, "level": level})

    # Get form parameters
    dataset_name = (request.form.get("dataset_name") or "Converted Dataset").strip()
    modality_filter = request.form.get("modality", "all")
    sampling_rate_str = request.form.get("sampling_rate", "").strip()
    return_format = request.form.get("format", "zip")  # "zip" or "json"
    
    try:
        sampling_rate = float(sampling_rate_str) if sampling_rate_str else None
    except ValueError:
        return jsonify({"error": "sampling_rate must be a number", "logs": logs}), 400
    
    if modality_filter not in ("all", "physio", "eyetracking"):
        modality_filter = "all"
    
    log_callback(f"🚀 Starting batch conversion job {job_id}", "info")
    log_callback(f"   Dataset name: {dataset_name}", "info")
    log_callback(f"   Modality filter: {modality_filter}", "info")
    if sampling_rate:
        log_callback(f"   Physio sampling rate: {sampling_rate} Hz", "info")
    
    # Get uploaded files
    files = request.files.getlist("files[]")
    if not files:
        files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded", "logs": logs}), 400
    
    log_callback(f"📦 Received {len(files)} files", "info")
    
    # Validate file names before processing
    valid_extensions = {".raw", ".vpd", ".edf"}
    validated_files = []
    validation_errors = []
    
    for f in files:
        if not f or not f.filename:
            continue
        filename = secure_filename(f.filename)
        ext = Path(filename).suffix.lower()
        
        if ext not in valid_extensions:
            msg = f"{f.filename}: unsupported extension (use .raw, .vpd, or .edf)"
            validation_errors.append(msg)
            log_callback(f"⚠️  {msg}", "warning")
            continue
        
        # Check naming pattern
        parsed = parse_bids_filename(filename)
        if not parsed:
            msg = f"{f.filename}: invalid naming pattern (expected sub-XXX_ses-YYY_task-ZZZ.ext)"
            validation_errors.append(msg)
            log_callback(f"⚠️  {msg}", "warning")
            continue
        
        validated_files.append((f, filename, parsed))
        log_callback(f"✓ Validated: {filename}", "info")
    
    if not validated_files:
        error_msg = "No valid files to convert."
        if validation_errors:
            error_msg += f" {len(validation_errors)} files had issues."
        log_callback(f"❌ {error_msg}", "error")
        return jsonify({"error": error_msg, "logs": logs}), 400
    
    log_callback(f"", "info")
    log_callback(f"📋 {len(validated_files)} files ready for conversion", "info")
    
    # Create temp directories
    tmp_dir = tempfile.mkdtemp(prefix="prism_batch_convert_")
    try:
        tmp_path = Path(tmp_dir)
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        
        # Save uploaded files to input directory
        log_callback(f"💾 Saving files to temporary directory...", "info")
        for f, filename, _ in validated_files:
            input_path = input_dir / filename
            f.save(str(input_path))
        
        log_callback(f"", "info")
        
        # Run batch conversion with logging
        result = batch_convert_folder(
            input_dir,
            output_dir,
            physio_sampling_rate=sampling_rate,
            modality_filter=modality_filter,
            log_callback=log_callback,
        )
        
        # Create dataset_description.json
        create_dataset_description(output_dir, name=dataset_name)
        log_callback(f"📄 Created dataset_description.json", "info")
        
        # Build response info
        response_info = {
            "job_id": job_id,
            "success_count": result.success_count,
            "error_count": result.error_count,
            "skipped_count": len(result.skipped),
            "logs": logs,
            "converted": [],
        }
        
        for conv in result.converted:
            conv_info = {
                "source": conv.source_path.name,
                "modality": conv.modality,
                "subject": conv.subject,
                "session": conv.session,
                "task": conv.task,
                "success": conv.success,
            }
            if conv.error:
                conv_info["error"] = conv.error
            response_info["converted"].append(conv_info)
        
        # Create ZIP of output
        log_callback(f"📦 Creating ZIP archive...", "info")
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(output_dir)
                    zf.write(file_path, arcname)
        mem.seek(0)
        
        log_callback(f"✅ Conversion complete!", "success")
        
        # Return based on format
        if return_format == "json":
            # Return JSON with logs (for polling/preview mode)
            response_info["status"] = "complete"
            return jsonify(response_info)
        
        # Default: Return ZIP file directly with logs in headers
        # (Client can display these before download completes)
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", dataset_name)[:50]
        response = send_file(
            mem,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{safe_name}_prism.zip",
        )
        # Add summary info as custom headers (limited, but useful)
        response.headers['X-Prism-Success-Count'] = str(result.success_count)
        response.headers['X-Prism-Error-Count'] = str(result.error_count)
        response.headers['X-Prism-Skipped-Count'] = str(len(result.skipped))
        return response
        
    except Exception as e:
        log_callback(f"❌ Error: {str(e)}", "error")
        return jsonify({"error": str(e), "logs": logs}), 500
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


def find_dataset_root(extract_dir):
    """Find the actual dataset root directory after extraction"""
    # Look for dataset_description.json or typical BIDS structure
    for root, dirs, files in os.walk(extract_dir):
        if "dataset_description.json" in files:
            return root
        # Look for subject directories
        if any(d.startswith("sub-") for d in dirs):
            return root

    # If no clear dataset structure, return the extraction directory
    return extract_dir


def find_free_port(start_port):
    """Find a free port starting from start_port"""
    import socket
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
            port += 1
    return start_port

def main():
    """Run the web application"""
    import argparse

    parser = argparse.ArgumentParser(description="PRISM Studio")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5001,
        help="Port to bind to (default: 5001, avoiding macOS Control Center on port 5000)",
    )
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    parser.add_argument(
        "--public",
        action="store_true",
        help="Allow external connections (sets host to 0.0.0.0)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open browser",
    )

    args = parser.parse_args()

    host = "0.0.0.0" if args.public else args.host
    
    # Find a free port if the default one is taken
    port = args.port
    if not args.public: # Only auto-find port for local binding
        port = find_free_port(args.port)
        if port != args.port:
            print(f"ℹ️  Port {args.port} is in use, using {port} instead")

    display_host = "localhost" if host == "127.0.0.1" else host
    url = f"http://{display_host}:{port}"

    print("🌐 Starting PRISM Studio")
    print(f"🔗 URL: {url}")
    if args.public:
        print("⚠️  Warning: Running in public mode - accessible from other computers")
    print("💡 Press Ctrl+C to stop the server")
    print()

    # Open browser in a separate thread to avoid blocking the Flask server
    if not args.no_browser:

        def open_browser():
            import time

            time.sleep(1)  # Wait for server to start
            try:
                webbrowser.open(url)
                print("✅ Browser opened automatically")
            except Exception as e:
                print(f"ℹ️  Could not open browser automatically: {e}")
                print(f"   Please visit {url} manually")

        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

    if args.debug:
        app.run(host=host, port=port, debug=True)
    else:
        try:
            from waitress import serve
            print(f"🚀 Running with Waitress server on {host}:{port}")
            serve(app, host=host, port=port)
        except ImportError:
            print("⚠️  Waitress not installed, falling back to Flask development server")
            app.run(host=host, port=port, debug=False)


@app.route("/survey-generator")
def survey_generator():
    """Survey generator page"""
    preferred = (BASE_DIR / "library" / "survey_i18n").resolve()
    default_library_path = preferred
    if not (preferred.exists() and any(preferred.glob("survey-*.json"))):
        default_library_path = (BASE_DIR / "survey_library").resolve()
    return render_template(
        "survey_generator.html",
        default_survey_library_path=str(default_library_path),
    )


@app.route("/derivatives")
def derivatives():
    return render_template("derivatives.html")


@app.route("/api/derivatives-surveys", methods=["POST"])
def api_derivatives_surveys():
    """Run survey-derivatives generation inside an existing PRISM dataset."""

    if not compute_survey_derivatives:
        return jsonify({"error": "Derivatives module not available"}), 500

    data = request.get_json(silent=True) or {}
    dataset_path = (data.get("dataset_path") or "").strip()
    modality = (data.get("modality") or "survey").strip().lower() or "survey"
    out_format = (data.get("format") or "csv").strip().lower() or "csv"
    survey_filter = (data.get("survey") or "").strip() or None

    if not dataset_path:
        return jsonify({"error": "Missing dataset_path"}), 400
    if not os.path.exists(dataset_path) or not os.path.isdir(dataset_path):
        return jsonify({"error": f"Dataset path is not a directory: {dataset_path}"}), 400

    # Validate that the dataset is PRISM-valid before writing derivatives.
    issues, _stats = run_validation(dataset_path, verbose=False, schema_version=None, run_bids=False)
    error_issues = [i for i in (issues or []) if (len(i) >= 1 and str(i[0]).upper() == "ERROR")]
    if error_issues:
        # Keep message compact but actionable.
        first = error_issues[0][1] if len(error_issues[0]) > 1 else "Dataset has validation errors"
        return jsonify({
            "error": f"Dataset is not PRISM-valid (errors: {len(error_issues)}). First error: {first}",
        }), 400

    try:
        result = compute_survey_derivatives(
            prism_root=dataset_path,
            repo_root=BASE_DIR,
            survey=survey_filter,
            out_format=out_format,
            modality=modality,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    msg = f"✅ Survey derivatives complete: wrote {result.written_files} file(s)"
    if result.flat_out_path:
        msg = f"✅ Survey derivatives complete: wrote {result.flat_out_path}"
    return jsonify(
        {
            "ok": True,
            "message": msg,
            "written_files": result.written_files,
            "processed_files": result.processed_files,
            "out_format": result.out_format,
            "out_root": str(result.out_root),
            "flat_out_path": str(result.flat_out_path) if result.flat_out_path else None,
        }
    )


# ==========================================
# Survey Library Management Routes
# ==========================================


@app.route("/library")
def library_view():
    """View the survey library management page"""
    if not survey_manager:
        return "Survey Manager not initialized", 500
    
    surveys = survey_manager.list_surveys()
    return render_template("library.html", surveys=surveys)


@app.route("/library/edit/<filename>")
def edit_survey(filename):
    """Edit a survey draft"""
    if not survey_manager:
        return "Survey Manager not initialized", 500
    
    try:
        content = survey_manager.get_draft_content(filename)
        return render_template("library_editor.html", filename=filename, content=content)
    except FileNotFoundError:
        return "Draft not found", 404
    except Exception as e:
        return str(e), 500


@app.route("/library/api/draft/<filename>", methods=["POST"])
def create_draft(filename):
    """Create a new draft from master"""
    if not survey_manager:
        return jsonify({"error": "Survey Manager not initialized"}), 500
    
    try:
        survey_manager.create_draft(filename)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/library/api/draft/<filename>", methods=["DELETE"])
def discard_draft(filename):
    """Discard a draft"""
    if not survey_manager:
        return jsonify({"error": "Survey Manager not initialized"}), 500
    
    try:
        survey_manager.discard_draft(filename)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/library/api/save/<filename>", methods=["POST"])
def save_draft(filename):
    """Save content to draft"""
    if not survey_manager:
        return jsonify({"error": "Survey Manager not initialized"}), 500
    
    try:
        content = request.json
        survey_manager.save_draft(filename, content)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/library/api/publish/<filename>", methods=["POST"])
def publish_draft(filename):
    """Submit draft as merge request"""
    if not survey_manager:
        return jsonify({"error": "Survey Manager not initialized"}), 500
    
    try:
        survey_manager.publish_draft(filename)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/browse-folder")
def browse_folder():
    """Open a system dialog to select a folder"""
    folder_path = ""
    try:
        if sys.platform == "darwin":
            # Use AppleScript on macOS to avoid Tkinter threading issues
            import subprocess

            try:
                script = "POSIX path of (choose folder)"
                # Run osascript
                result = subprocess.check_output(
                    ["osascript", "-e", script], stderr=subprocess.STDOUT
                )
                folder_path = result.decode("utf-8").strip()
            except subprocess.CalledProcessError:
                # User cancelled
                folder_path = ""
        else:
            # Fallback to Tkinter for Windows/Linux
            # Note: This might still have threading issues on some systems
            import tkinter as tk
            from tkinter import filedialog

            # Create a root window and hide it
            root = tk.Tk()
            root.withdraw()

            # Make it appear on top
            root.attributes("-topmost", True)

            folder_path = filedialog.askdirectory()

            root.destroy()

        if folder_path:
            return jsonify({"path": folder_path})
        else:
            return jsonify({"path": ""})  # User cancelled

    except Exception as e:
        print(f"Error opening file dialog: {e}")
        return (
            jsonify(
                {"error": "Could not open file dialog. Please enter path manually."}
            ),
            500,
        )


@app.route("/api/list-library-files")
def list_library_files():
    """List JSON files in a user-specified library path"""
    library_path = request.args.get("path")
    if not library_path:
        return jsonify({"error": "Path parameter is required"}), 400

    if not os.path.exists(library_path):
        return jsonify({"error": "Path does not exist"}), 404

    if not os.path.isdir(library_path):
        return jsonify({"error": "Path is not a directory"}), 400

    try:
        files = []
        for f in os.listdir(library_path):
            if f.endswith(".json") and not f.startswith("."):
                full_path = os.path.join(library_path, f)
                # Try to read description and metadata
                desc = ""
                original_name = ""
                questions = []
                try:
                    with open(full_path, "r") as jf:
                        data = json.load(jf)
                        study = data.get("Study", {})
                        desc = study.get("Description", "")
                        original_name = study.get("OriginalName", "")
                        if not desc:
                            desc = data.get("TaskName", "")

                        # Extract questions
                        questions = []
                        
                        # Check for "Questions" key (New Format)
                        if "Questions" in data and isinstance(data["Questions"], dict):
                            for k, v in data["Questions"].items():
                                q_desc = ""
                                q_levels = None
                                q_units = None
                                q_min = None
                                q_max = None
                                q_warn_min = None
                                q_warn_max = None
                                q_type = None
                                
                                if isinstance(v, dict):
                                    q_desc = v.get("Description", "")
                                    q_levels = v.get("Levels")
                                    q_units = v.get("Units")
                                    q_min = v.get("MinValue")
                                    q_max = v.get("MaxValue")
                                    q_warn_min = v.get("WarnMinValue")
                                    q_warn_max = v.get("WarnMaxValue")
                                    q_type = v.get("DataType")
                                    
                                questions.append(
                                    {
                                        "id": k, 
                                        "description": q_desc, 
                                        "levels": q_levels,
                                        "units": q_units,
                                        "min": q_min,
                                        "max": q_max,
                                        "warn_min": q_warn_min,
                                        "warn_max": q_warn_max,
                                        "type": q_type
                                    }
                                )
                        else:
                            # Fallback for Old Format (Flat structure)
                            reserved = [
                                "Technical",
                                "Study",
                                "Metadata",
                                "Categories",
                                "TaskName",
                                "Name",
                                "BIDSVersion",
                                "Description",
                                "URL",
                                "License",
                                "Authors",
                                "Acknowledgements",
                                "References",
                                "Funding"
                            ]
                            for k, v in data.items():
                                if k not in reserved:
                                    q_desc = ""
                                    q_levels = None
                                    q_units = None
                                    q_min = None
                                    q_max = None
                                    q_warn_min = None
                                    q_warn_max = None
                                    q_type = None
                                    
                                    if isinstance(v, dict):
                                        q_desc = v.get("Description", "")
                                        q_levels = v.get("Levels")
                                        q_units = v.get("Units")
                                        q_min = v.get("MinValue")
                                        q_max = v.get("MaxValue")
                                        q_warn_min = v.get("WarnMinValue")
                                        q_warn_max = v.get("WarnMaxValue")
                                        q_type = v.get("DataType")
                                        
                                    questions.append(
                                        {
                                            "id": k, 
                                            "description": q_desc, 
                                            "levels": q_levels,
                                            "units": q_units,
                                            "min": q_min,
                                            "max": q_max,
                                            "warn_min": q_warn_min,
                                            "warn_max": q_warn_max,
                                            "type": q_type
                                        }
                                    )
                except:
                    pass

                files.append(
                    {
                        "filename": f,
                        "path": full_path,
                        "description": desc,
                        "original_name": original_name,
                        "questions": questions,
                        "question_count": len(questions),
                    }
                )

        return jsonify({"files": sorted(files, key=lambda x: x["filename"])})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/generate-lss", methods=["POST"])
def generate_lss_endpoint():
    """Generate LSS from selected JSON files"""
    if not generate_lss:
        return jsonify({"error": "LSS exporter not available"}), 500

    try:
        data = request.get_json()
        if not data or "files" not in data:
            return jsonify({"error": "No files selected"}), 400

        files = data["files"]
        if not files:
            return jsonify({"error": "File list is empty"}), 400

        # Verify files exist
        valid_files = []
        for item in files:
            f_path = item
            if isinstance(item, dict):
                f_path = item.get("path")

            if f_path and os.path.exists(f_path):
                valid_files.append(item)
            else:
                print(f"Warning: File not found: {f_path}")

        if not valid_files:
            return jsonify({"error": "No valid files found"}), 404

        # Generate LSS content
        # We return it as a downloadable file

        # Create a temporary file
        fd, temp_path = tempfile.mkstemp(suffix=".lss")
        os.close(fd)

        generate_lss(valid_files, temp_path)

        return send_file(
            temp_path,
            as_attachment=True,
            download_name="survey_export.lss",
            mimetype="application/xml",
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    main()
