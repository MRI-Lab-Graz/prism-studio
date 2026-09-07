# Design: New "Survey Authoring" tutorial series

Date: 2026-09-07
Status: Approved, pending implementation plan

## Problem

Survey/questionnaire authoring is, per the user, "for most users the most
important part" of PRISM Studio — but the material that covers it is
scattered across reference docs written for lookup, not learning:
`EXCEL_TEMPLATE_BASICS.md`, `EXCEL_TEMPLATE_ADVANCED.md`,
`docs/studio/template_editor.md`, `docs/studio/survey_generator.md`,
`docs/studio/survey_customizer.md`, `docs/LIMESURVEY_INTEGRATION.md`,
`docs/TEMPLATES.md`. None of them is a guided, hands-on, chapter-by-chapter
walkthrough the way `TUTORIAL_BEGINNER_*` is for the core BIDS-project
workflow. The existing beginner tutorial's own survey chapter
(`TUTORIAL_BEGINNER_3_SURVEY_IMPORT.md`) explicitly defers authoring detail
("there's no need to repeat it here") and never touches the Template
Editor's own create/import UI, multi-language/multi-variant authoring, or
LimeSurvey export at all.

This spec defines a new, standalone, multi-chapter tutorial — same family
as `TUTORIAL_BEGINNER_*` and `TUTORIAL_FILE_MANAGEMENT.md` — that fills that
gap: authoring a questionnaire from a blank Excel template through to a
validated, LimeSurvey-exported, multi-language, multi-version template.

## Research basis

A full inventory of the survey-authoring code/docs surface was done before
this design (Excel template parser `app/src/converters/excel_to_survey.py`,
Template Editor `app/static/js/template-editor.js` +
`tools_template_editor_blueprint.py`, LimeSurvey exporter
`app/src/limesurvey_exporter.py` + importer `src/converters/limesurvey.py`,
template validation `app/src/template_validator.py` +
`app/src/library_validator.py`, and every existing doc touching this
territory). Findings that shape this design:

- **Official vs. project-local templates** is a load-bearing concept
  (`official/library/<modality>/` vs. `code/library/<modality>/`, Template
  Editor auto-forks on save) that's easy to under-explain and isn't given
  its own explicit treatment anywhere — this tutorial gives it one early.
- **LimeSurvey export is bidirectional**, but export
  (`limesurvey_exporter.py`, most actively maintained survey file in the
  repo) is the more built-out, more clearly "central" direction; the full
  round trip is already documented end-to-end in
  `LIMESURVEY_INTEGRATION.md` (641 lines) — confirmed by the user's answer
  to defer re-import detail there rather than duplicate it.
- **Scoring/Recipes** is tightly coupled to survey templates but already
  has a full chapter in the beginner tutorial (`TUTORIAL_BEGINNER_4_RECIPE.md`)
  — confirmed by the user's answer to close with a pointer, not a chapter.
- **Multi-version (Variants) authoring** is untouched by any existing
  tutorial-style doc — only the terse `EXCEL_TEMPLATE_ADVANCED.md` reference
  covers it.
- `docs/LIMESURVEY_VERSION_DIFFERENCES.md` documents an export bug that
  appears already fixed in current code (verified `aid_counter` usage in
  `limesurvey_exporter.py`) — this tutorial must not cite its "known
  broken" language as current.

## Scope decisions (confirmed with user)

1. **Standalone**, not a continuation of the Beginner tutorial. Own
   scenario, own scratch project. A reader who has never opened the
   Beginner tutorial can complete this one.
2. **LimeSurvey chapter covers Export + Customizer only**, ending in a real
   `.lss` file, then a pointer to `LIMESURVEY_INTEGRATION.md` for the
   collect-data-and-reimport half of the round trip. No LimeSurvey instance
   required to complete this tutorial.
3. **Scoring/Recipes gets a closing "What's next" pointer only**, no
   dedicated chapter — avoids duplicating `TUTORIAL_BEGINNER_4_RECIPE.md`.
4. **No persona-picker mechanic** (the `data-persona` localStorage gimmick
   used by `TUTORIAL_BEGINNER.md`). Matches `TUTORIAL_FILE_MANAGEMENT.md`
   precedent; this series doesn't need it.

## The running scenario

