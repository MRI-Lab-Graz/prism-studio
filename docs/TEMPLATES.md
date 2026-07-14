# Survey Templates

The reference model for survey templates, rather than the step-by-step editing
workflow — for interactive editing, use [Template Editor](studio/template_editor.md).
Useful when you need to answer questions like "what belongs in `Study` vs
`Technical`?" or "how is item-level metadata represented?"

## What a template is

A survey template is a JSON description of a questionnaire: what the instrument is,
how items are named/described, which response options belong to each item, and how
the questionnaire was administered in the project.

The same conceptual template appears in two roles: the **official/global template**
(canonical reference, `official/library/survey/`) and the **project-local copy**
(what your project actually uses and completes, `code/library/survey/`). For
everyday project work, the project-local copy is what matters.

## `Study` and `Technical` blocks

- **`Study`** describes the instrument itself: `TaskName`, `OriginalName`,
  `ShortName`, `Authors`, `DOI`, `LicenseID`, `ItemCount`. For project-local copies,
  `TaskName` matters especially — it connects the template to filenames and task
  usage in the dataset.
- **`Technical`** describes how the survey was actually run in *this* project:
  `StimulusType`, `FileFormat`, `Language`, `Respondent`, `AdministrationMethod`,
  `SoftwarePlatform`, `SoftwareVersion`. Often the block that still needs
  project-specific completion after an import or template copy.

## Item definitions and example

Each item is its own key (e.g. `PSS01`, `ADS03`), commonly containing a
`Description`, plus either `Levels` (named response options) or `MinValue`/
`MaxValue` (numeric bounded scales).

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

## Common mistakes

Treating the official library file as the normal project editing target; leaving
`Technical` incomplete after import; changing `TaskName` without considering the
dataset naming that depends on it; assuming item columns are self-explanatory
without descriptions or levels.

## What's next

- [Template Editor](studio/template_editor.md)
- [Survey Import](studio/converter_survey.md)
- [specs/survey](specs/survey)
