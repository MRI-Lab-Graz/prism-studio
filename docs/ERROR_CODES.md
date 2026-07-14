# Error Codes Reference

Use this page when validation gives you a PRISM code and you need to decide what
to fix first.

This page works best as a triage guide:

1. identify the code range
2. understand whether the issue is structural, metadata-related, or system-level
3. decide whether auto-fix is appropriate
4. re-run validation after the repair

This reference is generated from the canonical error-code registry in
`app/src/issues.py` — if it ever looks out of sync with what the validator actually
reports, that file is the source of truth.

## How PRISM codes are organized

All validation issues use structured codes in the form `PRISMxxx`.

| Code range | Category | Typical meaning |
|---|---|---|
| `PRISM0xx` | Dataset structure | The dataset root or top-level organization is broken or incomplete |
| `PRISM1xx` | File naming | Filenames or path entities do not match expectations |
| `PRISM2xx` | Sidecar and metadata files | Required JSON sidecars are missing, empty, or malformed |
| `PRISM3xx` | Schema validation | Metadata exists, but it does not satisfy schema rules |
| `PRISM4xx` | Content validation | TSV content values don't satisfy Levels/range rules from the sidecar |
| `PRISM5xx` | BIDS compatibility | BIDS-oriented compatibility issues or warnings |
| `PRISM6xx` | Consistency | Cross-subject/cross-session consistency warnings |
| `PRISM7xx` | Procedure/session declaration | On-disk data vs. `project.json`'s declared Sessions/Tasks |
| `PRISM9xx` | Internal/system errors | Internal validation failures |

## Recommended fix order

When you see multiple codes at once, this order is usually fastest:

1. fix dataset structure (`PRISM0xx`)
2. fix filename problems (`PRISM1xx`)
3. fix missing sidecars (`PRISM2xx`)
4. fix schema-required metadata (`PRISM3xx`)
5. fix content/value issues (`PRISM4xx`)
6. review BIDS, consistency, and procedure warnings afterward (`PRISM5xx`–`PRISM7xx`)

This prevents you from polishing metadata on a file that still needs to be moved
or renamed.

## Dataset structure errors (`PRISM0xx`)

### `PRISM001` — Missing `dataset_description.json`

Create the file at the dataset root with at least `Name` and `BIDSVersion`. Auto-fixable.

```json
{
  "Name": "My Dataset",
  "BIDSVersion": "1.9.0",
  "DatasetType": "raw"
}
```

### `PRISM002` — No subjects found in dataset

Ensure subject folders are named `sub-<label>` and located at the project dataset root.

### `PRISM003` — Invalid `dataset_description.json`

The file exists but its JSON syntax or required BIDS fields are invalid — validate
the syntax and repair missing fields.

### `PRISM004` — Missing `participants.tsv`

Create `participants.tsv` listing every subject, with at least a `participant_id`
column. In Studio, run the participants/sociodemographics import step instead of
hand-writing it.

### `PRISM005` — Schema version mismatch

The metadata uses an older or newer schema version than the validator. Update
`SchemaVersion` in your metadata files, or pass `--schema-version` to match.

### `PRISM006` — FAIR compliance issue in `dataset_description.json`

Add recommended metadata for FAIR compliance: `Description` (min 50 chars),
`License`, `EthicsApprovals`, `Funding`, `Keywords` (min 3), `Authors` with
ORCID/affiliation.

### `PRISM007` — Incomplete survey template metadata

Add recommended fields to the survey template: `References`, `Description`,
`Reliability`, `AdministrationTime`.

### `PRISM008` — Template consistency error

Check that `ItemCount` matches the actual questions, that `Subscale` items exist,
that `ReverseCodedItems` exist, and that `Levels` keys are within the
`MinValue`/`MaxValue` range.

## File naming errors (`PRISM1xx`)

### `PRISM101` — Invalid BIDS filename format

Ensure the filename follows `sub-<label>[_ses-<label>]_task-<label>_<suffix>.<ext>`.

Valid: `sub-01_task-faces_bold.nii.gz`, `sub-01_ses-01_task-nback_eeg.edf`.
Invalid: `subject01_task-faces.nii.gz`, `sub-01-task-faces.nii.gz`.

### `PRISM102` — Filename doesn't match expected pattern for modality

Use the correct suffix for the modality: `_survey`, `_physio`, `_eyetrack`,
`_biometrics`, or `_events`.

### `PRISM103` — Subject ID mismatch

The `sub-<label>` in the filename must match the parent directory.

### `PRISM104` — Session ID mismatch

The `ses-<label>` in the filename must match the parent directory.

## Sidecar and metadata-file errors (`PRISM2xx`)

### `PRISM201` — Missing JSON sidecar

