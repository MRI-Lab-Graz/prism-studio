---
title: "PRISM: An independent, BIDS-compatible validator and metadata framework for psychological experiment datasets"
tags:
  - neuroscience
  - psychology
  - data standard
  - metadata
  - validation
  - BIDS
authors:
  - name: "Karl Koschutnig"
    orcid: "0000-0001-6234-0498"
    affiliation: 1
  - name: "TODO: Coauthor Name"
    orcid: "TODO: 0000-0000-0000-0000"
    affiliation: 1
affiliations:
  - name: "MRI-Lab Graz / Department of Psychology / Graz / Austria"
    index: 1
date: "2025-12-21"
bibliography: paper.bib
---

# Summary

Psychological and behavioral experiments frequently generate heterogeneous data (for example, surveys, behavioral task logs, and physical performance measures) that are challenging to standardize for sharing and reanalysis.
The Brain Imaging Data Structure (BIDS) has become a widely used standard for organizing neuroimaging datasets and associated behavioral and physiological recordings [@gorgolewski2016bids].
However, many psychology-specific data types and rich variable-level metadata requirements are not covered uniformly across studies.

PRISM is an open-source, independent toolkit that validates datasets and applies additional, versioned JSON Schemas for psychology-oriented modalities, with an emphasis on survey instruments and biometrics. PRISM is released under the GNU Affero General Public License v3.0 (AGPL-3.0).
PRISM is designed to be additive and BIDS-compatible: it does not replace BIDS, and it aims to keep standard BIDS tools and apps usable on PRISM datasets by avoiding destructive changes to core BIDS files and by supporting ignore rules where appropriate.

# Statement of need

Reproducible psychological research requires machine-readable descriptions of variables (units, response scales, levels), consistent naming conventions, and automated validation.
In practice, questionnaire exports and measurement codebooks are often stored as ad hoc spreadsheets, and metadata are distributed across lab-specific documentation.
This makes it difficult to compare studies, reuse analysis pipelines, or combine datasets.

PRISM addresses this need by providing:

- A dataset validator that checks filename conventions and required metadata sidecars.
- A schema manager for versioned JSON Schemas that extend BIDS-style metadata for psychology-focused modalities.
- CLI and web-based workflows for converting survey and biometrics codebooks into reusable library templates.
- Optional multi-language (i18n) metadata support for variable descriptions and instrument documentation.

PRISM is intended for researchers and tool developers who want stronger, schema-based metadata guarantees for psychology datasets, while maintaining compatibility with established BIDS ecosystem tools.

# Functionality

PRISM provides:

- Validation of dataset structure and metadata sidecars.
- Library-driven conversion workflows for survey and biometrics templates.
- A web interface (PRISM Studio) to validate datasets and interact with metadata.
- Utilities to generate manuscript-ready method boilerplate text from library templates.

Documentation is available at https://prism-studio.readthedocs.io/en/latest/.

# Acknowledgements

TODO: Acknowledge contributors, labs, funding, and community feedback.

# References

TODO: Add references for BIDS and related work in paper.bib.
