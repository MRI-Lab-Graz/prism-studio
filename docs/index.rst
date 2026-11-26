.. PRISM Studio documentation master file

PRISM Studio Documentation
============================

.. raw:: html

   <div class="prism-hero-shell">
     <div class="prism-hero">
       <img src="_static/prism_logo.png" alt="PRISM logo">
       <h2 class="prism-headline">Raw study data in. A BIDS-compatible project out.</h2>
       <p class="prism-tagline">
         PRISM Studio converts, scores, validates and exports psychology and neuroscience data
         &mdash; on your own machine. Participant data is never uploaded or sent to a remote service.
       </p>
       <div class="prism-cta-row">
         <a href="INSTALLATION.html" class="prism-cta">Install PRISM Studio</a>
         <a href="TUTORIAL_BEGINNER.html" class="prism-cta prism-cta--secondary">Start the Tutorial</a>
         <a href="MODALITY_WORKFLOW.html" class="prism-cta prism-cta--secondary">Propose a modality</a>
       </div>
       <img class="prism-hero-shot" src="_static/screenshots/landing-validator.png"
            alt="PRISM Studio validation results: dataset is valid, 17 of 17 files valid, 11 subjects">
       <div class="prism-pill-list">
         <span class="prism-pill">BIDS-compatible</span>
         <span class="prism-pill">Full DataLad support</span>
         <span class="prism-pill">Version-aware surveys</span>
         <span class="prism-pill">Privacy-safe export</span>
         <span class="prism-pill">Local-first</span>
         <span class="prism-pill">Community modalities</span>
       </div>
     </div>
   </div>

Ontology-ready
===============

Every PRISM ID is a stable address. It resolves to the definition of that
instrument, item or term, and it can carry links to external vocabularies such as
SNOMED CT or LOINC. Those links live in a separate, checked ``mappings/`` layer;
PRISM never changes your data to carry meaning.

.. raw:: html

   <div class="prism-ontology">
     <div class="prism-ontology-step">
       <span class="prism-ontology-label">1 &middot; An ID</span>
       <code>prism:dass21.dass2101</code>
       <p>One item of one instrument. The ID never changes.</p>
     </div>
     <span class="prism-ontology-arrow">&rarr;</span>
     <div class="prism-ontology-step">
       <span class="prism-ontology-label">2 &middot; Its address</span>
       <code>w3id.org/prism-specification/terms/survey/dass21.dass2101</code>
       <p>Resolves to the instrument&rsquo;s definition.</p>
     </div>
     <span class="prism-ontology-arrow">&rarr;</span>
     <div class="prism-ontology-step">
       <span class="prism-ontology-label">3 &middot; Its links</span>
       <code>mappings/survey/dass21.json</code>
       <p>The item links to the SNOMED CT score of its subscale.</p>
     </div>
   </div>
   <p>
     <a href="ONTOLOGY_READY.html" class="prism-cta">How it works</a>
     <a href="specs/mappings.html" class="prism-cta prism-cta--secondary">Mappings specification</a>
   </p>

Why researchers use PRISM Studio
==================================

.. raw:: html

   <div class="prism-highlight-grid">
     <div>
       <h4>Convert &amp; score</h4>
       <p>Import Excel, CSV, TSV and LimeSurvey data into a structured dataset, then compute questionnaire scores with recipes instead of fragile spreadsheet formulas. Version-aware and run-aware surveys stay traceable across sessions.</p>
     </div>
     <div>
       <h4>Privacy-safe export</h4>
       <p>Export SPSS, CSV, TSV, labels and codebooks with anonymization and MRI metadata safeguards. Rename and de-identify subjects in bulk, with collision checks.</p>
     </div>
     <div>
       <h4>BIDS and DataLad</h4>
       <p>PRISM adds surveys and other study metadata without giving up standard BIDS validators and apps. Full DataLad provenance, and one-click sync to a remote store that verifies every file.</p>
     </div>
     <div>
       <h4>Open modalities and ontologies</h4>
       <p>Missing a data type? Propose it. Link your terms to external vocabularies in a separate, checked layer, and share them with the community.</p>
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
     <li><span class="prism-structure-check">&check;</span><span><code>environment/</code> &mdash; Environmental variables linked to a session (weather, air quality, pollen, time windows)</span></li>
     <li><span class="prism-structure-check">&check;</span><span><code>physio/</code> &mdash; Task-free physiological recordings (task-bound physio lives in <code>beh/</code>, <code>func/</code>, <code>eeg/</code>)</span></li>
     <li><span class="prism-structure-check">&check;</span><span><code>your-modality/</code> &mdash; Missing a data type? <a href="MODALITY_WORKFLOW.html">Propose it</a></span></li>
   </ul>
   </div>
   </div>

