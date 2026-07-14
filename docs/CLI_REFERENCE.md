# CLI & Script Reference

The detailed command reference for PRISM's terminal surfaces. Reference-first — for
a guided narrative use [CLI Workflows](CLI_WORKFLOWS.md), for a short first success
[Quick Start](QUICK_START.md), for schema context [Specifications](SPECIFICATIONS.md),
for scoring-definition details [Recipes](RECIPES.md).

## Getting started

| Task | Preferred entry point |
|---|---|
| Start Studio from the terminal | `rtk studio` or `python prism-studio.py` |
| Validate a dataset | `rtk validator ...` or `prism-validator ...` |
| Run tools subcommands | `rtk tools ...` or `python prism_tools.py ...` |
| Run repo-local tests | `rtk test -q` |
| Run coverage in this repo | `rtk coverage` |

Daily repo checks: `bash scripts/ci/run_local_smoke.sh` (fast sanity),
`bash scripts/ci/run_runtime_gate.sh` (full required gate).

Both `prism.py` and `prism_tools.py` **enforce** running from the repo-local virtual
environment at `./.venv` — activate it first
(`source .venv/bin/activate` / `.venv\Scripts\activate`) or you'll see
`Error: You are not running inside the prism virtual environment!`.

**`rtk`** is a lightweight wrapper for common workflows — use it first for normal
repo-local work, drop to direct Python entry points when you need the explicit
underlying command. Subcommands: `setup`, `studio`, `validator` (aliases `validate`,
`prism`), `tools` (alias `prism-tools`), `test`, `coverage`, `codecov`, `git`, `gh`.

```bash
rtk setup --dev
rtk studio
rtk validator /data/study-01 --bids
rtk tools survey convert --help
rtk test -q
rtk coverage
rtk codecov upload-process       # requires CODECOV_TOKEN
rtk git status
rtk gh pr list
```

## `prism.py` — the dataset validator

Validates a dataset against BIDS rules (optional) and PRISM schemas, produces
machine-readable reports (JSON, SARIF, JUnit, Markdown, CSV), and can optionally
apply safe auto-fixes.

```bash
prism-validator /path/to/dataset
```

**Options:**

| Option | Meaning |
|---|---|
| `-v`, `--verbose` | Print detailed progress / scanning info |
| `--schema-version VERSION` | Choose schema version (e.g. `stable`, `0.1`). Default `stable` |
| `--schema-info MODALITY` | Show schema details for a modality (minimal stub) |
| `--list-versions` | List schema versions available in `app/schemas/` |
| `--bids` | Run the standard BIDS validator in addition to PRISM validation |
| `--bids-warnings` | Include BIDS validator warnings (default hidden) |
| `--library PATH` | Override the template library path for schema/template lookups |
| `--no-prism` | Skip PRISM-specific checks (only BIDS if `--bids` is set) |
| `--validate-templates PATH` | Validate all survey/biometrics JSON templates in a library directory ([details](TEMPLATE_VALIDATION.md)) |
| `--build-environment` | Build a privacy-safe `*_environment.tsv` from `scans.tsv` anchors (no dataset validation run) |
| `--scans-tsv` / `--environment-tsv` / `--lat` / `--lon` | Required with `--build-environment` |
| `--environment-providers ...` | Provider list for enrichment (default: `weather pollen air_quality`) |
| `--environment-cache PATH` | Cache file for provider responses (default `.prism/environment_cache.json`) |
| `--json` / `--json-pretty` | Output a JSON report to stdout |
| `--format {json,sarif,junit,markdown,csv}` | Explicit output format |
| `-o FILE`, `--output FILE` | Write report to a file |
| `--fix` / `--dry-run` / `--list-fixes` | Apply/preview auto-fixes, or list fixable issue types |
| `--init-plugin NAME` / `--list-plugins` / `--no-plugins` | Validator plugin management |
| `--version` | Print PRISM version and exit |

```bash
prism-validator /data/study-01                          # validate
prism-validator /data/study-01 --bids                    # + BIDS
prism-validator /data/study-01 --format sarif -o prism.sarif   # SARIF for GitHub Code Scanning
prism-validator --validate-templates /code/library/survey      # validate templates
prism-validator /data/study-01 --fix --dry-run            # preview auto-fix
prism-validator /data/study-01 --fix                      # apply auto-fix

# Build privacy-safe environment table from scans anchors (independent of normal validation)
prism-validator --build-environment \
  --scans-tsv /data/study-01/sub-01/ses-01/sub-01_ses-01_scans.tsv \
  --environment-tsv /data/study-01/sub-01/ses-01/environment/sub-01_ses-01_environment.tsv \
  --lat 47.07 --lon 15.44
```

`--build-environment` uses privacy-safe temporal anchors (`prism_time_anchor`) from
`scans.tsv` and rejects raw time keys (`date`, `datetime`, `timestamp`,
`acquisition_time`) in input rows. Bundled providers: `weather`, `pollen`,
`air_quality`.

## `prism_tools.py` — conversions, libraries, and helpers

