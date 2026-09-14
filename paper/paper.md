---
title: "PRISM: an extensible data-and-sidecar model for describing and validating research data"
tags:
  - research data management
  - metadata
  - validation
  - JSON schema
  - BIDS
  - psychology
authors:
  - name: Karl Koschutnig
    orcid: 0000-0001-6234-0498
    affiliation: "1"
  - name: Bernhard Weber
    affiliation: "1"
  - name: David Matischek
    affiliation: "1"
affiliations:
  - index: 1
    name: MRI-Lab Graz, Department of Psychology, University of Graz, Graz, Austria
date: 14 September 2026
bibliography: paper.bib
---

# Summary

Any measurement becomes self-describing and machine-checkable when it is
stored next to a JSON sidecar that explains it: a data file (`.nii.gz`,
`.tsv`, `.edf`, or any other format) holds the raw values, and a file of the
same name describes what those values mean. PRISM (Principled Research
Information & Sidecar Model) organizes research data around this principle
along three axes (subject, session, and modality) and keeps every part of the
model in data rather than in code. File-naming rules, modality definitions,
and sidecar contracts are JSON schemas that a lab can add to or change.

PRISM ships a validator, converters, and PRISM Studio, a local graphical
interface with a matching command-line interface. Its current modalities and
template library serve psychological research: questionnaires, biometrics,
physiological recordings, eye tracking, events, and environmental context.
Psychology is PRISM's first application, not its boundary; the same mechanism
applies to any field that pairs data files with descriptions.

# Statement of need

The Brain Imaging Data Structure (BIDS) [@gorgolewski2016bids] proved that the
data-and-sidecar principle works at scale. Predictable paths, JSON sidecars,
and an official validator made neuroimaging datasets portable across analysis
pipelines. BIDS, however, is centrally governed: its modalities and metadata
fields are defined by the specification, and a new modality enters through a
community extension process that can take years. Content outside that
specification stays undescribed. For a questionnaire, this includes the item
wording, the labels of each response level, reverse-scored items, the
administered version or language, and how a subscale score is computed.

Research data keeps producing measurements that no central specification
anticipates: new instruments, translations, short forms, new sensors, and new
fields. Two things are needed for such data to be described with the same
rigor as imaging data. First, the description contract must be open, so a lab
can define a new instrument or modality itself and validate it immediately.
Second, the path to a valid dataset must be practical for researchers whose
starting point is a survey-platform export and a spreadsheet codebook.

PRISM keeps the principle and opens the vocabulary. A lab describes an
instrument PRISM has never seen, in a language it does not ship, as a JSON
template and gets full validation without changing the software. PRISM
datasets remain BIDS datasets: PRISM-specific files are declared in
`.bidsignore`, and the validator can run the official BIDS Validator
alongside its own checks. The intended users are researchers, data stewards,
and tool developers who need richer, checkable descriptions than a central
standard provides, without giving up BIDS tooling.

# State of the field

BIDS and its validator remain the reference for structural compliance of
neuroimaging data [@gorgolewski2016bids]; PRISM builds on them rather than
replacing them. BIDS `phenotype/` tables store participant-level measures as
flat tables and cannot retain session-, run-, and variant-level context for
repeated administrations. PRISM therefore stores questionnaires as subject-,
session-, and run-resolved files and offers an optional, deliberately lossy
export to `phenotype/`. DataLad [@halchenko2021datalad] versions and
distributes datasets but does not define what the files in them must
contain. Survey platforms such as LimeSurvey administer instruments but do not
produce a validated, self-describing dataset.

Instrument-specific converters and curated questionnaire databases handle new
measurements by enumeration: an instrument nobody has encoded requires a code
contribution. PRISM fixes the shape of a description and leaves its
vocabulary open, so an unsupported instrument is a data-authoring task for the
researcher who has it. The bundled library is a starting point rather than a
limit.

# Software design

**The model is data.** Entity order, modality suffixes, file extensions, and
allowed entity values are read from a rules file (`entities.schema.json`);
sidecar contracts are versioned JSON schemas. A survey template's item names
are not fixed: any item is valid if it satisfies the item contract
(`Description`, optional `Levels`, `MinValue`/`MaxValue`, `DataType`, `Unit`,
and so on). Items can carry `ApplicableVersions` for short and long forms,
and `Aliases` reconcile the same question under different identifiers across
studies. Adding a modality to the data model and validator requires a rules
entry and a JSON schema; converters and Studio screens are optional
conveniences built on top.

**Validation is the core.** `prism-validator` checks sidecars against their
schemas and, with `--bids`, also runs the official BIDS Validator, merging
both into one report without reimplementing BIDS rules. Reports are available
as JSON, SARIF, JUnit, Markdown, or CSV, so a dataset can be checked in
continuous integration like software; the validator is distributed as a
standalone executable, a Docker image, and a GitHub Action. Schema versions
are selectable per run (`--schema-version`), templates can be validated before
use (`--validate-templates`), labs can add their own checks as plugins, and
automatic fixes are previewed with `--dry-run` before `--fix` writes anything.

**The path to a valid dataset.** Converters ask domain questions, such as which
column identifies the participant, and derive correct file names from the
rules file instead of expecting users to type them. Helper commands reshape
wide spreadsheets to long format, build `participants.tsv`, compute scores
from raw items with provenance sidecars (recipe version, PRISM version, and
SHA-256 hashes of inputs), and prepare anonymized exports. Every Studio action
is available from the command line. Participant data stays on the local
machine; the only network access is optional environmental enrichment
(weather, air quality), which is off by default.

**The current library.** PRISM bundles 103 questionnaire templates and one
biometrics template. Most questionnaire templates are derived from the
PsyToolkit survey library [@stoet2010psytoolkit; @stoet2017psytoolkit]; each
records its upstream licensing statement, and instruments with unclear terms
are excluded.

**Testing.** A seeded generator (`prism_tools dataset build-hostile-demo`)
builds an entirely synthetic dataset with 59 deliberately hostile cases across
nine pipeline areas, for example the session labels `ses-1`, `ses-01`, and
`ses-pre` (which must stay distinct), a non-ASCII subject label, broken scoring
recipes, and invalid scanner timestamps. Automated tests check the expected
outcome of these cases in continuous integration.

# Research impact statement

PRISM was built for, and used to prepare, the mixed-modality Austrian
NeuroCloud dataset *Creativity: a (white) matter of connectivity*
[@koschutnig2026creativity], whose metadata record names PRISM Studio as its
creation tool. This is use by the developer's own group; the dataset is
access-restricted under the Austrian NeuroCloud data-use agreement. The
repository provides tagged releases (currently 1.18.0), cross-platform builds
for macOS, Windows, and Linux, workshop materials, and example datasets
including the synthetic hostile dataset, so that other groups can test the
workflows locally.

# AI usage disclosure

Claude (Anthropic) and GitHub Copilot were used to assist with code drafting
and refactoring, documentation, and manuscript drafting and editing. The
GitHub Copilot model and version were not recorded. The authors reviewed all
AI-assisted output, accept full responsibility for the software and this
paper, and made the substantive software-design and framing decisions.

# Acknowledgements

The authors thank the MRI-Lab Graz community for testing, issue reports, and
feedback, and the BIDS community for the standard on which PRISM builds.

# References
