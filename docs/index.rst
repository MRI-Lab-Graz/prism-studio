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

- **Installation**: get PRISM Studio running, prebuilt or from source
- **Quick Start**: shortest path from install to a first validated dataset
- **Studio Guide**: every Studio screen explained in detail
- **CLI**: terminal/automation workflows
- **Tutorial**: a guided walkthrough with demo data
- **Reference**: concepts, schemas, error codes, and detailed data specifications

.. toctree::
   :maxdepth: 2
   :caption: Installation

   INSTALLATION

.. toctree::
   :maxdepth: 2
   :caption: Quick Start

   QUICK_START

.. toctree::
   :maxdepth: 2
   :caption: Studio Guide

   studio/index

.. toctree::
   :maxdepth: 2
   :caption: CLI

   CLI_REFERENCE
   CLI_WORKFLOWS

.. toctree::
   :maxdepth: 2
   :caption: Tutorial

   WORKSHOP
   EXAMPLES

.. toctree::
   :maxdepth: 2
   :caption: Reference

   WHAT_IS_PRISM
   PROJECT_OVERVIEW
   SPECIFICATIONS
   RECIPES
   ERROR_CODES
   QUICK_REFERENCE_BIDS
   TEMPLATE_VALIDATION
   TEMPLATES
   SURVEY_VERSION_PLAN
   SCHEMA_VERSIONING
   DATALAD
   FAIR_POLICY
   LIMESURVEY_INTEGRATION

.. toctree::
   :maxdepth: 2
   :caption: Schema Specifications

   specs/survey
   specs/biometrics
   specs/events
   specs/environment

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
