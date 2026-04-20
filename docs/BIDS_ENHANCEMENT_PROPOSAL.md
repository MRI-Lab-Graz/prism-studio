# BIDS Enhancement Proposal — Structured Phenotypic / Survey Data

> **Status**: Draft for community discussion  
> **Authors**: PRISM Studio Team, MRI-Lab-Graz  
> **Related PR draft**: [BIDS_SURVEY_MODALITY_PR_DRAFT.md](BIDS_SURVEY_MODALITY_PR_DRAFT.md)  
> **Reference implementation**: [PRISM Studio](https://github.com/MRI-Lab-Graz/prism-studio)

---

## Overview

This document describes the precise schema changes needed to formally support
structured, session-resolved instrument-based phenotypic data in the BIDS
specification.  It is intended as a working document when opening a fork of
[`bids-standard/bids-specification`](https://github.com/bids-standard/bids-specification)
and submitting a pull request.

The proposal incorporates feedback received from the BIDS community:

- Re-use **`phenotype/`** as the primary modality directory (instead of a new
  `survey/` folder), because BIDS already recognises the term and it avoids
  fragmenting the phenotyping namespace.
- Introduce the suffix **`pheno`** for instrument-resolved TSV files.
- Propose a new entity **`inst`** (instrument) as a semantically precise label
  that identifies the administered instrument without overloading `task`.
  Alternative names under discussion: `assess`, `form`, `meas`, `table`.
- Keep `phenotype/` as a valid **aggregate / derived** representation as well,
  so existing datasets remain fully compatible.

---

## 1. Motivation

BIDS is strongest when its canonical structures reflect how data are actually
acquired.  For imaging, physio, events, and other modalities the normative
pattern is a subject-resolved structure first, with higher-level summaries
produced as derivatives later.

Instrument-based phenotypic data fit this same pattern.  Treating `phenotype/`
as a flat, top-level aggregate directory flattens the acquisition context at the
exact point where BIDS usually preserves it.

A structured phenotype modality would:

- preserve provenance and administration context,
- support repeated assessments across sessions and runs,
- keep sidecar metadata co-located with corresponding data files, and
- still allow aggregated phenotype tables to be generated later.

A working reference implementation already exists in PRISM Studio; the proposed
changes reflect patterns that are already practical in the field.

---

## 2. Proposed schema changes

The sections below show the **exact file changes** needed in a fork of
`bids-standard/bids-specification`.

### 2.1 `src/schema/objects/datatypes.yaml`

The existing `phenotype` entry describes only the aggregate directory.  Extend
it (or add a companion entry) to also cover subject-session-resolved data:

```yaml
# Existing entry — keep as-is for backward compat
phenotype:
  value: phenotype
  display_name: Phenotype
  description: |
    Participant-level measurement data (for example, responses from multiple
    questionnaires) that may be stored either as an aggregate file in the
    top-level `phenotype/` directory **or** as subject- and session-resolved
    files under `sub-<label>/[ses-<label>/]phenotype/`.
    The subject-resolved form preserves acquisition provenance and supports
    repeated assessments across sessions and runs.
```

No additional entry is strictly required because we re-use the existing
datatype name; the structural flexibility is expressed in the file rules
(section 2.3).

### 2.2 `src/schema/objects/suffixes.yaml`

Add the `pheno` suffix.  Position it alphabetically near the `physio` / `beh`
cluster:

```yaml
pheno:
  value: pheno
  display_name: Phenotypic recording
  description: |
    Structured responses collected with a standardised instrument (questionnaire,
    rating scale, cognitive battery, clinical assessment, etc.).
    Each file contains the responses of a single participant for one
    administration of one instrument.
    A JSON sidecar MUST accompany the TSV file and MUST describe each column.
    Aggregate representations may additionally be stored in `phenotype/` at the
    dataset root using the existing phenotype conventions.
```

### 2.3 `src/schema/rules/files/raw/phenotype.yaml`

Create this new file to define file-naming rules for subject-resolved phenotype
data:

```yaml
# Subject- and session-resolved instrument-based phenotypic data.
#
# Canonical form:
#   sub-<label>[_ses-<label>][_inst-<label>][_acq-<label>][_run-<index>]_pheno.tsv
#   sub-<label>[_ses-<label>][_inst-<label>][_acq-<label>][_run-<index>]_pheno.json
#
# The `inst` entity identifies the administered instrument (e.g., pss, phq9).
# `acq` may encode an instrument version or administration variant.
# `run` distinguishes repeated administrations within the same session.

pheno:
  suffixes:
    - pheno
  extensions:
    - .tsv
    - .json
  datatypes:
    - phenotype
  entities:
    subject: required
    session: optional
    inst: optional
    acquisition: optional
    run: optional
```

### 2.4 `src/schema/rules/modalities.yaml`

Add `phenotype` to the modalities mapping so the datatype is associated with
the correct high-level modality:

```yaml
# Add to existing file:
phenotype:
  datatypes:
    - phenotype
```

### 2.5 `src/schema/objects/entities.yaml`

Add the `inst` entity.  Alphabetical position places it between `hemisphere`
and `inversion`:

```yaml
inst:
  name: inst
  display_name: Instrument
  description: |
    The `inst-<label>` entity identifies the administered instrument
    (questionnaire, rating scale, cognitive battery, clinical assessment, etc.).
    The label SHOULD match the task name used in the accompanying sidecar JSON
    and SHOULD be a short, URL-safe identifier (for example, `pss`, `phq9`,
    `stai`, `beck`).
    This entity is currently only defined for the `phenotype` datatype.
  type: string
  format: label
```

> **Alternative names under active discussion**: `assess`, `form`, `table`,
> `meas`, `lab`, `survey`, `quiz`.  The working group is encouraged to settle
> on the canonical name before merging.

### 2.6 `src/schema/rules/entities.yaml`

Insert `inst` in the canonical entity ordering.  It should appear after `task`
and before `acquisition` to maintain the logical grouping (what was measured →
how it was acquired):

```yaml
- subject
- template
- session
- cohort
- sample
- task
- inst          # <-- new
- tracksys
- acquisition
...
```

---

## 3. Relationship to the existing `phenotype/` convention

The existing `phenotype/` convention describes flat, dataset-level aggregate
tables:

```
study/
└── phenotype/
    ├── pss.tsv
    ├── pss.json
    └── stai.tsv
```

This proposal **does not remove** that convention.  It adds a parallel,
subject-resolved form:

```
study/
├── sub-01/
│   ├── ses-baseline/
│   │   └── phenotype/
│   │       ├── sub-01_ses-baseline_inst-pss_run-01_pheno.tsv
│   │       ├── sub-01_ses-baseline_inst-pss_run-01_pheno.json
│   │       └── sub-01_ses-baseline_inst-stai_pheno.tsv
│   └── ses-week04/
│       └── phenotype/
│           └── sub-01_ses-week04_inst-pss_pheno.tsv
└── phenotype/            # optional aggregate (existing convention)
    ├── pss.tsv
    └── stai.tsv
```

The subject-resolved form is the primary acquisition representation.
The aggregate form is a valid derived / summary representation.

---

## 4. Sidecar JSON requirements

The JSON sidecar for `*_pheno.tsv` files MUST follow the standard BIDS
variable-level description convention and SHOULD include the following
top-level fields (proposed as RECOMMENDED metadata):

| Field | Level | Description |
|---|---|---|
| `InstrumentName` | RECOMMENDED | Full name of the administered instrument |
| `InstrumentVersion` | RECOMMENDED | Version or edition |
| `InstrumentCitation` | OPTIONAL | DOI or citation for the instrument |
| `Language` | RECOMMENDED | Language code actually used (`en`, `de-AT`, …) |
| `Respondent` | RECOMMENDED | Who filled in the form (`self`, `clinician`, `parent`, …) |
| `AdministrationMethod` | OPTIONAL | `online`, `paper`, `interview`, `phone` |
| `SoftwarePlatform` | OPTIONAL | Platform used (e.g., `LimeSurvey`, `REDCap`) |

Column-level descriptions follow the standard BIDS sidecar convention:
each column name maps to an object containing at minimum a `Description` field
and, for coded variables, a `Levels` mapping.

Example:

```json
{
  "InstrumentName": "Perceived Stress Scale",
  "InstrumentVersion": "10-item",
  "InstrumentCitation": "10.1037/t01035-000",
  "Language": "en",
  "Respondent": "self",
  "AdministrationMethod": "online",
  "SoftwarePlatform": "LimeSurvey",
  "PSS01": {
    "Description": "In the last month, how often have you been upset ...",
    "Levels": {
      "0": "Never",
      "1": "Almost never",
      "2": "Sometimes",
      "3": "Fairly often",
      "4": "Very often"
    }
  }
}
```

---

## 5. Backward compatibility

- Existing datasets that use only `phenotype/` aggregate tables are fully
  unaffected; the new rule adds a new valid form without invalidating the old.
- BIDS validators that are unaware of this extension will flag the new
  subject-resolved files as unknown, which is the standard behaviour for
  unrecognised file patterns.  A `.bidsignore` entry can suppress warnings
  during the transition period.
- PRISM Studio already emits a `.bidsignore` rule for `sub-*/ses-*/survey/`
  (its current directory name).  Migrating to `phenotype/` as the directory
  name and `pheno` as the suffix is a one-version migration path.

---

## 6. Migration path for PRISM Studio datasets

| Current PRISM form | Proposed BIDS-canonical form |
|---|---|
| `sub-01/ses-1/survey/sub-01_ses-1_task-pss_survey.tsv` | `sub-01/ses-1/phenotype/sub-01_ses-1_inst-pss_pheno.tsv` |
| `sub-01/ses-1/survey/sub-01_ses-1_task-pss_survey.json` | `sub-01/ses-1/phenotype/sub-01_ses-1_inst-pss_pheno.json` |

PRISM Studio will continue to support the legacy `survey/` path and `_survey`
suffix under `.bidsignore` until an official BIDS version incorporating this
proposal is released.  When that happens, a migration command
(`prism_tools.py migrate phenotype`) will rename files and update sidecars
automatically.

---

## 7. Open questions for the working group

1. **Directory name**: Should subject-resolved phenotypic data live in a
   sub-folder named `phenotype/` (reusing the existing top-level concept) or in
   a new folder (e.g., `pheno/`)?  Reusing `phenotype/` is cleaner but requires
   clarifying that the same name refers to two structural patterns.
2. **Entity name**: The working group should settle on one name from the
   candidate list: `inst`, `assess`, `form`, `meas`, `table`, `lab`, `survey`,
   `quiz`.  `inst` (instrument) and `assess` (assessment) are the two
   strongest candidates based on community feedback.
3. **Suffix**: Is `pheno` the right suffix?  Alternatives: `survey`, `assess`,
   `form`.  `pheno` has the advantage of being distinct and short; `survey` is
   already used by PRISM Studio in practice.
4. **Sidecar requirements**: Should the top-level metadata fields listed in
   section 4 be formally REQUIRED, RECOMMENDED, or OPTIONAL?
5. **Aggregate tables**: Should the existing `phenotype/*.tsv` convention be
   re-classified as a BIDS derivative rather than raw data?

---

## 8. Steps to open the PR against bids-standard/bids-specification

1. Fork `https://github.com/bids-standard/bids-specification` on GitHub.
2. Create a branch: `feat/phenotype-modality-structured`.
3. Apply the changes listed in section 2 to the fork.
4. Add a documentation chapter under `src/` describing the new convention
   (follow the pattern of existing datatype chapters, e.g., `src/modality_specific_files/behavioral-experiments.md`).
5. Run the BIDS schema validator locally to confirm no regressions.
6. Open a draft PR with the title:  
   `[SCHEMA] Add subject-resolved phenotypic data files (pheno suffix, inst entity, phenotype datatype)`  
   and reference this document and the PRISM Studio reference implementation.
7. Link to relevant prior discussions:
   - Any existing GitHub issues about phenotype / questionnaire data in BIDS
   - The BIDS starter kit discussion threads
8. Request review from the BIDS maintainers and the neuroscience working group.

---

## 9. Reference implementation (PRISM Studio)

PRISM Studio already implements this pattern (currently under `survey/`
directory and `_survey` suffix):

- [Survey spec](https://prism-studio.readthedocs.io/en/latest/specs/survey.html)
- [Converter](https://prism-studio.readthedocs.io/en/latest/CONVERTER.html)
- [Template format](https://prism-studio.readthedocs.io/en/latest/TEMPLATES.html)
- [Validator](https://prism-studio.readthedocs.io/en/latest/VALIDATOR.html)
- [Example dataset](https://github.com/MRI-Lab-Graz/prism-studio/tree/main/examples/wellbeing_multi_demo)

The PRISM Studio sidecar JSON (documented in `docs/specs/survey.md`) is
intentionally richer than the minimal BIDS sidecar; the BIDS proposal covers
the intersection that is universally useful, while PRISM-specific fields remain
as extensions.
