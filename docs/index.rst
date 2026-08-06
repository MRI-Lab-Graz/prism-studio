.. PRISM Studio documentation master file

PRISM Studio Documentation
============================

.. raw:: html

   <div class="prism-hero-shell">
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
       <a href="INSTALLATION.html" class="prism-cta">Install PRISM Studio</a>
       <a href="TUTORIAL_BEGINNER.html" class="prism-cta prism-cta--secondary">Start the Tutorial</a>
     </div>
   </div>

A concrete before and after
============================

One common workflow: take a raw questionnaire spreadsheet, map participants, attach
metadata, run scoring recipes, and export a clean project for analysis.

.. raw:: html

   <div class="prism-proof-grid">
     <div class="prism-proof-panel">
       <span class="prism-proof-label prism-proof-label--before">Before</span>
       <h4>Raw study files</h4>
       <ul class="prism-proof-list">
         <li><span class="prism-proof-icon prism-proof-icon--before">!</span><span>One spreadsheet with mixed survey items, coded demographics, and ad hoc participant IDs</span></li>
         <li><span class="prism-proof-icon prism-proof-icon--before">!</span><span>No reusable metadata, no scoring logic, and no clear BIDS-ready structure</span></li>
         <li><span class="prism-proof-icon prism-proof-icon--before">!</span><span>Manual cleanup repeated in spreadsheets before every export or analysis pass</span></li>
       </ul>
     </div>
     <div class="prism-proof-step">
       <span class="prism-proof-step-badge">&rarr;</span>
       <span class="prism-proof-step-text">Convert, score, validate, export</span>
     </div>
     <div class="prism-proof-panel">
       <span class="prism-proof-label prism-proof-label--after">After</span>
       <h4>One analysis-ready PRISM project</h4>
       <ul class="prism-proof-list">
         <li><span class="prism-proof-icon prism-proof-icon--after">&check;</span><span>Participant mappings standardized once, with cleaner IDs and ontology-friendly metadata</span></li>
         <li><span class="prism-proof-icon prism-proof-icon--after">&check;</span><span>Survey sidecars, scoring recipes, and validation feedback stored inside the project</span></li>
         <li><span class="prism-proof-icon prism-proof-icon--after">&check;</span><span>BIDS-compatible structure plus export targets such as SPSS, TSV, CSV, labels, and codebooks</span></li>
       </ul>
     </div>
   </div>

   <p class="prism-proof-note">This is the core promise of PRISM Studio: less spreadsheet surgery, more
   reproducible research data.</p>

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

One structure for multimodal studies
======================================

.. raw:: html

   <div class="prism-structure-grid">
   <pre class="prism-structure-tree"><code>dataset/
   ├── dataset_description.json
   ├── participants.tsv
   ├── sub-01/
   │   └── ses-001/
   │       ├── survey/
   │       ├── biometrics/
   │       └── environment/
   └── sub-02/
       └── ...</code></pre>
   <div class="prism-structure-copy">
   <h4>What PRISM adds to a BIDS-style project</h4>
   <p>Keep a familiar BIDS layout while adding the extra structure needed for
   surveys, participant-level assessments, and richer behavioral studies.</p>
   <ul class="prism-structure-list">
     <li><span class="prism-structure-check">&check;</span><span><code>survey/</code> &mdash; Questionnaires, scoring inputs, and behavioral responses</span></li>
     <li><span class="prism-structure-check">&check;</span><span><code>biometrics/</code> &mdash; Fitness, strength, balance, and other assessments</span></li>
     <li><span class="prism-structure-check">&check;</span><span><code>environment/</code> &mdash; Privacy-safe contextual enrichment data</span></li>
     <li><span class="prism-structure-check">&check;</span><span><code>eyetracking/</code> &mdash; Eye tracking workflows in the same study layout</span></li>
     <li><span class="prism-structure-check">&check;</span><span><code>physiological/</code> &mdash; Standard BIDS physio alongside PRISM extensions</span></li>
   </ul>
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
   :caption: Concepts

   CONCEPTS
   WHAT_IS_PRISM
   PROJECT_OVERVIEW
   SPECIFICATIONS

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Tutorial

   TUTORIAL_BEGINNER
   TUTORIAL_BEGINNER_1_NEW_PROJECT
   TUTORIAL_BEGINNER_2_PARTICIPANTS
   TUTORIAL_BEGINNER_3_SURVEY_IMPORT
   TUTORIAL_BEGINNER_4_RECIPE
   TUTORIAL_BEGINNER_5_VALIDATOR
   TUTORIAL_BEGINNER_6_EXISTING_BIDS

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Studio Guide

   studio/index

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: More Resources

   MORE_RESOURCES
   WORKSHOP
   EXAMPLES
   EXCEL_TEMPLATE_BASICS
   EXCEL_TEMPLATE_ADVANCED

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Data Reference

   DATA_REFERENCE
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

   SCHEMA_SPECIFICATIONS
   specs/survey
   specs/biometrics
   specs/events
   specs/environment
   specs/entities

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Installation

   INSTALLATION

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: CLI

   CLI_REFERENCE
   CLI_WORKFLOWS

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
