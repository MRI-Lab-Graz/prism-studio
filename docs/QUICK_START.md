# Quick Start Guide - After Refactoring

This guide shows how to use the improved psycho-validator after the B, C, A refactoring.

## For End Users

### Web Interface (Recommended)

```bash
# Activate environment
source .venv/bin/activate

# Start web interface
python web_interface.py

# Or specify port
python web_interface.py --port 5000
```

Then open http://127.0.0.1:5000 in your browser.

**Features:**
- Drag and drop dataset folder
- Upload ZIP file
- Browse local folder path
- View grouped errors with short, readable paths
- Click error codes to view documentation
- Download JSON report
- BIDS-style validation results

### Command Line Interface

```bash
# Activate environment
source .venv/bin/activate

# Validate a dataset
python psycho-validator.py /path/to/dataset

# Verbose output
python psycho-validator.py /path/to/dataset --verbose
```

## For Developers

### Import and Use Validation Programmatically

```python
import sys
sys.path.insert(0, '/path/to/psycho-validator')

from src.runner import validate_dataset

# Validate a dataset
issues, stats = validate_dataset('/path/to/dataset', verbose=False)

# Check results
error_count = sum(1 for issue in issues if issue[0] == 'ERROR')
warning_count = sum(1 for issue in issues if issue[0] == 'WARNING')

print(f"Found {error_count} errors and {warning_count} warnings")
print(f"Total files: {stats.total_files}")
print(f"Subjects: {len(stats.subjects)}")
print(f"Modalities: {list(stats.modalities.keys())}")

# Process issues
for level, message in issues:
    if level == 'ERROR':
        print(f"❌ {message}")
    elif level == 'WARNING':
        print(f"⚠️  {message}")
```

### Use Individual Validators

```python
from src.validator import DatasetValidator
from src.schema_manager import load_all_schemas

# Load schemas
schemas = load_all_schemas('./schemas')

# Create validator
validator = DatasetValidator(schemas)

# Validate a filename
issues = validator.validate_filename('sub-01_task-test_bold.nii.gz', 'func')

# Validate a sidecar
issues = validator.validate_sidecar('/path/to/file.nii.gz', 'func', '/dataset/root')
```

### Use Statistics Collector

```python
from src.stats import DatasetStats

stats = DatasetStats()

# Add files manually
stats.add_file('sub-01', 'ses-01', 'func', 'nback', 'sub-01_ses-01_task-nback_bold.nii.gz')
stats.add_file('sub-01', 'ses-01', 'func', 'nback', 'sub-01_ses-01_task-nback_bold.json')

# Check consistency
warnings = stats.check_consistency()

# Access stats
print(f"Subjects: {stats.subjects}")
print(f"Sessions: {stats.sessions}")
print(f"Total files: {stats.total_files}")
print(f"Modalities: {stats.modalities}")
```

### Run Tests

```bash
# Activate environment
source .venv/bin/activate

# Run all tests
python tests/test_runner.py
python tests/test_web_formatting.py

# Or use pytest (if installed)
pytest tests/ -v
```

## Understanding Error Codes

When validation finds issues, they're grouped by error code:

### Common Error Codes

| Code | Meaning | Fix |
|------|---------|-----|
| `INVALID_BIDS_FILENAME` | Filename doesn't follow BIDS naming | Rename file to match `sub-<label>_...` pattern |
| `MISSING_SIDECAR` | JSON sidecar file not found | Create matching `.json` file |
| `SCHEMA_VALIDATION_ERROR` | JSON content doesn't match schema | Add required fields to JSON |
| `INVALID_JSON` | JSON syntax errors | Fix JSON syntax (use jsonlint) |
| `FILENAME_PATTERN_MISMATCH` | Wrong file extension for modality | Use correct extension or move to correct directory |

### Get Detailed Help

Each error code has comprehensive documentation:

**Online:** https://github.com/MRI-Lab-Graz/psycho-validator/blob/main/docs/ERROR_CODES.md

**Local:** `docs/ERROR_CODES.md`

**In Web UI:** Click the error code link in the results page

## Web Interface Features

### Upload Methods

1. **Drag & Drop Folder**
   - Works in Chrome, Edge, Opera
   - Preserves directory structure
   - Best for local datasets

2. **Upload ZIP File**
   - Works in all browsers
   - Good for remote validation
   - Automatically extracted

3. **Browse Local Path**
   - Type or paste full path
   - No upload needed
   - Fast for large datasets

### Results Page

#### Summary Cards
- **Total Files** - All files in dataset
- **Valid Files** - Files with no errors
- **Invalid Files** - Files with errors
- **Warnings** - Non-critical issues

#### Grouped Errors
Errors are grouped by type (BIDS-style):
- Shows first 5 files per error type
- "X more files" indicator for large groups
- Click error code for documentation

#### Error Details
For each error:
- **Filename** - Just the filename (not full path)
- **Path** - Abbreviated path (.../last/3/parts)
- **Message** - What's wrong
- **Documentation Link** - How to fix it

#### Actions
- **Download Report** - JSON format
- **Cleanup** - Remove temp files
- **Validate Another** - Return to upload

## File Structure After Refactoring

