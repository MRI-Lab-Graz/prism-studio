.. PRISM documentation master file

PRISM Documentation
=============================

**PRISM** (Psychological Research Information System & Management) is a validation and metadata framework for psychological experiment datasets. It extends the BIDS standard to support modalities common in psychological research—like surveys, biometrics, and eyetracking—while ensuring your data remains **fully compatible with existing BIDS tools**.

.. important::
   PRISM is an **add-on to BIDS**, not a replacement. Your PRISM-validated datasets will still work with fMRIPrep, MRIQC, and all other BIDS apps.

**Key Features:**

- 🔍 **Validation** with structured error codes and auto-fix
- 📝 **Self-documenting data** with complete metadata in JSON sidecars
- 📊 **Questionnaire scoring** with recipes and SPSS export
- 🌐 **Web interface** (PRISM Studio) for easy project management
- ✨ **100+ survey templates** in the official library

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   WHAT_IS_PRISM
   INSTALLATION
   QUICK_START
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
   :caption: Reference

   CLI_REFERENCE
   SPECIFICATIONS
   RECIPES
   SURVEY_LIBRARY
   ERROR_CODES
   PARTICIPANTS_MAPPING

.. toctree::
   :maxdepth: 2
   :caption: Schema Specifications

   specs/survey
   specs/biometrics
   specs/events

.. toctree::
   :maxdepth: 2
   :caption: Advanced Topics

   LIMESURVEY_INTEGRATION
   SCHEMA_VERSIONING
   WINDOWS_SETUP
   WINDOWS_BUILD
   FAIR_POLICY

.. toctree::
   :maxdepth: 1
   :caption: Development

   CHANGELOG
   RELEASE_GUIDE


Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
