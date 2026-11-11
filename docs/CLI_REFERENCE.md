# CLI & Script Reference

The detailed command reference for PRISM's terminal surfaces. Reference-first — for
a guided narrative use [CLI Workflows](CLI_WORKFLOWS.md), for a guided first success
[Getting Started](TUTORIAL_BEGINNER.md), for schema context [Specifications](SPECIFICATIONS.md),
for scoring-definition details [Recipes](RECIPES.md).

## Getting started

| Task | Preferred entry point |
|---|---|
| Start Studio from the terminal | `python prism-studio.py` |
| Validate a dataset | `python prism.py ...` |
| Run tools subcommands | `python prism_tools.py ...` |
| Run repo-local tests | `pytest -q` |
| Run coverage in this repo | `pytest --cov=src --cov-report=term-missing` |

Daily repo check (full required gate): `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix`.

Both `prism.py` and `prism_tools.py` **enforce** running from the repo-local virtual
environment at `./.venv` — activate it first
(`source .venv/bin/activate` / `.venv\Scripts\activate`) or you'll see
`Error: You are not running inside the prism virtual environment!`.

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
| `--modality-version NAME=X.Y.Z` | Validate one modality against a specific version (repeatable); overrides the `project.json` pin. See [Schema versioning](SCHEMA_VERSIONING.md) |
| `--schema-info MODALITY` | Show schema details for a modality (minimal stub) |
| `--list-versions` | List schema versions available in `app/schemas/`, and the versions of each modality |
| `--bids` | Run the BIDS validator. This is the default; the flag only overrides `"runBids": false` in `.prismrc.json` |
| `--no-bids` | Skip the BIDS validator and run only the PRISM checks (cannot be combined with `--bids`) |
| `--bids-warnings` | Include BIDS validator warnings (default hidden) |
| `--library PATH` | Override the template library path for schema/template lookups |
| `--no-prism` | Skip PRISM-specific checks (only the BIDS check runs). Cannot be combined with `--no-bids` or `"runBids": false`: nothing would be left to run (exit 2) |
| `--validate-templates PATH` | Validate all survey/biometrics JSON templates in a library directory ([details](TEMPLATES.md)) |
| `--json` / `--json-pretty` | Output a JSON report to stdout |
| `--format {json,sarif,junit,markdown,csv}` | Explicit output format |
| `-o FILE`, `--output FILE` | Write report to a file |
| `--fix` / `--dry-run` / `--list-fixes` | Apply/preview auto-fixes, or list fixable issue types |
| `--init-plugin NAME` / `--list-plugins` / `--plugins` | Validator plugin management. Plugins are Python code from the dataset, so they load only with `--plugins` (use on datasets you trust) |
| `--version` | Print PRISM version and exit |

```bash
prism-validator /data/study-01                          # PRISM + BIDS (default)
prism-validator /data/study-01 --no-bids                 # PRISM checks only
prism-validator /data/study-01 --format sarif -o prism.sarif   # SARIF for GitHub Code Scanning
prism-validator --validate-templates /code/library/survey      # validate templates
prism-validator /data/study-01 --fix --dry-run            # preview auto-fix
prism-validator /data/study-01 --fix                      # apply auto-fix

```

### Machine-readable output and exit codes

Two JSON shapes, both with a boolean `valid` that is `true` if and only if there
is no ERROR-severity issue (warnings and info do not invalidate):

- `--json` / `--json-pretty`: `dataset`, `schema_version`, `valid`, `summary`, `issues`, `statistics`
- `--format json`: `valid`, `summary`, `issues`

Both JSON outputs add a `bids_validator` object (`engine`, `version`, `spec`) naming the BIDS engine that ran; the key is absent when BIDS did not run (`--no-bids`).

`PRISM902` (BIDS validator not available) is reported when the BIDS engine `bids-validator-deno` cannot be found or fails to start, for example on a platform without a Deno wheel. Reinstall `prism-validator` or run with `--no-bids`.

In these modes stdout carries only the JSON (progress goes to stderr).

| Exit code | Meaning |
|---|---|
| `0` | Validated, no errors |
| `1` | Validation errors (also: dataset path not found) |
| `2` | The validator could not run (crash or bad arguments); stdout has no JSON |

`1` also covers a broken installation or an unexpected error before validation starts; a caller treating only `0` as success fails closed.

Environment enrichment (weather, air quality, pollen) is `prism_tools.py environment convert`.

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

**`recipes validate-file`** — validate a recipe JSON file's structure on its own,
without running a scoring job. Matches the validation Studio's Recipe Builder
"Save" action uses; pass `--known-items-from` a matched template to also catch
typo'd item IDs in `Scores`/`Transforms`:

```bash
python prism_tools.py recipes validate-file recipe-ads.json --known-items-from survey-ads.json
```

**`recipes save`** — validate a recipe against its matching template (project library
first, then the official library) and write it to
`<project>/code/recipes/<modality>/recipe-<task>.json`. This is the same code path
as Studio's Recipe Builder "Save" action:

```bash
python prism_tools.py recipes save --project /path/to/project --recipe recipe-ads.json
```

**`library`** — maintain the PRISM library:

```bash
python prism_tools.py library generate-methods-text --output methods.md --lang en
python prism_tools.py library fill --modality survey --path library/survey/
python prism_tools.py library sync --modality biometrics --path library/biometrics/
python prism_tools.py library catalog --input library/survey --output catalog.csv
```

**`library template-save`** / **`template-delete`** — validate-and-save or delete a
single template in a project's own `code/library/<modality>/` folder, the CLI
equivalents of Studio's Template Editor Save/Delete actions:

```bash
python prism_tools.py library template-save --project /path/to/project \
  --modality survey --filename survey-mytask.json --template mytask.json
python prism_tools.py library template-delete --project /path/to/project \
  --modality survey --filename survey-mytask.json --yes
```

**`library template-check`** — list what a project's survey templates still lack before
data can be converted with them (the check Studio runs before a conversion). Exits 1
when anything is missing; `--tasks a,b` limits it, otherwise every survey template of the
project is checked:

```bash
python prism_tools.py library template-check --project /path/to/project
```

**`library template-remove-language`** — what Studio's Template Editor does with *Remove Language*: takes a
language (`--language en`) out of every item description, answer level and the study instructions, and out of
`I18n.Languages`. The general header (`OriginalName`, `Description`, `Citation`, ...) is never touched, and if the
removed language was `I18n.DefaultLanguage`, another remaining one becomes the default. Prints the template, or writes
it to `--output`:

```bash
python prism_tools.py library template-remove-language --template survey-mytask.json --language en --output survey-mytask.de.json
```

