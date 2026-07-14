.. PRISM Studio documentation master file

PRISM Studio Documentation
============================

.. raw:: html

   <div class="prism-hero">
     <img src="_static/prism_logo.png" alt="PRISM logo">
     <p class="prism-tagline">
       Turn raw psychology and neuroscience study data into clean, BIDS-compatible
       datasets &mdash; without your data ever leaving your own computer.
     </p>
     <div class="prism-pill-list">
       <span class="prism-pill">BIDS-compatible</span>
       <span class="prism-pill">Full DataLad support</span>
       <span class="prism-pill">Version-aware surveys</span>
       <span class="prism-pill">Privacy-safe export</span>
       <span class="prism-pill">Local-first</span>
     </div>
     <a href="INSTALLATION.html" class="prism-cta">Get Started</a>
     <a href="studio/index.html" class="prism-cta prism-cta--secondary">Explore the Studio Guide</a>
   </div>

   <img src="_static/screenshots/prism-studio-home.png" alt="PRISM Studio Home screen" class="prism-screenshot">

A concrete before and after
============================

One common workflow: take a raw questionnaire spreadsheet, map participants, attach
metadata, run scoring recipes, and export a clean project for analysis.

.. raw:: html

   <div class="prism-proof-grid">
     <div class="prism-proof-panel">
       <div class="prism-proof-label">Before</div>
       <h4>Raw study files</h4>
       <ul>
         <li>One spreadsheet with mixed survey items, coded demographics, and ad hoc participant IDs</li>
         <li>No reusable metadata, no scoring logic, and no clear BIDS-ready structure</li>
         <li>Manual cleanup repeated in spreadsheets before every export or analysis pass</li>
       </ul>
     </div>
     <div class="prism-proof-arrow">&rarr;</div>
     <div class="prism-proof-panel">
       <div class="prism-proof-label">After</div>
       <h4>One analysis-ready PRISM project</h4>
       <ul>
         <li>Participant mappings standardized once, with cleaner IDs and ontology-friendly metadata</li>
         <li>Survey sidecars, scoring recipes, and validation feedback stored inside the project</li>
         <li>BIDS-compatible structure plus export targets such as SPSS, TSV, CSV, labels, and codebooks</li>
       </ul>
     </div>
   </div>

This is the core promise of PRISM Studio: less spreadsheet surgery, more
reproducible research data.

Why researchers use PRISM Studio
==================================

.. raw:: html

   <div class="prism-highlight-grid">
     <div>
       <h4>Convert messy source data</h4>
       <p>Import Excel, CSV, TSV, and LimeSurvey data into a structured PRISM dataset without hand-building folders or filenames.</p>
     </div>
     <div>
       <h4>Score questionnaires automatically</h4>
       <p>Build scoring recipes for surveys and compute derived scores without maintaining fragile spreadsheet formulas.</p>
     </div>
     <div>
       <h4>Privacy-safe export for analysis</h4>
       <p>Generate analysis-ready exports such as SPSS, CSV, TSV, labels, and codebooks with anonymization and MRI metadata/privacy safeguards.</p>
     </div>
     <div>
       <h4>Stay compatible with BIDS apps</h4>
       <p>PRISM adds surveys and other study metadata without giving up standard BIDS validators and downstream tools.</p>
     </div>
     <div>
       <h4>Handle multi-version survey studies</h4>
       <p>Use version-aware and run-aware survey workflows so evolving instruments remain conversion-ready and traceable across sessions.</p>
     </div>
     <div>
       <h4>Full DataLad provenance support</h4>
       <p>Initialize tracked projects, save snapshots, and record DataLad-backed mutation runs for critical dataset updates.</p>
     </div>
     <div>
       <h4>Rename and de-identify subjects in bulk</h4>
       <p>Rewrite subject or BIDS entity IDs across an entire dataset in one batch, with DataLad-aware per-subject commits and collision checks.</p>
     </div>
     <div>
       <h4>Sync to a remote DataLad server</h4>
       <p>Push a tracked project to a remote RIA store with one click, verify every file transferred intact, and disconnect safely.</p>
     </div>
   </div>

.. important::
   PRISM is an add-on to BIDS, not a replacement. PRISM Studio datasets should
   still work with BIDS apps such as fMRIPrep and MRIQC.

.. important::
   Source installation requires Python 3.10 or newer.

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Installation

   INSTALLATION

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Quick Start

   QUICK_START

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Studio Guide

   studio/index

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: CLI

   CLI_REFERENCE
   CLI_WORKFLOWS

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Tutorial

   WORKSHOP
   EXAMPLES

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Concepts

   WHAT_IS_PRISM
   PROJECT_OVERVIEW
   SPECIFICATIONS

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Data Reference

   RECIPES
   ERROR_CODES
   TEMPLATES
   SCHEMA_VERSIONING

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Integrations

   DATALAD
   LIMESURVEY_INTEGRATION

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Schema Specifications

   specs/survey
   specs/biometrics
   specs/events
   specs/environment

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
