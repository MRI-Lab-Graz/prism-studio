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

Studies of human behavior rarely produce a single kind of data: one session
can yield questionnaires, biometrics, physiological recordings, eye tracking,
and brain imaging. The numbers alone carry little meaning — a column of
questionnaire responses is uninterpretable without the item wording, the
label attached to each response level, which items are reverse-scored, and
which version or language was administered.

Neuroimaging solved the equivalent problem with the Brain Imaging Data
Structure (BIDS) [@gorgolewski2016bids], which pairs every data file with a
JSON sidecar of the same name, organizes files under predictable paths, and
ships an official validator, making datasets portable across analysis
pipelines. Its vocabulary, however, is centrally governed, so measurements
the specification does not anticipate stay undescribed.

PRISM (Principled Research Information & Sidecar Model) keeps that principle
and opens the vocabulary. File-naming rules, modality definitions, and
sidecar contracts are JSON schemas that a lab can extend, so an instrument
PRISM has never seen can be described and fully validated without changing
the software. It ships a validator, converters, and PRISM Studio, a local
graphical interface with a matching command-line interface. Its current
modalities and template library serve psychological research, but nothing in
the mechanism is specific to that domain: psychology is PRISM's first
application, not its boundary.

# Statement of need

A new BIDS modality enters through a community extension process that can
take years, yet research data keeps producing measurements no specification
anticipates: new instruments, translations, short forms, and new sensors.
Describing such data with imaging-grade rigor needs two things. First, the
description contract must be open, so a lab can define a new instrument or
modality itself and validate it immediately.
Second, the path to a valid dataset must be practical for researchers whose
starting point is a survey-platform export and a spreadsheet codebook.

PRISM datasets remain BIDS datasets, with PRISM-specific files declared in
`.bidsignore`. The intended users are researchers, data stewards, and tool
developers who need richer, checkable descriptions than a central standard
provides, without giving up BIDS tooling.

# State of the field

BIDS `phenotype/` tables store participant-level measures as flat tables and
cannot retain session-, run-, and variant-level context for repeated
administrations. PRISM therefore stores questionnaires as subject-, session-,
and run-resolved files and offers an optional, deliberately lossy export to
`phenotype/`. DataLad [@halchenko2021datalad] versions and distributes
datasets but does not define what the files in them must contain. Survey
platforms such as LimeSurvey administer instruments but do not produce a
validated, self-describing dataset.

Instrument-specific converters and curated questionnaire databases handle new
measurements by enumeration: an instrument nobody has encoded requires a code
contribution. PRISM fixes the shape of a description and leaves its
vocabulary open, so an unsupported instrument is a data-authoring task for the
researcher who has it rather than a feature request.

# Software design

**The model is data.** Entity order, modality suffixes, file extensions, and
allowed entity values are read from a rules file (`entities.schema.json`);
sidecar contracts are versioned JSON schemas. A survey template's item names
are not fixed: any item is valid if it satisfies the item contract
(`Description`, optional `Levels`, `MinValue`/`MaxValue`, `DataType`, `Unit`,
and so on). Items carry `ApplicableVersions` for short and long forms, and
`Aliases` reconcile the same question under different identifiers across
studies. Adding a modality requires a rules entry and a JSON schema;
converters and Studio screens are optional conveniences built on top.

**Validation is the core.** `prism-validator` checks sidecars against their
schemas and, with `--bids`, also runs the official BIDS Validator, merging
both into one report without reimplementing BIDS rules. Reports are emitted as
JSON, SARIF, JUnit, Markdown, or CSV, so a dataset can be checked in
continuous integration like software; the validator ships as a standalone
executable, a Docker image, and a GitHub Action. Schema versions are
selectable per run (`--schema-version`), templates can be validated before use
(`--validate-templates`), labs can add their own checks as plugins, and
automatic fixes are previewed with `--dry-run` before `--fix` writes anything.

**The path to a valid dataset.** Converters ask domain questions, such as which
column identifies the participant, and derive correct file names from the
rules file instead of expecting users to type them. Helper commands reshape
wide spreadsheets to long format, build `participants.tsv`, compute scores
from raw items with provenance sidecars (recipe and PRISM versions, SHA-256
input hashes), and prepare anonymized exports. Every Studio action
is available from the command line. Participant data stays on the local
machine; the only network access is optional environmental enrichment, off by
default.

**The current library.** PRISM bundles 103 questionnaire templates and one
biometrics template. Most derive from the PsyToolkit survey library
[@stoet2010psytoolkit; @stoet2017psytoolkit]; each records its upstream
licensing statement, and instruments with unclear terms are excluded.

**Testing.** A seeded generator (`prism_tools dataset build-hostile-demo`)
builds an entirely synthetic dataset with 59 deliberately hostile cases across
nine pipeline areas: for example the session labels `ses-1`, `ses-01`, and
`ses-pre`, which must stay distinct, a non-ASCII subject label, broken scoring
recipes, and invalid scanner timestamps. Automated tests check the expected
outcome of each case in continuous integration.

# Research impact statement

PRISM was built for, and used to prepare, the mixed-modality Austrian
NeuroCloud dataset *Creativity: a (white) matter of connectivity*
[@koschutnig2026creativity], whose metadata record names PRISM Studio as its
creation tool. This is use by the developer's own group; the dataset is
access-restricted under the Austrian NeuroCloud data-use agreement. The
repository provides tagged releases (currently 1.18.0), cross-platform builds,
workshop materials, and example datasets including the synthetic hostile
dataset, so that other groups can test the workflows locally.

# Conflict of interest

The authors declare no competing interests.

# AI usage disclosure

GPT-5.3 (OpenAI), Claude Sonnet 5 and Claude Opus 4.6 (Anthropic), and
GitHub Copilot were used to assist with code drafting and refactoring,
documentation, and manuscript drafting and editing. The GitHub Copilot model
and version were not recorded. The authors reviewed all AI-assisted output,
accept full responsibility for the software and this paper, and made the
substantive software-design and framing decisions.

# Acknowledgements

The authors thank the MRI-Lab Graz community for testing, issue reports, and
feedback, and the BIDS community for the standard on which PRISM builds.

# References
