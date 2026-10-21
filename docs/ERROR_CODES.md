# Error Codes Reference

Use this page when validation gives you a PRISM code and you need to decide what to
fix first: identify the code range → understand whether it's structural,
metadata-related, or system-level → decide whether auto-fix applies → re-run
validation after the repair.

The registry is `app/src/issues.py`. `tests/test_error_codes_registry.py` fails if the
validator can emit a code that is not in that registry, or if a registered code is
missing from this page, so the two cannot drift silently.

## Errors, warnings and info

Every issue has a severity:

| Severity | Meaning | Effect |
|---|---|---|
| **Error** | The dataset breaks a PRISM or BIDS rule | `prism-validator` exits with code `1`; Studio shows it under *Errors*; export and publish are blocked in the validation mode you chose |
| **Warning** | Probably a mistake, or a gap that weakens the dataset (FAIR metadata, an out-of-range value, a participant outside the eligibility limits) | Exit code stays `0`; shown under *Warnings* |
| **Info** | A note that needs no action (for example a survey without an optional recipe) | Shown, never counted as a warning |

The same code can be an error in one context and a warning in another (see `PRISM707`
and `PRISM709`). Issues raised by the standard BIDS validator keep their own BIDS code
and are tagged **BIDS** in the results; warnings from it are hidden unless you ask for
them (`--bids-warnings`, or *Show BIDS Warnings* in Studio). Issues from dataset
plugins (only loaded with `--plugins`) are reported as `PRISM900`.

## How codes are organized

All validation issues use structured codes in the form `PRISMxxx`.

| Code range | Category | Typical meaning |
|---|---|---|
| `PRISM0xx` | Dataset structure | The dataset root or top-level organization is broken or incomplete |
| `PRISM1xx` | File naming | Filenames or path entities do not match expectations |
| `PRISM2xx` | Sidecar and metadata files | Required JSON sidecars are missing, empty, or malformed |
| `PRISM3xx` | Schema validation | Metadata exists, but it does not satisfy schema rules |
| `PRISM4xx` | Content validation | TSV content values don't satisfy Levels/range rules from the sidecar |
| `PRISM5xx` | BIDS compatibility | BIDS-oriented compatibility issues or warnings |
| `PRISM6xx` | Consistency and eligibility | Cross-subject/cross-session consistency and participant eligibility warnings |
| `PRISM7xx` | Procedure/session declaration | On-disk data vs. `project.json`'s declared Sessions/Tasks |
| `PRISM9xx` | Internal/system errors | Internal validation failures |

Recommended fix order when you see several at once: `0xx` → `1xx` → `2xx` → `3xx` →
`4xx` → then review `5xx`–`7xx` warnings. This avoids polishing metadata on a file
that still needs to be moved or renamed.

## `PRISM0xx` — Dataset structure

| Code | Meaning | Fix |
|---|---|---|
| `PRISM000` | Optional `.prismrc.json` configuration not present (info only) | Create it only if you want to configure PRISM. **Auto-fixable.** |
| `PRISM001` | Missing `dataset_description.json` | Create it at the dataset root with at least `Name`/`BIDSVersion`. **Auto-fixable.** |
| `PRISM002` | No subjects found | Ensure `sub-<label>` folders exist at the project dataset root |
| `PRISM003` | Invalid `dataset_description.json` | Validate JSON syntax, repair missing fields |
| `PRISM004` | Missing `participants.tsv` | Create it with at least `participant_id`; in Studio, use the participants import step rather than hand-writing it |
| `PRISM005` | Schema version mismatch | Update `SchemaVersion` in metadata, or pass `--schema-version` to match |
| `PRISM006` | FAIR compliance issue | Add `Description` (≥50 chars), `License`, `EthicsApprovals`, `Funding`, `Keywords` (≥3), `Authors` with ORCID/affiliation |
| `PRISM007` | Incomplete survey template metadata | Add `References`, `Description`, `Reliability`, `AdministrationTime` |
| `PRISM008` | Template consistency error | Check `ItemCount` matches actual questions, `Subscale`/`ReverseCodedItems` exist, `Levels` keys are within `MinValue`/`MaxValue` |
| `PRISM010` | Missing `project.json` at the project root (checked when a project is opened in Studio) | Create the project on the Projects page, or add a `project.json`; see [Project metadata](specs/project.md) |

```json
{ "Name": "My Dataset", "BIDSVersion": "1.9.0", "DatasetType": "raw" }
```

## `PRISM1xx` — File naming

| Code | Meaning | Fix |
|---|---|---|
| `PRISM101` | Invalid BIDS filename format | Follow `sub-<label>[_ses-<label>]_task-<label>_<suffix>.<ext>`. Valid: `sub-01_task-faces_bold.nii.gz`. Invalid: `subject01_task-faces.nii.gz` |
| `PRISM102` | Filename doesn't match expected pattern for modality | Use the correct suffix: `_survey`, `_physio`, `_eyetrack`, `_biometrics`, `_events` |
| `PRISM103` | Subject ID mismatch | `sub-<label>` in the filename must match the parent directory |
| `PRISM104` | Session ID mismatch | `ses-<label>` in the filename must match the parent directory |

## `PRISM2xx` — Sidecar and metadata files

