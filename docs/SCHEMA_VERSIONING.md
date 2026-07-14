# Schema Versioning

PRISM supports schema versioning so datasets can be validated against a specific
schema release. Versions are stored under `app/schemas/`.

## Available versions

| Version | Status | Notes |
|---------|--------|-------|
| `stable` | ✅ Recommended | Current release, all features |
| `v0.1` | Legacy | Original schema without variant support |
| `v0.2` | Stable | Variant-aware survey schema; use for multi-version questionnaires |

**`v0.2` — multi-variant survey schema**: first-class support for questionnaires
existing in multiple validated forms. In the library template's `Study` block:
`Study.Versions` (list of variant IDs, e.g. `["10-likert", "7-likert", "10-vas"]`)
and `Study.VariantDefinitions` (per-variant `VariantID`/`ItemCount`/`ScaleType`/
`Description`). Per-item: `ApplicableVersions` (which variants the item belongs to)
and `VariantScales` (per-variant scale overrides — `VariantID`, `ScaleType`,
`MinValue`, `MaxValue`, `Levels`).

```json
{
  "WB01": {
    "Description": { "en": "I have felt cheerful and in good spirits" },
    "ApplicableVersions": ["10-likert", "7-likert", "10-vas"],
    "DataType": "integer",
    "MinValue": 1,
    "MaxValue": 5,
    "VariantScales": [
      { "VariantID": "10-likert", "ScaleType": "likert", "MinValue": 1, "MaxValue": 5 },
      { "VariantID": "10-vas", "ScaleType": "vas", "MinValue": 0, "MaxValue": 100, "Unit": "points" }
    ]
  }
}
```

Items not listed in `ApplicableVersions` for the resolved variant are expected to be
absent from data files for that variant.

## How the active variant is selected

There is no project-level version-selection UI or mapping file — the active variant
is derived entirely from the template and the filename:

1. **Template metadata**: `Study.Versions` (all allowed variant IDs) and
   `Study.Version` (the active variant used during conversion).
2. **BIDS filename entity**: `acq-<version>` on multi-variant outputs.

```json
{ "Study": { "TaskName": "wellbeing-multi", "Versions": ["10-likert", "7-likert", "10-vas"], "Version": "10-likert" } }
```

produces `sub-001_ses-01_task-wellbeing-multi_acq-10-likert_survey.tsv`. A
single-version template gets no `acq` entity at all.

At validation and scoring time, the version resolves from the filename's `acq`
entity first when present; if `acq` is absent, PRISM falls back to the template's
`Study.Version`. Recipe `VersionedScores` are selected using that resolved version.

Older projects may still have a `survey_version_mapping` key — it's tolerated but no
longer required. New conversions don't need it; just keep `Study.Version` accurate
in the template and rely on the generated `acq` labels.

## Using a version

CLI: `prism.py /path/to/dataset` uses `stable` by default; pass
`--schema-version 0.1` (or `v0.1`, `v0.2`, `stable`) for a specific version, or
`--list-versions` to list what's available. In Studio, select the schema version in
the validator's Advanced Options before running validation — validation outputs
include the schema version used, so reports stay traceable.

Naming: `stable` points to the recommended release; version tags follow
`v<major>.<minor>` (e.g. `v0.1`); the CLI accepts both `0.1` and `v0.1`.

**Best practices**: use `stable` for routine/project validation; use explicit legacy
versions only for reproducibility checks; record the schema version in methods/report
text when sharing results; re-validate datasets after switching schema versions.

## Troubleshooting

If a schema version isn't found: check the corresponding folder exists in
`app/schemas/`, verify spelling (`stable`, `v0.1`, `v0.2`), and run
`prism.py --list-versions` to confirm available options.
