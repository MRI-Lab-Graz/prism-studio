# Entities and filename grammar

PRISM's filename/entity conventions - which entities a modality requires or
allows, the canonical entity ordering used when rewriting filenames, and the
suffix/extension grammar used to validate them - are expressed as data
rather than scattered across parser code. The rules file is
[`app/schemas/stable/entities.schema.json`](../../app/schemas/stable/entities.schema.json)
and is loaded through `schema_manager.load_schema("entities", ...)` by
`src/entity_rules.py`, which compiles it into the validator's filename
patterns, the entity rewriter, and the fixer's suggestion hints. Adding a new
suffix or entity requires only a rules-file edit and tests - no parser code
changes.

This file is a grammar/rules document, not a per-file sidecar-validation
schema like `survey.schema.json` or `biometrics.schema.json` - it is loaded
directly by name rather than through `schema_manager.load_all_schemas()`'s
modality registry.

## Entity ordering

`entityOrder` fixes the canonical left-to-right order entities appear in a
filename when PRISM constructs or rewrites one:

```
sub, ses, task, acq, run, rec, dir, echo, ce, part, space, desc
```

`defaultRequiredEntities` (`sub`, `task`) apply to every modality unless a
modality's own entry overrides them.

## Modality kinds

Each entry under `modalities` has a `kind`:

- **`prism`** - a PRISM-native modality (`survey`, `biometrics`,
  `environment`, `events`, `physio`). These define their own `suffixes` and
  `extensions`.
- **`bidsPassthrough`** - a standard BIDS modality PRISM validates using
  BIDS's own conventions rather than PRISM-specific suffix/extension rules
  (`anat`, `func`, `fmap`, `dwi`, `eeg`, `beh`; `eyetracking` is a
  `bidsPassthrough` modality that additionally constrains a PRISM-specific
  `trackedEye` entity value).

An `aliases` map (`physiological` -> `physio`) lets older/alternate modality
names resolve to their canonical entry.

## Per-modality rules

| Modality | Kind | Suffixes | Extensions | Notable entity constraints |
| --- | --- | --- | --- | --- |
| `survey` | prism | `survey` | `tsv`, `json` | example: `task-panas` |
| `biometrics` | prism | `biometrics` | `tsv`, `json` | - |
| `environment` | prism | `environment` | `tsv`, `tsv.gz`, `json` | `recording` entity required, matching `[a-zA-Z0-9]+` |
| `events` | prism | `events` | `tsv` | - |
| `physio` | prism | `physio` | `tsv`, `tsv.gz`, `json`, `edf` | optional `recording` entity: enum of common channel types (`ecg`, `cardiac`, `puls`, `resp`, `eda`, `ppg`, `emg`, `temp`, `bp`, `spo2`, `trigger`), plus any other alphanumeric value |
| `eyetracking` | bidsPassthrough | `eyetrack`, `eye`, `gaze` | `tsv`, `tsv.gz`, `json`, `edf`, `asc` | optional `trackedEye` entity: `left`, `right`, or `both` |
| `anat`, `func`, `fmap`, `dwi`, `eeg`, `beh` | bidsPassthrough | (standard BIDS) | (standard BIDS) | validated per standard BIDS rules |

See [`app/schemas/stable/entities.schema.json`](../../app/schemas/stable/entities.schema.json)
for the authoritative, machine-readable version of this table.