**`library template-score`** — how complete one template is, the numbers behind the rings
in Studio's Template Editor: required fields filled (what a template needs before data can
be converted or exported with it) and recommended fields filled (the FAIR ring: short name,
version, authors, DOI, construct, description, instructions; these never block). Exits 1
while a required field is empty; `--is-global` scores a library template (the project-level
fields are not required), `--json` prints the result as JSON:

```bash
python prism_tools.py library template-score --template survey-mytask.json
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
(unmapped columns), `--dry-run`, `--force`,
`--duplicate-handling {error,keep_first,keep_last,sessions}` (repeated IDs; `sessions`
numbers each ID's rows 1, 2, … by `startdate`/`datestamp`).
`--skip-existing` imports only what is new: a response already in the output project
(recognised by the `startdate`/`seed`/`token` record kept in `code/survey_imports.json`, whatever
session it was stored under) is skipped per survey, a response found under another session is
flagged, and a different response in an occupied subject/session/survey slot is reported as a
conflict and never overwritten. A recorded response is skipped as a whole, even if the project lacks a file for one of the
questionnaires in the export (the check is about new *responses*). Without a record in that file it falls back to the
file name and says so.

Templates are optional for `.lsa` files: questionnaires without a library template are
left out of the conversion and listed as a warning; the matched ones convert.

**`survey export-lss`** / **`export-lss-customized`** / **`export-questionnaire-docx`**
— export template(s) to a LimeSurvey `.lss` file, export a Survey Customizer-style
customization JSON to `.lss`, or render a template as a paper-pencil Word
questionnaire. CLI equivalents of Studio's Survey Generator "Quick Export", Survey
Customizer "Export", and the "Export Word" action shared by Template Editor and
Survey Customizer:

`survey customizer-groups` builds that customization JSON from one or more
templates (what loading templates into the Survey Customizer does); edit it,
then pass it to `export-lss-customized`.

```bash
python prism_tools.py survey export-lss library/survey/survey-gad7.json --output gad7.lss
# keep only some questions (one template; same as un-ticking questions in the GUI)
python prism_tools.py survey export-lss library/survey/survey-gad7.json \
  --include GAD701,GAD702 --output gad7_short.lss
python prism_tools.py survey customizer-groups \
  --template library/survey/survey-gad7.json --output my_customization.json
python prism_tools.py survey export-lss-customized \
  --customization-json my_customization.json --output custom.lss
python prism_tools.py survey export-questionnaire-docx \
  --template library/survey/survey-gad7.json --output gad7.docx
# the page Studio shows for "Preview Questionnaire" (same questions and answers as the Word file)
python prism_tools.py survey export-questionnaire-docx --format html \
  --template library/survey/survey-gad7.json --output gad7.html
```

**`survey export-pavlovia`** — export a PRISM survey template to a
Pavlovia/PsychoPy experiment (`.psyexp` + `conditions.csv`). CLI equivalent
of the "Pavlovia/PsychoPy" option in Studio's Survey Generator "Target
Tool" selector:

```bash
python prism_tools.py survey export-pavlovia library/survey/survey-gad7.json \
  --output ./pavlovia_export --experiment-name gad7_study --language en \
  --include GAD701,GAD702   # optional: keep only these questions
```

Pavlovia export is single-language scoped: `--language`/`-l` picks which
one (default: the template's own default language); `--experiment-name`
overrides the generated experiment/task name (default: derived from the
template); `--output` defaults to alongside the input file.

**`survey import-limesurvey`** / **`survey import-limesurvey-batch`**:

```bash
python prism_tools.py survey import-limesurvey --input instrument.lsa            # list questionnaires
python prism_tools.py survey import-limesurvey --input instrument.lsa --select g30 --output ./templates
python prism_tools.py survey import-limesurvey-batch \
  --input-dir ./limesurvey_exports --output-dir ./my_dataset \
  --session-map t1:ses-1,t2:ses-2,t3:ses-3
```

`import-limesurvey` matches the Template Editor's "Import Template Source" for
`.lss`/`.lsa`. `--split group|question|survey` (default `group`) chooses one
template per question group, per question, or for the whole survey. Without
`--select` (or with `--list`) it only lists the questionnaires; `--select KEY ...`
takes keys from that listing (e.g. `g30`) or `all`, and `--output DIR` receives one
`survey-<taskname>.json` per questionnaire (an existing file is never overwritten).

Listing prints a `[PRISM] Library match for '<name>': ...` line per questionnaire,
compared by wording against the global library (plus the project's library with
`--project DIR`). `--use-library` writes the matched library template instead of
the imported one (the survey's codes are kept as item `Aliases`); it only works
for an exact/high match and otherwise fails with a "one-to-one" message. The
global library is only read, never written.

```bash
python prism_tools.py survey import-limesurvey --input instrument.lsa --select g30 --use-library --output ./templates
```

**`survey import-codebook`** — turn the instrument groups of an Excel/CSV/TSV codebook into PRISM
templates (one per variable prefix), like Studio's Template Editor "Import Template Source". Every import
(codebook, LimeSurvey, Pavlovia) goes through the same step: it is matched against the template library and
the result is printed, `--project` adds that project's library:

```bash
python prism_tools.py survey import-codebook --input codebook.xlsx                         # list groups + library match
python prism_tools.py survey import-codebook --input codebook.xlsx --select ads pss --output ./templates --project ./myproject
```

(`survey import-excel` is the older importer that writes a whole library at once.)

**`survey import-pavlovia`** — turn a Pavlovia survey (SurveyJS `.json`) into one PRISM template per
page (`--split survey` for a single template), like Studio's Template Editor "Import Template Source":

```bash
python prism_tools.py survey import-pavlovia --input survey.json                                  # list pages
python prism_tools.py survey import-pavlovia --input survey.json --select p1 p2 --output ./templates --language de
python prism_tools.py survey import-pavlovia --input survey.json --select all --output ./templates --language de --software-version 2025.1
```

Choices and rating scales keep the stored value as the level key and the shown text as its label;
`visibleIf` becomes `Relevance`; page and question descriptions go to `Study.Instructions`. The file has no
language, so writing needs `--language` (e.g. `de`), which labels all texts and levels (a survey `locale`
is used when present). In Studio's Template Editor you choose it in the language bar after the import,
before the template can be validated.

Rating scales keep `rateMin`/`rateMax`/`rateStep`; a matrix becomes one item per row, multiple text one item
per field, "other"/"none" options become levels. What cannot be represented (checkbox = several values in one
column, ranking, expression formulas, html blocks, hidden items, choices from another question, other question
types) is printed as an import note and shown in the Template Editor's preview.

**`survey prepare-pavlovia`** — turn the responses `.csv` downloaded from Pavlovia into a clean wide table
(`participant_id`, `session`, one column per question) for `survey convert`. The download has no participant or
session column, carries bookkeeping and `_rt` columns, and stores answers under `block/` when the survey ran in a
block, or under an older name when a question was renamed:

```bash
python prism_tools.py survey prepare-pavlovia --input responses.csv --survey survey.json --output wide.csv \
    --id-columns studyID,subID --id-pad 3 --session-column sesID --rename question3=rauchen
