# Error Codes Reference

This document describes all validation error codes used by PRISM and how to fix them.

## PRISM Error Code System

All errors now use structured codes in the format `PRISMxxx`:

| Code Range | Category | Description |
|------------|----------|-------------|
| PRISM0xx | Dataset Structure | Dataset-level issues |
| PRISM1xx | File Naming | Filename pattern errors |
| PRISM2xx | Sidecar/Metadata | Missing or invalid sidecars |
| PRISM3xx | Schema Validation | JSON schema errors |
| PRISM4xx | Content Validation | Data content issues |
| PRISM5xx | BIDS Compatibility | BIDS-specific warnings |
| PRISM9xx | System/Plugin | Internal or plugin errors |

---

## Dataset Structure Errors (PRISM0xx)

### PRISM001 - Missing dataset_description.json

**Description:** The required `dataset_description.json` file is missing from the dataset root.

**Fix Hint:** Create a `dataset_description.json` file at the dataset root with required fields: `Name`, `BIDSVersion`

**Auto-fixable:** ✅ Yes (`--fix` creates a template)

**Example Fix:**
```json
{
  "Name": "My Dataset",
  "BIDSVersion": "1.9.0",
  "DatasetType": "raw"
}
```

---

### PRISM002 - No subjects found

**Description:** No subject directories (starting with `sub-`) were found in the dataset.

**Fix Hint:** Ensure subject folders are named `sub-<label>` and located at the dataset root.

**Auto-fixable:** ❌ No (requires data reorganization)

---

### PRISM003 - Invalid dataset_description.json

**Description:** The `dataset_description.json` file exists but contains invalid JSON or missing required fields.

**Fix Hint:** Ensure the file contains valid JSON with required BIDS fields.

---

### PRISM004 - Missing participants.tsv

**Description:** The `participants.tsv` file is missing.

**Fix Hint:** Create a `participants.tsv` file listing all subjects with at least a `participant_id` column.

---

## File Naming Errors (PRISM1xx)

### PRISM101 - Invalid filename pattern

**Description:** Filename does not follow BIDS naming conventions.

**Fix Hint:** Use BIDS naming: `sub-<label>[_ses-<label>][_task-<label>]_<suffix>.<ext>`

**Examples of Valid Filenames:**
- `sub-01_task-faces_bold.nii.gz`
- `sub-01_ses-01_task-nback_eeg.edf`
- `sub-02_task-rest_physio.tsv`

**Examples of Invalid Filenames:**
- `subject01_task-faces.nii.gz` ❌ (missing `sub-` prefix)
- `sub-01-task-faces.nii.gz` ❌ (use `_` not `-` between entities)

---

### PRISM102 - Subject ID mismatch

**Description:** The subject ID in the filename doesn't match the parent directory.

**Fix Hint:** Ensure the `sub-<label>` in the filename matches the parent directory name.

---

### PRISM103 - Session ID mismatch

**Description:** The session ID in the filename doesn't match the parent directory.

**Fix Hint:** Ensure the `ses-<label>` in the filename matches the parent directory name.

---

### PRISM104 - Invalid characters

**Description:** Filename contains invalid characters.

**Fix Hint:** Use only alphanumeric characters, hyphens, and underscores.

---

## Sidecar/Metadata Errors (PRISM2xx)

### PRISM201 - Missing sidecar

**Description:** A data file is missing its required JSON sidecar.

**Fix Hint:** Create a JSON sidecar with the same base name as the data file.

**Auto-fixable:** ✅ Yes (`--fix` creates template sidecars)

**Example:**
```
sub-01/survey/sub-01_task-bdi_survey.tsv     # Data file
sub-01/survey/sub-01_task-bdi_survey.json    # Required sidecar (auto-created by --fix)
```

---

### PRISM202 - Invalid JSON syntax

**Description:** The JSON sidecar contains syntax errors.

**Fix Hint:** Validate JSON syntax - check for missing quotes, trailing commas, etc.

---

### PRISM203 - Empty sidecar

**Description:** The JSON sidecar is empty or contains only `{}`.

**Fix Hint:** Add required metadata fields to the sidecar.

---

## Schema Validation Errors (PRISM3xx)

### PRISM301 - Missing required field

**Description:** A required field is missing from the sidecar according to the loaded PRISM schema. This includes both standard BIDS requirements and **PRISM-specific mandatory extensions** (e.g., `StimulusPresentation` for events).

**Fix Hint:** Add the missing property to the JSON sidecar. PRISM schemas often require additional metadata (like software details or hardware settings) to ensure experimental reproducibility beyond the core BIDS standard.

**Example (PRISM Extension):**
For `_events.json` files, PRISM requires the `StimulusPresentation` object:
```json
{
    "StimulusPresentation": {
        "SoftwareName": "PsychoPy",
        "SoftwareVersion": "2023.2.3"
    }
}
```

---

### PRISM302 - Invalid field type

**Description:** A field has the wrong data type (e.g., string instead of number).

**Fix Hint:** Correct the field type according to the schema.

---

### PRISM303 - Invalid field value

**Description:** A field value is outside the allowed range or not in the enum.

**Fix Hint:** Use a valid value from the schema definition.

---

## BIDS Compatibility Warnings (PRISM5xx)

### PRISM501 - .bidsignore needs update

**Description:** The `.bidsignore` file needs to be updated for PRISM compatibility.

**Fix Hint:** Add PRISM-specific directories to `.bidsignore` so standard BIDS tools ignore them.

**Auto-fixable:** ✅ Yes

---

### PRISM502 - BIDS validator warning

**Description:** The standard BIDS validator reported a warning.

**Fix Hint:** Review the BIDS validator output for details.

---

## Plugin/System Errors (PRISM9xx)

### PRISM900 - Plugin issue

**Description:** A validation issue reported by a custom plugin.

**Fix Hint:** Check the plugin-specific message for details.

---

### PRISM901 - Plugin failure

**Description:** A plugin failed to execute.

**Fix Hint:** Check plugin code for errors; ensure `validate()` function returns a list.

---

### PRISM999 - Internal error

**Description:** An unexpected internal error occurred.

**Fix Hint:** Report this issue on GitHub with full error details.

---

## Legacy Error Names

For backwards compatibility, these legacy error names map to PRISM codes:

| Legacy Name | PRISM Code |
|-------------|------------|
| INVALID_BIDS_FILENAME | PRISM101 |
| MISSING_SIDECAR | PRISM201 |
| SCHEMA_VALIDATION_ERROR | PRISM301-303 |
| INVALID_JSON | PRISM202 |
| FILENAME_PATTERN_MISMATCH | PRISM101 |

---

## Auto-Fix Support

Many issues can be automatically fixed using `--fix`:

```bash
# Preview fixes without applying
python prism.py /path/to/dataset --dry-run

# Apply fixes
python prism.py /path/to/dataset --fix

# List all fixable issues
python prism.py --list-fixes
```

**Auto-fixable issues:**
- PRISM001: Creates template `dataset_description.json`
- PRISM201: Creates template JSON sidecars
- PRISM501: Updates `.bidsignore` for PRISM compatibility

---

## Getting Help

If you're still stuck after reading this documentation:

1. Check [QUICK_START.md](QUICK_START.md) for general guidance
2. Review example datasets in `docs/examples/`
3. Open an issue on [GitHub](https://github.com/MRI-Lab-Graz/prism/issues)
4. Consult the [BIDS Specification](https://bids-specification.readthedocs.io/)
