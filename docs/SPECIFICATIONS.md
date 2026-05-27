# Specifications and Schemas

Use this page to understand the specification layer behind PRISM Studio: what
PRISM adds to BIDS, how schemas are versioned, and what kinds of files and
metadata the validator expects.

This page is conceptual and reference-oriented. For step-by-step workflows, use
the workflow pages instead.

## The main idea

PRISM is an add-on to BIDS.

That means:

- PRISM does not replace BIDS
- BIDS structure and naming stay the baseline where BIDS applies
- PRISM adds schemas for psychology-focused data and metadata that are not fully
  covered by standard BIDS practice
- a core goal is that standard BIDS tools can still operate on PRISM datasets

## Three layers to keep separate

### BIDS

BIDS provides the baseline for:

- dataset structure
- filename entities such as `sub-`, `ses-`, and `task-`
- standard files such as `dataset_description.json`

### PRISM

PRISM extends that baseline with additional schemas and stricter metadata rules,
especially for workflows that are common in psychological research.

Examples:

- surveys
- biometrics
- environment metadata
- richer sidecar expectations
- some additional requirements for otherwise standard BIDS-style data such as
  events metadata blocks

### PRISM Studio

PRISM Studio is the software layer that helps you work with those rules through:

- import and conversion workflows
- validation
- scoring and derivatives
- export workflows

## Schema versions

Schemas are versioned in the repository.

Typical locations:

- `schemas/stable/`
- `schemas/vX.Y/`

Useful commands:

```bash
python prism-validator --list-versions
python prism-validator /path/to/dataset --schema-version stable
```

For version migration details, see [SCHEMA_VERSIONING.md](SCHEMA_VERSIONING.md).

## What PRISM usually expects in a dataset

At the BIDS-core level, the project still needs the usual baseline files such as:

- `dataset_description.json`
- often `participants.tsv` in practice for participant-oriented datasets

PRISM-specific extensions commonly add:

- survey files under subject and session paths
- biometrics files under subject and session paths
- physiology files and sidecars
- environment-specific data and sidecars
- JSON sidecars for the non-JSON data files PRISM validates

## High-level filename expectations

PRISM follows BIDS-like entity conventions.

Examples:

- survey TSV: `sub-001_ses-1_task-ads_beh.tsv`
- biometrics TSV: `sub-001_ses-1_biometrics-cmj_biometrics.tsv`
- physio EDF: `sub-001_ses-1_task-rest_physio.edf`

In general, data files should have matching JSON sidecars with the same stem.

## Derivatives and processed outputs

PRISM can generate derivatives such as scores and subscales from raw data using
recipes.

Typical characteristics:

- derivative outputs live under `derivatives/`
- derivative datasets need their own `dataset_description.json`
- recipe definitions live separately from the derivative outputs themselves

See [RECIPES.md](RECIPES.md) and [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md) for
the operational side of this.

## What is inside a PRISM schema?

PRISM uses JSON Schema documents to define:

- required top-level blocks
- required fields
- allowed data types and value shapes
- optional blocks such as i18n or scoring-related metadata

Common logical blocks include:

- `Study`
- `Technical`
- sometimes scoring or metadata-related blocks depending on modality

## Important schema concepts

### `Study`

`Study` is usually instrument-level or scientific metadata.

Typical fields include:

- `OriginalName`
- `ShortName`
- `Authors`
- `DOI` or `Citation`
- `Construct`
- `Reliability` and `Validity`

For surveys, `TaskName` is especially important because it ties the instrument to
how it is referenced in the dataset.

### `Technical`

`Technical` describes how the data was actually collected in the project.

Examples:

- software platform and version
- language
- respondent type
- administration method
- equipment or location details

This is often the block that still needs project-specific completion after an
import or template copy.

### Item-level metadata

Item or column metadata can describe:

- question or metric text
- levels or response labels
- units
- hard and soft bounds
- expected data type
- relevance logic

This is what makes survey and biometrics data self-documenting instead of just a
set of column names.

## Internationalization

Some PRISM templates support multilingual descriptive fields.

Example:

```json
{
  "en": "Measures explosive leg power.",
  "de": "Misst die explosive Beinkraft."
}
```

This is especially useful for instrument descriptions and item-level text.

## Where to read the detailed modality specs

For modality-specific semantics, use the spec pages under `docs/specs/`:

- [Survey specification](specs/survey)
- [Biometrics specification](specs/biometrics)
- [Events specification](specs/events)
- [Environment specification](specs/environment)

## Related pages

- [WHAT_IS_PRISM.md](WHAT_IS_PRISM.md)
- [VALIDATOR.md](VALIDATOR.md)
- [SCHEMA_VERSIONING.md](SCHEMA_VERSIONING.md)
- [RECIPES.md](RECIPES.md)