The general-purpose tool for creating and managing PRISM-compatible content: import
Survey/Biometrics libraries from Excel, convert wide survey exports, compute
derivatives via Recipes, convert Varioport physio data, generate Methods
boilerplate, and manage library templates.

```bash
python prism_tools.py --help
python prism_tools.py <command> --help
```

### Recipes and library management

**`recipes surveys` / `recipes biometrics`** — compute derived scores from TSVs in
an already-valid PRISM dataset. There is no separate `derivatives` command; this is
the only way to compute scored output from the CLI. `--format` accepts `prism`,
`flat` (default), `csv`, `xlsx`, or `sav` for SPSS (no `r` format). See
[Recipes](RECIPES.md) for how to write scoring recipes.

```bash
python prism_tools.py recipes surveys --prism /path/to/dataset --format prism
python prism_tools.py recipes biometrics --prism /path/to/dataset --format xlsx
```

**`library`** — maintain the PRISM library:

```bash
python prism_tools.py library generate-methods-text --output methods.md --lang en
python prism_tools.py library fill --modality survey --path library/survey/
python prism_tools.py library sync --modality biometrics --path library/biometrics/
python prism_tools.py library catalog --input library/survey --output catalog.csv
```

The generated Methods boilerplate summarizes richer schema metadata (DOIs, licenses,
age ranges, administration/scoring times, item counts, access levels) alongside
citations.

### Survey conversion, templates, and i18n

**`survey import-excel`** / **`survey validate`** / **`survey convert`** — import a
codebook, validate a library, or convert a wide export/LimeSurvey `.lsa` into a
PRISM/BIDS-like dataset:

```bash
python prism_tools.py survey import-excel --excel surveys.xlsx --library-root library
python prism_tools.py survey validate --library library/survey
python prism_tools.py survey convert --input survey_export.xlsx --output /tmp/my_prism_dataset
```

`survey convert` key options: `--library` (template folder), `--lang` (i18n
language, `de` default / `auto` for `.lsa`), `--unknown {error,warn,ignore}`
(unmapped columns), `--dry-run`, `--force`.

**`survey import-limesurvey`** / **`survey import-limesurvey-batch`**:

```bash
python prism_tools.py survey import-limesurvey --input instrument.lsa --output survey-ads.json
python prism_tools.py survey import-limesurvey-batch \
  --input-dir ./limesurvey_exports --output-dir ./my_dataset \
  --session-map t1:ses-1,t2:ses-2,t3:ses-3
```

**`survey i18n-migrate`** / **`i18n-build`** / **`i18n-autotranslate`** — create,
compile, and auto-translate i18n-capable templates:

```bash
python prism_tools.py survey i18n-migrate --src library/survey --dst library/survey_i18n --languages de,en
python prism_tools.py survey i18n-build --src library/survey_i18n --out library/survey_de --lang de --fallback de

export DEEPL_API_KEY="your_deepl_key"
python prism_tools.py survey i18n-autotranslate \
  --src library/survey_i18n --out library/survey_i18n_de \
  --provider deepl --source-lang en --target-lang de
# or --provider libretranslate --api-url https://libretranslate.example/translate
```

### Biometrics

**`biometrics import-excel`** — import biometrics templates from an Excel codebook:

```bash
python prism_tools.py biometrics import-excel --excel biometrics_codebook.xlsx --sheet 0 --library-root library
```

Key options: `--equipment` (default `Technical.Equipment` value, default
`"Legacy/Imported"`), `--supervisor` (`investigator` default, or `physician`,
`trainer`, `self`).

**`dataset build-biometrics-smoketest`** — generate a small biometrics dataset
(templates + dummy data) for testing:

```bash
python prism_tools.py dataset build-biometrics-smoketest --output /tmp/prism_biometrics_smoketest
```

### Participants

Helper commands used by the web converter backend and terminal workflows. Use
absolute paths for `--input`; `--project` accepts a project root or a `project.json`
path. `participants preview`/`convert` cover imported-file workflows (Studio Case 1);
`participants merge` covers the preview-first safe-merge workflow (Studio Case 3);
Case 2 (modify existing project files in place) is Studio-only, no dedicated CLI
command. `participants convert` writes `participants.tsv` into the resolved project
root.

```bash
# Detect participant ID column
python prism_tools.py participants detect-id --input /absolute/path/to/T1.xlsx --sheet 0 --separator auto --json

# Preview / convert
python prism_tools.py participants preview --input /absolute/path/to/T1.xlsx --id-column ID --project /absolute/path/to/my-project/project.json --json
python prism_tools.py participants convert --input /absolute/path/to/T1.xlsx --id-column ID --project /absolute/path/to/my-project/project.json --force --json

# Safe merge: preview, then apply once preview shows zero conflicts
python prism_tools.py participants merge --input /absolute/path/to/T1.xlsx --id-column ID --project /absolute/path/to/my-project/project.json --json
python prism_tools.py participants merge --input /absolute/path/to/T1.xlsx --id-column ID --project /absolute/path/to/my-project/project.json --apply --json
python prism_tools.py participants merge --input /absolute/path/to/T1.xlsx --id-column ID --project /absolute/path/to/my-project/project.json --conflicts-csv

# Save a reusable mapping (preferred target: <project>/code/library)
python prism_tools.py participants save-mapping --mapping-json '{"participant_id": {"source_column": "ID"}}' --project /absolute/path/to/my-project/project.json
```