| Code | Meaning | Fix |
|---|---|---|
| `PRISM201` | Missing JSON sidecar | Provide a matching sidecar or a BIDS-inherited root sidecar (`task-<name>_<suffix>.json`). **Auto-fixable.** |
| `PRISM202` | Invalid JSON syntax in sidecar | Repair missing quotes/commas/brackets |
| `PRISM203` | Empty sidecar file | The `.json` exists but has no data |
| `PRISM204` | Empty data file | The data file exists but has no content |

```text
sub-01/survey/sub-01_task-demo_survey.tsv
sub-01/survey/sub-01_task-demo_survey.json
```

## `PRISM3xx` — Schema validation

| Code | Meaning | Fix |
|---|---|---|
| `PRISM301` | Metadata schema validation failed | Add the missing required field for this modality (standard BIDS or PRISM-specific) |
| `PRISM302` | Invalid field type in sidecar | Match the schema-expected type (string, number, object, array...) |
| `PRISM303` | `CITATION.cff` validation failed | Fix formatting/required fields — `cff-version`, `title`, `message`, `authors`, reference keys |

```json
{ "StimulusPresentation": { "SoftwareName": "PsychoPy", "SoftwareVersion": "2023.2.3" } }
```

## `PRISM4xx` — Content validation

| Code | Meaning | Fix |
|---|---|---|
| `PRISM401` | TSV file is empty or missing header | Ensure a tab-separated header row exists |
| `PRISM402` | Value not in allowed levels | Match one of the `Levels` defined in the sidecar |
| `PRISM403` | Value out of range | Stay within `MinValue`/`MaxValue` from the sidecar |
| `PRISM404` | Value out of warning range | Within absolute limits but outside typical range — worth a second look, not necessarily wrong |

## `PRISM5xx` — BIDS compatibility

| Code | Meaning | Fix |
|---|---|---|
| `PRISM501` | `.bidsignore` needs update | Add PRISM-specific modalities to avoid standard BIDS validator errors. **Auto-fixable.** |
| `PRISM502` | BIDS validator warning | Surfaces when the BIDS check runs (the default; not with `--no-bids`) and `--bids-warnings` is set |
| `PRISM503` | BIDS validator error | Standard BIDS validator reported an error |

## `PRISM6xx` / `PRISM7xx` — Consistency and procedure

| Code | Meaning | Fix |
|---|---|---|
| `PRISM601` | Dataset consistency warning | Check for missing sessions/modalities across subjects |
| `PRISM602` | Participants outside an eligibility criterion (warning only; one line per criterion with the number of participants) | Check the participants in participants.tsv, or correct the criterion in the project's Study Metadata |
| `PRISM603` | Eligibility criterion cannot be checked (not linked to a participants column, unknown id, missing column, min above max, no value labels) | Fix the link in participants.json or the criterion in project.json |
| `PRISM701` | Session on disk not declared in `project.json` | Add it to the `Sessions` array, or use the session picker in the Converter |
| `PRISM702` | Deprecated | Session presence is now inferred from disk; no action needed, not emitted by current validation |
| `PRISM703` | Task on disk not declared in session | Register it in the session's `tasks` array |
| `PRISM704` | Declared non-optional task has no data on disk | Convert data for it, mark it optional, or remove it |
| `PRISM705` | Task references undefined `TaskDefinition` | Add it to `TaskDefinitions` with at least a `modality` |
| `PRISM706` | Sessions array is empty | Define your study procedure in `Sessions`, or convert data with save-to-project to auto-register it |
| `PRISM707` | A `sub-*` folder has no row in `participants.tsv` (error), or `participants.tsv` lists participants without a folder, e.g. prescreened but not enrolled (warning) | Import or add the missing participants for the error; the warning needs no action |
| `PRISM708` | A survey in the dataset has no recipe in the project (`code/recipes/survey/`). Info note only: recipes are optional and are not counted as a warning | Create or copy it with the Recipe builder if you want scores |
| `PRISM709` | A participants column has no value labels, or its `Levels` miss a value in `participants.tsv` (warning if unlabeled and it looks like a code list, error if `Levels` exist but are incomplete) | Add every code to `Levels` in `participants.json`, or add a `Unit` if the column is a measurement |

`PRISM7xx` compares what's actually on disk against `project.json`'s declared
`Sessions`/`TaskDefinitions`.

## `PRISM9xx` — Internal/system

| Code | Meaning | Fix |
|---|---|---|
| `PRISM900` | An issue reported by a dataset validation plugin (message is prefixed with the plugin name) | Fix what the plugin reports; plugins only run with `--plugins` |
| `PRISM901` | Internal validation error | Unexpected error during validation |
| `PRISM902` | BIDS validator requested but not available | The bids-validator-deno program was not found or failed to run: reinstall prism-validator, or run with `--no-bids` |
| `PRISM999` | General validation error | Catch-all — check the error message for details |

## Auto-fix and troubleshooting

Currently auto-fixable: `PRISM000`, `PRISM001`, `PRISM201`, `PRISM501` (run `prism-validator --list-fixes` for the live list).

```bash
prism-validator /path/to/dataset --fix --dry-run
prism-validator /path/to/dataset --fix
prism-validator --list-fixes
```

Use the dry run first whenever the dataset isn't disposable. Re-run validation
after each repair instead of making many unrelated changes at once. See
[Validator](studio/validator.md) for the broader workflow,
[Specifications](SPECIFICATIONS.md) or the [modality spec pages](SCHEMA_SPECIFICATIONS.md) for schema context,
or [Getting Started](TUTORIAL_BEGINNER.md)/[Workshop](WORKSHOP.md) if the issue is really a
workflow misunderstanding rather than a code-level problem.
