# What is PRISM?

Psychological studies often combine well-supported BIDS data with materials that
do not have a shared practical structure: questionnaires and their item-level
response options, participant and sociodemographic data, sport-science
biometrics and performance assessments, environment descriptions, and scoring
rules. Too often, these details remain in spreadsheets or lab-specific folder
conventions, making validation, reuse, and reproducible derived results harder.

PRISM provides documented structures and validation for these psychology-focused
workflows. It extends [BIDS](https://bids.neuroimaging.io/) with explicit files
and metadata for the information BIDS does not standardize, while retaining the
BIDS organization and naming that existing BIDS tools expect. **PRISM Studio**
implements the model as a web interface and command-line tools.

```{important}
PRISM does not replace BIDS. It adds structure for psychological research while
preserving the ability to use BIDS-oriented tooling.
```

PRISM stands for **Psychological Research Information System Model** — the data
and metadata model behind these additions.

## How PRISM relates to BIDS

| Topic | BIDS | PRISM |
|---|---|---|
| Primary baseline | Dataset organization for established BIDS modalities | Adds psychology-focused structure and metadata |
| Surveys | Limited practical support (phenotype) | Rich sidecars, items, response options, and scoring support |
| Biometrics and sport-science performance tests | Not a standard focus | Dedicated schema support for sport-science-oriented assessments and biometrics |
| Environment metadata | Not consistently standardized in practice | Structured sidecars and workflows |
| Validation | BIDS rules | PRISM rules with optional BIDS validation alongside them |
| Scoring and exports | Not part of BIDS itself | Implemented in PRISM Studio workflows |

In practice, BIDS compatibility means: your dataset still follows BIDS naming where
BIDS applies; PRISM-specific files are kept explicit instead of hidden in ad-hoc
spreadsheets; PRISM validation can run alongside BIDS validation; downstream BIDS
apps can still operate on the parts of the dataset they expect.

## What PRISM Studio adds

PRISM Studio turns the model into day-to-day workflows: **guided project setup**
(create/open a project, manage study metadata, track project-local templates,
prepare export-ready datasets); **conversion** (Excel/CSV/SPSS/LimeSurvey exports →
structured PRISM/BIDS outputs); **validation** (severity levels, error codes,
optional BIDS checks, selected auto-fix support); **templates and metadata** (build
survey/biometrics templates, edit JSON sidecars safely); **scoring and exports**
(recipes, derived values, CSV/SPSS/shareable bundles).

## Supported modalities

| Modality | Typical files | Notes |
|---|---|---|
| Survey | `.tsv` plus `.json` | Questionnaires, assessments, item metadata, response options |
| Biometrics | `.tsv` plus `.json` | Sport-science and performance-testing workflows |
| Physiological | `.edf`, `.edf+`, or tabular signals plus `.json` | Continuous signals with metadata |
| Environment | `.tsv` plus `.json` | Environmental or contextual metadata |
| Standard BIDS imaging and EEG modalities | Standard BIDS files | Validated under BIDS expectations where applicable |

See [Specifications](SPECIFICATIONS.md) and the pages under `docs/specs/` for the
detailed schema layer.

## Project vs. dataset

A **project** is the whole working area: study metadata, `code/`, `derivatives/`,
`sourcedata/`, local library assets, and the dataset itself. A **dataset** is the
data structure you validate and ultimately share.

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

`participants.tsv`/`participants.json` aren't part of this "at creation" tree — they're
written once you run the participants import step. PRISM encourages a YODA-style
layout, keeping incoming source material, validated data, code, and derived outputs
separate.

DataLad is optional but useful for larger projects: large-file handling with
provenance, portable project history, reproducible export/mutation workflows,
project structures that scale beyond small local folders. See [DataLad](DATALAD.md).

## What's next

- [Project Overview](PROJECT_OVERVIEW.md) for the repo and feature map
- [Installation](INSTALLATION.md) · [Getting Started](TUTORIAL_BEGINNER.md) ·
  [Workshop](WORKSHOP.md)
