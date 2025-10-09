# Schema Versioning Quick Reference

## Command Line Usage

### List Available Versions
```bash
python psycho-validator.py --list-versions
```

### Validate with Specific Version
```bash
# Using stable (default)
python psycho-validator.py /path/to/dataset

# Using version 0.1
python psycho-validator.py /path/to/dataset --schema-version 0.1
python psycho-validator.py /path/to/dataset --schema-version v0.1

# Explicitly using stable
python psycho-validator.py /path/to/dataset --schema-version stable
```

### Verbose Mode with Version
```bash
python psycho-validator.py /path/to/dataset --schema-version v0.1 --verbose
```

## Web Interface Usage

1. Start the web interface:
   ```bash
   python launch_web.py
   ```

2. Select schema version from the dropdown menu

3. Choose validation method:
   - **Upload folder/ZIP**: Select files and click "Validate Dataset"
   - **Local folder**: Enter path and click "Validate Now"

4. View results with schema version displayed

## Directory Structure

```
schemas/
├── stable/                    # Default version
│   ├── behavior.schema.json
│   ├── dataset_description.schema.json
│   ├── eeg.schema.json
│   ├── eyetracking.schema.json
│   ├── image.schema.json
│   ├── movie.schema.json
│   └── physiological.schema.json
└── v0.1/                      # Version 0.1
    └── (same structure)
```

## Best Practices

1. ✅ **Use `stable` for production** - Always use the stable version unless you have a specific reason
2. ✅ **Test with multiple versions** - When updating schemas, test against previous versions
3. ✅ **Document changes** - Keep track of what changed between versions
4. ✅ **Track version in reports** - Validation results automatically include schema version

## Version Naming

- **stable** - Current recommended version
- **v0.1, v0.2, v0.3** - Semantic versioning
- Both `0.1` and `v0.1` formats are supported

## API Usage (Python)

```python
from runner import validate_dataset

# Use stable version
issues, stats = validate_dataset('/path/to/dataset')

# Use specific version
issues, stats = validate_dataset('/path/to/dataset', schema_version='v0.1')

# Verbose mode with version
issues, stats = validate_dataset('/path/to/dataset', 
                                verbose=True, 
                                schema_version='stable')
```

## Creating New Versions

```bash
# Create new version directory
mkdir schemas/v0.2

# Copy from previous version
cp schemas/stable/*.json schemas/v0.2/

# Edit schemas as needed
# ... make your changes ...

# Test thoroughly
python psycho-validator.py test_dataset --schema-version v0.2

# When ready, promote to stable
rm -rf schemas/stable
cp -r schemas/v0.2 schemas/stable
```

## Troubleshooting

### Version not found
```
❌ Error: Schema version 'v0.5' not found
```
**Solution**: Check available versions with `--list-versions`

### No schemas loaded
```
⚠️ Warning: No schemas loaded for version 'v0.1'
```
**Solution**: Ensure version directory exists and contains all required schema files

### Default to stable
If no version is specified, the system automatically uses `stable`:
```bash
python psycho-validator.py /path/to/dataset
# Equivalent to:
python psycho-validator.py /path/to/dataset --schema-version stable
```

## Related Documentation

- [Full Guide](SCHEMA_VERSIONING_GUIDE.md) - Comprehensive documentation
- [Implementation](SCHEMA_VERSIONING_IMPLEMENTATION.md) - Technical details
- [Quick Start](QUICK_START.md) - Getting started guide