python prism_tools.py survey convert --input wide.csv --library ./templates --output ./ds \
    --id-column participant_id --session-column session --session all --duplicate-handling keep_last
```

The participant ID joins `--id-columns` (every part after the first zero-padded to `--id-pad` digits); an empty
part takes the survey's default value, but only for an experiment that never stores the field (a hidden field).
The session is the text the participant saw for the stored choice. Rows without answers or without an ID are
dropped; `isComplete` is not used, because an unfinished row can hold every answer. A row whose answers are all
in a fuller row of the same participant and session is dropped as a repeat; two different attempts stay, and
`survey convert --duplicate-handling` decides (rows are ordered by `responseDate`, so `keep_first` is the
earliest, `keep_last` the latest). Every drop and merge is printed as a note.

**`survey import-lsq`** — turn a single LimeSurvey question (`.lsq`) or question group
(`.lsg`) export into a PRISM template JSON, like Studio's Template Editor
"Import .lsq/.lsg" button:

```bash
python prism_tools.py survey import-lsq --input mood.lsq --output survey-mood.json
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

Recommended Excel columns (header-friendly, case-insensitive):

- `item_id` (aliases: id, code, variable, name) — the TSV column name
- `description` (aliases: question, text, item)
- `units` (aliases: unit) — **required** by the biometrics schema
- `datatype` (optional; one of: string, integer, float)
- `minvalue` / `maxvalue`, `warnminvalue` / `warnmaxvalue` (optional)
- `allowedvalues` (optional; comma/semicolon list or `1=foo;2=bar`)
- `group` (aliases: test, instrument, category) — optional; creates one
  `biometrics-<group>.json` per group. If omitted, all rows go into
  `biometrics-biometrics.json`. Special case: set `group` to `participant` to
  write those rows to `participants.json` instead.
- `alias_of` (optional)
- `session` / `run` (optional; normalized to `ses-<n>` / `run-<n>`, written
  to the metric entries as `SessionHint`/`RunHint`)

Optional per-group metadata columns (repeatable on any row; the first
non-empty value per group is used to fill the JSON header): `originalname`
(or `test_name`/`testname`) → `Study.OriginalName`; `protocol` →
`Study.Protocol`; `instructions` → `Study.Instructions`; `reference` (or
`citation`/`doi`) → `Study.Reference`; `estimatedduration` (or `duration`) →
`Study.EstimatedDuration`; `equipment` → `Technical.Equipment`; `supervisor`
→ `Technical.Supervisor` (enum: investigator|physician|trainer|self).

Labeled values like `0=selten;1=manchmal;2=...` in `allowedvalues` are stored
as `Levels` (value→label) **and** used to derive `AllowedValues`. A numeric
range like `1-10` in `allowedvalues` expands to allowed integers 1..10.

If no header row is present, positional columns map in order: item_id,
description, units, datatype, minvalue, maxvalue, allowedvalues, group,
alias_of, session, run.

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

# Repeated IDs without a session column (LimeSurvey): number each ID's rows 1, 2, ... by date
# (default column startdate, falling back to datestamp); works on preview, convert and merge
python prism_tools.py participants merge --input /absolute/path/to/survey_archive.lsa --id-column token --sessions-from-date --project /absolute/path/to/my-project/project.json --json

# Repeated rows per ID: identical values collapse quietly. A value that changes between an ID's rows
# (e.g. age across sessions) is an error unless you keep ONE session (--session-column + --session)
# or one column per session (--session-column + --split-sessions: age@ses-1, age@ses-2)
python prism_tools.py participants convert --input /absolute/path/to/T1.xlsx --id-column ID --session-column session --split-sessions --project /absolute/path/to/my-project/project.json --json

# Save a reusable mapping (preferred target: <project>/code/library)
python prism_tools.py participants save-mapping --mapping-json '{"participant_id": {"source_column": "ID"}}' --project /absolute/path/to/my-project/project.json

# Fetch the Neurobagel vocabulary + sample local participants.tsv columns,
# to inform building a --neurobagel-schema payload for convert/merge/save-mapping
python prism_tools.py participants neurobagel-schema --project /absolute/path/to/my-project --json

# Save a participants.json schema (canonicalizes participant-ID-like fields).
# Matches Studio's Neurobagel widget "Save Annotations" action.
python prism_tools.py participants save-schema --project /absolute/path/to/my-project --schema-json schema.json

# Make participants.tsv BIDS-friendly (numeric columns, numeric sex codes -> M/F/O).
# Matches Studio's "Fix participants.tsv for BIDS" action.
python prism_tools.py participants fix-bids --file /absolute/path/to/my-project/participants.tsv --dry-run
```

### Session map

**One timepoint (`Timepoints: single`):** every import writes `ses-1`, whatever session label the
data carries; a label other than `1` is reported ("session label 'pre' was written as ses-1"), and
two labels for one participant meet the normal duplicate check. This is a project rule you chose on the
Projects page, not label normalization. It covers `survey convert`, the participants importer,
`biometrics convert`, `convert physio` batch import and the environment importer.

**Several timepoints (`Timepoints: multiple`):** every session label in an import must be mapped by you
in `code/session_map.json`. Labels stay exact strings: `1`, `01` and `pre` are three different
labels, and even `1 -> 1` has to be written down once. Several source labels may map to one
session (`T0 -> 1` and `pre -> 1`). PRISM only *proposes* defaults `1, 2, 3` in order of appearance
(`session-map suggest`, pre-filled and editable in the Studio panel); nothing is saved until you save
or pass `--apply`. Existing converted data is never rewritten.

```bash
# Show the declaration and the map
python prism_tools.py session-map show --project /absolute/path/to/my-project --json

# Map one source label (exactly as it appears in the data) to a session name (letters and digits)
python prism_tools.py session-map set --project /absolute/path/to/my-project --label pre --target 1
python prism_tools.py session-map set --project /absolute/path/to/my-project --label T0 --target 1

# Propose defaults 1, 2, 3 for labels without an entry (add --apply to save them)
python prism_tools.py session-map suggest --project /absolute/path/to/my-project --label pre --label post

