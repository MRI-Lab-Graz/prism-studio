---
title: "PRISM: a BIDS-compatible metadata and workflow toolkit for psychological experiment datasets"
tags:
  - psychology
  - neuroscience
  - metadata
  - validation
  - BIDS
  - research software
authors:
  - name: Karl Koschutnig
    orcid: 0000-0001-6234-0498
    affiliation: "1"
affiliations:
  - index: 1
    name: MRI-Lab Graz, Department of Psychology, University of Graz, Graz, Austria
date: 7 August 2026
bibliography: paper.bib
---

# Summary

Psychological and behavioral studies often combine neuroimaging with questionnaires, participants metadata, physiological recordings, eye tracking, and other tabular measurements. The Brain Imaging Data Structure (BIDS) provides an effective baseline for organizing neuroimaging datasets and associated behavioral files [@gorgolewski2016bids], but many psychology workflows still depend on ad hoc spreadsheets, incomplete codebooks, and lab-specific conventions for instrument metadata, response levels, and derived scores.

PRISM is a local-first, open-source toolkit for converting, validating, and documenting psychological experiment datasets while remaining compatible with BIDS. It extends BIDS with additional schema-driven metadata for surveys, biometrics, physiological recordings, eye tracking, and environment/context files, but it does so additively rather than replacing core BIDS conventions. PRISM Studio provides guided workflows for template authoring, conversion, scoring, validation, and export, while the standalone `prism-validator` enables the same data-quality checks in scripted and continuous-integration workflows. Survey templates can be authored as JSON, imported from structured Excel codebooks, or reused from the bundled library of 104 survey and one biometrics template. Templates retain item-level response options, instrument identity, administration details, versions, and variants from collection through validation and sharing.

# Statement of need

Reproducible psychology requires more than stable filenames. Researchers need machine-readable descriptions of survey items, response options, reverse coding, units, acquisition settings, participant variables, and instrument versions. In practice, these details are often scattered across spreadsheets, survey platform exports, protocol documents, and manuscript drafts. This creates ambiguity during reanalysis, cross-study comparison, and long-term reuse.

The gap becomes especially visible in mixed-modality studies. A BIDS-formatted imaging dataset may be structurally correct while still lacking the metadata needed to interpret repeated questionnaire administrations, compare two versions of the same instrument, harmonize participant variables, or regenerate derived scores. These problems are not only about validation; they are also about conversion, template reuse, and keeping metadata synchronized with the data that produced it.

PRISM addresses this need by providing a single workflow layer for psychology-oriented metadata on top of BIDS. It offers schema-based validation for additional modalities, converters from common tabular and survey exports, reusable instrument templates, recipe-based scoring, participants.tsv generation, and manuscript-facing outputs such as methods boilerplate. The intended users are researchers, data stewards, and tool developers who want richer guarantees for behavioral metadata without giving up compatibility with established BIDS tooling.

# State of the field

PRISM complements rather than replaces established tools in the BIDS ecosystem. The official BIDS Validator and the broader BIDS standard are essential for core structural compliance, especially for imaging data [@gorgolewski2016bids]. BIDS `phenotype/` tables offer a useful flat representation of participant-level measurements, but they cannot retain all session, run, and acquisition-variant context for repeated instrument administrations. PRISM therefore uses subject-, session-, and run-resolved survey files as its native representation, while providing an optional, deliberately lossy `phenotype/` bridge for compatibility with existing BIDS workflows. PRISM adds checks for item-level metadata, recipe-based scoring rules, and project-facing conversion workflows that the BIDS Validator does not attempt to enforce. DataLad is highly effective for dataset versioning, provenance, distribution, and nested dataset management [@halchenko2021datalad], but it is not designed to define domain schemas for psychological instruments or to normalize questionnaire exports into BIDS-compatible tabular layouts.

Survey collection platforms such as LimeSurvey solve a different problem again: they help author and administer instruments, but they do not by themselves produce a reusable research dataset with BIDS-style naming, sidecars, schema validation, participants harmonization, and derivative generation. PRISM was therefore developed as a separate toolkit because the scholarly contribution lies in integrating these concerns: additive BIDS compatibility, psychology-oriented schemas, template libraries, conversion, scoring, and export in one reproducible workflow. Contributing isolated pieces of this functionality upstream would not by itself provide the end-to-end workflow needed by the target users.

# Software design

PRISM follows four design principles. First, it preserves BIDS compatibility by treating PRISM metadata as an additive layer. PRISM-specific files live alongside standard BIDS content, and `.bidsignore` support allows standard BIDS tools to ignore PRISM-only artifacts when necessary. This makes it possible to retain acquisition context in native survey files while keeping BIDS apps usable.

Second, PRISM treats metadata as an executable contract rather than a post-hoc annotation. Survey and biometrics templates separate instrument identity and item definitions from study-specific administration details. Versioned JSON schemas, a registry of instrument identifiers and citations, and declarative entity rules provide one machine-readable basis for conversion, filename construction, and validation. This supports multilingual templates, instrument variants, and version-aware scoring without requiring researchers to reconstruct those decisions from spreadsheet conventions.

