# Chapter 3: Edit and Refine in the Template Editor

**Time:** ~25 minutes | **Outcome:** comfortable editing `survey-recovery.json`
directly in the browser — a single item's wording, a shared change across
several items at once, and a paper-pencil export — without re-importing
Excel for any of it.

```{mermaid}
flowchart LR
    T["🗂️ code/library/survey/<br/>survey-recovery.json"]
    A["🔧 Top-level panel<br/>Study / Technical"] --> T
    B["📝 Item list + Bulk Edit"] --> T
    C["👁️ Preview / Export"] --> T
```

## Why edit here instead of re-importing Excel

Chapter 2 got the template into PRISM the fast way for a first draft: fill a
spreadsheet, import it once. But every small change after that — tightening
one item's wording, fixing a typo in the study description — doesn't need a
round trip through a workbook. Excel is for first-draft authoring and bulk
data entry, when you're typing out many rows at once; once the template is
project-local, the Template Editor's own form is faster for refinement,
because it edits `survey-recovery.json` in place, no re-import step at all.

## The Top-level panel

Load `survey-recovery.json` from **Template Editor** if it isn't already
open (select it from `#projectTemplateSelect`). Above the item list sit the
**Study** and **Technical** sections — the same fields you filled in on the
`General` sheet in Chapter 2, `OriginalName_en` and `LicenseID` among them,
now rendered as form fields instead of spreadsheet rows. Nothing new lives
here: it's literally the same underlying JSON as `Items`/`General` in the
workbook, just a different editing surface over it.

## Editing one item directly

1. In the item list, click `rec_mood`.
2. In the **Selected Item** panel, change its wording — for example, tighten
   `Description_en` from "Overall mood today" to "Overall mood, right now."
3. Click **Validate**.
4. Click **Save to Project** again.

That's the entire edit-without-Excel loop: pick an item, change a field,
validate, save. No workbook touched.

## Bulk Edit Items

Editing nine items one at a time for a shared wording change is exactly the
kind of repetition the Template Editor avoids. Open **"Bulk Edit Items"**
(`#bulkEditSection`), check the 9 Likert items in the item list — every
Recovery Check-In item except `rec_pain`, which is the 0–100 VAS pain item
and has no `Scale_en` to share — then set the change once in the Bulk Edit
form (for example, tightening the shared
`1=not at all;2=slightly;3=moderately;4=very;5=extremely` wording). Apply it,
and it lands on all nine checked items in a single action.

```{note}
Bulk Edit applies to whichever items are checked in the list above it, or to
*all* items if none are checked — leave `rec_pain` unchecked so its (blank)
`Scale_en` isn't touched.
```

## Preview and Word export

Switch to the **Preview** tab to see the template rendered as a
respondent would. Two export paths sit here, side by side:

- **"Print / Save as PDF"** (`#btnPrintPreview`) — sends the current preview
  to your browser's print dialog.
- **"Export as Word document"** (`#btnExportWord`) — opens the **"Export
  Paper-Pencil Questionnaire"** modal, with layout options including a
  participant ID line, a date field, showing authors & year, showing item
  codes, and randomizing item order.

```{note}
Word export needs the `python-docx` package installed.
```

## What you just did

You edited `survey-recovery.json` three different ways without opening
Excel once: a single item's wording through the item list and Selected Item
panel, a shared wording change across all nine Likert items through Bulk
Edit, and the Study/Technical metadata through the Top-level panel — then
previewed the result and exported it as a paper-pencil Word questionnaire.

## What's next

- [Chapter 4: Languages and Scales](TUTORIAL_SURVEY_4_LANGUAGES_SCALES.md) —
  add German alongside English and reuse the shared Likert scale across items
