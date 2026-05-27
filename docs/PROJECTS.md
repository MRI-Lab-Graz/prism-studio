# Projects

Use the Projects page to create, open, document, and export a PRISM project.

If you only remember one rule from this page, use this one: start every new
study in **Projects** before you begin importing or editing data elsewhere.

## What the Projects page owns

The Projects page is the home base for study-level state.

Use it to:

- create a new project
- open an existing project
- maintain study metadata
- manage project-level preferences and generated text
- prepare export and sharing workflows

Other pages depend on the active project context created here.

## Before you create a project

You only need:

- a project name
- a parent folder where the project should be created

Recommended naming:

- use letters, numbers, underscores, or hyphens
- avoid spaces
- keep the name short and stable

If you expect a DataLad-aware project, read [DATALAD.md](DATALAD.md) before
manually restructuring anything.

## Create a new project

1. Open PRISM Studio.
2. Open **Projects**.
3. Select **Create New Project**.
4. Enter the project name.
5. Choose the parent folder.
6. Confirm creation.

PRISM Studio creates the project structure for you.

## What PRISM creates

A new project is a working area, not a finished dataset.

Typical structure:

```text
my_study/
├── dataset_description.json
├── participants.tsv
├── README.md
├── CITATION.cff
├── CHANGES
├── .bidsignore
├── .prismrc.json
├── project.json
├── contributors.json
├── sourcedata/
├── derivatives/
└── code/
    └── library/
```

Why this matters:

- `sourcedata/` holds incoming source material
- validated dataset files live at the project root
- `code/` keeps project-local templates, recipes, and scripts
- `derivatives/` holds processed outputs rather than raw inputs

That separation makes the project easier to validate, understand, and share.

## Open an existing project

You can open a project by selecting either:

- the project folder
- the `project.json` file inside it

This dual entry path is useful because file-picker behavior differs across
operating systems.

After loading, confirm that the active project shown in Studio matches the one
you intended to edit. This matters before any import, template, or export action.

## Recommended first-session workflow

For a new study, this order is usually safest:

1. Create or open the project.
2. Fill in the key study metadata.
3. Import participants and survey data.
4. Run validation.
5. Fix blocking issues.
6. Add templates or recipes if needed.
7. Export or share only after the dataset is in good shape.

## Metadata sections: what to complete first

Once the project is active, stay on the Projects page and work through the
metadata sections.

Good beginner order:

1. Basics
2. Overview
3. Study Design
4. Recruitment
5. Eligibility
6. Procedure
7. References

Do not try to perfect every field in the first session. The right first goal is
a complete enough project that other workflows can safely build on it.

## What belongs in project metadata

Use the Projects forms for study-level information such as:

- dataset title
- study description
- authors and contributors
- recruitment details
- inclusion and exclusion criteria
- procedure summary
- references, identifiers, and funding

This is safer than editing project-level JSON files manually because the form
workflow helps keep the structure consistent.

## Example: first project setup

Example project: `wellbeing_study`

1. Create the project in **Projects**.
2. Enter a short title and study summary.
3. Add the main contributors.
4. Save the project metadata.
5. Move to **Converter** and import `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx`.

Expected outcome after this phase:

- the project root exists and loads cleanly
- study-level files such as `project.json` and `dataset_description.json` exist
- the project is ready for the converter and validator workflows

## Methods text generation

The Projects page can generate draft methods text from project metadata and
instrument information.

Use this after:

- the key project metadata is present
- your templates or instrument metadata are reasonably complete

Treat the output as a starting draft, not final manuscript text.

## Export and sharing

The Projects page also owns project-level export workflows.

Current export tasks can include:

- shareable ZIP export
- anonymized export with participant ID remapping
- optional metadata-masking or privacy-related export controls
- ANC export
- openMINDS-related export workflows

The safe rule is to export after validation, not before it.

For the deeper output guide, see [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md).

## Common mistakes on the Projects page

### Starting import before a project is active

If you import first and only later realize the wrong project was active, you can
create confusing results. Confirm the active project name before any save action.

### Treating `sourcedata/` as the final dataset location

`sourcedata/` is for incoming material. Validated project data and export-ready
data should not stay only there.

### Trying to finish all metadata in one pass

Complete the required and high-value fields first, then come back for the richer
descriptive metadata.

## Related pages

- [CONVERTER.md](CONVERTER.md)
- [SURVEY_IMPORT.md](SURVEY_IMPORT.md)
- [PARTICIPANTS_MAPPING.md](PARTICIPANTS_MAPPING.md)
- [VALIDATOR.md](VALIDATOR.md)
- [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md)