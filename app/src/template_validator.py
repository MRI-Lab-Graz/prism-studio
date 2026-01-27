"""
Template validation for survey and biometrics JSON templates in project libraries.
Validates survey/biometrics template structure, metadata completeness, and item definitions.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Tuple


class TemplateValidationError:
    """Represents a single validation issue."""

    def __init__(
        self,
        file: str,
        error_type: str,
        message: str,
        severity: str = "error",
        item: str = None,
        details: str = None,
    ):
        self.file = file
        self.error_type = error_type
        self.message = message
        self.severity = severity  # "error", "warning", "info"
        self.item = item
        self.details = details

    def __repr__(self):
        prefix = f"[{self.severity.upper()}]"
        location = f"{self.file}"
        if self.item:
            location += f" ({self.item})"
        return f"{prefix} {location}: {self.message}"


class TemplateValidator:
    """Validates survey and biometrics template JSON files."""

    IGNORE_KEYS = {
        "Technical",
        "Study",
        "Metadata",
        "Questions",
        "I18n",
        "Scoring",
        "Normative",
        "StudyMetadata",
        "LimesurveyID",
    }

    REQUIRED_STUDY_FIELDS = {
        "OriginalName": "Original name of the instrument is required",
    }

    OPTIONAL_STUDY_FIELDS = {
        "Abbreviation",
        "Authors",
        "Year",
        "DOI",
        "Citation",
        "NumberOfItems",
        "License",
        "Source",
        "Instructions",
        "ShortName",
        "Version",
        "LicenseID",
        "Publisher",
        "PublicationYear",
        "Description",
    }

    REQUIRED_ITEM_FIELDS = {
        "Description": "Item description is required",
    }

    OPTIONAL_ITEM_FIELDS = {
        "Levels",
        "Reversed",
        "Range",
        "DataType",
        "Required",
        "Instructions",
        "Aliases",
        "AliasOf",
        "Score",
    }

    def __init__(self, library_path: str):
        """Initialize validator with library path."""
        self.library_path = Path(library_path)

    def validate_directory(self, pattern: str = "*.json") -> Tuple[List[TemplateValidationError], Dict[str, Any]]:
        """
        Validate all template files in the library directory.

        Returns:
            Tuple of (error_list, summary_dict)
        """
        errors = []
        summary = {
            "total_files": 0,
            "valid_files": 0,
            "files_with_errors": 0,
            "total_errors": 0,
            "error_breakdown": {
                "json_parse": 0,
                "missing_study": 0,
                "study_validation": 0,
                "item_validation": 0,
                "i18n_validation": 0,
                "other": 0,
            },
        }

        if not self.library_path.exists():
            errors.append(
                TemplateValidationError(
                    file=str(self.library_path),
                    error_type="not_found",
                    message="Library directory does not exist",
                    severity="error",
                )
            )
            return errors, summary

        # Find all JSON files matching pattern
        template_files = sorted(self.library_path.glob(pattern))

        for file_path in template_files:
            if not file_path.is_file():
                continue

            summary["total_files"] += 1
            file_errors = self.validate_file(file_path)

            if file_errors:
                summary["files_with_errors"] += 1
                for error in file_errors:
                    summary["error_breakdown"][error.error_type] += 1
                errors.extend(file_errors)
            else:
                summary["valid_files"] += 1

        summary["total_errors"] = len(errors)
        return errors, summary

    def validate_file(self, file_path: Path) -> List[TemplateValidationError]:
        """
        Validate a single template file.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        file_name = file_path.name

        # 1. Check if file can be parsed as JSON
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(
                TemplateValidationError(
                    file=file_name,
                    error_type="json_parse",
                    message=f"Invalid JSON: {e.msg} at line {e.lineno}",
                    severity="error",
                    details=str(e),
                )
            )
            return errors
        except Exception as e:
            errors.append(
                TemplateValidationError(
                    file=file_name,
                    error_type="json_parse",
                    message=f"Failed to read file: {str(e)}",
                    severity="error",
                )
            )
            return errors

        # 2. Check if Study metadata exists
        if "Study" not in data:
            errors.append(
                TemplateValidationError(
                    file=file_name,
                    error_type="missing_study",
                    message="Missing required 'Study' section with template metadata",
                    severity="error",
                )
            )
            # Continue validating items even without Study
        else:
            # 3. Validate Study metadata
            study_errors = self._validate_study(file_name, data["Study"])
            errors.extend(study_errors)

        # 4. Validate internationalization (i18n) if present
        if "I18n" in data:
            i18n_errors = self._validate_i18n(file_name, data["I18n"])
            errors.extend(i18n_errors)

        # 5. Extract and validate items
        items = self._extract_items(data)
        if not items:
            # Only warn if there's no Study metadata either
            # (templates can be metadata-only, which is valid)
            if "Study" not in data:
                errors.append(
                    TemplateValidationError(
                        file=file_name,
                        error_type="other",
                        message="No items or Study metadata found in template",
                        severity="warning",
                    )
                )
            # else: metadata-only templates are valid
        else:
            item_errors = self._validate_items(file_name, items)
            errors.extend(item_errors)

        return errors

    def _validate_study(self, file_name: str, study_data: Any) -> List[TemplateValidationError]:
        """Validate Study metadata section."""
        errors = []

        if not isinstance(study_data, dict):
            errors.append(
                TemplateValidationError(
                    file=file_name,
                    error_type="study_validation",
                    message="'Study' must be a JSON object",
                    severity="error",
                )
            )
            return errors

        # Check required fields
        for field, error_msg in self.REQUIRED_STUDY_FIELDS.items():
            if field not in study_data or not study_data[field]:
                errors.append(
                    TemplateValidationError(
                        file=file_name,
                        error_type="study_validation",
                        message=f"Study.{field}: {error_msg}",
                        severity="error",
                    )
                )

        # Validate specific field formats
        if "Year" in study_data and study_data["Year"]:
            if not isinstance(study_data["Year"], int):
                errors.append(
                    TemplateValidationError(
                        file=file_name,
                        error_type="study_validation",
                        message="Study.Year must be an integer (e.g., 1988, 2020)",
                        severity="warning",
                    )
                )
            elif study_data["Year"] < 1900 or study_data["Year"] > 2100:
                errors.append(
                    TemplateValidationError(
                        file=file_name,
                        error_type="study_validation",
                        message=f"Study.Year seems incorrect: {study_data['Year']}",
                        severity="warning",
                    )
                )

        if "DOI" in study_data and study_data["DOI"]:
            doi = study_data["DOI"].strip()
            if doi and not (doi.startswith("10.") or doi.startswith("https://doi.org/")):
                errors.append(
                    TemplateValidationError(
                        file=file_name,
                        error_type="study_validation",
                        message="Study.DOI should start with '10.' or 'https://doi.org/'",
                        severity="warning",
                    )
                )

        if "NumberOfItems" in study_data and study_data["NumberOfItems"]:
            if not isinstance(study_data["NumberOfItems"], int):
                errors.append(
                    TemplateValidationError(
                        file=file_name,
                        error_type="study_validation",
                        message="Study.NumberOfItems must be an integer",
                        severity="warning",
                    )
                )

        # Check for translation-related fields
        if "License" in study_data:
            if isinstance(study_data["License"], dict):
                if not any(lang in study_data["License"] for lang in ["en", "de"]):
                    errors.append(
                        TemplateValidationError(
                            file=file_name,
                            error_type="i18n_validation",
                            message="Study.License (object) should have at least 'en' and 'de' keys",
                            severity="warning",
                        )
                    )

        if "OriginalName" in study_data and isinstance(study_data["OriginalName"], dict):
            if "en" not in study_data["OriginalName"]:
                errors.append(
                    TemplateValidationError(
                        file=file_name,
                        error_type="i18n_validation",
                        message="Study.OriginalName (object) must have at least 'en' key",
                        severity="error",
                    )
                )

        return errors

    def _validate_i18n(self, file_name: str, i18n_data: Any) -> List[TemplateValidationError]:
        """Validate internationalization (I18n) settings."""
        errors = []

        if not isinstance(i18n_data, dict):
            errors.append(
                TemplateValidationError(
                    file=file_name,
                    error_type="i18n_validation",
                    message="'I18n' must be a JSON object",
                    severity="warning",
                )
            )
            return errors

        # Validate Languages array
        if "Languages" in i18n_data:
            langs = i18n_data["Languages"]
            if not isinstance(langs, list):
                errors.append(
                    TemplateValidationError(
                        file=file_name,
                        error_type="i18n_validation",
                        message="I18n.Languages must be an array (e.g., ['en', 'de', 'fr'])",
                        severity="warning",
                    )
                )
            else:
                # Check language codes format
                for lang in langs:
                    if not self._is_valid_language_code(lang):
                        errors.append(
                            TemplateValidationError(
                                file=file_name,
                                error_type="i18n_validation",
                                message=f"I18n.Languages: invalid language code '{lang}' (use format like 'en', 'de', 'en-US')",
                                severity="warning",
                            )
                        )

        # Validate DefaultLanguage
        if "DefaultLanguage" in i18n_data:
            default_lang = i18n_data["DefaultLanguage"]
            if not self._is_valid_language_code(default_lang):
                errors.append(
                    TemplateValidationError(
                        file=file_name,
                        error_type="i18n_validation",
                        message=f"I18n.DefaultLanguage: invalid language code '{default_lang}'",
                        severity="warning",
                    )
                )
            # Check consistency with Languages array
            if "Languages" in i18n_data and isinstance(i18n_data["Languages"], list):
                if default_lang not in i18n_data["Languages"]:
                    errors.append(
                        TemplateValidationError(
                            file=file_name,
                            error_type="i18n_validation",
                            message=f"I18n.DefaultLanguage '{default_lang}' not in I18n.Languages list",
                            severity="warning",
                        )
                    )

        return errors

    def _extract_items(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract items from template data (handles various structures)."""
        items = {}

        # Check for Questions section first
        if "Questions" in data and isinstance(data["Questions"], dict):
            items = data["Questions"]
        else:
            # Extract all keys that are not metadata
            items = {k: v for k, v in data.items() if k not in self.IGNORE_KEYS}

        return items

    def _validate_items(self, file_name: str, items: Dict[str, Any]) -> List[TemplateValidationError]:
        """Validate item definitions."""
        errors = []

        if not items:
            return errors

        for item_id, item_def in items.items():
            # Item should be a dictionary (not a string, array, etc.)
            if not isinstance(item_def, dict):
                errors.append(
                    TemplateValidationError(
                        file=file_name,
                        error_type="item_validation",
                        message=f"Item '{item_id}' must be an object (got {type(item_def).__name__})",
                        severity="error",
                        item=item_id,
                    )
                )
                continue

            # Check required fields
            for field, error_msg in self.REQUIRED_ITEM_FIELDS.items():
                if field not in item_def or not item_def[field]:
                    errors.append(
                        TemplateValidationError(
                            file=file_name,
                            error_type="item_validation",
                            message=f"{error_msg}",
                            severity="error",
                            item=item_id,
                            details=f"Missing or empty '{field}' field",
                        )
                    )

            # Validate item structure
            item_errors = self._validate_item_structure(file_name, item_id, item_def)
            errors.extend(item_errors)

            # Validate item i18n if present
            if isinstance(item_def.get("Description"), dict):
                i18n_errors = self._validate_item_i18n(file_name, item_id, item_def)
                errors.extend(i18n_errors)

        return errors

    def _validate_item_structure(self, file_name: str, item_id: str, item_def: Dict[str, Any]) -> List[TemplateValidationError]:
        """Validate individual item structure."""
        errors = []

        # Validate Levels if present
        if "Levels" in item_def:
            if not isinstance(item_def["Levels"], dict):
                errors.append(
                    TemplateValidationError(
                        file=file_name,
                        error_type="item_validation",
                        message="Levels must be an object with numeric keys",
                        severity="error",
                        item=item_id,
                    )
                )
            else:
                # Validate level structure
                for level_key, level_def in item_def["Levels"].items():
                    if not isinstance(level_def, (str, dict)):
                        errors.append(
                            TemplateValidationError(
                                file=file_name,
                                error_type="item_validation",
                                message=f"Level '{level_key}' must be a string or object",
                                severity="error",
                                item=item_id,
                                details=f"Got {type(level_def).__name__}",
                            )
                        )

        # Validate Reversed field
        if "Reversed" in item_def and not isinstance(item_def["Reversed"], bool):
            errors.append(
                TemplateValidationError(
                    file=file_name,
                    error_type="item_validation",
                    message="'Reversed' must be a boolean (true/false)",
                    severity="warning",
                    item=item_id,
                )
            )

        # Validate Range if present
        if "Range" in item_def:
            range_data = item_def["Range"]
            if isinstance(range_data, dict):
                if not all(k in ("min", "max") for k in range_data.keys()):
                    errors.append(
                        TemplateValidationError(
                            file=file_name,
                            error_type="item_validation",
                            message="Range must have 'min' and/or 'max' keys",
                            severity="warning",
                            item=item_id,
                        )
                    )

        return errors

    def _validate_item_i18n(self, file_name: str, item_id: str, item_def: Dict[str, Any]) -> List[TemplateValidationError]:
        """Validate internationalization in item definition."""
        errors = []

        # Check Description i18n
        if isinstance(item_def.get("Description"), dict):
            desc = item_def["Description"]
            if "en" not in desc:
                errors.append(
                    TemplateValidationError(
                        file=file_name,
                        error_type="i18n_validation",
                        message="Item Description (as object) must have at least 'en' key",
                        severity="warning",
                        item=item_id,
                    )
                )

        # Check Levels i18n consistency
        if isinstance(item_def.get("Levels"), dict):
            levels = item_def["Levels"]
            level_languages = set()

            for level_def in levels.values():
                if isinstance(level_def, dict):
                    level_languages.update(level_def.keys())

            if level_languages and "en" not in level_languages:
                errors.append(
                    TemplateValidationError(
                        file=file_name,
                        error_type="i18n_validation",
                        message="Item Levels must have at least 'en' language keys",
                        severity="warning",
                        item=item_id,
                    )
                )

        return errors

    @staticmethod
    def _is_valid_language_code(code: str) -> bool:
        """Check if a string is a valid language code (e.g., 'en', 'de', 'en-US')."""
        import re

        pattern = r"^[a-z]{2}(-[A-Z]{2})?$"
        return bool(re.match(pattern, code))


def validate_templates(
    library_path: str, verbose: bool = True
) -> Tuple[List[TemplateValidationError], Dict[str, Any]]:
    """
    Convenience function to validate all templates in a library.

    Args:
        library_path: Path to the library directory
        verbose: Whether to print results to stdout

    Returns:
        Tuple of (error_list, summary_dict)
    """
    validator = TemplateValidator(library_path)
    errors, summary = validator.validate_directory()

    if verbose:
        print(f"\n{'='*70}")
        print(f"Template Validation Report: {library_path}")
        print(f"{'='*70}")
        print(
            f"Total files: {summary['total_files']} | "
            f"Valid: {summary['valid_files']} | "
            f"With errors: {summary['files_with_errors']} | "
            f"Total errors: {summary['total_errors']}"
        )

        if errors:
            print(f"\n{'-'*70}")
            print("VALIDATION ERRORS:")
            print(f"{'-'*70}")

            # Group errors by severity
            errors_by_severity = {"error": [], "warning": [], "info": []}
            for error in errors:
                errors_by_severity[error.severity].append(error)

            for severity in ["error", "warning", "info"]:
                severity_errors = errors_by_severity[severity]
                if severity_errors:
                    print(f"\n{severity.upper()}S ({len(severity_errors)}):")
                    for error in severity_errors:
                        print(f"  {error}")
                        if error.details:
                            print(f"    → {error.details}")

            print(f"\n{'-'*70}")
        else:
            print("\n✅ All templates are valid!")

        print(f"{'='*70}\n")

    return errors, summary
