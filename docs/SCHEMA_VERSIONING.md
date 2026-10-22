# Schema Versioning

PRISM versions each modality schema separately, so a study keeps validating the
same way until you decide to move it. The older whole-schema bundles (`v0.1`,
`v0.2`) are still available; see [Legacy schema bundles](#legacy-schema-bundles).

## Per-modality versions

Every modality (survey, biometrics, eyetracking, ...) has its own
`major.minor.patch` version, stored as `version` in its schema file. A modality
proposal starts at `1.0.0`. By default a validation uses the latest version of
every modality.

### Pins in project.json

When a modality is first imported into a project (through Studio or the
converters), PRISM pins the then-current version in the project's
`project.json`:

```json
{
  "SchemaVersions": { "survey": "1.0.0", "biometrics": "1.0.0" },
  "SchemaVersionsAcknowledged": { "survey": "1.1.0" }
}
```

- `SchemaVersions` is the version each modality is validated against.
- `SchemaVersionsAcknowledged` records the newest version you have already
  decided about, so you are told about a newer version only once.
- For DataLad projects, Studio imports record the pin as a small separate commit
  whose message ends with "(record modality versions)". The command-line
  converters and environment conversion leave `project.json` uncommitted along
  with their data.
- Validation never writes pins. A project is only pinned by an import, or by the
  `pin` command below.

When a newer version of a pinned modality exists, `prism.py` prints a hint on
stderr after the validation. Decide with the command line:

```bash
python prism_tools.py modality-version update <project> survey   # move to the latest
python prism_tools.py modality-version freeze <project> survey   # keep the pinned version
```

Either choice is remembered in `SchemaVersionsAcknowledged`; freezing keeps the
pin and only silences the hint until a still newer version is released. The
Studio notice with "Update" and "Keep current version" buttons is coming; today
the stderr hint is the notice. `status` shows the pins and pending updates,
`list` shows the available versions, and `pin` pins projects created before this
feature (it pins the modalities that have data in the project, or the ones you
name):

```bash
python prism_tools.py modality-version status <project>
python prism_tools.py modality-version list [survey]
python prism_tools.py modality-version pin <project> [survey ...]
```

All five accept `--json`. See [CLI reference](CLI_REFERENCE.md).

### Overriding for one run

```bash
python prism.py <dataset> --modality-version survey=<version> --modality-version biometrics=<version>
```

`<version>` is one of the versions `modality-version list` shows. The flag is repeatable. Precedence per modality: the flag, then the pin in
`project.json`, then the latest version. Project pins apply
on the `stable` base only: an explicit legacy `--schema-version v0.x` ignores the
project pins, while `--modality-version` applies on any base. A version that does
not exist is an error that lists the available versions. `prism.py --list-versions`
prints the available versions of every modality.

Studio keeps the version used per modality, and where it came from (`cli`,
`project.json` or `latest`), in the project's validation record. The
command-line `--json` report does not list them yet.

### Releasing a new modality version (maintainers)

The modality schemas are edited and released in the
[prism-specification](https://github.com/MRI-Lab-Graz/prism-specification) repository
(see its `CONTRIBUTING.md`); this repository carries a hash-locked copy of a tagged
release at the same paths (`app/schemas/`, `official/library/terms/`, `docs/specs/`) and
never edits it. A release there is:

1. Copy the current `schemas/stable/<name>.schema.json` unchanged to
   `schemas/archive/<name>/<old version>.schema.json`.
2. Edit the stable file and bump its `version` and the version suffix of its
   `$id`.
3. Tag the repository, then run `python scripts/sync_specification.py --tag <tag>` here.

The CI job `Modality schema versions` of prism-specification
(`scripts/check_schema_versions.py`) enforces three rules: files under
`schemas/archive/` are never modified or deleted; a changed stable modality schema
must carry a bumped `version`; and a bumped version needs the previous version
archived as an exact copy of the previous stable file. It does not guard deleting or
renaming a stable modality schema. Here, the job `Vendored specification`
(`scripts/ci/check_specification_lock.py`) fails when the copy differs from
`specification.lock.json`.

The archive ships automatically: the validator wheel copies the whole
`app/schemas` tree and the app bundle adds the whole directory, so no extra
packaging step is needed. Versions that existed before this feature (for example
survey `1.1.1`) have no archive entry until their first change, so versions
older than the first archive entry cannot be pinned.

## Legacy schema bundles

### Available versions

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
