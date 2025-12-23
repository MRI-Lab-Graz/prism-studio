Prism Tools (CLI)
=================

PRISM includes a command-line utility `prism_tools.py` for advanced data conversion tasks, particularly for physiological data ingestion.

Requirements
------------

`prism_tools.py` enforces the same strict environment rule as the validator: it must be run from the repository's local virtual environment at ``./.venv``.

Install dependencies via the setup script (recommended):

.. code-block:: bash

  # macOS / Linux
  bash scripts/setup/setup.sh
  source .venv/bin/activate

On Windows:

.. code-block:: bat

  scripts\setup\setup-windows.bat
  .venv\Scripts\activate

Physiological Data Conversion
-----------------------------

This tool converts raw Varioport data (`.raw`) into BIDS-compliant EDF+ files (`.edf`) with accompanying JSON sidecars.

1. Prepare your ``sourcedata``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Before running the conversion, you must organize your raw files into a BIDS-compliant ``sourcedata`` directory structure. This step is crucial as it allows the tool to automatically infer the Subject ID and Session ID from the file path or filename.

**Recommended Structure:**

.. code-block:: text

    sourcedata/
      sub-1292001/
        ses-1/
          physio/
            sub-1292001_ses-1_physio.raw   <-- Renamed from VPDATA.RAW
      sub-1292002/
        ses-1/
          physio/
            sub-1292002_ses-1_physio.raw

2. Run the Conversion Command
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the ``convert physio`` command to process the data.

.. code-block:: bash

    ./prism_tools.py convert physio \
      --input ./sourcedata \
      --output ./rawdata \
      --task rest \
      --suffix ecg \
      --sampling-rate 256

**Arguments:**

*   ``--input``: Path to your organized ``sourcedata`` folder.
*   ``--output``: Destination path where the BIDS-compliant ``rawdata`` will be generated.
*   ``--task``: The task name to assign to the output files (e.g., ``rest``, ``auditory``).
*   ``--suffix``: The filename suffix to use (e.g., ``ecg``, ``physio``).
*   ``--sampling-rate``: (Optional) Force a specific sampling rate (in Hz) if the raw file header contains incorrect information (e.g., Varioport files often report 150Hz when the effective rate is 256Hz).

Demo Dataset
------------

You can create a fresh demo dataset to test the validator or experiment with the structure.

.. code-block:: bash

    ./prism_tools.py demo create --output my_demo_dataset

Survey Library Management
-------------------------

Tools for managing the JSON survey library used by the validator.

Import from Excel
~~~~~~~~~~~~~~~~~

You can import survey definitions from an Excel file into the PRISM library format.

.. code-block:: bash

    ./prism_tools.py survey import-excel --excel my_definitions.xlsx --output library/survey

**Templates:**
We provide Excel templates with a **Help** sheet explaining all supported columns:

* `Survey Template <https://github.com/MRI-Lab-Graz/prism-studio/blob/main/docs/examples/survey_import_template.xlsx>`_
* `Biometrics Template <https://github.com/MRI-Lab-Graz/prism-studio/blob/main/docs/examples/biometrics_import_template.xlsx>`_

Convert Survey Data (Wide Table)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert a “wide” survey export (one row per participant and one column per item, e.g., ``ADS01``) into a PRISM/BIDS-like dataset.

The converter:

- Reads a tabular input file (``.xlsx`` or LimeSurvey ``.lsa``)
- Matches column headers against item IDs in your survey templates (``survey-*.json``)
- Writes a dataset with ``participants.tsv`` and per-subject TSVs under ``sub-*/ses-*/survey/``
- Copies inherited sidecars to ``surveys/survey-<task>_beh.json`` for BIDS inheritance

Minimum expected columns in the input table:

- ``participant_id`` (or specify ``--id-column``)
- Optional session column: ``ses`` / ``session`` / ``visit`` (or specify ``--session-column``). If missing, all rows are written to ``ses-1``.

Example

.. code-block:: bash

  ./prism_tools.py survey convert \
    --input responses.xlsx \
    --library library/survey \
    --output my_survey_dataset \
    --survey ads

Useful options

- ``--dry-run``: print a mapping report but do not write files
- ``--unknown {error,warn,ignore}``: control how unmapped columns are handled
- ``--sheet``: choose the Excel sheet by index/name
- ``--alias``: optional TSV/whitespace mapping file to map changing item IDs onto stable canonical IDs

After conversion, validate the output with:

.. code-block:: bash

  python prism.py my_survey_dataset

Import from Excel
~~~~~~~~~~~~~~~~~

Converts a data dictionary (Excel) into PRISM-compliant JSON sidecars.

