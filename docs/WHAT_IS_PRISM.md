# What is PRISM?

PRISM stands for **Psychological Research Information System Model**. It is a
data and metadata model for psychological research datasets.

PRISM extends [BIDS](https://bids.neuroimaging.io/) for workflows that are
common in psychology, such as questionnaires, biometrics, environment
descriptions, and richer study metadata, while keeping compatibility with the
standard BIDS ecosystem.

PRISM Studio is the software that implements these workflows in a web interface
and command-line tools.

## The short version

- **PRISM** is the model.
- **PRISM Studio** is the software.
- **BIDS compatibility remains a core requirement.**

```{important}
PRISM does not replace BIDS. It adds structure for psychological research while
preserving the ability to use BIDS-oriented tooling.
```

## Why PRISM exists

Psychological studies often need data structures that are only partially covered
by standard BIDS practice:

- survey instruments with item-level descriptions and response options
- sociodemographics and participant harmonization
- biometrics and performance testing metadata
- physiology and environment metadata tied to a study workflow
- recipe-based scoring and reproducible derived outputs

PRISM gives those areas a documented structure instead of leaving them as
spreadsheet conventions or lab-specific folder rules.

## How PRISM relates to BIDS

PRISM builds on top of BIDS instead of competing with it.

| Topic | BIDS | PRISM |
|---|---|---|
| Primary baseline | Dataset organization for established BIDS modalities | Adds psychology-focused structure and metadata |
| Surveys | Limited practical support | Rich sidecars, items, response options, and scoring support |
| Biometrics and performance tests | Not a standard focus | Dedicated schema support |
| Environment metadata | Not consistently standardized in practice | Structured sidecars and workflows |
| Validation | BIDS rules | PRISM rules with optional BIDS validation alongside them |
| Scoring and exports | Not part of BIDS itself | Implemented in PRISM Studio workflows |

### What BIDS compatibility means in practice

PRISM Studio keeps BIDS compatibility by organizing PRISM-specific files in a
way that standard BIDS tooling can coexist with. In practice that means:

- your dataset still follows BIDS naming where BIDS applies
- PRISM-specific files are kept explicit instead of hidden in ad-hoc spreadsheets
- PRISM validation can run alongside BIDS validation
- downstream BIDS apps can still operate on the parts of the dataset they expect

## What PRISM Studio adds on top of the model

PRISM Studio turns the model into day-to-day workflows.

### Guided project setup

Create or open a project, manage study metadata, track project-local templates,
and prepare export-ready datasets.

### Conversion workflows

Import source files such as Excel, CSV, SPSS, and LimeSurvey exports and turn
them into structured PRISM/BIDS-compatible outputs.

### Validation

Run structured checks with severity levels, error codes, optional BIDS checks,
and selected auto-fix support.

### Templates and metadata

Build survey and biometrics templates, edit JSON sidecars safely, and keep the
dataset self-documenting.

### Scoring and exports

Define recipes, compute derived values, and export analysis-ready outputs such
as CSV, SPSS, and shareable bundles.

## Supported modalities

The repository currently documents and supports these major modality groups:

| Modality | Typical files | Notes |
|---|---|---|
| Survey | `.tsv` plus `.json` | Questionnaires, assessments, item metadata, response options |
| Biometrics | `.tsv` plus `.json` | Performance and testing workflows |
| Physiological | `.edf`, `.edf+`, or tabular signals plus `.json` | Continuous signals with metadata |
| Eyetracking | `.tsv` plus `.json` | Structured eye-movement metadata and validation |
| Environment | `.tsv` plus `.json` | Environmental or contextual metadata |
| Events | `.tsv` plus `.json` | Task and stimulus timing or event logs |
| Standard BIDS imaging and EEG modalities | Standard BIDS files | Validated under BIDS expectations where applicable |

See [SPECIFICATIONS.md](SPECIFICATIONS.md) and the pages under `docs/specs/` for
the detailed schema layer.

## Project vs dataset

One recurring source of confusion is the difference between a project and the
dataset inside it.

- A **project** is the whole working area: study metadata, `code/`,
  `derivatives/`, `sourcedata/`, local library assets, and the dataset itself.
- A **dataset** is the data structure you validate and ultimately share.

Typical project root:

```text
my_study/
├── dataset_description.json
├── project.json
├── CITATION.cff
├── CHANGES
├── README.md
├── .bidsignore
├── .prismrc.json
├── sourcedata/
├── derivatives/
├── code/
│   ├── library/
│   └── recipes/
└── sub-001/
    └── survey/
        ├── sub-001_task-demo_survey.tsv
        └── sub-001_task-demo_survey.json
```

`participants.tsv` and `participants.json` aren't part of this "at creation" tree —
they're written once you run the participants/sociodemographics import step.

PRISM encourages a YODA-style project layout because it keeps incoming source
material, validated data, code, and derived outputs separate.

## DataLad in the PRISM model

DataLad is optional, but important for larger projects and provenance-aware
workflows. PRISM Studio is designed to work with DataLad-friendly project
layouts instead of forcing a separate structure.

Use DataLad when you need:

- large-file handling with provenance
- portable project history
- reproducible export or mutation workflows
- project structures that scale beyond small local folders

For the user-facing guidance, see [DATALAD.md](DATALAD.md).

## Example: survey data as self-documenting data

One benefit of PRISM is that tabular data can carry rich metadata in sidecars.

```json
{
  "SurveyName": "Wellbeing Demo",
  "Items": [
    {
      "ItemID": "WB01",
      "Question": {
        "en": "I felt motivated to start my daily tasks"
      },
      "ResponseOptions": {
        "0": "At no time",
        "1": "Some of the time",
        "2": "Most of the time",
        "3": "All of the time"
      }
    }
  ]
}
```

That makes the data easier to understand, validate, reuse, and export.

## Where to go next

- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) for the repo and feature map
- [INSTALLATION.md](INSTALLATION.md) for setup
- [QUICK_START.md](QUICK_START.md) for a first successful workflow
- [WORKSHOP.md](WORKSHOP.md) for a fuller hands-on example
