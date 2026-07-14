# CLI & Script Reference

Use this page as the detailed command reference for PRISM’s terminal surfaces.

This page is intentionally reference-first. If you want a guided narrative, use:

- [CLI_WORKFLOWS.md](CLI_WORKFLOWS.md) for task-oriented terminal paths
- [QUICK_START.md](QUICK_START.md) for a short first success
- [SPECIFICATIONS.md](SPECIFICATIONS.md) for schema context
- [RECIPES.md](RECIPES.md) for scoring-definition details

## Quick command map

| Task | Preferred entry point |
|---|---|
| Start Studio from the terminal | `rtk studio` or `python prism-studio.py` |
| Validate a dataset | `rtk validator ...` or `python prism-validator ...` |
| Run tools subcommands | `rtk tools ...` or `python prism_tools.py ...` |
| Run repo-local tests | `rtk test -q` |
| Run coverage in this repo | `rtk coverage` |

## Daily checks

Useful repo-root checks:

```bash
# fast sanity
bash scripts/ci/run_local_smoke.sh

# full required gate
bash scripts/ci/run_runtime_gate.sh
```

## How to read this page

The command surfaces are grouped into three layers:

1. environment and wrapper usage
2. validator commands
3. `prism_tools.py` subcommands and helper scripts

If you are scanning rather than reading closely, start with the command map and
then jump to the specific tool section you need.

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

## 0.5) `rtk` - repo toolkit wrapper

`rtk` is a lightweight command wrapper for common project workflows.

Examples:

```bash
# Setup and dependency bootstrap
rtk setup --dev

# Start Studio
rtk studio

# Run validator
rtk validator /data/study-01 --bids

# Use prism_tools commands
rtk tools survey convert --help

# Run tests
rtk test -q

# Run coverage with enforced threshold (default: 80%)
rtk coverage

# Upload with Codecov CLI (requires CODECOV_TOKEN)
rtk codecov upload-process

# RTK-first git and GitHub CLI usage
rtk git status
rtk gh pr list
```

Available subcommands:
- `setup`
- `studio`
- `validator` (aliases: `validate`, `prism`)
- `tools` (alias: `prism-tools`)
- `test`
- `coverage`
- `codecov`
- `git`
- `gh`

Recommended rule:

- use `rtk` first for normal repo-local work
- drop to direct Python entry points when you need the explicit underlying command

---

## 1) `prism.py` — the dataset validator

### Purpose
- Validate a dataset against **BIDS rules** (optional) and **PRISM schemas**.
- Produce machine-readable reports (JSON, SARIF, JUnit, Markdown, CSV).
- Optionally apply safe auto-fixes (`--fix`).

### Usage

```bash
python prism-validator /path/to/dataset
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
| `--library PATH` | Override the template library path used for schema/template lookups during validation. |
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
python prism-validator /data/study-01

# Validate with BIDS validator too
python prism-validator /data/study-01 --bids

# Produce SARIF for GitHub Code Scanning
python prism-validator /data/study-01 --format sarif -o prism.sarif

# Validate survey templates in your project library
python prism-validator --validate-templates /code/library/survey

# Build privacy-safe environment table from scans anchors
python prism-validator \
  --build-environment \
  --scans-tsv /data/study-01/sub-01/ses-01/sub-01_ses-01_scans.tsv \
  --environment-tsv /data/study-01/sub-01/ses-01/environment/sub-01_ses-01_environment.tsv \
  --lat 47.07 \
  --lon 15.44

# Auto-fix (preview)
python prism-validator /data/study-01 --fix --dry-run

# Auto-fix (apply)
python prism-validator /data/study-01 --fix
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
python prism_tools.py survey import-excel --excel data.xlsx --output library/survey/
```

#### `convert physio`
Convert Varioport physiological recordings (`.raw`, `.vpd`) into outputs from either a sourcedata directory or a single file.

```bash
python prism_tools.py convert physio \
  --input ./sourcedata \
  --output ./rawdata \
  --task rest \
  --suffix ecg \
  --sampling-rate 256
```

#### `wide-to-long`
Convert a wide survey-style table into a long table by matching exact session indicators in column names.

```bash
# Inspect matches and rename preview without writing output
python prism.py wide-to-long \
  --input build/Limesurvey_gesamt.xlsx \
  --session-indicators T1_,T2_,T3_ \
  --inspect-only

# Convert and write a CSV
python prism.py wide-to-long \
  --input survey_export.xlsx \
  --output survey_export_long.csv \
  --session-indicators T1_,T2_,T3_
```