Accepted columns (header-friendly, case-insensitive):
- `item_id` (aliases: id, code, variable, name)
- `question` (aliases: item, description, text)
- `scale` (aliases: levels, options, answers)
- `group` (aliases: survey, section, domain, category) – optional override to force items into the same survey (e.g., `demographics`) even without a shared prefix. Set to `disable`/`skip`/`omit`/`ignore` to drop an item entirely.
- `alias_of` (aliases: alias, canonical, duplicate_of, merge_into) – optional; keeps the current `item_id` as the key but annotates it as an alias of the given canonical ID.
- `session` (aliases: visit, wave, timepoint) – optional per-item session hint (e.g., `ses-2`, `t2`, `visit2`). Useful when the same item code appears in multiple timepoints; the value is normalized to `ses-<n>`.
- `run` (aliases: repeat) – optional per-item run hint (e.g., `run-2`).
If no header row is present, positional columns map in order: item_id, question, scale, group, alias_of, session, run.

.. code-block:: bash

    ./prism_tools.py survey import-excel \
      --excel metadata.xlsx \
      --output survey_library

To use a unified library layout, pass ``--library-root`` to write into ``<library-root>/survey``:

.. code-block:: bash

    ./prism_tools.py survey import-excel \
      --excel metadata.xlsx \
      --library-root library

Validate Library
~~~~~~~~~~~~~~~~

Checks the survey library for duplicate variable names across different instruments.

.. code-block:: bash

    ./prism_tools.py survey validate --library survey_library

Bilingual Survey Templates (i18n)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

PRISM supports bilingual survey templates that contain both German and English in a single JSON file. At "compile time," you select the language to produce a clean, single-language output.

**Template Format:**

Survey templates can store multiple languages in one JSON file. The common convention is:

- ``Study.OriginalName`` / ``Study.Version`` / ``Study.Description`` / ``Study.Instructions`` as language maps like ``{"de": "…", "en": "…"}``
- item ``Description`` as a language map
- item ``Levels`` values as language maps, e.g. ``{"0": {"de": "Nie", "en": "Never"}, ...}``

At build/convert time, you select a single language to produce a schema-valid sidecar.

**Migrate Existing Survey to i18n Format:**

.. code-block:: bash

    ./prism_tools.py survey i18n-migrate \
      --input library/survey/survey-ads.json \
      --output library/survey/survey-ads.json

This helps migrate older survey JSONs into PRISM's current i18n-capable template format.

**Build Compiled Survey (Choose Language):**

.. code-block:: bash

    # Build German version
    ./prism_tools.py survey i18n-build \
      library/survey/survey-phq9.json \
      --lang de \
      --output survey-phq9-de.json

    # Build English version
    ./prism_tools.py survey i18n-build \
      library/survey/survey-phq9.json \
      --lang en \
      --output survey-phq9-en.json

If no ``--output`` is specified, the result is written to stdout (suitable for piping).

**Available Bilingual Surveys:**

- ``survey-phq9.json`` - Patient Health Questionnaire (PHQ-9)
- ``survey-gad7.json`` - Generalized Anxiety Disorder (GAD-7)
- ``survey-pss10.json`` - Perceived Stress Scale (PSS-10)
- ``survey-who5.json`` - WHO Well-Being Index (WHO-5)
- ``survey-rosenberg.json`` - Rosenberg Self-Esteem Scale

Import from LimeSurvey
~~~~~~~~~~~~~~~~~~~~~~

Converts a LimeSurvey structure file (`.lss` or `.lsa`) into a PRISM JSON sidecar.

.. code-block:: bash

    ./prism_tools.py survey import-limesurvey \
      --input survey_archive.lsa \
      --output survey-mysurvey.json

Batch import with session mapping (e.g., t1/t2/t3 -> ses-1/ses-2/ses-3) and subject inference from the path:

.. code-block:: bash

    ./prism_tools.py survey import-limesurvey-batch \
      --input-dir /Volumes/Evo/data/AF134/sourcedata \
      --output-dir /Volumes/Evo/data/AF134/survey_json \
      --session-map t1:ses-1,t2:ses-2,t3:ses-3

The batch command walks `input-dir` for `.lsa/.lss` files, looks for `sub-*` and session tokens (e.g., `t1`) in the path, and writes sidecars like `sub-<id>/ses-1/survey/sub-<id>_ses-1_task-<task>_survey.json` under `output-dir`.


Biometrics Library Management
-----------------------------

Tools for managing biometrics JSON templates/libraries (schema: ``schemas/stable/biometrics.schema.json``).

Import from Excel
~~~~~~~~~~~~~~~~~

Converts a biometrics *codebook* (Excel, **no data required**) into PRISM-compliant biometrics JSON sidecars.

Recommended Excel structure (header-friendly, case-insensitive):