# Remove a mistyped entry (exact label)
python prism_tools.py session-map unset --project /absolute/path/to/my-project --label pree
```

### Session order (content sessions)

For projects with several timepoints you declare under Study Design (`StudyDesign.SessionLabels`)
what the sessions are:

- **time:** sessions are waves in the same order for everyone (`ses-1`, `ses-2` or `pre`/`post`).
  The session map above names them. This is what a project without the field does.
- **content:** sessions are conditions whose order differs per participant (for example `sleepdep`
  and `rested` in counterbalanced order); you then provide each participant's order, and the folders
  are named after the condition (`ses-rested`, not `ses-2`).

LimeSurvey stores only dates, so PRISM still numbers each participant's completed responses `1`, `2`,
... by date (see `sessions review`); in a content project the session order then turns those numbers
into names. Record it in `code/session_order.tsv` (columns `participant_id`, `session_number`,
`session`), with `participant_id` exactly as in the survey data (a leading `sub-` is ignored) and the
session names letters and digits only. PRISM never creates or guesses an order: a participant who is
missing, or whose number of responses differs from their recorded sessions, stops the import with a
list of who is affected. Name such responses yourself in the review (`sessions set --session
sleepdep`); a response you name is final.

```bash
# Show the declaration and the recorded order
python prism_tools.py session-order show --project /absolute/path/to/my-project --json

# One participant at a time ...
python prism_tools.py session-order set --project /absolute/path/to/my-project --participant P01 --number 1 --session sleepdep
python prism_tools.py session-order set --project /absolute/path/to/my-project --participant P01 --number 2 --session rested

# ... or a prepared .tsv/.csv/.xlsx (merged into what is recorded; --replace replaces it)
python prism_tools.py session-order import --project /absolute/path/to/my-project --file order.xlsx

# Remove a participant, or only one number of theirs
python prism_tools.py session-order unset --project /absolute/path/to/my-project --participant P01 --number 2
```

`survey convert` and the participants importer stop with the list of unmapped labels until
they are all in the map. In a longitudinal project `survey convert` imports every session of
a file with a session column (it never silently picks "the first one"); use
`--session <label>` to import one session, or to label a file that has no session column
(the label must be in the map). If `--project` is omitted but `--output` is a PRISM project,
that project's rules apply.

**`sessions review|set|unset`** — repeated LimeSurvey responses (one row per start, no
session column). Sessions come from *completed* responses (`submitdate` filled), numbered
by `startdate`/`datestamp`; incomplete ones are left out. Review, then override:

```bash
python prism_tools.py sessions review --input survey_archive.lsa --id-column token --project /abs/path/my-project
python prism_tools.py sessions review --input survey_archive.lsa --id-column token --project /abs/path/my-project --skip-existing  # only responses not yet imported
python prism_tools.py sessions set --project /abs/path/my-project --survey 999999 --response 502 --session pre
python prism_tools.py sessions set --project /abs/path/my-project --survey 999999 --response 501 --skip
python prism_tools.py sessions set --project /abs/path/my-project --survey 999999 --response 503 --include
python prism_tools.py sessions unset --project /abs/path/my-project --survey 999999 --response 502
```

`set` takes exactly one of `--skip` (leave a response out), `--include` (take an incomplete
response anyway; it is numbered by date like a completed one) or `--session <label>`.

`review` also takes `--date-column` (default `startdate`, falls back to `datestamp`) and `--json`
(adds `survey_id`); the text output starts with `Survey: <id>`. LimeSurvey numbers responses
1..N per survey, so decisions are scoped by survey: the id is the number in the `.lsa`
(`survey_<id>.lss`), shown by `review`, and passed as `--survey` to `set`/`unset` (default
`default`, which is what every non-`.lsa` file uses).

Decisions are saved in `code/session_assignments.json`, per survey and keyed by response id, so
they survive re-exports:
`{"version": 2, "surveys": {"999999": {"responses": {"502": {"session": "pre"}, "501": {"skip": true}, "503": {"include": true}}}}}`.
`survey convert --duplicate-handling sessions` and `participants … --sessions-from-date` apply
them automatically.

The legacy `survey import-limesurvey-batch --session-map t1:ses-1,...` is a different,
older per-import rename of LimeSurvey archives. It is refused when the output folder is a
PRISM project (one or several timepoints): use `survey convert`, which enforces the project's
session rule. In a one-timepoint project, `survey convert` with repeated responses that would be
numbered into several sessions stops with a message; declare several timepoints first.

### Settings

The Settings page as commands. `settings set` changes only the options you name; switches take `on` or `off`.

```bash
python prism_tools.py settings show
python prism_tools.py settings set --datalad-for-new-projects on
python prism_tools.py settings set --personal-library-path /absolute/path/to/my-library
```

### Publish

Pushes a DataLad dataset on a department share to its server sibling, but only if the
dataset validates. Refusals are exit code `1` (validation errors) or `2` (anything else:
no identity, no sibling, not a dataset, uncommitted changes (run `datalad save` first), bad `--as`, existing hook). Success is `0`.

```bash
# Validate and push (identity: --as, else PRISM_USER_NAME/PRISM_USER_EMAIL, else git config)
python prism_tools.py publish --project /absolute/path/to/share/my-project --as "Ada Lovelace <ada@example.org>" --json

# Validate only; exit 1 on errors (this is what the pre-push hook runs)
python prism_tools.py publish --check --project /absolute/path/to/share/my-project

# Install the git pre-push hook that enforces the same rule on plain `git push`
python prism_tools.py publish --install-hook --project /absolute/path/to/share/my-project
```

Options: `--project` (required), `--sibling`, `--as "Name <email>"`, `--allow-invalid`, `--check`,
`--install-hook`, `--json`. `--allow-invalid` sends the dataset despite validation errors (you acknowledge them);
the result is `pushed_with_errors`, still lists the errors, and the audit log records it with the error count. See [DataLad](DATALAD.md#publishing-from-a-department-share)
for the hook's requirements and limits.

### Methods section and preregistration draft

```bash
python prism_tools.py methods generate --project /path/to/project \
    [--detail brief|standard|detailed] [--format md|html|docx|tex|bib] [--output FILE]
python prism_tools.py preregistration draft --project /path/to/project \
    [--format md|html|docx|tex] [--output FILE]
