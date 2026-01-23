# Usage Guide

PRISM offers two ways to validate your data: a user-friendly **Web Interface** and a powerful **Command Line Interface (CLI)**.

## 🖥️ Web Interface (Recommended)

The web interface is the easiest way to validate your data. It provides a visual dashboard, drag-and-drop support, and detailed error reports.

### Starting the Web Interface

1.  **Open your terminal/command prompt.**
2.  **Navigate to the prism folder.**
3.  **Run the start command:**

    **macOS / Linux:**
    ```bash
    source .venv/bin/activate
    python prism-studio.py
    ```

    **Windows:**
    ```bat
    .venv\Scripts\activate
    python prism-studio.py
    ```

4.  **Open your browser** and go to `http://127.0.0.1:5001`.

### Validating Data

1.  **Select Schema Version**: Choose between `stable` (recommended) or specific versions like `v0.1`.
2.  **Upload Data**:
    *   **Drag & Drop**: Drag your dataset folder directly onto the drop zone.
    *   **Select Folder**: Click to browse for a local folder.
    *   **Upload ZIP**: Upload a compressed `.zip` file of your dataset.
3.  **View Results**:
    *   The dashboard will show a summary of **Errors** (must fix) and **Warnings** (should fix).
    *   Click on any error to see exactly which file is affected and how to fix it.
4.  **Download Report**: You can download a full JSON report of the validation results.

Notes
-----

- **Structure-only uploads**: For large datasets, the Web UI may upload only metadata (e.g., `.json`, `.tsv`) and create placeholders for large binaries. In this mode, the validator checks dataset structure, filenames, and sidecar/schema consistency without transferring large imaging/stimulus files.
- **Dataset description**: `dataset_description.json` is required and validated against the selected schema version.
- **BIDS compatibility**: When validating, the tool may update `.bidsignore` to hide PRISM-only folders from standard BIDS tools/apps.

---

## ⌨️ Command Line Interface (CLI)

For advanced users or batch processing, the CLI allows you to run validations directly from the terminal.

### Basic Usage

```bash
python prism.py /path/to/your/dataset
```

### Options

| Flag | Description | Example |
|------|-------------|---------|
| `--schema-version` | Specify which schema version to use (default: `stable`). | `python prism.py /data --schema-version v0.1` |
| `-v`, `--verbose` | Show detailed progress and file scanning info. | `python prism.py /data -v` |
| `--json` | Output results as JSON (compact). | `python prism.py /data --json` |
| `--json-pretty` | Output results as formatted JSON. | `python prism.py /data --json-pretty` |
| `--format` | Output format: json, sarif, junit, markdown, csv. | `python prism.py /data --format sarif` |
| `-o`, `--output` | Write output to file instead of stdout. | `python prism.py /data --format junit -o report.xml` |
| `--fix` | Automatically fix common issues. | `python prism.py /data --fix` |
| `--dry-run` | Preview what --fix would do without making changes. | `python prism.py /data --dry-run` |
| `--list-fixes` | List all auto-fixable issue types. | `python prism.py --list-fixes` |
| `--init-plugin` | Generate a plugin template in validators/. | `python prism.py /data --init-plugin custom` |
| `--list-plugins` | List loaded plugins for the dataset. | `python prism.py /data --list-plugins` |
| `--no-plugins` | Disable plugin loading. | `python prism.py /data --no-plugins` |
| `--bids` | Run the standard BIDS validator in addition to PRISM validation. | `python prism.py /data --bids` |
| `--bids-warnings` | Show warnings from the BIDS validator (default: hidden). | `python prism.py /data --bids --bids-warnings` |
| `--list-versions` | Show all available schema versions. | `python prism.py --list-versions` |

### Example Output

```text
🔍 Validating dataset: /data/study-01

============================================================
🗂️  DATASET SUMMARY
============================================================
👥 Subjects: 15
🎯 MODALITIES:
  ✅ survey: 15 files
  ✅ biometrics: 15 files

============================================================
✅ VALIDATION RESULTS
============================================================
🎉 No issues found! Dataset is valid.
```

