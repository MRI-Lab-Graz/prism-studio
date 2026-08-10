# What is PRISM?

PRISM helps psychology and neuroscience teams turn working study files into an
organized, shareable project. It is useful when questionnaires, participant
information, test results, study context, and scoring rules are spread across
spreadsheets and lab-specific folders.

The [Brain Imaging Data Structure (BIDS)](https://bids.neuroimaging.io/) is a
widely used way to organize brain and related research data. PRISM is an add-on
to BIDS, not a replacement: it provides a clear home for study information that
BIDS does not cover in detail, while keeping the usual BIDS files usable with
common BIDS software.

You do not need to know BIDS or run a separate BIDS validation tool to begin.
PRISM Studio provides web and command-line workflows for creating a project,
importing data, checking it, and preparing it for sharing or analysis.

```{important}
PRISM works alongside BIDS; it does not replace it. Standard BIDS files remain
in the form expected by BIDS analysis and validation software.
```

PRISM stands for **Psychological Research Information System Model**. It is the
set of practical rules that PRISM Studio uses to organize study files and their
descriptions.

## How PRISM relates to BIDS

| Topic | What BIDS provides | What PRISM adds |
|---|---|---|
| Main purpose | A widely recognized layout for established brain-data types | Extra structure for psychology-focused study information |
| Project documentation | A basic dataset description | Guided project information for authorship, contact details, ethics, funding, methods, and sharing |
| Surveys | Basic participant-level data support | Question items, answer options, and scoring support |
| Biometrics and performance tests | No dedicated format | A structured way to record assessments such as strength, balance, or fitness tests |
| Study environment | No consistent practical convention | A structured way to record relevant contextual information |
| Checks | Rules for standard BIDS files | PRISM checks, with optional BIDS checks alongside them |
| Scores and exports | No built-in scoring workflow | PRISM Studio workflows for derived scores and shareable exports |

In practice, BIDS compatibility means that files covered by BIDS keep their BIDS
names and organization. PRISM keeps its additional information in clearly
identified files instead of hiding it in spreadsheets. BIDS applications can
continue to work with the standard BIDS files they recognize.

## What PRISM Studio adds

PRISM Studio includes a web application and command-line tools that put PRISM
into everyday practice. It can help you:

- **Make a project ready to share**: require a dataset title, authors, and a
  contact person before a new project is created. PRISM then guides you to add
  the study description, licence, ethics approval, funding, keywords, and
  methods information that others need to find, understand, trust, and reuse
  the dataset.
- **Bring in existing data**: convert Excel, CSV, SPSS, or LimeSurvey exports
  into an organized project.
- **Check your work**: find missing files, inconsistent names, or values that
  need attention. BIDS checks are available when they are useful for your
  project.
- **Describe questionnaires and assessments**: keep question text, answer
  options, and other useful explanations with the data.
- **Calculate and share results**: apply scoring rules and create calculated
  scores, CSV files, SPSS files, or other exports for analysis or sharing.

This supports the FAIR principles: making research data **Findable**,
**Accessible**, **Interoperable**, and **Reusable**. BIDS provides a useful
foundation for organizing many data types; PRISM adds more guided, project-level
documentation so that a shared psychology study is not just a collection of
correctly named files.

## Types of study information

PRISM often stores a data table as a tab-separated value (`.tsv`) file and its
description as a nearby JSON (`.json`) file. A TSV file is similar to a
spreadsheet table; the JSON file explains what its columns and values mean.

| Type of information | Typical files | What it can contain |
|---|---|---|
| Surveys | `.tsv` plus `.json` | Questionnaire and assessment responses, question text, and answer options |
| Biometrics and performance tests | `.tsv` plus `.json` | Assessments such as strength, balance, fitness, or other measurements |
| Physiological recordings | `.edf`, `.edf+`, or tables plus `.json` | Continuous signals and the information needed to interpret them |
| Study environment | `.tsv` plus `.json` | Relevant contextual or environmental information |
| Standard BIDS imaging and EEG data | Standard BIDS files | PRISM leaves these files in their usual BIDS form |

See [Specifications](SPECIFICATIONS.md) and the pages under `docs/specs/` for
the technical file rules.

## Project vs. dataset

A **project** is the whole working folder for a study. It can include the
original files you received, notes about the study, code and scoring rules,
results, and the dataset itself. A **dataset** is the organized collection of
data files that you check and eventually share.

The example below shows a project with one participant (`sub-001`) and one
survey. `sourcedata/` holds incoming files, `code/` holds scripts and scoring
rules, and `derivatives/` holds results created from the data.

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

`participants.tsv` and `participants.json` are created when you import
participant information. PRISM keeps incoming material, checked data, code, and
results separate so that it is easier to understand where each file came from.

You do not need DataLad to use PRISM. For larger or collaborative projects,
[DataLad](DATALAD.md) is an optional tool for tracking project history and
working with large files.

## What's next

- [Getting Started](TUTORIAL_BEGINNER.md) to create your first project
- [Installation](INSTALLATION.md) to install PRISM Studio
- [Project Overview](PROJECT_OVERVIEW.md) for a feature map
- [Workshop](WORKSHOP.md) for a guided exercise