Key options:
- `--session-indicators`: comma-separated exact tokens to match anywhere in the column name, for example `T1_,T2_,T3_` or `_pre,_post`
- `--session-map`: optional indicator-to-session mapping such as `T1_:pre,T2_:post`
- `--inspect-only`: print indicator counts, rename preview, and ambiguity warnings without writing a file
- `--preview-limit`: limit how many preview lines are printed
- `--force`: overwrite an existing output file

Notes:
- If the same indicator appears multiple times in a column name, the backend treats that as ambiguous and refuses conversion until the indicator is made more specific.
- Output format is inferred from the output file extension: `.csv`, `.tsv`, or `.xlsx`.

#### `merge-versions`
Merge a new version of a survey instrument into an existing template, producing a
single multi-variant template for version-aware validation and recipe scoring.
Dispatched from `prism.py` the same way `wide-to-long` is.

```bash
# Auto-detects version names
python prism.py merge-versions survey-bdi.json bdi_long.xlsx

# Explicit version names
python prism.py merge-versions survey-bdi.json bdi_long.json --new-version long --existing-version short

# Preview without saving
python prism.py merge-versions survey-bdi.json bdi_long.xlsx --dry-run
```

#### `participants`
Participants helper commands used by the web converter backend and terminal workflows.

Important:
- Use absolute file paths for `--input`.
- `--project` can point to either a project root directory or a `project.json` file path.
- `participants preview` and `participants convert` cover imported-file workflows that match Studio Case 1.
- `participants merge` covers the preview-first safe merge workflow that matches Studio Case 3.
- Studio Case 2 (modify existing project files in place) is currently a Studio workflow rather than a dedicated CLI command.
- `participants convert` writes `participants.tsv` into the resolved project root.

```bash
# Detect participant ID column
python prism_tools.py participants detect-id \
  --input /absolute/path/to/T1.xlsx \
  --sheet 0 \
  --separator auto \
  --json

# Preview participant extraction columns/rows
python prism_tools.py participants preview \
  --input /absolute/path/to/T1.xlsx \
  --sheet 0 \
  --id-column ID \
  --separator auto \
  --project /absolute/path/to/my-project/project.json \
  --preview-limit 20 \
  --json

# Convert to participants.tsv under project root
python prism_tools.py participants convert \
  --input /absolute/path/to/T1.xlsx \
  --sheet 0 \
  --id-column ID \
  --separator auto \
  --project /absolute/path/to/my-project/project.json \
  --force \
  --json

# Preview a safe merge into an existing participants.tsv
python prism_tools.py participants merge \
  --input /absolute/path/to/T1.xlsx \
  --sheet 0 \
  --id-column ID \
  --separator auto \
  --project /absolute/path/to/my-project/project.json \
  --json

# Apply the merge only after preview shows zero conflicts
python prism_tools.py participants merge \
  --input /absolute/path/to/T1.xlsx \
  --sheet 0 \
  --id-column ID \
  --separator auto \
  --project /absolute/path/to/my-project/project.json \
  --apply \
  --json

# Export the full conflict report as CSV
python prism_tools.py participants merge \
  --input /absolute/path/to/T1.xlsx \
  --sheet 0 \
  --id-column ID \
  --separator auto \
  --project /absolute/path/to/my-project/project.json \
  --conflicts-csv

# Save a reusable participants_mapping.json (preferred target: <project>/code/library)
python prism_tools.py participants save-mapping \
  --mapping-json '{"participant_id": {"source_column": "ID"}}' \
  --project /absolute/path/to/my-project/project.json
```

#### `environment`
Preview or convert environment/sociodemographic-adjacent source tables.

```bash
# Preview detected columns and sample rows
python prism_tools.py environment preview --input /absolute/path/to/environment.xlsx --json

# Convert into project environment outputs (--timestamp-col is required)
python prism_tools.py environment convert \
  --input /absolute/path/to/environment.xlsx \
  --project /absolute/path/to/my-project \
  --timestamp-col collected_at
```

#### `physio batch-convert`
Batch-convert physio/eyetracking files sitting in a flat source folder (distinct
from `convert physio`, which operates against a `sourcedata` directory or a single
file — see above).

```bash
python prism_tools.py physio batch-convert --input ./flat_source_folder --output ./converted
```

