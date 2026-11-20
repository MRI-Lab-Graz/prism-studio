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
date: 20 November 2026
bibliography: paper.bib
---

# Summary

Studies of human behavior rarely produce a single kind of data: a single session can yield questionnaires, biometrics, physiological recordings, biosamples, environmental measurements, eye tracking, and brain imaging. Yet raw data files are rarely self-explanatory — a column of questionnaire responses is meaningless without knowing the item wording, each response option's label, which items are reverse-scored, or which version and language was administered.

Neuroimaging addressed an equivalent problem with the Brain Imaging Data Structure (BIDS) [@gorgolewski2016bids], which pairs every data file with a same-named JSON sidecar, uses predictable paths, and provides an official validator. Its vocabulary, however, is centrally governed, meaning measurements the specification does not anticipate remain undescribed.

PRISM (Principled Research Information & Sidecar Model) — named for its commitment to the FAIR data principles [@wilkinson2016fair], applied at the level of the individual file rather than the repository as a whole — preserves that core principle while opening up the vocabulary. File-naming rules, modality definitions, and sidecar contracts are JSON schemas, and the term registry behind them is data too; any lab can extend both locally, so an instrument PRISM has never encountered can be fully described and validated without modifying the software. PRISM ships a validator, format converters, and PRISM Studio, a local graphical interface paired with a matching command-line interface. Its modalities and templates are oriented toward psychology, but the mechanism is domain-agnostic.

# Statement of need

In practice, behavioral data is still described by a codebook: a spreadsheet or PDF appendix listing item wordings, response options, and scoring rules beside the data rather than inside it. Nothing enforces that such codebooks are complete, stay synchronized with the file they describe, or cover the recorded values, and their layout is idiosyncratic, so no tool can read one reliably. Mismatches surface late, when a second analyst opens the dataset.

BIDS has expanded steadily across neuroimaging modalities, yet the community extension process through which new modalities are formally adopted can take years. Meanwhile, research data continues to outpace any central specification: new instruments, translations, short forms, and novel sensors generate measurements that remain undescribed. Capturing such data with imaging-grade rigor requires three things. First, the description contract must be open, so a lab can define a new instrument or modality itself and validate it immediately. Second, the meaning of a term must be linkable to the vocabularies the wider community already uses, without changing the data. Third, reaching a valid dataset must be achievable by the researchers who collected it, not only by those who can write code: the tooling has to meet data where it already is — an Excel, CSV, SPSS, or survey-platform export with a codebook — and lead to a validated dataset through a graphical interface as readily as a script.

PRISM datasets remain valid BIDS datasets, with PRISM-specific files declared in `.bidsignore`. The intended users are researchers, data stewards, and tool developers who need richer, machine-checkable descriptions than a central standard provides.

# State of the field

Describing research data at scale requires a vocabulary that can grow where the data is produced. Any central enumeration of measurements — a modality list, a curated instrument database — stalls on what has not yet been encoded, because it scales with maintainer effort, not with the variety of measurements researchers produce.

Even BIDS is not fully consistent with its own principle here: its one home for this kind of data, `phenotype/`, is a flat table with one row per participant and no per-file sidecar, leaving no place for session-, run-, or variant-level detail. PRISM applies the sidecar principle uniformly: every administration is its own sidecar-described file, with `phenotype/` available only as an optional export.

The closest neighbor is Psych-DS [@psychds], which pairs CSV files under `data/` with dataset-level JSON-LD metadata; it targets dataset structure rather than a per-file, per-item contract, and defines its own layout instead of remaining valid BIDS. DataLad [@halchenko2021datalad] versions and distributes datasets without defining file contents; PRISM composes with it rather than competing, optionally recording provenance for dataset mutations and recipe scoring. Elsewhere, instrument-specific converters require a code contribution before an uncoded instrument can be described at all.

PRISM fixes the shape of a description and leaves its vocabulary open. An unsupported instrument becomes a data-authoring task rather than a feature request, resolvable locally and immediately without upstream approval.

# Software design

**Implementation.** PRISM is written in Python (3.10+). The validation engine needs only `jsonschema`, `defusedxml`, and a bundled engine for the official BIDS validator (`bids-validator-deno`), so `prism-validator` runs on a machine carrying none of the Studio stack. The BIDS pass is on by default and fails closed: if it cannot run, the run reports an error rather than passing silently. PRISM Studio is a local Flask application served by `waitress` in a native window, with a plain-JavaScript frontend and no build step. Converters (`pandas`, `openpyxl`, `pyreadstat`, `pyreadr`) read CSV, Excel, SPSS, R, LimeSurvey, and Pavlovia exports.

**One implementation, two front ends.** Every Studio action except project setup is a command-line command that Studio merely triggers; a difference between the two is a bug, and a parity test runs both on identical project copies and compares the files they write. Figure 1 shows the shared engine: adapters and contracts create and validate sidecar-described datasets.

![PRISM combines research data and schemas in one engine, creating and validating BIDS-compatible datasets through Studio or the command line.](prism_workflow.pdf)

