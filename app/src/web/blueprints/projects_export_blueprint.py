from flask import Blueprint, jsonify, request, send_file
from pathlib import Path
import os
import tempfile
import traceback
from .projects_helpers import _resolve_project_root_path

projects_export_bp = Blueprint("projects_export", __name__)


@projects_export_bp.route("/api/projects/export", methods=["POST"])
def export_project():
    """
    Export the current project as a ZIP file with optional anonymization.

    Expected JSON body:
    {
        "project_path": "/path/to/project",
        "anonymize": true,
        "mask_questions": true,
        "id_length": 8,
        "deterministic": true,
        "include_derivatives": true,
        "include_code": true,
        "include_analysis": false
    }
    """
    from src.web.export_project import export_project as do_export

    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"error": "No data provided"}), 400

        project_path = data.get("project_path")
        resolved_project_path = _resolve_project_root_path(project_path)
        if resolved_project_path is None:
            return jsonify({"error": "Invalid project path"}), 400

        project_path = resolved_project_path

        # Get export options
        anonymize = bool(data.get("anonymize", True))
        mask_questions = bool(data.get("mask_questions", True))
        id_length = int(data.get("id_length", 8))
        deterministic = bool(data.get("deterministic", True))
        include_derivatives = bool(data.get("include_derivatives", True))
        include_code = bool(data.get("include_code", True))
        include_analysis = bool(data.get("include_analysis", False))

        # Create temporary file for ZIP
        temp_fd, temp_path = tempfile.mkstemp(suffix=".zip")
        os.close(temp_fd)

        try:
            # Perform export
            do_export(
                project_path=project_path,
                output_zip=Path(temp_path),
                anonymize=anonymize,
                mask_questions=mask_questions,
                id_length=id_length,
                deterministic=deterministic,
                include_derivatives=include_derivatives,
                include_code=include_code,
                include_analysis=include_analysis,
            )

            # Generate filename
            project_name = project_path.name
            anon_suffix = "_anonymized" if anonymize else ""
            filename = f"{project_name}{anon_suffix}_export.zip"

            # Send file
            return send_file(
                temp_path,
                mimetype="application/zip",
                as_attachment=True,
                download_name=filename,
            )

        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@projects_export_bp.route("/api/projects/anc-export", methods=["POST"])
def anc_export_project():
    """
    Export the current project to AND (Austrian NeuroCloud) compatible format.

    Expected JSON body:
    {
        "project_path": "/path/to/project",
        "convert_to_git_lfs": false,
        "include_ci_examples": false,
        "metadata": {
            "DATASET_NAME": "My Study",
            "CONTACT_EMAIL": "contact@example.com",
            "AUTHOR_GIVEN_NAME": "John",
            "AUTHOR_FAMILY_NAME": "Doe",
            "DATASET_ABSTRACT": "Description of the dataset"
        }
    }
    """
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        project_path = data.get("project_path")
        resolved_project_path = _resolve_project_root_path(project_path)
        if resolved_project_path is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400

        project_path = resolved_project_path

        # Import AND exporter
        from src.converters.anc_export import ANCExporter

        # Get export options
        convert_to_git_lfs = bool(data.get("convert_to_git_lfs", False))
        include_ci_examples = bool(data.get("include_ci_examples", False))
        metadata = data.get("metadata", {})

        # Determine output path
        output_path = project_path.parent / f"{project_path.name}_anc_export"

        # Create exporter
        exporter = ANCExporter(project_path, output_path)

        # Perform export
        result_path = exporter.export(
            metadata=metadata,
            convert_to_git_lfs=convert_to_git_lfs,
            include_ci_examples=include_ci_examples,
            copy_data=True,
        )

        return jsonify(
            {
                "success": True,
                "output_path": str(result_path),
                "message": "AND export completed successfully",
                "generated_files": {
                    "readme": str(result_path / "README.md"),
                    "citation": str(result_path / "CITATION.cff"),
                    "validator_config": str(
                        result_path / ".bids-validator-config.json"
                    ),
                },
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
