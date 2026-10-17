# Propose a New Modality

Workbook for proposing a new PRISM modality (for example blood samples).

- `modality_proposal_template.xlsx`: fill in the sheets `Modality` and `Columns`
  (and optionally `Types` and `Entities`). It ships filled in with an example (`biosample`);
  replace the example values.
  - `Modality`: name, suffix, data file extension(s), description. Use the name of an existing PRISM
    modality (e.g. `biometrics`) to add a new suffix to it, or a new name to
    propose a new modality; the suffix is always required. See
    `examples/modality_proposal/bloodpanel.yml` for the suffix example.
  - `Columns`: the columns of your **sample file** (ID, Description, Units,
    DataType, Scale, Type, Min, Max, AllowedValues). This is an example, not a
    contract: two or three columns are enough, and every study defines its own
    columns later in its own sidecar. `Scale` is optional: choose categorical,
    continuous or boolean from the drop-down.
  - `Types` (optional): a short list of the measurement types your modality
    knows (for example CRP, glucose, cortisol), each with a description. Columns
    can then say which `Type` they are, so the same thing gets the same name
    across studies even when column names differ. `other` is always allowed.
  - `Entities` (optional, new modalities only): suggested values for the
    `task` or `acq` filename parts, e.g. `acq | fasting`. Not allowed when you
    add a suffix to an existing modality.
- A small **synthetic** sample data file in the same format as your real
  data (at most 50 rows, 1 MB). Never use real participant data.

Name and suffix must be lowercase letters and digits and must not already be
used by PRISM or BIDS (for example `blood` is a BIDS suffix for PET blood
radioactivity). The tool tells you if a name is taken.

Run `python prism_tools.py modality propose <your-file> --sample <your-sample> --check`
to see whether the name is taken and whether the sample matches.

See `docs/MODALITY_PROPOSALS.md` for the full workflow.
