"""
Conversion Blueprint for PRISM.
Handles survey, biometrics, and physio conversion routes.
"""

import io
import json
import re
import shutil
import tempfile
import zipfile
import base64
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file, current_app, session
from werkzeug.utils import secure_filename
from src.web.utils import list_survey_template_languages, sanitize_jsonable
from src.web import run_validation

# Import shared utilities
from .conversion_utils import (
    participant_json_candidates,
    log_file_head,
    resolve_effective_library_path,
)

# Import conversion logic
try:
    from src.converters.survey import (
        convert_survey_xlsx_to_prism_dataset,
        convert_survey_lsa_to_prism_dataset,
        infer_lsa_metadata,
        MissingIdMappingError,
        UnmatchedGroupsError,
        _NON_ITEM_TOPLEVEL_KEYS,
    )
except ImportError:
    convert_survey_xlsx_to_prism_dataset = None
    convert_survey_lsa_to_prism_dataset = None
    infer_lsa_metadata = None
    MissingIdMappingError = None
    UnmatchedGroupsError = None
    _NON_ITEM_TOPLEVEL_KEYS = set()

try:
    from src.converters.id_detection import IdColumnNotDetectedError
except ImportError:
    IdColumnNotDetectedError = None

try:
    from src.converters.biometrics import convert_biometrics_table_to_prism_dataset
except ImportError:
    convert_biometrics_table_to_prism_dataset = None

try:
    from helpers.physio.convert_varioport import convert_varioport
except ImportError:
    convert_varioport = None

try:
    from src.batch_convert import (
        batch_convert_folder,
        create_dataset_description,
        parse_bids_filename,
    )
except ImportError:
    batch_convert_folder = None
    create_dataset_description = None
    parse_bids_filename = None

conversion_bp = Blueprint("conversion", __name__)

# Batch conversion job tracking
_batch_convert_jobs = {}

# Keep backward-compatible wrappers for any internal calls
_participant_json_candidates = participant_json_candidates
_log_file_head = log_file_head
_resolve_effective_library_path = resolve_effective_library_path


def _extract_tasks_from_output(output_root: Path) -> list:
    """Extract unique task names from BIDS-style filenames in output directory."""
    tasks = set()
    for f in output_root.rglob("*"):
        if f.is_file() and "_task-" in f.name:
            m = re.search(r"_task-([a-zA-Z0-9]+)", f.name)
            if m:
                tasks.add(m.group(1))
    return sorted(tasks)


def _register_session_in_project(
    project_path: Path,
    session_id: str,
    tasks: list,
    modality: str,
    source_file: str,
    converter: str,
):
    """Register conversion output in project.json Sessions/TaskDefinitions.

    This is a backend-side helper called after save-to-project file copy.
    It mirrors the logic in the /api/projects/sessions/register endpoint
    so that registrations happen even when the client-side JS call doesn't fire.
    """
    if not session_id or not tasks:
        return

    pj_path = project_path / "project.json"
    if not pj_path.exists():
        return

    try:
        with open(pj_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    if "Sessions" not in data:
        data["Sessions"] = []
    if "TaskDefinitions" not in data:
        data["TaskDefinitions"] = {}

    # Normalize session_id with zero-padding for numeric values
    if not session_id.startswith("ses-"):
        session_id = f"ses-{session_id}"
    # Ensure zero-padding for numeric session IDs
    num_part = session_id[4:]  # Strip "ses-" prefix
    try:
        n = int(num_part)
        session_id = f"ses-{n:02d}"
    except ValueError:
        pass  # Non-numeric labels pass through as-is

    # Find or create session
    target = None
    for s in data["Sessions"]:
        if s.get("id") == session_id:
            target = s
            break
    if target is None:
        target = {"id": session_id, "label": session_id, "tasks": []}
        data["Sessions"].append(target)
    if "tasks" not in target:
        target["tasks"] = []

    from datetime import date

    today = date.today().isoformat()
    source_obj = {
        "file": source_file,
        "converter": converter,
        "convertedAt": today,
    }

    for task_name in tasks:
        existing = next(
            (t for t in target["tasks"] if t.get("task") == task_name), None
        )
        if existing:
            existing["source"] = source_obj
        else:
            target["tasks"].append({"task": task_name, "source": source_obj})

        if task_name not in data["TaskDefinitions"]:
            data["TaskDefinitions"][task_name] = {"modality": modality}

    try:
        from src.cross_platform import CrossPlatformFile

        CrossPlatformFile.write_text(
            str(pj_path), json.dumps(data, indent=2, ensure_ascii=False)
        )
    except Exception:
        pass  # Don't fail conversion if registration fails


def _format_unmatched_groups_response(uge, log_messages=None):
    """Build the JSON response dict for an UnmatchedGroupsError."""
    payload = {
        "error": "unmatched_groups",
        "message": str(uge),
        "unmatched": [
            {
                "group_name": g["group_name"],
                "task_key": g["task_key"],
                "item_count": len(
                    [
                        k
                        for k in g["prism_json"]
                        if k not in _NON_ITEM_TOPLEVEL_KEYS
                        and isinstance(g["prism_json"].get(k), dict)
                    ]
                ),
                "item_codes": g["item_codes"][:10],
                "prism_json": g["prism_json"],
            }
            for g in uge.unmatched
        ],
    }
    if log_messages is not None:
        payload["log"] = log_messages
    return payload


def _generate_neurobagel_schema(df, id_column):
    """
    Generate NeuroBagel-compliant participants.json schema from DataFrame.
    Auto-detects data types, standard variables, and suggests annotations.

    Returns dict with column definitions including NeuroBagel annotations.
    """
    import pandas as pd

    # NeuroBagel standard variable mappings with level URIs
    NEUROBAGEL_VOCAB = {
        # Core demographics
        "age": {
            "term": "nb:Age",
            "label": "Age",
            "type": "continuous",
            "unit": "years",
        },
        "sex": {
            "term": "nb:Sex",
            "label": "Sex",
            "type": "categorical",
            "levels": {
                "M": {"label": "Male", "uri": "nb:BiologicalSex/Male"},
                "F": {"label": "Female", "uri": "nb:BiologicalSex/Female"},
                "O": {"label": "Other", "uri": "nb:BiologicalSex/Other"},
                "1": {"label": "Male", "uri": "nb:BiologicalSex/Male"},
                "2": {"label": "Female", "uri": "nb:BiologicalSex/Female"},
            },
        },
        "gender": {
            "term": "nb:Gender",
            "label": "Gender",
            "type": "categorical",
            "levels": {
                "M": {"label": "Male", "uri": "nb:Gender/Male"},
                "F": {"label": "Female", "uri": "nb:Gender/Female"},
                "NB": {"label": "Non-binary", "uri": "nb:Gender/NonBinary"},
            },
        },
        "handedness": {
            "term": "nb:Handedness",
            "label": "Handedness",
            "type": "categorical",
            "levels": {
                "R": {"label": "Right", "uri": "nb:Handedness/Right"},
                "L": {"label": "Left", "uri": "nb:Handedness/Left"},
                "A": {"label": "Ambidextrous", "uri": "nb:Handedness/Ambidextrous"},
                "1": {"label": "Right", "uri": "nb:Handedness/Right"},
                "2": {"label": "Left", "uri": "nb:Handedness/Left"},
                "3": {"label": "Ambidextrous", "uri": "nb:Handedness/Ambidextrous"},
            },
        },
        # Clinical/study info
        "group": {"term": "nb:Group", "label": "Group", "type": "categorical"},
        "diagnosis": {
            "term": "nb:Diagnosis",
            "label": "Diagnosis",
            "type": "categorical",
        },
        "education": {
            "term": "nb:EducationLevel",
            "label": "Education Level",
            "type": "continuous",
            "unit": "years",
        },
        "ethnicity": {
            "term": "nb:Ethnicity",
            "label": "Ethnicity",
            "type": "categorical",
        },
        # IDs
        "participant_id": {
            "term": "nb:ParticipantID",
            "label": "Participant ID",
            "type": "string",
        },
        "subject": {
            "term": "nb:ParticipantID",
            "label": "Subject ID",
            "type": "string",
        },
        "sub": {"term": "nb:ParticipantID", "label": "Subject ID", "type": "string"},
    }

    schema = {}

    for col in df.columns:
        col_lower = str(col).lower().strip()
        col_data = df[col].dropna()

        # Start with basic structure
        field = {"Description": "", "Annotations": {}}

        # Check if column matches NeuroBagel vocabulary
        neurobagel_match = None
        for key, vocab in NEUROBAGEL_VOCAB.items():
            if key in col_lower or col_lower in key:
                neurobagel_match = vocab
                break

        # Infer data type
        if col == id_column:
            data_type = "string"
            is_categorical = False
        else:
            # Try to detect if numeric
            try:
                pd.to_numeric(col_data, errors="raise")
                unique_count = col_data.nunique()
                # If less than 10 unique values, likely categorical
                is_categorical = unique_count < 10
                data_type = "categorical" if is_categorical else "continuous"
            except (ValueError, TypeError):
                # String data - check uniqueness
                unique_count = col_data.nunique()
                is_categorical = unique_count < 20
                data_type = "categorical" if is_categorical else "string"

        # Build description
        if neurobagel_match:
            field["Description"] = neurobagel_match.get("label", col)
            field["Annotations"]["IsAbout"] = {
                "TermURL": neurobagel_match["term"],
                "Label": neurobagel_match["label"],
            }
            field["Annotations"]["VariableType"] = neurobagel_match["type"].capitalize()

            # Add unit if specified
            if "unit" in neurobagel_match:
                field["Unit"] = neurobagel_match["unit"]
                if data_type == "continuous":
                    field["Annotations"]["Format"] = {
                        "TermURL": "nb:FromFloat",
                        "Label": "Float",
                    }
        else:
            # No NeuroBagel match - use generic description
            field["Description"] = f"{col} (auto-detected)"
            field["Annotations"]["VariableType"] = data_type.capitalize()

        # Extract levels for categorical variables with NeuroBagel annotations
        if is_categorical and len(col_data) > 0:
            levels = {}
            level_annotations = {}
            unique_vals = col_data.unique()[:50]  # Limit to 50 levels

            # Use NeuroBagel levels if available
            if neurobagel_match and "levels" in neurobagel_match:
                nb_levels = neurobagel_match["levels"]
                for val in unique_vals:
                    val_str = str(val)
                    if val_str in nb_levels:
                        # Has NeuroBagel mapping
                        nb_info = nb_levels[val_str]
                        if isinstance(nb_info, dict):
                            levels[val_str] = nb_info.get("label", val_str)
                            level_annotations[val_str] = {
                                "TermURL": nb_info.get("uri"),
                                "Label": nb_info.get("label", val_str),
                            }
                        else:
                            # String value (old format)
                            levels[val_str] = nb_info
                    else:
                        # No mapping - use raw value
                        levels[val_str] = val_str
            else:
                for val in unique_vals:
                    levels[str(val)] = str(val)

            field["Levels"] = levels

            # Add level annotations if available
            if level_annotations:
                if "Annotations" not in field:
                    field["Annotations"] = {}
                field["Annotations"]["Levels"] = level_annotations

        schema[col] = field

    return schema


@conversion_bp.route("/api/survey-languages", methods=["GET"])
def api_survey_languages():
    """List available languages for the selected survey template library folder."""
    library_path = (request.args.get("library_path") or "").strip()
    base_dir = Path(current_app.root_path)
    if not library_path:
        project_path = (session.get("current_project_path") or "").strip()
        if project_path:
            # Check for standard PRISM library location (code/library)
            candidate = (Path(project_path) / "code" / "library").expanduser()
            if candidate.exists() and candidate.is_dir():
                library_path = str(candidate)
            else:
                # Check legacy location
                candidate = (Path(project_path) / "library").expanduser()
                if candidate.exists() and candidate.is_dir():
                    library_path = str(candidate)

    if not library_path:
        preferred = (base_dir / "library" / "survey_i18n").resolve()
        fallback = (base_dir / "survey_library").resolve()
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
        "missing_items": [],
    }

    # Check for expected items - handle official/library/survey structure
    if (library_root / "library" / "survey").is_dir():
        survey_dir = library_root / "library" / "survey"
    else:
        survey_dir = library_root / "survey"

    if (library_root / "library" / "biometrics").is_dir():
        biometrics_dir = library_root / "library" / "biometrics"
    else:
        biometrics_dir = library_root / "biometrics"

    participant_candidates = _participant_json_candidates(library_root)

    structure_info["has_survey_folder"] = survey_dir.is_dir()
    structure_info["has_biometrics_folder"] = biometrics_dir.is_dir()
    # Accept participants.json from library folder or any reasonable ancestor (project root, code/)
    structure_info["has_participants_json"] = any(
        p.is_file() for p in participant_candidates
    )

    # Build missing items list for survey conversion
    if not structure_info["has_survey_folder"]:
        structure_info["missing_items"].append("survey/")
    if not structure_info["has_participants_json"]:
        structure_info["missing_items"].append(
            "participants.json (or ../participants.json)"
        )

    # Determine effective survey directory
    if survey_dir.is_dir():
        effective_survey_dir = str(survey_dir)
    else:
        effective_survey_dir = library_path

    langs, default, template_count, i18n_count = list_survey_template_languages(
        effective_survey_dir
    )
    return jsonify(
        {
            "languages": langs,
            "default": default,
            "library_path": effective_survey_dir,
            "template_count": template_count,
            "i18n_count": i18n_count,
            "structure": structure_info,
        }
    )


