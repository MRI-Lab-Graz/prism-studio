# Excel Survey Template — Basics

A hands-on walkthrough for building a survey JSON template by filling in an Excel
workbook and importing it in **Template Editor**, rather than hand-typing every item
in the form. Use this when you already have a codebook or item list in a spreadsheet
(from a prior study, a published instrument, or your own drafting) and want it turned
into a PRISM survey template quickly.

This is about **authoring an instrument definition** (what the questionnaire is, what
its items are). It is not about importing respondent answers — for that, see
[Converter — Survey Import](studio/converter_survey.md).

**Time:** ~15 minutes. **Outcome:** one validated, project-saved survey template with
four items, built entirely from a spreadsheet.

## 1. Get a workbook

Two options:

- **Follow along** with the finished example workbook at
  [examples/excel_template/basic/survey_import_basic_example.xlsx](../examples/excel_template/basic/survey_import_basic_example.xlsx)
  — a small 4-item instrument called "Daily Mood Check".
- **Start your own** from the canonical blank workbook at
  [official/create_new_survey/survey_import_template.xlsx](../official/create_new_survey/survey_import_template.xlsx)
  and clear out its two placeholder item rows.

Either way, you get the same four sheets: `Items`, `General`, `Variants`, `Help`. This
tutorial only uses `Items` and `General` — `Variants` is for multi-version instruments,
covered in [Excel Survey Template — Multiple Versions](EXCEL_TEMPLATE_ADVANCED.md).

Both sheets have built-in guardrails so you don't have to remember every valid value
by heart:

- **Header row is locked.** You can fill in rows below it, but the column names
  themselves can't be edited by accident.
- **Several columns are dropdowns**, not free-text fields — click the cell and pick
  from the list instead of typing. In `Items`: `DataType`, `Units`. In `General`:
  `LicenseID`, `Respondent`, `AdministrationMethod`, `SoftwarePlatform`,
  `TranslationMethod`. This is the main thing that avoids a failed or silently-wrong
  import: a typo like `interger` in a hand-typed `DataType` column, or `digital` where
  the schema actually expects `online`, won't be caught until validation, while the
  dropdown only offers valid values in the first place.
- Dropdowns here are a *guide*, not a hard lock — you can still type a custom value if
  you have a good reason to (e.g. a `Units` value not in the recommended list).
- In `General`, only the `Value` column is editable; `Field`, `Required`, and `Notes`
  are locked so a metadata key can't be renamed by mistake.

## 2. Fill in `Items`

One row per question. The columns that matter for a simple, single-version, bilingual
instrument:

| Column | Example | Meaning |
|---|---|---|
| `ItemID` | `mood01` | Unique key — becomes both the item's JSON key and part of downstream column names. |
| `Group` | `mood` | Groups item rows into one instrument. All rows sharing a `Group` become one template; a workbook can define more than one instrument this way. |
| `Description_en` / `Description_de` | "Today I felt cheerful" / "Heute fuehlte ich mich froehlich" | The item text per language. |
| `Scale_en` / `Scale_de` | `0=never;1=rarely;2=sometimes;3=often` | Response labels, as `value=label` pairs joined with `;`. |
| `Units`, `DataType` | `ordinal`, `integer` | How the responses should be typed downstream. |
| `AllowedValues`, `MinValue`, `MaxValue` | `0;1;2;3`, `0`, `3` | Numeric bounds/allowed set matching the scale. |

The example workbook has four rows: `mood01`–`mood04`, all in `Group = mood`, all
sharing the same 4-point scale.

## 3. Fill in `General`

`General` is transposed — one metadata field per row, in `Field`/`Value` columns.
Rows with `Required = yes` (highlighted) must be filled or the template fails
validation later:

| Field | Value (example) |
|---|---|
| `OriginalName_en` *(required)* | Daily Mood Check |
| `OriginalName_de` *(required — at least one `OriginalName_<lang>` is mandatory)* | Taeglicher Stimmungscheck |
| `LicenseID` *(required)* | CC-BY-4.0 |
| `ShortName` | mood |
| `Authors` | PRISM Docs Team |
| `Respondent` | self |
| `AdministrationMethod` | online |
| `SoftwarePlatform` | Other |
| `SoftwareVersion` | unspecified |
| `I18nLanguages` | en;de |
| `I18nDefaultLanguage` | en |

