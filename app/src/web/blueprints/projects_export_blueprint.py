from flask import Blueprint, jsonify, request, send_file, session
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import traceback
from src.cross_platform import safe_path_join
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
        # Keep anonymization settings simple in UI: fixed random IDs when enabled.
        id_length = 8
        deterministic = False
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
    Export the current project to ANC (Austrian NeuroCloud) compatible format.

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
            "message": "ANC export completed successfully",
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


@projects_export_bp.route("/api/projects/openminds-tasks", methods=["GET"])
def openminds_get_tasks():
    """Return task names from the current project for the openMINDS pre-flight form."""
    try:
        project_path_value = request.args.get("project_path") or session.get(
            "current_project_path"
        )
        resolved = _resolve_project_root_path(project_path_value)
        if resolved is None:
            return jsonify({"success": False, "error": "No active project"}), 400

        project_json = resolved / "project.json"
        if not project_json.exists():
            return jsonify({"success": True, "tasks": []})

        with open(project_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        task_names = sorted(data.get("TaskDefinitions", {}).keys())
        return jsonify({"success": True, "tasks": task_names})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def _patch_openminds_descriptions(
    output_path: Path, protocol_descriptions: dict
) -> None:
    """Post-process a bids2openminds .jsonld file to fill in behavioral protocol descriptions."""
    if not output_path.exists() or not protocol_descriptions:
        return

    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    modified = False

    def _str_val(v):
        if isinstance(v, str):
            return v
        if isinstance(v, list) and len(v) == 1 and isinstance(v[0], dict):
            return v[0].get("@value", "")
        if isinstance(v, dict):
            return v.get("@value", "")
        return ""

    def _set_val(node, key, new_val):
        old = node[key]
        if isinstance(old, list) and len(old) == 1 and isinstance(old[0], dict):
            old[0]["@value"] = new_val
        elif isinstance(old, dict):
            old["@value"] = new_val
        else:
            node[key] = new_val

    def _patch_node(node):
        nonlocal modified
        if not isinstance(node, dict):
            return

        name_val = None
        desc_key = None

        for k, v in node.items():
            k_lower = k.lower()
            if (
                k_lower in ("name",)
                or k_lower.endswith("/name")
                or k_lower.endswith(":name")
            ):
                sv = _str_val(v)
                if sv:
                    name_val = sv
            if (
                k_lower in ("description",)
                or k_lower.endswith("/description")
                or k_lower.endswith(":description")
            ):
                if _str_val(v) == "To be defined":
                    desc_key = k

        if name_val and desc_key and name_val in protocol_descriptions:
            new_desc = protocol_descriptions[name_val].strip()
            if new_desc:
                _set_val(node, desc_key, new_desc)
                modified = True

    graph = data.get("@graph", [])
    if isinstance(graph, list):
        for node in graph:
            _patch_node(node)
    else:
        _patch_node(data)

    if modified:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


@projects_export_bp.route("/api/projects/openminds-export", methods=["POST"])
def openminds_export_project():
    """
    Export the current project to openMINDS metadata format using bids2openminds.

    Expected JSON body:
    {
        "project_path": "/path/to/project",
        "single_file": true,
        "include_empty": false
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

        # Locate bids2openminds CLI (prefer same venv as current Python)
        python_bin_dir = str(Path(sys.executable).parent)
        bids2openminds_cmd = safe_path_join(python_bin_dir, "bids2openminds")
        if not Path(bids2openminds_cmd).is_file():
            # Fall back to PATH
            import shutil

            bids2openminds_cmd = shutil.which("bids2openminds")

        if not bids2openminds_cmd:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": (
                            "bids2openminds is not installed. "
                            "Install it with: pip install bids2openminds"
                        ),
                    }
                ),
                500,
            )

        # Get options
        single_file = bool(data.get("single_file", True))
        include_empty = bool(data.get("include_empty", False))
        supplements = data.get("supplements", {})

        # Determine output path
        project_name = project_path.name
        if single_file:
            output_path = project_path.parent / f"{project_name}_openminds.jsonld"
        else:
            output_path = project_path.parent / f"{project_name}_openminds"

        # Build command
        cmd = [
            bids2openminds_cmd,
            str(project_path),
            "-o",
            str(output_path),
            "--single-file" if single_file else "--multiple-files",
            "--quiet",
        ]
        if include_empty:
            cmd.append("--include-empty-properties")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            error_msg = (
                result.stderr or result.stdout or "bids2openminds conversion failed"
            ).strip()
            return jsonify({"success": False, "error": error_msg}), 500

        # Post-process: patch behavioral protocol descriptions if provided
        protocol_descriptions = supplements.get("protocol_descriptions", {})
        if protocol_descriptions and single_file and output_path.exists():
            _patch_openminds_descriptions(output_path, protocol_descriptions)

        # Write a notes file for ethics/other supplements that can't be auto-patched
        notes = {}
        ethics_category = supplements.get("ethics_category", "").strip()
        if ethics_category:
            notes["ethics_assessment"] = ethics_category
        if notes and single_file:
            notes_path = output_path.parent / (output_path.stem + "_supplements.json")
            with open(notes_path, "w", encoding="utf-8") as f:
                json.dump(notes, f, indent=2, ensure_ascii=False)

        return jsonify(
            {
                "success": True,
                "output_path": str(output_path),
                "single_file": single_file,
                "message": "openMINDS export completed successfully",
                "has_notes": bool(notes),
            }
        )

    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Export timed out (>5 min)"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
