# Chapter 2: Prepare a New Questionnaire in Excel

**Time:** ~30 minutes | **Outcome:** a validated, saved `survey-recovery.json`
template with all 10 Recovery Check-In **Full** version items, English only.

```{mermaid}
flowchart LR
    A["📄 survey_import_template.xlsx<br/>blank"] --> B["✏️ Fill Items + General"]
    B --> C["🛠️ Template Editor<br/>Import Template Source"]
    C --> D["✅ Validate"]
    D --> E["💾 Save to Project"]
    E --> F["🗂️ code/library/survey/<br/>survey-recovery.json"]
```

This chapter turns the Recovery Check-In **Full** version — 10 items,
introduced in [Chapter 1](TUTORIAL_SURVEY_1_CONCEPTS.md) — into a real
survey template, by filling in a spreadsheet rather than hand-typing every
item in the Template Editor's form. If you haven't read
[Excel Survey Template — Basics](EXCEL_TEMPLATE_BASICS.md) yet, this chapter
walks through the same mechanics against our specific study; that page
remains the full field-by-field reference once you're past this first pass.

## Copy the blank template

Start from the canonical blank workbook,
[official/create_new_survey/survey_import_template.xlsx](../official/create_new_survey/survey_import_template.xlsx).

Make a working copy — don't edit the official file in place. Save it as
`code/survey/recovery_survey_template.xlsx` **inside** the
`recovery_check_in_demo` project (create the `code/survey/` folder if it
doesn't exist yet) rather than somewhere outside it like your Desktop —
this workbook is authoring material for the template, the same way
`code/library/` holds the template itself and `code/recipes/` holds
scoring recipes, and keeping it in the project means it travels with your
DataLad history instead of living only on your machine. Open the copy; you
should see four sheets: `Items`, `General`, `Help`, `Variants`.
This chapter only fills in `Items` and `General` — `Variants` is for
multi-version instruments (the Full/Short split), which a later chapter
covers.

```{note}
The workbook ships with two placeholder item rows already in `Items`.
Clear those out before entering the Recovery Check-In rows below.
```

## Fill the Items sheet

One row per question. All 10 Full-version items share `Group = recovery`.
Nine are 5-point Likert items; the pain item uses a 0–100 numeric scale
instead.

Six columns matter for this pass — the workbook has more (`Session`,
`Run`, `AllowedValues`, ...), and `docs/EXCEL_TEMPLATE_BASICS.md`
documents the full set:

- **ItemID** — a unique, machine-readable identifier. It becomes the
  column name in every response file this template ever produces, so pick
  something stable (`rec_mood`, not `Q1`). It must be unique within this
  instrument: two rows sharing an `ItemID` don't raise an error, they
  silently merge into one item and you lose whichever row's data didn't
  win. PRISM doesn't check this against other templates already in your
  project either, so an instrument-specific prefix (`rec_mood`, not just
  `mood`) is worth the extra characters.
- **Group** — which instrument this row belongs to. One workbook can
  define several instruments; every row sharing a `Group` value becomes
  one template.
- **Description_en** — the actual question text a respondent sees, in
  this language.
- **Scale_en** — the response options, as `value=label;value=label;...`
  pairs. Leave it blank for a continuous scale — see `rec_pain` below.
- **DataType / MinValue / MaxValue** — the stored value's type and
  numeric bounds, used for validation whether or not `Scale_en` is filled
  in.
- **Units** — optional, only meaningful for a continuous item like the
  VAS pain scale below.

| ItemID | Group | Description_en | Scale_en | DataType | MinValue | MaxValue | Units |
|---|---|---|---|---|---|---|---|
| `rec_mood` | recovery | Overall mood today | `1=not at all;2=slightly;3=moderately;4=very;5=extremely` | integer | 1 | 5 | |
| `rec_sore` | recovery | Muscle soreness | `1=not at all;2=slightly;3=moderately;4=very;5=extremely` | integer | 1 | 5 | |
| `rec_sleep` | recovery | Sleep quality last night | `1=not at all;2=slightly;3=moderately;4=very;5=extremely` | integer | 1 | 5 | |
| `rec_motiv` | recovery | Motivation to train | `1=not at all;2=slightly;3=moderately;4=very;5=extremely` | integer | 1 | 5 | |
| `rec_stress` | recovery | Stress level | `1=not at all;2=slightly;3=moderately;4=very;5=extremely` | integer | 1 | 5 | |
| `rec_fatigue` | recovery | Fatigue | `1=not at all;2=slightly;3=moderately;4=very;5=extremely` | integer | 1 | 5 | |
| `rec_appetite` | recovery | Appetite | `1=not at all;2=slightly;3=moderately;4=very;5=extremely` | integer | 1 | 5 | |
| `rec_hydration` | recovery | Hydration | `1=not at all;2=slightly;3=moderately;4=very;5=extremely` | integer | 1 | 5 | |
| `rec_satisf` | recovery | Satisfaction with training | `1=not at all;2=slightly;3=moderately;4=very;5=extremely` | integer | 1 | 5 | |
| `rec_pain` | recovery | Pain intensity | *(leave blank)* | integer | 0 | 100 | points |

Two things to note about that last row: `rec_pain` is the 0–100 VAS
(visual analogue scale) item — leave `Scale_en` empty and set `MinValue`/
`MaxValue`/`Units` instead. This is the same pattern the shipped template's
own `Variants` sheet uses later for its `10-vas` variant row: a numeric
range with `Units`, not a `value=label` list.

```{note}
Leave `Description_de` and `Scale_de` blank for every row, and leave the
plain `Description`/`Scale` columns (without a language suffix) blank too —
they're unused here. A later chapter in this series comes back to add the
German columns; for now they just sit empty in the sheet, which is
expected.
```

## Fill the General sheet

`General` is transposed — one metadata field per row, `Field`/`Value`
columns. The schema actually requires at least one `OriginalName_<lang>`
field (`_de` or `_en`) plus `LicenseID`; filling in `OriginalName_en` below
satisfies that on its own, so `OriginalName_de` doesn't need a value yet
(German comes in a later chapter). Fill those two required fields plus the
handful below that matter for this study:

| Field | Value |
|---|---|
| `OriginalName_en` *(required)* | Recovery Check-In |
| `LicenseID` *(required)* | CC-BY-4.0 |
| `ShortName` | recovery |
| `Authors` | Jordan Lee |
| `I18nLanguages` | en |
| `I18nDefaultLanguage` | en |
| `Respondent` | self |
| `AdministrationMethod` | electronic |

Every other `General` field can stay blank — leave `Version`, `Versions`,
`SoftwarePlatform`, `SoftwareVersion`, and the rest as they are.

`AdministrationMethod` is worth a pause: the shipped example workbook
defaults this to `paper`, but Recovery Check-In is a digital, in-app
check-in, so this chapter sets it to `electronic` instead. That's a
deliberate choice made now because a later chapter in this series exports
this same template to LimeSurvey, which expects an electronic
administration method — changing it later would mean re-editing metadata
you've already validated and saved.

```{warning}
Placeholder text like `n/a`, `NA`, or `null` in any cell — pandas (which
PRISM uses to read the workbook) treats these as blank/missing, even in a
column read as text. If you're tempted to mark a `Scale`/`Description`
column as "not applicable" for the `rec_pain` row, leave the cell **truly
empty** instead of typing `n/a` — typing it doesn't fail loudly, it just
silently disappears on import.
```

## Import into the Template Editor

1. Open **Template Editor** and set **Modality** to `survey`.
2. Click **Create or Import**.
3. Click **Import Template Source**.
4. Select your `recovery_survey_template.xlsx` file.

The generated form should load one instrument (`Group = recovery`) with 10
items and the `General` fields you filled in above.

## Validate, then save

1. Click **Validate**.

   Expected outcome: no errors. If validation fails, the most likely causes
   are the two things called out above — an `n/a`-style placeholder
   somewhere it silently became blank, or `OriginalName_en`/`LicenseID`
   left empty (the schema needs at least one `OriginalName_<lang>` plus
   `LicenseID`). Re-check the sheets against the tables above.

2. Click **Save to Project**.

   This writes the template to `code/library/survey/survey-recovery.json`
   inside your `recovery_check_in_demo` project — the filename comes from
   `ShortName`. Every later chapter in this series assumes this exact file
   exists.

## What you just did

Starting from the blank official workbook, you filled in all 10 Recovery
Check-In Full-version items — nine 5-point Likert items and one 0–100 VAS
pain item — plus the minimum `General` metadata this study needs, imported
that workbook through the Template Editor, validated it, and saved it as
`code/library/survey/survey-recovery.json` in your project.

## What's next

- [Chapter 3: Edit and Refine in the Template Editor](TUTORIAL_SURVEY_3_TEMPLATE_EDITOR.md) —
  work directly in the form you just imported into
- [Excel Survey Template — Basics](EXCEL_TEMPLATE_BASICS.md) — the full
  field-by-field reference this chapter only used a slice of