@conversion_bp.route("/api/survey-convert-preview", methods=["POST"])
def api_survey_convert_preview():
    """Run a dry-run conversion to preview what will be created without writing files."""
    if (
        not convert_survey_xlsx_to_prism_dataset
        and not convert_survey_lsa_to_prism_dataset
    ):
        return jsonify({"error": "Survey conversion module not available"}), 500

    uploaded_file = request.files.get("excel") or request.files.get("file")
    alias_upload = request.files.get("alias") or request.files.get("alias_file")
    id_map_upload = request.files.get("id_map")
    id_map_upload = request.files.get("id_map")

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xlsx", ".lsa", ".csv", ".tsv"}:
        return jsonify({"error": "Supported formats: .xlsx, .lsa, .csv, .tsv"}), 400

    alias_filename = None
    if alias_upload and getattr(alias_upload, "filename", ""):
        alias_filename = secure_filename(alias_upload.filename)
        alias_suffix = Path(alias_filename).suffix.lower()
        if alias_suffix and alias_suffix not in {".tsv", ".txt"}:
            return (
                jsonify({"error": "Alias file must be a .tsv or .txt mapping file"}),
                400,
            )

    id_map_filename = None
    if id_map_upload and getattr(id_map_upload, "filename", ""):
        id_map_filename = secure_filename(id_map_upload.filename)
        id_map_suffix = Path(id_map_filename).suffix.lower()
        if id_map_suffix and id_map_suffix not in {".tsv", ".txt", ".csv"}:
            return (
                jsonify({"error": "ID map file must be a .tsv, .csv, or .txt file"}),
                400,
            )

    id_map_filename = None
    if id_map_upload and getattr(id_map_upload, "filename", ""):
        id_map_filename = secure_filename(id_map_upload.filename)
        id_map_suffix = Path(id_map_filename).suffix.lower()
        if id_map_suffix and id_map_suffix not in {".tsv", ".txt", ".csv"}:
            return (
                jsonify({"error": "ID map file must be a .tsv, .csv, or .txt file"}),
                400,
            )

    # Automatically resolve library path (project first, then global)
    try:
        library_path = _resolve_effective_library_path()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 400

    # Check for survey subdirectory
    if (library_path / "survey").is_dir():
        survey_dir = library_path / "survey"
    else:
        survey_dir = library_path

    effective_survey_dir = survey_dir

    # DEBUG: Log which library is being used
    print(f"[PRISM DEBUG] DRY-RUN Preview using library: {effective_survey_dir}")
    print(f"[PRISM DEBUG] Session project path: {session.get('current_project_path')}")
    print(
        f"[PRISM DEBUG] Available templates: {list(effective_survey_dir.glob('survey-*.json'))}"
    )

    survey_templates = list(effective_survey_dir.glob("survey-*.json"))
    if not survey_templates:
        return (
            jsonify({"error": f"No survey templates found in: {effective_survey_dir}"}),
            400,
        )

    survey_filter = (request.form.get("survey") or "").strip() or None
    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    session_override = (request.form.get("session") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    language = (request.form.get("language") or "").strip() or None
    strict_levels_raw = (request.form.get("strict_levels") or "").strip().lower()
    strict_levels = strict_levels_raw in {"1", "true", "yes", "on"}
    validate_raw = (request.form.get("validate") or "").strip().lower()
    # Default: run validation in preview unless explicitly disabled
    validate_preview = (
        True if validate_raw == "" else validate_raw in {"1", "true", "yes", "on"}
    )
    duplicate_handling = (request.form.get("duplicate_handling") or "error").strip()
    if duplicate_handling not in {"error", "keep_first", "keep_last", "sessions"}:
        duplicate_handling = "error"

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_preview_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        alias_path = None
        if alias_filename:
            alias_path = tmp_dir_path / alias_filename
            alias_upload.save(str(alias_path))

        id_map_path = None
        if id_map_filename:
            id_map_path = tmp_dir_path / id_map_filename
            # DEBUG: Check file object before saving
            print(
                f"[PRISM DEBUG] ID map upload object: filename={id_map_upload.filename}"
            )
            print(
                f"[PRISM DEBUG] ID map upload stream size: {id_map_upload.stream.seek(0, 2)} bytes (seek to end)"
            )
            id_map_upload.stream.seek(0)  # Reset to beginning
            id_map_upload.save(str(id_map_path))
            # Check what was actually saved
            saved_size = id_map_path.stat().st_size if id_map_path.exists() else 0
            print(
                f"[PRISM DEBUG] ID map saved to: {id_map_path} (size: {saved_size} bytes)"
            )

        # Copy participants_mapping.json from project to temp directory if it exists
        project_path = session.get("current_project_path")
        if project_path:
            project_path = Path(project_path)
            if project_path.is_file():
                project_path = project_path.parent

            mapping_candidates = [
                project_path / "participants_mapping.json",
                project_path / "code" / "participants_mapping.json",
                project_path / "code" / "library" / "participants_mapping.json",
                project_path
                / "code"
                / "library"
                / "survey"
                / "participants_mapping.json",
            ]

            for mapping_file in mapping_candidates:
                if mapping_file.exists():
                    dest_mapping = tmp_dir_path / "code" / "participants_mapping.json"
                    dest_mapping.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(mapping_file, dest_mapping)
                    print(
                        f"[PRISM DEBUG] Using participants mapping from: {mapping_file}"
                    )
                    break

        output_root = tmp_dir_path / "rawdata"

        # DEBUG: log the resolved parameters for dry-run
        print("[PRISM DEBUG] Dry-run request:")
        print(f"  file: {input_path}")
        print(f"  id_column: {id_column}")
        print(f"  session_column: {session_column}")
        print(f"  session_override: {session_override}")
        print(f"  sheet: {sheet}")
        print(f"  unknown: {unknown}")
        print(f"  strict_levels: {strict_levels}")
        print(f"  duplicate_handling: {duplicate_handling}")
        if alias_path:
            print(f"  alias_file: {alias_path}")
        if "id_map_path" in locals() and id_map_path:
            print(f"  id_map_file: {id_map_path}")
        print(f"  library_dir: {effective_survey_dir}")

        # Run dry-run conversion
        if suffix in {".xlsx", ".csv", ".tsv"}:
            result = convert_survey_xlsx_to_prism_dataset(
                input_path=input_path,
                library_dir=str(effective_survey_dir),
                output_root=output_root,
                survey=survey_filter,
                id_column=id_column,
                session_column=session_column,
                session=session_override,
                sheet=sheet,
                unknown=unknown,
                dry_run=True,  # DRY RUN MODE
                force=True,
                name="preview",
                authors=["prism-studio"],
                language=language,
                alias_file=alias_path,
                id_map_file=id_map_path,
                duplicate_handling=duplicate_handling,
            )
        elif suffix == ".lsa":
            result = convert_survey_lsa_to_prism_dataset(
                input_path=input_path,
                library_dir=str(effective_survey_dir),
                output_root=output_root,
                survey=survey_filter,
                id_column=id_column,
                session_column=session_column,
                session=session_override,
                unknown=unknown,
                dry_run=True,  # DRY RUN MODE
                force=True,
                name="preview",
                authors=["prism-studio"],
                language=language,
                alias_file=alias_path,
                id_map_file=id_map_path,
                strict_levels=True if strict_levels else None,
                duplicate_handling=duplicate_handling,
                project_path=session.get("current_project_path"),
            )
        else:
            return jsonify({"error": "Unsupported file format"}), 400

        # Optionally run full validation in preview (writes to temp, then cleans up)
        validation_result = None
        if validate_preview:
            try:
                validate_root = tmp_dir_path / "rawdata_validate"
                validate_root.mkdir(parents=True, exist_ok=True)

                if suffix in {".xlsx", ".csv", ".tsv"}:
                    convert_survey_xlsx_to_prism_dataset(
                        input_path=input_path,
                        library_dir=str(effective_survey_dir),
                        output_root=validate_root,
                        survey=survey_filter,
                        id_column=id_column,
                        session_column=session_column,
                        session=session_override,
                        sheet=sheet,
                        unknown=unknown,
                        dry_run=False,
                        force=True,
                        name="preview",
                        authors=["prism-studio"],
                        language=language,
                        alias_file=alias_path,
                        id_map_file=id_map_path,
                        duplicate_handling=duplicate_handling,
                    )
                elif suffix == ".lsa":
                    convert_survey_lsa_to_prism_dataset(
                        input_path=input_path,
                        library_dir=str(effective_survey_dir),
                        output_root=validate_root,
                        survey=survey_filter,
                        id_column=id_column,
                        session_column=session_column,
                        session=session_override,
                        unknown=unknown,
                        dry_run=False,
                        force=True,
                        name="preview",
                        authors=["prism-studio"],
                        language=language,
                        alias_file=alias_path,
                        id_map_file=id_map_path,
                        strict_levels=True if strict_levels else None,
                        duplicate_handling=duplicate_handling,
                        project_path=session.get("current_project_path"),
                    )

                v_res = run_validation(
                    str(validate_root),
                    schema_version="stable",
                    library_path=str(effective_survey_dir),
                )
                # run_validation returns (issues, stats)
                if v_res and isinstance(v_res, tuple):
                    issues, stats = v_res
                    validation_result = {
                        "errors": issues.get("errors", []),
                        "warnings": issues.get("warnings", []),
                        "summary": stats or {},
                    }
                    err_cnt = len(validation_result.get("errors", []))
                    warn_cnt = len(validation_result.get("warnings", []))
                    print(
                        f"[PRISM DEBUG] Preview validation: errors={err_cnt}, warnings={warn_cnt}"
                    )
            except Exception as ve:
                validation_result = {"error": str(ve)}

        # Return the dry-run preview as JSON
        response_data = {
            "preview": result.dry_run_preview,
            "tasks_included": result.tasks_included,
            "unknown_columns": result.unknown_columns,
            "missing_items_by_task": result.missing_items_by_task,
            "id_column": result.id_column,
            "session_column": result.session_column,
            "conversion_warnings": result.conversion_warnings,
            "task_runs": result.task_runs,
        }

        if validation_result is not None:
            response_data["validation"] = validation_result

        # Build conversion summary for the preview
        conv_summary = {}
        if result.tasks_included:
            conv_summary["tasks_included"] = result.tasks_included
        if result.task_runs:
            conv_summary["task_runs"] = result.task_runs
        if result.unknown_columns:
            conv_summary["unknown_columns"] = result.unknown_columns
        if getattr(result, "tool_columns", None):
            conv_summary["tool_columns"] = result.tool_columns
        if result.conversion_warnings:
            conv_summary["conversion_warnings"] = result.conversion_warnings

        # Include template match results in response and conversion summary.
        # For LSA files, structural matching is done during conversion (more accurate).
        # For other formats, fall back to post-hoc matching against library templates.
        if result.template_matches:
            response_data["template_matches"] = result.template_matches
            conv_summary["template_matches"] = result.template_matches
        elif result.tasks_included:
            try:
                from src.converters.template_matcher import match_against_library
                from src.converters.survey import _load_global_templates

                global_templates = _load_global_templates()
                project_path = session.get("current_project_path")
                template_matches = {}
                for task_name in result.tasks_included:
                    # Load the task's template from the survey dir
                    task_template_path = (
                        effective_survey_dir / f"survey-{task_name}.json"
                    )
                    if task_template_path.exists():
                        import json as _json

                        with open(task_template_path, "r", encoding="utf-8") as tf:
                            task_json = _json.load(tf)
                        match = match_against_library(
                            task_json,
                            global_templates,
                            group_name=task_name,
                            project_path=project_path,
                        )
                        template_matches[task_name] = match.to_dict() if match else None
                    else:
                        template_matches[task_name] = None
                response_data["template_matches"] = template_matches
                conv_summary["template_matches"] = template_matches
            except Exception:
                pass  # Template matching is non-critical

        if conv_summary:
            response_data["conversion_summary"] = conv_summary

        return jsonify(response_data)
    except IdColumnNotDetectedError as e:
        return (
            jsonify(
                {
                    "error": "id_column_required",
                    "message": str(e),
                    "columns": e.available_columns,
                }
            ),
            409,
        )
    except UnmatchedGroupsError as uge:
        return jsonify(_format_unmatched_groups_response(uge)), 409
    except Exception as e:
        import traceback

        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_bp.route("/api/survey-convert", methods=["POST"])
def api_survey_convert():
    """Convert an uploaded survey file (.xlsx or .lsa) to a PRISM dataset and return it as a zip."""
    if (
        not convert_survey_xlsx_to_prism_dataset
        and not convert_survey_lsa_to_prism_dataset
    ):
        return jsonify({"error": "Survey conversion module not available"}), 500

    uploaded_file = request.files.get("excel") or request.files.get("file")
    alias_upload = request.files.get("alias") or request.files.get("alias_file")
    id_map_upload = request.files.get("id_map")

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xlsx", ".lsa", ".csv", ".tsv"}:
        return jsonify({"error": "Supported formats: .xlsx, .lsa, .csv, .tsv"}), 400

    alias_filename = None
    if alias_upload and getattr(alias_upload, "filename", ""):
        alias_filename = secure_filename(alias_upload.filename)
        alias_suffix = Path(alias_filename).suffix.lower()
        if alias_suffix and alias_suffix not in {".tsv", ".txt"}:
            return (
                jsonify({"error": "Alias file must be a .tsv or .txt mapping file"}),
                400,
            )

    id_map_filename = None
    if id_map_upload and getattr(id_map_upload, "filename", ""):
        id_map_filename = secure_filename(id_map_upload.filename)
        id_map_suffix = Path(id_map_filename).suffix.lower()
        if id_map_suffix and id_map_suffix not in {".tsv", ".csv", ".txt"}:
            return (
                jsonify({"error": "ID map file must be a .tsv, .csv, or .txt file"}),
                400,
            )

    # Automatically resolve library path (project first, then global)
    try:
        library_path = _resolve_effective_library_path()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 400

    # _resolve_effective_library_path() returns the library directory itself
    # Check for survey subdirectory
    if (library_path / "survey").is_dir():
        survey_dir = library_path / "survey"
    else:
        survey_dir = library_path

    effective_survey_dir = survey_dir

    survey_templates = list(effective_survey_dir.glob("survey-*.json"))
    if not survey_templates:
        return (
            jsonify({"error": f"No survey templates found in: {effective_survey_dir}"}),
            400,
        )

    survey_filter = (request.form.get("survey") or "").strip() or None
    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    session_override = (request.form.get("session") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    dataset_name = (request.form.get("dataset_name") or "").strip() or None
    language = (request.form.get("language") or "").strip() or None
    strict_levels_raw = (request.form.get("strict_levels") or "").strip().lower()
    strict_levels = strict_levels_raw in {"1", "true", "yes", "on"}
    save_to_project = request.form.get("save_to_project") == "true"
    archive_sourcedata = request.form.get("archive_sourcedata") == "true"
    duplicate_handling = (request.form.get("duplicate_handling") or "error").strip()
    if duplicate_handling not in {"error", "keep_first", "keep_last", "sessions"}:
        duplicate_handling = "error"

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_convert_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        alias_path = None
        if alias_filename:
            alias_path = tmp_dir_path / alias_filename
            alias_upload.save(str(alias_path))

        id_map_path = None
        if id_map_filename:
            id_map_path = tmp_dir_path / id_map_filename
            id_map_upload.save(str(id_map_path))

        output_root = tmp_dir_path / "rawdata"
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

        try:
            if suffix in {".xlsx", ".csv", ".tsv"}:
                convert_survey_xlsx_to_prism_dataset(
                    input_path=input_path,
                    library_dir=str(effective_survey_dir),
                    output_root=output_root,
                    survey=survey_filter,
                    id_column=id_column,
                    session_column=session_column,
                    session=session_override,
                    sheet=sheet,
                    unknown=unknown,
                    dry_run=False,
                    force=True,
                    name=dataset_name,
                    authors=["prism-studio"],
                    language=language,
                    alias_file=alias_path,
                    id_map_file=id_map_path,
                    duplicate_handling=duplicate_handling,
                )
            elif suffix == ".lsa":
                convert_survey_lsa_to_prism_dataset(
                    input_path=input_path,
                    library_dir=str(effective_survey_dir),
                    output_root=output_root,
                    survey=survey_filter,
                    id_column=id_column,
                    session_column=session_column,
                    session=session_override,
                    unknown=unknown,
                    dry_run=False,
                    force=True,
                    name=dataset_name,
                    authors=["prism-studio"],
                    language=language,
                    alias_file=alias_path,
                    id_map_file=id_map_path,
                    strict_levels=True if strict_levels else None,
                    duplicate_handling=duplicate_handling,
                    project_path=session.get("current_project_path"),
                )
        except IdColumnNotDetectedError as e:
            return (
                jsonify(
                    {
                        "error": "id_column_required",
                        "message": str(e),
                        "columns": e.available_columns,
                    }
                ),
                409,
            )
        except MissingIdMappingError as mie:
            return (
                jsonify(
                    {
                        "error": "id_mapping_incomplete",
                        "message": str(mie),
                        "missing_ids": mie.missing_ids,
                        "suggestions": mie.suggestions,
                    }
                ),
                409,
            )
        except UnmatchedGroupsError as uge:
            return jsonify(_format_unmatched_groups_response(uge)), 409

        # Save to project if requested
        if save_to_project:
            p_path = session.get("current_project_path")
            if p_path:
                p_path = Path(p_path)
                if p_path.exists():
                    # Prefer rawdata/ (BIDS/YODA standard), create if needed
                    dest_root = p_path / "rawdata"
                    dest_root.mkdir(parents=True, exist_ok=True)

                    # Merge output_root contents into dest_root
                    for item in output_root.rglob("*"):
                        if item.is_file():
                            rel_path = item.relative_to(output_root)
                            dest = dest_root / rel_path
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, dest)

                    # Archive original file to sourcedata/ if requested
                    if archive_sourcedata:
                        sourcedata_dir = p_path / "sourcedata"
                        sourcedata_dir.mkdir(parents=True, exist_ok=True)
                        archive_dest = sourcedata_dir / filename
                        shutil.copy2(input_path, archive_dest)

                    # Register session in project.json
                    if session_override:
                        conv_type = "survey-lsa" if suffix == ".lsa" else "survey-xlsx"
                        tasks_out = _extract_tasks_from_output(output_root)
                        _register_session_in_project(
                            p_path,
                            session_override,
                            tasks_out,
                            "survey",
                            filename,
                            conv_type,
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
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_bp.route("/api/survey-convert-validate", methods=["POST"])
def api_survey_convert_validate():
    """Convert survey and run validation immediately, returning results + ZIP as base64."""
    if (
        not convert_survey_xlsx_to_prism_dataset
        and not convert_survey_lsa_to_prism_dataset
    ):
        return jsonify({"error": "Survey conversion module not available"}), 500

    log_messages = []
    conversion_warnings = []

    def add_log(message, level="info"):
        log_messages.append({"message": message, "level": level})

    uploaded_file = request.files.get("excel") or request.files.get("file")
    alias_upload = request.files.get("alias") or request.files.get("alias_file")
    id_map_upload = request.files.get("id_map")

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file", "log": log_messages}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xlsx", ".lsa", ".csv", ".tsv"}:
        return (
            jsonify(
                {
                    "error": "Supported formats: .xlsx, .lsa, .csv, .tsv",
                    "log": log_messages,
                }
            ),
            400,
        )

    # Automatically resolve library path (project first, then global)
    try:
        library_path = _resolve_effective_library_path()
    except FileNotFoundError as e:
        return jsonify({"error": str(e), "log": log_messages}), 400

    # _resolve_effective_library_path() returns the library directory itself
    # Check for survey subdirectory
    if (library_path / "survey").is_dir():
        survey_dir = library_path / "survey"
    else:
        survey_dir = library_path

    effective_survey_dir = survey_dir

    survey_templates = list(effective_survey_dir.glob("survey-*.json"))
    if not survey_templates:
        return (
            jsonify(
                {
                    "error": f"No survey templates found in: {effective_survey_dir}",
                    "log": log_messages,
                }
            ),
            400,
        )

    survey_filter = (request.form.get("survey") or "").strip() or None
    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    session_override = (request.form.get("session") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    dataset_name = (request.form.get("dataset_name") or "").strip() or None
    language = (request.form.get("language") or "").strip() or None
    strict_levels_raw = (request.form.get("strict_levels") or "").strip().lower()
    strict_levels = strict_levels_raw in {"1", "true", "yes", "on"}
    save_to_project = request.form.get("save_to_project") == "true"
    archive_sourcedata = request.form.get("archive_sourcedata") == "true"
    duplicate_handling = (request.form.get("duplicate_handling") or "error").strip()
    if duplicate_handling not in {"error", "keep_first", "keep_last", "sessions"}:
        duplicate_handling = "error"

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_convert_validate_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        alias_path = None
        if alias_upload and getattr(alias_upload, "filename", ""):
            alias_path = tmp_dir_path / secure_filename(alias_upload.filename)
            alias_upload.save(str(alias_path))

        id_map_path = None
        if id_map_upload and getattr(id_map_upload, "filename", ""):
            id_map_filename = secure_filename(id_map_upload.filename)
            id_map_path = tmp_dir_path / id_map_filename
            id_map_upload.save(str(id_map_path))
            saved_size = id_map_path.stat().st_size if id_map_path.exists() else 0
            add_log(
                f"Using ID map file: {id_map_filename} ({saved_size} bytes)", "info"
            )

        # Copy participants_mapping.json from project to temp directory if it exists
        project_path = session.get("current_project_path")
        if project_path and save_to_project:
            project_path = Path(project_path)
            if project_path.is_file():
                project_path = project_path.parent

            # Search for participants_mapping.json in project
            mapping_candidates = [
                project_path / "participants_mapping.json",
                project_path / "code" / "participants_mapping.json",
                project_path / "code" / "library" / "participants_mapping.json",
                project_path
                / "code"
                / "library"
                / "survey"
                / "participants_mapping.json",
            ]

            for mapping_file in mapping_candidates:
                if mapping_file.exists():
                    # Copy to temp directory's code/ folder where conversion will look for it
                    dest_mapping = tmp_dir_path / "code" / "participants_mapping.json"
                    dest_mapping.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(mapping_file, dest_mapping)
                    add_log(
                        f"Using participants mapping from: {mapping_file.name}", "info"
                    )
                    break

        output_root = tmp_dir_path / "rawdata"
        output_root.mkdir(parents=True, exist_ok=True)
        add_log("Starting data conversion...", "info")

        # Log the head to help debug delimiter/structure issues
        try:
            _log_file_head(input_path, suffix, add_log)
        except Exception as head_err:
            add_log(f"Header preview failed: {head_err}", "warning")

        if strict_levels:
            add_log("Strict Levels Validation: enabled", "info")

        convert_result = None
        try:
            if suffix in {".xlsx", ".csv", ".tsv"}:
                convert_result = convert_survey_xlsx_to_prism_dataset(
                    input_path=input_path,
                    library_dir=str(effective_survey_dir),
                    output_root=output_root,
                    survey=survey_filter,
                    id_column=id_column,
                    session_column=session_column,
                    session=session_override,
                    sheet=sheet,
                    unknown=unknown,
                    dry_run=False,
                    force=True,
                    name=dataset_name,
                    authors=["prism-studio"],
                    language=language,
                    alias_file=alias_path,
                    duplicate_handling=duplicate_handling,
                )
            elif suffix == ".lsa":
                add_log(f"Processing LimeSurvey archive: {filename}", "info")
                convert_result = convert_survey_lsa_to_prism_dataset(
                    input_path=input_path,
                    library_dir=str(effective_survey_dir),
                    output_root=output_root,
                    survey=survey_filter,
                    id_column=id_column,
                    session_column=session_column,
                    session=session_override,
                    unknown=unknown,
                    dry_run=False,
                    force=True,
                    name=dataset_name,
                    authors=["prism-studio"],
                    language=language,
                    alias_file=alias_path,
                    strict_levels=True if strict_levels else None,
                    duplicate_handling=duplicate_handling,
                    project_path=session.get("current_project_path"),
                )
            add_log("Conversion completed successfully", "success")
        except IdColumnNotDetectedError as e:
            add_log(f"ID column not detected: {str(e)}", "error")
            return (
                jsonify(
                    {
                        "error": "id_column_required",
                        "message": str(e),
                        "columns": e.available_columns,
                        "log": log_messages,
                    }
                ),
                409,
            )
        except MissingIdMappingError as mie:
            add_log(f"ID mapping incomplete: {str(mie)}", "error")
            return (
                jsonify(
                    {
                        "error": "id_mapping_incomplete",
                        "message": str(mie),
                        "missing_ids": mie.missing_ids,
                        "suggestions": mie.suggestions,
                        "log": log_messages,
                    }
                ),
                409,
            )
        except UnmatchedGroupsError as uge:
            add_log(f"Unmatched groups: {str(uge)}", "error")
            return (
                jsonify(_format_unmatched_groups_response(uge, log_messages)),
                409,
            )
        except Exception as conv_err:
            import traceback
            import sys

            full_trace = traceback.format_exc()
            # Log to console as well
            print(
                f"\n[CONVERSION ERROR] {type(conv_err).__name__}: {str(conv_err)}",
                file=sys.stderr,
            )
            print(f"[FULL TRACEBACK]\n{full_trace}", file=sys.stderr)
            add_log(
                f"Conversion engine failed: {type(conv_err).__name__}: {str(conv_err)}",
                "error",
            )
            # Split traceback into lines for better display in web UI
            for line in full_trace.split("\n"):
                if line.strip():
                    add_log(line, "error")
            raise conv_err

        # Process warnings and missing cells
        if convert_result and getattr(convert_result, "missing_cells_by_subject", None):
            missing_counts = {
                sid: cnt
                for sid, cnt in convert_result.missing_cells_by_subject.items()
                if cnt > 0
            }
            if missing_counts:
                conversion_warnings.append(
                    f"Missing responses normalized: {sum(missing_counts.values())} cells."
                )

        if convert_result and getattr(convert_result, "conversion_warnings", None):
            conversion_warnings.extend(convert_result.conversion_warnings)

        # Run validation
        add_log("Running validation...", "info")
        validation_result = {"errors": [], "warnings": [], "summary": {}}
        if request.form.get("validate") == "true":
            try:
                v_res = run_validation(
                    str(output_root),
                    schema_version="stable",
                    library_path=str(effective_survey_dir),
                )
                if v_res and isinstance(v_res, tuple):
                    issues = v_res[0]
                    stats = v_res[1]

                    # Format results for the UI
                    from src.web.reporting_utils import format_validation_results

                    formatted = format_validation_results(
                        issues, stats, str(output_root)
                    )

                    # Include the full formatted results for the UI to display properly
                    # We use a new dict to avoid circular references
                    validation_result = {"formatted": formatted}
                    validation_result.update(formatted)

                    # Log errors to the web terminal
                    total_err = formatted.get("summary", {}).get("total_errors", 0)
                    total_warn = formatted.get("summary", {}).get("total_warnings", 0)

                    if total_err > 0:
                        add_log(
                            f"✗ Validation failed with {total_err} error(s)", "error"
                        )
                        # Log the first 20 errors specifically to the terminal
                        count = 0
                        for group in formatted.get("errors", []):
                            for f in group.get("files", []):
                                if count < 20:
                                    # Clean up message for terminal
                                    msg = f["message"]
                                    if ": " in msg:
                                        msg = msg.split(": ", 1)[1]
                                    add_log(f"  - {msg}", "error")
                                    count += 1
                        if total_err > 20:
                            add_log(
                                f"  ... and {total_err - 20} more errors (see details below)",
                                "error",
                            )
                    else:
                        add_log("✓ PRISM validation passed!", "success")

                    if total_warn > 0:
                        add_log(f"⚠ {total_warn} warning(s) found", "warning")

            except Exception as val_err:
                validation_result["warnings"].append(
                    f"Validation error: {str(val_err)}"
                )

        # Add conversion warnings to the final result
        if conversion_warnings:
            if "warnings" not in validation_result:
                validation_result["warnings"] = []

            # Add as a group if we have formatted results
            if "formatted" in validation_result:
                conv_group = {
                    "code": "CONVERSION",
                    "message": "Conversion Warnings",
                    "description": "Issues encountered during data conversion",
                    "files": [
                        {"file": filename, "message": w} for w in conversion_warnings
                    ],
                    "count": len(conversion_warnings),
                }
                validation_result["warnings"].append(conv_group)
                if "summary" in validation_result:
                    validation_result["summary"]["total_warnings"] += len(
                        conversion_warnings
                    )
            else:
                # Simple string list for non-formatted results
                validation_result["warnings"].extend(conversion_warnings)

        # Save to project if requested
        if save_to_project:
            project_path = session.get("current_project_path")
            if project_path:
                project_path = Path(project_path)

                # If the path is a file (project.json), get the parent directory
                if project_path.is_file():
                    project_path = project_path.parent

                if project_path.exists() and project_path.is_dir():
                    # Prefer rawdata/ (BIDS/YODA standard), create if needed
                    dest_root = project_path / "rawdata"
                    dest_root.mkdir(parents=True, exist_ok=True)
                    add_log(
                        f"Saving output to project: {project_path.name} (into {dest_root.name}/)",
                        "info",
                    )

                    # Merge output_root contents into dest_root
                    for item in output_root.rglob("*"):
                        if item.is_file():
                            rel_path = item.relative_to(output_root)
                            dest = dest_root / rel_path
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, dest)
                    add_log("Project updated successfully!", "success")

                    # Archive original file to sourcedata/ if requested
                    if archive_sourcedata:
                        sourcedata_dir = project_path / "sourcedata"
                        sourcedata_dir.mkdir(parents=True, exist_ok=True)
                        archive_dest = sourcedata_dir / filename
                        shutil.copy2(input_path, archive_dest)
                        add_log(
                            f"Archived original file to sourcedata/{filename}", "info"
                        )

                    # Register session in project.json
                    if session_override:
                        conv_type = "survey-lsa" if suffix == ".lsa" else "survey-xlsx"
                        tasks_out = (
                            convert_result.tasks_included
                            if convert_result
                            and getattr(convert_result, "tasks_included", None)
                            else _extract_tasks_from_output(output_root)
                        )
                        _register_session_in_project(
                            project_path,
                            session_override,
                            tasks_out,
                            "survey",
                            filename,
                            conv_type,
                        )
                        add_log(
                            f"Registered in project.json: ses-{session_override} → {', '.join(tasks_out)}",
                            "info",
                        )
                else:
                    add_log(f"Project path not found: {project_path}", "error")
            else:
                add_log(
                    "No project selected in session. Cannot save directly.", "warning"
                )

        # Create ZIP
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in output_root.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(output_root).as_posix())
        mem.seek(0)
        zip_base64 = base64.b64encode(mem.read()).decode("utf-8")

        response_payload = {
            "success": True,
            "log": log_messages,
            "validation": validation_result,
            "zip_base64": zip_base64,
        }

        # Include conversion summary for LSA files (template matches, tool columns, etc.)
        if convert_result:
            summary = {}
            if getattr(convert_result, "template_matches", None):
                summary["template_matches"] = convert_result.template_matches
            if getattr(convert_result, "tasks_included", None):
                summary["tasks_included"] = convert_result.tasks_included
            if getattr(convert_result, "task_runs", None):
                summary["task_runs"] = convert_result.task_runs
            if getattr(convert_result, "unknown_columns", None):
                summary["unknown_columns"] = convert_result.unknown_columns
            if getattr(convert_result, "tool_columns", None):
                summary["tool_columns"] = convert_result.tool_columns
            if conversion_warnings:
                summary["conversion_warnings"] = conversion_warnings
            if summary:
                response_payload["conversion_summary"] = summary

        return jsonify(sanitize_jsonable(response_payload))
    except Exception as e:
        return jsonify({"error": str(e), "log": log_messages}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_bp.route("/api/save-unmatched-template", methods=["POST"])
def api_save_unmatched_template():
    """Save a generated template for an unmatched group to the project library."""
    project_path = session.get("current_project_path")
    if not project_path:
        return jsonify({"error": "No project selected"}), 400

    data = request.get_json()
    task_key = data.get("task_key")
    prism_json = data.get("prism_json")
    if not task_key or not prism_json:
        return jsonify({"error": "Missing task_key or prism_json"}), 400

    # Clean internal keys and strip run suffixes from item codes so the
    # saved template uses base codes (e.g. BRS01 not BRS01run02).  This
    # ensures the template matcher can match it on re-import regardless
    # of run numbering.
    from src.converters.template_matcher import _strip_run_suffix

    clean = {}
    for k, v in prism_json.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and k not in _NON_ITEM_TOPLEVEL_KEYS:
            base, _ = _strip_run_suffix(k)
            if base not in clean:
                clean[base] = v
        else:
            clean[k] = v

    library_path = Path(project_path) / "code" / "library" / "survey"
    library_path.mkdir(parents=True, exist_ok=True)

    filename = f"survey-{task_key}.json"
    filepath = library_path / filename

    from src.utils.io import write_json

    write_json(filepath, clean)

    return jsonify(
        {
            "success": True,
            "path": str(filepath),
            "filename": filename,
        }
    )


@conversion_bp.route("/api/biometrics-check-library", methods=["GET"])
def api_biometrics_check_library():
    """Check the structure of a biometrics template library folder."""
    library_path = (request.args.get("library_path") or "").strip()
    if not library_path:
        return jsonify({"error": "No library path provided"}), 400

    library_root = Path(library_path)
    # Handle official/library/biometrics structure
    if (library_root / "library" / "biometrics").is_dir():
        biometrics_dir = library_root / "library" / "biometrics"
    else:
        biometrics_dir = library_root / "biometrics"

    # Handle official/library/survey structure
    if (library_root / "library" / "survey").is_dir():
        survey_dir = library_root / "library" / "survey"
    else:
        survey_dir = library_root / "survey"

    participant_candidates = _participant_json_candidates(library_root)
    has_participants = any(p.is_file() for p in participant_candidates)

    structure_info = {
        "has_survey_folder": survey_dir.is_dir(),
        "has_biometrics_folder": biometrics_dir.is_dir(),
        "has_participants_json": has_participants,
        "missing_items": [],
        "template_count": 0,
    }

    if not structure_info["has_biometrics_folder"]:
        structure_info["missing_items"].append("biometrics/")
    if not structure_info["has_participants_json"]:
        structure_info["missing_items"].append(
            "participants.json (or ../participants.json)"
        )
    if biometrics_dir.is_dir():
        structure_info["template_count"] = len(
            list(biometrics_dir.glob("biometrics-*.json"))
        )

    return jsonify({"structure": structure_info})


@conversion_bp.route("/api/biometrics-detect", methods=["POST"])
def api_biometrics_detect():
    """Detect which biometrics tasks are present in the uploaded file."""
    from src.converters.biometrics import detect_biometrics_in_table

    uploaded_file = request.files.get("data") or request.files.get("file")

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    # Automatically resolve library path (project first, then global)
    try:
        library_root = _resolve_effective_library_path()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 400

    filename = secure_filename(uploaded_file.filename)
    tmp_dir = tempfile.mkdtemp(prefix="prism_biometrics_detect_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        biometrics_dir = library_root / "biometrics"
        effective_biometrics_dir = (
            biometrics_dir if biometrics_dir.is_dir() else library_root
        )

        detected_tasks = detect_biometrics_in_table(
            input_path=input_path,
            library_dir=effective_biometrics_dir,
            sheet=(request.form.get("sheet") or "0").strip() or 0,
        )

        return jsonify({"tasks": detected_tasks})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_bp.route("/api/biometrics-convert", methods=["POST"])
def api_biometrics_convert():
    """Convert an uploaded biometrics table (.csv or .xlsx) into a PRISM/BIDS-style dataset ZIP."""
    print("[DEBUG] api_biometrics_convert() called")  # DEBUG
    if not convert_biometrics_table_to_prism_dataset:
        print(
            "[DEBUG] convert_biometrics_table_to_prism_dataset not available!"
        )  # DEBUG
        return jsonify({"error": "Biometrics conversion module not available"}), 500

    uploaded_file = request.files.get("data") or request.files.get("file")
    print(f"[DEBUG] uploaded_file: {uploaded_file}")  # DEBUG

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx", ".tsv"}:
        return jsonify({"error": "Supported formats: .csv, .xlsx, .tsv"}), 400

    # Automatically resolve library path (project first, then global)
    try:
        library_root = _resolve_effective_library_path()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 400

    biometrics_dir = library_root / "biometrics"
    effective_biometrics_dir = (
        biometrics_dir if biometrics_dir.is_dir() else library_root
    )

    biometrics_templates = list(effective_biometrics_dir.glob("biometrics-*.json"))
    if not biometrics_templates:
        return (
            jsonify(
                {
                    "error": f"No biometrics templates found in: {effective_biometrics_dir}"
                }
            ),
            400,
        )

    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    session_override = (request.form.get("session") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    dataset_name = (request.form.get("dataset_name") or "").strip() or None
    save_to_project = request.form.get("save_to_project") == "true"
    dry_run = request.form.get("dry_run", "false").lower() == "true"

    # Get tasks to export
    tasks_to_export = request.form.getlist("tasks[]")
    if not tasks_to_export:
        # Fallback to all if none specified (for backward compatibility)
        tasks_to_export = None

    log = []

    def log_msg(message, type="info"):
        log.append({"message": message, "type": type})

    tmp_dir = tempfile.mkdtemp(prefix="prism_biometrics_convert_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        output_root = tmp_dir_path / "prism_dataset"

        if dry_run:
            log_msg("🔍 DRY-RUN MODE - No files will be created", "info")

        log_msg("", "info")
        log_msg(f"Starting biometrics conversion for {filename}", "info")
        log_msg(f"Template library: {effective_biometrics_dir}", "step")
        log_msg(f"Session: {session_override or 'auto-detect'}", "step")
        log_msg(f"Sheet: {sheet}", "step")
        log_msg("", "info")

        # Log the head to help debug delimiter/structure issues
        _log_file_head(input_path, suffix, log_msg)

        log_msg("", "info")
        log_msg("Backend command:", "step")
        log_msg("  convert_biometrics_table_to_prism_dataset(", "info")
        log_msg(f"    input_path='{input_path.name}',", "info")
        log_msg(f"    library_dir='{effective_biometrics_dir}',", "info")
        log_msg(f"    session='{session_override}',", "info")
        log_msg(f"    sheet={sheet},", "info")
        log_msg(f"    unknown='{unknown}'", "info")
        log_msg("  )", "info")
        log_msg("", "info")

        if tasks_to_export:
            log_msg(f"Exporting tasks: {', '.join(tasks_to_export)}", "step")

        result = convert_biometrics_table_to_prism_dataset(
            input_path=input_path,
            library_dir=str(effective_biometrics_dir),
            output_root=output_root,
            id_column=id_column,
            session_column=session_column,
            session=session_override,
            sheet=sheet,
            unknown=unknown,
            force=True,
            name=dataset_name,
            authors=["prism-studio"],
            tasks_to_export=tasks_to_export,
        )

        log_msg(f"Detected ID column: {result.id_column}", "success")
        if result.session_column:
            log_msg(f"Detected session column: {result.session_column}", "success")

        log_msg(f"Included tasks: {', '.join(result.tasks_included)}", "info")

        if result.unknown_columns:
            for col in result.unknown_columns:
                log_msg(f"Unknown column ignored: {col}", "warning")

        # Save to project if requested (but not in dry-run mode)
        if save_to_project and not dry_run:
            project_path = session.get("current_project_path")
            if project_path:
                project_path = Path(project_path)
                if project_path.exists():
                    log_msg(f"Saving output to project: {project_path.name}", "info")
                    # Merge output_root contents into project_path
                    for item in output_root.rglob("*"):
                        if item.is_file():
                            rel_path = item.relative_to(output_root)
                            dest = project_path / rel_path
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, dest)
                    log_msg("Project updated successfully!", "success")

                    # Register session in project.json
                    if (
                        session_override
                        and result
                        and getattr(result, "tasks_included", None)
                    ):
                        _register_session_in_project(
                            project_path,
                            session_override,
                            result.tasks_included,
                            "biometrics",
                            filename,
                            "biometrics",
                        )
                        log_msg(
                            f"Registered in project.json: ses-{session_override} → {', '.join(result.tasks_included)}",
                            "info",
                        )
                else:
                    log_msg(f"Project path not found: {project_path}", "error")
            else:
                log_msg(
                    "No project selected in session. Cannot save directly.", "warning"
                )

        # Create ZIP (but not in dry-run mode)
        zip_base64 = None
        if not dry_run:
            mem = io.BytesIO()
            with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                for p in output_root.rglob("*"):
                    if p.is_file():
                        arcname = p.relative_to(output_root)
                        zf.write(p, arcname.as_posix())
            mem.seek(0)

            zip_base64 = base64.b64encode(mem.read()).decode("utf-8")

        # Run validation if requested
        validation = None
        if request.form.get("validate") == "true":
            log_msg("Running PRISM validation on generated dataset...", "step")
            validation = {"errors": [], "warnings": [], "summary": {}}
            try:
                # Use run_validation which is already imported and handles the tuple return
                v_res = run_validation(
                    str(output_root),
                    schema_version="stable",
                    library_path=str(library_root),
                )
                if v_res and isinstance(v_res, tuple):
                    issues = v_res[0]
                    stats = v_res[1]

                    # Format results for the UI
                    from src.web.reporting_utils import format_validation_results

                    formatted = format_validation_results(
                        issues, stats, str(output_root)
                    )

                    # Extract flat lists for the simple log
                    for group in formatted.get("errors", []):
                        for f in group.get("files", []):
                            validation["errors"].append(
                                f"{group['code']}: {f['message']} ({f['file']})"
                            )

                    for group in formatted.get("warnings", []):
                        for f in group.get("files", []):
                            validation["warnings"].append(
                                f"{group['code']}: {f['message']} ({f['file']})"
                            )

                    validation["summary"] = {
                        "files_created": len(
                            list(output_root.rglob("*_biometrics.tsv"))
                        ),
                        "total_errors": formatted.get("summary", {}).get(
                            "total_errors", 0
                        ),
                        "total_warnings": formatted.get("summary", {}).get(
                            "total_warnings", 0
                        ),
                    }

                    # Include the full formatted results for the UI to display properly
                    validation["formatted"] = formatted

                    # Log errors to the web terminal
                    total_err = formatted.get("summary", {}).get("total_errors", 0)
                    total_warn = formatted.get("summary", {}).get("total_warnings", 0)

                    if total_err > 0:
                        log_msg(
                            f"✗ Validation failed with {total_err} error(s)", "error"
                        )
                        # Log the first 20 errors specifically to the terminal
                        count = 0
                        for group in formatted.get("errors", []):
                            for f in group.get("files", []):
                                if count < 20:
                                    # Clean up message for terminal (remove file path if redundant)
                                    msg = f["message"]
                                    if ": " in msg:
                                        msg = msg.split(": ", 1)[1]
                                    log_msg(f"  - {msg}", "error")
                                    count += 1
                        if total_err > 20:
                            log_msg(
                                f"  ... and {total_err - 20} more errors (see details below)",
                                "error",
                            )
                    else:
                        log_msg("✓ PRISM validation passed!", "success")

                    if total_warn > 0:
                        log_msg(f"⚠ {total_warn} warning(s) found", "warning")

            except Exception as val_err:
                log_msg(f"Validation error: {val_err}", "error")

        return jsonify({"log": log, "zip_base64": zip_base64, "validation": validation})

    except IdColumnNotDetectedError as e:
        return (
            jsonify(
                {
                    "error": "id_column_required",
                    "message": str(e),
                    "columns": e.available_columns,
                    "log": log,
                }
            ),
            409,
        )
    except Exception as e:
        return jsonify({"error": str(e), "log": log}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_bp.route("/api/physio-convert", methods=["POST"])
def api_physio_convert():
    """Convert an uploaded Varioport file (.raw/.vpd) into EDF+ (.edf) + sidecar (.json) and return as ZIP."""
    if convert_varioport is None:
        return jsonify({"error": "Physio conversion (Varioport) not available"}), 500

    uploaded_file = request.files.get("raw") or request.files.get("file")
    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".raw", ".vpd"}:
        return (
            jsonify({"error": "Only Varioport .raw and .vpd files are supported"}),
            400,
        )

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
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_bp.route("/api/batch-convert", methods=["POST"])
def api_batch_convert():
    """Batch convert physio/eyetracking files from a flat folder structure."""
    if not batch_convert_folder:
        return jsonify({"error": "Batch conversion not available"}), 500

    logs = []

    def log_callback(message: str, level: str = "info"):
        logs.append({"message": message, "level": level})

    dataset_name = (request.form.get("dataset_name") or "Converted Dataset").strip()
    modality_filter = request.form.get("modality", "all")
    save_to_project = (request.form.get("save_to_project") or "false").lower() == "true"
    dest_root = (request.form.get("dest_root") or "rawdata").strip().lower()
    if dest_root not in {"rawdata", "sourcedata"}:
        dest_root = "rawdata"
    sampling_rate_str = request.form.get("sampling_rate", "").strip()
    dry_run = (request.form.get("dry_run") or "false").lower() == "true"

    try:
        sampling_rate = float(sampling_rate_str) if sampling_rate_str else None
    except ValueError:
        return jsonify({"error": "sampling_rate must be a number", "logs": logs}), 400

    files = request.files.getlist("files[]") or request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded", "logs": logs}), 400

    # Accept a wider range of extensions for the batch organizer
    valid_extensions = {
        ".raw",
        ".vpd",
        ".edf",
        ".tsv",
        ".tsv.gz",
        ".csv",
        ".txt",
        ".json",
        ".nii",
        ".nii.gz",
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
    }
    validated_files = []
    for f in files:
        if not f or not f.filename:
            continue
        filename = secure_filename(f.filename)

        # Handle .nii.gz and .tsv.gz
        lower_name = filename.lower()
        if lower_name.endswith(".nii.gz"):
            ext = ".nii.gz"
        elif lower_name.endswith(".tsv.gz"):
            ext = ".tsv.gz"
        else:
            ext = Path(filename).suffix.lower()

        if ext in valid_extensions and parse_bids_filename(filename):
            validated_files.append((f, filename))

    if not validated_files:
        return jsonify({"error": "No valid files to convert.", "logs": logs}), 400

    tmp_dir = tempfile.mkdtemp(prefix="prism_batch_convert_")
    warnings = []
    warned_subjects = set()
    try:
        tmp_path = Path(tmp_dir)
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        for f, filename in validated_files:
            f.save(str(input_dir / filename))

        result = batch_convert_folder(
            input_dir,
            output_dir,
            physio_sampling_rate=sampling_rate,
            modality_filter=modality_filter,
            log_callback=log_callback,
            dry_run=dry_run,
        )

        if dry_run:
            # For dry run, just return the logs (no file creation)
            return jsonify(
                {
                    "converted": result.success_count,
                    "errors": result.error_count,
                    "new_files": result.new_files,
                    "existing_files": result.existing_files,
                    "logs": logs,
                    "dry_run": True,
                }
            )

        create_dataset_description(output_dir, name=dataset_name)

        # Check for conflicts (files with different content)
        if result.conflicts:
            conflicts_info = [
                {"path": str(c.output_path.relative_to(output_dir)), "reason": c.reason}
                for c in result.conflicts
            ]
            return (
                jsonify(
                    {
                        "error": f"File conflicts detected: {len(result.conflicts)} files already exist with different content. Please use different names or delete existing files.",
                        "conflicts": conflicts_info,
                        "logs": logs,
                    }
                ),
                409,
            )

        project_saved = False
        project_root = None
        if save_to_project:
            p_path = session.get("current_project_path")
            if p_path:
                project_root = Path(p_path)
                if project_root.exists():
                    project_root = project_root / dest_root
                    project_root.mkdir(parents=True, exist_ok=True)
                else:
                    warnings.append(
                        f"Project path not found: {p_path}. Copy to project skipped."
                    )
                    project_root = None
            else:
                warnings.append("No active project selected; copy to project skipped.")

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(output_dir)
                    zf.write(file_path, rel_path)

                    if project_root:
                        # Warn if subject folder is being created
                        bids = (
                            parse_bids_filename(rel_path.name)
                            if parse_bids_filename
                            else None
                        )
                        subject_label = None
                        if bids and bids.get("sub"):
                            subject_label = bids.get("sub")
                        else:
                            m = re.search(r"(sub-[A-Za-z0-9]+)", rel_path.name)
                            if m:
                                subject_label = m.group(1)

                        if subject_label:
                            subject_dir = project_root / subject_label
                            if (
                                not subject_dir.exists()
                                and subject_label not in warned_subjects
                            ):
                                warnings.append(
                                    f"Subject folder {subject_label} did not exist and will be created in project."
                                )
                                warned_subjects.add(subject_label)

                        dest_path = project_root / rel_path
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file_path, dest_path)
                        project_saved = True

        import base64

        zip_base64 = base64.b64encode(mem.read()).decode("utf-8")

        return jsonify(
            {
                "status": "success",
                "log": "\n".join([log_entry["message"] for log_entry in logs]),
                "zip": zip_base64,
                "converted": result.success_count,
                "errors": result.error_count,
                "project_saved": project_saved,
                "warnings": warnings,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e), "logs": logs}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_bp.route("/api/physio-rename", methods=["POST"])
def api_physio_rename():
    """Rename uploaded files based on a regex pattern and return a ZIP."""
    pattern = request.form.get("pattern", "")
    replacement = request.form.get("replacement", "")
    dry_run = request.form.get("dry_run", "false").lower() == "true"
    organize = request.form.get("organize", "false").lower() == "true"
    modality = request.form.get("modality", "physio")
    save_to_project = request.form.get("save_to_project", "false").lower() == "true"

    files = request.files.getlist("files[]") or request.files.getlist("files")

    # If dry run, we might just have filenames in a list
    filenames = request.form.getlist("filenames[]") or request.form.getlist("filenames")

    if not files and not filenames and not dry_run:
        return jsonify({"error": "No files or filenames provided"}), 400

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return jsonify({"error": f"Invalid regex: {str(e)}"}), 400

    results = []
    warnings = []
    warned_subjects = set()

    if dry_run:
        # Use filenames if provided, else use uploaded files' names
        source_names = (
            filenames if filenames else [f.filename for f in files if f.filename]
        )
        for fname in source_names:
            try:
                new_name = regex.sub(replacement, fname)

                # Determine the path within the ZIP (for preview)
                zip_path = new_name
                if organize:
                    bids = None
                    if parse_bids_filename:
                        bids = parse_bids_filename(new_name)

                    if bids:
                        sub = bids.get("sub")
                        ses = bids.get("ses")
                        parts = [sub]
                        if ses:
                            parts.append(ses)
                        parts.append(modality)
                        parts.append(new_name)
                        zip_path = "/".join(parts)

                results.append(
                    {"old": fname, "new": new_name, "path": zip_path, "success": True}
                )
            except Exception as e:
                results.append({"old": fname, "new": str(e), "success": False})
        return jsonify({"results": results, "warnings": warnings})

    # Actual renaming and zipping
    if not files:
        return jsonify({"error": "No files uploaded for renaming"}), 400

    mem = io.BytesIO()
    project_root = None
    if save_to_project:
        p_path = session.get("current_project_path")
        if p_path:
            project_root = Path(p_path)
            if project_root.exists():
                project_root = project_root / "rawdata"
                project_root.mkdir(parents=True, exist_ok=True)
            else:
                warnings.append(
                    f"Project path not found: {p_path}. Copy to project skipped."
                )
                project_root = None
        else:
            warnings.append("No active project selected; copy to project skipped.")
    try:
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                if not f or not f.filename:
                    continue
                old_name = secure_filename(f.filename)

                try:
                    new_name = regex.sub(replacement, old_name)

                    # Determine the path within the ZIP
                    zip_path = new_name
                    if organize:
                        # Try to parse BIDS components to build structure
                        bids = None
                        if parse_bids_filename:
                            bids = parse_bids_filename(new_name)

                        if bids:
                            sub = bids.get("sub")
                            ses = bids.get("ses")

                            parts = [sub]
                            if ses:
                                parts.append(ses)
                            parts.append(modality)
                            parts.append(new_name)

                            zip_path = "/".join(parts)

                    f_content = f.read()
                    zf.writestr(zip_path, f_content)

                    if project_root:
                        dest_path = project_root / Path(zip_path)

                        # Warn if subject folder does not yet exist (but still allow creation)
                        subject_label = None
                        if parse_bids_filename:
                            bids_parts = parse_bids_filename(new_name)
                            if bids_parts:
                                subject_label = bids_parts.get("sub")
                        if not subject_label:
                            m = re.search(r"(sub-[A-Za-z0-9]+)", new_name)
                            if m:
                                subject_label = m.group(1)

                        if subject_label:
                            subject_dir = project_root / subject_label
                            if (
                                not subject_dir.exists()
                                and subject_label not in warned_subjects
                            ):
                                warnings.append(
                                    f"Subject folder {subject_label} did not exist and will be created in project."
                                )
                                warned_subjects.add(subject_label)

                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(dest_path, "wb") as out_f:
                            out_f.write(f_content)
                    results.append(
                        {
                            "old": old_name,
                            "new": new_name,
                            "success": True,
                            "path": zip_path,
                        }
                    )
                except Exception as e:
                    results.append({"old": old_name, "new": str(e), "success": False})

        mem.seek(0)
        import base64

        zip_base64 = base64.b64encode(mem.read()).decode("utf-8")

        return jsonify(
            {
                "status": "success",
                "results": results,
                "zip": zip_base64,
                "project_saved": bool(project_root),
                "warnings": warnings,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@conversion_bp.route("/api/save-participant-mapping", methods=["POST"])
def save_participant_mapping():
    """Save participant mapping JSON file to the project survey library directory.

    Priority:
    1. Save to project library if available
    2. Fall back to provided library path
    """
    try:
        import json

        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        mapping = data.get("mapping")
        library_path = data.get("library_path")
        project_path = session.get("current_project_path")

        if not mapping:
            return jsonify({"error": "Missing mapping data"}), 400

        # Determine target library path
        target_lib_path = None
        used_source = None

        # Priority 1: Use project library if available
        if project_path:
            try:
                project_lib = (
                    Path(str(project_path)).resolve() / "code" / "library" / "survey"
                )
                # Create the library folder if it doesn't exist
                project_lib.mkdir(parents=True, exist_ok=True)
                target_lib_path = project_lib
                used_source = "project"
            except Exception:
                pass  # Fall through to Priority 2

        # Priority 2: Fall back to provided library path
        if not target_lib_path and library_path:
            try:
                lib_path = Path(str(library_path)).resolve()
                if lib_path.exists() and lib_path.is_dir():
                    target_lib_path = lib_path
                    used_source = "provided"
            except Exception as e:
                return jsonify({"error": f"Invalid library path: {str(e)}"}), 400

        if not target_lib_path:
            return (
                jsonify(
                    {
                        "error": "No valid library path found. Please ensure project is loaded or select a library path."
                    }
                ),
                400,
            )

        # Create participants_mapping.json in the target library directory
        mapping_file = target_lib_path / "participants_mapping.json"

        # Write the mapping file
        with open(mapping_file, "w") as f:
            json.dump(mapping, f, indent=2)

        return jsonify(
            {
                "status": "success",
                "file_path": str(mapping_file),
                "library_source": used_source,
                "message": f"Participant mapping saved to {mapping_file.name}",
            }
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Error saving mapping: {str(e)}"}), 500


# ==================== PARTICIPANTS CONVERSION ROUTES ====================


@conversion_bp.route("/api/participants-check", methods=["GET"])
def api_participants_check():
    """Check if participants.tsv and participants.json exist in the project/dataset."""
    project_path = session.get("current_project_path")
    if not project_path:
        return jsonify({"error": "No project selected"}), 400

    project_root = Path(project_path)

    # Check both root and rawdata subfolder
    participants_tsv = project_root / "participants.tsv"
    participants_json = project_root / "participants.json"

    rawdata_participants_tsv = project_root / "rawdata" / "participants.tsv"
    rawdata_participants_json = project_root / "rawdata" / "participants.json"

    exists_root = participants_tsv.exists() or participants_json.exists()
    exists_rawdata = (
        rawdata_participants_tsv.exists() or rawdata_participants_json.exists()
    )

    return jsonify(
        {
            "exists": exists_root or exists_rawdata,
            "location": (
                "root" if exists_root else ("rawdata" if exists_rawdata else None)
            ),
            "files": {
                "participants_tsv": (
                    str(participants_tsv)
                    if participants_tsv.exists()
                    else (
                        str(rawdata_participants_tsv)
                        if rawdata_participants_tsv.exists()
                        else None
                    )
                ),
                "participants_json": (
                    str(participants_json)
                    if participants_json.exists()
                    else (
                        str(rawdata_participants_json)
                        if rawdata_participants_json.exists()
                        else None
                    )
                ),
            },
        }
    )


@conversion_bp.route("/api/participants-preview", methods=["POST"])
def api_participants_preview():
    """Preview participant data extraction from uploaded file."""
    try:
        from src.participants_converter import ParticipantsConverter
        import pandas as pd
    except ImportError as e:
        return jsonify({"error": f"Required module not available: {str(e)}"}), 500

    mode = request.form.get("mode", "file")

    if mode == "file":
        # File mode: extract from uploaded file
        uploaded_file = request.files.get("file")
        if not uploaded_file or not uploaded_file.filename:
            return jsonify({"error": "Missing input file"}), 400

        filename = secure_filename(uploaded_file.filename)
        suffix = Path(filename).suffix.lower()

        if suffix not in {".xlsx", ".csv", ".tsv", ".lsa"}:
            return jsonify({"error": "Supported formats: .xlsx, .csv, .tsv, .lsa"}), 400

        tmp_dir = tempfile.mkdtemp(prefix="prism_participants_preview_")
        try:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / filename
            uploaded_file.save(str(input_path))

            # Read the file
            sheet = request.form.get("sheet", "0").strip() or "0"
            try:
                sheet_arg = int(sheet) if sheet.isdigit() else sheet
            except (ValueError, TypeError):
                sheet_arg = 0

            if suffix == ".xlsx":
                df = pd.read_excel(input_path, sheet_name=sheet_arg, dtype=str)
            elif suffix in {".csv", ".tsv"}:
                sep = "\t" if suffix == ".tsv" else ","
                df = pd.read_csv(input_path, sep=sep, dtype=str)
            elif suffix == ".lsa":
                # Handle LimeSurvey archive
                try:
                    from src.converters.survey import _read_lsa_as_dataframe

                    df = _read_lsa_as_dataframe(input_path)
                except ImportError:
                    return jsonify({"error": "LimeSurvey support not available"}), 500

            # Detect ID column
            from src.converters.id_detection import (
                detect_id_column as _detect_id,
                has_prismmeta_columns as _has_pm_cols,
            )

            id_column = request.form.get("id_column", "").strip() or None
            source_fmt = "lsa" if suffix == ".lsa" else "xlsx"
            _has_pm = _has_pm_cols(list(df.columns))
            id_column = _detect_id(
                list(df.columns),
                source_fmt,
                explicit_id_column=id_column,
                has_prismmeta=_has_pm,
            )

            if not id_column:
                return (
                    jsonify(
                        {
                            "error": "id_column_required",
                            "message": f"Could not auto-detect ID column. Available columns: {', '.join(df.columns)}",
                            "columns": list(df.columns),
                        }
                    ),
                    409,
                )

            # Get library path for participants.json
            library_path = _resolve_effective_library_path()

            # SIMULATE CONVERSION: Show what the OUTPUT will look like
            # Check if participants.json exists in library to determine expected schema
            participants_json_path = library_path / "participants.json"

            # Build expected output columns based on participants.json if available
            expected_columns = []
            if participants_json_path.exists():
                try:
                    with open(participants_json_path, "r") as f:
                        schema = json.load(f)
                        expected_columns = list(schema.keys())
                except (OSError, json.JSONDecodeError, KeyError):
                    pass

            # If no schema, use common participant columns
            if not expected_columns:
                expected_columns = [
                    "participant_id",
                    "age",
                    "sex",
                    "handedness",
                    "group",
                ]

            # Filter to only columns that exist in the source data
            output_columns = [id_column]  # Always include ID column first
            for col in expected_columns:
                if col != id_column and col in df.columns:
                    output_columns.append(col)

            # If still empty (no matching columns), show a limited set from source
            if len(output_columns) <= 1:
                # Show all columns but warn it's raw
                output_df = df[list(df.columns)]
                simulation_note = (
                    "No participants.json schema found. Showing raw file structure."
                )
            else:
                # Show only the columns that will be in participants.tsv
                output_df = df[output_columns]
                simulation_note = (
                    f"Simulated output with {len(output_columns)} participant columns."
                )

            # Preview first 20 rows
            preview_df = output_df.head(20)

            # NEUROBAGEL INTEGRATION: Generate suggested participants.json with annotations
            neurobagel_schema = _generate_neurobagel_schema(output_df, id_column)

            return jsonify(
                {
                    "status": "success",
                    "columns": list(output_df.columns),
                    "id_column": id_column,
                    "participant_count": len(df),
                    "preview_rows": preview_df.to_dict(orient="records"),
                    "library_path": str(library_path),
                    "simulation_note": simulation_note,
                    "total_source_columns": len(df.columns),
                    "extracted_columns": len(output_df.columns),
                    "neurobagel_schema": neurobagel_schema,
                }
            )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    elif mode == "dataset":
        # Dataset mode: extract from converted data
        project_path = session.get("current_project_path")
        if not project_path:
            return jsonify({"error": "No project selected"}), 400

        project_root = Path(project_path)
        extract_from_survey = (
            request.form.get("extract_from_survey", "true").lower() == "true"
        )
        extract_from_biometrics = (
            request.form.get("extract_from_biometrics", "true").lower() == "true"
        )

        # Scan for survey and biometrics files
        participants = set()

        if extract_from_survey:
            survey_files = list(project_root.rglob("**/survey/*_survey.tsv"))
            for f in survey_files:
                # Extract participant ID from filename
                match = re.search(r"(sub-[A-Za-z0-9]+)", f.name)
                if match:
                    participants.add(match.group(1))

        if extract_from_biometrics:
            biometrics_files = list(
                project_root.rglob("**/biometrics/*_biometrics.tsv")
            )
            for f in biometrics_files:
                match = re.search(r"(sub-[A-Za-z0-9]+)", f.name)
                if match:
                    participants.add(match.group(1))

        if not participants:
            return jsonify({"error": "No participant data found in dataset"}), 400

        participants_list = sorted(list(participants))

        return jsonify(
            {
                "status": "success",
                "participant_count": len(participants_list),
                "participants": participants_list[:20],  # Preview first 20
                "total_participants": len(participants_list),
            }
        )

    else:
        return jsonify({"error": f"Unknown mode: {mode}"}), 400


@conversion_bp.route("/api/participants-convert", methods=["POST"])
def api_participants_convert():
    """Convert/extract participant data and create participants.tsv and participants.json."""
    try:
        from src.participants_converter import ParticipantsConverter
        import pandas as pd
        import json
    except ImportError as e:
        return jsonify({"error": f"Required module not available: {str(e)}"}), 500

    mode = request.form.get("mode", "file")
    force_overwrite = request.form.get("force_overwrite", "false").lower() == "true"
    neurobagel_schema_json = request.form.get("neurobagel_schema")

    # Parse the neurobagel schema if provided
    neurobagel_schema = {}
    if neurobagel_schema_json:
        try:
            neurobagel_schema = json.loads(neurobagel_schema_json)
        except json.JSONDecodeError:
            pass

    project_path = session.get("current_project_path")
    if not project_path:
        return jsonify({"error": "No project selected"}), 400

    project_root = Path(project_path)

    # Check for existing files
    participants_tsv = project_root / "participants.tsv"
    participants_json = project_root / "participants.json"
    rawdata_tsv = project_root / "rawdata" / "participants.tsv"
    rawdata_json = project_root / "rawdata" / "participants.json"

    existing_files = []
    if participants_tsv.exists():
        existing_files.append(str(participants_tsv))
    if participants_json.exists():
        existing_files.append(str(participants_json))
    if rawdata_tsv.exists():
        existing_files.append(str(rawdata_tsv))
    if rawdata_json.exists():
        existing_files.append(str(rawdata_json))

    if existing_files and not force_overwrite:
        return (
            jsonify(
                {
                    "error": "Participant files already exist. Enable 'force overwrite' to replace them.",
                    "existing_files": existing_files,
                }
            ),
            409,
        )

    logs = []

    def log_msg(level, message):
        logs.append({"level": level, "message": message})

    try:
        if mode == "file":
            # File mode: extract from uploaded file
            uploaded_file = request.files.get("file")
            if not uploaded_file or not uploaded_file.filename:
                return jsonify({"error": "Missing input file"}), 400

            filename = secure_filename(uploaded_file.filename)

            tmp_dir = tempfile.mkdtemp(prefix="prism_participants_convert_")
            try:
                tmp_path = Path(tmp_dir)
                input_path = tmp_path / filename
                uploaded_file.save(str(input_path))

                log_msg("INFO", f"Processing {filename}...")

                # Initialize converter
                converter = ParticipantsConverter(project_root, log_callback=log_msg)

                # Load or create mapping
                mapping = converter.load_mapping()
                if not mapping:
                    # No mapping file, try auto-detection from file headers
                    import pandas as pd

                    try:
                        # Try to detect format
                        test_df = pd.read_csv(
                            str(input_path), sep=None, engine="python", nrows=0
                        )
                        columns = list(test_df.columns)
                        log_msg("INFO", f"Auto-detected columns: {', '.join(columns)}")

                        # Create basic mapping from columns
                        mapping = {"version": "1.0", "mappings": {}}

                        # Map common participant columns
                        for col in columns:
                            col_lower = col.lower()
                            if col_lower in ["participant_id", "sub", "subject", "id"]:
                                mapping["mappings"]["participant_id"] = {
                                    "source_column": col,
                                    "standard_variable": "participant_id",
                                }
                            elif col_lower in ["age"]:
                                mapping["mappings"]["age"] = {
                                    "source_column": col,
                                    "standard_variable": "age",
                                }
                            elif col_lower in ["sex", "biological_sex"]:
                                mapping["mappings"]["sex"] = {
                                    "source_column": col,
                                    "standard_variable": "sex",
                                }
                            elif col_lower in ["gender"]:
                                mapping["mappings"]["gender"] = {
                                    "source_column": col,
                                    "standard_variable": "gender",
                                }
                            elif col_lower in ["handedness"]:
                                mapping["mappings"]["handedness"] = {
                                    "source_column": col,
                                    "standard_variable": "handedness",
                                }

                        if mapping["mappings"]:
                            log_msg(
                                "INFO",
                                f"Auto-created mapping for {len(mapping['mappings'])} columns",
                            )
                    except Exception as e:
                        log_msg("WARNING", f"Could not auto-detect columns: {e}")
                        mapping = {"version": "1.0", "mappings": {}}
                else:
                    log_msg(
                        "INFO",
                        f"Using participants_mapping.json from {converter.mapping_file}",
                    )

                # Convert using the uploaded file
                success, df, messages = converter.convert_participant_data(
                    source_file=str(input_path),
                    mapping=mapping,
                    output_file=str(participants_tsv),
                )

                for msg in messages:
                    log_msg("INFO", msg)

                if not success or df is None:
                    return jsonify({"error": "Conversion failed", "log": logs}), 400

                # Write the dataframe to TSV
                df.to_csv(participants_tsv, sep="\t", index=False)
                log_msg("INFO", f"✓ Created {participants_tsv.name}")

                # Create or update participants.json
                import json as json_module

                participants_json_data = {}
                for col in df.columns:
                    participants_json_data[col] = {"Description": f"Participant {col}"}

                # If neurobagel schema is provided, merge it with participants.json
                if neurobagel_schema:
                    try:
                        for col, schema_def in neurobagel_schema.items():
                            if col not in participants_json_data:
                                participants_json_data[col] = {}

                            # Merge annotations and other properties
                            if "Annotations" in schema_def:
                                if "Annotations" not in participants_json_data[col]:
                                    participants_json_data[col]["Annotations"] = {}
                                participants_json_data[col]["Annotations"].update(
                                    schema_def["Annotations"]
                                )

                            # Also merge other properties (Description, Units, etc.)
                            for key, value in schema_def.items():
                                if (
                                    key != "Annotations"
                                    and key not in participants_json_data[col]
                                ):
                                    participants_json_data[col][key] = value

                        log_msg(
                            "INFO",
                            "Merged NeuroBagel annotations into participants.json",
                        )
                    except Exception as e:
                        log_msg(
                            "WARNING", f"Could not merge NeuroBagel schema: {str(e)}"
                        )

                with open(participants_json, "w") as f:
                    json_module.dump(participants_json_data, f, indent=2)

                log_msg("INFO", f"✓ Created {participants_json.name}")

                log_msg("INFO", f"✓ Created {participants_tsv.name}")
                log_msg("INFO", f"✓ Created {participants_json.name}")

                return jsonify(
                    {
                        "status": "success",
                        "log": logs,
                        "files_created": [
                            str(participants_tsv),
                            str(participants_json),
                        ],
                    }
                )

            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        elif mode == "dataset":
            # Dataset mode: extract from converted data
            extract_from_survey = (
                request.form.get("extract_from_survey", "true").lower() == "true"
            )
            extract_from_biometrics = (
                request.form.get("extract_from_biometrics", "true").lower() == "true"
            )

            log_msg("INFO", "Extracting participant data from dataset...")

            # Scan for participants
            participants = set()

            if extract_from_survey:
                survey_files = list(project_root.rglob("**/survey/*_survey.tsv"))
                log_msg("INFO", f"Found {len(survey_files)} survey files")
                for f in survey_files:
                    match = re.search(r"(sub-[A-Za-z0-9]+)", f.name)
                    if match:
                        participants.add(match.group(1))

            if extract_from_biometrics:
                biometrics_files = list(
                    project_root.rglob("**/biometrics/*_biometrics.tsv")
                )
                log_msg("INFO", f"Found {len(biometrics_files)} biometrics files")
                for f in biometrics_files:
                    match = re.search(r"(sub-[A-Za-z0-9]+)", f.name)
                    if match:
                        participants.add(match.group(1))

            if not participants:
                return (
                    jsonify(
                        {"error": "No participant data found in dataset", "log": logs}
                    ),
                    400,
                )

            participants_list = sorted(list(participants))
            log_msg("INFO", f"Found {len(participants_list)} unique participants")

            # Create simple participants.tsv
            df = pd.DataFrame({"participant_id": participants_list})
            df.to_csv(participants_tsv, sep="\t", index=False)

            # Create basic participants.json
            participants_json_data = {
                "participant_id": {"Description": "Unique participant identifier"}
            }

            # Merge neurobagel schema if provided
            if neurobagel_schema:
                for col, schema_def in neurobagel_schema.items():
                    if col not in participants_json_data:
                        participants_json_data[col] = {}

                    if "Annotations" in schema_def:
                        if "Annotations" not in participants_json_data[col]:
                            participants_json_data[col]["Annotations"] = {}
                        participants_json_data[col]["Annotations"].update(
                            schema_def["Annotations"]
                        )

                    for key, value in schema_def.items():
                        if (
                            key != "Annotations"
                            and key not in participants_json_data[col]
                        ):
                            participants_json_data[col][key] = value

            import json as json_module

            with open(participants_json, "w") as f:
                json_module.dump(participants_json_data, f, indent=2)

            log_msg(
                "INFO",
                f"✓ Created {participants_tsv.name} with {len(participants_list)} participants",
            )
            log_msg("INFO", f"✓ Created {participants_json.name}")

            return jsonify(
                {
                    "status": "success",
                    "log": logs,
                    "participant_count": len(participants_list),
                    "files_created": [str(participants_tsv), str(participants_json)],
                }
            )

        else:
            return jsonify({"error": f"Unknown mode: {mode}", "log": logs}), 400

    except Exception as e:
        import traceback

        log_msg("ERROR", f"Error: {str(e)}")
        log_msg("ERROR", traceback.format_exc())
        return jsonify({"error": str(e), "log": logs}), 500