`LicenseID` is required by the schema — pick from the dropdown (SPDX-style IDs, or
`Proprietary`/`Other` if none fit). `AdministrationMethod` and `SoftwarePlatform` are
both closed enums (that's why they're dropdowns): there's no `digital` option for
administration — the closest valid value for a self-administered digital
questionnaire is `online`. And whenever `SoftwarePlatform` is set to anything other
than `Paper and Pencil` (and `AdministrationMethod` isn't `paper`), `SoftwareVersion`
becomes required too — fill in something, even a placeholder like `unspecified`.

Leave `Version`, `Versions`, and the entire `Variants` sheet empty — those only apply
when an instrument has multiple variants (see the advanced tutorial).

## 4. Import in Template Editor

1. Open **Template Editor** → set **Modality** to `survey`.
2. Click **Import Template Source** → choose your `.xlsx` file.
3. If the workbook defines more than one `Group`, a picker appears — choose `mood`.
4. The generated form loads: `Study` fields from `General`, four items from `Items`.

## 5. Validate and save

Click **Validate**, confirm no errors, then **Save to Project**. This writes
`code/library/survey/survey-mood.json` (the filename comes from `ShortName`/`Group`).

The saved template's `Study` block and one item look like this (trimmed):

```json
{
  "Study": {
    "TaskName": "mood",
    "OriginalName": { "en": "Daily Mood Check", "de": "Taeglicher Stimmungscheck" },
    "ShortName": "mood",
    "Authors": ["PRISM Docs Team"],
    "LicenseID": "CC-BY-4.0",
    "Instructions": {
      "en": "Think about today and answer each question.",
      "de": "Denken Sie an den heutigen Tag und beantworten Sie jede Frage."
    }
  },
  "Technical": {
    "SoftwarePlatform": "Other",
    "SoftwareVersion": "unspecified",
    "Respondent": "self",
    "AdministrationMethod": "online"
  },
  "mood01": {
    "Description": { "en": "Today I felt cheerful", "de": "Heute fuehlte ich mich froehlich" },
    "Levels": {
      "0": { "en": "never", "de": "nie" },
      "1": { "en": "rarely", "de": "selten" },
      "2": { "en": "sometimes", "de": "manchmal" },
      "3": { "en": "often", "de": "haeufig" }
    },
    "DataType": "integer",
    "MinValue": 0.0,
    "MaxValue": 3.0,
    "AllowedValues": [0, 1, 2, 3]
  }
}
```

Full output for comparison:
[examples/excel_template/basic/survey-mood.json](../examples/excel_template/basic/survey-mood.json).

## Common mistakes

- **No `OriginalName_<lang>` filled in** — validation fails with `Study.OriginalName`
  missing. At least one language variant is required.
- **No `LicenseID`** — validation fails with `Study.LicenseID` missing; it's required
  even for an internal/unpublished instrument. Pick `Proprietary` or `Other` if no
  real license applies yet.
- **`AdministrationMethod`/`SoftwarePlatform` set to something outside the dropdown
  list** (typed instead of picked) — these are closed enums; a value like `digital` or
  `PsychoPy 2023` fails validation even though it reads as reasonable. Pick from the
  dropdown.
- **Placeholder text like `n/a`, `NA`, or `null` in any `Value` cell** — pandas (which
  PRISM uses to read the workbook) treats these as blank/missing, even when the
  column is read as text. If a field is required (like `SoftwareVersion` once
  `SoftwarePlatform` is set), use a real placeholder word such as `unspecified`
  instead — `n/a` will silently disappear on import.
- **`Scale` and `AllowedValues`/`MinValue`/`MaxValue` disagree** — e.g. four scale
  labels (`0`–`3`) but `MaxValue` set to `4`. Keep them in sync. The dropdown columns
  prevent typos in themselves, but they can't catch a mismatch between the scale and
  the numeric bounds — check that by hand.
- **Duplicate `ItemID` across rows** — each item key must be unique within the
  instrument. PRISM does *not* check this against other templates already in your
  project when importing here (that check only runs in the Converter's bulk import,
  not Template Editor) — use an instrument-specific prefix (`mood01`, not `q01`) so two
  different instruments can never collide.
- **Forgetting to pick a `Group`** when the workbook has several instruments in one
  sheet — you'll otherwise get one merged, nonsensical template.
- **Trying to edit the header row or unprotecting the sheet "to fix" the dropdown** —
  you don't need to. There's no password; if you ever genuinely need to change a
  header name, unprotect via Excel's Review tab and re-protect afterward.

## What's next

- [Excel Survey Template — Multiple Versions](EXCEL_TEMPLATE_ADVANCED.md) — same
  workflow, extended to instruments with a long/short form or other variants.
- [Template Editor](studio/template_editor.md) — full reference for the screen used
  in step 4.
- [Survey Templates](TEMPLATES.md) — the reference model for the JSON this produces.
- [Converter — Survey Import](studio/converter_survey.md) — the separate workflow for
  importing respondent data against a template like this one.
