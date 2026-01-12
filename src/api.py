"""
REST API for prism.

Provides programmatic access to validation functionality for:
- CI/CD pipelines
- Third-party tool integration
- Automated testing workflows

API Endpoints:
    POST /api/v1/validate       - Validate a local dataset path
    GET  /api/v1/schemas        - List available schema versions
    GET  /api/v1/health         - Health check endpoint
"""

import os
import sys
from datetime import datetime
from typing import Optional
from flask import Blueprint, request, jsonify

# Ensure src is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from runner import validate_dataset
    from schema_manager import get_available_schema_versions, load_all_schemas
    from issues import tuple_to_issue, issues_to_dict, summarize_issues
except ImportError as e:
    print(f"⚠️  API import error: {e}")
    validate_dataset = None
    get_available_schema_versions = None


def create_api_blueprint(schema_dir: Optional[str] = None):
    """
    Create the API blueprint.

    Args:
        schema_dir: Path to schemas directory (defaults to ../schemas)

    Returns:
        Flask Blueprint
    """
    api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

    if schema_dir is None:
        schema_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schemas")

    @api_bp.route("/health", methods=["GET"])
    def health():
        """Health check endpoint"""
        return jsonify(
            {
                "status": "healthy",
                "service": "prism",
                "version": "1.7.0",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        )

    @api_bp.route("/schemas", methods=["GET"])
    def list_schemas():
        """List available schema versions and their modalities"""
        if not get_available_schema_versions:
            return jsonify({"error": "Schema manager not available"}), 500

        versions = get_available_schema_versions(schema_dir)

        result = {
            "default": "stable",
            "versions": {},
        }

        for version in versions:
            schemas = load_all_schemas(schema_dir, version=version)
            result["versions"][version] = {
                "modalities": list(schemas.keys()),
                "count": len(schemas),
            }

        return jsonify(result)

    @api_bp.route("/schemas/<version>", methods=["GET"])
    def get_schema_version(version):
        """Get details for a specific schema version"""
        schemas = load_all_schemas(schema_dir, version=version)

        if not schemas:
            return jsonify({"error": f"Schema version '{version}' not found"}), 404

        result = {
            "version": version,
            "modalities": {},
        }

        for name, schema in schemas.items():
            result["modalities"][name] = {
                "title": schema.get("title", name),
                "description": schema.get("description", ""),
                "schema_version": schema.get("version", "unknown"),
                "required": schema.get("required", []),
            }

        return jsonify(result)

    @api_bp.route("/validate", methods=["POST"])
    def validate():
        """
        Validate a dataset.

        Request Body (JSON):
            {
                "path": "/absolute/path/to/dataset",
                "schema_version": "stable",  // optional, defaults to "stable"
                "run_bids": false,           // optional, run BIDS validator
                "verbose": false             // optional, verbose output
            }

        Response:
            {
                "dataset": "/absolute/path/to/dataset",
                "schema_version": "stable",
                "valid": true/false,
                "summary": {
                    "total": 5,
                    "errors": 2,
                    "warnings": 3,
                    "by_code": {"PRISM001": 1, ...}
                },
                "issues": [...],
                "statistics": {
                    "total_files": 100,
                    "subjects": ["sub-01", ...],
                    ...
                }
            }
        """
        if not validate_dataset:
            return jsonify({"error": "Validator not available"}), 500

        # Parse request
        data = request.get_json()

        if not data:
            return (
                jsonify(
                    {
                        "error": "Request body must be JSON",
                        "hint": "Send a JSON object with at least a 'path' field",
                    }
                ),
                400,
            )

        dataset_path = data.get("path")

        if not dataset_path:
            return (
                jsonify(
                    {
                        "error": "Missing required field: 'path'",
                        "hint": "Provide the absolute path to your dataset",
                    }
                ),
                400,
            )

        if not os.path.isabs(dataset_path):
            return (
                jsonify(
                    {
                        "error": "Path must be absolute",
                        "hint": f"Use absolute path instead of: {dataset_path}",
                    }
                ),
                400,
            )

        if not os.path.exists(dataset_path):
            return (
                jsonify(
                    {
                        "error": f"Dataset path does not exist: {dataset_path}",
                    }
                ),
                404,
            )

        if not os.path.isdir(dataset_path):
            return (
                jsonify(
                    {
                        "error": f"Path is not a directory: {dataset_path}",
                    }
                ),
                400,
            )

        # Get options
        schema_version = data.get("schema_version", "stable")
        run_bids = data.get("run_bids", False)
        verbose = data.get("verbose", False)

        # Run validation
        try:
            issues, stats = validate_dataset(
                dataset_path,
                verbose=verbose,
                schema_version=schema_version,
                run_bids=run_bids,
            )

            # Convert to structured issues
            structured_issues = [
                tuple_to_issue(issue) if isinstance(issue, tuple) else issue
                for issue in issues
            ]

            # Build response
            result = {
                "dataset": os.path.abspath(dataset_path),
                "schema_version": schema_version,
                "valid": all(i.severity.value != "ERROR" for i in structured_issues),
                "summary": summarize_issues(structured_issues),
                "issues": issues_to_dict(structured_issues),
                "statistics": {
                    "total_files": stats.total_files,
                    "subjects": list(stats.subjects),
                    "sessions": list(stats.sessions),
                    "tasks": list(stats.tasks),
                    "modalities": dict(stats.modalities),
                    "surveys": list(getattr(stats, "surveys", set())),
                    "biometrics": list(getattr(stats, "biometrics", set())),
                },
            }

            # Use 200 for success, 422 for validation errors (still a valid API response)
            status_code = 200 if result["valid"] else 422
            return jsonify(result), status_code

        except Exception as e:
            return (
                jsonify(
                    {
                        "error": f"Validation failed: {str(e)}",
                        "type": type(e).__name__,
                    }
                ),
                500,
            )

    @api_bp.route("/validate/batch", methods=["POST"])
    def validate_batch():
        """
        Validate multiple datasets in batch.

        Request Body (JSON):
            {
                "datasets": [
                    {"path": "/path/to/dataset1"},
                    {"path": "/path/to/dataset2", "schema_version": "v0.1"}
                ],
                "schema_version": "stable",  // default for all
                "stop_on_error": false       // continue even if one fails
            }

        Response:
            {
                "results": [
                    {"dataset": "...", "valid": true, ...},
                    {"dataset": "...", "valid": false, ...}
                ],
                "summary": {
                    "total": 2,
                    "valid": 1,
                    "invalid": 1
                }
            }
        """
        if not validate_dataset:
            return jsonify({"error": "Validator not available"}), 500

        data = request.get_json()

        if not data or "datasets" not in data:
            return (
                jsonify(
                    {
                        "error": "Missing required field: 'datasets'",
                        "hint": "Provide an array of dataset objects with 'path' fields",
                    }
                ),
                400,
            )

        datasets = data.get("datasets", [])
        default_version = data.get("schema_version", "stable")
        stop_on_error = data.get("stop_on_error", False)

        results = []
        valid_count = 0
        invalid_count = 0

        for dataset_config in datasets:
            if isinstance(dataset_config, str):
                dataset_path = dataset_config
                schema_version = default_version
            else:
                dataset_path = dataset_config.get("path")
                schema_version = dataset_config.get("schema_version", default_version)

            if not dataset_path:
                results.append(
                    {
                        "error": "Missing 'path' in dataset config",
                        "valid": False,
                    }
                )
                invalid_count += 1
                continue

            if not os.path.exists(dataset_path):
                results.append(
                    {
                        "dataset": dataset_path,
                        "error": "Path does not exist",
                        "valid": False,
                    }
                )
                invalid_count += 1
                if stop_on_error:
                    break
                continue

            try:
                issues, stats = validate_dataset(
                    dataset_path,
                    verbose=False,
                    schema_version=schema_version,
                    run_bids=False,
                )

                structured_issues = [
                    tuple_to_issue(issue) if isinstance(issue, tuple) else issue
                    for issue in issues
                ]

                is_valid = all(i.severity.value != "ERROR" for i in structured_issues)

                results.append(
                    {
                        "dataset": os.path.abspath(dataset_path),
                        "schema_version": schema_version,
                        "valid": is_valid,
                        "summary": summarize_issues(structured_issues),
                    }
                )

                if is_valid:
                    valid_count += 1
                else:
                    invalid_count += 1
                    if stop_on_error:
                        break

            except Exception as e:
                results.append(
                    {
                        "dataset": dataset_path,
                        "error": str(e),
                        "valid": False,
                    }
                )
                invalid_count += 1
                if stop_on_error:
                    break

        return jsonify(
            {
                "results": results,
                "summary": {
                    "total": len(results),
                    "valid": valid_count,
                    "invalid": invalid_count,
                },
            }
        )

    return api_bp