A fictional exercise-recovery study, **"Recovery Check-In"** — invented
fresh rather than continuing `wellbeing_study` (Beginner tutorial) or
building the tutorial's hands-on steps directly on top of
`examples/wellbeing_multi_demo` (an existing, already-finished multi-version
fixture, which gets one "see also" mention in Chapter 5 instead). Chosen so
every chapter has a genuine reason to exist rather than a contrived one:

- **Task name**: `recovery`
- **Full version** (10 items): evening, post-training-session check-in —
  mood, soreness, sleep quality, motivation, stress, fatigue, appetite,
  hydration, satisfaction (all 5-point Likert), plus pain intensity (0–100
  VAS).
- **Short version** (5 items): same-day quick follow-up — mood, soreness,
  pain intensity (VAS), fatigue, sleep quality. A true subset of the Full
  item set (via `ApplicableVersions`), not a separately-written form.
- **Languages**: English (default) + German, added in Chapter 4 (the Excel
  workbook and the Template Editor both start English-only in Chapters 2–3).
- **Scratch project**: `recovery_check_in_demo`, created fresh in Chapter 1
  the same way `TUTORIAL_FILE_MANAGEMENT.md` does — self-contained, doesn't
  touch any other project, deletable when done.
- **Filenames that recur across chapters** (fix these once, reuse
  verbatim): the reader's own filled copy of
  `official/create_new_survey/survey_import_template.xlsx` is saved as
  `recovery_survey_template.xlsx`; the resulting project-local template
  lands at `code/library/survey/survey-recovery.json` (per Template
  Editor's documented save behavior); the LimeSurvey export in Chapter 6 is
  named `recovery_full_en_de.lss`.

## Chapter structure

Same file-per-chapter convention as `TUTORIAL_BEGINNER_*`:
`TUTORIAL_SURVEY.md` (landing) + `TUTORIAL_SURVEY_1_CONCEPTS.md` through
`TUTORIAL_SURVEY_7_VALIDATION.md`. Same per-chapter shape as
`TUTORIAL_FILE_MANAGEMENT.md`: time/outcome header, one mermaid
flowchart, numbered hands-on steps, `{note}`/`{warning}`/`{important}`
admonitions where a real gotcha exists (drawn from the research above, not
invented), "What you just did" + "What's next" closing sections.

### Landing page — `TUTORIAL_SURVEY.md`, titled "Author a Survey"

- 2–3 sentence recap of Beginner-tutorial concepts assumed but not
  required in depth: a PRISM project has a `sub-*/ses-*/<modality>/`
  structure, and survey response data eventually lands there — with a
  link to `TUTORIAL_BEGINNER.md` for anyone who wants that fuller grounding
  first, but not a hard prerequisite.
- Who this is for / prerequisites (PRISM Studio installed; no LimeSurvey
  instance required).
- The scenario, in 1 paragraph.
- Chapter card grid (7 cards, same `prism-chapter-grid` CSS as the beginner
  landing page), each with outcome + time estimate.
- Total time estimate: sum of the per-chapter estimates below (~2.5–3
  hours), stated up front like `TUTORIAL_BEGINNER.md` does.

### Chapter 1 — Survey Concepts You Need First (~15 min)

- The Beginner-tutorial recap (BIDS `sub-*/ses-*/survey/` layout,
  `participant_id`), kept short — this chapter's real job is the next
  point.
- **Official vs. project-local templates**: `official/library/survey/`
  (shared instrument definitions) vs. `code/library/survey/` (this
  project's administration instance); Template Editor forks on save;
  Delete is hidden for anything not project-local. Explicit early callout
  per the research finding that this is otherwise under-explained.
- What a template *is*: a JSON file matching `survey.schema.json`, and the
  Excel workbook is one authoring format for producing it — not the only
  one, and not the format itself.
- Create the `recovery_check_in_demo` scratch project.

### Chapter 2 — Prepare a New Questionnaire in Excel (~30 min)

- Tutorial-ized walkthrough of `EXCEL_TEMPLATE_BASICS.md`'s ground, scoped
  to the Recovery Check-In Full version, English only:
  `official/create_new_survey/survey_import_template.xlsx` → save as
  `recovery_survey_template.xlsx` → fill `Items` (10 rows: `ItemID`,
  `Group`, `Description_en`, `Scale_en` or `MinValue`/`MaxValue` for the
  VAS item, `DataType`) → fill `General` (`OriginalName_en`, `LicenseID`,
  `ShortName`, `Authors`, `I18nLanguages: en`, `I18nDefaultLanguage: en`).
- Import into Template Editor, first **Validate**, first **Save** →
  confirms it lands at `code/library/survey/survey-recovery.json`.
- One `{warning}` on the real documented gotcha: placeholder text like
  `n/a` silently becomes blank via pandas.

### Chapter 3 — Edit and Refine in the Template Editor (~25 min)

- Going beyond the Excel import, in the online tool itself: Top-level
  panel (`Study`/`Technical`), Selected Item panel, Tool Properties,
  editing one item's wording directly in the editor (not by re-importing
  Excel).
- **Bulk Edit Items** panel — apply one change across several items at
  once (e.g. a shared response-scale tweak).
- **Preview** tab → Word/.docx export, with layout options (headers, item
  codes, randomize order) — note the `python-docx` dependency.

### Chapter 4 — Languages and Scales (~25 min)

- Add German: `Description_de`/`Scale_de` columns (Excel path) *or* the
  in-editor language bar + per-item "add language" controls — cover both
  since the doc set does.
- The language-consistency warning: what it means when `Technical.Language`
  doesn't match languages actually present in item content.
- Scales: Likert (`Levels` map) vs. VAS (`ScaleType: vas`, renders as a
  slider) for the pain-intensity item; `MinValue`/`MaxValue`/`AllowedValues`.
- **Copy Style** to reuse an existing item's scale/type on a new item,
  framed accurately as copy-based reuse, not a shared reference.

### Chapter 5 — Multiple Versions (Variants) (~25 min)

- Add the `Variants` sheet to `recovery_survey_template.xlsx`: define the
  Short version, tag the 5 shared items via `ApplicableVersions`, produce
  `Study.VariantDefinitions` + per-item `VariantScales`.
- Re-import/update in Template Editor, confirm the variant selector shows
  both versions.
- One paragraph on run-aware/repeated-administration designs (`Run` number
  per template, `SessionHint`/`RunHint`) — flagged by research as an easily
  missed, related concept — with a pointer to `LIMESURVEY_INTEGRATION.md`
  and `docs/specs/survey.md` for depth rather than full treatment here.
- `{note}` pointing to `examples/wellbeing_multi_demo` as a finished,
  already-in-the-repo example of a multi-version template, for anyone who
  wants to see a more complex real one.

### Chapter 6 — Export to LimeSurvey (~30 min)

- Survey Export page: pick the `recovery` template + version(s), Base/
  Export Languages (en + de), LS version, **Quick Export (.lss)** vs.
  **Customize & Export**.
- Survey Customizer, hands-on: group reordering, per-question LS settings
  (type override, mandatory, relevance, hidden), matrix grouping (the 9
  Likert items), welcome/end text, **Export Survey** → `recovery_full_en_de.lss`.
- Closing section: what happens next (import `.lss` into LimeSurvey,
  collect responses, export `.lsa`, import back via Converter → Survey) is
  explained conceptually in 1 paragraph with a clear pointer to
  `LIMESURVEY_INTEGRATION.md` for the full walkthrough — per the confirmed
  scope decision, not duplicated here.

### Chapter 7 — Validating Your Template (~15 min)

- Template Editor's in-browser **Validate** button: schema errors vs.
  i18n/language-consistency warnings as two distinct result arrays —
  correcting the common assumption that Preview alone is validation.
- `TemplateValidator` CLI (`prism-validator --validate-templates`) for
  validating a whole library outside the browser.
- One-line mention of `library_validator.py`'s library-wide uniqueness
  check, for anyone maintaining a shared template library across projects.

### Closing "What's next" (on the landing page and/or Chapter 7)

- [Recipes](RECIPES.md) / [`TUTORIAL_BEGINNER_4_RECIPE.md`](TUTORIAL_BEGINNER_4_RECIPE.md)
  — score the responses once you have them.
- [Converter → Survey](studio/converter_survey.md) — import real response
  data against this template.
- [LimeSurvey Integration](LIMESURVEY_INTEGRATION.md) — the full round trip.
- [Validator](studio/validator.md) — dataset-level validation once data
  exists.

## File layout and wiring

New files (8), landing page titled "Author a Survey":

```
docs/TUTORIAL_SURVEY.md
docs/TUTORIAL_SURVEY_1_CONCEPTS.md
docs/TUTORIAL_SURVEY_2_EXCEL_TEMPLATE.md
docs/TUTORIAL_SURVEY_3_TEMPLATE_EDITOR.md
docs/TUTORIAL_SURVEY_4_LANGUAGES_SCALES.md
docs/TUTORIAL_SURVEY_5_VARIANTS.md
docs/TUTORIAL_SURVEY_6_LIMESURVEY_EXPORT.md
docs/TUTORIAL_SURVEY_7_VALIDATION.md
```

`docs/index.rst`'s existing `:caption: Tutorial` toctree currently lists
all 6 Beginner chapters flatly, plus `TUTORIAL_FILE_MANAGEMENT` — 7 entries
under one caption, and about to become 15 if the 7 new chapters were just
appended the same way. Revised during design review to use the same
collapsible-nested-toctree mechanism `docs/studio/index.md` already uses
for "Studio Guide" (a hidden `` {toctree} `` block inside the landing page
itself, with only the landing page referenced from `docs/index.rst`) —
Sphinx/Furo renders that as a single sidebar entry with a chevron that
expands to the nested pages, rather than flattening everything:

- Add a hidden `` {toctree} `` block to `TUTORIAL_BEGINNER.md` listing its
  6 chapters (content unchanged otherwise), and drop those 6 from
  `docs/index.rst`'s Tutorial toctree, leaving just `TUTORIAL_BEGINNER`.
- Add the same to the new `TUTORIAL_SURVEY.md`, listing its 7 chapters;
  `docs/index.rst`'s Tutorial toctree gets just `TUTORIAL_SURVEY` added.
- `TUTORIAL_FILE_MANAGEMENT` stays a flat single entry, unchanged — one
  page has nothing to collapse.

Net result under the one `:caption: Tutorial`: three sidebar rows —
"Getting Started — Your First PRISM Project" (collapsible, 6 chapters),
"File Management: Bulk Rename, Reorganize, and Clean Up" (flat), "Author a
Survey" (collapsible, 7 chapters) — matching the grouping the user asked
for without a second caption.

Modified existing files: `docs/index.rst` (toctree restructure above),
`TUTORIAL_BEGINNER.md` (adds the hidden nested toctree only — no content
change), plus backlinks added to existing docs' "What's next"/related
sections, same pattern used when `TUTORIAL_FILE_MANAGEMENT.md` was added:
`EXCEL_TEMPLATE_BASICS.md`, `EXCEL_TEMPLATE_ADVANCED.md`,
`docs/studio/template_editor.md`, `docs/studio/survey_generator.md`,
`docs/studio/survey_customizer.md`.

## Explicitly out of scope

- No new example/fixture files under `examples/` — the reader fills the
  existing blank `official/create_new_survey/survey_import_template.xlsx`
  themselves; inline markdown tables (as `TUTORIAL_BEGINNER_6` and
  `TUTORIAL_FILE_MANAGEMENT` already do) supply any other small sample data.
- No new screenshots captured for this tutorial. Where a screenshot adds
  real value, reuse an existing whole-page one already in
  `docs/_static/screenshots/` (`prism-studio-template-editor.png`,
  `prism-studio-survey-export.png`) — no new per-step/per-state captures.
- No LimeSurvey collect-and-reimport chapter (scope decision above).
- No dedicated scoring/Recipes chapter (scope decision above).
- No fix/update to `docs/LIMESURVEY_VERSION_DIFFERENCES.md`'s stale
  "known broken" language — flagged for a separate, unrelated cleanup task.
- No persona-picker mechanic.

## Verification

Documentation-only change; no application code touched. Verification is:

1. Every UI label, button ID, route, and file path named in each chapter
   must be confirmed against current code/templates before being written
   (same standard applied to `TUTORIAL_FILE_MANAGEMENT.md` — several of
   its details were corrected after checking the live template rather than
   trusting the existing reference docs).
2. `python3 -m sphinx -b html docs <tmp-dir> -q` must complete with zero
   warnings referencing any new file (broken cross-references, missing
   images, orphaned toctree entries).
3. Spot-check that no chapter duplicates ground already covered by
   `TUTORIAL_BEGINNER_3_SURVEY_IMPORT.md` without adding something new.
4. Render the built HTML sidebar and confirm the "Tutorial" caption shows
   exactly three rows (Beginner, File Management, Author a Survey), with
   the two multi-chapter ones collapsed by default and expandable —
   matching `docs/studio/index.md`'s existing "Studio Guide" behavior.
