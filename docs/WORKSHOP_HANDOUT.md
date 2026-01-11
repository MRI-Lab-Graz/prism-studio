# PRISM Workshop Handout: Hands-on Validation & Conversion

Welcome to the PRISM Hand-on Workshop! This document contains all the links, commands, and tasks you need for today's session.

## 1. Setup

### Repository & Environment
```bash
# Clone the repository (if you haven't)
git clone https://github.com/your-repo/psycho-validator.git
cd psycho-validator

# Activate the environment
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Launch the Web Interface
python prism-studio.py
```
Open your browser at: `http://localhost:5001` or `http://127.0.0.1:5001`

---

## 2. Hands-on Session 1: Validation & Fixing
**Folder:** `demo/workshop/messy_dataset`

Your goal is to get this dataset to pass 100% validation.

### Common Tasks
1.  **Run Validation:** Select the folder in the Dashboard and click "Validate".
2.  **Fix Filenames:** Look for files missing the `-` separator (e.g., `sub02` instead of `sub-02`).
3.  **Missing Sidecars:** Use the "Generate Sidecar" button next to `.tsv` files that lack a `.json` partner.
4.  **Schema Errors:** Check if keys like `SamplingRate` are correctly nested inside `Technical`.
5.  **Modalities:** Ensure Eye-tracking files are using the `eyetracking` schema, not `biometrics`.

---

## 3. Hands-on Session 2: Conversion & Library
**Folder:** `demo/workshop/raw_material`

Turn the raw CSV files into structured PRISM datasets.

### Workflow
1.  **Open Library:** Navigate to the "Library" or "Golden Master" section.
2.  **Map Files:** Connect `phq9_scores.csv` to the `PHQ-9` survey template.
3.  **Export:** Select `sub-01` as the target and let PRISM generate the structured folders.

---

## 4. Advanced Features
- **NeuroBagel Export:** In the validation results page, click "Export to NeuroBagel" to generate a BIDS-compliant `participants.json`.
- **Method Snippets:** Copy the auto-generated "Methods" paragraph for your paper.
- **CLI Commands:**
  ```bash
  # Fast validation via terminal
  python prism.py path/to/dataset
  ```

---

## Troubleshooting & Tips
- **Hidden Files:** If validation fails for unknown reasons, check for hidden `.DS_Store` or `Thumbs.db` files.
- **Schema Refresh:** If you edit a JSON schema file, restart the Flask server or click "Reload Schemas" in settings.
- **The "Golden Master":** Remember that your metadata should live in the `library/` for reuse across projects.

---
*Thank you for participating! Please report any bugs on GitHub.*
