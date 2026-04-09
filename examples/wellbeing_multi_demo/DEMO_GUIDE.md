# Multi-Variant Survey Demo: Wellbeing

This guide shows how to import data for a multi-variant questionnaire using the current PRISM behavior:

- Variant choice is template-driven (`Study.Version`)
- Output naming uses `acq-<version>` for multi-variant templates
- The Survey Version selector appears only when a multi-version survey is detected
- Session/run mapping is only required when the uploaded file contains multiple observed contexts

## Variants in This Demo

Template: `code/library/survey/survey-wellbeing-multi.json`

| Variant ID | Items | Scale | Range |
|---|---|---|---|
| `10-likert` | WB01-WB10 | Likert | 1-5 |
| `7-likert` | WB01-WB07 | Likert | 1-5 |
| `10-vas` | WB01-WB10 | VAS | 0-100 |

## Prerequisites

- PRISM Studio is running
- Project `wellbeing_multi_demo` is open
- Template file exists at `code/library/survey/survey-wellbeing-multi.json`
- Raw files are in `code/rawdata/`

## Where To Set The Version

Set the active variant in template `Study.Version` before conversion.

Example:

```json
{
  "Study": {
    "TaskName": "wellbeing-multi",
    "Versions": ["10-likert", "7-likert", "10-vas"],
    "Version": "10-likert"
  }
}
```

For multi-variant templates, conversion emits filenames like:

`sub-P01_ses-01_task-wellbeing-multi_acq-10-likert_survey.tsv`

## Scenario 1: Single Version For Whole Study

File: `code/rawdata/scenario1_single_version.tsv`

1. Set `Study.Version` to `10-likert`.
2. Convert the file in Survey Converter.
3. Validate output.

Expected: files carry `acq-10-likert` and enforce WB01-WB10 with range 1-5.

## Scenario 2: Different Versions Across Sessions

File: `code/rawdata/scenario2_session_versions.tsv`

Recommended import approach:

1. Import session-1 rows with `Study.Version = 10-likert`.
2. Import session-2 rows with `Study.Version = 7-likert`.
3. Validate output.

Expected:

- session-1 files use `acq-10-likert`
- session-2 files use `acq-7-likert`
- validator applies variant-appropriate item and range rules

## Scenario 3: Different Versions Across Runs

Files:

- `code/rawdata/scenario3_run01_10likert.tsv`
- `code/rawdata/scenario3_run02_10vas.tsv`

Steps:

1. Set `Study.Version = 10-likert` and import run-01.
2. Set `Study.Version = 10-vas` and import run-02.
3. Validate output.

Expected:

- run-01 files use `acq-10-likert` (range 1-5)
- run-02 files use `acq-10-vas` (range 0-100)

## Scenario 4: One File With Session And Run Mapping

File: `code/rawdata/scenario4_contextual_session_run_versions.csv`

Use this file to test the new Survey Version selector with one upload.

Recommended converter settings:

1. Upload the CSV in Survey Converter.
2. Set `ID column = Code`.
3. Set `Session column = session`.
4. Set `Run column = run`.
5. Keep the survey filter empty so `wellbeing-multi` is auto-detected.

Expected selector mapping:

| Session | Run | Expected version |
|---|---:|---|
| `ses-pre` | 1 | `10-likert` |
| `ses-post` | 1 | `7-likert` |
| `ses-pre` | 2 | `10-vas` |
| `ses-post` | 2 | `10-likert` |

Why this file is useful:

- `ses-pre`, run `1` contains full 10-item Likert values (`1-5`)
- `ses-post`, run `1` leaves `WBM08-WBM10` empty so the 7-item short form is the right choice
- `ses-pre`, run `2` uses `0-100` values so it should map to `10-vas`
- `ses-post`, run `2` goes back to a full 10-item Likert form to prove that run-only mapping is not enough

Expected outcome:

- The wizard should detect `wellbeing-multi` as multi-version
- The wizard should render contextual selectors because the file contains both multiple sessions and multiple runs
- Preview/convert should emit different `acq-*` labels per context after you choose the matching versions

## Version Resolution Priority

PRISM resolves variant in this order:

1. Filename `acq` entity (highest)
2. Template `Study.Version` (fallback)

## Troubleshooting

- "Template version mismatch": `Study.Version` is not listed in `Study.Versions`.
- Missing `acq` in output: template is not treated as multi-variant (check `Study.Versions`).
- VAS values flagged as Likert: wrong version selected during conversion.
- Extra missing items for `WBM08-WBM10` in `ses-post` run `1`: the short-form context was not set to `7-likert`.

## See Also

- [Survey Versioning](../../docs/SURVEY_VERSION_PLAN.md)
- [Schema Versioning](../../docs/SCHEMA_VERSIONING.md)
- [Survey Library](../../docs/SURVEY_LIBRARY.md)
- [Converter](../../docs/CONVERTER.md)
