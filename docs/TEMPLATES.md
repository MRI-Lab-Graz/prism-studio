# Survey Templates

This page explains what a survey template is and what the main parts of the template mean.

For editing steps in PRISM Studio, use the Template Editor guide instead.

## What a template is

A survey template is a JSON file that describes a questionnaire.

It tells PRISM:

- what the instrument is
- what the items are called
- which response options belong to each item
- how the survey was administered in the project

## Two common contexts

The same template structure appears in two places:

- official or global template
- project-local template copy

The global template is the reference version.

The project-local copy is the version your project actually uses.

## Typical locations

Common survey template locations are:

- `official/library/survey/`
- `code/library/survey/`

For everyday project work, the important folder is `code/library/survey/`.

## The two main blocks

The two most important parts are:

- `Study`
- `Technical`

`Study` describes the instrument itself.

`Technical` describes how the survey was actually collected in your project.

## `Study`

The `Study` block usually contains fields such as:

- `TaskName`
- `OriginalName`
- `ShortName`
- `Authors`
- `DOI`
- `LicenseID`
- `ItemCount`

For project-local copies, `TaskName` is especially important because it connects the template to filenames and task labels.

## `Technical`

The `Technical` block records project-level administration details such as:

- `StimulusType`
- `FileFormat`
- `Language`
- `Respondent`
- `AdministrationMethod`
- `SoftwarePlatform`
- `SoftwareVersion`

This is the part most users need to complete after an import.

## Item definitions

Each item usually appears as a top-level key such as `PSS01` or `ADS03`.

An item normally contains:

- `Description`
- `Levels` for discrete choices
- or `MinValue` and `MaxValue` for numeric ranges

Use `Levels` for named answer options.

Use `MinValue` and `MaxValue` for numeric scales.

## Minimal example

```json
{
  "Technical": {
    "StimulusType": "Questionnaire",
    "FileFormat": "tsv",
    "Language": "en",
    "Respondent": "self"
  },
  "Study": {
    "TaskName": "mood",
    "OriginalName": "Mood Check"
  },
  "MOOD01": {
    "Description": "How do you feel right now?"
  }
}
```

## Beginner advice

Keep the first template simple.

Make sure the task name, item texts, and administration details are correct before you worry about advanced metadata.

## Related pages

- Template editing workflow: [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)
- Survey import: [SURVEY_IMPORT.md](SURVEY_IMPORT.md)
- Survey library overview: [SURVEY_LIBRARY.md](SURVEY_LIBRARY.md)