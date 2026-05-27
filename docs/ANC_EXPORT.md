# ANC Export

Use ANC export when you need a delivery package for Austrian NeuroCloud-oriented
submission workflows.

If you are looking for the broader export picture first, start with
[ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md).

## What ANC export is for

ANC export is not the same as everyday project saving or derivative generation.
It is a packaging workflow for a specific downstream submission context.

In practice it should:

- create a dedicated export folder separate from the working project
- preserve the project itself as the source of truth
- prepare a package shaped for ANC-oriented handoff requirements

Typical result:

- a separate folder ending in `_anc_export`

## When to use it

Use ANC export when:

- the project is already in a validated state
- you need a dedicated submission package rather than an ordinary working copy
- the target workflow explicitly expects ANC-oriented export structure

Do not use ANC export as a substitute for ordinary project work. Finish the core
project workflow first.

## Recommended workflow

1. Open the correct project in PRISM Studio.
2. Complete validation first.
3. Review whether anonymization or other export-related decisions should happen before submission.
4. Open the project export area.
5. Run **ANC export**.
6. Review the generated `_anc_export` folder before submission.

## What to review before submission

At minimum, check:

- required project metadata is present
- participant identifiers match the intended submission policy
- the export was generated from the correct, latest validated project state
- the package contains the expected structure rather than an older stale export

## Relationship to other outputs

Useful rule of thumb:

- use `derivatives/` for processed outputs that still belong inside the project
- use anonymized or shareable export for general external sharing
- use ANC export when the target is specifically ANC-oriented submission

## Common mistakes

- running ANC export before validation
- treating the `_anc_export` folder as the main working dataset
- forgetting to check participant identifier policy before submission
- assuming the most recent export folder automatically reflects the most recent project state

## Related pages

- [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md)
- [PROJECTS.md](PROJECTS.md)
- [VALIDATOR.md](VALIDATOR.md)