```

`methods generate` builds a paper-ready Methods text from `project.json`, the
task templates, the BIDS sidecars (scanner/sequence parameters, counts per
session), the scoring recipes and the PRISM version. Gaps (no sample size, an
instrument without a citation) are printed to stderr as warnings and are never
invented. `--format bib` writes the instrument references as BibTeX; the `.tex` output cites them with `\citep{key}` and ends with `\bibliography{references}`, so save the bib as `references.bib` next to the `.tex` and compile with `pdflatex`, `bibtex`, `pdflatex` twice (citations without a readable author and year stay plain text). `docx`
needs `--output` and the `python-docx` package (exit code 2 otherwise); the Studio
Projects page offers the same downloads (Word, TeX, BibTeX).

### Save gate

Refuses a `git commit` in a PRISM dataset unless the dataset validates (a git pre-commit
hook in every dataset root, including nested `sub-*` datasets, calls `save-gate --check`).
The very first commit of a dataset is exempt. Exit codes: `0` allowed/ok, `1` refused because of
validation errors, `2` any other problem (cannot read git state, validator crashed, bad path, foreign hook, no action chosen).
The hook blocks on any non-zero exit. Each `--check` appends a line to the audit log.

```bash
# Validate; exit 1 if the commit must be refused (this is what the hook runs)
python prism_tools.py save-gate --check --project /absolute/path/to/my-project

# Install the pre-commit hook in the project and every nested dataset
python prism_tools.py save-gate --install-hooks --project /absolute/path/to/my-project

# Show which datasets have the hook
python prism_tools.py save-gate --status --project /absolute/path/to/my-project --json
```

Options: `--project` (required), `--check`, `--install-hooks`, `--status`, `--json`.

Hook requirements and limits:

- The hook runs `$PRISM_TOOLS save-gate --check ...` (default `prism_tools`). `PRISM_TOOLS` must be
  an **executable file**; if the hook cannot find it, the commit is blocked.
- `git commit --no-verify` bypasses the hook.
- The hook lives in each repository's `.git/hooks`: it is per clone and per dataset. A fresh
  clone is ungated until `--install-hooks` runs there.
- A pre-existing foreign `pre-commit` hook is never overwritten (reported, exit `2`).

### Environment

**`environment preview`** / **`convert`**:

```bash
python prism_tools.py environment preview --input /absolute/path/to/environment.xlsx --json

# --timestamp-col is required for convert
python prism_tools.py environment convert \
  --input /absolute/path/to/environment.xlsx \
  --project /absolute/path/to/my-project --timestamp-col collected_at

# Summarise a variable over a time window before the session (repeatable):
# VAR:DURATION:STAT, STAT is mean|min|max|sum|count, DURATION is ISO 8601 (P3D, PT12H; no years/months)
python prism_tools.py environment convert --input environment.xlsx --project my-project \
  --timestamp-col collected_at --window temp_c:P3D:max --window precip_mm:PT12H:sum
```

The converter writes environment format 2.0.0 (term columns, no `Privacy` block). Windows are half-open
(session - duration, session]; rows left empty or built from a partial window are listed as `window_problems` in the `--json` result.
Each window becomes a column named `<var>_<stat>_<duration lowercased>`, for example `temp_c_max_p3d` or
`precip_mm_sum_pt12h`; a repeated window is written once. A project still pinned to environment 1.1.0 is moved to the
current version (`environment schema pin 1.1.0 -> 2.0.0` in the log and as `schema_pin_change` in the result).

**`environment scan-mri`** — scan a project's rawdata for MRI acquisition
timestamps/scanner-site location from existing BIDS JSON sidecars, writing a TSV
usable with `environment convert --input`. Matches the Studio GUI's
Environment/MRI tab "Scan Project MRI Data" action:

```bash
python prism_tools.py environment scan-mri --project /path/to/project --output mri_scan.tsv
python prism_tools.py environment convert --input mri_scan.tsv --project /path/to/project \
  --timestamp-col timestamp
```

### Physio

**`convert physio`** — Varioport (`.raw`/`.vpd`) recordings from a `sourcedata`
directory or single file:

```bash
python prism_tools.py convert physio --input ./sourcedata --output ./rawdata --task rest --suffix ecg --sampling-rate 256
```

**`physio batch-convert`** — batch-convert physio files sitting in a
flat source folder (distinct from `convert physio` above):

```bash
python prism_tools.py physio batch-convert --input ./flat_source_folder --output ./converted
```

### Wide-to-long and version merging (dispatched via `prism.py`)

**`wide-to-long`** — convert a wide survey-style table into long format by matching
session indicators in column names:

```bash
# Inspect matches without writing output
python prism_tools.py wide-to-long --input build/Limesurvey_gesamt.xlsx --session-indicators T1_,T2_,T3_ --inspect-only

# Convert and write
python prism_tools.py wide-to-long --input survey_export.xlsx --output survey_export_long.csv --session-indicators T1_,T2_,T3_
```

Key options: `--session-indicators` (comma-separated tokens, e.g. `T1_,T2_,T3_` or
`_pre,_post`), `--session-map` (e.g. `T1_:pre,T2_:post`), `--inspect-only`,
`--preview-limit`, `--force`. Output format is inferred from the extension
(`.csv`/`.tsv`/`.xlsx`). A column-name indicator appearing more than once is treated
as ambiguous and refused until made more specific.

**`merge-versions`** — merge a new instrument version into an existing template into
a single multi-variant template:

```bash
python prism_tools.py merge-versions survey-bdi.json bdi_long.xlsx                      # auto-detects version names
python prism_tools.py merge-versions survey-bdi.json bdi_long.json --new-version long --existing-version short
python prism_tools.py merge-versions survey-bdi.json bdi_long.xlsx --dry-run            # preview only
```

### Dataset utilities, anonymize, and export

**`dataset build-hostile-demo`** / **`cleanup-project-metadata`** /
**`rename-subjects`** / **`rewrite-entities`**: build an adversarial test dataset,
remove legacy converter-written session metadata, rename subject IDs, or
rename/delete a non-subject BIDS entity (task/acq/run/ses/etc.) — both rewrites are
DataLad-aware (one commit per subject where tracked). Less common maintenance
operations — run `python prism_tools.py dataset <action> --help` for full flags.

```bash
python prism_tools.py dataset build-hostile-demo --output /tmp/prism_hostile_demo   # a finished project: required fields set, sessions 1 / 01 / pre mapped one-to-one
python prism_tools.py dataset cleanup-project-metadata --project /path/to/project
python prism_tools.py dataset rename-subjects --project /path/to/project --mode last3 --dry-run
python prism_tools.py dataset rewrite-entities --project /path/to/project --list-modalities
python prism_tools.py dataset rewrite-entities --project /path/to/project \
  --modality func --entity task --replacement rest --dry-run
