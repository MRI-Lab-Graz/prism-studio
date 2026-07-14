# DataLad Workflows

DataLad is optional in PRISM Studio, but matters for projects needing large-file
handling, provenance-aware operations, and reproducible dataset changes. This page
covers the public usage model, not internal implementation details.

## When to use it

Use DataLad when: your project has large files that shouldn't behave like ordinary
Git text files; you need provenance for dataset-changing operations; you want a
layout that scales to larger/longer-lived studies; you expect to exchange datasets
through DataLad-aware workflows (OpenNeuro-style installs, nested datasets).

You can skip it if: the dataset is small, you're just learning PRISM Studio, you
don't need dataset-level provenance yet, or the project is a local, short-lived
exercise/workshop. Don't make DataLad the first thing a beginner has to learn unless
the project actually needs it.

## How PRISM Studio uses it

PRISM Studio works with DataLad-friendly projects instead of forcing a separate
structure: the project root stays the controlling dataset; each `sub-*` folder is
treated as a nested dataset when DataLad is in use; PRISM stays an add-on to BIDS
rather than introducing a parallel layout; export-side processing happens on export
targets or copies, not by mutating source raw data in place.

For most workflows the visible effect isn't a different UI — the practical change is
in how the project is organized and how large-file/provenance-aware operations
behave: project creation/repair flows preserve dataset topology; file-management
operations keep provenance instead of behaving like ordinary file moves;
export/anonymization workflows preserve the source dataset and operate on copies;
large remote datasets may be validated/prepared incrementally instead of forcing
full local materialization first.

```text
my_study/
├── .git/
├── .datalad/
├── dataset_description.json
├── project.json
├── code/
├── derivatives/
├── sourcedata/
├── sub-001/
└── sub-002/
```

The exact internal state depends on how the dataset was created, but the public
rule is simple: don't flatten or manually rearrange the project into a
non-BIDS structure just because DataLad is enabled.

## Common use cases

**Local project with large files**: create/open the project → keep the root
structure intact → use normal PRISM workflows for conversion, validation, export →
prefer PRISM-managed actions over manual ad-hoc file moves.

**OpenNeuro or remote DataLad install**: when the source comes from a DataLad-aware
remote, check that the project root is present locally, the expected `sub-*`
dataset structure resolves locally, and PRISM Studio sees the project as one
coherent working tree.

**Export and anonymization**: PRISM prepares an export target rather than changing
the source project in place — your source project stays reusable, provenance is
easier to reason about, and accidental mutation of raw data is avoided.

## Practical advice

Keep BIDS naming and structure intact even when DataLad is enabled. Let PRISM
Studio manage project-aware workflows instead of manually editing the layout. Treat
`sourcedata/`, validated dataset files, `code/`, and `derivatives/` as separate
responsibilities. Validate after structural changes so DataLad-aware edits don't
silently drift from PRISM expectations.

## What's next

- [What is PRISM](WHAT_IS_PRISM.md)
- [Projects](studio/projects.md) · [Export](studio/export.md)
- [CLI Workflows](CLI_WORKFLOWS.md)
