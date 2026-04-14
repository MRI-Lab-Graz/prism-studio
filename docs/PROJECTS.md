# Projects

Use the Projects page to create, open, document, and export a PRISM project.

This page is written for beginners. Use the written guide here for the full workflow. Use the companion videos for quick hands-on examples.

## What the Projects page is for

The Projects page is the home base of PRISM Studio.

Use it to:

- create a new project
- open an existing project
- fill in study metadata
- generate methods text
- prepare exports for sharing

If you are not sure where to start, start here.

## Before you begin

You only need two things:

- a project name
- a folder where the project should be created

Keep the project name short. Use letters, numbers, underscores, or hyphens. Avoid spaces.

## Create a new project

1. Open PRISM Studio.
2. Open the Projects page.
3. Select Create New Project.
4. Enter a project name.
5. Choose the parent folder.
6. Confirm creation.

PRISM creates the project folder for you.

## What PRISM creates

The exact structure is more detailed than older screenshots may suggest.

Typical project structure:

```text
my_study/
|-- dataset_description.json
|-- participants.tsv
|-- README.md
|-- CITATION.cff
|-- CHANGES
|-- .bidsignore
|-- .prismrc.json
|-- project.json
|-- contributors.json
|-- sourcedata/
|-- derivatives/
`-- code/
    `-- library/
```

You do not need to fill everything immediately. A new project is a starting point, not a finished dataset.

## Open an existing project

You can open a project in two ways:

- select the project folder
- select the `project.json` file inside that folder

This is useful when different file pickers behave differently on different systems.

After loading, the active project name appears in the Studio interface.

## Recent projects

PRISM Studio keeps a short recent-project list to make reopening easier.

If an old path no longer exists, it is removed from the recent list instead of staying there forever.

## Study metadata

After opening a project, stay on the Projects page and move through the metadata sections.

Start with the required fields first. That is enough for a clean first pass.

Good beginner order:

1. Basics
2. Overview
3. Study Design
4. Recruitment
5. Eligibility
6. Procedure
7. References

Do not try to write everything perfectly in one session. Fill the required parts first, then come back for the richer FAIR-style details.

## What belongs in project metadata

Use the Projects forms for study-level information such as:

- dataset title
- short study description
- authors and contributors
- recruitment details
- inclusion and exclusion criteria
- procedure summary
- references and funding

These forms are easier and safer than editing the JSON files by hand.

## Project files vs data files

It helps to keep the folders straight:

- `sourcedata/` is for incoming or raw source material
- `code/` is for project-local templates, recipes, and scripts
- `derivatives/` is for processed outputs such as scoring results

This separation keeps the project easier to understand later.

## Suggested beginner workflow

Use this order for most projects:

1. Create or open the project.
2. Fill in the most important metadata.
3. Import sociodemographics and survey data.
4. Run validation.
5. Fix blocking issues.
6. Run recipe-based scoring if needed.
7. Export or share the project.

## Generate methods text

The Projects page can also help you generate methods text from the project metadata and instrument information.

Use this after your templates and metadata are in reasonable shape. The result is a starting draft, not a final manuscript paragraph.

## Data Export / Share

The Projects page includes an export area for sharing and downstream use.

Current export options include:

- shareable ZIP export
- anonymized export with randomized participant IDs
- optional masking of question text in JSON sidecars
- ANC export
- openMINDS metadata export

Use the detailed written export guide in the analysis/output documentation when you reach this step.

## Beginner advice

Do not try to solve conversion, metadata, validation, and export all at once.

Finish the Projects page first. A clean project setup makes the later steps much easier.

## Related pages

- Survey import: [SURVEY_IMPORT.md](SURVEY_IMPORT.md)
- Sociodemographics import: [PARTICIPANTS_MAPPING.md](PARTICIPANTS_MAPPING.md)
- Analysis and export outputs: [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md)
- Template editing: [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)
- Recipe-based scoring: [RECIPE_BUILDER.md](RECIPE_BUILDER.md)