```

**`dataset validation-matrix`** — how well does the validator catch real mistakes? It builds a
small clean control project (three participants, one survey, required fields set), applies about
thirty known defects **one at a time** to fresh copies (missing or broken files, bad names, wrong
values, undeclared tasks, a participants.tsv that misses a subject, ...) and runs the validator on
each. Every defect names the PRISM code the issue catalogue promises; the output says per defect
`detected`, `wrong_code` (other issues reported instead) or `missed`, and which of the two ways of
validating reported it (`validate` is what `prism.py` runs; `project` is the Projects page check,
which also covers project.json, participants.tsv and .bidsignore). The control project is kept in
`--output` so you can run the validator on it yourself. Exit code 1 when the control is noisy, a
defect is newly missed, or a documented gap (`KNOWN_GAPS` in `src/validation_matrix.py`) is now closed.

```bash
python prism_tools.py dataset validation-matrix --output /tmp/prism_matrix [--json]
```

**`dataset rename-sessions`** / **`renumber-runs`** / **`undo`** — the CLI equivalents
of Studio's File Management session rewrite, run renumbering, and "Undo Last
Operation". Session labels are rewritten only by the rule you give (`ses-1` and
`ses-01` stay distinct); `renumber-runs` closes gaps such as `run-01`, `run-03` →
`run-01`, `run-02`; `undo` reverses the most recent of these File Management
operations. All three support `--dry-run`, `--yes`, and `--json`.

```bash
python prism_tools.py dataset rename-sessions --project /path/to/project \
  --example-session ses-baseline1 --keep-fragment baseline --dry-run
python prism_tools.py dataset renumber-runs --project /path/to/project --dry-run
python prism_tools.py dataset undo --project /path/to/project --dry-run
```

**`anonymize`** — randomize participant IDs and/or mask copyrighted question text,
the CLI equivalent of Studio's Standard Export anonymization (see
[Export](studio/export.md)). `recipes surveys/biometrics --anonymized` does the
same participant-ID pseudonymization scoped to that command's output (plus
`--mask-questions`/`--id-length`/`--random-ids`); `anonymize` operates on a whole
dataset copy instead.

**`file-management delete-files`** / **`remove-scans-tsv`** / **`rename-physio`** —
preview or delete project files matching BIDS entity filters, delete every
`*_scans.tsv` file across a project (DataLad-aware where applicable), or
regex-rename a folder of physio files (with optional
`{subject}`/`{session}` folder-path placeholders and BIDS-organized output) —
the CLI equivalents of Studio's File Management -> Delete Files / "Delete all
scans.tsv" / Physio Renamer actions. Also runnable as `prism.py
file-management ...` (delegates into the same `prism_tools.py` command tree,
like `wide-to-long`).

```bash
python prism_tools.py file-management delete-files --project /path/to/project \
  --modality func --entity-filter task=RS                # preview only
python prism_tools.py file-management delete-files --project /path/to/project \
  --modality func --entity-filter task=RS --apply --yes   # actually delete
python prism_tools.py file-management remove-scans-tsv --project /path/to/project --yes
python prism_tools.py file-management rename-physio --input /path/to/raw \
  --pattern '^VP_' --replacement 'clean_'                 # preview only
python prism_tools.py file-management rename-physio --input /path/to/raw \
  --output /path/to/renamed --pattern '^VP_' --replacement 'clean_' --apply
```

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

### JSON Editor

**`json-editor save`** — save a BIDS sidecar JSON file (`dataset_description`,
`participants`, `samples`, or `task-<name>`) into a project, with the same
post-save validation the Studio GUI's JSON Editor "Save to Project" action runs:

```bash
python prism_tools.py json-editor save --project /path/to/project \
  --type participants --file participants.json
```

## Scripts in `scripts/`

Most files under `scripts/` are implementation details called by the CLIs. If
you're a new user, prefer `prism-validator ...`, `python prism_tools.py ...`, and
`python prism-studio.py` instead of calling scripts directly.

## DataLad server (setup check, get latest, sync)

Checks that this machine can use DataLad with a DataLad server: Git, git-annex, DataLad,
the SSH client, an SSH key (set up by your IT admin, not by PRISM), and (with a server URL) a real key-based login. Each failed
check prints what to do; the exit code is 1 if anything failed. The Studio GUI calls the
same function (`GET /api/projects/datalad/doctor?url=...`).

```bash
python prism_tools.py datalad doctor
python prism_tools.py datalad doctor --url user@server.example.org:/data/study
python prism_tools.py datalad doctor --url user@server.example.org:/data/study --json
```

`update` gets what others have saved on the server. It only fast-forwards (it never
merges), refuses while the project has unsaved changes, and skips a project that has no
server yet. `sync` runs `update`, then sends your saved changes, and only if the dataset
validates; unsaved changes must be saved first. The server is the project's `origin`
(or `--sibling-name`). `--allow-invalid` sends despite validation errors (as `datalad save --allow-invalid`
saves); the result is `pushed_with_errors` and the audit log records it. Exit codes: 0 ok, 1 refused or failed, 2 bad usage.

```bash
python prism_tools.py datalad update --project /absolute/path/to/my-project
python prism_tools.py datalad sync --project /absolute/path/to/my-project
```

`put-on-server` is for the first person: it creates the project's dataset at `--location` (a local or network
folder such as `/srv/lab/study` or `C:\share\study`, `user@host:path`, or `ssh://host/path`; web addresses and
values starting with `-` are refused), names it `origin` (or `--sibling-name`) and then sends it like `sync`. Before
anything is created on the server it refuses a project that already has that server (use `sync`), a folder that is
not empty ("open it from the server instead"), unsaved changes, validation errors (unless `--allow-invalid`) and a
public host while `sourcedata/` is tracked. Nested subject datasets are created too. If the send is interrupted after
the server dataset exists, run `sync`. Studio's `POST /api/projects/datalad/put-on-server` runs the same function as a
job (`location`, `sibling_name`, `allow_invalid`, and `name`/`email` for `--as`). An ssh location whose user or server
name starts with `-` or contains spaces, and any location containing `::` (git transport helpers), is refused.

```bash
python prism_tools.py datalad put-on-server --project /absolute/path/to/my-project --location user@lab.example.org:/data/study
```

