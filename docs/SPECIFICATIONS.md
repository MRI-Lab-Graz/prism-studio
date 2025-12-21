# Specifications and Schemas (PRISM vs BIDS)

This page explains PRISM’s **specification layer**: how schemas work, where they live, and how they relate to standard BIDS.

PRISM is an add-on to BIDS:
- PRISM **does not replace** BIDS.
- BIDS standards should not be changed in PRISM.
- PRISM adds additional schemas (e.g., Survey, Biometrics) that are not fully standardized in BIDS yet.
- A key design goal is that standard BIDS tools/apps still work on PRISM datasets.

---

## 1) Conceptual model

### BIDS (core)
BIDS defines:
- dataset structure conventions
- filename conventions and entities (`sub-`, `ses-`, `task-`, etc.)
- standard metadata files (e.g., `dataset_description.json`, `participants.tsv`)

### PRISM (extensions)
PRISM adds:
- additional modality-specific schemas
- stricter sidecar requirements for certain data types
- optional internationalization (i18n) support for variable-level descriptions

---

## 2) Schema versions

PRISM schemas are versioned under the repository folder:
- `schemas/stable/` (default)
- `schemas/vX.Y/` (historical / pinned versions)

You can:

```bash
python prism.py --list-versions
python prism.py /path/to/dataset --schema-version stable
```

For details, see:
- [SCHEMA_VERSIONING.md](SCHEMA_VERSIONING.md)
- [SCHEMA_VERSIONING_GUIDE.md](SCHEMA_VERSIONING_GUIDE.md)

---

## 3) Files PRISM expects in a dataset

At minimum (BIDS core):
- `dataset_description.json` (required)
- `participants.tsv` (commonly required in practice)

For PRISM extensions, typical additions are:
- per-subject survey TSVs under `sub-*/ses-*/survey/`
- per-subject biometrics TSVs under `sub-*/ses-*/biometrics/`
- JSON sidecars for each data file (PRISM requires sidecars for non-JSON data files it validates)

---

## 4) Filename conventions (high-level)

PRISM follows BIDS-like entity conventions. Examples:

Survey TSV:
- `sub-001_ses-1_task-ads_beh.tsv`

Biometrics TSV:
- `sub-001_ses-1_biometrics-cmj_biometrics.tsv`

Each data file should have a corresponding JSON sidecar with the same stem.

---

## 5) What is inside a PRISM schema?

PRISM uses JSON Schema documents to define:
- required top-level blocks (commonly `Technical`, `Study`, `Metadata`)
- required fields and allowed types
- optional blocks like `I18n`

Schemas live in `schemas/<version>/`.

Example (Biometrics schema path):
- `schemas/stable/biometrics.schema.json`

---

## 6) Internationalization (i18n)

Some PRISM templates support bilingual/multilingual text fields (e.g., English + German). Depending on the schema, a descriptive field may be either:
- a plain string, or
- a language map like:

```json
{
  "en": "Measures explosive leg power.",
  "de": "Misst die explosive Beinkraft."
}
```

This is especially useful for:
- `Study.Description`
- variable-level `Description`

---

## 7) Detailed modality specifications

PRISM’s modality-specific specifications are documented under `docs/specs/`.

Start here:
- [Biometrics specification](specs/biometrics)
- [Survey specification](specs/survey)
- [Events specification](specs/events)

(These pages are intended to play the same role as BIDS specification pages: they describe the expected files, naming, and metadata semantics.)
