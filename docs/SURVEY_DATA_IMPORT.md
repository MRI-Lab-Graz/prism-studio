# Survey Data Import Workflow

Prism-Validator provides a robust, study-agnostic workflow for converting external survey data (CSV/Excel) into a BIDS/PRISM compliant structure. This workflow ensures that your metadata ("Golden Master" Library) is consistent and that your data extraction is reproducible.

## Workflow Overview

1.  **Define Metadata**: Convert your data dictionary (Excel) into a library of JSON sidecars.
2.  **Validate Library**: Ensure variable names are unique and generate a catalog.
3.  **Import Data**: Use the library to extract data from a raw CSV and generate the dataset structure.

---

## Step 1: Create the "Golden Master" Library

Use `scripts/excel_to_library.py` to convert a study-specific Excel data dictionary into standard PRISM JSON sidecars.

**Input Excel Format:**
- **Column 1**: Variable Name (e.g., `ADS1`, `BDI_1`)
- **Column 2**: Question/Description (e.g., "I feel sad")
- **Column 3**: Scale/Levels (e.g., "1=Not at all; 2=Very much")
- **Column 4 (optional)**: Group override (e.g., `demographics`), or `disable/skip/omit/ignore` to drop the item.
- **Column 5 (optional)**: `alias_of` to mark duplicates (keeps `item_id` as the column name but annotates it as an alias of the canonical ID).
- **Column 6/7 (optional)**: `session` / `run` hints. Defaults: `ses-1` and implicit `run-1` (no run suffix unless run > 1). Use multiple rows for repeated occurrences: set `alias_of` to the canonical ID and per-row `session`/`run` to route occurrences into the right `ses-*/run-*` TSV.

**Usage:**

```bash
python scripts/excel_to_library.py --excel metadata.xlsx --output survey_library
```

This will create a folder `survey_library/` containing files like `survey-ads.json`, `survey-bdi.json`, etc. The script automatically groups variables based on their prefix (e.g., `ADS1` -> `ads`).

---

## Step 2: Validate & Document the Library

Before importing data, ensure your library is clean and well-documented.

### Check Uniqueness
Variable names must be unique across the entire library to ensure unambiguous data extraction.

```bash
python scripts/check_survey_library.py
```

### Generate Catalog
Generate a readable Markdown catalog (`CATALOG.md`) of all instruments in your library, including domains, keywords, and citations.

```bash
python scripts/catalog_survey_library.py
```

---

## Step 3: Convert Data to PRISM Structure

Use `scripts/csv_to_prism.py` to extract data from your raw CSV export and generate the BIDS/PRISM directory structure.

**How it works:**
1.  Reads all JSONs in your `survey_library`.
2.  Scans your CSV for columns matching the variables in the JSONs.
3.  Generates `sub-XX/ses-YY/survey/sub-XX_ses-YY_task-<name>_beh.tsv` files.
4.  Copies the corresponding JSON sidecar to the dataset root for BIDS inheritance.

**Usage:**

```bash
python scripts/csv_to_prism.py \
  --csv raw_data.csv \
  --library survey_library \
  --output PK01
```

**Arguments:**
- `--csv`: Path to the large CSV data file containing all participants and responses.
- `--library`: Path to the folder containing `survey-*.json` files.
- `--output`: Root directory of the output dataset (e.g., `PK01`).

---

## Best Practices

- **Golden Master**: Treat your `survey_library` as the source of truth. Do not manually edit JSONs in the dataset; edit them in the library and re-run the import.
- **Unique Names**: Ensure every variable name (e.g., `ADS1`) is unique across all questionnaires.
- **Metadata**: Add `Domain`, `Keywords`, and `Citation` to your JSONs (via the `SURVEY_METADATA` dictionary in `excel_to_library.py` or manually) to keep your catalog useful.