`open-from-server` is for everybody else: it needs no project. It clones the project at `--location` (same forms and
refusals as `put-on-server`; a relative folder is relative to your working directory) into `--target`, an empty or new
folder given as a full path, with the server as `origin`. It installs the nested subject datasets level by level without
their data (fetch it with Get data). Before a dataset's nested datasets are installed, its own files are checked; a
failed check stops the install. What is checked: the dataset was checked out completely (`git status`, at most 60
seconds); its committed `.datalad/config` holds only `datalad.dataset.id` and its `.gitmodules` only `path`, `url` and
`datalad-id` (any other setting could redirect an address); `.datalad`, `.datalad/config` and `.gitmodules` are not
links; every `url` is a relative path inside the dataset (what DataLad writes, `./sub-01`) or an address under the
exact `--location`; every `path` is a nested dataset recorded in that very dataset (not a deeper path such as
`sub-01/ses-1`, not a link) and a real folder. For a folder location (the server is read on your computer), the
location, every folder down to each nested dataset's source on the server and each of their `.git` must be real
folders (a link or a `gitdir:` file is refused) without `.git/objects/info/alternates`, and no copied dataset may end
up with an alternates file (either would make the copy read another repository of your computer). For an ssh location
the addresses are resolved on the server and are not checked on your computer beyond the rules above. The server's own
`origin` is not added to your copy. Known limitation: a nested dataset recorded with `datalad-url` (DataLad writes it
when a subdataset was added from an address rather than created in place; PRISM never does) cannot be opened this way. The save-gate hook goes into every dataset as soon as it is there (git
does not copy hooks). It stops before cloning when the target is not a full path, not empty, or inside a git
repository, when DataLad, git or git-annex is missing, or git does not know your name and email (`reason`:
`bad_location`, `bad_target`, `target_not_empty`, `no_datalad`, `no_identity`, `clone_failed`). If a nested install
fails after the clone, the copy is left incomplete (and gated): delete the folder named in the message, then try again.
Studio's `POST /api/projects/datalad/open-from-server` (`location`, `target`) runs the same function as a job (a target
that is not a full path is refused with 400) and then opens the new copy as the current project.

```bash
python prism_tools.py datalad open-from-server --location user@lab.example.org:/data/study --target ~/projects/study
```