#### `dataset build-hostile-demo` / `cleanup-project-metadata` / `rename-subjects`
Additional `dataset` actions beyond `build-biometrics-smoketest`:

- `build-hostile-demo` — builds an adversarial PRISM dataset exercising edge cases
  across sociodemographics, biometrics, environment/MRI, and subject/session IDs.
- `cleanup-project-metadata` — removes legacy converter-written session metadata
  from `project.json`.
- `rename-subjects` — renames subject IDs across a PRISM/BIDS dataset (DataLad-aware,
  one commit per subject).

```bash
python prism_tools.py dataset build-hostile-demo --output /tmp/prism_hostile_demo
python prism_tools.py dataset cleanup-project-metadata --project /path/to/project
python prism_tools.py dataset rename-subjects --project /path/to/project --mode last3 --dry-run
```

Run `python prism_tools.py dataset <action> --help` for each action's full flag set —
these are less common maintenance operations, not part of the everyday workflow.

#### `anonymize`
Anonymize a dataset for sharing: randomize participant IDs and/or mask copyrighted
question text. This is the CLI equivalent of Studio's Standard Export anonymization
options (see [export.md](studio/export.md)), and is distinct from the `--anonymized`
flag on `recipes surveys`/`recipes biometrics`, which only affects the output
subfolder name.

```bash
python prism_tools.py anonymize --dataset /path/to/project --output /path/to/project_anonymized --random --mask-questions
```

#### `template-export`
Export a reusable project template ZIP without subject folders — keeps project
metadata/structure, drops participant-specific content.

```bash
python prism_tools.py template-export --project /path/to/project --output /path/to/project_template.zip
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

#### `survey i18n-autotranslate`
Auto-translate localized survey template strings from one language into another.

```bash
# DeepL (API key via env var)
export DEEPL_API_KEY="your_deepl_key"
python prism_tools.py survey i18n-autotranslate \
  --src library/survey_i18n \
  --out library/survey_i18n_de \
  --provider deepl \
  --source-lang en \
  --target-lang de
```

```bash
# LibreTranslate
python prism_tools.py survey i18n-autotranslate \
  --src library/survey_i18n \
  --out library/survey_i18n_de \
  --provider libretranslate \
  --api-url https://libretranslate.example/translate \
  --source-lang en \
  --target-lang de
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
- `--equipment`: default `Technical.Equipment` value written to the biometrics JSON, default `"Legacy/Imported"`
- `--supervisor`: one of `investigator` (default), `physician`, `trainer`, `self`

#### `dataset build-biometrics-smoketest`
Generate a small biometrics dataset (templates + dummy data) for testing.

```bash
python prism_tools.py dataset build-biometrics-smoketest --output /tmp/prism_biometrics_smoketest
```

#### `recipes surveys` / `recipes biometrics`
Compute derived scores from TSVs in an already valid PRISM dataset. There is no
separate `derivatives` command — this is the only way to compute scored output from
the CLI (see the `recipes` (Derivatives) section above for the full flag list;
`--format` accepts `prism`, `flat` (default), `csv`, `xlsx`, or `sav` for SPSS —
there is no `r` format).

```bash
# Survey derivatives
python prism_tools.py recipes surveys --prism /path/to/dataset --format prism

# Biometric derivatives
python prism_tools.py recipes biometrics --prism /path/to/dataset --format xlsx
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

Note: These utilities are currently parked under `scripts/future_feature/`.
They are planned work and not part of the active web/CLI backend runtime path yet.
For regular use, prefer `prism_tools.py` / backend modules.

PRISM provides one remaining future-feature script for environmental enrichment:

**Survey / international workflow** (location provided per run):

```bash
python scripts/future_feature/build_environment_from_survey.py \
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

It queries Open-Meteo hourly weather/air-quality/pollen APIs and includes
moon and sun context variables.

(The earlier scanner/DICOM variant of this script was removed — the web
Environment Data Import panel now scans the project's own BIDS JSON sidecars
for acquisition timestamps and scanner-location tags directly, with no
hardcoded site coordinates.)

Most files under `scripts/` are **implementation details** called by the CLIs.

If you’re a new user, prefer:
- `python prism-validator ...` (validation)
- `python prism_tools.py ...` (imports/conversion/derivatives)
- `python prism-studio.py` (web interface)

If you are developing PRISM, refer to the repository changelog file (`CHANGELOG.md`).
