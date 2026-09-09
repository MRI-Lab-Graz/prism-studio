# Survey Authoring Tutorial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a new, standalone, 7-chapter "Author a Survey" tutorial series under `docs/`, and restructure the Tutorial sidebar so it and the existing Beginner tutorial each collapse to one row instead of flattening every chapter into the top-level list.

**Architecture:** This is a documentation-only change — no application code is touched. Each task produces one Markdown file (or a small, self-contained edit to existing ones) following the exact structural convention already established by `TUTORIAL_FILE_MANAGEMENT.md`: a `Time:`/`Outcome:` header line, one mermaid flowchart, numbered hands-on steps grounded in real, verified UI labels/routes/files, `{note}`/`{warning}`/`{important}` MyST admonitions only where a real documented gotcha exists, and closing "What you just did"/"What's next" sections. "Tests" for a docs change are: (a) every UI label/route/field name used was confirmed against live code before writing (done during plan-writing below — each task states the confirmed facts directly), and (b) `sphinx-build` completes with zero new warnings.

**Tech Stack:** Sphinx + MyST (Markdown) + Furo theme, matching the rest of `docs/`.

**Spec:** `docs/superpowers/specs/2026-09-07-survey-tutorial-design.md`

## Global Constraints

- No new files under `examples/` — the reader fills the existing blank `official/create_new_survey/survey_import_template.xlsx` themselves; any other sample data is an inline markdown table.
- No new screenshots — reuse only `docs/_static/screenshots/prism-studio-template-editor.png` and `docs/_static/screenshots/prism-studio-survey-export.png` where a whole-page image adds value; no new per-step captures.
- No persona-picker mechanic (the `data-persona` localStorage gimmick from `TUTORIAL_BEGINNER.md`).
- LimeSurvey chapter covers Export + Customizer only, ending in a real `.lss`; the collect-and-reimport half is one paragraph + a pointer to `LIMESURVEY_INTEGRATION.md`, never duplicated.
- Recipes/scoring gets a closing "What's next" pointer only, never a dedicated chapter.
- Every chapter's scenario facts are fixed and must be reused verbatim (do not invent alternate names): task name `recovery`; scratch project `recovery_check_in_demo`; workbook `recovery_survey_template.xlsx`; resulting template `code/library/survey/survey-recovery.json`; LimeSurvey export `recovery_full_en_de.lss`; Full version = 10 items (mood, soreness, sleep quality, motivation, stress, fatigue, appetite, hydration, satisfaction — all 5-point Likert — plus pain intensity as a 0–100 VAS); Short version = 5 items, a true subset (mood, soreness, pain intensity, fatigue, sleep quality).
- Languages: English (default) throughout Chapters 1–3; German added in Chapter 4 (`de`/`en`, matching `I18nLanguages`/`I18nDefaultLanguage` convention already used in the shipped Excel template's example row).

---

## Confirmed facts (verified against live code before writing this plan — use these exactly, do not re-derive different names)

**Excel template** (`official/create_new_survey/survey_import_template.xlsx`, verified via `openpyxl`):

- `Items` sheet columns, in order: `ItemID`, `Group`, `Description`, `Description_de`, `Description_en`, `Scale`, `Scale_de`, `Scale_en`, `Units`, `DataType`, `AllowedValues`, `MinValue`, `MaxValue`, `WarnMinValue`, `WarnMaxValue`, `TermURL`, `Relevance`, `AliasOf`, `Session`, `Run`, `ApplicableVersions`.
- `General` sheet is `Field`/`Value`/`Required`/`Notes` rows (transposed). Confirmed fields present in the shipped template, with only these three actually marked `Required: yes`: `OriginalName_de`, `OriginalName_en` ("At least one `OriginalName_<lang>` is required"), `LicenseID` ("Pick an SPDX ID, or Proprietary/Other"). Other fields present (not required): `ShortName`, `Version_<lang>`, `Citation`, `Construct_<lang>`, `Instructions_<lang>`, `StudyDescription_<lang>`, `Keywords`, `Authors`, `DOI`, `Respondent`, `AdministrationMethod`, `SoftwarePlatform`, `SoftwareVersion` ("Required unless SoftwarePlatform is Paper and Pencil or AdministrationMethod is paper"), `I18nLanguages`, `I18nDefaultLanguage`, `TranslationMethod`, `Version` ("Active/default variant ID when multiple versions are declared"), `Versions` ("Optional list of all variant IDs supported by this survey").
- `Variants` sheet columns, in order: `Group`, `VariantID`, `ItemID`, `ItemCount`, `ScaleType`, `Description_en`, `Description_de`, `ApplicableVersions`, `DataType`, `AllowedValues`, `MinValue`, `MaxValue`, `WarnMinValue`, `WarnMaxValue`, `Unit`, `Scale_en`, `Scale_de`, `TermURL`, `Relevance`. Two row shapes: a **definition row** (`ItemID` blank, `ItemCount`+`ScaleType`+`Description_<lang>` filled) declares one variant; an **override row** (`ItemID` filled, `VariantID` matching a definition row) changes just that item's scale for that one variant.
- `Help` sheet is a `Sheet`/`Field`/`Description` reference table already inside the workbook.

**Template Editor** (`app/templates/template_editor.html`, `app/static/js/template-editor.js`):

- Top pickers: `Modality` (`#modality`, options `survey`/`biometrics`), `Schema version` (`#schemaVersion`), `Project Templates` (`#projectTemplateSelect`), `Global Templates` (`#globalTemplateSelect`).
- **"Create or Import"** button (`#btnCreateOpen`) expands a panel with **"Create Blank Template"** (`#btnNew`) and **"Import Template Source"** (`#btnImportTemplateSource`, file input accepts `.lsq,.lsg,.lss,.lsa,.xlsx,.csv,.tsv`); importing an Excel file with multiple `Group`s shows a "Multiple instrument groups detected" picker.
- Action row: **"Validate"** (`#btnValidate`), **"Save to Project"** (`#btnSave`, tooltip confirms it "Saves to project/code/library/{modality}/ and confirms before replacing an existing project template"), **"Download JSON"** (`#btnDownload`), **"Delete"** (`#btnDelete`, hidden entirely for anything not project-local).
- Item list: `#newItemId` input + **"Add"** (`#btnAddItem`) + **"Delete"** (`#btnDeleteItems`, supports exact ID or a `prefix...` wildcard); a `#newItemMode` dropdown with options **"Blank new"** and **"Copy style from item"** (the latter reveals `#copyStyleSourceItem` to pick the source item).
- **"Bulk Edit Items"** collapsible panel (`#bulkEditSection`).
- Language bar (`#languageBar`) with **"Add Language"** button (`#btnAddLang`, tooltip "Add a language to all questions").
- Variant selector (`#variantSelectorRow`, label "Survey Variant:", `#activeVariantSelect`) — shown automatically once a template has more than one version; Preview tab has its own "Preview variant:" switcher (`#previewVariantSelect`).
- Preview tab: **"Print / Save as PDF"** (`#btnPrintPreview`) and **"Export as Word document"** (`#btnExportWord`, opens a modal titled "Export Paper-Pencil Questionnaire", needs `python-docx`).

**Survey Export** (`app/templates/survey_generator.html`, route `/survey-generator`):

- Toolbar: `Target Tool` (`#targetToolSelect`), `Base Language` (`#baseLanguageSelect`), `Export Languages` (checkboxes, `#exportLanguageCheckboxes`), `LS Version` (`#lsVersionSelect`), a matrix-grouping checkbox (`#lsMatrixGroupCheckbox`, checked by default).
- Templates are listed in grouped sections: Survey Questionnaires, Biometrics & Physio, Participants, Other Templates — with a search box (`#templateSearch`).
- Buttons: **"Quick Export (.lss)"** (`#generateLssBtn`), **"Customize & Export"** (`#customizeExportBtn`), and a Boilerplate export (`#generateBoilerplateBtn`).

**Survey Customizer** (`app/templates/survey_customizer.html`, route `/survey-customizer`):

- **"Groups"** panel with **"Add new group"** (`#addGroupBtn` → modal "Add New Group", `#newGroupName` input, "Add Group" confirm).
- **"Export Settings"** panel: `#exportFormat` select, a matrix-mode checkbox (`#matrixMode`, checked) and a global-matrix checkbox (`#globalMatrix`, checked).
- Collapsible sections: **"Welcome Message"** (`#lsWelcomeText`, template dropdown `#lsWelcomeTemplate` with options "Standard Welcome"/"Brief Welcome") and **"End Message"**; **"Data Policy / Ethics"**; **"Presentation & Navigation"** (`#lsShowWelcome`, `#lsNavigationDelay`, `#lsShowGroupInfo`).
- Bottom action bar: **"Reset Changes"** (`#resetBtn`), **"Preview Questionnaire"** (`#previewQuestionnaireBtn`, opens a modal with its own language switcher), an Export Word button (`#exportWordBtn`), and the primary CTA **"Export Survey"** (`#exportBtn`).

**Template validation:**

- CLI: `prism-validator --validate-templates /path/to/library` (documented and matches the `argparse` flag in `app/prism.py`). Sample report format (from `docs/TEMPLATES.md`, already verified accurate):
  ```
  ======================================================================
  Template Validation Report: /code/library/survey
  ======================================================================
  Total files: 5 | Valid: 4 | With errors: 1 | Total errors: 2

  ERRORS (2):
    [ERROR] survey-mydepression.json: Study.OriginalName: Original name of the instrument is required
    [ERROR] survey-mydepression.json (ITEM01): Item description is required
      → Missing or empty 'Description' field
  ```
- Five distinct error/warning types returned by the Template Editor's `/api/template-editor/validate` endpoint: `json_parse`, `missing_study`, `study_validation`, `item_validation`, `i18n_validation` — the last one (i18n/language-consistency) is computed separately from schema validation and returned as its own array in the response, per `docs/TEMPLATES.md` and `tools_template_editor_blueprint.py` (confirmed in prior research pass).

---

## Task 1: Collapsible sidebar for the Beginner tutorial

Independent of the new tutorial's content — do this first so the collapsing mechanism is proven before Task 9 relies on it again for the new series.

**Files:**
- Modify: `docs/index.rst` (Tutorial toctree)
- Modify: `docs/TUTORIAL_BEGINNER.md` (add a hidden nested toctree)

**Interfaces:**
- Consumes: nothing new.
- Produces: the "hidden nested toctree inside a landing page, only the landing page listed at the top level" pattern that Task 9 repeats for `TUTORIAL_SURVEY.md`.

- [ ] **Step 1: Read the current Tutorial toctree block**

Run: `grep -n "caption: Tutorial" -A 12 docs/index.rst`

Expected output (confirm this is still accurate before editing):
```
   :caption: Tutorial

   TUTORIAL_BEGINNER
   TUTORIAL_BEGINNER_1_NEW_PROJECT
   TUTORIAL_BEGINNER_2_PARTICIPANTS
   TUTORIAL_BEGINNER_3_SURVEY_IMPORT
   TUTORIAL_BEGINNER_4_RECIPE
   TUTORIAL_BEGINNER_5_VALIDATOR
   TUTORIAL_BEGINNER_6_EXISTING_BIDS
   TUTORIAL_FILE_MANAGEMENT
```

- [ ] **Step 2: Trim the Tutorial toctree in `docs/index.rst` down to landing pages only**

Replace that block with:
```rst
   :caption: Tutorial

   TUTORIAL_BEGINNER
   TUTORIAL_FILE_MANAGEMENT
```

- [ ] **Step 3: Add a hidden nested toctree to `TUTORIAL_BEGINNER.md`**

Look at the end of `docs/studio/index.md` for the exact pattern to mirror (a fenced `` ```{toctree} `` block with `:maxdepth: 1` and `:hidden:`, listing bare filenames with no extension, placed at the very end of the file). Add this at the very end of `docs/TUTORIAL_BEGINNER.md`, after its existing "What's next" section:

````markdown

```{toctree}
:maxdepth: 1
:hidden:

TUTORIAL_BEGINNER_1_NEW_PROJECT
TUTORIAL_BEGINNER_2_PARTICIPANTS
TUTORIAL_BEGINNER_3_SURVEY_IMPORT
TUTORIAL_BEGINNER_4_RECIPE
TUTORIAL_BEGINNER_5_VALIDATOR
TUTORIAL_BEGINNER_6_EXISTING_BIDS
```
````

- [ ] **Step 4: Build the docs and check for warnings**

Run: `python3 -m sphinx -b html docs /tmp/survey-tutorial-check -q 2>&1 | grep -iE "warning|error"`

Expected: no output (zero warnings/errors). If you see "document isn't included in any toctree", the nested toctree in Step 3 is missing one of the 6 chapter filenames — check the list against Step 1's original block.

- [ ] **Step 5: Visually confirm the collapse**

Run: `grep -o "Getting Started[^<]*</a>" /tmp/survey-tutorial-check/index.html || true` (informational only — the real check is opening `/tmp/survey-tutorial-check/index.html` in a browser and confirming the sidebar's "Tutorial" section now shows a "Getting Started — Your First PRISM Project" row with a chevron that expands to the 6 chapters, and a separate flat "File Management: ..." row, matching how "Studio Guide" already behaves.)

- [ ] **Step 6: Commit**

```bash
git add docs/index.rst docs/TUTORIAL_BEGINNER.md
git commit -m "$(cat <<'EOF'
Collapse Beginner tutorial chapters into one sidebar entry

Mirrors the hidden-nested-toctree pattern docs/studio/index.md already
uses for "Studio Guide", so the Tutorial sidebar section shows one row
per tutorial series instead of flattening every chapter into the
top-level list.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Chapter 1 — Survey Concepts You Need First

**Files:**
- Create: `docs/TUTORIAL_SURVEY_1_CONCEPTS.md`

**Interfaces:**
- Consumes: nothing (first content chapter).
- Produces: the `recovery_check_in_demo` scratch project, which every later chapter assumes already exists and is open.

- [ ] **Step 1: Re-read `TUTORIAL_FILE_MANAGEMENT.md` in full as the style reference**

Run: `cat docs/TUTORIAL_FILE_MANAGEMENT.md`

This is the exact structural/voice template to match: `# Title`, a `**Time:** ~N minutes | **Outcome:** ...` line, one ` ```{mermaid} ` flowchart, `##`-level sections with numbered steps, `{note}`/`{warning}`/`{important}` admonitions, a "What you just did" section, and a "What's next" section with bullet links.

- [ ] **Step 2: Write `docs/TUTORIAL_SURVEY_1_CONCEPTS.md`**

Structure to follow exactly:

1. `# Chapter 1: Survey Concepts You Need First`
2. Header line: `**Time:** ~15 minutes | **Outcome:** ...` (a clear grasp of official-vs-project-local templates, and a fresh scratch project ready for Chapter 2).
3. A mermaid flowchart showing: `official/library/survey/` (shared instrument) → Template Editor loads it → Save forks a copy into → `code/library/survey/` (this project's copy) — visually establishing the fork-on-save concept before the prose explains it.
4. `## If you haven't done the Beginner tutorial` — 2–3 sentences: a PRISM project has a `sub-*/ses-*/<modality>/` layout, survey response data eventually lands in `sub-*/ses-*/survey/`, `participant_id` ties everything together. Link to `TUTORIAL_BEGINNER.md`, explicitly framed as optional background, not a prerequisite.
5. `## Official vs. project-local templates` — the core content of this chapter:
   - `official/library/<modality>/` holds shared, reusable instrument definitions (what a validated licensed questionnaire *is*).
   - `code/library/<modality>/` holds this project's own copy — the one actually used for import/export in that project.
   - State plainly: **Template Editor always forks on save** — loading a Global (official) template and clicking "Save to Project" writes a new copy into `code/library/<modality>/`; it never overwrites the official one. Delete (`#btnDelete`) is hidden entirely for anything that isn't project-local.
   - One `{important}` admonition: this project/official split is why editing "the same" template in two different projects never collides — each project gets its own fork.
6. `## What a template actually is` — a template is a JSON file matching PRISM's `survey.schema.json`; the Excel workbook used in Chapter 2 is *one* authoring format for producing that JSON, not the format itself — you could also build the JSON by hand, or import it from LimeSurvey XML. This sets up Chapter 2 correctly (it's about the Excel *path*, not the only path).
7. `## The scenario: Recovery Check-In` — one paragraph introducing the fictional exercise-recovery study exactly as described in the spec (Full 10-item evening check-in + Short 5-item same-day follow-up, bilingual EN/DE later, mixing Likert and a VAS pain item) — this paragraph can reuse the spec's own wording closely since it's already precise.
8. `## Set up a scratch project` — numbered steps, mirroring `TUTORIAL_FILE_MANAGEMENT.md`'s own "Set up a scratch project" section format exactly: Create New Project named `recovery_check_in_demo`, DataLad optional, same phrasing pattern ("nothing you do in this tutorial touches any project you already have").
9. `## What you just did` — 2–3 sentences.
10. `## What's next` — link to `TUTORIAL_SURVEY_2_EXCEL_TEMPLATE.md` as the next chapter, plus `TUTORIAL_SURVEY.md` (series landing) and `docs/TEMPLATES.md` for the reference-doc version of the template JSON model.

- [ ] **Step 3: Build the docs and check for warnings on this file**

Run: `python3 -m sphinx -b html docs /tmp/survey-tutorial-check -q 2>&1 | grep -i "TUTORIAL_SURVEY_1_CONCEPTS"`

Expected: exactly one line, a "document isn't included in any toctree" warning — this is expected and correct at this point (the landing page that includes it doesn't exist until Task 9). Any *other* warning (broken mermaid syntax, bad cross-reference target, malformed admonition) must be fixed now.

- [ ] **Step 4: Commit**

```bash
git add docs/TUTORIAL_SURVEY_1_CONCEPTS.md
git commit -m "$(cat <<'EOF'
Add Survey tutorial Chapter 1: concepts and scratch project

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Chapter 2 — Prepare a New Questionnaire in Excel

**Files:**
- Create: `docs/TUTORIAL_SURVEY_2_EXCEL_TEMPLATE.md`

**Interfaces:**
- Consumes: `recovery_check_in_demo` project (Task 2); the exact `Items`/`General` sheet column lists from "Confirmed facts" above.
- Produces: `recovery_survey_template.xlsx` (the reader's filled workbook) and `code/library/survey/survey-recovery.json` (imported+saved), which every later chapter assumes exist.

- [ ] **Step 1: Re-read `docs/EXCEL_TEMPLATE_BASICS.md` in full**

Run: `cat docs/EXCEL_TEMPLATE_BASICS.md`

This is the reference doc being tutorial-ized — reuse its field-by-field facts and its documented "Common mistakes" (placeholder text like `n/a` silently becomes blank via pandas), but rewrite as a narrative hands-on walkthrough scoped to the Recovery Check-In Full version, English only, rather than a generic reference.

- [ ] **Step 2: Write `docs/TUTORIAL_SURVEY_2_EXCEL_TEMPLATE.md`**

Structure:

1. `# Chapter 2: Prepare a New Questionnaire in Excel`
2. `**Time:** ~30 minutes | **Outcome:** ...` (a validated, saved `survey-recovery.json` template with all 10 Full-version items, English only).
3. Mermaid flowchart: blank `survey_import_template.xlsx` → fill `Items` + `General` → Template Editor "Import Template Source" → "Validate" → "Save to Project" → `code/library/survey/survey-recovery.json`.
4. `## Copy the blank template` — copy `official/create_new_survey/survey_import_template.xlsx` to a working copy named `recovery_survey_template.xlsx` (state plainly: never edit the official copy in place).
5. `## Fill the Items sheet` — a markdown table with all 10 Full-version items filled in for the columns that matter (`ItemID`, `Group`, `Description_en`, `Scale_en` for the 9 Likert items using `0=never;1=rarely;2=sometimes;3=often`-style value=label pairs — pick a mood/soreness-appropriate scale text such as `1=not at all;2=slightly;3=moderately;4=very;5=extremely`, `DataType: integer`, `MinValue: 1`, `MaxValue: 5` — and for the pain-intensity item use `DataType: integer`, `MinValue: 0`, `MaxValue: 100`, `Units: points` instead of a `Scale_en` value list, matching how the shipped template's own `10-vas` variant row in the `Variants` sheet later demonstrates the same MinValue/MaxValue-instead-of-Scale pattern). Use `ItemID`s like `rec_mood`, `rec_sore`, `rec_sleep`, `rec_motiv`, `rec_stress`, `rec_fatigue`, `rec_appetite`, `rec_hydration`, `rec_satisf`, `rec_pain`. Leave `Description`/`Scale`/`Description_de`/`Scale_de` blank for now (Chapter 4 adds German) — note this explicitly so the reader isn't confused why those columns exist but are unused here.
6. `## Fill the General sheet` — only the 3 actually-required fields plus the handful that matter for this study, as a table: `OriginalName_en` = `Recovery Check-In`, `LicenseID` = e.g. `CC-BY-4.0`, `ShortName` = `recovery`, `Authors` = a placeholder name, `I18nLanguages` = `en` (Chapter 4 changes this to `de;en`), `I18nDefaultLanguage` = `en`, `Respondent` = `self`, `AdministrationMethod` = `electronic` (this study is digital, unlike the shipped example's `paper` default — call this out as a deliberate choice since Chapter 6 exports to LimeSurvey). State plainly that every other `General` field is optional and can stay blank.
7. `{warning}` admonition, verbatim gotcha from `EXCEL_TEMPLATE_BASICS.md`: placeholder text like `n/a` in a cell silently becomes blank when read by pandas — don't use it as a "not applicable" marker in `Scale`/`Description` columns.
8. `## Import into the Template Editor` — numbered steps using the exact confirmed button chain: open `/template-editor`, `Modality` = `survey`, click **"Create or Import"** (`#btnCreateOpen`) → **"Import Template Source"** (`#btnImportTemplateSource`) → select `recovery_survey_template.xlsx`.
9. `## Validate, then save` — click **"Validate"** (`#btnValidate`); expected outcome: no errors (if there are, the reader likely used `n/a` somewhere or left a required `General` field blank — point back to the warning above). Click **"Save to Project"** (`#btnSave`); confirms it lands at `code/library/survey/survey-recovery.json`.
10. `## What you just did` / `## What's next` — next chapter `TUTORIAL_SURVEY_3_TEMPLATE_EDITOR.md`; also link back to `docs/EXCEL_TEMPLATE_BASICS.md` for the full field reference this chapter only used a slice of.

- [ ] **Step 3: Build the docs and check for warnings on this file**

Run: `python3 -m sphinx -b html docs /tmp/survey-tutorial-check -q 2>&1 | grep -i "TUTORIAL_SURVEY_2_EXCEL_TEMPLATE"`

Expected: exactly one "not included in any toctree" warning (same reasoning as Task 2 Step 3). Fix anything else.

- [ ] **Step 4: Commit**

```bash
git add docs/TUTORIAL_SURVEY_2_EXCEL_TEMPLATE.md
git commit -m "$(cat <<'EOF'
Add Survey tutorial Chapter 2: author the questionnaire in Excel

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Chapter 3 — Edit and Refine in the Template Editor

**Files:**
- Create: `docs/TUTORIAL_SURVEY_3_TEMPLATE_EDITOR.md`

**Interfaces:**
- Consumes: `code/library/survey/survey-recovery.json` (Task 3).
- Produces: nothing new file-wise; leaves the template with one item's wording tweaked in-editor and a Word export produced, both ephemeral/demonstrative rather than facts later chapters depend on.

- [ ] **Step 1: Confirm the Bulk Edit and Preview/Word-export UI hasn't changed**

Run: `grep -n "bulkEditSection\|btnExportWord\|Export Paper-Pencil" app/templates/template_editor.html`

Expected: all three strings still present (matches the "Confirmed facts" section above). If not, adjust the button/id references in Step 2 to whatever you find instead.

- [ ] **Step 2: Write `docs/TUTORIAL_SURVEY_3_TEMPLATE_EDITOR.md`**

Structure:

1. `# Chapter 3: Edit and Refine in the Template Editor`
2. `**Time:** ~25 minutes | **Outcome:** ...` (comfortable editing a template directly in the browser, without re-importing Excel every time you want to change something).
3. Mermaid flowchart: three parallel edit surfaces feeding the same template — Top-level panel, Item list + Bulk Edit, Preview/Export — all writing back to `survey-recovery.json`.
4. `## Why edit here instead of re-importing Excel` — one paragraph: once a template is project-local, round-tripping through Excel for every small wording change is slower than editing directly; Excel is for first-draft authoring and bulk data entry, the Template Editor is for refinement.
5. `## The Top-level panel` — `Study`/`Technical` sections hold the same `General`-sheet fields from Chapter 2 (e.g. `OriginalName_en`, `LicenseID`) as form fields instead of spreadsheet rows — point out this is literally the same underlying JSON, just a different editing surface.
6. `## Editing one item directly` — load `survey-recovery.json` (`#projectTemplateSelect`), click the `rec_mood` item in the list, change its wording in the Selected Item panel, re-**Validate**, **Save to Project** again. This demonstrates the edit-without-Excel loop concretely.
7. `## Bulk Edit Items` — open **"Bulk Edit Items"** (`#bulkEditSection`), select the 9 Likert items (not the VAS pain item), apply one shared change across all of them at once (e.g. tightening the shared `Scale_en` wording) in a single action instead of editing each item individually.
8. `## Preview and Word export` — Preview tab, **"Print / Save as PDF"** (`#btnPrintPreview`) vs. **"Export as Word document"** (`#btnExportWord`, opens the "Export Paper-Pencil Questionnaire" modal with layout options: headers, item codes, randomize order). `{note}`: Word export needs the `python-docx` package installed.
9. `## What you just did` / `## What's next` — next chapter `TUTORIAL_SURVEY_4_LANGUAGES_SCALES.md`.

- [ ] **Step 3: Build the docs and check for warnings on this file**

Run: `python3 -m sphinx -b html docs /tmp/survey-tutorial-check -q 2>&1 | grep -i "TUTORIAL_SURVEY_3_TEMPLATE_EDITOR"`

Expected: exactly one "not included in any toctree" warning, nothing else.

- [ ] **Step 4: Commit**

```bash
git add docs/TUTORIAL_SURVEY_3_TEMPLATE_EDITOR.md
git commit -m "$(cat <<'EOF'
Add Survey tutorial Chapter 3: edit and refine in the Template Editor

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Chapter 4 — Languages and Scales

**Files:**
- Create: `docs/TUTORIAL_SURVEY_4_LANGUAGES_SCALES.md`

**Interfaces:**
- Consumes: `survey-recovery.json` (English-only, Task 3/4).
- Produces: the same template now bilingual (`I18nLanguages: de;en`) with the pain item using a VAS scale — a fact Chapter 5 (Variants) and Chapter 6 (LimeSurvey export, which exports both languages) both depend on.

- [ ] **Step 1: Write `docs/TUTORIAL_SURVEY_4_LANGUAGES_SCALES.md`**

Structure:

1. `# Chapter 4: Languages and Scales`
2. `**Time:** ~25 minutes | **Outcome:** ...` (a bilingual EN/DE template with both a Likert and a VAS scale correctly represented).
3. Mermaid flowchart: one item → two parallel language columns (`Description_en`/`Description_de`) → one shared `DataType`/`MinValue`/`MaxValue` scale definition — showing language and scale are independent axes of the same item.
4. `## Two ways to add a language` — cover both, since the doc set does:
   - **Excel path**: fill the already-present `Description_de`/`Scale_de` columns for all 10 items in `recovery_survey_template.xlsx`, update `General.I18nLanguages` to `de;en`, re-import.
   - **In-editor path**: the language bar (`#languageBar`) → **"Add Language"** (`#btnAddLang`, tooltip "Add a language to all questions") adds the language to every item at once from inside the Template Editor, without touching the Excel file at all.
5. `## The language-consistency warning` — explain concretely: after adding German, clicking **Validate** may show an `i18n_validation`-type warning if any item still has an English-only field somewhere (e.g. you added `Description_de` but forgot `Scale_de` for one item) — this is a *warning* about content completeness, not a schema *error*, and the two show up as separate result lists in the Validate response (set this up explicitly for Chapter 7, which explains the distinction in full).
6. `## Likert vs. VAS` — the 9 mood/soreness-style items use a `Levels`-style value=label map (the `Scale_en`/`Scale_de` columns, e.g. `1=not at all;...;5=extremely`) — a **Likert** scale. The pain-intensity item instead uses `MinValue: 0`/`MaxValue: 100` with no `Scale_en` value list — a continuous **VAS** (visual analogue scale). In the Template Editor this item's `ScaleType` renders as a slider input rather than radio buttons/a dropdown.
7. `## Reusing a scale with Copy Style` — in the item list, set `#newItemMode` to **"Copy style from item"**, pick an existing Likert item (e.g. `rec_mood`) in `#copyStyleSourceItem`, and add a new item that starts with the same `MinValue`/`MaxValue`/`DataType` pre-filled. `{note}`: this is copy-based reuse, not a shared reference — editing the scale on one item afterward does not change the other; there's no separate "scale library" object, by design.
8. `## What you just did` / `## What's next` — next chapter `TUTORIAL_SURVEY_5_VARIANTS.md`.

- [ ] **Step 2: Build the docs and check for warnings on this file**

Run: `python3 -m sphinx -b html docs /tmp/survey-tutorial-check -q 2>&1 | grep -i "TUTORIAL_SURVEY_4_LANGUAGES_SCALES"`

Expected: exactly one "not included in any toctree" warning, nothing else.

- [ ] **Step 3: Commit**

```bash
git add docs/TUTORIAL_SURVEY_4_LANGUAGES_SCALES.md
git commit -m "$(cat <<'EOF'
Add Survey tutorial Chapter 4: languages and scales

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Chapter 5 — Multiple Versions (Variants)

**Files:**
- Create: `docs/TUTORIAL_SURVEY_5_VARIANTS.md`

**Interfaces:**
- Consumes: bilingual `survey-recovery.json` (Task 5); the exact `Variants` sheet column list from "Confirmed facts".
- Produces: the template now has two declared versions (`full`, `short`), a fact Chapter 6 (LimeSurvey export lets you pick a version) references.

- [ ] **Step 1: Write `docs/TUTORIAL_SURVEY_5_VARIANTS.md`**

Structure:

1. `# Chapter 5: Multiple Versions (Variants)`
2. `**Time:** ~25 minutes | **Outcome:** ...` (one template that serves both the Full and Short Recovery Check-In forms, without maintaining two separate files).
3. Mermaid flowchart: `survey-recovery.json` → `Variants` sheet definition rows (`full`: 10 items, `short`: 5 items) → variant selector in Template Editor shows both.
4. `## Why one template, not two files` — one paragraph: the Short form is a genuine subset of the Full form's items, not a different instrument — maintaining it as a separate template would mean editing wording twice forever; a variant is the same item set with a declared subset + optional per-item scale override.
5. `## Add the Variants sheet` — in `recovery_survey_template.xlsx`, add two **definition rows** to `Variants`: `VariantID: full`, `ItemCount: 10`, `ScaleType: likert` (mixed — call out that `ScaleType` here describes the predominant scale, individual items keep their own `DataType`/`MinValue`/`MaxValue`), `Description_en: Full evening check-in`; and `VariantID: short`, `ItemCount: 5`, `Description_en: Same-day quick follow-up`. Then tag every `Items` row's `ApplicableVersions` column: the 5 shared items (`rec_mood`, `rec_sore`, `rec_pain`, `rec_fatigue`, `rec_sleep`) get `full;short`; the other 5 get `full` only.
6. `## Re-import and confirm both versions` — re-import the updated workbook (or add the same via **"Bulk Edit Items"** in-editor, whichever the reader already has open), **Validate**, **Save to Project**. The **Survey Variant:** selector (`#activeVariantSelect`) should now show both `full` and `short`; switching it filters the item list to that version's `ApplicableVersions`.
7. `## A note on repeated administrations` — one paragraph, not a full section: Survey Export (next chapter) lets you set a **Run** number per template for pre/post designs, and Converter output writes `run-01`/`run-02` files plus item-level `SessionHint`/`RunHint` fields for longitudinal studies — out of scope for this tutorial's hands-on steps, with a pointer to `docs/specs/survey.md` and `docs/LIMESURVEY_INTEGRATION.md` for depth.
8. `{note}` — for a more complex, already-finished multi-version example than this tutorial's own, point to `examples/wellbeing_multi_demo` in the repository.
9. `## What you just did` / `## What's next` — next chapter `TUTORIAL_SURVEY_6_LIMESURVEY_EXPORT.md`; also `docs/EXCEL_TEMPLATE_ADVANCED.md` for the full Variants reference.

- [ ] **Step 2: Build the docs and check for warnings on this file**

Run: `python3 -m sphinx -b html docs /tmp/survey-tutorial-check -q 2>&1 | grep -i "TUTORIAL_SURVEY_5_VARIANTS"`

Expected: exactly one "not included in any toctree" warning, nothing else.

- [ ] **Step 3: Commit**

```bash
git add docs/TUTORIAL_SURVEY_5_VARIANTS.md
git commit -m "$(cat <<'EOF'
Add Survey tutorial Chapter 5: multiple versions (variants)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Chapter 6 — Export to LimeSurvey

**Files:**
- Create: `docs/TUTORIAL_SURVEY_6_LIMESURVEY_EXPORT.md`

**Interfaces:**
- Consumes: two-version, bilingual `survey-recovery.json` (Task 6); the exact Survey Export / Customizer labels from "Confirmed facts".
- Produces: `recovery_full_en_de.lss` (a real, downloadable file) — the tutorial's terminal deliverable for this chapter; nothing later depends on it programmatically.

- [ ] **Step 1: Write `docs/TUTORIAL_SURVEY_6_LIMESURVEY_EXPORT.md`**

Structure:

1. `# Chapter 6: Export to LimeSurvey`
2. `**Time:** ~30 minutes | **Outcome:** ...` (a real `.lss` file, ready to import into a LimeSurvey installation, with per-question presentation configured).
3. Mermaid flowchart: `survey-recovery.json` (full version) → Survey Export → Customizer (grouping, per-question settings) → `recovery_full_en_de.lss` → (dashed/optional line) LimeSurvey.
4. `## Quick Export vs. Customize & Export` — on `/survey-generator`, find `recovery` under **Survey Questionnaires**, set **Base Language** = `en`, check both **Export Languages** (`en`, `de`), **LS Version** = whatever the current default is, select the `full` version. **"Quick Export (.lss)"** (`#generateLssBtn`) produces a ready-to-import file immediately with default presentation; **"Customize & Export"** (`#customizeExportBtn`) opens the Survey Customizer first — this tutorial uses the latter to show what's actually configurable.
5. `## Group and order questions` — in the Customizer's **Groups** panel, **"Add new group"** (`#addGroupBtn`) to split the 10 items into two logical groups (e.g. "Recovery Ratings" for the 9 Likert items, "Pain" for the VAS item), then drag to reorder.
6. `## Per-question LimeSurvey settings` — for one item, open its settings and set: question type override, mandatory, a relevance equation (one simple example, e.g. only show the pain item if a "session included training" screening question was answered yes — phrase this as illustrative, not required for the reader's own file to validate), hidden, and page-break behavior — matching what `docs/studio/survey_customizer.md` documents these controls as.
7. `## Matrix grouping` — enable `#matrixMode`/`#globalMatrix` so the 9 shared-scale Likert items render as one LimeSurvey matrix question instead of 9 separate ones — call out this only makes sense because those 9 items share the same response scale (a callback to Chapter 4).
8. `## Welcome text and export` — fill **Welcome Message** (`#lsWelcomeText`, or pick the "Standard Welcome" template from `#lsWelcomeTemplate`) and **End Message**, then **"Export Survey"** (`#exportBtn`) → save as `recovery_full_en_de.lss`.
9. `## What happens next (not covered here)` — one paragraph, explicitly scoped: import this `.lss` into a running LimeSurvey installation, collect real responses, export a `.lsa` archive, then import that back into PRISM via Converter → Survey. Full walkthrough with screenshots: `docs/LIMESURVEY_INTEGRATION.md`. State plainly this tutorial stops here by design — no LimeSurvey instance is required to complete it.
10. `## What you just did` / `## What's next` — next chapter `TUTORIAL_SURVEY_7_VALIDATION.md`; also `docs/LIMESURVEY_INTEGRATION.md`.

- [ ] **Step 2: Build the docs and check for warnings on this file**

Run: `python3 -m sphinx -b html docs /tmp/survey-tutorial-check -q 2>&1 | grep -i "TUTORIAL_SURVEY_6_LIMESURVEY_EXPORT"`

Expected: exactly one "not included in any toctree" warning, nothing else.

- [ ] **Step 3: Commit**

```bash
git add docs/TUTORIAL_SURVEY_6_LIMESURVEY_EXPORT.md
git commit -m "$(cat <<'EOF'
Add Survey tutorial Chapter 6: export to LimeSurvey

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Chapter 7 — Validating Your Template

**Files:**
- Create: `docs/TUTORIAL_SURVEY_7_VALIDATION.md`

**Interfaces:**
- Consumes: `survey-recovery.json` (all prior chapters); the exact `prism-validator --validate-templates` syntax and error-type list from "Confirmed facts".
- Produces: nothing new — this is the series' closing technical chapter.

- [ ] **Step 1: Write `docs/TUTORIAL_SURVEY_7_VALIDATION.md`**

Structure:

1. `# Chapter 7: Validating Your Template`
2. `**Time:** ~15 minutes | **Outcome:** ...` (understanding exactly what "validated" means for a template, and how to check a whole library at once).
3. Mermaid flowchart: `survey-recovery.json` → two parallel checks — Template Editor **Validate** (schema errors + i18n warnings) and `prism-validator --validate-templates` (whole-library) — converging on "confidently correct template".
4. `## Preview is not validation` — correct the common assumption head-on: Chapter 3's Preview tab shows how the template *renders*, it does not check the underlying JSON against the schema. **Validate** (`#btnValidate`) is the actual check, and it always has been available since Chapter 2 — this chapter explains what it's actually checking, in full.
5. `## Two kinds of Validate result` — schema errors (structural: missing required fields, wrong types — the same rules `prism-validator --validate-templates` enforces) vs. i18n/language-consistency warnings (content completeness: a language added but not applied everywhere — first raised in Chapter 4). State plainly these come back as two separate arrays in the API response, not one merged list, and one used error types: `json_parse`, `missing_study`, `study_validation`, `item_validation` (schema-side) and `i18n_validation` (separate).
6. `## Validate a whole library from the command line` — `prism-validator --validate-templates code/library/survey` (run from the project root), reproduce the sample report format from "Confirmed facts" above with `survey-recovery.json` substituted for the filename in the example, and explain: useful for CI, for checking a library before sharing it, or when several templates need checking at once rather than one at a time in the browser.
7. `## If you maintain a shared library` — one line: `library_validator.py`'s uniqueness check additionally flags duplicate variable names and redundant items across an entire library (not just within one template) — relevant once you have more than one template sharing item IDs, out of scope for a single-template tutorial project but worth knowing exists.
8. `## What you just did` — this closes the whole series, so make it a full recap across all 7 chapters (one line each), not just this chapter.
9. `## What's next` — per the spec's confirmed scope: [Recipes](RECIPES.md) and [`TUTORIAL_BEGINNER_4_RECIPE.md`](TUTORIAL_BEGINNER_4_RECIPE.md) ("score the responses once you have them"), [Converter → Survey](studio/converter_survey.md) ("import real response data against this template"), [LimeSurvey Integration](LIMESURVEY_INTEGRATION.md) ("the full round trip"), [Validator](studio/validator.md) ("dataset-level validation once data exists").

- [ ] **Step 2: Build the docs and check for warnings on this file**

Run: `python3 -m sphinx -b html docs /tmp/survey-tutorial-check -q 2>&1 | grep -i "TUTORIAL_SURVEY_7_VALIDATION"`

Expected: exactly one "not included in any toctree" warning, nothing else.

- [ ] **Step 3: Commit**

```bash
git add docs/TUTORIAL_SURVEY_7_VALIDATION.md
git commit -m "$(cat <<'EOF'
Add Survey tutorial Chapter 7: validating your template

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Landing page + wire the collapsible sidebar entry

**Files:**
- Create: `docs/TUTORIAL_SURVEY.md`
- Modify: `docs/index.rst` (Tutorial toctree)

**Interfaces:**
- Consumes: all 7 chapter files (Tasks 2–8) must already exist; the collapsing pattern proven in Task 1.
- Produces: a fully navigable, zero-warning tutorial series.

- [ ] **Step 1: Re-read `TUTORIAL_BEGINNER.md`'s landing-page structure**

Run: `cat docs/TUTORIAL_BEGINNER.md`

Reuse its `<div class="prism-chapter-grid">` card markup structure exactly (one `<a class="prism-chapter-card" href="...">` per chapter, each with an icon/number span, title span, outcome span, time span) but **without** the persona-picker block (`<div class="prism-persona-grid" ...>` and everything between it and the chapter grid) — this series has no persona mechanic.

- [ ] **Step 2: Write `docs/TUTORIAL_SURVEY.md`**

Structure:

1. `# Author a Survey` (this exact title — it's the string that will appear as the collapsible sidebar row, per the spec).
2. 2–3 sentence framing: this is the most-used part of PRISM Studio for most users; standalone series, no Beginner-tutorial prerequisite.
3. `## Who this is for` / prerequisites: PRISM Studio installed (link `INSTALLATION.md`); no LimeSurvey instance required; no prior PRISM knowledge assumed.
4. `## The scenario` — the Recovery Check-In paragraph (same content as Chapter 1's scenario paragraph, framed here as a preview).
5. Chapter card grid, 7 cards, same CSS classes as the Beginner landing grid, each linking to its `.html` (Sphinx will resolve `TUTORIAL_SURVEY_N_....html`), with outcome + time estimate matching each chapter's own header line.
6. Total time estimate stated up front (~2h45m, sum of 15+30+25+25+25+30+15 minutes), matching how `TUTORIAL_BEGINNER.md` states its own total.
7. `## What's next` — same 4 links as Chapter 7's closing "What's next" (Recipes, Converter → Survey, LimeSurvey Integration, Validator).
8. At the very end, the hidden nested toctree (mirroring Task 1's Step 3 pattern exactly):

````markdown

```{toctree}
:maxdepth: 1
:hidden:

TUTORIAL_SURVEY_1_CONCEPTS
TUTORIAL_SURVEY_2_EXCEL_TEMPLATE
TUTORIAL_SURVEY_3_TEMPLATE_EDITOR
TUTORIAL_SURVEY_4_LANGUAGES_SCALES
TUTORIAL_SURVEY_5_VARIANTS
TUTORIAL_SURVEY_6_LIMESURVEY_EXPORT
TUTORIAL_SURVEY_7_VALIDATION
```
````

- [ ] **Step 3: Wire it into `docs/index.rst`**

Add `TUTORIAL_SURVEY` as a third entry in the Tutorial toctree (after Task 1's trim, it currently reads `TUTORIAL_BEGINNER` then `TUTORIAL_FILE_MANAGEMENT`):

```rst
   :caption: Tutorial

   TUTORIAL_BEGINNER
   TUTORIAL_FILE_MANAGEMENT
   TUTORIAL_SURVEY
```

- [ ] **Step 4: Full build, zero warnings anywhere**

Run: `python3 -m sphinx -b html docs /tmp/survey-tutorial-check -q 2>&1 | grep -iE "warning|error"`

Expected: **no output at all** now — every chapter's "not included in any toctree" warning from Tasks 2–8 must be gone, since all 7 are now listed in `TUTORIAL_SURVEY.md`'s nested toctree. If anything remains, find which chapter filename is missing or misspelled in Step 2's toctree list.

- [ ] **Step 5: Visually confirm the full sidebar**

Open `/tmp/survey-tutorial-check/index.html` in a browser. Confirm the "Tutorial" caption shows exactly three rows: "Getting Started — Your First PRISM Project" (chevron, expands to 6), "File Management: Bulk Rename, Reorganize, and Clean Up" (flat, no chevron), "Author a Survey" (chevron, expands to 7). Click through 2–3 of the new chapter links to confirm they render correctly (mermaid diagram shows, tables render, admonitions styled).

- [ ] **Step 6: Commit**

```bash
git add docs/TUTORIAL_SURVEY.md docs/index.rst
git commit -m "$(cat <<'EOF'
Add Survey tutorial landing page and wire it into the sidebar

Completes the new 7-chapter "Author a Survey" series: landing page with
its own collapsible nested toctree (matching the Beginner tutorial and
Studio Guide pattern), added as the third row under the Tutorial caption.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Backlinks from existing reference docs

**Files:**
- Modify: `docs/EXCEL_TEMPLATE_BASICS.md`
- Modify: `docs/EXCEL_TEMPLATE_ADVANCED.md`
- Modify: `docs/studio/template_editor.md`
- Modify: `docs/studio/survey_generator.md`
- Modify: `docs/studio/survey_customizer.md`

**Interfaces:**
- Consumes: `TUTORIAL_SURVEY.md` and all 7 chapters must exist and build clean (Task 9 complete).
- Produces: nothing new relied upon elsewhere — this is the final polish task.

- [ ] **Step 1: Add one backlink line to each file's existing closing section**

For each of the 5 files above, find its existing "What's next"/closing links section (each already has one, in the same style as every other `docs/studio/*.md` page) and add one new bullet pointing to the tutorial. Use the exact relative path form already used elsewhere in that file (files under `docs/studio/` use `../TUTORIAL_SURVEY.md`; files directly under `docs/` use `TUTORIAL_SURVEY.md`):

- `docs/EXCEL_TEMPLATE_BASICS.md`: `- [Author a Survey (tutorial)](TUTORIAL_SURVEY.md) — this reference's content, as a guided hands-on walkthrough`
- `docs/EXCEL_TEMPLATE_ADVANCED.md`: `- [Author a Survey (tutorial)](TUTORIAL_SURVEY.md) — see Chapter 5 for a guided walkthrough of adding a Variants sheet`
- `docs/studio/template_editor.md`: `- [Author a Survey (tutorial)](../TUTORIAL_SURVEY.md) — a full guided walkthrough using this screen`
- `docs/studio/survey_generator.md`: `- [Author a Survey (tutorial)](../TUTORIAL_SURVEY.md) — see Chapter 6 for a guided export walkthrough`
- `docs/studio/survey_customizer.md`: `- [Author a Survey (tutorial)](../TUTORIAL_SURVEY.md) — see Chapter 6 for a guided walkthrough of this screen`

- [ ] **Step 2: Spot-check against `TUTORIAL_BEGINNER_3_SURVEY_IMPORT.md` for duplication**

Run: `cat docs/TUTORIAL_BEGINNER_3_SURVEY_IMPORT.md`

That chapter already covers: getting a template by copying a pre-made JSON or being pointed at `EXCEL_TEMPLATE_BASICS.md`; the Converter → Survey import flow for response *data* (participant ID column, session column, Preview, Convert); and a closing pointer that punts LimeSurvey specifics to `LIMESURVEY_INTEGRATION.md`. Confirm the 7 new chapters don't re-teach the Converter → Survey data-import flow (they shouldn't need to — this series stops at a validated, exported *template*, never imports response data against it) and don't re-explain what a `participant_id`/session column is from scratch (Chapter 1's recap references it in one sentence, doesn't re-teach it). If either new chapter drifts into re-teaching that ground, trim it back to a cross-link instead.

- [ ] **Step 3: Final full build, zero warnings**

Run: `python3 -m sphinx -b html docs /tmp/survey-tutorial-check -q 2>&1 | grep -iE "warning|error"`

Expected: no output. This is the plan's final verification gate — if this passes, every task's changes compose correctly together.

- [ ] **Step 4: Clean up the scratch build directory**

Run: `rm -rf /tmp/survey-tutorial-check`

- [ ] **Step 5: Commit**

```bash
git add docs/EXCEL_TEMPLATE_BASICS.md docs/EXCEL_TEMPLATE_ADVANCED.md docs/studio/template_editor.md docs/studio/survey_generator.md docs/studio/survey_customizer.md
git commit -m "$(cat <<'EOF'
Backlink existing survey docs to the new Author a Survey tutorial

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
