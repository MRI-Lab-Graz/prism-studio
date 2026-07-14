# Specifications and Schemas

The specification layer behind PRISM Studio: what PRISM adds to BIDS, how schemas
are versioned, and what files/metadata the validator expects. This page is
conceptual and reference-oriented — for step-by-step workflows, use the
[Studio Guide](studio/index.md) instead.

## PRISM, BIDS, and PRISM Studio

**PRISM is an add-on to BIDS, not a replacement.** BIDS stays the baseline where it
applies (dataset structure, `sub-`/`ses-`/`task-` entities, standard files like
`dataset_description.json`); a core goal is that standard BIDS tools can still
operate on PRISM datasets.

**PRISM** extends that baseline with additional schemas and stricter metadata rules
for workflows common in psychological research: surveys, biometrics, environment
metadata, richer sidecar expectations, and some additional requirements for
otherwise-standard BIDS data (e.g. events metadata blocks).

**PRISM Studio** is the software layer that helps you work with those rules —
import/conversion, validation, scoring/derivatives, and export.

## Schema versions

Schemas are versioned under `app/schemas/stable/` and `app/schemas/vX.Y/`.

```bash
prism-validator --list-versions
prism-validator /path/to/dataset --schema-version stable
```

See [Schema Versioning](SCHEMA_VERSIONING.md) for migration details.

## What a PRISM dataset looks like

At the BIDS-core level: `dataset_description.json`, and typically `participants.tsv`
for participant-oriented datasets. PRISM-specific extensions add survey, biometrics,
physiology, and environment files under subject/session paths, each usually paired
with a JSON sidecar sharing the same filename stem — e.g.
`sub-001_ses-1_task-ads_survey.tsv` + `.json`, or
`sub-001_ses-1_task-rest_physio.edf` + `.json`.

Derivative outputs (scores/subscales computed via recipes) live under
`derivatives/`, with their own `dataset_description.json`; recipe *definitions* live
separately from the derivative *outputs* they produce. See
[Recipes](RECIPES.md) and [Export](studio/export.md) for the operational side.

## Schema anatomy

PRISM uses JSON Schema documents to define required top-level blocks, required
fields, allowed types/value shapes, and optional blocks (i18n, scoring metadata).

- **`Study`** — instrument-level/scientific metadata: `OriginalName`, `ShortName`,
  `Authors`, `DOI`/`Citation`, `Construct`, `Reliability`/`Validity`. For surveys,
  `TaskName` matters most since it ties the instrument to how it's referenced in the
  dataset.
- **`Technical`** — how the data was actually collected in *this* project: software
  platform/version, language, respondent type, administration method, equipment/
  location. Often the block that still needs project-specific completion after an
  import or template copy.
- **Item-level metadata** — question/metric text, levels/response labels, units,
  hard/soft bounds, expected type, relevance logic. This is what makes survey and
  biometrics data self-documenting instead of just column names.
- **Internationalization** — some templates support multilingual descriptive fields,
  e.g. `{"en": "Measures explosive leg power.", "de": "Misst die explosive
  Beinkraft."}` — useful for instrument descriptions and item text.

For modality-specific semantics, see the spec pages:
[Survey](specs/survey), [Biometrics](specs/biometrics), [Events](specs/events),
[Environment](specs/environment).

## What's next

- [What is PRISM](WHAT_IS_PRISM.md)
- [Validator](studio/validator.md)
- [Schema Versioning](SCHEMA_VERSIONING.md)
- [Recipes](RECIPES.md)
