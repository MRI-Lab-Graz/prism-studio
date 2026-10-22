# Specifications and Schemas

What PRISM adds to BIDS, how its schemas are versioned, and which files and
metadata the validator expects.

**Specification version:** the `stable` schema set under `app/schemas/stable/`
(see [Schema versions](#schema-versions)). The JSON Schemas and
`app/schemas/stable/entities.schema.json` together form the PRISM Specification.

## PRISM, BIDS, and PRISM Studio

**PRISM is an add-on to BIDS, not a replacement.** BIDS stays the baseline where it
applies (dataset structure, `sub-`/`ses-`/`task-` entities, standard files like
`dataset_description.json`); a core goal is that standard BIDS tools can still
operate on PRISM datasets.

**PRISM** extends that baseline with additional schemas and stricter metadata rules
for workflows common in psychological research: surveys, biometrics, environment
metadata, richer sidecar expectations, and some additional requirements for
otherwise-standard BIDS data (e.g. events metadata blocks).

## Schema versions

Schemas are versioned under `app/schemas/stable/` (the current version of each) and `app/schemas/vX.Y/` (frozen older sets). A project can pin a version per modality in `project.json`.

```bash
prism-validator --list-versions
prism-validator /path/to/dataset --schema-version stable
```

See [Schema Versioning](SCHEMA_VERSIONING.md) for migration details.

## What a PRISM dataset looks like

```text
my_study/
├── dataset_description.json     BIDS root file (see Dataset description)
├── participants.tsv / .json     one row per participant, with value labels
├── project.json                 study design, sessions, tasks, eligibility
├── CITATION.cff, README.md, CHANGES, .bidsignore, .prismrc.json
├── sub-001/
│   └── ses-1/                   sessions are free-form labels (pre, 1, 01 are different)
│       ├── survey/              sub-001_ses-1_task-ads_survey.tsv + .json
│       ├── biometrics/          sub-001_ses-1_task-grip_biometrics.tsv + .json
│       ├── physio/              sub-001_ses-1_recording-ecg_physio.edf + .json
│       ├── eyetracking/         sub-001_ses-1_task-find_eyetrack.edf + .json
│       ├── beh/ func/ eeg/ ... standard BIDS (events and task-bound physio live here)
├── sourcedata/                  raw input; internal lab server only
├── code/library/, code/recipes/ project copies of templates and scoring recipes
└── derivatives/                 scores and other computed outputs
```

Every data file has a JSON sidecar with the same file stem (or a BIDS-inherited sidecar
higher up). The sidecar carries the metadata that makes the file self-describing.

### Modalities

| Modality | Folder | Suffix | Spec page |
|---|---|---|---|
| Survey | `survey/` | `_survey` | [Survey](specs/survey.md) |
| Biometrics | `biometrics/` | `_biometrics` | [Biometrics](specs/biometrics.md) |
| Biosample | `biosample/` | `_biosample` | [Biosample](specs/biosample.md) |
| Environment | `environment/` | `_environment` | [Environment](specs/environment.md) |
| Physio (task-free) | `physio/` | `_physio` | [Physio](specs/physio.md) |
| Eyetracking | `eyetracking/` | `_eyetrack` (also `_eye`, `_gaze`) | [Eyetracking](specs/eyetracking.md) |
| Events | next to its task in `func/`, `beh/`, `eeg/` | `_events` | [Events](specs/events.md) |
| Standard BIDS (`anat`, `func`, `fmap`, `dwi`, `eeg`, `beh`) | as in BIDS | as in BIDS | validated by the BIDS validator |

### Project-level files

| File | Purpose | Spec page |
|---|---|---|
| `dataset_description.json` | Name, license, authors, FAIR metadata | [Dataset description](specs/dataset_description.md) |
| `project.json` | Study design, sessions, tasks, eligibility, preregistration | [Project metadata](specs/project.md) |
| `participants.tsv` / `.json` | Participants and their value labels | [Participants converter](studio/converter_participants.md) |
| `code/recipes/survey/*.json` | Scoring recipe definitions (outputs go to `derivatives/`) | [Recipes](RECIPES.md) |

Filename rules for every modality, including entity order, are in
[Entities and filename grammar](specs/entities.md).

## How validation works

`prism-validator` (and the Studio Validator page) runs two layers: the standard BIDS
validator, then PRISM's own checks. PRISM checks fall into the groups below; each issue
carries a code, a severity (error, warning or info) and a fix hint. The
[Error codes](ERROR_CODES.md) page lists every code.

| Check | Looks at | Codes |
|---|---|---|
| Dataset structure | root files, subjects, schema version, FAIR metadata, templates | `PRISM0xx` |
| File naming | entities, suffix, folder vs. filename | `PRISM1xx` |
| Sidecars | existence, valid JSON, not empty | `PRISM2xx` |
| Schema | required fields and types against the modality schema | `PRISM3xx` |
| Content | TSV values against `Levels`, `MinValue`/`MaxValue`, warning ranges | `PRISM4xx` |
| BIDS compatibility | `.bidsignore`, BIDS validator results | `PRISM5xx` |
| Consistency, eligibility | gaps across sessions/subjects, participants outside criteria | `PRISM6xx` |
| Procedure | what is on disk vs. `Sessions`/`TaskDefinitions` in `project.json`, participants coverage, recipes | `PRISM7xx` |

## Schema anatomy

PRISM uses JSON Schema documents to define required top-level blocks, required
fields, allowed types/value shapes, and optional blocks (i18n, scoring metadata).

- **`Study`** — instrument-level/scientific metadata: `OriginalName`, `ShortName`,
  `Authors`, `DOI`/`Citation`, `Construct`, `Reliability`/`Validity`. For surveys,
  `TaskName` ties the instrument to the `task-` entity in the dataset.
- **`Technical`** — how the data was actually collected in *this* project: software
  platform/version, language, respondent type, administration method, equipment/
  location.
- **Item-level metadata** — question/metric text, levels/response labels, units,
  hard/soft bounds, expected type, relevance logic. This is what makes survey and
  biometrics data self-documenting instead of just column names.
- **Internationalization** — some templates support multilingual descriptive fields,
  e.g. `{"en": "Measures explosive leg power.", "de": "Misst die explosive
  Beinkraft."}`, for instrument descriptions and item text.

For modality-specific semantics, see the spec pages:
[Survey](specs/survey), [Biometrics](specs/biometrics), [Events](specs/events) (`_events.tsv` next to its task in `func/`/`beh/`/`eeg/`),
[Environment](specs/environment), [Entities & filename grammar](specs/entities).

Besides the modality schemas, `app/schemas/stable/` holds `dataset_description`,
`project`, `entities` (filename grammar), `recipe.survey` (see [Recipes](RECIPES.md)),
`instrument-registry` (the index of the official survey library) and `tool-limesurvey`
(a legacy mapping that the importer no longer writes). Each spec page ends with a field
reference generated from its schema, so the tables always match the shipped version
(they are generated in the [prism-specification](https://github.com/MRI-Lab-Graz/prism-specification)
repository, where a test fails when they are stale).

## BIDS compatibility

`dataset_description.json` and `CITATION.cff` carry overlapping citation information
and must agree; `CITATION.cff` is the citation-focused file. The field list is on
[Dataset description](specs/dataset_description.md).

## FAIR compliance

PRISM's schema-driven design maps directly onto the FAIR principles:

| Principle | What PRISM implements |
|---|---|
| **F — Findable** | Rich metadata (hierarchical JSON schemas), unique identifiers (schema versioning with persistent `$id` URLs), standardized BIDS-inspired naming, keyword metadata |
| **A — Accessible** | Open source (AGPL-3.0), standard formats (JSON, TSV, CSV), comprehensive documentation, multiple export formats |
| **I — Interoperable** | JSON Schema validation, BIDS alignment, semantic schema versioning, modular architecture for new modalities |
| **R — Reusable** | Clear licensing, Git-based version control, comprehensive documentation, community contribution guidelines |

## What's next

- [What is PRISM](WHAT_IS_PRISM.md)
- [Error codes](ERROR_CODES.md)
- [Validator](studio/validator.md)
- [Schema Versioning](SCHEMA_VERSIONING.md)
- [Recipes](RECIPES.md)
