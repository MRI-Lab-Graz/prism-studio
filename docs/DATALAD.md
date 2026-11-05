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

- **Studio**: Settings > DataLad Version Control > *Your name and email*. If you enable DataLad without them,
  Studio asks once in a pop-up.
- **CLI**: `python prism_tools.py datalad identity --name "Your Name" --email you@example.org`
  (without `--name`/`--email` it shows the current values).
- **Older projects** that still carry a name and email in `.prismrc.json` are cleaned once: the values move to
  your git settings if you have none, and are removed from the project file.

## Snapshots

| Step | Studio | CLI |
|---|---|---|
| Check this computer (git, git-annex, DataLad, name and email) | *Check DataLad setup* | `prism_tools.py datalad doctor` |
| Turn DataLad on and save a first snapshot | *Enable DataLad* | `prism_tools.py datalad enable --project <root> --yes` |
| Save the changes as a snapshot | *Save* | `prism_tools.py datalad save --project <root> --message "..."` |

Enabling and saving are tied to validation: an existing project that does not validate cannot be put under
DataLad, and the **save gate** refuses a snapshot of a dataset that does not validate (see
[CLI Reference](CLI_REFERENCE.md) for `save-gate`). The refusal lists the validation errors, so fix them and
save again. Text files (`.tsv`, `.json`, `.csv`, ...) are always kept in plain git, never in git-annex.

## Working with several people

The intended setup for a lab: everybody has their own copy of the project and works with their own account;
one shared DataLad server holds the newest valid state.

1. **One person edits** in PRISM Studio and saves snapshots.
2. **Only a valid dataset reaches the server.** Publishing (below) validates first and pushes nothing if there
   are errors.
3. Everybody else updates their copy from the server.

**Getting the latest.** When you open a DataLad project, Studio asks the server for what others have saved and
brings it in (CLI: `prism_tools.py datalad update --project <root>`). It is deliberately careful:

- It only fast-forwards. It never merges, so it cannot mix two people's work. If you and someone else both
  saved changes, it stops, changes nothing and tells you to ask your data steward.
- It refuses while your project has unsaved changes. Save first, then get the latest.
- A project with no server yet is simply skipped, and a server that cannot be reached shows a message and does not
  stop you from working.

The server can be an SSH location or a mounted network share. Each user's copy is a clone of the server's
dataset, so the server is its `origin`; Studio's *Sync now* (`prism_tools.py datalad sync --project <root>`) is
*get the latest, then publish*.

**Putting a project on the server (the first person).** `prism_tools.py datalad put-on-server --project <root>
--location <folder | user@host:path | ssh://host/path>` creates the dataset on the server (subject datasets too) and
sends the project, with the same checks as publishing: saved, valid (or acknowledged with `--allow-invalid`), and no
public host while `sourcedata/` is tracked. All of them run before anything is created on the server. A location that is
not empty is refused: if the project is already there, open it from the server instead. If the first send is
interrupted, the server is already connected; *Sync now* finishes it.

**What to do next.** `prism_tools.py datalad status --project <root> [--check-server] [--validate] [--json]` tells
what the DataLad page offers next: enable DataLad, put the project on a server, save, or sync. A server that cannot be
reached is shown as such and does not change that advice.

**Saving despite validation errors.** If the dataset has validation errors, Save refuses and lists them. You can
save anyway (*Save anyway*, or `--allow-invalid`); the snapshot message then ends with
`[saved with N validation error(s)]` so the history shows it. Publishing and *Sync now* also refuse while there
are errors, unless you acknowledge them the same way (`--allow-invalid`); the push is then recorded in the audit log
as `pushed_with_errors` with the error count.

The acknowledgement reaches the git hooks through one environment variable, `PRISM_ACK_INVALID=1`, which PRISM passes
only to the one save or push you acknowledged (never to Studio itself, so its other saves stay gated). The save gate (pre-commit) and the publish
gate (pre-push) let that one command through and log it (`save_acknowledged`, `hook_acknowledged`). Like the hooks
themselves it is advisory: anyone can set it in a terminal, so the audit log is the record, not a lock. Unsaved
changes and a validator that cannot run are never acknowledged away.

## Publishing from a department share

The rule: a dataset on the department share reaches the DataLad server only if it
validates. `prism_tools.py publish --project <root>` validates and then pushes to the
server sibling; if validation has errors, nothing is pushed.

- **Who is publishing**: pass `--as "Name <email>"`, or set `PRISM_USER_NAME` and
  `PRISM_USER_EMAIL`; otherwise git config is used. The publish is recorded in an audit log.
- **Hook**: `prism_tools.py publish --install-hook --project <root>` installs a git
  pre-push hook so a plain `git push` to the server is gated by the same check
  (`publish --check`). It refuses to overwrite an existing hook.
- **`PRISM_TOOLS`**: the hook finds the tool through the `PRISM_TOOLS` environment variable,
  which must point to an executable file. A wrapper script that runs
  `python /path/to/prism_tools.py "$@"` works. If the hook cannot find the tool it fails
  closed: the push is blocked.
- **Caveats**: `git push --no-verify` bypasses the hook. Nested `sub-*` datasets are not
  covered by the superdataset's hook yet.
- **Save first**: the push sends committed state only, so publishing (and the hook) is
  refused while the dataset has uncommitted or untracked changes (including inside
  subdatasets). Run `datalad save`, then publish.
- **Audit log**: `<git-dir>/prism/publish.jsonl`, one JSON line per attempt (pushed, pushed_with_errors,
  refused, hook allowed/refused/acknowledged). It lives in the git dir, so it never dirties the dataset.
- **Studio**: both "Publish (validated)" and "Sync now" are gated; Sync now also gets the latest first.
- **More caveats**:
  - The gate validates with the stable schema and no library path, so the Studio validator
    page can disagree if the project uses another schema or library. The backend is the authority.
  - The hook only gates the sibling name it was installed with; a push by URL or after
    renaming the sibling passes.
  - `datalad push` copies annexed files to the server before `git push` runs the hook, so a
    blocked push can still leave annexed content (no branch points to it) on the server.
  - Pushing an arbitrary older commit by hand is not covered.

## What's next

- [What is PRISM](WHAT_IS_PRISM.md)
- [Projects](studio/projects.md) · [Export](studio/export.md)
- [CLI Workflows](CLI_WORKFLOWS.md)