Provide metadata via a matching sidecar, or a BIDS-inherited root sidecar (e.g.
`task-<name>_<suffix>.json`) to avoid redundant per-file copies. Auto-fixable.

```text
sub-01/survey/sub-01_task-demo_survey.tsv
sub-01/survey/sub-01_task-demo_survey.json
```

### `PRISM202` — Invalid JSON syntax in sidecar

Repair missing quotes, commas, or brackets in the `.json` file.

### `PRISM203` — Empty sidecar file

The `.json` sidecar exists but contains no data.

### `PRISM204` — Empty data file

The data file exists but contains no content.

## Schema validation errors (`PRISM3xx`)

### `PRISM301` — Metadata schema validation failed

A required field for this modality is missing from the JSON sidecar. This can
include standard BIDS-required metadata or PRISM-specific extensions.

```json
{
  "StimulusPresentation": {
    "SoftwareName": "PsychoPy",
    "SoftwareVersion": "2023.2.3"
  }
}
```

### `PRISM302` — Invalid field type in sidecar

A field exists but its type doesn't match the schema (string, number, object,
array, ...).

### `PRISM303` — CITATION.cff validation failed

Fix `CITATION.cff` formatting/required fields — `cff-version`, `title`, `message`,
`authors`, and reference keys — so citation metadata is valid.

## Content validation errors (`PRISM4xx`)

### `PRISM401` — TSV file is empty or missing header

Ensure the TSV file has a tab-separated header row.

### `PRISM402` — Value not in allowed levels

The value in the TSV doesn't match one of the `Levels` defined in the sidecar.

### `PRISM403` — Value out of range

The value falls outside the `MinValue`/`MaxValue` range defined in the sidecar.

### `PRISM404` — Value out of warning range

The value is within absolute limits but outside the typical warning range —
worth a second look, not necessarily wrong.

## BIDS compatibility (`PRISM5xx`)

### `PRISM501` — `.bidsignore` needs update

Add PRISM-specific modalities to `.bidsignore` to avoid standard BIDS validator
errors. Auto-fixable.

### `PRISM502` — BIDS validator warning

The standard BIDS validator reported a warning. Only surfaces when `--bids` (or
its equivalent Studio option) is enabled.

### `PRISM503` — BIDS validator error

The standard BIDS validator reported an error.

## Consistency errors (`PRISM6xx`)

### `PRISM601` — Dataset consistency warning

Check for missing sessions or modalities across subjects — e.g. one subject is
missing a session everyone else has.

## Procedure/session declaration errors (`PRISM7xx`)

These compare what's actually on disk against what `project.json`'s `Sessions`
and `TaskDefinitions` declare.

### `PRISM701` — Session on disk not declared in `project.json`

Add the session to the `Sessions` array in `project.json`, or use the session
picker in the Converter.

### `PRISM702` — Deprecated

Session presence is now inferred from the on-disk `sub-*/ses-*` structure. Kept
for backward compatibility only — not emitted by current validation.

### `PRISM703` — Task on disk not declared in session

Register the task in the session's `tasks` array in `project.json`.

### `PRISM704` — Declared non-optional task has no data on disk

Convert data for the task, mark it optional, or remove it from the session.

### `PRISM705` — Task references undefined `TaskDefinition`

Add the task to the `TaskDefinitions` object in `project.json` with at least a
`modality`.

### `PRISM706` — Sessions array is empty — no procedure defined yet

Define your study procedure in the `Sessions` array, or convert data with
save-to-project to auto-register it.

### `PRISM707` — `participants.tsv` does not cover all subject folders on disk

Open the participants/sociodemographics import step and import or add the missing
participants so `participants.tsv` lists every subject already saved in the dataset.

## Internal/system errors (`PRISM9xx`)

### `PRISM901` — Internal validation error

An unexpected error occurred during validation.

### `PRISM999` — General validation error

Check the error message for details; this is a catch-all.

## Auto-fix support

Some issues can be handled mechanically with `--fix`. Currently: `PRISM001`,
`PRISM201`, `PRISM501`.

```bash
prism-validator /path/to/dataset --fix --dry-run
prism-validator /path/to/dataset --fix
prism-validator --list-fixes
```

Use the dry run first whenever the dataset is not disposable.

## If you are still stuck

1. Re-run validation after each repair instead of making many unrelated changes at once.
2. Check [VALIDATOR.md](studio/validator.md) for the broader validation workflow.
3. Check [SPECIFICATIONS.md](SPECIFICATIONS.md) or the modality spec pages for schema context.
4. Use [QUICK_START.md](QUICK_START.md) or [WORKSHOP.md](WORKSHOP.md) if the issue is really a workflow misunderstanding rather than a code-level problem.
