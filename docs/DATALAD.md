# DataLad Workflows

DataLad is optional in PRISM Studio, but it matters for projects that need large
file handling, provenance-aware operations, and reproducible dataset changes.

This page explains the public usage model rather than every internal
implementation detail.

## When to use DataLad

Use DataLad when one or more of these are true:

- your project contains large files that should not behave like ordinary Git text files
- you need provenance for dataset-changing operations
- you want a project layout that scales to larger or longer-lived studies
- you expect to exchange datasets through DataLad-aware workflows such as OpenNeuro-style installs or nested datasets

If you only need a small local project, you can use PRISM Studio without
thinking about DataLad first.

## PRISM Studio and DataLad

PRISM Studio is designed to work with DataLad-friendly projects instead of
forcing a separate structure.

Important principles:

- the project root should remain the controlling dataset
- each `sub-*` folder should be treated as a nested dataset when DataLad is in use
- PRISM stays an add-on to BIDS rather than introducing a parallel layout
- export-side processing should happen on export targets or copies, not by mutating source raw data in place

## What DataLad changes for a user

For most user workflows, the visible effect is not a different UI. The practical
change is in how the project should be organized and how large-file or
provenance-aware operations behave.

Typical impacts:

- project creation and repair flows need to preserve the dataset topology
- some file-management operations should keep provenance instead of behaving like ordinary file moves
- export or anonymization workflows should preserve the source dataset and operate on copies or export targets
- large remote datasets may be validated or prepared incrementally instead of forcing full local materialization first

## Recommended project topology

A DataLad-aware PRISM project should keep the project root as the superdataset.
When subject folders are managed as nested datasets, treat each `sub-*` folder as
part of that controlled structure.

Conceptually:

```text
my_study/
├── .git/
├── .datalad/
├── dataset_description.json
├── participants.tsv
├── project.json
├── code/
├── derivatives/
├── sourcedata/
├── sub-001/
└── sub-002/
```

The exact internal state depends on how the dataset was created, but the public
rule is simple: do not flatten or manually rearrange the project into a separate
non-BIDS structure just because DataLad is enabled.

## Common use cases

### Local project with large files

Use DataLad when your project contains large binaries and you still want a clean
project history.

Typical path:

1. Create or open the project in PRISM Studio.
2. Keep the root project structure intact.
3. Use normal PRISM workflows for conversion, validation, and export.
4. Prefer PRISM-managed actions over manual ad-hoc file moves.

### OpenNeuro or remote DataLad install

When the source comes from a DataLad-aware remote, the important requirement is
that the nested dataset structure resolves correctly locally.

What to check:

- the project root is present locally
- the expected `sub-*` dataset structure exists locally
- PRISM Studio sees the project as one coherent working tree

### Export and anonymization

When export workflows include anonymization or defacing, the safe mental model is
that PRISM should prepare an export target rather than changing the source
project in place.

That matters because:

- your source project stays reusable
- provenance is easier to reason about
- accidental mutation of raw data is avoided

## When not to use DataLad first

Do not make DataLad the first thing a beginner has to learn unless the project
actually needs it.

You can start without it if:

- the dataset is small
- you are just learning PRISM Studio
- you do not need dataset-level provenance yet
- the project is a local, short-lived exercise or workshop

## Practical advice

- Keep BIDS naming and structure intact even when DataLad is enabled.
- Let PRISM Studio manage project-aware workflows instead of manually editing the layout.
- Treat `sourcedata/`, validated dataset files, `code/`, and `derivatives/` as separate responsibilities.
- Use validation after structural changes so DataLad-aware project edits do not silently drift from PRISM expectations.

## Related pages

- [WHAT_IS_PRISM.md](WHAT_IS_PRISM.md)
- [PROJECTS.md](studio/projects.md)
- [ANALYSIS_OUTPUT.md](studio/export.md)
- [CLI_WORKFLOWS.md](CLI_WORKFLOWS.md)
