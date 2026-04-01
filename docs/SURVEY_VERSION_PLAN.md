# Survey Versioning

PRISM no longer requires a project-level Survey Version Plan UI or project-level survey mapping for conversion.

Version selection is now derived from:

1. Template metadata: `Study.Versions` and `Study.Version`
2. BIDS filename entity: `acq-<version>` for multi-variant outputs

This keeps versioning in templates and filenames, instead of in separate per-project selection state.

## How Variant Selection Works

For templates that define multiple variants:

- `Study.Versions` lists all allowed variant IDs (for example: `10-likert`, `7-likert`, `10-vas`).
- `Study.Version` sets the active variant used during conversion.
- Converted files include `acq-<Study.Version>` in the output filename.

Example template snippet:

```json
{
  "Study": {
    "TaskName": "wellbeing-multi",
    "Versions": ["10-likert", "7-likert", "10-vas"],
    "Version": "10-likert"
  }
}
```

Example output filename:

`sub-001_ses-01_task-wellbeing-multi_acq-10-likert_survey.tsv`

If a template has only one version, PRISM does not add an `acq` entity.

## Validation and Scoring

- Validation resolves version from filename `acq` first when present.
- If `acq` is absent, PRISM falls back to template `Study.Version`.
- Recipe `VersionedScores` are selected using the resolved version.

## Migration Notes

- Existing `survey_version_mapping` keys in older projects are tolerated.
- New conversion workflows do not require editing `survey_version_mapping`.
- Recommended practice is to keep template `Study.Version` accurate and rely on generated `acq` labels.

## See Also

- [Schema Versioning](SCHEMA_VERSIONING.md)
- [Survey Templates](TEMPLATES.md)
- [Survey Library](SURVEY_LIBRARY.md)