`get-data --project <root> [filters] [--json]` fetches the data (MRI, physio, ...) of your own copy from the server
(`origin`). It takes the export's filter flags, added by the same helper to the `export` commands:
`--exclude-subject`, `--exclude-session`, `--exclude-modality`, `--exclude-acq MODALITY=LABEL`, `--exclude-task MODALITY=TASK`,
`--include-sourcedata`, `--no-derivatives`, `--no-code`, `--include-analysis` (same defaults as the export). Without filters
everything the defaults keep is fetched. A project without `origin` is not an error (`skipped: true`, exit 0, "nothing to fetch
from"); an unreachable server, or files no server has (listed in the message and in `failed_paths`), exit 1. Studio's
`POST /api/projects/datalad/get-data` runs the same function as a job (the filters under the export page's option names,
e.g. `exclude_subjects`). The selection itself is `src/export_selection.py`, which the export's "fetch annexed content"
step uses too.

```bash
python prism_tools.py datalad get-data --project ~/projects/study --exclude-subject sub-02 --exclude-modality physio
```

`status` shows how many changes are unsaved and the one next step the DataLad page offers
(`install_datalad`, `enable`, `put_on_server`, `save` or `sync`; `save` also when the unsaved changes cannot be counted, `checked: false`). `--check-server` asks the server whether it can be reached
(10 s limit; an unreachable server is reported as `reachable: false`, never an error, and never changes
the next step), `--validate` adds `valid` and `error_count`, `--json` prints what Studio's `GET /api/projects/datalad/state`
returns. A server not called `origin` is listed in `other_servers`.

```bash
python prism_tools.py datalad status --project /absolute/path/to/my-project --check-server --json
```

On Windows the install hint is: install Git for Windows, then (without uv)
`py -m pip install datalad git-annex` and restart PRISM Studio (macOS/Linux:
`uv tool install datalad --with-executables-from git-annex`).

## modality propose

Check a modality proposal and generate its schema, example sidecar, fixture
dataset and `REGISTRATION.md`.

    python prism_tools.py modality propose <proposal.xlsx|.yml|.json> --sample <file> [--out <dir>] [--check] [--json]

- `--sample`: synthetic sample data file (required).
- `--out`: output folder (required unless `--check`). The proposal may add a suffix to an existing modality; `--out` then writes no schema file.
- `--check`: validate only, write nothing.
- `--json`: machine-readable output.

Exit code 0 on success, 1 if any problem is an error, 2 if `--out` is missing
without `--check`. See `MODALITY_PROPOSALS.md`.

## terms

Look up the shipped metric terms (the term registry, see the Terms section of
`specs/biosample.md`).

    python prism_tools.py terms list [--modality biosample] [--json]
    python prism_tools.py terms show <term> [--modality biosample] [--json]
    python prism_tools.py terms suggest <column> [--specimen saliva] [--modality biosample] [--json]
    python prism_tools.py terms propose (--sidecar <sidecar.json> | --data <file.tsv>) --column <column> [--label TEXT] [--open] [--out FILE] [--modality biosample] [--json]

- `list`: every term with its level, units and status.
- `show`: one term; `<term>` is an ID (`prism:cortisol`), a local name, a label, an alias or an equivalent. Exit code 1 if it is unknown.
- `suggest`: how the validator relates a column name to the registry (`suggestion`, `unknown`, ...) and which official terms look similar.
- `propose`: builds a proposal for a new metric from a column of your sidecar (a new analyte gets a parent and a child term, a known analyte with a new specimen only a child) and checks it with the rules of the specification repository. **Nothing is sent** unless you add `--open`, which opens a prefilled "Propose a Metric" form in the [prism-specification](https://github.com/MRI-Lab-Graz/prism-specification) repository in your browser (if the link would be too long, the command prints the form address and you paste the proposal). A bot checks it there and a maintainer takes it from there; the maintainers may choose a different ID or name, and your column name is kept as an alias. `--label` sets the name of the new term (default: the column name, or the name of a `Term` the column already carries). `--out FILE` also saves the proposal document (format v2), for sending to a maintainer if you do not use GitHub. Give either the sidecar that defines the column and `Technical` (`--sidecar`), or a data file (`--data`, a `.tsv`): then its sidecar is resolved with BIDS inheritance (root-level merged with subject-level), exactly as the validator reads it. - `local add-values`: allows new values of an enum field of the biosample schema in this project, for example `--field Technical.SpecimenType --value sweat` (lowercase letters, digits and `-`). They are stored in `code/specification/patches/biosample.json` (a schema patch: `add_enum_values`, checked by the vendored `schema_patch.py`) and the validator uses them from the next run; a value the official schema has is left out and reported. A value outside such a field's enum prints this command in the validator's error. Exit code 1 for a field that cannot be extended or a value that is not allowed; a broken patch file is never overwritten.
- `local remove-values`: removes values added this way; removing the last one removes the file. `local list` shows these items as layer 2 (`local`, `now-official` or `invalid`).
- `propose --patch`: shares the schema additions (file `patches/biosample.json` of the proposal); `--all` includes them, and a term whose specimen only a local addition provides brings them along. The maintainers' bot applies the patch to the real schema and prepares the release (archive, minor version, regenerated spec page) for review.

The validator's "not an official metric" notice prints the matching `--data` command. Exit code 1 if the metric is already official (the message names the term to use with `Term`), the sidecar or column cannot be read, or the proposal fails the checks.

## spec

Your project's own, not yet official specification: metrics PRISM does not know yet, used in this project
right away, and sharing them later. They live in the project at `code/specification/terms/<modality>/` (one
JSON file per term, exactly the term a proposal carries) and are read by the validator together with the
official registry; the official registry always wins, and a local term never reaches another project.

    python prism_tools.py spec local list --project <project> [--json]
    python prism_tools.py spec local add-term --project <project> (--data <file.tsv> | --sidecar <sidecar.json>) --column <column> [--label TEXT] [--json]
    python prism_tools.py spec local remove --project <project> <term-id> [--json]
    python prism_tools.py spec local add-values --project <project> --field <field> --value <value> [--value <value> ...] [--json]
    python prism_tools.py spec local remove-values --project <project> --field <field> --value <value> [--value <value> ...] [--json]
    python prism_tools.py spec propose --project <project> (--term <term-id> [--term <term-id> ...] | --all | --patch) [--patch] [--out FILE] [--open] [--json]

- `local list`: every local item with its status: `local`, `now-official` (the official registry has it since; the official definition is used, remove your copy) or `invalid` (a file that was skipped, with the reason).
- `local add-term`: makes the metric of a column a local term (a new analyte gets a parent and a child, a known analyte with a new specimen only a child), after the same checks a proposal passes. The validator uses it from the next run; a column that carries `"Term": "<id>"` inherits its unit and range. Exit code 1 for an official metric (the message names the term to use), a name an existing term owns, or an unreadable source.
- `local remove`: removes a term; removing a parent also removes its local children.
- `propose`: the same as `terms propose`, for local terms: `--term` (repeatable) names the ones to share, `--all` shares every local term of the project in one proposal. A named child brings its local parent, a named parent its local children. Terms the official registry has adopted since are left out and listed (`skipped` in `--json`). The proposal is checked with the specification repository's rules and sent as a **format v2** document (`prism-proposal/2`: the files it adds, up to 40, at most 50,000 bytes); `--out FILE` saves that document, and with `--open` the prefilled form opens (a proposal too long for a link is pasted into the form's text field). **Nothing is sent** otherwise.

The validator's "not an official metric" notice prints the matching `spec local add-term` and `terms propose` commands. Studio's *Specifications → Propose changes* page does the same from a browser.

### Propose without a project

These need no project and send nothing unless you add `--open`; they are what *Specifications → Propose changes* runs.

    python prism_tools.py spec catalog [--json]
    python prism_tools.py spec propose-values --modality <modality> --field <field> --value <value> [--value <value> ...] [--not-sure] [--closest <name>] [--entry FIELD=VALUE ...] [--out FILE] [--open] [--json]
    python prism_tools.py spec propose-metric --name <name> --description <text> --units <units> --specimen <specimen> [--alias <name> ...] [--modality biosample|environment] [--level CODE=LABEL ...] [--cf-standard-name <name>] [--group <heading>] [--project <folder>] [--not-sure] [--closest <name>] [--entry FIELD=VALUE ...] [--out FILE] [--open] [--json]
    python prism_tools.py spec example --modality <modality> [--template <stem>] [--json]
    python prism_tools.py spec check-kind-name <name> [--json]
    python prism_tools.py spec propose-new-kind (--description <text> | --measured <text> --holds <text> [--device <text>] [--row <text>]) --sample <file> [--name <name>] [--closest <name>] [--out FILE] [--open] [--json]

- `catalog`: what can be proposed: the kinds of data, their lists with the values they allow, and the measurements PRISM already knows.
- `propose-values`: proposes missing choices in a list, for example `--modality biosample --field Technical.SpecimenType --value sweat`. A value the list already has is reported and left out.
- `propose-metric`: proposes a missing measurement (`--name`, what it measures, `--units`, the `--specimen` it is taken from; `--alias` adds other names). `--project` also accepts the sample types that project added. A measurement PRISM already has is reported with the term to use. For `--modality environment` there is no sample type: give `--units` (for example `dB`) or `--level CODE=LABEL` (repeatable), and optionally `--cf-standard-name`. `--group <heading>` (1-60 characters) lists the new measurement under that heading, as the Propose changes page does.
- `example`: prints an example of a kind of data from its library template (`--template` picks one by stem, default the first), so you can see what an entry looks like before proposing.
- `check-kind-name NAME`: says whether a suggested name for a new kind of data is free (names BIDS or PRISM use are refused); the page asks the same while you type.
- `propose-new-kind`: proposes a kind of data PRISM does not have: `--description` says what the data is and how it is recorded (or give it in parts: `--measured`, `--holds`, and optionally `--device` and `--row`, as the page does), `--sample` is a sample data file (UTF-8 text) that you paste into the form yourself, `--closest` names the closest existing kind, `--name` suggests a name (lowercase letters and digits; a name BIDS or PRISM already uses is refused). `--out FILE` saves the proposal text; `--open` opens the prefilled prism-specification form.
- `--not-sure` (on `propose-values` and `propose-metric`) says you do not know which kind of data this belongs to; `--closest` then names the nearest one. `--entry FIELD=VALUE` (repeatable) adds a field you filled in.
- `--out FILE` also saves the proposal document (format v2); `--open` opens the prefilled form on GitHub. `biosample` and `environment` can be proposed as measurements.

## modality-version

Per-modality schema versions and the pins in a project's `project.json`
(see [Schema versioning](SCHEMA_VERSIONING.md)).

    python prism_tools.py modality-version status <project> [--json]
    python prism_tools.py modality-version list [<name>] [--json]
    python prism_tools.py modality-version pin <project> [<name> ...] [--json]
    python prism_tools.py modality-version update <project> <name> [--json]
    python prism_tools.py modality-version freeze <project> <name> [--json]

- `status`: the pinned versions and the updates not yet decided.
- `list`: the available versions of one modality, or of all.
- `pin`: pin the named modalities, or those with data in the project; modalities already pinned are left alone. For projects created before pinning existed.
- `update`: move a pinned modality to the latest version.
- `freeze`: keep the pinned version and stop reporting the newer one.
- `--json`: machine-readable output (`{"success": true, ...}`, or `{"success": false, "error": ...}`).

`<project>` must contain a readable `project.json`. `update` and `freeze` fail
for a modality that is not pinned. Exit code 0 on success, 1 on error.
