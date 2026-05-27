# Error Codes Reference

Use this page when validation gives you a PRISM code and you need to decide what
to fix first.

This page works best as a triage guide:

1. identify the code range
2. understand whether the issue is structural, metadata-related, or system-level
3. decide whether auto-fix is appropriate
4. re-run validation after the repair

## How PRISM codes are organized

All validation issues use structured codes in the form `PRISMxxx`.

| Code range | Category | Typical meaning |
|---|---|---|
| `PRISM0xx` | Dataset structure | The dataset root or top-level organization is broken or incomplete |
| `PRISM1xx` | File naming | Filenames or path entities do not match expectations |
| `PRISM2xx` | Sidecar and metadata files | Required JSON sidecars are missing, empty, or malformed |
| `PRISM3xx` | Schema validation | Metadata exists, but it does not satisfy schema rules |
| `PRISM4xx` | Content validation | The content itself is problematic beyond simple schema shape |
| `PRISM5xx` | BIDS compatibility | BIDS-oriented compatibility issues or warnings |
| `PRISM9xx` | Plugin or system errors | Internal failures or plugin-related problems |

## Recommended fix order

When you see multiple codes at once, this order is usually fastest:

1. fix dataset structure (`PRISM0xx`)
2. fix filename problems (`PRISM1xx`)
3. fix missing sidecars (`PRISM2xx`)
4. fix schema-required metadata (`PRISM3xx`)
5. review BIDS warnings and plugin issues afterward

This prevents you from polishing metadata on a file that still needs to be moved
or renamed.

## Dataset structure errors (`PRISM0xx`)

### `PRISM001` — Missing `dataset_description.json`

Meaning: the required `dataset_description.json` file is missing from the dataset root.

Typical fix:

- create the file at dataset root with at least `Name` and `BIDSVersion`

Auto-fixable: yes

Example:

```json
{
  "Name": "My Dataset",
  "BIDSVersion": "1.9.0",
  "DatasetType": "raw"
}
```

### `PRISM002` — No subjects found

Meaning: no `sub-*` subject directories were detected.

Typical fix:

- check that subject folders are present
- ensure they use `sub-<label>` naming
- ensure they are located where the validator expects them

Auto-fixable: no

### `PRISM003` — Invalid `dataset_description.json`

Meaning: the file exists, but its JSON syntax or required metadata is invalid.

Typical fix:

- validate the JSON syntax
- repair missing required fields

### `PRISM004` — Missing `participants.tsv`

Meaning: the participant table expected for the dataset is missing.

Typical fix:

- create `participants.tsv`
- include at least a `participant_id` column and the expected participant rows

## File naming errors (`PRISM1xx`)

### `PRISM101` — Invalid filename pattern

Meaning: the filename does not follow expected BIDS or PRISM entity conventions.

Typical fix:

- rename the file using entity-based structure such as
  `sub-<label>[_ses-<label>][_task-<label>]_<suffix>.<ext>`

Valid examples:

- `sub-01_task-faces_bold.nii.gz`
- `sub-01_ses-01_task-nback_eeg.edf`
- `sub-02_task-rest_physio.tsv`

Invalid examples:

- `subject01_task-faces.nii.gz`
- `sub-01-task-faces.nii.gz`

### `PRISM102` — Subject ID mismatch

Meaning: the subject entity in the filename does not match the parent directory.

Typical fix:

- align the filename with the `sub-*` directory name

### `PRISM103` — Session ID mismatch

Meaning: the session entity in the filename does not match the parent directory.

Typical fix:

- align the filename with the `ses-*` directory name

### `PRISM104` — Invalid characters

Meaning: the filename contains disallowed characters.

Typical fix:

- keep names to letters, numbers, hyphens, and underscores

## Sidecar and metadata-file errors (`PRISM2xx`)

### `PRISM201` — Missing sidecar

Meaning: a non-JSON data file is missing its required JSON sidecar.

Typical fix:

