"""
BIDS Schema Loader Module

This module handles loading and caching the BIDS schema using bidsschematools.
It provides utilities to extract dataset_description field definitions.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import bidsschematools as bst

    BIDSSCHEMATOOLS_AVAILABLE = True
except ImportError:
    BIDSSCHEMATOOLS_AVAILABLE = False


class BIDSSchemaLoader:
    """Manages loading and caching of BIDS schema"""

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize schema loader.

        :param cache_dir: Directory to cache schema. Defaults to ~/.cache/bids_gui/
        """
        if cache_dir is None:
            cache_dir = str(Path.home() / ".cache" / "bids_gui")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.schema_file = self.cache_dir / "schema.json"
        self.schema: Optional[Dict[str, Any]] = None
        self.schema_version: Optional[str] = None

    def load_schema(self, force_reload: bool = False) -> Optional[Dict[str, Any]]:
        """
        Load BIDS schema from cache or remote source.

        Attempts to load from:
        1. Local cache (if available and not force_reload)
        2. Remote URL (https://bids-specification.readthedocs.io/en/latest/schema.json)
        3. Bundled bidsschematools package

        :param force_reload: Force download from remote source
        :return: Schema dictionary or None if loading fails
        """
        # Try cache first
        if not force_reload and self.schema_file.exists():
            try:
                with open(self.schema_file, "r") as f:
                    self.schema = json.load(f)
                print(f"✓ Schema loaded from cache: {self.schema_file}")
                self._extract_version()
                return self.schema
            except Exception as e:
                print(f"! Warning: Failed to load cached schema: {e}")

        # Try loading from remote URL
        if self._load_from_remote():
            return self.schema

        # Try loading from bidsschematools package
        if self._load_from_bidsschematools():
            return self.schema

        print("✗ Error: Failed to load BIDS schema from all sources")
        return None

    def _load_from_remote(self) -> bool:
        """
        Load schema from remote BIDS specification.

        :return: True if successful, False otherwise
        """
        try:
            print("Downloading BIDS schema from remote source...")
            url = "https://bids-specification.readthedocs.io/en/latest/schema.json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            self.schema = response.json()

            # Cache it
            with open(self.schema_file, "w") as f:
                json.dump(self.schema, f, indent=2)

            print(f"✓ Schema loaded from remote and cached to: {self.schema_file}")
            self._extract_version()
            return True

        except requests.exceptions.RequestException as e:
            print(f"! Warning: Failed to download schema from remote: {e}")
            return False
        except Exception as e:
            print(f"! Warning: Error processing remote schema: {e}")
            return False

    def _load_from_bidsschematools(self) -> bool:
        """
        Load schema from bundled bidsschematools package.

        :return: True if successful, False otherwise
        """
        if not BIDSSCHEMATOOLS_AVAILABLE:
            return False

        try:
            print("Loading schema from bidsschematools package...")
            schema = bst.schema.load_schema()
            # Convert Namespace to dict
            self.schema = self._namespace_to_dict(schema)

            # Cache it
            with open(self.schema_file, "w") as f:
                json.dump(self.schema, f, indent=2)

            print("✓ Schema loaded from bidsschematools and cached")
            self._extract_version()
            return True

        except Exception as e:
            print(f"! Warning: Failed to load schema from bidsschematools: {e}")
            return False

    def _namespace_to_dict(self, namespace) -> Dict[str, Any]:
        """
        Convert bidsschematools Namespace object to dictionary.

        :param namespace: Namespace object from bidsschematools
        :return: Dictionary representation
        """
        try:
            return namespace.to_dict()
        except Exception:
            # Fallback: try direct dict conversion
            return dict(namespace)

    def _extract_version(self):
        """Extract BIDS version from schema"""
        try:
            self.schema_version = self.schema.get("bids_version", "unknown")
            print(f"  BIDS Version: {self.schema_version}")
        except Exception:
            pass

    def get_dataset_description_schema(self) -> Optional[Dict[str, Any]]:
        """
        Extract dataset_description object schema from BIDS schema.
        Builds a schema from individual metadata fields that apply to dataset_description.json

        :return: Dataset description schema or None
        """
        if self.schema is None:
            return None

        try:
            # Get metadata section
            if "objects" not in self.schema:
                return None

            metadata = self.schema["objects"].get("metadata", {})

            # List of fields that belong in dataset_description.json
            dataset_description_fields = [
                "Name",
                "BIDSVersion",
                "DatasetType",
                "License",
                "Authors",
                "Acknowledgements",
                "HowToAcknowledge",
                "Funding",
                "EthicsApprovals",
                "ReferencesAndLinks",
                "DatasetDOI",
                "GeneratedBy",
                "SourceDatasets",
            ]

            # Build properties object from metadata
            properties = {}
            for field_name in dataset_description_fields:
                if field_name in metadata:
                    properties[field_name] = metadata[field_name]

            # Return schema-like object
            return {
                "type": "object",
                "properties": properties,
                "required": ["Name", "BIDSVersion"],
            }

        except Exception as e:
            print(f"! Error extracting dataset_description schema: {e}")
            return None

    def get_required_fields(self) -> list:
        """
        Get list of required fields for dataset_description.

        :return: List of required field names
        """
        ds_schema = self.get_dataset_description_schema()
        if ds_schema is None:
            # Fallback to known BIDS requirements
            return ["Name", "BIDSVersion"]

        try:
            # Check if schema has a 'required' field
            if isinstance(ds_schema, dict):
                required = ds_schema.get("required", [])
                if isinstance(required, list):
                    return required
        except Exception:
            pass

        return ["Name", "BIDSVersion"]

    def get_field_properties(self, field_name: str) -> Dict[str, Any]:
        """
        Get properties for a specific dataset_description field.

        :param field_name: Name of the field
        :return: Dictionary with field properties (type, description, enum, etc.)
        """
        ds_schema = self.get_dataset_description_schema()
        if ds_schema is None:
            return {}

        try:
            if isinstance(ds_schema, dict) and "properties" in ds_schema:
                properties = ds_schema["properties"]
                if field_name in properties:
                    return properties[field_name]
        except Exception:
            pass

        return {}

    def get_schema_for_type(self, json_type: str) -> Optional[Dict[str, Any]]:
        """
        Get schema for a specific BIDS JSON file type.

        :param json_type: 'dataset_description', 'participants', 'task-fmri', etc.
        :return: Schema for the requested type or None
        """
        if self.schema is None:
            return None

        try:
            metadata = self.schema.get("objects", {}).get("metadata", {})

            # Map json_type to relevant fields
            if json_type == "dataset_description":
                return self.get_dataset_description_schema()

            elif json_type == "participants":
                # Participants file - return None to use raw JSON editor
                # (Schema-based form doesn't work well for nested object structures)
                return None

            elif json_type.startswith("task-"):
                # Task files can have various properties like RepetitionTime, EchoTime, etc.
                task_fields = [
                    "RepetitionTime",
                    "EchoTime",
                    "FlipAngle",
                    "SliceTiming",
                    "TaskDescription",
                    "TaskName",
                ]
                properties = {}
                for field_name in task_fields:
                    if field_name in metadata:
                        properties[field_name] = metadata[field_name]

                return {
                    "type": "object",
                    "properties": properties,
                    "required": [],
                }

            elif json_type == "samples":
                # Samples file properties
                samples_fields = ["Age", "Sex", "Group", "Species"]
                properties = {}
                for field_name in samples_fields:
                    if field_name in metadata:
                        properties[field_name] = metadata[field_name]

                return {
                    "type": "object",
                    "properties": properties,
                    "required": [],
                }

            return None
        except Exception as e:
            print(f"! Error getting schema for {json_type}: {e}")
            return None


def get_default_schema_loader() -> BIDSSchemaLoader:
    """Get or create a default schema loader instance"""
    return BIDSSchemaLoader()
