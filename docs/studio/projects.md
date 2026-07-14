# Projects

The Projects page is the entry point for creating, opening, and re-opening PRISM
Studio projects.

## Goal

Get a project created or loaded so the rest of Studio (Converter, Validator,
Template Editor, Recipe Builder, Share/Export) has something to work against.

## Entry points

The page shows three cards:

- **Create New Project** — start a brand-new project from scratch.
- **Init PRISM on BIDS Dataset** — add PRISM's project files to a BIDS dataset that
  already exists, without overwriting anything already there.
- **Open Existing Project** — load a project you (or a collaborator) already created.

## Creating a new project

Fields on the **Create New Project** form:

- **Project Name** — required, letters/numbers/`_`/`-` only, no spaces. The field
  validates live as you type and explains specifically what's wrong (e.g. flags
  spaces or German umlauts/`ß` by name) rather than just turning red.
- **Project Location** — the parent folder the new project directory is created in.
- **Use DataLad version control for this new project** — optional checkbox. If
  DataLad/git-annex aren't installed, project creation silently falls back to a
  non-DataLad project rather than failing.
- **Import from study application (survey.json)** — optional file button that prefills
  PI/author/ethics/funding fields from a Pavlovia study-application export.

There is no modality or session picker at creation time — modalities and sessions are
no longer chosen up front; they're populated as you actually import data.

Buttons: **Preliminary Save** (saves the form without creating the project yet) and
**Create Project**.

### What gets created

```text
my_first_study/
├── dataset_description.json
├── .bidsignore
├── .prismrc.json
├── README.md
├── project.json
├── CITATION.cff
├── CHANGES
├── .gitattributes        (only if the DataLad text-tracking policy write succeeds)
├── sourcedata/
├── derivatives/
└── code/
    ├── library/
    └── recipes/
```

`participants.tsv` and `participants.json` are **not** created here — they're written
later, once you run the participants/sociodemographics import step (see
[Converter — Participants](converter_participants.md)).

The generated `README.md` describes this same layout and points you at `sourcedata/`,
`code/library/`, and `code/recipes/` for the next steps.

## Init PRISM on BIDS Dataset

Same file set as project creation, but only for files that don't already exist —
nothing your existing BIDS dataset already has gets overwritten. If the dataset has a
legacy `phenotype/` directory, it's auto-imported as part of this step.

## Deleting a project

A **Delete Project** button appears once a project is created or loaded (in the
project-created panel and in the loaded-project panel). Deletion is permanent and
irreversible — it removes the entire project folder from disk, including DataLad/git
history and derivatives.

To prevent accidental deletion, the confirmation dialog requires you to type the
project's exact name before the delete button enables. On confirmation, Studio clears
the project from your current-project and recent-projects state and returns you to the
Projects page.

There is still no "trash"/undo — deletion goes straight to the filesystem. If you want
a safety net, make sure the project is backed up (e.g. pushed to a DataLad sibling)
before deleting it here.

## Opening an existing project

The **Open Existing Project** form takes a single path, and accepts either:

- the project's root folder, or
- the path to its `project.json` file directly.

Submitting validates the project's structure, sets it as your active project for the
rest of Studio, and remembers it as your last-opened project.

A **Recent Projects** list (with a **Clear** button) tracks projects you've opened
before, de-duplicated by their resolved absolute path.

## What's next

- [Studio Guide overview](index.md)
- [Survey Import](converter_survey.md) or [Participants Import](converter_participants.md) to bring in your first data
- [Share / Export](export.md) once you have something to export
