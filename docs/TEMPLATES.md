# Survey Templates

Use this page when you need the reference model for survey templates rather than
the step-by-step editing workflow.

For the interactive editing path, use [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md).

## What a survey template is

A survey template is a JSON description of a questionnaire.

It tells PRISM:

- what the instrument is
- how items are named and described
- which response options belong to each item
- how the questionnaire was administered in the project

## Official template vs project copy

The same conceptual template can appear in two roles:

- **official or global template**: the canonical reference version
- **project-local copy**: the version your project actually uses and completes

Common locations:

- `official/library/survey/`
- `code/library/survey/`

For everyday project work, the important path is the project-local copy.

## The two most important blocks

### `Study`

`Study` describes the instrument itself.

Typical fields include:

- `TaskName`
- `OriginalName`
- `ShortName`
- `Authors`
- `DOI`
- `LicenseID`
- `ItemCount`

For project-local copies, `TaskName` matters especially because it connects the
template to filenames and task usage in the dataset.

### `Technical`

`Technical` describes how the survey was actually run in the project.

Common fields include:

- `StimulusType`
- `FileFormat`
- `Language`
- `Respondent`
- `AdministrationMethod`
- `SoftwarePlatform`
- `SoftwareVersion`

This is often the block that still needs project-specific completion after an
import or template copy.

## Item definitions

Each item usually appears as its own key such as `PSS01` or `ADS03`.

An item commonly contains:

- `Description`
- `Levels` for named response options
- or `MinValue` and `MaxValue` for numeric scales

Use `Levels` when the answer options need explicit labels.
Use `MinValue` and `MaxValue` when the item is numeric and bounded.

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

## How to use this reference page

This page is most useful when you need to answer questions such as:

- what belongs in `Study` vs `Technical`
- what the project-local copy is supposed to hold
- how item-level metadata is represented

For actual editing, switch back to [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md).

## Common mistakes

- treating the official library file as the normal project editing target
- leaving `Technical` incomplete after import
- changing `TaskName` without considering the dataset naming that depends on it
- assuming item columns are self-explanatory without descriptions or levels

## Related pages

- [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)
- [SURVEY_IMPORT.md](SURVEY_IMPORT.md)
- [specs/survey](specs/survey)