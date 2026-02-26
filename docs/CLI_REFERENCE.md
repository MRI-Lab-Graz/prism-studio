# CLI & Script Reference

This page is the **detailed reference** for PRISM’s command-line tools and scripts.

- For a first-time, step-by-step narrative: see [QUICK_START.md](QUICK_START.md).
- For specification / schema details: see [SPECIFICATIONS.md](SPECIFICATIONS.md).
- For derivative scoring recipes: see [RECIPES.md](RECIPES.md).

---

## 0) Environment requirement (`.venv`)

Both `prism.py` and `prism_tools.py` **enforce** running from the repo-local virtual environment at `./.venv`.

macOS / Linux:

```bash
source .venv/bin/activate
```

Windows:

```bat
.venv\Scripts\activate
```

If you see:

```text
❌ Error: You are not running inside the prism virtual environment!
```

activate the environment and retry.

---

## 1) `prism.py` — the dataset validator

### Purpose
- Validate a dataset against **BIDS rules** (optional) and **PRISM schemas**.
- Produce machine-readable reports (JSON, SARIF, JUnit, Markdown, CSV).
- Optionally apply safe auto-fixes (`--fix`).

### Usage

```bash
python prism.py /path/to/dataset
```

### Options (complete)

| Option | Meaning |
|---|---|
| `-v`, `--verbose` | Print detailed progress / scanning info. |
| `--schema-version VERSION` | Choose schema version (e.g. `stable`, `0.1`). Default is `stable`. |
| `--schema-info MODALITY` | Show schema details for a modality (currently a minimal stub). |
| `--list-versions` | List schema versions available in `schemas/`. |
| `--bids` | Run the standard BIDS validator in addition to PRISM validation. |
| `--bids-warnings` | Include warnings from BIDS validator output (default hidden). |
| `--no-prism` | Skip PRISM-specific checks (only BIDS if `--bids` is set). |
| `--validate-templates PATH` | Validate all survey/biometrics JSON templates in a library directory. See [Template Validation](TEMPLATE_VALIDATION.md) for details. |
| `--build-environment` | Build a privacy-safe `*_environment.tsv` from `scans.tsv` anchors (no dataset validation run). |
| `--scans-tsv PATH` | Input scans table containing `filename` and `prism_time_anchor` (required with `--build-environment`). |
| `--environment-tsv PATH` | Output path for generated `*_environment.tsv` (required with `--build-environment`). |
| `--lat FLOAT` | Site latitude used by environment providers (required with `--build-environment`). |
| `--lon FLOAT` | Site longitude used by environment providers (required with `--build-environment`). |
| `--environment-providers ...` | Provider list for enrichment (default: `weather pollen air_quality`). |
| `--environment-cache PATH` | Cache file for provider responses (default: `.prism/environment_cache.json`). |
| `--json` | Output a JSON report to stdout (compact). |
| `--json-pretty` | Output a JSON report to stdout (pretty). |
| `--format {json,sarif,junit,markdown,csv}` | Set an explicit output format. |
| `-o FILE`, `--output FILE` | Write report to a file. |
| `--fix` | Apply auto-fixes for common issues (e.g., missing sidecars, `.bidsignore`). |
| `--dry-run` | Show what `--fix` would change without applying it. |
| `--list-fixes` | List which issue types are auto-fixable. |
| `--init-plugin NAME` | Create a validator plugin template at `<dataset>/validators/<NAME>.py`. |
| `--list-plugins` | List plugins loaded for a dataset. |
| `--no-plugins` | Disable plugin loading. |
| `--version` | Print PRISM version and exit. |

### Common examples

