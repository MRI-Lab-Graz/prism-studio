# Modality Registration Workflow Design

Date: 2026-10-15
Status: Draft, awaiting review
Supersedes: `2026-09-11-modality-contribution-workflow-design.md` (removed from
`main` in #135; see git history) for everything about how a proposal is
authored, parsed and turned into a PR. The CI checks already built on this
branch are kept (see "Reused").

## Motivation

PRISM's central claim is that a modality is not a fixed list: data belonging
to a subject is a data file plus a JSON sidecar, and new kinds of data can be
added. The first real case is a colleague's MRI study that also drew blood
samples. The specifics of that data are unknown; the workflow must not depend
on them.

The workflow must be usable by a researcher who works in Studio and a
spreadsheet, not in a terminal or YAML.

## Decisions

| Topic | Decision |
|---|---|
| Where a modality lives | Upstream only. A proposal becomes a PR to `prism-studio`; it is usable after merge and release. No per-project or per-installation modalities. |
| Registration | Manual. A maintainer adds the core registration; the generator never edits core files. It writes instructions instead. |
| Definition depth | Column dictionary, matching the existing modality schemas (`biometrics.schema.json`): per column `Description`, `Units`, `MinValue`/`MaxValue`, `AllowedValues`, datatype, plus `Technical`/`Study`/`Metadata` blocks. |
| User-facing input | An Excel workbook (`.xlsx`), like the existing survey and biometrics authoring workbooks. YAML/JSON accepted as an equivalent for CI and power users. |
| Sample data | Mandatory. A small, synthetic sample data file in the modality's real format. |
| Entry points | One backend generator, exposed via the CLI. The GitHub Issue Form bot is an adapter that calls the same CLI command. No Studio page in this phase. |

## Inputs

### 1. Proposal workbook: `modality_proposal_template.xlsx`

Shipped at `official/create_new_modality/modality_proposal_template.xlsx`,
next to `official/create_new_survey/`. Sheets `Modality` and `Columns`, plus the optional `Types`:

**`Modality`** (one data row):

| Column | Example | Rule |
|---|---|---|
| `Name` | `biosample` | lowercase `[a-z][a-z0-9]*`; becomes the schema filename and the data folder name |
| `Suffix` | `bloodchem` | lowercase `[a-z][a-z0-9]*` |
| `Extensions` | `tsv` | comma-separated, no leading dot |
| `Description` | `Venous blood samples drawn alongside MRI` | non-empty |
| `Rationale` | free text | non-empty |

**`Columns`** (one row per data-file column). The headers are the same as the
biometrics workbook (`ID`, `Description`, `Units`, `Min`, `Max`,
`AllowedValues`, `DataType`) plus `Scale` (see below), so the parsing helpers in
`src/converters/excel_to_biometrics.py` / `excel_base.py` are reused, not
copied.

The `Columns` sheet describes the **sample file**. It is an example, not a contract on future studies: two or three columns are enough, and every study defines its own columns in its own sidecar, using the generated example sidecar as the pattern. The optional `Types` sheet (see "Controlled vocabulary") is the part that keeps columns comparable across studies.

The template ships pre-filled with the blood example under the placeholder
name `biosample`/`bloodchem`. The real name is chosen with the colleague once
the data is known.

### 2. Equivalent YAML/JSON

The same content as a mapping (`modality`, `suffix`, `extensions`,
`description`, `rationale`, `columns: [...]`). Both readers produce the same
Python dict. That dict is the one internal contract.

### 3. Sample data file

One file in a declared extension, e.g. `bloodchem.tsv` with a few rows of
made-up values. Required; a proposal without it is rejected.

## Backend (`src/modality_contribution.py`, extends the existing module)

```
read_proposal(path) -> dict                  # .xlsx / .yml / .yaml / .json
check_proposal(proposal) -> list[Problem]    # names, collisions, columns
check_sample(proposal, sample_path) -> list[Problem]
build_modality_artifacts(proposal, sample_path, out_dir) -> list[Path]
```

All checks collect every problem (with sheet/row/column or file row/column)
instead of stopping at the first.

### Name and suffix collision check

Rejects a proposal whose modality name or suffix is already taken. Sources
are read live, nothing is hardcoded:

| Clash with | Source |
|---|---|
| PRISM modality names, suffixes, aliases | `app/schemas/stable/entities.schema.json` (`modalities`, `aliases`) |
| BIDS suffixes | `bidsschematools.schema.load_schema().objects.suffixes` |
| BIDS datatypes (the modality name is also the folder name) | `bidsschematools.schema.load_schema().objects.datatypes` |

The error names the existing meaning, e.g. "`blood` is a BIDS suffix: blood
radioactivity recordings in `pet/`". PRISM's `physio` and `events`
deliberately reuse BIDS suffixes with the same meaning. Such overlaps are a
maintainer decision during registration, so the generator rejects them and
does not offer an override.

### Column scale

`Scale` says what kind of variable a column is, which `DataType` (how it is
stored: string, integer, float) does not. It is optional, one of
`categorical`, `continuous`, `boolean`, and never guessed: a blank cell means
"not stated" (identifiers, times and free text legitimately have none). In the
workbook the cell is a drop-down. In the generated sidecar it is written as
`MeasurementScale` (not `Scale`, which survey recipes already use for scoring
levels). When given, it must agree with the rest of the column:

| Scale | Requires |
|---|---|
| `continuous` | `DataType` integer or float, no `AllowedValues` |
| `categorical` | `AllowedValues` (the categories) |
| `boolean` | exactly two `AllowedValues` (for example `yes; no`, `0; 1`) |

### Controlled vocabulary (`Type`)

Column names are free: each study names its own columns. To make columns
comparable across studies anyway, a modality can carry a controlled
vocabulary, the pattern `physio.schema.json` uses for channels: every column
definition may have a `Type` from a fixed list plus `other` as the escape
hatch. Harmonisation happens on `Type`, not on the column name.

- Optional. The proposal lists `types` (value and short description) in the
  workbook sheet `Types` or the `types:` key of the YAML. `other` is added
  automatically and must not be listed.
- The generated schema restricts `Type` to the list plus `other`; the example
  sidecar sets `Type` on the example columns that are measurements.
- `Type` is not required per column (identifiers and times are not
  measurements). New values are added later by an upstream pull request that
  bumps the schema version.
- Checks: values unique, matching `[A-Za-z0-9][A-Za-z0-9_-]*`, not `other`;
  a column `Type` must be in the list or `other`; a column `Type` while the
  proposal lists no types is an error.
- Out of scope: standard codes (for example LOINC) per type.

### Column dictionary check

- `ID` unique and non-empty; `Min <= Max`; `AllowedValues` parse; `DataType`
  one of the datatypes the biometrics converter already infers; `Scale` one of
  the three values and consistent with the column (table above).

### Sample check

- **Tabular** (`tsv`, `tsv.gz`): the header equals the `Columns` IDs exactly
  (no missing or extra columns). Every value respects its column's datatype,
  min/max and allowed values.
- **Non-tabular** (any other extension): only that the file exists, has a
  declared extension and is readable. Its content is not checked.
- **Privacy limits** (the sample ends up in a public issue and PR):
  - Hard errors: more than 50 rows, larger than 1 MB, a participant/subject
    column holding anything other than `sub-01`/`01`.
  - Warning for the maintainer: a column whose ID or values look like an
    identifier (name, birth date, email, phone).
  - The warning is a hint, not a guarantee. The real safeguards are the
    required "synthetic data only" checkbox in the Issue Form and maintainer
    review.

### Generated artifacts (`<out_dir>/`)

| File | Content |
|---|---|
| `<name>.schema.json` | draft-07, same envelope as `biometrics.schema.json`: the `Technical`/`Study`/`Metadata` blocks plus the shape of a column definition (`additionalProperties`); passes the existing `modality-schema-conventions` check. The column dictionary itself is written into the example sidecar, as in real templates. |
| `example_sidecar.json` | filled in from the proposal; validates against the generated schema |
| `fixture/` | minimal dataset via the existing `write_minimal_dataset`, with the **sample file** as the data file, paired with the example sidecar |
| `REGISTRATION.md` | the exact manual edits for a maintainer: the `entities.schema.json` entry (`kind: prism`, `suffixes`, `extensions`), where the schema file goes (`app/schemas/stable/`), and any other place found to need it during implementation |
| `proposal.<ext>` | copy of the original input, so the source stays reviewable |

Note from verification (2026-10-15): `schema_manager.load_all_schemas` now
derives the modality list from `entities.schema.json`, so the registration is
expected to be that entry plus the schema file. One display-only hardcoded set
remains in `app/src/reporting.py:995`. The end-to-end test (below) is the
authority on what `REGISTRATION.md` must list.

## CLI

```
prism_tools.py modality propose <proposal.xlsx|.yml|.json> --sample <file> --out <dir>
prism_tools.py modality propose <proposal> --sample <file> --check
```

- Registered in `app/src/cli/parser.py` with a handler in
  `app/src/cli/commands/modality.py`, which only calls the backend.
- Exit code 0 on success. On any problem, non-zero with all problems listed.
- `--check` validates the proposal and sample and writes nothing.

## GitHub adapter

### Issue Form (replaces the line-per-field form on this branch)

`.github/ISSUE_TEMPLATE/propose-modality.yml`, fields:

- No name input: the modality name lives in the workbook (the issue title is the fixed prefix `[Modality]: `).
- Two textareas, `Proposal file` and `Sample data file`, each for one dragged-in file. GitHub turns them into `github.com/user-attachments/...` links.
- Rationale (textarea).
- Required checkbox: "The sample contains no real participant data:
  synthetic or fully de-identified values only."
- A link to download `modality_proposal_template.xlsx`.

### Bot (GitHub Actions)

`.github/workflows/propose-modality.yml`, triggered when an issue labelled
`type: new-modality` is opened. It has two jobs, split by trust. It has since
run on real issues (#179-#181, draft PR #182).

**`check` (untrusted).** Parses attacker-controlled files, so it has a
read-only token (`contents: read`), a checkout without persisted credentials
and no secrets. Issue-derived text reaches it only through `env:`. It reads
the two upload fields of the form (`Proposal file`, `Sample data file`); each
must contain exactly one `https://github.com/user-attachments/` upload. It
downloads them and runs `prism_tools.py modality propose ... --out
bundle/proposals/issue-<n>` in a directory outside the checkout, then uploads
the `bundle` (the `proposals/issue-<n>` output, `propose.log` and a `status`
file of `ok` or `failed`) as an artifact.

**`report` (privileged).** Has write permissions for contents, pull requests
and issues, and runs only trusted code: a fresh checkout of the default
branch. It downloads the bundle, verifies that it contains only plain files
and directories (no links or special files), and treats it strictly as data.
The issue number comes from the event, not from the bundle.

- On a failed check it comments the log on the issue (backticks stripped from
  the log), creates the `needs-changes` label if missing and adds it, and
  stops. The contributor opens a new issue with corrected files.
- On success, for issues opened by an OWNER, MEMBER or COLLABORATOR it copies
  `proposals/issue-<n>/` to a branch named `modality/issue-<n>-<run id>` and
  opens a **draft** PR against `main`, with the generated artifacts and both
  original files. For every other author it only comments that the automatic
  check passed and a maintainer will take it from here (anyone on GitHub can
  open an issue, so they do not get a branch in this repository).
- If the job itself fails, it comments on the issue that the bot could not
  finish and a maintainer will look.

Actions are pinned by commit SHA. The pure parts (attachment-link extraction,
PR body) live in `scripts/ci/modality_issue_to_files.py`; the GitHub API calls
are thin and untested.

PRs created with the workflow token trigger no workflows, so automatic checks
do not run on the bot's commit. A maintainer's registration push to the PR branch is what
runs the CI gate (`tests/test_modality_proposal_fixtures.py`).

## CI: two stages, because registration is manual

| Stage | When | Runs |
|---|---|---|
| Before registration | the bot's draft PR | `modality-schema-conventions` (runs in `ci.yml`); the sample check already ran in the bot |
| After registration | the maintainer has added the `REGISTRATION.md` edits to the same PR | `scripts/ci/flag_restricted_schema_changes.py` exists but is not wired into a workflow yet; `prism-validator` on `proposals/issue-<n>/fixture/` must pass |

A maintainer signs off before merge. CI cannot judge whether units are
semantically right or whether a modality duplicates an existing one under
another name.

## Reused from this branch (already built and tested)

- `tests/verify_repo.py` check `modality-schema-conventions`.
- `scripts/ci/flag_restricted_schema_changes.py` (core-file PR flag).
- `index.json` freshness check.
- `src/modality_contribution.write_minimal_dataset`.

Replaced: the Issue Form's line-per-field syntax and the planned
line-per-field parser.

## Testing (TDD, failing test first)

- **Readers:** the workbook and the YAML for the blood example yield the same
  dict. A missing sheet or header gives a clear error.
- **Collisions:** rejects `blood` (BIDS suffix), `pet` (BIDS datatype),
  `eyetrack` (PRISM suffix), `physiological` (PRISM alias); accepts a fresh
  name. Reads the live sources.
- **Column check:** duplicate ID, `Min > Max`, unknown datatype.
- **Sample check:** wrong header, out-of-range value, value outside the
  allowed list, more than 50 rows, foreign subject ID, each reported with
  row/column. Non-tabular is checked for existence and extension only.
  Identifier-like column produces the warning.
- **Generator:** the schema passes `modality-schema-conventions`; the sidecar
  validates against the schema.
- **CLI:** success exits 0 and writes all files; an invalid proposal exits
  non-zero listing every problem; `--check` writes nothing.
- **End-to-end registration:** copy the repo schemas to a temp dir, apply the
  edits `REGISTRATION.md` describes for the example modality, run
  `validate_dataset` on the generated fixture, expect zero errors. This fails
  if the registration instructions are wrong or incomplete.
- **Bot helpers:** attachment extraction (exactly one of each, user-attachments
  only), size limit, PR body.

Example inputs live in `examples/modality_proposal/` (workbook, YAML, sample
`.tsv`) and serve as test inputs and as the downloadable template's content.

## Out of scope

- Automatic registration (editing `entities.schema.json` from the generator).
- A Studio page. It can be added later as a thin adapter over the same
  command.
- Per-project or per-installation modalities.
- Moving the library into a separate repository.
- Content checks for non-tabular sample files.
