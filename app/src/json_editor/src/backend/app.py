"""
Flask application for BIDS JSON Editor
Serves HTML interface and provides API endpoints for schema-driven form generation,
file loading/saving, and JSON validation.
"""

from pathlib import Path
from flask import Flask, render_template, request, jsonify
from .file_manager import FileManager
from .json_validator import JSONValidator
from ..schema_loader import BIDSSchemaLoader


def create_app(bids_folder=None):
    """Create and configure Flask app"""
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent.parent / "frontend"),
        static_folder=str(Path(__file__).parent.parent / "frontend"),
    )

    # Initialize managers
    file_manager = FileManager(bids_folder)
    validator = JSONValidator()
    schema_loader = BIDSSchemaLoader()

    # Load schema on startup
    schema = schema_loader.load_schema()
    app.schema = schema

    # ==================== API ENDPOINTS ====================

    @app.route("/")
    def index():
        """Serve main HTML page"""
        return render_template("index.html")

    @app.route("/api/schema/<json_type>", methods=["GET"])
    def get_schema(json_type):
        """
        Get schema for specific BIDS JSON type
        Args:
            json_type: 'dataset_description', 'participants', 'task', etc.
        Returns:
            JSON schema for the requested type
        """
        try:
            schema_def = schema_loader.get_schema_for_type(json_type)
            return jsonify({"success": True, "schema": schema_def})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/api/files", methods=["GET"])
    def list_files():
        """
        List available BIDS JSON files in the loaded folder
        Returns:
            List of file types available (dataset_description, participants, etc.)
        """
        try:
            files = file_manager.list_available_files()
            return jsonify({"success": True, "files": files})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/api/file/<json_type>", methods=["GET"])
    def load_file(json_type):
        """
        Load a BIDS JSON file
        Args:
            json_type: 'dataset_description', 'participants', etc.
        Returns:
            JSON content of the file
        """
        try:
            data = file_manager.load_file(json_type)
            return jsonify({"success": True, "data": data})
        except FileNotFoundError as e:
            return jsonify({"success": False, "error": str(e)}), 404
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/api/file/<json_type>", methods=["POST"])
    def save_file(json_type):
        """
        Save a BIDS JSON file
        Args:
            json_type: 'dataset_description', 'participants', etc.
            Request body: JSON data to save
        Returns:
            Success status
        """
        try:
            data = request.get_json()

            # Validate before saving
            is_valid, errors = validator.validate(json_type, data, app.schema)
            if not is_valid:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Validation failed",
                            "errors": errors,
                        }
                    ),
                    400,
                )

            file_manager.save_file(json_type, data)
            return jsonify(
                {"success": True, "message": f"{json_type} saved successfully"}
            )
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/api/validate/<json_type>", methods=["POST"])
    def validate_json(json_type):
        """
        Validate JSON against BIDS schema
        Args:
            json_type: 'dataset_description', 'participants', etc.
            Request body: JSON data to validate
        Returns:
            Validation result with errors if any
        """
        try:
            data = request.get_json()
            is_valid, errors = validator.validate(json_type, data, app.schema)

            return jsonify({"success": True, "valid": is_valid, "errors": errors})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/api/bids-folder", methods=["GET"])
    def get_bids_folder():
        """Get current BIDS folder path"""
        folder_path = (
            str(file_manager.bids_folder)
            if file_manager.bids_folder
            else "No folder loaded"
        )
        return jsonify({"success": True, "folder": folder_path})

    @app.route("/api/bids-folder", methods=["POST"])
    def set_bids_folder():
        """Set BIDS folder path"""
        try:
            data = request.get_json()
            folder = data.get("folder")
            if not folder:
                return jsonify({"success": False, "error": "Folder path required"}), 400

            file_manager.set_bids_folder(folder)
            return jsonify({"success": True, "message": f"BIDS folder set to {folder}"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=False, port=5000)
