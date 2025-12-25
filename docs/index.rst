.. PRISM documentation master file

PRISM Documentation
=============================

PRISM is an independent, BIDS-compatible dataset validation tool for psychological experiments. It validates standard BIDS datasets and additionally enforces PRISM extensions (e.g., stricter metadata requirements for certain files and support for modalities like surveys and biometrics) while remaining compatible with BIDS tools/apps.

**Key Features:**

- **Multi-modal validation**: survey, physio, eyetracking, biometrics, events, anat, func, dwi, fmap
- **Structured error codes**: PRISM001-PRISM9xx with severity levels
- **Auto-fix**: Automatically fix common issues (``--fix``)
- **Multiple output formats**: JSON, SARIF, JUnit XML, Markdown, CSV
- **Plugin system**: Custom validators for project-specific rules
- **REST API**: Integrate validation into workflows
- **Bilingual surveys**: German + English templates in single JSON files
- **Template Editor (Web UI)**: Value-only editing for Survey/Biometrics templates with schema guidance

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   WALKTHROUGH
   QUICK_START
   INSTALLATION
   USAGE
   DEMO_DATA
   PRISM_TOOLS
   SURVEY_DATA_IMPORT
   SURVEY_LIBRARY
   WINDOWS_SETUP

.. toctree::
   :maxdepth: 2
   :caption: Reference

   WEB_INTERFACE
   CLI_REFERENCE

.. toctree::
   :maxdepth: 2
   :caption: Understanding the Data

   SPECIFICATIONS
   specs/biometrics
   specs/events
   specs/survey
   SCHEMA_VERSIONING
   SCHEMA_VERSIONING_GUIDE
   FAIR_POLICY

.. toctree::
   :maxdepth: 2
   :caption: Troubleshooting

   ERROR_CODES

.. toctree::
   :maxdepth: 2
   :caption: Advanced / Developer

   LIMESURVEY_INTEGRATION
   WINDOWS_COMPATIBILITY
   WINDOWS_BUILD
   IMPLEMENTATION_SUMMARY
   RELEASE_GUIDE
   RELEASE_NOTES_v1.0.0
   CHANGELOG
   READTHEDOCS




Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