- ``item_id`` (aliases: id, code, variable, name) – the TSV column name
- ``description`` (aliases: question, text, item)
- ``units`` (aliases: unit) – **required** by the biometrics schema
- ``datatype`` (optional; one of: string, integer, float)
- ``minvalue`` / ``maxvalue`` (optional)
- ``warnminvalue`` / ``warnmaxvalue`` (optional)
- ``allowedvalues`` (optional; comma/semicolon list or ``1=foo;2=bar``)
- ``group`` (aliases: test, instrument, category) – optional; creates one ``biometrics-<group>.json`` per group. If omitted, all rows go into ``biometrics-biometrics.json``. Special case: set ``group`` to ``participant`` to write those rows to ``participants.json`` instead.
- ``alias_of`` (optional)
- ``session`` (optional; normalized to ``ses-<n>``)
- ``run`` (optional; normalized to ``run-<n>``)

If provided, ``session``/``run`` are written to the metric entries as ``SessionHint``/``RunHint``.

Optional per-group metadata columns (can be repeated on any row; the first non-empty value per group is used to fill the JSON header):

- ``originalname`` (or ``test_name`` / ``testname``) -> ``Study.OriginalName``
- ``protocol`` -> ``Study.Protocol``
- ``instructions`` -> ``Study.Instructions``
- ``reference`` (or ``citation`` / ``doi``) -> ``Study.Reference``
- ``estimatedduration`` (or ``duration``) -> ``Study.EstimatedDuration``
- ``equipment`` -> ``Technical.Equipment``
- ``supervisor`` -> ``Technical.Supervisor`` (enum: investigator|physician|trainer|self)

Notes on scales / levels

- If you provide labeled values like ``0=selten;1=manchmal;2=...`` in ``allowedvalues`` (or in ``scaling``), the importer stores them as ``Levels`` (value->label mapping) **and** derives ``AllowedValues`` from the codes.
- For numeric ranges, you can write ``1-10`` in ``allowedvalues`` to expand to allowed integers 1..10 (kept small by design).

If no header row is present, positional columns map in order: item_id, description, units, datatype, minvalue, maxvalue, allowedvalues, group, alias_of, session, run.

Example:

.. code-block:: bash

    ./prism_tools.py biometrics import-excel \
      --excel test_dataset/Biometrics_variables.xlsx \
      --sheet biometrics_codebook \
      --output biometrics_library \
      --equipment "Functional Movement Screen – Y Balance Test Kit"

To use a unified library layout, pass ``--library-root`` to write into ``<library-root>/biometrics``:

.. code-block:: bash

    ./prism_tools.py biometrics import-excel \
      --excel test_dataset/Biometrics_variables.xlsx \
      --sheet biometrics_codebook \
      --library-root library


Dataset Helpers
---------------

Build a small PRISM-valid biometrics dataset from the biometrics codebook and dummy CSV. This is intended as a smoke test.

The builder uses the BIDS inheritance principle for biometrics sidecars: it writes one dataset-level sidecar per task (``task-<task>_biometrics.json`` in the dataset root) instead of duplicating JSON files per subject/session.

Dummy data formats

- **Long format (recommended):** columns ``participant_id``, ``session``, ``item_id``, ``value`` (optional ``group``; optional ``instance`` for trials/repeats). The builder will create one TSV per subject/session/task and (if ``instance`` is present) multiple rows per TSV.
- **Wide format (supported):** one row per participant (optional ``session`` column) and one column per ``item_id``.

.. code-block:: bash

    ./prism_tools.py dataset build-biometrics-smoketest \
      --codebook test_dataset/Biometrics_variables.xlsx \
      --sheet biometrics_codebook \
      --data test_dataset/Biometrics_dummy_data.csv \
      --library-root library \
      --output test_dataset/_tmp_prism_biometrics_dataset


Manuscript methods boilerplate (scientific text)
------------------------------------------------

Generate a manuscript-ready Methods section snippet (Markdown) describing the instruments and measures defined in your libraries.
The text is derived from ``Study.OriginalName``, ``Study.Description``, and (for biometrics) technical metadata such as ``Technical.Equipment``.

.. code-block:: bash

    # English methods snippet
    ./prism_tools.py library generate-methods-text \
      --output tmp/methods_en.md \
      --lang en

    # German methods snippet
    ./prism_tools.py library generate-methods-text \
      --output tmp/methods_de.md \
      --lang de

By default, the command reads from ``library/survey`` and ``library/biometrics``.
You can override paths if needed:

.. code-block:: bash

    ./prism_tools.py library generate-methods-text \
      --survey-lib /path/to/survey_library \
      --biometrics-lib /path/to/biometrics_library \
      --output methods.md \
      --lang en

Note: This output is a starting point for a paper.
Always review and adapt it to your actual study protocol and reporting standards.

