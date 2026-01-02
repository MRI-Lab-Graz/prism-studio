# PRISM Studio (Web Interface)

PRISM Studio (`prism-studio.py`) is the web interface for validating datasets and interactively working with metadata.

- For installation: see [INSTALLATION.md](INSTALLATION.md).
- For CLI validation and automation: see [CLI_REFERENCE.md](CLI_REFERENCE.md).

---

## 1) Start PRISM Studio

macOS / Linux:

```bash
source .venv/bin/activate
python prism-studio.py
```

Windows:

```bat
.venv\Scripts\activate
python prism-studio.py
```

Open:
- http://localhost:5001

---

## 2) Upload and validation workflow

### What you can upload
- **Folder** (recommended)
- **ZIP file**

### Large datasets (“structure-only uploads”)
PRISM Studio supports a "DataLad-style" upload strategy for large datasets:

- Metadata files (e.g., `.json`, `.tsv`) are uploaded.
- Large binaries (e.g., `.nii`, `.mp4`) may be skipped.
- The backend creates placeholders so PRISM can validate **structure**, **filenames**, and **sidecar/schema consistency** without transferring large payloads.

This is useful when you only need to validate correctness of the dataset layout and metadata.

---

## 3) Understanding the results

After validation, PRISM Studio displays:
- A summary of **Errors** (must fix) and **Warnings** (should fix)
- Per-issue details including which file is affected and why it failed

Typical errors include:
- Missing required BIDS files (e.g., `dataset_description.json`)
- Missing sidecar JSON for a TSV/recording
- Filename not matching expected patterns
- JSON fields failing schema validation

You can typically download a **JSON report** for archiving or CI workflows.

---

## 4) JSON editor

PRISM Studio includes a JSON editor that can:
- Create/edit sidecars (`*_beh.json`, `*_physio.json`, biometrics JSON sidecars)
- Validate JSON content against the selected schema version

This helps when building metadata iteratively.

---

## 5) Template Editor (Survey / Biometrics)

PRISM Studio includes a **Template Editor** to create or modify PRISM library templates (Survey or Biometrics) without editing raw JSON.

What it supports:
- **Load** a template from a library folder or create a **new** template from the selected PRISM schema version
- **Value-only editing**: keys stay fixed/locked; the UI renders fields as form controls
- **No brackets for typical fields**: arrays/levels/translations are edited via add/remove controls and language rows
- **Schema help**: hover the ⓘ icons to see descriptions and allowed values
- **Validate** against the selected schema and **download** the JSON (no server-side overwrite)

Where to find it:
- From the navbar: **Template Editor**
- Or open directly: `http://localhost:5001/template-editor`

Tips:
- Use **Add** in the left “Items (questions/metrics)” panel to add a new item ID (it becomes fixed once created).
- For translated text fields, language codes (e.g., `de`, `en`) are non-editable; only the text values are editable.

---

## 6) NeuroBagel integration (participants)

PRISM Studio provides a participants annotation workflow compatible with NeuroBagel:
- Reads `participants.tsv`
- Helps you annotate with standardized ontology terms
- Supports categorical level extraction

---

## 7) Methods Boilerplate Generator

PRISM Studio can generate a draft of a scientific **Methods section** based on the metadata in your library.

- **How it works**: It scans your `library/survey` and `library/biometrics` folders.
- **Output**: A Markdown document describing the instruments used, their authors, citations, and constructs.
- **Languages**: Supports generating text in **English** and **German**.

Access it via the **Tools** menu or at `/methods-generator`.

---

## 8) Survey Generator & Export

The Survey Export tool allows you to:
- Select items from the library.
- Preview response scales (levels), units, and value ranges.
- Export a "clean" dataset structure for data collection.
- Generate codebooks automatically.

---

## 7) Tips for first-time use

- Start with a small demo dataset: see [DEMO_DATA.md](DEMO_DATA.md).
- Validate first, then iterate on metadata fields.
- If you want strict automation, use `prism.py` in your terminal.
