# Survey instrument categorization (`Study.Category`)

> **Later change (2026-09-10):** `BSRI` was removed from the library for
> licensing reasons (Mind Garden licenses it and forbids open-web
> publication). Counts below are the 104 as of this spec's date; the
> library now holds 103.

## Problem

The official instrument library (`official/library/survey/`, 104 questionnaire
templates) has no content-domain grouping. Browsing the Survey Questionnaires
panel in Studio means scanning a single flat alphabetical list of 104 items.
We want to cluster instruments into content-groups (Hogrefe-style, but fitted
to what's actually in this library) and make that grouping a mandatory,
schema-validated field on every library instrument.

## Scope

- **In scope**: a new mandatory `Study.Category` field on the 104 official
  library templates; schema + validator enforcement for the library only;
  classifying all 104 existing instruments; propagating `Category` into the
  generated `index.json` / instrument registry; grouping the Survey
  Questionnaires panel UI by category.
- **Out of scope**: requiring `Category` on real project/participant
  `survey.json` sidecars (see decision below); a true external
  ontology/controlled-vocabulary mapping (SNOMED/NIH-CDE) — that already has
  a reserved home in `instrument-registry.schema.json`'s unused `Vocabulary`
  field and is a separate future pass; updating
  `official/create_new_survey/survey_import_template.xlsx` (binary file, not
  code — noted for a human follow-up); the Survey Customizer tool
  (`survey_customizer.html`/`survey-customizer.js`), which does not render
  its own copy of this list and only links out to Survey Generator.

## Decisions

### Validation scope: library templates only, not project data

`survey.schema.json` is shared by both the curated library templates and
every real participant's exported `sub-*_survey-*.json`. Making `Category`
required everywhere would retroactively break validation for every
already-exported dataset and any hand-authored custom questionnaire. Category
is therefore mandatory only for files under `official/library/survey/`.

### One primary category per instrument, closed enum

`Study.Category` is a single string, not an array of tags — matches the
Hogrefe-style UX (one home per test) and keeps "mandatory" simple (must be
one of a fixed list, not a non-empty array). The category values are a closed
`enum` baked into `survey.schema.json` (like the existing `LicenseID` enum),
so a typo is caught by schema validation immediately rather than needing a
separate vocabulary file kept in sync by hand.

### Taxonomy: bottom-up from the actual corpus, not an imported framework

Two alternatives were considered and rejected:
- **Hogrefe's own top-level categories** (Persönlichkeitstests, Klinische
  Verfahren, Intelligenztests, Schultests, ...): ~5 of Hogrefe's 9 categories
  would hold 0-2 of our instruments, while 70+ of our 104 would pile into
  just "Persönlichkeitstests" and "Klinische Verfahren" — not useful for
  browsing.
- **A published clinical construct ontology (RDoC or HiTOP)**: the most
  literally "ontological" option, but both are psychopathology-research
  frameworks built around ~6 domains (e.g. "Negative Valence Systems",
  "Arousal/Regulatory Systems"). Relationship-satisfaction, humor-style,
  procrastination, or worldview/belief instruments don't map onto them
  without real distortion.

Instead, all 104 instrument titles were read and grouped into 12 categories
that fit the actual corpus, covering every instrument without a forced fit.
A 13th, `"Other / Uncategorized"`, exists in the enum as a legitimate escape
hatch for future additions that genuinely don't fit — none of the current 104
use it.

True ontological/controlled-vocabulary mapping (SNOMED, NIH-CDE) is left to
`instrument-registry.schema.json`'s already-reserved (currently unused)
`Vocabulary` field, documented there as "reserved for a future
Neurobagel-annotation pass" — `Category` should not be overloaded to do both
jobs.

## The taxonomy

| Category | Count |
|---|---|
| Personality & Individual Differences | 14 |
| Mood, Anxiety & Clinical Screening | 16 |
| Well-being & Life Satisfaction | 13 |
| Social, Relationships & Attachment | 11 |
| Addictive & Problematic Behaviors | 9 |
| Self-Concept & Self-Esteem | 7 |
| Aggression, Antisocial & Dark Traits | 8 |
| Cognitive & Executive Function | 6 |
| Autism & Neurodevelopmental | 1 |
| Sleep, Health & Physical | 5 |
| Beliefs, Values & Worldview | 7 |
| Educational & Occupational | 7 |
| Other / Uncategorized (reserved, unused today) | 0 |

Total: 104.

### Full instrument → category mapping

(`ShortName` per `official/library/survey/index.json`.)

**Personality & Individual Differences**: AISS, BFI-S, BHPS, BIS, BSRI, CCM-S,
Grit-S, HSQ, ISC, SAPS, SHYNESS, TIPI, TYPE-D, ZKPQ

**Mood, Anxiety & Clinical Screening**: AAI, BITe, CIA, CUDOS, DASS, DASS-21,
ERQ, GAD-7, GPTS, O-LIFE, OCI-R, PHQ-9, PIOS, PSS, RRS, SPQ

**Well-being & Life Satisfaction**: BRCS, BRS, FS, GQ-6, LOT-R, MHC-SF, OHQ,
PTS, SPANE, SWLS, WB-MULTI, WB, WHO-5

