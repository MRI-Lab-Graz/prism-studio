# PRISM Walkthrough: A Comprehensive Guide for New Users

Welcome to PRISM (Psychological Research Information Standard for Metadata). This guide will walk you through everything from installation to generating your first validated dataset and manuscript boilerplate.

This document is intentionally a **hands-on walkthrough**. For complete option-by-option documentation, see:

- [CLI_REFERENCE.md](CLI_REFERENCE.md) (all `prism.py` / `prism_tools.py` commands and flags)
- [WEB_INTERFACE.md](WEB_INTERFACE.md) (PRISM Studio web interface)
- [SPECIFICATIONS.md](SPECIFICATIONS.md) (schemas and specification, BIDS compatibility)

---

## 1. What is PRISM?

PRISM is an **independent, BIDS-compatible** framework designed to enrich standard BIDS datasets with psychological and physiological metadata.

- **BIDS-Compatible**: It doesn't replace BIDS; it extends it. Your standard BIDS tools (like fMRIPrep) will still work.
- **Independent**: You don't need to wait for official BIDS extensions to start using structured metadata for surveys and biometrics.
- **Validation-First**: It ensures your metadata is machine-readable, consistent, and reproducible.

---

## 2. Installation

### Prerequisites
- **Python 3.8+**: [Download here](https://www.python.org/downloads/)
- **Deno**: Required for the standard BIDS validator (automatically installed by our setup script).

### Quick Install

#### macOS / Linux
```bash
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio
bash scripts/setup/setup.sh
```

#### Windows
```bat
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio
scripts\setup\setup-windows.bat
```

**Note:** PRISM uses a local virtual environment (`.venv`). Always activate it before running commands:
- **macOS/Linux**: `source .venv/bin/activate`
- **Windows**: `.venv\Scripts\activate`

---

## 3. Starting the Interfaces

### Option A: Web Interface (PRISM Studio)
The web interface is the most user-friendly way to validate data and edit metadata.
```bash
python prism-studio.py
```
Then open **http://localhost:5001** in your browser.

### Option B: Desktop GUI
A native application with a modern dark theme.
```bash
python prism-gui.py
```

### Option C: Terminal (CLI)
For power users and automation.
```bash
python prism.py --help
python prism_tools.py --help
```

---

## 4. Data Preparation

PRISM focuses on two main "extensions" to BIDS: **Surveys** and **Biometrics**.

### A. Preparing a "Codebook" (Library Generation)
Before you can validate data, you need a "Golden Master" JSON template for your instrument. You can generate this from an Excel codebook.

**Excel Headers for Biometrics:**
`item_id`, `description`, `units`, `datatype`, `minvalue`, `maxvalue`, `allowedvalues`, `group`, `originalname`, `protocol`, `instructions`, `reference`, `equipment`, `supervisor`

**Excel Headers for Surveys:**
`item_id`, `question`, `scale`, `group`, `alias_of`, `session`, `run`

### B. Preparing Raw Data for Conversion
If you have a "wide" Excel file (one row per participant, columns for every question), PRISM can convert it into a BIDS-compliant structure.

---

## 5. Using the PRISM Studio Web Interface

### Validating a Dataset
1. **Drag & Drop**: Drop your entire dataset folder onto the dashboard.
2. **Real-time Results**: PRISM will scan all files. You'll see a summary chart of Errors (red) and Warnings (yellow).
3. **Fixing Issues**: Click on an error to see the file path and a description of what's wrong (e.g., "Missing sidecar JSON" or "Invalid SamplingRate").

### JSON Editor
Use the built-in editor to create or modify `.json` sidecars without leaving the browser. It provides schema-aware validation as you type.

### NeuroBagel Integration
Annotate your `participants.tsv` with standardized ontologies (like SNOMED-CT) to make your data findable in the NeuroBagel ecosystem.

---

## 6. Using the Terminal (CLI)

### Validation
```bash
# Basic validation
python prism.py /path/to/dataset

# Auto-fix common naming issues
python prism.py /path/to/dataset --fix
```

### Importing a Biometrics Codebook
```bash
python prism_tools.py biometrics import-excel \
  --excel my_codebook.xlsx \
  --output library/biometrics
```

### Generating Manuscript Methods Text
Once your data is organized, PRISM can write the "Methods" section for your paper:
```bash
python prism_tools.py library generate-methods-text \
  --output methods_en.md \
  --lang en
```

---

## 7. What the Output Looks Like

### Dataset Structure
A valid PRISM dataset looks like this:
```text
my_dataset/
├── dataset_description.json
├── participants.tsv
├── participants.json
├── sub-001/
│   ├── ses-1/
│   │   ├── survey/
│   │   │   ├── sub-001_ses-1_task-phq9_beh.tsv
│   │   │   └── sub-001_ses-1_task-phq9_beh.json
│   │   └── biometrics/
│   │       ├── sub-001_ses-1_biometrics-cmj_biometrics.tsv
│   │       └── sub-001_ses-1_biometrics-cmj_biometrics.json
```

### TSV Data Format
Survey and Biometrics data are stored as simple tab-separated values.

**Example `sub-001_ses-1_task-phq9_beh.tsv`:**
```text
item_id   response
PHQ9_1    1
PHQ9_2    0
PHQ9_3    2
```

**Example `sub-001_ses-1_biometrics-cmj_biometrics.tsv`:**
```text
JumpHeight   FlightTime   TakeoffVelocity
32.5         0.514        2.52
33.1         0.519        2.55
```

### JSON Sidecar Format
The sidecar contains the "intelligence" of your data. It defines what the columns in the TSV mean.

**Example `sub-001_ses-1_biometrics-cmj_biometrics.json`:**
```json
{
  "Technical": {
    "Type": "Biometrics",
    "Equipment": "Force Plate",
    "FileFormat": "TSV"
  },
  "Study": {
    "BiometricName": "cmj",
    "OriginalName": "Countermovement Jump",
    "Description": "Measures explosive leg power through a vertical jump."
  },
  "JumpHeight": {
    "Description": "Height of the jump in centimeters",
    "Units": "cm",
    "DataType": "float",
    "MinValue": 0,
    "MaxValue": 100
  },
  "Metadata": {
    "SchemaVersion": "1.1.0",
    "CreationDate": "2025-12-21"
  }
}
```

---

## 8. Computing Derivatives (Scores & Subscales)

Once your dataset is valid, you can automatically compute scores (e.g., PHQ-9 total score) or derived variables (e.g., best of 3 CMJ trials).

1.  **Create a Recipe**: Define your scoring logic in a JSON file under `derivatives/surveys/` or `derivatives/biometrics/`.
2.  **Run the Tool**:
    ```bash
    python prism_tools.py derivatives surveys --prism /path/to/dataset
    ```
3.  **Check Results**: PRISM creates a `derivatives/` folder in your dataset containing the computed scores and a BIDS-compliant `dataset_description.json`.

For details on recipe syntax (including mathematical formulas), see [DERIVATIVES.md](DERIVATIVES.md).

---

## 9. Summary of Tools

| Tool | Purpose |
| :--- | :--- |
| `prism.py` | The core validator. Use this to check if your dataset is "PRISM-compliant". |
| `prism_tools.py` | The "Swiss Army Knife". Use this for importing Excel, converting data, and generating text. |
| `prism-studio.py` | The Web UI. Best for interactive work and visual validation. |
| `prism-gui.py` | The Desktop App. A fast, local alternative to the web interface. |

---

Need more help? Check out the [Full Documentation](https://prism-studio.readthedocs.io/) or open an issue on GitHub!
