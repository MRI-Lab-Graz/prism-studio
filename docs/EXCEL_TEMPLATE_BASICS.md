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
| `ShortName` | mood |
| `Authors` | PRISM Docs Team |
| `Respondent` | self |
| `AdministrationMethod` | digital |
| `I18nLanguages` | en;de |
| `I18nDefaultLanguage` | en |

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
    "Instructions": {
      "en": "Think about today and answer each question.",
      "de": "Denken Sie an den heutigen Tag und beantworten Sie jede Frage."
    }
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
- **`Scale` and `AllowedValues`/`MinValue`/`MaxValue` disagree** — e.g. four scale
  labels (`0`–`3`) but `MaxValue` set to `4`. Keep them in sync.
- **Duplicate `ItemID` across rows** — each item key must be unique within the
  instrument.
- **Forgetting to pick a `Group`** when the workbook has several instruments in one
  sheet — you'll otherwise get one merged, nonsensical template.

## What's next

- [Excel Survey Template — Multiple Versions](EXCEL_TEMPLATE_ADVANCED.md) — same
  workflow, extended to instruments with a long/short form or other variants.
- [Template Editor](studio/template_editor.md) — full reference for the screen used
  in step 4.
- [Survey Templates](TEMPLATES.md) — the reference model for the JSON this produces.
- [Converter — Survey Import](studio/converter_survey.md) — the separate workflow for
  importing respondent data against a template like this one.