### Environment

**`environment preview`** / **`convert`**:

```bash
python prism_tools.py environment preview --input /absolute/path/to/environment.xlsx --json

# --timestamp-col is required for convert
python prism_tools.py environment convert \
  --input /absolute/path/to/environment.xlsx \
  --project /absolute/path/to/my-project --timestamp-col collected_at
```

### Physio and eyetracking

**`convert physio`** — Varioport (`.raw`/`.vpd`) recordings from a `sourcedata`
directory or single file:

```bash
python prism_tools.py convert physio --input ./sourcedata --output ./rawdata --task rest --suffix ecg --sampling-rate 256
```

**`physio batch-convert`** — batch-convert physio/eyetracking files sitting in a
flat source folder (distinct from `convert physio` above):

```bash
python prism_tools.py physio batch-convert --input ./flat_source_folder --output ./converted
```

### Wide-to-long and version merging (dispatched via `prism.py`)

**`wide-to-long`** — convert a wide survey-style table into long format by matching
session indicators in column names:

```bash
# Inspect matches without writing output
python prism.py wide-to-long --input build/Limesurvey_gesamt.xlsx --session-indicators T1_,T2_,T3_ --inspect-only

# Convert and write
python prism.py wide-to-long --input survey_export.xlsx --output survey_export_long.csv --session-indicators T1_,T2_,T3_
```

Key options: `--session-indicators` (comma-separated tokens, e.g. `T1_,T2_,T3_` or
`_pre,_post`), `--session-map` (e.g. `T1_:pre,T2_:post`), `--inspect-only`,
`--preview-limit`, `--force`. Output format is inferred from the extension
(`.csv`/`.tsv`/`.xlsx`). A column-name indicator appearing more than once is treated
as ambiguous and refused until made more specific.

**`merge-versions`** — merge a new instrument version into an existing template into
a single multi-variant template:

```bash
python prism.py merge-versions survey-bdi.json bdi_long.xlsx                      # auto-detects version names
python prism.py merge-versions survey-bdi.json bdi_long.json --new-version long --existing-version short
python prism.py merge-versions survey-bdi.json bdi_long.xlsx --dry-run            # preview only
```

### Dataset utilities, anonymize, and export

**`dataset build-hostile-demo`** / **`cleanup-project-metadata`** /
**`rename-subjects`**: build an adversarial test dataset, remove legacy
converter-written session metadata, or rename subject IDs (DataLad-aware, one commit
per subject). Less common maintenance operations — run
`python prism_tools.py dataset <action> --help` for full flags.

```bash
python prism_tools.py dataset build-hostile-demo --output /tmp/prism_hostile_demo
python prism_tools.py dataset cleanup-project-metadata --project /path/to/project
python prism_tools.py dataset rename-subjects --project /path/to/project --mode last3 --dry-run
```

**`anonymize`** — randomize participant IDs and/or mask copyrighted question text,
the CLI equivalent of Studio's Standard Export anonymization (see
[Export](studio/export.md)). Distinct from `recipes`' `--anonymized` flag, which only
affects the output subfolder name.

```bash
python prism_tools.py anonymize --dataset /path/to/project --output /path/to/project_anonymized --random --mask-questions
```

**`template-export`** — export a reusable project template ZIP without subject
folders (keeps structure, drops participant-specific content):

```bash
python prism_tools.py template-export --project /path/to/project --output /path/to/project_template.zip
```

**`demo create`** — create a demo dataset for testing:

```bash
python prism_tools.py demo create --output archive/prism_demo_copy
```

## Scripts in `scripts/`

Most files under `scripts/` are implementation details called by the CLIs. If
you're a new user, prefer `prism-validator ...`, `python prism_tools.py ...`, and
`python prism-studio.py` instead of calling scripts directly.

One environment-enrichment script remains under `scripts/future_feature/` — planned
work, not part of the active runtime path yet:

```bash
python scripts/future_feature/build_environment_from_survey.py \
  --timestamp 2026-02-26T14:30:00 --lat 47.0707 --lon 15.4395 \
  --location-label survey-site \
  --output /path/to/sub-01_ses-01_environment.tsv \
  --subject-id sub-01 --session-id ses-01
```

Uses a provided timestamp + coordinates (designed for multi-country survey studies),
queries Open-Meteo hourly weather/air-quality/pollen APIs, and includes moon/sun
context variables — writes one row per context. (The earlier scanner/DICOM variant
was removed; the web Environment Data Import panel now scans the project's own BIDS
JSON sidecars for acquisition timestamps and scanner-location tags directly.)
