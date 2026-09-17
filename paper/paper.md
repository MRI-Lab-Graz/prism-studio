---
title: "PRISM: extensible sidecar metadata and validation for research data"
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
    orcid: 0000-0001-6598-7772
    affiliation: "2"
  - name: David Matischek
    orcid: 0009-0009-7882-4070
    affiliation: "2"
affiliations:
  - index: 1
    name: MRI-Lab Graz, Department of Psychology, University of Graz, Graz, Austria
  - index: 2
    name: Institute of Psychology, University of Graz, Graz, Austria
date: 17 September 2026
bibliography: paper.bib
---

# Summary

Studies of human behavior rarely produce a single kind of data: a single session can yield questionnaires, biometrics, physiological recordings, eye tracking, and brain imaging. Yet raw data files are rarely self-explanatory — a column of questionnaire responses is meaningless without knowing the item wording, each response option's label, which items are reverse-scored, or which version and language was administered.

Neuroimaging addressed an equivalent problem with the Brain Imaging Data Structure (BIDS) [@gorgolewski2016bids], which pairs every data file with a JSON sidecar of the same name, organizes files under predictable directory paths, and provides an official validator, making datasets portable across analysis pipelines. Its vocabulary, however, is centrally governed, meaning measurements the specification does not anticipate remain undescribed.

PRISM (Principled Research Information & Sidecar Model) — named for its commitment to the FAIR data principles [@wilkinson2016fair], applied at the level of the individual file rather than the repository as a whole — preserves that core principle while opening up the vocabulary. File-naming rules, modality definitions, and sidecar contracts are defined as JSON schemas that any lab can extend, so an instrument PRISM has never encountered can be fully described and validated without modifying the software itself. PRISM ships a validator, format converters, and PRISM Studio — a local graphical interface paired with a matching command-line interface. Its current modalities and template library are oriented toward psychological research, but the underlying mechanism is entirely domain-agnostic: psychology is PRISM’s first application, not its limit.

# Statement of need

In practice, behavioral data is still described by a codebook: a spreadsheet or PDF appendix listing item wordings, response options, and scoring rules beside the data rather than inside it. Written for human readers, nothing enforces that they are complete, that they stay synchronized with the file they describe, or that the recorded values are among the ones they declare; and their layout is idiosyncratic to each lab, so no tool can read one reliably. Mismatches surface late — when a second analyst opens the dataset and the responses no longer match the scale they were measured on.

BIDS has expanded steadily across neuroimaging modalities, yet the community extension process through which new modalities are formally adopted can take years. Meanwhile, research data continues to outpace any central specification: new instruments, translations, short forms, and novel sensors generate measurements that remain undescribed. Capturing such data with imaging-grade rigor requires two things. First, the description contract must be open, so a lab can define a new instrument or modality itself and validate it immediately. Second, reaching a valid dataset must be achievable by the researchers who collected it, not only by those who can write code: the tooling has to meet data where it already is — an Excel, CSV, SPSS, or survey-platform export with a codebook — and lead to a validated dataset through a graphical interface as readily as a script.

Beyond validation and portability, AI-assisted analysis, automated pipelines, and large-scale data harmonization all become more tractable when every file carries an unambiguous, schema-backed description — without waiting for a central specification to adopt it first.

PRISM datasets remain valid BIDS datasets, with PRISM-specific files declared in `.bidsignore`. The intended users are researchers, data stewards, and tool developers who need richer, machine-checkable descriptions than a central standard can provide — without giving up compatibility with existing BIDS tooling.

# State of the field

Describing research data at scale requires a vocabulary that can grow where the data is produced. Any approach that enumerates measurements centrally — a specification’s modality list, a curated instrument database — supports what has already been encoded and stalls on what has not, because enumeration scales with maintainer effort, not the variety of measurements researchers produce.

Even BIDS is not fully consistent with its own principle here: imaging files get the full data-plus-sidecar treatment, but its one home for this kind of data, `phenotype/`, falls back to a flat table, one row per participant, dropping the per-file sidecar the rest of the standard insists on. That fallback suits a score recorded once per participant, but has no place to keep session-, run-, or variant-level detail once the same instrument is administered more than once. PRISM applies the sidecar principle uniformly instead: every administration is its own sidecar-described file, with the flat `phenotype/` table available only as an optional export when matching the wider BIDS toolchain outweighs that detail.

The closest neighbor is Psych-DS [@psychds], a community standard pairing CSV files under a `data/` directory with dataset-level JSON-LD metadata; it targets dataset structure and file naming rather than a per-file, per-item contract, and defines its own layout rather than remaining a valid BIDS dataset. REDCap [@harris2009redcap] enforces item-level constraints, but only inside its own database — once data is exported, that description is lost. DataLad [@halchenko2021datalad] versions and distributes datasets without defining file contents; PRISM composes with it rather than competing, optionally recording provenance for dataset mutations and recipe scoring. Elsewhere, instrument-specific converters require a code contribution before an uncoded instrument can be described at all.

PRISM fixes the shape of a description and leaves its vocabulary open. An unsupported instrument becomes a data-authoring task rather than a feature request, resolvable locally and immediately without upstream approval.

# Software design

