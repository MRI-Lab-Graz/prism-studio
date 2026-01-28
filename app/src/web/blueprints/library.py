from flask import Blueprint, render_template, jsonify, request, current_app

library_bp = Blueprint("library", __name__)


@library_bp.route("/library")
def library_view():
    """View the survey library management page"""
    survey_manager = current_app.config.get("SURVEY_MANAGER")
    if not survey_manager:
        return "Survey Manager not initialized", 500

    surveys = survey_manager.list_surveys()
    return render_template("library.html", surveys=surveys)


@library_bp.route("/library/edit/<filename>")
def edit_survey(filename):
    """Edit a survey draft"""
    survey_manager = current_app.config.get("SURVEY_MANAGER")
    if not survey_manager:
        return "Survey Manager not initialized", 500

    try:
        content = survey_manager.get_draft_content(filename)
        return render_template(
            "library_editor.html", filename=filename, content=content
        )
    except FileNotFoundError:
        return "Draft not found", 404
    except Exception as e:
        return str(e), 500


@library_bp.route("/library/api/draft/<filename>", methods=["POST"])
def create_draft(filename):
    """Create a new draft from master"""
    survey_manager = current_app.config.get("SURVEY_MANAGER")
    if not survey_manager:
        return jsonify({"error": "Survey Manager not initialized"}), 500

    try:
        survey_manager.create_draft(filename)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@library_bp.route("/library/api/draft/<filename>", methods=["DELETE"])
def discard_draft(filename):
    """Discard a draft"""
    survey_manager = current_app.config.get("SURVEY_MANAGER")
    if not survey_manager:
        return jsonify({"error": "Survey Manager not initialized"}), 500

    try:
        survey_manager.discard_draft(filename)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@library_bp.route("/library/api/save/<filename>", methods=["POST"])
def save_draft(filename):
    """Save content to draft"""
    survey_manager = current_app.config.get("SURVEY_MANAGER")
    if not survey_manager:
        return jsonify({"error": "Survey Manager not initialized"}), 500

    try:
        content = request.json
        survey_manager.save_draft(filename, content)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@library_bp.route("/library/api/publish/<filename>", methods=["POST"])
def publish_draft(filename):
    """Submit draft as merge request"""
    survey_manager = current_app.config.get("SURVEY_MANAGER")
    if not survey_manager:
        return jsonify({"error": "Survey Manager not initialized"}), 500

    try:
        survey_manager.publish_draft(filename)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
