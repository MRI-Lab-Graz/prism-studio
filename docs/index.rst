.. PRISM Studio documentation master file

PRISM Studio Documentation
==========================

**PRISM Studio** is the software implementation of the **PRISM**
(Psychological Research Information System Model) for psychological research
datasets. It extends BIDS for workflows that are common in psychology, such as
surveys, biometrics, environment metadata, and scoring, while keeping datasets
compatible with standard BIDS tooling.

.. important::
   PRISM is an add-on to BIDS, not a replacement. PRISM Studio datasets should
   still work with BIDS apps such as fMRIPrep and MRIQC.

.. important::
   Source installation requires Python 3.10 or newer.

Start here if you want to understand the project before diving into a specific
workflow:

- **Concepts**: what PRISM is, how PRISM Studio fits, and how projects are organized
- **Getting started**: install the tool, create a first project, and validate a first dataset
- **Guided workflows**: projects, conversion, validation, templates, scoring, and export
- **Reference**: schemas, error codes, CLI commands, and detailed data specifications

.. toctree::
   :maxdepth: 2
   :caption: Fundamentals

   WHAT_IS_PRISM
   PROJECT_OVERVIEW
   SPECIFICATIONS

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   INSTALLATION
   QUICK_START
   STUDIO_OVERVIEW

.. toctree::
   :maxdepth: 2
   :caption: Studio Guide (New)

   studio/index

.. toctree::
   :maxdepth: 2
   :caption: User Workflows (Legacy — being replaced by Studio Guide)

   PROJECTS
   CONVERTER
   SURVEY_IMPORT
   VALIDATOR
   TOOLS
   TEMPLATE_EDITOR
   RECIPE_BUILDER
   ANALYSIS_OUTPUT
   WEB_INTERFACE

.. toctree::
   :maxdepth: 2
   :caption: Examples

   EXAMPLES
   WORKSHOP

.. toctree::
   :maxdepth: 2
   :caption: CLI and Automation

   CLI_WORKFLOWS
   CLI_REFERENCE

.. toctree::
   :maxdepth: 2
   :caption: Reference

   RECIPES
   ERROR_CODES
   PARTICIPANTS_MAPPING
   QUICK_REFERENCE_BIDS
   TEMPLATE_VALIDATION
   ANC_EXPORT

.. toctree::
   :maxdepth: 2
   :caption: Schema Specifications

   specs/survey
   specs/biometrics
   specs/events
   specs/environment

.. toctree::
   :maxdepth: 2
   :caption: Library and Survey Design

   TEMPLATES
   SURVEY_VERSION_PLAN
   SURVEY_LIBRARY
   LIMESURVEY_INTEGRATION

.. toctree::
   :maxdepth: 2
   :caption: Integrations and Advanced

   DATALAD
   SCHEMA_VERSIONING
   FAIR_POLICY

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