**Implementation.** PRISM is written in Python (3.10+). The validation engine
needs only `jsonschema`, `defusedxml`, and the official `bids-validator` for the
optional BIDS pass, so `prism-validator` runs on a machine carrying none of the
Studio stack. PRISM Studio is a local Flask application served by `waitress` in a
native window (pywebview on macOS, a Chromium application window elsewhere), with
a plain-JavaScript frontend and no build step. Converters add `pandas`,
`openpyxl`, `pyreadstat`, and `pyreadr` to read and write what researchers
exchange: CSV, Excel, SPSS, R, and LimeSurvey archives. Command line and
interface share one core. Figure 1 shows the shared engine: adapters and
contracts create and validate sidecar-described datasets.

![PRISM combines research data and schemas in one engine, creating and validating BIDS-compatible datasets through Studio or the command line.](prism_workflow.pdf)

**How validation works.** A run walks the dataset tree in four layers.
*Structure*: each file path is matched against the entity grammar in
`entities.schema.json` — which entities may appear, in which order, and which
suffixes and extensions a modality permits — and subject and session labels are
checked for consistency across the dataset. *Metadata*: every data file must have
a JSON sidecar; sidecars are resolved through BIDS inheritance, merging the
dataset- and subject-level files before validating the result against the JSON
Schema (draft-07) registered for that modality. *Content*: for tabular modalities
each value is checked against the definition its sidecar gives for that column —
membership in the declared `Levels`, data type, numeric range — with `n/a`
marking missing data and instrument variants honoured, so items of a long form
are not demanded of a short one. *Delegation*: with `--bids`, the official BIDS
Validator runs over the same tree. All findings are tagged as errors or
warnings, merged into one JSON report, with a non-zero exit status on errors.

**Rules live in data, not code.** Entity order, modality suffixes, file extensions, and sidecar contracts are JSON schemas — that rules file plus twelve versioned schemas, six of them modalities — so adding a modality or a site-specific check means adding data rather than changing the software: a new schema, a rules entry, or — for checks no schema can express — a Python module dropped into the dataset's `validators/` directory and picked up automatically as a plugin. The cost is weaker compile-time guarantees and site-specific vocabulary, traded for extension without forking.

**One schema, two strictness profiles.** An `x-prism` block marks fields required only of the curated library (`officialOnlyRequired`) or only of project data (`projectOnlyRequired`), so one schema can demand curation-grade completeness of bundled templates without rejecting a researcher's in-progress questionnaire for lacking a citation.

**Versions coexist so validation stays reproducible.** Three schema versions (`stable`, `v0.1`, `v0.2`) ship side by side, selectable per run, so a dataset can still be validated against the rules it was authored under.

**Nothing is written without a preview.** `--dry-run` precedes `--fix`, conversions show what they will produce, and colliding operations report the conflict instead of resolving it silently. Participant data stays on the local machine; the single network call, environmental enrichment, is opt-in.

**The current library.** The bundled library is the psychology instance of the model, not the model itself: 103 questionnaire templates and one biometrics template, each with upstream licensing recorded. A project may point PRISM at its own instead.

**Testing.** 3,730 automated tests across 268 files, plus browser-side tests for the Studio interface, run in continuous integration on every push alongside static analysis (`ruff`, `mypy`), secret scanning, and architectural-invariant checks. Data-handling paths are additionally exercised against adversarial input: a seeded generator builds a synthetic dataset of 59 deliberately hostile cases — among them session labels that must stay distinct (`ses-1`, `ses-01`, `ses-pre`), non-ASCII subject labels, and invalid acquisition timestamps — whose documented outcomes 51 tests assert case by case.

Usage-level material — installation, the command reference, converter walkthroughs, and the Studio guide — is maintained as documentation at <https://prism-studio.readthedocs.io> rather than reproduced here.

# Research impact statement

PRISM was built for, and used to prepare, the mixed-modality Austrian
NeuroCloud dataset *Creativity: a (white) matter of connectivity*
[@koschutnig2026creativity], whose metadata record names PRISM Studio as its
creation tool. This is use by the developer's own group; the dataset is
access-restricted under the Austrian NeuroCloud data-use agreement. A graduate
seminar built on PRISM, *PRISM in Research Practice: Data Validation for
Psychological Studies* (PSY.91C), is scheduled at the authors' institution for
the winter semester 2026/27, introducing the model to
students preparing their own datasets. Development is public: issues raised by
users outside the core team — installation failures and packaging requests —
are tracked openly and addressed in subsequent
releases. The repository provides tagged, archived releases
[@prism_software] (currently 1.19.0), cross-platform builds,
workshop materials, and example datasets including the synthetic hostile
dataset, so that other groups can test the workflows locally.

# Conflict of interest

The authors declare no competing interests.

# AI usage disclosure

GPT-5.3 (OpenAI), Claude Sonnet 5 and Opus 4.6 (Anthropic), and GitHub
Copilot (model/version unrecorded) assisted with code, documentation, and
manuscript drafting. The authors reviewed all output, made every
software-design and framing decision, and accept full responsibility for the
software and this paper.

# Acknowledgements

The authors thank the MRI-Lab Graz community for testing, issue reports, and
feedback, and the BIDS community for the standard on which PRISM builds.

# References