**How validation works.** A run walks the dataset tree in four layers. *Structure*: file paths are matched against the entity grammar in `entities.schema.json`, and subject and session labels are checked for consistency; session labels are free-form strings and never normalized (`ses-1`, `ses-01`, `ses-pre` stay distinct). *Metadata*: every data file needs a JSON sidecar, resolved through BIDS inheritance and validated against the modality's schema (draft-07). *Content*: each tabular value is checked against its sidecar's definition — declared `Levels`, data type, numeric range — with `n/a` for missing data and instrument variants honoured. *Delegation*: the official BIDS Validator runs over the same tree. Findings are errors or warnings in one JSON report, with a non-zero exit status on errors.

**The specification is data, and it is separate from the software.** Entity order, modality suffixes, file extensions, and sidecar contracts are JSON schemas — a rules file plus twelve versioned schemas, six of them modalities (survey, biometrics, biosample, environment, physiological recordings, events) — so adding a modality or a site-specific check means adding data rather than changing the software. Checks no schema can express are Python modules dropped into the dataset's `validators/` directory and loaded as plugins. The community schemas and the term registry are maintained in their own repository (`prism-specification`) and vendored into Studio as a hash-locked copy of a tagged release, so the specification can evolve and be cited independently of the application. Each run reads one specification object built for that run, so a project's local additions never leak into another.

**A project carries its own specification.** Terms that are not yet official live in the project (`code/specification/`) in the shape of a proposal, and additions to an existing schema are declared as patches checked by the same code that governs the official schemas and applied to a copy, never to files on disk. The official registry always wins, local additions apply to that project's run only, and files from a shared project are treated as untrusted. A local term can be sent upstream (`spec propose`), so the path from "my lab needs this" to "the community has it" is a data pipeline, not a feature request.

**Meaning is linked, never written into the data.** PRISM IDs are stable and resolvable (`https://w3id.org/prism-specification/...`). Links from an ID to an external vocabulary — currently 29, among them SNOMED CT, LOINC, ChEBI, NCIT, HPO, and Wikidata — live in a separate, checked `mappings/` layer; the DASS templates, for example, link every item to the SNOMED CT score of its subscale. A lab checks its own mapping files with `terms check-links`. Data files are never rewritten to carry meaning, which keeps the dataset valid BIDS.

**Strictness profiles and versions.** An `x-prism` block in each schema marks fields required only of the curated library or only of project data, so bundled templates can be held to curation-grade completeness without rejecting a researcher's in-progress questionnaire. Three schema versions (`stable`, `v0.1`, `v0.2`) ship side by side, selectable per run, so validation stays reproducible.

**Nothing is written without a preview.** `--fix` auto-repairs common issues, and `--dry-run` reports what it would change; converters preview their output and report overwrite conflicts instead of resolving them silently. Participant data stays local, and the only network call (environmental enrichment) is opt-in. In DataLad projects text files are never annexed, and publishing is refused for targets that would expose `sourcedata/`.

**The current library.** The bundled library is the psychology instance of the model: a demonstration questionnaire, the DASS templates (licensing recorded), and biometrics and biosample templates. A project or user can point PRISM at further libraries (`globalLibraryRoot`, `personalLibraryPath`).

**Testing.** More than 650 test files cover the engine and Studio routes, with browser-side tests, in continuous integration alongside `ruff`, `mypy`, secret scanning, and architectural-invariant checks. A seeded generator also builds a synthetic dataset of deliberately hostile cases (distinct session labels, non-ASCII subject labels, invalid timestamps) whose documented outcomes are asserted case by case.


# Research impact statement

PRISM was built for, and used to prepare, the mixed-modality Austrian NeuroCloud dataset *Creativity: a (white) matter of connectivity* [@koschutnig2026creativity], whose metadata record names PRISM Studio as its creation tool; the Austrian NeuroCloud (ANC) repository, which holds the CoreTrustSeal, officially accepts PRISM-formatted datasets in its data format requirements (<https://handbook.anc.plus.ac.at/terms/data_format_requirements/>). Beyond the developers' group, PRISM is used by the Department of Biological Psychology at the University of Graz and by colleagues at the University of Salzburg. It was presented at CLARIAH-AT's *Tag der guten Daten 2026* (Graz, February 2026), and a graduate seminar (PSY.91C) on it runs in the winter semester 2026/27, alongside hands-on workshops. Development is public, and issues from users outside the core team are tracked openly and addressed in later releases. The repository provides tagged, archived releases [@prism_software] (currently 1.26.0), cross-platform builds, workshop materials, and example datasets including the synthetic hostile dataset, so that other groups can test the workflows locally.

# Conflict of interest

The authors declare no competing interests.

# AI usage disclosure

GPT-5.3 (OpenAI), Claude Sonnet 5, Sonnet 5.5 and Opus 4.6 (Anthropic), and GitHub Copilot (model/version unrecorded) assisted with code, documentation, and manuscript drafting. The authors reviewed all output, made every software-design and framing decision, and accept full responsibility for the software and this paper.

# Acknowledgements

The authors thank the MRI-Lab Graz community for testing, issue reports, and feedback, and the BIDS community for the standard on which PRISM builds.

# References
