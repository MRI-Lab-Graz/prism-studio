# Quick Start

## 1) Install (source checkout)

- macOS / Linux: follow [INSTALLATION.md](INSTALLATION.md) (uses `./setup.sh` and enforces a local `.venv`).
- Windows: follow [WINDOWS_SETUP.md](WINDOWS_SETUP.md).

## 2) Validate a dataset (CLI)

```bash
# Basic validation
python prism-validator.py /path/to/dataset

# JSON output for CI/CD
python prism-validator.py /path/to/dataset --json

# Auto-fix common issues
python prism-validator.py /path/to/dataset --fix

# Export as SARIF (GitHub Code Scanning)
python prism-validator.py /path/to/dataset --format sarif -o results.sarif
```

See [USAGE.md](USAGE.md) for all CLI options.

## 3) Run the web interface

```bash
python prism-validator-web.py
```

Open http://localhost:5001 in your browser.

## 4) Use PRISM tools

```bash
# List all commands
python prism_tools.py --help

# Build bilingual survey template
python prism_tools.py survey i18n-build library/survey/survey-phq9.json --lang en

# Initialize a plugin
python prism-validator.py --init-plugin my_validator /path/to/dataset
```

See [PRISM_TOOLS.rst](PRISM_TOOLS.rst) and [USAGE.md](USAGE.md).

## 5) Error Codes

All errors use structured PRISM codes (PRISM001-PRISM9xx). See [ERROR_CODES.md](ERROR_CODES.md) for the complete reference.
