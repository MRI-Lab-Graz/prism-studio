# Suggested PR Title

[SCHEMA] Support structured survey data as a BIDS modality

<!-- If this is opened as a BEP-linked PR, prepend the note and tip blocks required by .github/pull_request_template.md with meeting and communication details. -->

## Proposed Changes

- Add schema support for structured survey data as a first-class BIDS representation for instrument-based phenotypic data.
- Allow survey files to follow the existing subject and session hierarchy and to use entities such as `task` and `run` when needed.
- Preserve `phenotype/` as an optional aggregate or derived representation rather than the only primary representation.

## Summary

This PR proposes adding schema support for structured instrument-based survey data as a valid BIDS representation, organized in the same subject-, session-, and run-resolved way as other BIDS modalities.

The goal is not to replace aggregated tabular phenotypic data.
It is to complement them with a canonical acquisition-facing structure that preserves provenance, timing, and instrument context, while still allowing aggregated tables to be generated later when needed.

A working reference implementation already exists in [PRISM Studio](https://github.com/MRI-Lab-Graz/prism-studio), with documentation at [prism-studio.readthedocs.io](https://prism-studio.readthedocs.io).

## Rationale

BIDS is strongest when its canonical structures reflect how data are actually acquired.
For imaging, physio, events, and other modalities, the normative pattern is a subject-resolved structure first, with higher-level summaries and derivatives produced later.

Instrument-based phenotypic data fit this same pattern.
Treating `phenotype/` as the only primary home for those data flattens acquisition context at the point where BIDS usually preserves it.

A structured survey modality would:

- preserve provenance and administration context,
- support repeated assessments across sessions and runs,
- keep sidecar metadata next to the corresponding data files, and
- still allow aggregated phenotype tables to be generated later.

That direction is structurally stronger because aggregated tables can be written from a structured survey layout with little ambiguity, whereas reconstructing the original structure from only an aggregate table often requires extra assumptions.

## Reference Implementation

This proposal is grounded in an existing toolchain rather than a purely abstract design discussion:

- [PRISM Studio repository](https://github.com/MRI-Lab-Graz/prism-studio)
- [PRISM Studio documentation](https://prism-studio.readthedocs.io)
- [Survey import template](https://github.com/MRI-Lab-Graz/prism-studio/blob/main/official/create_new_survey/survey_import_template.xlsx)
- [Survey schema and modality schemas](https://github.com/MRI-Lab-Graz/prism-studio/tree/main/app/schemas)
- [Template validation documentation](https://github.com/MRI-Lab-Graz/prism-studio/blob/main/docs/TEMPLATE_VALIDATION.md)
- [Dataset validation documentation](https://github.com/MRI-Lab-Graz/prism-studio/blob/main/docs/VALIDATOR.md)

These references show that the proposed structure is already practical for curation, metadata authoring, template-based reuse, and validation.

## Example Structure

Below is the kind of subject-, session-, and run-resolved structure this PR is intended to support.
I use `survey` here as a working label for the modality directory, but I am open to discussion on the exact naming.

```text
study/
├── dataset_description.json
├── participants.tsv
├── code/
│   └── library/
│       └── survey/
│           ├── survey-pss.json
│           └── survey-stai.json
├── sub-01/
│   ├── ses-baseline/
│   │   └── survey/
│   │       ├── sub-01_ses-baseline_task-pss_run-01_survey.tsv
│   │       ├── sub-01_ses-baseline_task-pss_run-01_survey.json
│   │       ├── sub-01_ses-baseline_task-stai_run-01_survey.tsv
│   │       └── sub-01_ses-baseline_task-stai_run-01_survey.json
│   └── ses-week04/
│       └── survey/
│           ├── sub-01_ses-week04_task-pss_run-01_survey.tsv
│           ├── sub-01_ses-week04_task-pss_run-01_survey.json
│           ├── sub-01_ses-week04_task-pss_run-02_survey.tsv
│           └── sub-01_ses-week04_task-pss_run-02_survey.json
├── sub-02/
│   └── ses-baseline/
│       └── survey/
│           ├── sub-02_ses-baseline_task-pss_run-01_survey.tsv
│           └── sub-02_ses-baseline_task-pss_run-01_survey.json
└── phenotype/
    ├── pss_summary.tsv
    └── stai_summary.tsv
```

The `phenotype/` directory in this example is deliberate.
It shows that aggregated outputs remain compatible with this proposal, but they are downstream views of structured data rather than the only canonical form.

## Scope

This PR does not propose removing aggregated phenotype tables.
It proposes that BIDS should also recognize a canonical modality-style structure for instrument-based phenotypic data, especially when those data are acquired repeatedly across sessions and runs.

## Questions For Reviewers

- Should instrument-based phenotypic data be representable in a subject-, session-, and run-resolved modality structure in the schema?
- If so, should `phenotype/` remain an optional aggregate or derived representation rather than the only primary representation?
- Is `survey` the right directory and suffix label, or should the working group prefer another term such as `pheno`, `assess`, `form`, `inst`, or `meas`?