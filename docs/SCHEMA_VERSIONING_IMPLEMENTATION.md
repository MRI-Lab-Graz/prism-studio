# Schema Versioning Implementation Summary

## What Was Implemented

Schema versioning has been successfully added to Psycho-Validator, allowing users to validate datasets against different versions of validation schemas (similar to Docker's image tagging system).

## Changes Made

### 1. Directory Structure
```
schemas/
├── stable/              # Current stable version (default)
│   ├── behavior.schema.json
│   ├── dataset_description.schema.json
│   ├── eeg.schema.json
│   ├── eyetracking.schema.json
│   ├── image.schema.json
│   ├── movie.schema.json
│   └── physiological.schema.json
├── v0.1/               # Version 0.1
│   └── (same files)
└── (legacy schema files at root - kept for backward compatibility)
```

### 2. Updated Files

#### `src/schema_manager.py`
- Added `DEFAULT_SCHEMA_VERSION = "stable"` constant
- Updated `load_schema()` to accept optional `version` parameter
- Updated `load_all_schemas()` to load schemas from version-specific directories
- Added `get_available_schema_versions()` function to list available versions
- Version normalization (supports both `0.1` and `v0.1` formats)

#### `psycho-validator.py`
- Updated `validate_dataset()` to accept `schema_version` parameter
- Added `--schema-version` command-line flag
- Added `--list-versions` command to show available schema versions
- Schema version is displayed in verbose output

#### `src/runner.py`
- Updated `validate_dataset()` to accept and pass through `schema_version` parameter
- Ensures web interface and CLI use the same validation logic

#### `web_interface.py`
- Updated `run_main_validator()` to accept `schema_version` parameter
- Updated `index()` route to load and pass available schema versions to template
- Updated `upload_dataset()` to get schema version from form data
- Updated `validate_folder()` to get schema version from form data
- Schema version is included in validation results

#### `templates/index.html`
- Added schema version dropdown selector to upload form
- Added schema version selector to local folder validation form
- Default selection is "stable"
- Shows "(default)" label for stable version

#### `templates/results.html`
- Added display of schema version used in validation results

### 3. New Documentation

#### `docs/SCHEMA_VERSIONING_GUIDE.md`
Comprehensive guide covering:
- Overview and available versions
- Command-line usage examples
- Web interface usage
- Version naming conventions
- Creating new schema versions
- Best practices
- Migration guidance
- FAQ section

## Usage Examples

### Command Line

```bash
# Default (uses stable)
python psycho-validator.py /path/to/dataset

# Specify version explicitly
python psycho-validator.py /path/to/dataset --schema-version 0.1
python psycho-validator.py /path/to/dataset --schema-version v0.1
python psycho-validator.py /path/to/dataset --schema-version stable

# List available versions
python psycho-validator.py --list-versions
```

Output:
```
Available schema versions:
  • stable (default)
  • v0.1
```

### Web Interface

1. Open the web interface (`python launch_web.py`)
2. Select schema version from dropdown menu (defaults to "stable")
3. Upload dataset or enter local folder path
4. Results page shows which schema version was used

## Key Features

### Version Flexibility
- Supports both `v0.1` and `0.1` format (automatically normalized)
- `stable` always points to recommended version
- Falls back to `stable` if no version specified

### Backward Compatibility
- Legacy schema files remain at root level for existing code
- New code uses versioned schemas
- Smooth migration path

### Consistent Behavior
- CLI and web interface use same validation logic
- Schema version tracked in all validation results
- Clear indication of version in use

### User-Friendly
- Simple dropdown in web interface
- Clear command-line flags
- Comprehensive documentation
- Helpful error messages

## Testing

All functionality has been tested:

✅ Command-line `--list-versions` flag  
✅ Command-line `--schema-version` flag with different versions  
✅ Web interface schema version selector  
✅ Schema loading from version directories  
✅ Version normalization (v0.1 vs 0.1)  
✅ Default behavior (stable)  

## Future Enhancements

Potential future improvements:

1. **Schema Validation**: Validate schema files themselves for correctness
2. **Version Comparison**: Tool to compare differences between schema versions
3. **Auto-Migration**: Automated dataset updates for schema version changes
4. **Version Metadata**: Store more detailed version info in schema files
5. **Deprecation Warnings**: Warn users when using old/deprecated versions
6. **CI/CD Integration**: Automated testing across all schema versions

## Rollout Plan

1. ✅ Implement core versioning functionality
2. ✅ Update CLI and web interface
3. ✅ Create documentation
4. ✅ Test with existing datasets
5. 🔄 User testing and feedback
6. 📝 Update main README
7. 🚀 Release as part of next version

## Notes for Users

- **Always use `stable` for production validation**
- Schema versions are stored in `schemas/` directory
- Validation reports include schema version for reproducibility
- Version selection available in both CLI and web interface
- See `docs/SCHEMA_VERSIONING_GUIDE.md` for detailed usage

## Notes for Developers

- Schema versions must be subdirectories of `schemas/`
- Version names should follow pattern: `stable`, `v0.1`, `v0.2`, etc.
- Each version directory must contain all required schema files
- Update `SCHEMA_VERSIONING_GUIDE.md` when adding new versions
- Test backward compatibility when updating schemas
