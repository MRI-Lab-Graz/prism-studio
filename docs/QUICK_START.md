# Quick Start

The shortest path from install to a first successful PRISM Studio workflow: launch
Studio, create a project, import one small dataset, validate it, and know what to do
next. For a longer guided exercise with prepared sample material, see
[Workshop](WORKSHOP.md) after this page.

## 1. Launch and create a project

**Launch**: use the prebuilt release (recommended — see [Installation](INSTALLATION.md)),
or from a source checkout: `source .venv/bin/activate && python prism-studio.py` (or
`rtk studio`). Studio opens at `http://localhost:5001`.

**Create a project**: open **Projects** → **Create New Project** → enter a name (e.g.
`my_first_study`) and a parent folder → confirm. This creates
`dataset_description.json`, `project.json`, `CITATION.cff`, `CHANGES`, `README.md`,
`.bidsignore`, `.prismrc.json`, `sourcedata/`, `derivatives/`, and `code/`.
`participants.tsv` isn't created yet — it's written once you run the
sociodemographics import step. Full details: [Projects](studio/projects.md).

## 2. Import a small dataset

The simplest first success is the workshop sample material:
`examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx`.

**Survey data**: open **Converter** → survey tab → select `wellbeing.xlsx` → confirm
the participant ID column → select item columns → preview → save into your project.
You should get survey files written into subject folders. Details:
[Converter — Survey Import](studio/converter_survey.md).

**Sociodemographics instead?** Pick the right case first — the imported file becomes
the source of truth, you're editing an existing project file, or you want a safe
merge. See [Converter — Participants](studio/converter_participants.md).

## 3. Validate

Open **Validator** → confirm your project is selected (full validation, including
BIDS, runs by default) → **Start Validation**. Findings are grouped by severity:

| Level | Meaning | What to do |
|---|---|---|
| Error | Blocking problem | Fix before treating the dataset as valid |
| Warning | Important issue | Fix soon, especially before sharing |
| Suggestion | Improvement | Use when polishing the dataset |

A first run reporting several issues is normal, not a failure — it's the feedback
that tells you what to clean up next. Common first findings: `PRISM201` (missing JSON
sidecar), `PRISM101` (invalid filename), `PRISM301` (missing required metadata
field) — see [Error Codes](ERROR_CODES.md) for the full list. Equivalent from the
terminal: `prism-validator /path/to/project`.

## 4. Score (optional) and what's next

If your survey data is ready: **Prepare Data** → **Recipe Builder** → load or create a
scoring recipe → run it → export as CSV/SPSS if needed. See
[Recipe Builder](studio/recipe_builder.md) and [Recipes](RECIPES.md) for the deeper
workflow.

From here: [Studio Guide](studio/index.md) for every screen in detail,
[CLI Reference](CLI_REFERENCE.md) for terminal workflows, or
[Workshop](WORKSHOP.md) for a longer guided exercise.

## Troubleshooting

- **No files found in the dataset** — check your data landed in the project's
  dataset structure, not only in a source-material folder.
- **Missing `dataset_description.json`** — project creation likely didn't complete;
  re-create the project.
- **Invalid filename pattern** — the validator expects BIDS-style entities, e.g.
  `sub-001_task-wellbeing_survey.tsv` or `sub-001_ses-01_task-wellbeing_survey.tsv`.
- **Studio starts but no page appears** — open `http://localhost:5001` manually and
  check the terminal output for launch errors.