```bash
# Validate
python prism.py /data/study-01

# Validate with BIDS validator too
python prism.py /data/study-01 --bids

# Produce SARIF for GitHub Code Scanning
python prism.py /data/study-01 --format sarif -o prism.sarif

# Validate survey templates in your project library
python prism.py --validate-templates /code/library/survey

# Build privacy-safe environment table from scans anchors
python prism.py \
  --build-environment \
  --scans-tsv /data/study-01/sub-01/ses-01/sub-01_ses-01_scans.tsv \
  --environment-tsv /data/study-01/sub-01/ses-01/environment/sub-01_ses-01_environment.tsv \
  --lat 47.07 \
  --lon 15.44

# Auto-fix (preview)
python prism.py /data/study-01 --fix --dry-run

# Auto-fix (apply)
python prism.py /data/study-01 --fix
```

### Environment build mode (`--build-environment`)

- Uses privacy-safe temporal anchors (`prism_time_anchor`) from `scans.tsv`.
- Rejects raw time keys like `date`, `datetime`, `timestamp`, `acquisition_time` in input rows.
- Runs independently from normal dataset validation (you can call it without positional `dataset`).
- Current bundled providers: `weather`, `pollen`, `air_quality`.

---

## 2) `prism_tools.py` — conversions, libraries, and helpers

### Purpose
`prism_tools.py` is the “Swiss Army Knife” for creating and managing PRISM-compatible content:

- Import **Survey** and **Biometrics** libraries from Excel
- Convert wide survey exports into a PRISM/BIDS-like dataset
- Create **survey derivatives** (scores, reverse-coding) using **Recipes**
- Convert Varioport `.raw` physio data into BIDS-like output
- Generate manuscript-ready **Methods** boilerplate from your libraries
- Manage and synchronize library templates

### Usage

```bash
python prism_tools.py --help
python prism_tools.py <command> --help
```

### Command overview

#### `recipes` (Derivatives)
Compute scores and subscales based on JSON recipe files.

```bash
# Compute survey scores
python prism_tools.py recipes surveys --prism /path/to/dataset

# Compute biometrics scores
python prism_tools.py recipes biometrics --prism /path/to/dataset
```

#### `library` (Management)
Tools for maintaining the PRISM library.

```bash
# Generate methods boilerplate
python prism_tools.py library generate-methods-text --output methods.md --lang en

# Fill missing schema keys in library files
python prism_tools.py library fill --modality survey --path library/survey/

# Synchronize keys across library files
python prism_tools.py library sync --modality biometrics --path library/biometrics/

# Generate a CSV catalog of the library
python prism_tools.py library catalog --input library/survey --output catalog.csv
```

The generated Methods boilerplate now summarizes the richer PRISM schema metadata (DOIs, licenses, age ranges, administration/scoring times, item counts, and access levels) alongside the existing citations.

#### `survey` / `biometrics` (Conversions)
Import data from external formats.

```bash
# Import from LimeSurvey (LSA)
python prism_tools.py survey import-limesurvey --input survey.lsa --output library/survey/

# Import from Excel
python prism_tools.py survey import-excel --input data.xlsx --output library/survey/
```

#### `convert physio`
Convert Varioport physiological recordings (`.raw`) into BIDS-like outputs.

```bash
python prism_tools.py convert physio \
  --input ./sourcedata \
  --output ./rawdata \
  --task rest \
  --suffix ecg \
  --sampling-rate 256
```

#### `demo create`
Create a demo dataset for testing.

```bash
python prism_tools.py demo create --output archive/prism_demo_copy
```

#### `survey import-excel`
Import survey templates from an Excel codebook into a JSON library.

```bash
python prism_tools.py survey import-excel --excel surveys.xlsx --library-root library
```

#### `survey validate`
Validate survey library JSONs and enforce uniqueness constraints.

```bash
python prism_tools.py survey validate --library library/survey
```

#### `survey convert`
Convert a wide survey export (`.xlsx` or LimeSurvey `.lsa`) into a PRISM/BIDS-like dataset.

```bash
python prism_tools.py survey convert \
  --input survey_export.xlsx \
  --output /tmp/my_prism_dataset
```

