.. PRISM Studio documentation master file

PRISM Studio Documentation
=============================

**PRISM Studio** is the software implementation of the **PRISM** (Psychological Research Information System Model) framework for psychological experiment datasets. It extends BIDS workflows for modalities common in psychological research — surveys, biometrics, eyetracking, and environment — while ensuring your data remains **fully compatible with existing BIDS tools**.

.. important::
   PRISM (the model) is an **add-on to BIDS**, not a replacement. PRISM Studio datasets still work with fMRIPrep, MRIQC, and other BIDS apps.

**Key Features:**

- 🔍 **Validation** with structured error codes and auto-fix
- 📝 **Self-documenting data** with complete metadata in JSON sidecars
- 📊 **Questionnaire scoring in PRISM Studio** via recipes
- 📤 **Export workflows in PRISM Studio** (e.g., SPSS/integration formats)
- 🌐 **Web interface** (PRISM Studio) for easy project management
- ✨ **100+ survey templates** in the official library

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   WHAT_IS_PRISM
   INSTALLATION
   QUICK_START

.. toctree::
   :maxdepth: 2
   :caption: Examples

   EXAMPLES
   WORKSHOP

.. toctree::
   :maxdepth: 2
   :caption: PRISM Studio Guide

   STUDIO_OVERVIEW
   PROJECTS
   CONVERTER
   VALIDATOR
   TOOLS
   WEB_INTERFACE

.. toctree::
   :maxdepth: 2
   :caption: CLI Workflows

   CLI_WORKFLOWS
   CLI_REFERENCE

.. toctree::
   :maxdepth: 2
   :caption: Reference

   SPECIFICATIONS
   RECIPES
   ERROR_CODES
   PARTICIPANTS_MAPPING
   QUICK_REFERENCE_BIDS
   TEMPLATE_VALIDATION

.. toctree::
   :maxdepth: 2
   :caption: Schema Specifications

   specs/survey
   specs/biometrics
   specs/events
   specs/environment

.. toctree::
   :maxdepth: 2
   :caption: Survey Design

   SURVEY_VERSION_PLAN
   SURVEY_LIBRARY
   LIMESURVEY_INTEGRATION

.. toctree::
   :maxdepth: 2
   :caption: Advanced Topics

   SCHEMA_VERSIONING
   FAIR_POLICY

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
