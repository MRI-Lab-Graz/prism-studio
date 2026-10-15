# Propose a New Modality

Workbook for proposing a new PRISM modality (for example blood samples).

- `modality_proposal_template.xlsx`: fill in both sheets. It ships filled in
  with an example (`biosample`); replace the example values.
  - `Modality`: name, suffix, data file extension(s), description, rationale.
  - `Columns`: the columns of your **sample file** (ID, Description, Units,
    DataType, Scale, Type, Min, Max, AllowedValues). This is an example, not a
    contract: two or three columns are enough, and every study defines its own
    columns later in its own sidecar. `Scale` is optional: choose categorical,
    continuous or boolean from the drop-down.
  - `Types` (optional): a short list of the measurement types your modality
    knows (for example CRP, glucose, cortisol), each with a description. Columns
    can then say which `Type` they are, so the same thing gets the same name
    across studies even when column names differ. `other` is always allowed.
- A small **synthetic** sample data file in the same format as your real
  data (at most 50 rows, 1 MB). Never use real participant data.

Name and suffix must be lowercase letters and digits and must not already be
used by PRISM or BIDS (for example `blood` is a BIDS suffix for PET blood
radioactivity). The tool tells you if a name is taken.

See `docs/MODALITY_PROPOSALS.md` for the full workflow.
