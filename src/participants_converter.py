"""
Participant Data Converter

Converts raw participant data (with custom encodings) to standardized PRISM format
using a participants_mapping.json specification file.

The mapping file should be placed at the dataset root and specifies:
- Which columns in raw data are participant-relevant
- How they map to PRISM standard variables (from participants.json schema)
- Value transformations (numeric codes → standard codes)

Example participants_mapping.json:
{
  "version": "1.0",
  "description": "Mapping for wellbeing survey to PRISM standard",
  "mappings": {
    "participant_id": {
      "source_column": "participant_id",
      "standard_variable": "participant_id",
      "type": "string"
    },
    "sex": {
      "source_column": "sex",
      "standard_variable": "sex",
      "type": "string",
      "value_mapping": {
        "1": "M",
        "2": "F",
        "4": "O"
      }
    }
  }
}
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

try:
    from src.cross_platform import CrossPlatformFile
except ImportError:
    from app.src.cross_platform import CrossPlatformFile


logger = logging.getLogger(__name__)


class ParticipantsConverter:
    """Convert raw participant data to standardized PRISM format."""

    def __init__(self, dataset_path: str | Path, log_callback=None):
        """
        Initialize the converter.

        Args:
            dataset_path: Path to the dataset root
            log_callback: Optional callback function for logging messages
                         Receives (level, message) where level is 'INFO', 'WARNING', 'ERROR'
        """
        self.dataset_path = Path(dataset_path)
        self.mapping_file = self.dataset_path / "participants_mapping.json"
        self.log_callback = log_callback or (lambda level, msg: None)

    def _log(self, level: str, message: str):
        """Log a message."""
        logger.log(getattr(logging, level), message)
        self.log_callback(level, message)

    def load_mapping(self) -> Optional[Dict[str, Any]]:
        """
        Load the participants mapping specification from default location.

        Returns:
            Mapping dict if file exists, None otherwise
        """
        if not self.mapping_file.exists():
            self._log(
                "INFO", f"No participants_mapping.json found at {self.mapping_file}"
            )
            return None

        return self.load_mapping_from_file(self.mapping_file)

    def load_mapping_from_file(self, file_path: str | Path) -> Optional[Dict[str, Any]]:
        """
        Load the participants mapping specification from a specific file.

        Args:
            file_path: Path to the mapping file

        Returns:
            Mapping dict if file loads successfully, None otherwise
        """
        file_path = Path(file_path)
        if not file_path.exists():
            self._log("INFO", f"Mapping file not found: {file_path}")
            return None

        try:
            content = CrossPlatformFile.read_text(str(file_path))
            mapping = json.loads(content)
            self._log("INFO", f"Loaded participants mapping from {file_path.name}")
            return mapping
        except Exception as e:
            self._log("ERROR", f"Failed to load participants mapping: {e}")
            return None

    def validate_mapping(self, mapping: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate the mapping specification.

        Args:
            mapping: The mapping dict

        Returns:
            (is_valid, list of error messages)
        """
        errors = []

        # Check required fields
        if "version" not in mapping:
            errors.append("Missing 'version' field")
        if "mappings" not in mapping:
            errors.append("Missing 'mappings' field")
            return False, errors

        mappings = mapping.get("mappings", {})
        if not isinstance(mappings, dict):
            errors.append("'mappings' must be a dictionary")
            return False, errors

        # Validate each mapping
        for var_name, spec in mappings.items():
            if not isinstance(spec, dict):
                errors.append(
                    f"Mapping for '{var_name}' must be a dict, got {type(spec)}"
                )
                continue

            # Check required fields in each mapping
            if "source_column" not in spec:
                errors.append(f"Mapping '{var_name}' missing 'source_column'")
            if "standard_variable" not in spec:
                errors.append(f"Mapping '{var_name}' missing 'standard_variable'")

        return len(errors) == 0, errors

    def convert_participant_data(
        self,
        source_file: str | Path,
        mapping: Dict[str, Any],
        output_file: Optional[str | Path] = None,
    ) -> Tuple[bool, pd.DataFrame | None, List[str]]:
        """
        Convert participant data from raw format to standardized format.

        Args:
            source_file: Path to the source TSV file (e.g., wellbeing.tsv)
            mapping: The participants mapping specification
            output_file: Optional path to write converted data. If None, uses participants.tsv

        Returns:
            (success: bool, dataframe: pd.DataFrame | None, messages: List[str])
        """
        messages = []
        source_path = Path(source_file)

        # Load source data - handle multiple file formats
        try:
            file_ext = source_path.suffix.lower()

            if file_ext in [".xlsx", ".xls"]:
                # Excel file
                df = pd.read_excel(source_path)
                self._log(
                    "INFO", f"Loaded {len(df)} rows from Excel file {source_path.name}"
                )
                messages.append(f"✓ Loaded {len(df)} rows from {source_path.name}")
            elif file_ext == ".csv":
                # CSV file
                df = pd.read_csv(source_path)
                self._log("INFO", f"Loaded {len(df)} rows from {source_path.name}")
                messages.append(f"✓ Loaded {len(df)} rows from {source_path.name}")
            elif file_ext in [".tsv", ".txt"]:
                # TSV file
                df = pd.read_csv(source_path, sep="\t")
                self._log("INFO", f"Loaded {len(df)} rows from {source_path.name}")
                messages.append(f"✓ Loaded {len(df)} rows from {source_path.name}")
            else:
                # Try to detect separator automatically
                df = pd.read_csv(source_path, sep=None, engine="python")
                self._log(
                    "INFO",
                    f"Loaded {len(df)} rows from {source_path.name} (auto-detected format)",
                )
                messages.append(f"✓ Loaded {len(df)} rows from {source_path.name}")

        except Exception as e:
            self._log("ERROR", f"Failed to load {source_path.name}: {e}")
            messages.append(f"✗ Failed to load source file: {e}")
            return False, None, messages

        # Validate mapping
        is_valid, validation_errors = self.validate_mapping(mapping)
        if not is_valid:
            for error in validation_errors:
                self._log("ERROR", f"Mapping validation: {error}")
                messages.append(f"✗ {error}")
            return False, None, messages

        # Build output dataframe
        output_df = pd.DataFrame()
        mappings = mapping.get("mappings", {})

        for var_name, spec in mappings.items():
            source_column = spec.get("source_column")
            standard_variable = spec.get("standard_variable")
            value_mapping = spec.get("value_mapping", {})

            # Check if source column exists
            if source_column not in df.columns:
                self._log(
                    "WARNING",
                    f"Source column '{source_column}' not found in {source_path.name}",
                )
                messages.append(
                    f"⚠ Skipping '{standard_variable}': source column '{source_column}' not found"
                )
                continue

            # Extract and transform data
            try:
                column_data = df[source_column].copy()

                # Apply value mapping if specified
                if value_mapping:
                    original_count = len(column_data)
                    # Convert all values to strings for mapping
                    column_data = column_data.astype(str)
                    column_data = column_data.map(
                        lambda x: value_mapping.get(x, x) if x != "nan" else None
                    )

                    # Count unmapped values
                    unmapped = sum(
                        1 for v in column_data if v and v not in value_mapping.values()
                    )
                    if unmapped > 0:
                        self._log(
                            "WARNING",
                            f"'{standard_variable}': {unmapped}/{original_count} values not in mapping",
                        )
                        messages.append(
                            f"⚠ '{standard_variable}': {unmapped} values didn't match mapping (kept original)"
                        )

                output_df[standard_variable] = column_data
                self._log("INFO", f"Mapped '{source_column}' → '{standard_variable}'")
                messages.append(f"✓ Mapped '{source_column}' → '{standard_variable}'")

            except Exception as e:
                self._log("ERROR", f"Failed to map '{source_column}': {e}")
                messages.append(f"✗ Failed to map '{source_column}': {e}")
                continue

        # Write output
        if output_file is None:
            output_file = self.dataset_path / "participants.tsv"

        output_path = Path(output_file)

        try:
            output_df.to_csv(output_path, sep="\t", index=False)
            self._log("INFO", f"Wrote {len(output_df)} rows to {output_path.name}")
            messages.append(f"✓ Wrote participants.tsv with {len(output_df)} rows")
            return True, output_df, messages
        except Exception as e:
            self._log("ERROR", f"Failed to write {output_path.name}: {e}")
            messages.append(f"✗ Failed to write output: {e}")
            return False, output_df, messages

    def create_mapping_template(
        self, source_file: str | Path, output_file: Optional[str | Path] = None
    ) -> Tuple[bool, Dict[str, Any], List[str]]:
        """
        Create a template participants_mapping.json by inspecting a source file.

        Args:
            source_file: Path to the source TSV file
            output_file: Optional path to write the template

        Returns:
            (success: bool, template: Dict, messages: List[str])
        """
        messages = []
        source_path = Path(source_file)

        # Load source data
        try:
            df = pd.read_csv(source_path, sep="\t", nrows=10)
            self._log("INFO", f"Inspected {source_path.name} for template generation")
            messages.append(f"✓ Inspected {source_path.name}")
        except Exception as e:
            self._log("ERROR", f"Failed to read {source_path.name}: {e}")
            messages.append(f"✗ Failed to read source file: {e}")
            return False, {}, messages

        # Create template
        template = {
            "version": "1.0",
            "description": f"Participant mapping for {source_path.name}",
            "source_file": source_path.name,
            "instructions": {
                "participant_id": "Unique identifier for each participant (required)",
                "age": "Age in years at time of data collection",
                "sex": "Biological sex (use M, F, O, or n/a)",
                "value_mapping": "Map source values (e.g., 1, 2) to standard codes (e.g., M, F)",
            },
            "mappings": {},
        }

        # Detect participant-relevant columns
        participant_columns = [
            "participant_id",
            "sub_id",
            "subject_id",
            "age",
            "sex",
            "gender",
            "education",
            "education_level",
            "handedness",
            "group",
            "condition",
            "diagnosis",
        ]

        for col in df.columns:
            col_lower = col.lower()
            # Check for exact or partial matches
            if col_lower in participant_columns or any(
                pc in col_lower for pc in participant_columns
            ):
                # Get sample values
                sample_values = df[col].dropna().unique()[:5].tolist()

                mapping_spec = {
                    "source_column": col,
                    "standard_variable": col_lower,  # Suggest standardized name
                    "type": "string",
                    "sample_values": sample_values,
                }

                # If numeric, suggest value_mapping
                if pd.api.types.is_numeric_dtype(df[col]):
                    mapping_spec["note"] = (
                        "Numeric values detected - add 'value_mapping' if needed"
                    )

                template["mappings"][col] = mapping_spec

        # Write template if requested
        if output_file:
            output_path = Path(output_file)
            try:
                content = json.dumps(template, indent=2)
                CrossPlatformFile.write_text(str(output_path), content)
                self._log("INFO", f"Wrote mapping template to {output_path.name}")
                messages.append(f"✓ Created template at {output_path.name}")
            except Exception as e:
                self._log("ERROR", f"Failed to write template: {e}")
                messages.append(f"✗ Failed to write template: {e}")
                return False, template, messages

        return True, template, messages


def apply_participants_mapping(
    dataset_path: str | Path, source_file: str | Path, log_callback=None
) -> Tuple[bool, List[str]]:
    """
    High-level function to auto-detect and apply participants mapping.

    This is what gets called during dataset validation/conversion.

    Args:
        dataset_path: Path to dataset root
        source_file: Path to the raw participant data file (e.g., wellbeing.tsv)
        log_callback: Optional logging callback

    Returns:
        (success: bool, messages: List[str])
    """
    converter = ParticipantsConverter(dataset_path, log_callback)
    mapping = converter.load_mapping()

    if mapping is None:
        return True, ["No participants_mapping.json found - skipping conversion"]

    success, _, messages = converter.convert_participant_data(source_file, mapping)
    return success, messages
