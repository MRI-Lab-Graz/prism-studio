.. PRISM Studio documentation master file

PRISM Studio Documentation
=============================

**PRISM Studio** is the software implementation of the **PRISM** (Psychological Research Information System Model) framework for psychological experiment datasets. It extends BIDS workflows for modalities common in psychological research-like surveys, biometrics, eyetracking, and environment-while ensuring your data remains **fully compatible with existing BIDS tools**.

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
   SURVEY_LIBRARY
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
   :caption: Advanced Topics

   LIMESURVEY_INTEGRATION
   PAVLOVIA_EXPORT
   ANC_EXPORT
   EYETRACKING_TSV_NORMALIZATION
   BIDS_COMPLIANCE_IMPLEMENTATION
   BIDS_AUTO_MAPPING_COMPLETE
   SCHEMA_VERSIONING
   WINDOWS_SETUP
   WINDOWS_BUILD
   GITHUB_SIGNING
   FAIR_POLICY

.. toctree::
   :maxdepth: 1
   :caption: Development

   CHANGELOG
   RELEASE_GUIDE
   WINDOWS_TESTING
   WINDOWS_TEST_QUICKREF
   WINDOWS_TEST_SUMMARY
   WINDOWS_VM_BUILD_TESTING
   COMPLETE_WINDOWS_SUMMARY


Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
