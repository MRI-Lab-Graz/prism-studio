Prism Tools (CLI)
=================

Prism-Validator includes a command-line utility `prism_tools.py` for advanced data conversion tasks, particularly for physiological data ingestion.

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

The batch command walks `input-dir` for `.lsa/.lss` files, looks for `sub-*` and session tokens (e.g., `t1`) in the path, and writes sidecars like `sub-<id>/ses-1/survey/sub-<id>_ses-1_task-<task>_beh.json` under `output-dir`.


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

