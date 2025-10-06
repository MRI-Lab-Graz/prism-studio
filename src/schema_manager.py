"""
Schema management for psycho-validator
"""

import os
import json
import re


def parse_version(version_string):
    """Parse semantic version string to tuple of integers"""
    try:
        return tuple(map(int, version_string.split('.')))
    except:
        return (0, 0, 0)


def is_compatible_version(required_version, provided_version):
    """Check if provided version is compatible with required version"""
    req_major, req_minor, req_patch = parse_version(required_version)
    prov_major, prov_minor, prov_patch = parse_version(provided_version)
    
    # Same major version is required for compatibility
    if req_major != prov_major:
        return False
    
    # Minor version can be higher (backward compatible)
    if prov_minor < req_minor:
        return False
        
    # Patch version can be different
    return True


def load_schema(name, schema_dir="schemas"):
    """Load schema with version information"""
    schema_path = os.path.join(schema_dir, f"{name}.schema.json")
    if os.path.exists(schema_path):
        try:
            with open(schema_path) as f:
                schema = json.load(f)
            
            # Add schema metadata for versioning
            schema_version = schema.get('version', '1.0.0')
            schema['_validator_info'] = {
                'schema_version': schema_version,
                'modality': name,
                'loaded_at': json.dumps({"timestamp": "runtime"})
            }
            return schema
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load schema {schema_path}: {e}")
    return None


def load_all_schemas(schema_dir="schemas"):
    """Load all available schemas"""
    schemas = {}
    
    # Standard modalities
    modalities = [
        "image", "movie", "audio", "eyetracking", "eeg", 
        "behavior", "physiological", "dataset_description"
    ]
    
    for modality in modalities:
        schema = load_schema(modality, schema_dir)
        if schema:
            schemas[modality] = schema
            
    # MRI nested schemas (if they exist)
    mri_modalities = ["anat", "func", "fmap", "dwi"]
    for modality in mri_modalities:
        mri_schema_path = os.path.join(schema_dir, "mri", f"{modality}.schema.json")
        if os.path.exists(mri_schema_path):
            schemas[modality] = load_schema(os.path.join("mri", modality), schema_dir)
            
    return schemas


def validate_schema_version(metadata, schema):
    """Validate that metadata schema version is compatible with loaded schema"""
    issues = []
    
    if not schema or '_validator_info' not in schema:
        return issues
    
    schema_version = schema['_validator_info']['schema_version']
    
    # Check if metadata specifies a schema version
    metadata_version = None
    if 'Metadata' in metadata and 'SchemaVersion' in metadata['Metadata']:
        metadata_version = metadata['Metadata']['SchemaVersion']
    
    if metadata_version:
        if not is_compatible_version(schema_version, metadata_version):
            issues.append(("WARNING", 
                f"Schema version mismatch: metadata uses v{metadata_version}, "
                f"validator expects v{schema_version}. Consider upgrading metadata."))
    else:
        issues.append(("INFO", 
            f"No schema version specified in metadata. Using validator default v{schema_version}"))
    
    return issues