**Social, Relationships & Attachment**: ARD, BSAS, CCSS, LAS, LONELINESS-3,
PN-SMD, SAAM, SF-MJS, SWLLS, TRUST, UPLAS

**Addictive & Problematic Behaviors**: BFAS, CUDQ, DMQ-R, GAS, NMP-Q, PIU,
PIUQ, SMD, SOS

**Self-Concept & Self-Esteem**: BES, GSE, HS, ROSENBERG, SCSR, SOC-3, SSES

**Aggression, Antisocial & Dark Traits**: AGG-A, BPAQ, CABS, HSNS, LiES, LSRP,
SD3, VAST

**Cognitive & Executive Function**: CFS, EI, NCS-6, REI, TSIS, webexec

**Autism & Neurodevelopmental**: AQ10

**Sleep, Health & Physical**: CIRENS, EHI, GSQS, HSC-7, SQS

**Beliefs, Values & Worldview**: CNS, CSJAS, GAENE, MASLOW, MATE, SBS-10, SKEP

**Educational & Occupational**: AMAS, BES (higher-ed variant, `bes-alt`),
Teacher burnout (`burnout`), GP, MASI, PCI, TAI-5

This full mapping (keyed by `TaskName`, the filename slug) is the input to
the classification script in the implementation plan — every one of the 104
files gets an explicit, reviewed assignment, not a heuristic guess.

## Implementation

### 1. Schema: `app/schemas/stable/survey.schema.json`

- Add `Study.properties.Category`: `type: string`, `enum` of the 13 values
  above, with a description.
- Add `"Category"` to `Study.required` (alongside `TaskName`, `OriginalName`,
  `Citation`, `LicenseID`).
- Add `"x-prism.officialOnlyRequired": {"Study": ["Category"]}` (new
  annotation, sibling to the existing `projectOnlyRequired`).

### 2. Validation profile: `app/src/schema_manager.py`

`apply_schema_validation_profile()` currently short-circuits immediately for
`profile == "project"` (returns the schema unmodified — the strictest case)
and only relaxes fields for `profile == "official"` (stripping
`projectOnlyRequired` fields from `required`). Extend it symmetrically: for
`profile == "project"`, strip fields listed in `x-prism.officialOnlyRequired`
from `required` the same way. Net effect: `Category` is required when
validating `official/library/survey/*.json` (profile `"official"`, the
default/unmodified schema) and NOT required when validating real project
data (profile `"project"`, now relaxed). No other behavior changes — this
mirrors the existing code shape rather than introducing a new mechanism.

### 3. Classify all 104 library files

A small one-off script applies the `TaskName → Category` mapping above,
writing `Study.Category` into each `official/library/survey/survey-*.json`.
Every file gets touched exactly once; the mapping is the explicit dict from
this spec, not inferred at script-run-time, so the diff is reviewable
file-by-file.

### 4. Registry propagation

- `src/instrument_registry.py::build_registry_index()`: add
  `"Category": study.get("Category", "")` to the per-instrument dict.
- `app/schemas/stable/instrument-registry.schema.json`: add `Category` to the
  `Instruments.additionalProperties.properties` shape.
- Regenerate `official/library/survey/index.json` via
  `python scripts/generate_instrument_registry.py` after step 3.

### 5. UI: Survey Questionnaires panel

- `app/src/web/blueprints/tools_template_info_helpers.py::extract_template_info()`:
  add `"Category": study.get("Category", "")` to the `study_info` dict
  returned as `file.study`.
- `app/static/js/survey-generator.js`:
  - `createTemplateRow()`: add a category badge next to the existing
    Global/Matrix/items/language badges.
  - `renderLibrary()`: for the `survey` section only, group rows under
    category subheaders (fixed order matching the schema enum), instead of
    one flat list. Existing per-row behavior (checkbox, expand, select-all,
    language filtering) is unchanged; select-all/clear for the section still
    targets all rows in `#surveyList` regardless of group.
  - `applySearchFilter()` continues to operate per-row; a group with zero
    visible rows after a search filter should collapse (no empty header
    dangling).

### 6. Tests

- `tests/test_unit.py`: add a test mirroring
  `test_apply_schema_validation_profile_official_relaxes_project_only_fields`
  for the new `officialOnlyRequired` relaxation under `profile="project"`,
  and one confirming `profile="official"` still requires `Category`.
- A test that every `official/library/survey/survey-*.json` file has a
  `Study.Category` present and equal to one of the schema's enum values
  (extends the existing schema-compliance check in
  `app/src/library_validator.py::check_uniqueness`, or a small dedicated
  `tests/test_survey_library_categories.py`).

## Acceptance criteria

- `python3 -c "import jsonschema, json; ..."` (or the existing library
  validator) reports zero schema errors across
  `official/library/survey/*.json` post-classification.
- Validating a real (non-`/official/`) project's `survey.json` sidecar
  without `Study.Category` produces no new validation error.
- `official/library/survey/index.json` regenerated and each instrument entry
  carries its `Category`.
- Survey Questionnaires panel in Studio (Survey Generator page) visibly
  groups instruments under category headers; existing select/search/language
  behavior unchanged.
