# Survey Import

Use this page when you want to bring questionnaire data into a PRISM project.

This page is written for beginners. Use the written guide here for the full workflow. Use the companion videos for quick hands-on examples.

## What this page covers

This page focuses on the normal survey workflow in PRISM Studio.

It does not replace the separate LimeSurvey documentation. If you work with LimeSurvey-specific files or export details, use the dedicated LimeSurvey pages for that part.

## Where survey import happens

Open:

- PRISM Studio
- Converter
- Survey tab

This is the main survey import screen.

## What you usually need

For a typical import, you need:

- a survey data file
- a participant ID column
- a session value

Sometimes you also need:

- a run column
- a language choice
- an ID mapping file
- a specific survey template selection

## Supported starting points

The survey converter supports common tabular survey inputs such as:

- Excel files
- CSV files
- TSV files

The Studio interface may also show other survey file types. For beginner work, start with Excel, CSV, or TSV unless your teaching material tells you otherwise.

## If you need to create a survey template first

Use the canonical Excel workbook at `official/create_new_survey/survey_import_template.xlsx`.

Quick workbook flow:

1. Fill `General` (instrument metadata and version context).
2. Fill `Items` (default item texts and scale definitions).
3. Use `Variants` only when you need explicit multi-version definitions or per-variant item overrides.
4. Check the built-in `Help` sheet for column rules and examples.

For detailed field semantics, see [specs/survey.md](specs/survey.md).

## Recommended beginner workflow

1. Load your project first on the Projects page.
2. Open Converter and switch to Survey.
3. Choose the survey file.
4. Check that the participant ID column is correct.
5. Set the session.
6. Run Preview.
7. Review the summary and warnings.
8. Run Convert.

Preview first. Convert second. This is the safest habit.

## Step 1: Choose the file

Select the survey file from your computer.

If a project is already open, PRISM can also help you pick files from `sourcedata/`. That is useful once your project folder is organized.

## Step 2: Check the participant ID column

PRISM tries to detect the participant ID column automatically.

Always check the selection before converting. A wrong ID column causes the biggest downstream problems.

If automatic detection is wrong, choose the correct column manually.

## Step 3: Set the session

The session value is required in the survey converter.

This value becomes part of the file naming and project structure. Use a simple, stable label.

Examples:

- `1`
- `2`
- `baseline`
- `followup`

## Step 4: Use Preview

Preview is a dry run.

It lets you check:

- whether the file was read correctly
- whether IDs were understood correctly
- whether the session and run logic look right
- whether the expected output files make sense

Use Preview every time you work with a new file format or a new dataset.

## Step 5: Convert

After a clean preview, run Convert.

The converter writes PRISM-style survey files into the project structure. It also checks the matching template situation and tells you when more metadata work is still needed.

## Template follow-up after import

Survey import and template editing are connected.

If PRISM copies a survey template into your project library, that project-local template may still need administration details such as language or collection context.

When that happens, open the Template Editor next.

## Advanced options

You do not need the advanced options for every import. Use them only when the simple path is not enough.

Common advanced options are:

- choose a specific survey
- choose a language
- provide an ID mapping file
- override detected session column
- override detected run column
- choose a questionnaire version when multiple versions exist

If you are teaching beginners, it is usually better to keep the first import session simple and introduce these options later.

## Questionnaire versions

Some templates include more than one questionnaire version.

In that case, PRISM asks you to choose the version during import. This keeps the output consistent with the correct item set and naming.

If you are unsure which version to choose, stop and confirm it before converting.

## Common beginner mistakes

- converting before checking Preview
- selecting the wrong ID column
- forgetting to load the correct project first
- mixing data from different sessions into one import step
- assuming the template is finished when PRISM has only copied a project-local draft

## After survey import

Once survey import is complete, the usual next steps are:

1. open the Template Editor if PRISM asks for missing template details
2. run validation
3. run recipe-based scoring if needed

## Related pages

- Projects: [PROJECTS.md](PROJECTS.md)
- Template editing: [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)
- Sociodemographics import: [PARTICIPANTS_MAPPING.md](PARTICIPANTS_MAPPING.md)
- Recipe-based scoring: [RECIPE_BUILDER.md](RECIPE_BUILDER.md)
- Analysis and export outputs: [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md)