Key options:
- `--library`: select template folder
- `--lang`: language selection for i18n templates (`de` default; `auto` for `.lsa`)
- `--unknown {error,warn,ignore}`: how to handle unmapped columns
- `--dry-run`: print mapping only
- `--force`: allow writing into non-empty output directory

#### `survey import-limesurvey` / `survey import-limesurvey-batch`
Import LimeSurvey instruments into PRISM templates/datasets.

```bash
python prism_tools.py survey import-limesurvey --input instrument.lsa --output survey-ads.json
```

```bash
python prism_tools.py survey import-limesurvey-batch \
  --input-dir ./limesurvey_exports \
  --output-dir ./my_dataset \
  --session-map t1:ses-1,t2:ses-2,t3:ses-3
```

#### `survey i18n-migrate` / `survey i18n-build`
Create and compile i18n-capable survey templates.

```bash
# Create i18n source templates (no translation added automatically)
python prism_tools.py survey i18n-migrate --src library/survey --dst library/survey_i18n --languages de,en

# Compile i18n templates for one target language
python prism_tools.py survey i18n-build --src library/survey_i18n --out library/survey_de --lang de --fallback de
```

#### `biometrics import-excel`
Import biometrics templates from an Excel codebook.

```bash
python prism_tools.py biometrics import-excel \
  --excel biometrics_codebook.xlsx \
  --sheet 0 \
  --library-root library
```

Key options:
- `--equipment`: default `Technical.Equipment`
- `--supervisor`: default `Technical.Supervisor`

#### `dataset build-biometrics-smoketest`
Generate a small biometrics dataset (templates + dummy data) for testing.

```bash
python prism_tools.py dataset build-biometrics-smoketest --output /tmp/prism_biometrics_smoketest
```

#### `derivatives surveys` / `derivatives biometrics`
Compute derived scores from TSVs in an already valid PRISM dataset.

```bash
# Survey derivatives
python prism_tools.py derivatives surveys --prism /path/to/dataset --format prism

# Biometric derivatives (supports xlsx, csv, save, r)
python prism_tools.py derivatives biometrics --prism /path/to/dataset --format xlsx
```

See [RECIPES.md](RECIPES.md) for details on how to write scoring recipes.

#### `library generate-methods-text`
Generate manuscript-ready methods text from libraries.

```bash
python prism_tools.py library generate-methods-text --output methods_en.md --lang en
python prism_tools.py library generate-methods-text --output methods_de.md --lang de
```

---

## 3) “Scripts” in `scripts/`

### Environment enrichment scripts

PRISM now provides **two separate scripts** for environmental enrichment:

1. **Scanner / DICOM workflow** (site-fixed, scanner-related):

```bash
python scripts/build_environment_from_dicom.py \
  --dicom /path/to/file.dcm \
  --dataset-root /path/to/dataset \
  --subject-id sub-01 \
  --session-id ses-01
```

- Extracts acquisition timestamp from DICOM.
- Uses hardcoded scanner site coordinates.
- Writes directly to `sub-*/ses-*/environment/*_environment.tsv`.
- Updates `.bidsignore` in dataset root.

2. **Survey / international workflow** (location provided per run):

```bash
python scripts/build_environment_from_survey.py \
  --timestamp 2026-02-26T14:30:00 \
  --lat 47.0707 \
  --lon 15.4395 \
  --location-label survey-site \
  --output /path/to/sub-01_ses-01_environment.tsv \
  --subject-id sub-01 \
  --session-id ses-01
```

- Uses provided timestamp + coordinates.
- Designed for multi-country survey studies.
- Writes one-row environment TSV for the specified context.

Both scripts query Open-Meteo hourly weather/air-quality/pollen APIs and include
moon and sun context variables.

Most files under `scripts/` are **implementation details** called by the CLIs.

If you’re a new user, prefer:
- `python prism.py ...` (validation)
- `python prism_tools.py ...` (imports/conversion/derivatives)
- `python prism-studio.py` (web interface)

If you’re developing PRISM, see [CHANGELOG.md](CHANGELOG.md).