Third, PRISM separates interactive assistance from portable enforcement. PRISM Studio guides authoring and conversion, whereas core schema, validation, and scoring operations are available through CLI workflows. The standalone `prism-validator` runs PRISM checks with optional BIDS validation, template-library validation, safe fix previews, and JSON, JUnit, SARIF, Markdown, or CSV reports. It is distributed as a lightweight Docker image and GitHub Action so that datasets can be checked before sharing and in continuous integration.

Fourth, PRISM makes derived data and sharing decisions auditable. Recipe outputs include derivative metadata and per-recipe provenance sidecars recording the recipe identifier and version, PRISM version, timestamp, and SHA-256 hashes of input files. DataLad support is optional, but records scoped changes when used. The sharing workflow validates selected content before export and can randomize participant identifiers, mask copyrighted question text, scrub sensitive MRI sidecar fields, or apply anatomical defacing to the export copy. It prepares reusable project templates, analysis-oriented exports, and repository packages such as Austrian NeuroCloud submissions; optional openMINDS metadata export supports semantic sharing.

![PRISM lifecycle: reusable instrument definitions become versioned templates, guide data collection and conversion into native PRISM/BIDS datasets, are enforced by interactive and automated validation, and produce provenance-bearing derivatives and privacy-controlled sharing packages.](prism_lifecycle.pdf)

![PRISM's native survey representation preserves participant, session, run, and acquisition-version context. The optional BIDS `phenotype/` bridge creates a compatible aggregate view, but intentionally cannot retain all of that acquisition detail.](prism_representations.pdf)

# FAIR-oriented dataset preparation

PRISM supports FAIR-oriented dataset preparation [@wilkinson2016fair], but does not make a dataset FAIR automatically. Findability is supported by BIDS-style names, versioned schemas, instrument identifiers, keywords, and DOI/citation fields. Standard JSON, TSV, and CSV formats, BIDS alignment, optional `phenotype/` and openMINDS exports, licensing metadata, and recipe provenance support accessibility, interoperability, and reuse. Actual access conditions, consent, licensing, and repository deposition remain the responsibility of the dataset owners.

# Research impact statement

PRISM has supported a research-data workflow for the Austrian NeuroCloud dataset *Creativity: a (white) matter of connectivity* [@koschutnig2026creativity]. Its public metadata record identifies PRISM Studio version 1.15.2 as the creation tool; the authors used PRISM to enrich the mixed-modality BIDS dataset with metadata and validate it before repository submission. This is documented author/developer use rather than evidence of independent adoption, and the dataset remains access-restricted under the Austrian NeuroCloud data-use agreement.

The public repository shows iterative development from September 2025 onward, tagged releases through version 1.17.0, automated continuous integration, and cross-platform release artifacts for macOS, Windows, and Linux. The repository also includes workshop materials, example datasets, and end-to-end documentation so that researchers can test the workflows locally rather than treating the software as an opaque web service.

The scientific value of PRISM is its attempt to make structured behavioral metadata operational in day-to-day research practice. The bundled template library, participants and NeuroBagel workflows, survey version handling, wide-to-long reshaping, LimeSurvey integration, and repository-facing exports reduce the amount of manual metadata reconciliation required to move from raw collection outputs to reusable datasets. This is particularly relevant for labs that already use BIDS for imaging data but still manage questionnaires and participant metadata in less standardized ways.

# Availability and reproducibility

PRISM is released under the GNU Affero General Public License v3.0 (AGPL-3.0) and developed at https://github.com/MRI-Lab-Graz/prism-studio. The release described here is version 1.17.0. Source installation is documented for macOS, Windows, and Linux through `setup.sh` and `setup.ps1`; entry points include `python prism-studio.py` for the web application and `prism-validator` for portable validation. The validator is also distributed as platform bundles, a Docker image, and a GitHub Action. The repository contains example datasets and workshop material under `examples/`, while automated checks are run in CI through `python tests/verify_repo.py` and pytest-based verification.

The final JOSS submission should cite the archival DOI for the exact release under review once the corresponding Zenodo snapshot has been created.

# AI usage disclosure

Claude Sonnet 5 and GitHub Copilot were used to assist with code drafting and refactoring, documentation editing, and manuscript drafting and editing. The GitHub Copilot model and version were not recorded. The author reviewed all AI-assisted outputs, accepts full responsibility for the manuscript and software, and retained control of the substantive software-design and scientific framing decisions.

# Acknowledgements

The author thanks the MRI-Lab Graz community for testing, issue reports, and feedback during PRISM's development. We are grateful to the BIDS community for the standards ecosystem on which PRISM builds, and to contributors who provided templates, bug reports, and workflow feedback. This work was conducted at the University of Graz, Austria.

# References
