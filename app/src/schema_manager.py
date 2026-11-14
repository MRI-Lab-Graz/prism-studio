"""
Schema management for prism
"""

import os
import json
import sys
from copy import deepcopy
from pathlib import Path

# Default schema version to use when not specified
DEFAULT_SCHEMA_VERSION = "stable"


def _resolve_default_schema_dir() -> str:
    """Find `app/schemas` across dev and PyInstaller-frozen layouts.

    In dev (and the validator wheel) this file is `app/src/schema_manager.py`,
    so the schemas sit at `../schemas`. The frozen onedir build bundles them
    at `<_MEIPASS>/schemas` (`--add-data=app/schemas:schemas` in
    scripts/build/build_app.py). Never fall back to a cwd-relative "schemas":
    that only worked when run from inside app/.
    """
    candidates = [Path(__file__).resolve().parent.parent / "schemas"]
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass).resolve() / "schemas")
    for candidate in candidates:
        if candidate.is_dir():
            return str(candidate)
    return str(candidates[0])


DEFAULT_SCHEMA_DIR = _resolve_default_schema_dir()


def parse_version(version_string):
    """Parse a dotted version into exactly three integers.

    Fewer than three parts are padded with 0, more are cut. Anything that is
    not a string of dotted integers gives (0, 0, 0): version strings come from
    untrusted project files and must never raise.
    """
    try:
        parts = [int(p) for p in version_string.split(".")]
    except (AttributeError, ValueError):
        return (0, 0, 0)
    return tuple((parts + [0, 0, 0])[:3])


def is_compatible_version(required_version, provided_version):
    """Same major version; minor and patch may differ (older or newer)."""
    return parse_version(required_version)[0] == parse_version(provided_version)[0]


def _read_schema_file(schema_path, name, version_tag):
    """Load one schema file and attach the _validator_info block (None on failure)."""
    if not os.path.exists(schema_path):
        return None
    try:
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)

        # Add schema metadata for versioning
        schema_version = schema.get("version", "1.0.0")
        schema["_validator_info"] = {
            "schema_version": schema_version,
            "modality": name,
            "version_tag": version_tag,
            "loaded_at": json.dumps({"timestamp": "runtime"}),
        }
        return schema
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load schema {schema_path}: {e}")
    return None


def load_schema(name, schema_dir=DEFAULT_SCHEMA_DIR, version=None):
    """Load schema with version information

    Args:
        name: Schema name (e.g., 'image', 'eeg')
        schema_dir: Base schemas directory
        version: Schema version to load (e.g., 'stable', 'v0.1', '0.1').
                 If None, uses DEFAULT_SCHEMA_VERSION
        modality_versions: Optional {modality: 'X.Y.Z'} loaded from the stable/
                 archive instead of `version` (aliases follow the override).
    """
    # Normalize version string
    if version is None:
        version = DEFAULT_SCHEMA_VERSION
    elif version and not version.startswith("v") and version != "stable":
        version = f"v{version}"

    # Build schema path with version
    schema_path = os.path.join(schema_dir, version, f"{name}.schema.json")

    return _read_schema_file(schema_path, name, version)


def load_all_schemas(schema_dir=DEFAULT_SCHEMA_DIR, version=None, modality_versions=None):
    """Load all available schemas for a specific version

    Args:
        schema_dir: Base schemas directory
        version: Schema version to load (e.g., 'stable', 'v0.1', '0.1').
                 If None, uses DEFAULT_SCHEMA_VERSION
    """
    # Normalize version
    if version is None:
        version = DEFAULT_SCHEMA_VERSION
    elif version and not version.startswith("v") and version != "stable":
        version = f"v{version}"

    schemas = {}

    # Modality names come from the rules file, which only ships in "stable".
    entities = load_schema("entities", schema_dir, DEFAULT_SCHEMA_VERSION) or {}
    for modality in [*entities.get("modalities", {}), "dataset_description"]:
        schema = load_schema(modality, schema_dir, version)
        if schema:
            schemas[modality] = schema

    if modality_versions:
        from src.modality_versions import load_modality_schema

        for modality, modality_version in modality_versions.items():
            schemas[modality] = load_modality_schema(modality, modality_version, schema_dir)

    for alias, target in entities.get("aliases", {}).items():
        if target in schemas:
            schemas[alias] = schemas[target]

    # MRI nested schemas (if they exist)
    mri_modalities = ["anat", "func", "fmap", "dwi"]
    for modality in mri_modalities:
        mri_schema_path = os.path.join(
            schema_dir, version, "mri", f"{modality}.schema.json"
        )
        if os.path.exists(mri_schema_path):
            schemas[modality] = load_schema(
                os.path.join("mri", modality), schema_dir, version
            )

    return schemas


def get_available_schema_versions(schema_dir=DEFAULT_SCHEMA_DIR):
    """Get list of available schema versions

    Returns:
        List of version strings (e.g., ['stable', 'v0.1'])
    """
    versions = []
    if os.path.exists(schema_dir):
        for item in os.listdir(schema_dir):
            item_path = os.path.join(schema_dir, item)
            if os.path.isdir(item_path) and (item == "stable" or item.startswith("v")):
                versions.append(item)
    return sorted(versions, key=lambda x: (x != "stable", x))


def validate_schema_version(metadata, schema):
    """Validate that metadata schema version is compatible with loaded schema"""
    issues = []

    if not schema or "_validator_info" not in schema:
        return issues

    schema_version = schema["_validator_info"]["schema_version"]

    # Check if metadata specifies a schema version
    metadata_version = None
    if "Metadata" in metadata and "SchemaVersion" in metadata["Metadata"]:
        metadata_version = metadata["Metadata"]["SchemaVersion"]

    if metadata_version:
        if not is_compatible_version(schema_version, metadata_version):
            issues.append(
                (
                    "WARNING",
                    f"Schema version mismatch: metadata uses v{metadata_version}, "
                    f"validator expects v{schema_version} (different major version). "
                    "Consider upgrading metadata.",
                )
            )

    return issues


def apply_schema_validation_profile(schema, profile="project"):
    """Return schema adjusted for validation profile.

    Profiles:
    - project: relax fields listed in x-prism.officialOnlyRequired
    - official: relax fields listed in x-prism.projectOnlyRequired
    """
    if not isinstance(schema, dict) or profile not in ("project", "official"):
        return schema

    annotations = schema.get("x-prism", {})
    relax_key = (
        "officialOnlyRequired" if profile == "project" else "projectOnlyRequired"
    )
    relax_fields = annotations.get(relax_key, {})
    if not isinstance(relax_fields, dict) or not relax_fields:
        return schema

    adjusted = deepcopy(schema)
    properties = adjusted.get("properties", {})
    if not isinstance(properties, dict):
        return adjusted

    for section, keys in relax_fields.items():
        if not isinstance(keys, list):
            continue
        section_schema = properties.get(section)
        if not isinstance(section_schema, dict):
            continue
        req = section_schema.get("required")
        if not isinstance(req, list):
            continue
        section_schema["required"] = [r for r in req if r not in keys]

    return adjusted
