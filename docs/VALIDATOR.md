# Validator

Validate datasets against PRISM and BIDS standards.

```{note}
This page is under construction. For now, see [Studio Overview](STUDIO_OVERVIEW.md) for validator basics.
```

## Running Validation

### In PRISM Studio

1. Go to **Validator** in the navigation
2. Your project folder is pre-selected (if a project is loaded)
3. Or browse to select a different folder
4. Click **Validate**

### Command Line

```bash
# Basic validation
python prism-validator /path/to/project

# With auto-fix
python prism-validator /path/to/project --fix

# JSON output
python prism-validator /path/to/project --json-pretty
```

## Understanding Results

### Severity Levels

| Icon | Level | Meaning | Action |
|------|-------|---------|--------|
| ❌ | **Error** | Dataset is invalid | Must fix |
| ⚠️ | **Warning** | May cause issues | Should fix |
| 💡 | **Suggestion** | Best practice | Consider fixing |

### Result Categories

- **Valid files**: Files that pass all checks (shown in green)
- **Issues**: Problems that need attention
- **Summary**: Count of errors, warnings, suggestions

## Common Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| PRISM101 | Missing sidecar JSON | Create a `.json` file with the same name |
| PRISM102 | Invalid JSON syntax | Check for missing commas, brackets |
| PRISM201 | Invalid filename | Rename to `sub-XXX_task-YYY_modality.ext` |
| PRISM202 | Missing participant ID | Add `sub-XXX` prefix to filename |
| PRISM301 | Missing required field | Add the field to your JSON sidecar |
| PRISM302 | Invalid field value | Check the value against the schema |

→ See [Error Codes Reference](ERROR_CODES.md) for the complete list.

## Auto-Fix

Some issues can be fixed automatically:

### Fixable Issues

- Missing `dataset_description.json` → Creates default file
- Missing sidecar JSON → Creates from template
- Invalid line endings → Converts to Unix format

### Using Auto-Fix

**In Studio**:
1. Click the **Fix** button next to fixable issues
2. Review proposed changes
3. Apply fixes

**Command Line**:
```bash
python prism-validator /path/to/project --fix
```

## BIDS Validation

PRISM Studio can also run the standard BIDS validator:

### In Studio

Toggle **Include BIDS Validation** before validating.

### Command Line

```bash
python prism-validator /path/to/project --bids
```

### BIDS vs PRISM

| Check | BIDS Validator | PRISM |
|-------|---------------|-------|
| MRI structure | ✅ | ✅ (delegates) |
| MRI metadata | ✅ | ✅ (delegates) |
| Survey files | ❌ | ✅ |
| Biometrics | ❌ | ✅ |
| Eyetracking | Partial | ✅ |
| Item descriptions | ❌ | ✅ |

## Validation Output Formats

### JSON

```bash
python prism-validator /path/to/project --json-pretty > results.json
```

### SARIF (for CI/CD)

```bash
python prism-validator /path/to/project --format sarif > results.sarif
```

### Markdown

```bash
python prism-validator /path/to/project --format markdown > results.md
```
