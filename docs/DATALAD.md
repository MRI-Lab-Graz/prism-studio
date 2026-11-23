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

## Who signs your snapshots

Every snapshot (a DataLad "save") records a name and an email. These belong to **you**, not to the
project: PRISM Studio reads and writes them in your computer's git settings, and a project never stores them.
A project can therefore be shared, pushed and pulled without one person's name ending up on another person's
snapshots.

- **Studio**: Settings > DataLad Version Control > *Your name and email* (the [DataLad page](studio/datalad.md)
  links there under *More*). If you enable DataLad without them, Studio asks once in a pop-up.
- **CLI**: `python prism_tools.py datalad identity --name "Your Name" --email you@example.org`
  (without `--name`/`--email` it shows the current values).
- **Older projects** that still carry a name and email in `.prismrc.json` are cleaned once: the values move to
  your git settings if you have none, and are removed from the project file.

## Snapshots

| Step | Studio | CLI |
|---|---|---|
| Check this computer (git, git-annex, DataLad, name and email) | DataLad page > More > *Check this computer* | `prism_tools.py datalad doctor` |
| Turn DataLad on and save a first snapshot | DataLad page > *Enable DataLad* | `prism_tools.py datalad enable --project <root> --yes` |
| Save the changes as a snapshot | DataLad page > *Save* | `prism_tools.py datalad save --project <root> --message "..."` |

In Studio all of this is on the [DataLad page](studio/datalad.md) (the **DataLad** item in the navbar). It shows
the one next step for the open project and keeps the rest under *More*.

Enabling and saving are tied to validation: an existing project that does not validate cannot be put under
DataLad, and the **save gate** refuses a snapshot of a dataset that does not validate (see
[CLI Reference](CLI_REFERENCE.md) for `save-gate`). The refusal lists the validation errors, so fix them and
save again. Text files (`.tsv`, `.json`, `.csv`, ...) are always kept in plain git, never in git-annex.

## Working with several people

The intended setup for a lab: everybody has their own copy of the project and works with their own account;
one shared DataLad server holds the newest valid state. PRISM Studio makes the project DataLad-ready and edits it
safely; **sending, getting the latest, opening a copy from the server and getting data are done in
[Worldline Desktop](https://worldline-desktop.readthedocs.io/)**, which also checks the dataset with
`prism-validator` before every save.

- **`sourcedata/`** (raw data, possibly with names or emails) is tracked in plain git and travels with every
  push: send it to the internal lab server only. Worldline Desktop refuses to send a project that tracks
  `sourcedata/` to a public host (GitHub, GitLab, GIN, Bitbucket, Codeberg, OpenNeuro or any web address).
- **Save gate.** Studio installs a pre-commit hook (`prism_tools.py save-gate`) in the project and its subject
  datasets, so a commit from any tool is refused while the dataset has validation errors.

**What to do next.** `prism_tools.py datalad status --project <root> [--check-nested] [--json]` tells
what the [DataLad page](studio/datalad.md) offers next: enable DataLad or save. With `--check-nested` it also counts
the subject datasets that are not registered yet (as the page does); if some are left, the next step is to finish
enabling (`datalad enable` registers them).

**Saving despite validation errors.** If the dataset has validation errors, Save refuses and lists them. You can
save anyway (*Save anyway*, or `--allow-invalid`); the snapshot message then ends with
`[saved with N validation error(s)]` so the history shows it.

The acknowledgement reaches the save gate through one environment variable, `PRISM_ACK_INVALID=1`, which PRISM passes
only to the one save you acknowledged (never to Studio itself, so its other saves stay gated). The gate lets that one
command through and logs it (`save_acknowledged`). Like the hook itself it is advisory: anyone can set it in a
terminal, so the audit log is the record, not a lock. Unsaved changes and a validator that cannot run are never
acknowledged away.

## What's next

- [What is PRISM](WHAT_IS_PRISM.md)
- [DataLad page](studio/datalad.md) · [Projects](studio/projects.md) · [Export](studio/export.md)
- [CLI Workflows](CLI_WORKFLOWS.md)