```
psycho-validator/
├── src/                          # Core package
│   ├── __init__.py               # Package marker
│   ├── runner.py                 # ⭐ Canonical validation entry point
│   ├── validator.py              # Filename and sidecar validation
│   ├── stats.py                  # Dataset statistics
│   ├── reporting.py              # CLI output formatting
│   ├── schema_manager.py         # Schema loading
│   └── cross_platform.py         # Windows/Mac/Linux compatibility
│
├── tests/                        # Unit tests
│   ├── test_runner.py            # ⭐ Validation tests (5 tests)
│   ├── test_web_formatting.py    # ⭐ Web UI tests (12 tests)
│   └── test_windows_compatibility.py
│
├── docs/                         # Documentation
│   ├── ERROR_CODES.md            # ⭐ Comprehensive error guide
│   ├── IMPLEMENTATION_SUMMARY.md # ⭐ B, C, A task summary
│   ├── README.md
│   ├── WEB_INTERFACE.md
│   └── WINDOWS_SETUP.md
│
├── schemas/                      # JSON schemas
│   ├── behavior.schema.json
│   ├── eeg.schema.json
│   ├── eyetracking.schema.json
│   └── ...
│
├── templates/                    # Web UI templates
│   ├── base.html
│   ├── index.html                # Upload page
│   └── results.html              # ⭐ Improved results display
│
├── psycho-validator.py           # ⭐ CLI entry (now uses src.runner)
├── web_interface.py              # ⭐ Web interface (clean imports)
├── requirements.txt
├── setup.sh / setup.bat
└── README.md
```

**Legend:**
- ⭐ = Recently modified/improved
- 📦 = New file

## Common Tasks

### Add a New Error Code

1. **Add to `web_interface.py`:**
   ```python
   def get_error_description(error_code):
       descriptions = {
           # ... existing codes ...
           'MY_NEW_ERROR': 'Description of the error'
       }
   
   def get_error_documentation_url(error_code):
       doc_anchors = {
           # ... existing codes ...
           'MY_NEW_ERROR': f"{base_url}#my_new_error"
       }
   ```

2. **Add to `docs/ERROR_CODES.md`:**
   ```markdown
   ## MY_NEW_ERROR
   
   **Description:** Clear description
   
   **Common Causes:**
   - Cause 1
   - Cause 2
   
   **How to Fix:**
   [Examples and solutions]
   ```

3. **Update `format_validation_results()` heuristic:**
   ```python
   if 'my error pattern' in message:
       error_code = 'MY_NEW_ERROR'
   ```

### Add a New Test

```python
# tests/test_runner.py or tests/test_web_formatting.py

class TestMyNewFeature:
    def test_feature_works(self):
        # Arrange
        input_data = ...
        
        # Act
        result = my_function(input_data)
        
        # Assert
        assert result == expected
```

Run with:
```bash
python tests/test_runner.py  # or pytest tests/test_runner.py
```

### Deploy Web Interface

For production deployment:

```bash
# Install production WSGI server
pip install gunicorn

# Run with gunicorn (4 workers)
gunicorn -w 4 -b 0.0.0.0:8000 web_interface:app

# Or use waitress (cross-platform)
pip install waitress
waitress-serve --host 0.0.0.0 --port 8000 web_interface:app
```

**Security notes:**
- Change `app.secret_key` in production
- Use HTTPS (reverse proxy with nginx/caddy)
- Consider authentication for multi-user deployments
- Limit upload size based on your needs

## Troubleshooting

### Import Errors

```bash
# Make sure you're in project root
cd /path/to/psycho-validator

# Make sure .venv is activated
source .venv/bin/activate  # Mac/Linux
.venv\Scripts\activate     # Windows

# Verify Python finds src package
python -c "from src.runner import validate_dataset; print('OK')"
```

### Web Interface Won't Start

```bash
# Check port is not in use
lsof -i :5000  # Mac/Linux
netstat -ano | findstr :5000  # Windows

# Try different port
python web_interface.py --port 5001
```

### Tests Fail

```bash
# Update dependencies
pip install -r requirements.txt

# Check for schema changes
ls -l schemas/*.json

# Run tests with verbose output
python tests/test_runner.py
```

## Performance Tips

### Large Datasets

```python
# Use verbose=False for faster validation
issues, stats = validate_dataset('/large/dataset', verbose=False)

# Or validate in chunks (custom code)
for subject_dir in subject_dirs:
    issues, stats = validate_subject_only(subject_dir)
```

### Web Interface

```bash
# Increase max upload size (in web_interface.py)
app.config['MAX_CONTENT_LENGTH'] = 1000 * 1024 * 1024  # 1GB

# Use ZIP for large datasets (faster upload)
# Or use local folder path (no upload needed)
```

## Getting Help

1. **Error Documentation:** `docs/ERROR_CODES.md`
2. **Implementation Details:** `docs/IMPLEMENTATION_SUMMARY.md`
3. **Web Interface Guide:** `docs/WEB_INTERFACE.md`
4. **GitHub Issues:** https://github.com/MRI-Lab-Graz/psycho-validator/issues
5. **BIDS Specification:** https://bids-specification.readthedocs.io/

## Success! 🎉

You're now ready to use the improved psycho-validator with:
- ✅ Clean importable validation functions
- ✅ Better error messages with documentation links
- ✅ Comprehensive unit tests
- ✅ Professional-grade codebase

Happy validating! 🚀