---

## 🔧 Auto-Fix Mode

PRISM can automatically fix common issues in your dataset.

### Preview Fixes (Dry Run)

```bash
python prism.py /path/to/dataset --dry-run
```

Output:
```
🔧 Found 3 fixable issue(s):
==============================================================
  1. [PRISM001] Missing dataset_description.json
     Action: create → dataset_description.json
  2. [PRISM201] Missing sidecar for sub-01/survey/sub-01_task-bdi_survey.tsv
     Action: create → sub-01_task-bdi_survey.json
  3. [PRISM501] .bidsignore needs update for PRISM compatibility
     Action: update → .bidsignore
==============================================================
🔍 Dry run - no changes made.
   Run with --fix to apply these changes.
```

### Apply Fixes

```bash
python prism.py /path/to/dataset --fix
```

### List Fixable Issues

```bash
python prism.py --list-fixes
```

---

## 📄 Output Formats

### JSON Output (for CI/CD)

```bash
# Compact JSON
python prism.py /data --json

# Pretty-printed JSON
python prism.py /data --json-pretty
```

### SARIF (GitHub/GitLab Code Scanning)

```bash
python prism.py /data --format sarif -o report.sarif
```

Upload to GitHub Actions or GitLab SAST for inline annotations.

### JUnit XML (CI Test Results)

```bash
python prism.py /data --format junit -o junit-results.xml
```

Compatible with Jenkins, GitLab CI, GitHub Actions test reporting.

### Markdown Report

```bash
python prism.py /data --format markdown -o report.md
```

Generates a human-readable report with validation badge.

### CSV Export

```bash
python prism.py /data --format csv -o issues.csv
```

Simple spreadsheet-compatible export of all issues.

---

## 🔌 Plugin System

Extend validation with custom checks by creating plugins.

### Create a Plugin

```bash
python prism.py /path/to/dataset --init-plugin my_custom_checks
```

This creates `<dataset>/validators/my_custom_checks.py` with a template.

### Plugin Structure

```python
# validators/my_custom_checks.py
PLUGIN_NAME = "my_custom_checks"
PLUGIN_DESCRIPTION = "Custom validation rules"
PLUGIN_VERSION = "1.0.0"

def validate(dataset_path: str, context: dict) -> list:
    """
    Returns list of issues as tuples: (severity, message, [file_path])
    severity: "ERROR", "WARNING", or "INFO"
    """
    issues = []
    
    # Your custom validation logic here
    if not os.path.exists(os.path.join(dataset_path, "README.md")):
        issues.append(("WARNING", "Dataset should include a README file"))
    
    return issues
```

### List Loaded Plugins

```bash
python prism.py /path/to/dataset --list-plugins
```

### Disable Plugins

```bash
python prism.py /path/to/dataset --no-plugins
```

---

## 📋 Project Configuration

Create a `.prismrc.json` file in your dataset root:

```json
{
  "schema_version": "stable",
  "strict_mode": false,
  "run_bids": false,
  "ignore_paths": ["sourcedata/", "derivatives/", "code/"],
  "plugins": ["./validators/custom_checks.py"]
}
```

| Setting | Type | Description |
|---------|------|-------------|
| `schema_version` | string | Schema version to use (default: "stable") |
| `strict_mode` | boolean | Treat warnings as errors |
| `run_bids` | boolean | Run BIDS validator in addition to PRISM |
| `ignore_paths` | array | Paths to skip during validation |
| `plugins` | array | Additional plugin paths to load |

CLI arguments override config file settings.

---

## 🌐 REST API

PRISM includes a REST API for programmatic access.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/schemas` | List available schemas |
| POST | `/api/v1/validate` | Validate a dataset path |

### Example: Validate via API

```bash
curl -X POST http://localhost:5001/api/v1/validate \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/dataset"}'
```

Response:
```json
{
  "valid": false,
  "summary": {"errors": 1, "warnings": 2, "info": 0},
  "issues": [...],
  "statistics": {...}
}
```