- create the JSON file with the same stem as the data file

Auto-fixable: yes

Example:

```text
sub-01/survey/sub-01_task-demo_survey.tsv
sub-01/survey/sub-01_task-demo_survey.json
```

### `PRISM202` — Invalid JSON syntax

Meaning: the JSON exists, but the syntax is malformed.

Typical fix:

- repair missing quotes, commas, brackets, or other JSON syntax issues

### `PRISM203` — Empty sidecar

Meaning: the JSON file is empty or effectively empty.

Typical fix:

- add the required metadata fields instead of leaving `{}` in place

## Schema validation errors (`PRISM3xx`)

### `PRISM301` — Missing required field

Meaning: a required field is missing according to the loaded PRISM schema.

This can include:

- standard BIDS-related required metadata
- PRISM-specific required extensions such as event-sidecar metadata blocks

Typical fix:

- add the missing field to the JSON sidecar or template
- use the schema docs to confirm the required structure

Example for event-sidecar metadata:

```json
{
  "StimulusPresentation": {
    "SoftwareName": "PsychoPy",
    "SoftwareVersion": "2023.2.3"
  }
}
```

### `PRISM302` — Invalid field type

Meaning: a field exists, but its type is wrong.

Typical fix:

- change the value to the schema-expected type such as string, integer, float,
  object, or array

### `PRISM303` — Invalid field value

Meaning: the field type is acceptable, but the actual value is outside the
allowed range or set.

Typical fix:

- use a value permitted by the schema or the modality rules

## BIDS compatibility warnings (`PRISM5xx`)

### `PRISM501` — `.bidsignore` needs update

Meaning: the dataset should ignore PRISM-specific files for standard BIDS tools.

Typical fix:

- update `.bidsignore` to reflect the PRISM-specific paths that should not be
  treated as ordinary BIDS data files

Auto-fixable: yes

### `PRISM502` — BIDS validator warning

Meaning: the standard BIDS validator reported a warning.

Typical fix:

- inspect the BIDS-side warning and decide whether it is blocking for your target
  downstream tooling

## Plugin and system errors (`PRISM9xx`)

### `PRISM900` — Plugin issue

Meaning: a custom validator plugin reported a validation issue.

Typical fix:

- read the plugin-specific message and repair the condition it describes

### `PRISM901` — Plugin failure

Meaning: a plugin failed during execution.

Typical fix:

- inspect the plugin code and its expected `validate()` behavior

### `PRISM999` — Internal error

Meaning: an unexpected internal failure occurred.

Typical fix:

- capture the context and report it as a bug if it is reproducible

## Legacy name mapping

Some older names map to the structured code system.

| Legacy name | PRISM code |
|---|---|
| `INVALID_BIDS_FILENAME` | `PRISM101` |
| `MISSING_SIDECAR` | `PRISM201` |
| `SCHEMA_VALIDATION_ERROR` | `PRISM301` to `PRISM303` |
| `INVALID_JSON` | `PRISM202` |
| `FILENAME_PATTERN_MISMATCH` | `PRISM101` |

## Auto-fix support

Some issues can be handled mechanically with `--fix`.

Recommended use:

```bash
python prism-validator /path/to/dataset --fix --dry-run
python prism-validator /path/to/dataset --fix
python prism-validator --list-fixes
```

Commonly fixable issues include:

- `PRISM001`
- `PRISM201`
- `PRISM501`

Use the dry run first whenever the dataset is not disposable.

## If you are still stuck

1. Re-run validation after each repair instead of making many unrelated changes at once.
2. Check [VALIDATOR.md](VALIDATOR.md) for the broader validation workflow.
3. Check [SPECIFICATIONS.md](SPECIFICATIONS.md) or the modality spec pages for schema context.
4. Use [QUICK_START.md](QUICK_START.md) or [WORKSHOP.md](WORKSHOP.md) if the issue is really a workflow misunderstanding rather than a code-level problem.
