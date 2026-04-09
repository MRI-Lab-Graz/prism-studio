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
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd


def _import_read_tabular_file():
    try:
        from src.converters.file_reader import read_tabular_file

        return read_tabular_file
    except ImportError:
        pass

    try:
        from src._compat import load_canonical_module

        module = load_canonical_module(
            current_file=__file__,
            canonical_rel_path="converters/file_reader.py",
            alias="prism_backend_converters_file_reader_from_participants",
        )
        imported = getattr(module, "read_tabular_file", None)
        if callable(imported):
            return imported
    except Exception:
        pass

    from converters.file_reader import read_tabular_file

    return read_tabular_file


read_tabular_file = _import_read_tabular_file()

try:
    from src.cross_platform import CrossPlatformFile
except ImportError:
    from cross_platform import CrossPlatformFile


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

    @staticmethod
    def _normalize_participant_id(value: Any) -> str | None:
        """Normalize participant IDs to BIDS format (sub-<label>)."""
        if value is None:
            return None

        text = str(value).strip()
        if not text or text.lower() == "nan":
            return None

        if text.startswith("sub-"):
            label = text[4:].strip()
        else:
            label = text

        label = label.replace(" ", "")
        if not label:
            return None

        return f"sub-{label}"

    @staticmethod
    def _find_participant_id_source_column(columns: List[str]) -> str | None:
        """Find the most likely participant ID source column from a table header."""
        if not columns:
            return None

        # Prefer exact, explicit ID columns first
        preferred_exact = [
            "participant_id",
            "prism_participant_id",
            "participantid",
            "subject_id",
            "sub_id",
            "subject",
            "sub",
            "id",
        ]
        by_lower = {str(c).strip().lower(): c for c in columns}
        for key in preferred_exact:
            if key in by_lower:
                return by_lower[key]

        # Fallback: columns that contain both "participant" and "id"
        for column in columns:
            lowered = str(column).strip().lower()
            if "participant" in lowered and "id" in lowered:
                return column

        return None

    @staticmethod
    def _collapse_to_bids_participants_table(
        output_df: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, List[str], List[str]]:
        """Return a BIDS-valid participants table with one row per participant."""
        if output_df is None or output_df.empty:
            return output_df, [], []

        def _normalize_column_name(value: Any) -> str:
            return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())

        non_bids_aliases = {
            "ses",
            "session",
            "sessionid",
            "visit",
            "timepoint",
            "run",
            "runid",
            "runnumber",
            "runnr",
            "repeat",
        }
        columns_to_drop = [
            str(col)
            for col in output_df.columns
            if str(col) != "participant_id"
            and _normalize_column_name(col) in non_bids_aliases
        ]

        collapsed_source = output_df.drop(
            columns=columns_to_drop, errors="ignore"
        ).copy()
        if "participant_id" not in collapsed_source.columns:
            return collapsed_source, columns_to_drop, []

        ordered_columns = list(collapsed_source.columns)
        collapsed_rows: List[Dict[str, Any]] = []
        conflicting_columns: set[str] = set()

        for participant_id, group in collapsed_source.groupby(
            "participant_id", sort=False, dropna=False
        ):
            collapsed_row: Dict[str, Any] = {"participant_id": participant_id}

            for column in ordered_columns:
                if column == "participant_id":
                    continue

                non_empty_values: List[Any] = []
                seen_values: set[str] = set()
                for value in group[column].tolist():
                    if pd.isna(value):
                        continue
                    if isinstance(value, str):
                        value = value.strip()
                        if not value:
                            continue
                    non_empty_values.append(value)
                    seen_values.add(str(value))

                collapsed_row[column] = (
                    non_empty_values[0] if non_empty_values else None
                )
                if len(seen_values) > 1:
                    conflicting_columns.add(str(column))

            collapsed_rows.append(collapsed_row)

        collapsed_df = pd.DataFrame(collapsed_rows, columns=ordered_columns)
        return collapsed_df, columns_to_drop, sorted(conflicting_columns)

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
        separator: str = "auto",
        sheet: str | int = 0,
    ) -> Tuple[bool, pd.DataFrame | None, List[str]]:
        """
        Convert participant data from raw format to standardized format.

        Args:
            source_file: Path to the source TSV file (e.g., wellbeing.tsv)
            mapping: The participants mapping specification
            output_file: Optional path to write converted data. If None, uses participants.tsv
            sheet: Excel sheet name or 0-based index (Excel files only)

        Returns:
            (success: bool, dataframe: pd.DataFrame | None, messages: List[str])
        """
        messages = []
        source_path = Path(source_file)

        # Load source data - handle multiple file formats
        try:
            file_ext = source_path.suffix.lower()
            kind_map = {
                ".xlsx": "xlsx",
                ".xls": "xlsx",
                ".csv": "csv",
                ".tsv": "tsv",
                ".txt": "tsv",
            }
            kind = kind_map.get(file_ext, "csv")
            separator_value = None if separator == "auto" else separator
            result = read_tabular_file(
                source_path,
                kind=kind,
                separator=separator_value,
                sheet=sheet,
            )
            df = result.df
            self._log(
                "INFO",
                f"Loaded {len(df)} rows from {source_path.name} (encoding: {result.encoding_used})",
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

                # Keep source values as-is for all participant variables.
                # Historical value recoding (e.g., 1->R) caused mismatches between
                # participants.tsv values and participants.json Levels/codebooks.
                if value_mapping:
                    self._log(
                        "INFO",
                        f"Ignoring value_mapping for '{standard_variable}' to preserve source values",
                    )
                    messages.append(
                        f"ℹ Preserved original values for '{standard_variable}' (value_mapping ignored)"
                    )

                if standard_variable == "participant_id":
                    column_data = column_data.map(self._normalize_participant_id)
                    normalized_non_null = int(column_data.notna().sum())
                    self._log(
                        "INFO",
                        f"Normalized participant IDs to BIDS format for {normalized_non_null} rows",
                    )
                    messages.append(
                        "✓ Normalized participant_id values to BIDS format (sub-<label>)"
                    )

                output_df[standard_variable] = column_data
                self._log("INFO", f"Mapped '{source_column}' → '{standard_variable}'")
                messages.append(f"✓ Mapped '{source_column}' → '{standard_variable}'")

            except Exception as e:
                self._log("ERROR", f"Failed to map '{source_column}': {e}")
                messages.append(f"✗ Failed to map '{source_column}': {e}")
                continue

        # Enforce BIDS-required participant_id column:
        # - must exist
        # - values must be normalized as sub-<label>
        # - must be the first column
        if "participant_id" in output_df.columns:
            participant_ids = output_df["participant_id"].map(
                self._normalize_participant_id
            )
        else:
            participant_ids = pd.Series(
                [None] * len(df), index=df.index, dtype="object"
            )

        # If participant_id is missing or empty, try to recover from source columns
        if participant_ids.notna().sum() == 0:
            source_id_col = self._find_participant_id_source_column(list(df.columns))
            if source_id_col:
                participant_ids = df[source_id_col].map(self._normalize_participant_id)
                recovered_count = int(participant_ids.notna().sum())
                self._log(
                    "INFO",
                    f"Recovered participant_id from source column '{source_id_col}' ({recovered_count} rows)",
                )
                messages.append(
                    f"✓ Recovered participant_id from '{source_id_col}' and normalized to sub-<label>"
                )

        # Keep only rows with valid participant IDs (cannot be represented in BIDS otherwise)
        valid_mask = participant_ids.notna()
        dropped_rows = int((~valid_mask).sum())
        if dropped_rows > 0:
            output_df = output_df.loc[valid_mask].copy()
            participant_ids = participant_ids.loc[valid_mask]
            self._log(
                "WARNING",
                f"Dropped {dropped_rows} rows without valid participant_id",
            )
            messages.append(
                f"⚠ Dropped {dropped_rows} rows without valid participant_id"
            )

        if int(participant_ids.notna().sum()) == 0:
            error_msg = (
                "Could not determine participant_id values. "
                "Provide or map an ID column (e.g., participant_id, subject_id, sub, id)."
            )
            self._log("ERROR", error_msg)
            messages.append(f"✗ {error_msg}")
            return False, None, messages

        # Insert/overwrite participant_id and reorder so it is always first
        output_df["participant_id"] = participant_ids.values
        ordered_columns = ["participant_id"] + [
            col for col in output_df.columns if col != "participant_id"
        ]
        output_df = output_df[ordered_columns]

        pre_collapse_rows = len(output_df)
        output_df, dropped_columns, conflicting_columns = (
            self._collapse_to_bids_participants_table(output_df)
        )
        if dropped_columns:
            dropped_display = ", ".join(dropped_columns)
            self._log(
                "INFO",
                f"Dropped non-BIDS participant columns: {dropped_display}",
            )
            messages.append(
                f"✓ Dropped non-BIDS participants.tsv columns: {dropped_display}"
            )

        if len(output_df) != pre_collapse_rows:
            collapsed_count = pre_collapse_rows - len(output_df)
            self._log(
                "INFO",
                f"Collapsed {collapsed_count} repeated row(s) to enforce one row per participant_id",
            )
            messages.append(
                f"✓ Collapsed repeated rows to one row per participant_id ({len(output_df)} participants)"
            )

        if conflicting_columns:
            conflict_display = ", ".join(conflicting_columns)
            self._log(
                "WARNING",
                "Multiple non-empty values found across repeated participant rows; "
                f"kept first non-empty value for: {conflict_display}",
            )
            messages.append(
                "⚠ Multiple rows per participant had differing values; kept first non-empty value for: "
                f"{conflict_display}"
            )

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
            df = read_tabular_file(source_path).df.head(10)
            self._log("INFO", f"Inspected {source_path.name} for template generation")
            messages.append(f"✓ Inspected {source_path.name}")
        except Exception as e:
            self._log("ERROR", f"Failed to read {source_path.name}: {e}")
            messages.append(f"✗ Failed to read source file: {e}")
            return False, {}, messages

        # Create template
        template: Dict[str, Any] = {
            "version": "1.0",
            "description": f"Participant mapping for {source_path.name}",
            "source_file": source_path.name,
            "instructions": {
                "participant_id": "Unique identifier for each participant (required)",
                "age": "Age in years at time of data collection",
                "sex": "Biological sex as provided in source data",
                "value_mapping": "Deprecated. Source values are preserved as-is during conversion.",
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

                # Preserve source coding for numeric participant variables.
                if pd.api.types.is_numeric_dtype(df[col]):
                    mapping_spec["note"] = (
                        "Numeric values detected - preserved as-is during conversion"
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


from src._compat import load_canonical_module

_src_participants_converter = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="participants_converter.py",
    alias="prism_backend_participants_converter",
)
for _name in dir(_src_participants_converter):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_src_participants_converter, _name)

del _name
del _src_participants_converter
