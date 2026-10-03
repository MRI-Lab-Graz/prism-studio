"""
JSON Validator for BIDS files
Validates JSON against BIDS schema definitions
"""


class JSONValidator:
    """Validates BIDS JSON files against schema"""

    def validate(self, json_type, data, schema):
        """
        Validate JSON data against BIDS schema
        Args:
            json_type: 'dataset_description', 'participants', 'task-fmri', etc.
            data: JSON data to validate (dict)
            schema: BIDS schema (from BIDSSchemaLoader)
        Returns:
            Tuple of (is_valid: bool, errors: list of error messages)
        """
        errors = []

        if json_type == "dataset_description":
            errors = self._validate_dataset_description(data, schema)
        elif json_type == "participants":
            errors = self._validate_participants(data, schema)
        elif json_type.startswith("task-"):
            errors = self._validate_task_definition(data, schema)
        else:
            errors = [f"Unknown JSON type: {json_type}"]

        return len(errors) == 0, errors

    def _validate_dataset_description(self, data, schema):
        """Validate dataset_description.json"""
        errors = []

        # Required fields
        required_fields = ["Name", "BIDSVersion"]
        for field in required_fields:
            if field not in data or not data[field]:
                errors.append(f"Required field missing: {field}")

        # Type validation
        if "BIDSVersion" in data:
            try:
                # Check format x.y.z
                parts = str(data["BIDSVersion"]).split(".")
                if len(parts) < 2:
                    errors.append("BIDSVersion must be in format x.y or x.y.z")
            except Exception as e:
                errors.append(f"Invalid BIDSVersion format: {str(e)}")

        # DatasetType validation
        if "DatasetType" in data:
            if data["DatasetType"] not in ["raw", "derivative"]:
                errors.append("DatasetType must be 'raw' or 'derivative'")

        # License validation (must be SPDX or custom)
        if "License" in data:
            if not data["License"]:
                errors.append("License cannot be empty")

        errors.extend(self._prism_schema_errors(data, already_reported=errors))
        return errors

    @staticmethod
    def _prism_schema_errors(data, already_reported):
        """Same PRISM schema the Validate page applies (Authors, Keywords, ...)."""
        import json
        from pathlib import Path

        from jsonschema import Draft7Validator

        schema_path = (
            Path(__file__).resolve().parents[4]
            / "schemas"
            / "stable"
            / "dataset_description.schema.json"
        )
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []  # ponytail: no schema bundled -> keep the basic checks only

        messages = []
        for error in sorted(Draft7Validator(schema).iter_errors(data), key=lambda e: list(e.path)):
            field = " -> ".join(str(part) for part in error.path)
            message = f"{field}: {error.message}" if field else error.message
            if any(name in message for name in ("'Name'", "'BIDSVersion'")) and already_reported:
                continue  # already reported as "Required field missing"
            messages.append(message)
        return messages

    def _validate_participants(self, data, schema):
        """Validate participants.json"""
        errors = []

        # BIDS participants.json is flat: one entry per participants.tsv column,
        # each describing that column.
        for col_name, col_def in data.items():
            if not isinstance(col_def, dict):
                errors.append(f"Column '{col_name}' definition must be a dictionary")
                continue
            if "Description" not in col_def:
                errors.append(f"Column '{col_name}' missing required 'Description'")

        return errors

    def _validate_task_definition(self, data, schema):
        """Validate task-*.json files"""
        errors = []

        # Task files typically have RepetitionTime as required
        if "RepetitionTime" in data:
            if not isinstance(data["RepetitionTime"], (int, float)):
                errors.append("RepetitionTime must be a number")

        return errors

    def get_validation_rules(self, json_type, schema):
        """
        Get validation rules for a JSON type from schema
        Args:
            json_type: 'dataset_description', etc.
            schema: BIDS schema
        Returns:
            Dict with field names and their validation rules
        """
        rules = {}

        if json_type == "dataset_description":
            # Extract from schema if available
            if schema and "objects" in schema:
                schema_def = (
                    schema.get("objects", {})
                    .get("metadata", {})
                    .get("dataset_description", {})
                )
                if schema_def:
                    for field_name, field_def in schema_def.items():
                        rules[field_name] = {
                            "required": field_def.get("required", False),
                            "type": field_def.get("type"),
                            "description": field_def.get("description"),
                            "enum": field_def.get("enum"),
                        }

        return rules
