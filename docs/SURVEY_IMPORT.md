# Survey Import

Use this page when you want to bring questionnaire data into a PRISM project.

Survey import is one of the core PRISM Studio workflows because it connects raw
tabular responses to structured files, templates, validation, and later scoring.

## What this page covers

This page covers the normal survey workflow in PRISM Studio.

It does not replace the dedicated LimeSurvey documentation. If your workflow is
specifically about LimeSurvey export structure or integration details, use the
LimeSurvey pages for that part.

## Where survey import happens

Open:

- PRISM Studio
- Converter
- Survey tab

## What you typically need

For a straightforward first import, you usually need:

- one survey data file
- one participant ID column
- one session value

Depending on the dataset, you may also need:

- a run column
- a language selection
- an ID mapping file
- a questionnaire version choice
- a specific template selection

## Supported input types

Start with common tabular formats unless you have a specific workflow reason not
to.

Typical starting formats:

- Excel
- CSV
- TSV

## Recommended workflow

Use this sequence for most imports:

1. Load the correct project first.
2. Open **Converter → Survey**.
3. Select the source file.
4. Confirm the participant ID column.
5. Set the session value.
6. Review any run or version settings if they apply.
7. Run **Preview**.
8. Review the summary and warnings.
9. Run **Convert** only after the preview matches your expectation.

Preview first. Convert second. That is the key safety rule of this workflow.

## Step-by-step guidance

### Step 1: Choose the file

Select the survey file from disk or from project-local source material if your
project already uses `sourcedata/`.

Good first example:

- `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx`

### Step 2: Confirm the participant ID column

PRISM tries to detect the ID column automatically.

Always verify it. A wrong ID column is the fastest way to create a broken import
that looks fine at first glance but fails later in validation, participant
alignment, or scoring.

### Step 3: Set the session value

The session value becomes part of the project structure and filenames.

Use a stable label such as:

- `1`
- `2`
- `baseline`
- `followup`

Choose a value that matches the real study design instead of inventing one just
to get through the form.

### Step 4: Review advanced fields only when needed

For some datasets you may need to review:

- run logic
- language
- questionnaire version
- ID mapping

If the simple path works, keep the first import simple and come back to advanced
controls later.

### Step 5: Use Preview

Preview is the dry run. Use it every time you work with a new dataset or a new
import shape.

Preview should help you confirm:

- the file was read correctly
- the ID column is correct
- the session and run logic look right
- the output file structure makes sense
- the task or version assignment is what you intended

### Step 6: Convert

Convert only after the preview looks correct.

The converter writes survey files into the project structure and may also trigger
template follow-up work if PRISM needs more project-local template detail.

## Example workflow

Example source:

- `wellbeing.xlsx` with one participant ID column and several item columns such
	as `WB01` to `WB05`

Example path:

1. Load the project `wellbeing_study`.
2. Open **Converter → Survey**.
3. Select `wellbeing.xlsx`.
4. Confirm `participant_id` or the detected equivalent.
5. Set session `baseline`.
6. Run **Preview**.
7. Confirm that the subject-level output matches the expected survey structure.
8. Run **Convert**.

Expected result:

- survey files written into subject folders
- a project-local template situation that may need review in Template Editor
- a dataset that is ready for validation

## Template follow-up after import

Survey import and template editing are tightly connected.

Sometimes the import creates or copies a project-local template that still needs
administration details such as:

- language
- collection method
- version context
- technical details of how the questionnaire was administered

When that happens, the next step is [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md), not
manual JSON editing by guesswork.

## If you need to create a template first

Use the canonical workbook at:

- `official/create_new_survey/survey_import_template.xlsx`

Practical workbook flow:

1. Fill `General` for instrument and version context.
2. Fill `Items` for item texts and scale definitions.
3. Use `Variants` only when you truly need multi-version behavior.
4. Check the built-in `Help` sheet when a column meaning is unclear.

For schema semantics, see [specs/survey.md](specs/survey.md).

## Questionnaire versions

Some instruments have more than one explicit version. When PRISM asks you to
choose a version, stop and confirm it instead of guessing. A wrong version choice
can produce an internally consistent import that still represents the wrong
questionnaire form.

## Common mistakes

- converting before checking Preview
- selecting the wrong ID column
- forgetting to load the correct project first
- mixing different sessions into one import without noticing
- assuming the copied project template is already complete enough for publication

## What to do after survey import

The normal next steps are:

1. review the template if PRISM indicates missing template detail
2. run validation
3. create scoring recipes if the survey should produce derived scores

## Related pages

- [CONVERTER.md](CONVERTER.md)
- [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)
- [VALIDATOR.md](VALIDATOR.md)
- [RECIPE_BUILDER.md](RECIPE_BUILDER.md)
- [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md)