# Survey Customizer

Groups, orders, and configures the presentation of templates before exporting them
to LimeSurvey. Reached only via **Customize & Export** on
[Survey Export](survey_generator.md) — your selected templates are passed through
the browser session, so there's no way to load this page cold; if you land here
without a selection, you'll see "No survey data found" pointing back to Survey
Export.

## Layout

- **Groups panel** (left) — drag-to-reorder question groups, **+ Add new group**.
- **Questions panel** (right) — per-group question list, with a language switcher if
  multiple languages are set.

## Export Settings

- **Survey Name** (required), **Target Tool** (LimeSurvey only today), **Languages**
  (read-only, set back on Survey Export), **Export Format** (`.lss`), **LimeSurvey
  Version** (5.x/6.x or 3.x/4.x), **Base Language**.
- **Group questions with identical options into matrices** / **Global matrix
  grouping** checkboxes.
- **Save templates to project library** — optional, only shown with an active
  project; copies the source templates into `code/library/survey/`.

## LimeSurvey Survey Settings (optional accordion)

- **Text & Messages** — Welcome Message (HTML + template picker: Standard/
  Academic/Brief), End Message (HTML + templates, plus a Redirect Notice option), End
  URL, End URL Description.
- **Data Policy / Ethics** — Off / Show with checkbox / Show inline, template picker
  (Standard Ethics Consent, GDPR, Anonymous, Longitudinal, Minimal), Policy Checkbox
  Label, Policy Notice, Policy Error Message.
- **Presentation & Navigation** — Show Welcome Screen, Show Progress Bar, Allow
  Backward Navigation, Navigation Delay, Question Index mode, Show Group Info, Show
  Question Number/Code, Show "No Answer", Show Question Count, On-Screen Keyboard,
  Print Answers, Auto-load End URL, Public Statistics, Public Graphs.

## Finishing up

Action bar: **Reset Changes**, **Preview Questionnaire** (modal with a language
selector and Print/PDF), **Export Word**, and **Export Survey** (the primary action —
produces the `.lss` file with your grouping/settings applied).

## What's next

- [Survey Export](survey_generator.md)
- [Template Editor](template_editor.md) — edit the underlying templates themselves,
  not just their export grouping/presentation
