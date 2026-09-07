# Chapter 7: Validating Your Template

**Time:** ~15 minutes | **Outcome:** a clear picture of exactly what
"validated" means for a template — schema correctness versus translation
completeness — and how to check an entire library at once instead of one
template at a time in the browser.

```{mermaid}
flowchart LR
    W["📄 survey-recovery.json"]
    W --> V["✅ Template Editor Validate<br/>schema errors + i18n warnings"]
    W --> C["💻 prism-validator --validate-templates<br/>whole-library"]
    V --> R["🎯 confidently correct template"]
    C --> R
```

## Preview is not validation

It's easy to assume Chapter 3's Preview tab already tells you a template is
correct — after all, it renders every item, radio buttons, slider, and all.
It doesn't. Preview shows how the template *renders* for a respondent; it
never touches the schema rules underneath. A template can preview perfectly
and still be missing a required `Study` field, or have an item whose
`DataType` doesn't match its `Levels` map — Preview has no reason to notice
either, because rendering and schema-checking are different operations over
the same JSON.

**Validate** is the actual check, and it has been sitting in
the toolbar since Chapter 2 — you've clicked it at the end of nearly every
chapter in this series without this chapter yet explaining what it's doing.
It's time to open that up in full.

## Two kinds of Validate result

Chapter 4 already surfaced half of this when adding German turned up a
language-consistency warning. Here's the complete picture: the Template
Editor's `/api/template-editor/validate` endpoint returns **two genuinely
separate arrays**, not one merged list.

**Schema `errors`** — structural problems: missing required fields, wrong
types, a `Study` block that doesn't validate, an item missing its
`Description`. These are the same rules `prism-validator --validate-templates`
enforces from the command line (next section), and they're what blocks
**Save to Project**. Internally these come back tagged by error type:
`json_parse` (the file isn't valid JSON at all), `missing_study` (no `Study`
block present), `study_validation` (the `Study` block is present but fails
its own rules), and `item_validation` (a specific item fails its rules).

**`language_warnings`** — content-completeness checks, tagged
`i18n_validation`. This is the array Chapter 4's "Language 'de' is missing
from 1 question(s)..." message came from: the template is structurally
valid either way, but a translation looks incomplete. `i18n_validation`
warnings never block saving — they're a nudge to go fill in a field, not a
sign that anything is broken.

Put plainly: `errors` is schema, `language_warnings` is i18n, and a template
can have zero of one and several of the other in any combination.

## Validate a whole library from the command line

Clicking Validate in the browser checks one template at a time. Once you
have more than a couple of templates — or want validation to run
automatically in CI rather than by hand — `prism-validator` checks an entire
library directory in one pass:

```bash
prism-validator --validate-templates code/library/survey
```

Run from your project root, this walks every template file in that
directory and prints a report:

```text
======================================================================
Template Validation Report: /code/library/survey
======================================================================
Total files: 1 | Valid: 1 | With errors: 0 | Total errors: 0
```

A clean `survey-recovery.json` produces exactly this — zero errors, one
valid file. If it didn't, the report format matches what you'd see for any
failing template, for example:

```text
======================================================================
Template Validation Report: /code/library/survey
======================================================================
Total files: 1 | Valid: 0 | With errors: 1 | Total errors: 2

ERRORS (2):
  [ERROR] survey-recovery.json: Study.OriginalName: Original name of the instrument is required
  [ERROR] survey-recovery.json (rec_pain): Item description is required
    → Missing or empty 'Description' field
```

This is useful for exactly the situations the browser doesn't cover well:
running validation in CI before a template library ships, checking every
template in a shared library at once before handing it to someone else, or
validating several templates in one command instead of opening each one in
the Template Editor individually.

## If you maintain a shared library

One thing worth knowing exists, even though it's out of scope for a
single-template project like this tutorial's: `library_validator.py`'s
uniqueness check additionally flags duplicate variable names and redundant
item definitions *across an entire library*, not just within one template.
That only starts to matter once you have more than one template that might
accidentally reuse the same item ID or variable name — not a concern for
`survey-recovery.json` on its own, but worth knowing about before you add a
second template alongside it.

## What you just did

You closed out the full Survey tutorial series. Across seven chapters you:

1. **Chapter 1** — learned the official-vs-project-local template split and
   created the `recovery_check_in_demo` scratch project.
2. **Chapter 2** — filled in all 10 Recovery Check-In Full-version items in
   Excel and imported them into `code/library/survey/survey-recovery.json`.
3. **Chapter 3** — edited that template directly in the Template Editor:
   single-item wording, a Bulk Edit change across all nine Likert items, and
   Study/Technical metadata, then exported a paper-pencil Word version.
4. **Chapter 4** — added German alongside English, saw Validate report an
   incomplete translation as a warning rather than an error, and understood
   why `rec_pain`'s VAS scale is fundamentally different from the other
   items' Likert scale.
5. **Chapter 5** — split the template into `full` and `short` versions on
   the `Variants` sheet and gave `rec_pain` an explicit `ScaleType: vas`
   override, turning its Preview into an actual slider.
6. **Chapter 6** — exported the bilingual, ten-item `full` version through
   the Survey Customizer into a real, importable `recovery_full_en_de.lss`.
7. **Chapter 7** (this chapter) — learned exactly what Validate checks
   (schema `errors` vs. `i18n_validation` `language_warnings`), and how to
   validate a whole template library at once with `prism-validator
   --validate-templates`.

You now have a bilingual, two-version, schema-valid `survey-recovery.json`
that also exports cleanly to LimeSurvey — and you know how to keep it that
way as it grows.

## What's next

This tutorial series stops at the template — a correct, exportable
definition of what to ask. From here:

- [Recipes](RECIPES.md) and
  [Prepare a Recipe](TUTORIAL_BEGINNER_4_RECIPE.md) — score the responses
  once you actually have them
- [Converter → Survey](studio/converter_survey.md) — import real response
  data against this template
- [LimeSurvey Integration](LIMESURVEY_INTEGRATION.md) — the full round trip:
  import the `.lss`, collect data, bring it back into PRISM
- [Validator](studio/validator.md) — dataset-level validation, once you have
  actual response data to check
