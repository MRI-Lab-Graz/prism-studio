# Suggested PR Title

[SCHEMA] Add subject-resolved phenotypic data files (`pheno` suffix, `inst` entity, `phenotype` datatype)

<!-- If this is opened as a BEP-linked PR, prepend the note and tip blocks required by .github/pull_request_template.md with meeting and communication details. -->

> **Update (2026-04)**: This draft incorporates reviewer feedback received from the BIDS community.
> Key changes from the original proposal:
> - **Directory**: Use `phenotype/` (existing BIDS concept) instead of a new `survey/` folder.
> - **Suffix**: Propose `pheno` instead of `survey`.
> - **Entity**: Propose `inst` (instrument) as the new entity instead of `task`, to avoid overloading task semantics.
>   Other candidate names under discussion: `assess`, `form`, `meas`, `table`, `lab`.
> - See [`BIDS_ENHANCEMENT_PROPOSAL.md`](BIDS_ENHANCEMENT_PROPOSAL.md) for the full schema change specification.

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
- [Survey import template](https://github.com/MRI-Lab-Graz/prism-studio/blob/main/docs/examples/survey_import_template.xlsx)
- [Survey schema and modality schemas](https://github.com/MRI-Lab-Graz/prism-studio/tree/main/app/schemas)
- [Template validation documentation](https://github.com/MRI-Lab-Graz/prism-studio/blob/main/docs/TEMPLATE_VALIDATION.md)
- [Dataset validation documentation](https://github.com/MRI-Lab-Graz/prism-studio/blob/main/docs/VALIDATOR.md)

These references show that the proposed structure is already practical for curation, metadata authoring, template-based reuse, and validation.

## Example Structure

Below is the proposed structure using the `phenotype/` datatype directory and
the `pheno` suffix.  The `inst` entity identifies the administered instrument.
The top-level `phenotype/` remains as an optional aggregate representation.

```text
study/
├── dataset_description.json
├── participants.tsv
├── code/
│   └── library/
│       └── phenotype/
│           ├── inst-pss_pheno.json
│           └── inst-stai_pheno.json
├── sub-01/
│   ├── ses-baseline/
│   │   └── phenotype/
│   │       ├── sub-01_ses-baseline_inst-pss_run-01_pheno.tsv
│   │       ├── sub-01_ses-baseline_inst-pss_run-01_pheno.json
│   │       ├── sub-01_ses-baseline_inst-stai_pheno.tsv
│   │       └── sub-01_ses-baseline_inst-stai_pheno.json
│   └── ses-week04/
│       └── phenotype/
│           ├── sub-01_ses-week04_inst-pss_run-01_pheno.tsv
│           ├── sub-01_ses-week04_inst-pss_run-01_pheno.json
│           ├── sub-01_ses-week04_inst-pss_run-02_pheno.tsv
│           └── sub-01_ses-week04_inst-pss_run-02_pheno.json
├── sub-02/
│   └── ses-baseline/
│       └── phenotype/
│           ├── sub-02_ses-baseline_inst-pss_run-01_pheno.tsv
│           └── sub-02_ses-baseline_inst-pss_run-01_pheno.json
└── phenotype/            # optional aggregate (existing BIDS convention)
    ├── pss.tsv
    ├── pss.json
    └── stai.tsv
```

> Note: `acq-<label>` may encode an instrument version or administration
> variant (e.g., `acq-10likert` for a 10-point Likert version of a scale).

The `phenotype/` directory in this example is deliberate.
It shows that aggregated outputs remain compatible with this proposal, but they are downstream views of structured data rather than the only canonical form.

## Scope

This PR does not propose removing aggregated phenotype tables.
It proposes that BIDS should also recognize a canonical modality-style structure for instrument-based phenotypic data, especially when those data are acquired repeatedly across sessions and runs.

## Questions For Reviewers

- Should instrument-based phenotypic data be representable in a subject-, session-, and run-resolved modality structure in the schema?
- If so, should `phenotype/` remain an optional aggregate or derived representation rather than the only primary representation?
- Is **`pheno`** the right suffix, or should the working group prefer another term such as `survey`, `assess`, or `form`?
- Is **`inst`** (instrument) the right entity name, or should another term from the candidate list be chosen: `assess`, `form`, `meas`, `table`, `lab`, `survey`, `quiz`?
- Should the top-level sidecar metadata fields (`InstrumentName`, `Language`, `Respondent`, etc.) be REQUIRED, RECOMMENDED, or OPTIONAL?

---

## Detailed Schema Changes

See [`BIDS_ENHANCEMENT_PROPOSAL.md`](BIDS_ENHANCEMENT_PROPOSAL.md) for the
exact YAML snippets to apply to a fork of `bids-standard/bids-specification`,
including changes to:

- `src/schema/objects/datatypes.yaml`
- `src/schema/objects/suffixes.yaml`
- `src/schema/objects/entities.yaml`
- `src/schema/rules/entities.yaml`
- `src/schema/rules/modalities.yaml`
- `src/schema/rules/files/raw/phenotype.yaml` (new file)