Prism Tools (CLI)
=================

Prism-Validator includes a command-line utility `prism_tools.py` for advanced data conversion tasks, particularly for physiological data ingestion.

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

.. code-block:: bash

    ./prism_tools.py survey import-excel \
      --excel metadata.xlsx \
      --output survey_library

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