Missing a data type? Propose it.
=================================

PRISM is open and dynamic. If your study measures something PRISM does not
describe yet — blood samples, skin temperature, a new instrument —
you do not need to be a maintainer: you describe it, and it can ship in the
next PRISM release.

.. raw:: html

   <div class="prism-highlight-grid">
     <div>
       <h4>1. Describe it</h4>
       <p>Fill in a short workbook: the name, the filename ending (suffix), and a few example columns with units.</p>
     </div>
     <div>
       <h4>2. Attach a sample</h4>
       <p>Add a small synthetic data file in your format. No real participant data, ever.</p>
     </div>
     <div>
       <h4>3. A bot checks it</h4>
       <p>Names, columns and sample are checked automatically; if something is off, you get a comment saying what to fix.</p>
     </div>
     <div>
       <h4>4. It ships</h4>
       <p>A maintainer registers it, and your modality is part of the next release, with documentation.</p>
     </div>
   </div>
   <p>
     <a href="MODALITY_WORKFLOW.html" class="prism-cta">Propose a modality</a>
     <a href="MODALITY_PROPOSALS.html" class="prism-cta prism-cta--secondary">What you need</a>
   </p>

.. important::
   PRISM is an add-on to BIDS, not a replacement. PRISM Studio datasets should
   still work with BIDS apps such as fMRIPrep and MRIQC.

.. important::
   Source installation requires Python 3.10 or newer.

Citing PRISM
============

If PRISM is useful in your work, please cite it. Every tagged release is
archived on Zenodo with a citable DOI:

.. image:: https://zenodo.org/badge/DOI/10.5281/zenodo.22809100.svg
   :target: https://doi.org/10.5281/zenodo.22809100
   :alt: DOI

See `CITATION.cff <https://github.com/MRI-Lab-Graz/prism-studio/blob/main/CITATION.cff>`_
in the repository root for the full citation, including all authors.

.. raw:: html

   <div class="prism-footer-strip">
     <span>Open source &middot; AGPL-3.0</span>
     <span>Local-first: nothing is uploaded</span>
     <span>Cite: <a href="https://doi.org/10.5281/zenodo.22809100">doi:10.5281/zenodo.22809100</a></span>
     <span><a href="https://github.com/MRI-Lab-Graz/prism-studio">GitHub</a></span>
   </div>

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Concepts

   CONCEPTS
   INTRODUCTION
   WHAT_IS_PRISM
   PROJECT_OVERVIEW
   SPECIFICATIONS

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Tutorial

   TUTORIAL_BEGINNER
   TUTORIAL_FILE_MANAGEMENT
   TUTORIAL_SURVEY

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Studio Guide

   studio/index

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Propose a Modality

   MODALITY_WORKFLOW
   MODALITY_PROPOSALS

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: More Resources

   MORE_RESOURCES
   WORKSHOP
   EXAMPLES
   EXCEL_TEMPLATE_BASICS
   EXCEL_TEMPLATE_ADVANCED
   AI_USAGE

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Data Reference

   DATA_REFERENCE
   RECIPES
   ERROR_CODES
   TEMPLATES
   SCHEMA_VERSIONING
   ONTOLOGY_READY
   CODE_MAPS

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
   specs/biosample
   specs/events
   specs/environment
   specs/physio
   specs/mappings
   specs/instrument-ids
   specs/project
   specs/dataset_description
   specs/entities

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Installation

   INSTALLATION
   INSTALLATION_SECURITY

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
