# Schema Versioning

PRISM supports schema versioning so datasets can be validated against a specific schema release.

## Available Versions

Schema versions are stored under `schemas/`.

| Version | Status | Notes |
|---------|--------|-------|
| `stable` | ✅ Recommended | Current release, all features |
| `v0.1` | Legacy | Original schema without variant support |
| `v0.2` | Stable | Variant-aware survey schema; use for multi-version questionnaires |

### `v0.2`: Multi-Variant Survey Schema

`v0.2` introduced first-class support for questionnaires that exist in multiple validated forms. Key additions:

#### In the library template (`Study` block)

- `Study.Versions` — list of all variant IDs defined for this instrument, e.g. `["10-likert", "7-likert", "10-vas"]`
- `Study.VariantDefinitions` — array describing each variant: `VariantID`, `ItemCount`, `ScaleType`, `Description`

#### Per-item variant support

- `ApplicableVersions` — list of variant IDs the item belongs to; absent items are excluded from that variant's validation
- `VariantScales` — array of per-variant scale overrides: `VariantID`, `ScaleType`, `MinValue`, `MaxValue`, `Levels`

#### Example item with variant scales

```json
{
  "WB01": {
    "Description": { "en": "I have felt cheerful and in good spirits" },
    "ApplicableVersions": ["10-likert", "7-likert", "10-vas"],
    "DataType": "integer",
    "MinValue": 1,
    "MaxValue": 5,
    "VariantScales": [
      {
        "VariantID": "10-likert",
        "ScaleType": "likert",
        "MinValue": 1,
        "MaxValue": 5
      },
      {
        "VariantID": "10-vas",
        "ScaleType": "vas",
        "MinValue": 0,
        "MaxValue": 100,
        "Unit": "points"
      }
    ]
  }
}
```

Items not listed in `ApplicableVersions` for the resolved variant are expected to be absent from data files for that variant.

→ See [Survey Versioning](SURVEY_VERSION_PLAN.md) for how `Study.Version` and `acq-<version>` determine the active variant.

## CLI Usage

Use the default (`stable`):

```bash
python prism.py /path/to/dataset
```

Use a specific version:

```bash
python prism.py /path/to/dataset --schema-version 0.1
python prism.py /path/to/dataset --schema-version v0.1
python prism.py /path/to/dataset --schema-version v0.2
python prism.py /path/to/dataset --schema-version stable
```

List available versions:

```bash
python prism.py --list-versions
```

## Web Interface

In PRISM Studio, select the schema version in the validator controls before running validation.

Validation outputs include the schema version used, so reports remain traceable.

## Version Naming

- `stable` points to the recommended release.
- Version tags follow `v<major>.<minor>` style (for example `v0.1`).
- The CLI accepts both `0.1` and `v0.1`.

## Best Practices

1. Use `stable` for routine/project validation.
2. Use explicit legacy versions only for reproducibility checks.
3. Record the schema version in methods/report text when sharing results.
4. Re-validate datasets after switching schema versions.

## Troubleshooting

If a schema version is not found:

- Check that the corresponding folder exists in `schemas/`.
- Verify spelling (`stable`, `v0.1`, `v0.2`, etc.).
- Run `python prism.py --list-versions` to confirm available options.
