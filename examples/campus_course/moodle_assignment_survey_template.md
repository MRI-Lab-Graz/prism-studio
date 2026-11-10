# Assignment: Your first survey template

**Goal:** Turn a made-up questionnaire into a PRISM survey template. You start from the Excel template, import it into PRISM Studio, complete the missing fields in the Template Editor, validate it and hand in the resulting JSON file. Motivated students can earn extra points by using the template on test data (Task c).

## Before you start

1. **Install the latest version, PRISM Studio 1.25.0.** Download the source code ZIP from the [PRISM Studio repository](https://github.com/MRI-Lab-Graz/prism-studio) into a new folder (do not reuse an old copy) and run the installer (macOS/Linux `bash install.sh`, Windows `install.cmd`). Check the version badge in the Studio window: it must say **1.25.0**. Older versions behave differently from this description.
2. **Create a GitHub account** (free, [github.com](https://github.com)). You need it to report problems (see the last section).
3. Download the attached files: `survey_import_template.xlsx` (needed for everyone); for the extra task also `cch_sociodemographics.tsv` and `cch_responses.xlsx`.

## The questionnaire: "Campus Coffee Habits" (CCH)

Invented for this class. 14 items in three blocks. Items 1 to 12 are answered on a 5-point scale, items 13 and 14 are different.

**Instructions for participants:** Please tell us how often each statement applies to you.

**Block 1, items 1 to 8.** Scale: 1 = never, 2 = rarely, 3 = sometimes, 4 = often, 5 = always

| ItemID | Statement |
|---|---|
| cch01 | I drink coffee to wake up in the morning |
| cch02 | I drink coffee while studying |
| cch03 | I drink coffee together with friends |
| cch04 | I need coffee to get through a lecture |
| cch05 | I drink coffee when I feel stressed |
| cch06 | I drink coffee in the evening |
| cch07 | I replace a meal with coffee |
| cch08 | I buy coffee at the campus cafeteria |

**Block 2, items 9 to 12.** Scale: 1 = strongly disagree, 2 = disagree, 3 = neutral, 4 = agree, 5 = strongly agree

| ItemID | Statement |
|---|---|
| cch09 | Coffee helps me to concentrate |
| cch10 | I feel restless when I drink too much coffee |
| cch11 | I would find it hard to give up coffee |
| cch12 | I sleep worse on days when I drink a lot of coffee |

**Block 3, items 13 and 14.** These two have their own answer format.

| ItemID | Question | Answer |
|---|---|---|
| cch13 | How many cups of coffee do you usually drink per day? | a whole number from 0 to 15 (no labels) |
| cch14 | Do you usually drink decaffeinated coffee? | 0 = no, 1 = yes |

## Task a) Fill in the Excel template

Save a copy of `survey_import_template.xlsx` as `cch.xlsx`.

**Sheet `Items`:** delete the two example rows and add 14 rows, one per item.

| Column | Enter |
|---|---|
| ItemID | cch01 ... cch14 |
| Group | cch (the same in every row) |
| Description_en | the statement or question |
| Scale_en | the scale of the block, written as `1=never;2=rarely;3=sometimes;4=often;5=always`. Empty for cch13. |
| Units | ordinal (dropdown); for cch13 choose `count` |
| DataType | integer (dropdown) for all items |
| AllowedValues | `1;2;3;4;5` for items 1 to 12, `0;1` for cch14, empty for cch13 |
| MinValue / MaxValue | 1 / 5 for items 1 to 12, 0 / 15 for cch13, 0 / 1 for cch14 |

Leave all other columns empty, including the `_de` columns.

**Sheet `General`** (only the `Value` column is editable):

| Field | Value |
|---|---|
| OriginalName_en | Campus Coffee Habits |
| LicenseID | CC0-1.0 |
| ShortName | cch |
| Authors | your name |
| Instructions_en | Please tell us how often each statement applies to you. |
| Respondent | self |
| AdministrationMethod | online |
| SoftwarePlatform | Other |
| SoftwareVersion | unspecified |
| I18nLanguages | en |
| I18nDefaultLanguage | en |

**Empty every other Value cell** (all `_de` fields, Version, Versions, Keywords, TranslationMethod, ...). Empty the `Variants` sheet as well.

## Task b) Import and complete it in PRISM Studio

1. Open your project, then **Template Editor**. Choose **Create or import new**, Modality **survey**, then **Import Template Source** and select `cch.xlsx`. If you are asked for a group, choose `cch`.
2. The Excel file cannot carry everything. Fill in the fields the editor marks as missing:
   - **Citation:** `Made-up questionnaire for the PRISM class (2026).`
   - **Creator** (Metadata): your name
   - **Construct** (English): `Coffee consumption habits`
3. Click **Validate**. Fix anything reported as an error.
4. Click **Save to Project**. The file is `code/library/survey/survey-cch.json` in your project folder.

## Task c) Extra points: use your template on test data

Only for those who want more. Test data of 320 made-up participants is attached.

1. Create a **new** project (as in the first assignment): fill in all required fields of the Study Metadata. DataLad off.
2. Open **Prepare Data > Converter > Sociodemographics** and import `cch_sociodemographics.tsv`. It has only `participant_id`, `age` and `sex`. Annotate for NeuroBagel as in the first assignment: sex codes are 1 = Female, 2 = Male, 3 = Other; age is in years. Click **Create Participant Files**.
3. Save your `survey-cch.json` into this new project (Task b, steps 1 to 4, in the new project).
4. Open **Prepare Data > Converter > Survey** and import `cch_responses.xlsx`. Participant ID column is `participant_id`, the session column is `session`, the session is `baseline`. Run **Preview** first and read it, then convert.
5. Run the **validator** on the project and fix what it reports as an error.

## What to hand in

Everyone:
1. `survey-cch.json` from your project
2. A screenshot of the Template Editor after **Validate** (no errors)
3. The text of the GitHub issue you opened, or the sentence "I found no PRISM Studio problem" (see below)

Extra task only:
4. `participants.tsv` and `participants.json` of the new project
5. A screenshot of the Preview of the survey import
6. A screenshot of the final validator result

## How it is checked

- `survey-cch.json` has exactly the 14 items `cch01` to `cch14`
- items 1 to 8 have the frequency labels, items 9 to 12 the agreement labels, `MinValue` 1, `MaxValue` 5
- `cch13` has no levels, `MinValue` 0, `MaxValue` 15, unit `count`; `cch14` has levels 0 = no and 1 = yes
- `Study.OriginalName.en` is "Campus Coffee Habits", `I18n.Languages` is only `en`
- `Study.Citation`, `Study.Construct.en` and `Metadata.Creator` are filled
- the screenshot shows no validation errors
- extra points: `participants.tsv` has 320 rows with only the wanted columns, `participants.json` describes age (unit years) and sex (labelled levels, NeuroBagel terms), the preview reports 320 participants and task `cch`, and the final validator result has no errors

## Report PRISM Studio problems on GitHub

Software has bugs, and PRISM Studio is no exception. If something does not work and **you are confident it is not your mistake**, report it:

1. First check again: right version (1.25.0)? Steps exactly as in this text? Does a restart help?
2. Search the [issue list](https://github.com/MRI-Lab-Graz/prism-studio/issues) to see if it is already reported. If yes, add a comment with your details instead of a new issue.
3. Otherwise open a **New issue** with:
   - a short title (what happened, where)
   - the exact steps you did
   - what you expected and what happened instead (copy the error message as text, add a screenshot)
   - your operating system and the PRISM Studio version
4. Never put real personal data into an issue. The test data of this course is fine.

Not a bug: a typo in your Excel file, a missing field the editor marks as required, a message that tells you exactly what to fix. You do not lose points for a wrong report, but a good report earns credit. If you found no problem, say so in your hand-in.

## Tips

- Do not type `n/a` or `null` into a cell: Excel import treats it as empty. Leave it empty, or use a real word such as `unspecified`.
- Scale, AllowedValues, MinValue and MaxValue must agree (1 to 5, not 0 to 4).
- Administration method has no `digital`: pick `online` from the dropdown.
- Do not edit the header row of a sheet.
- Imported IDs get the prefix `sub-` (P001 becomes sub-P001). This is expected.
- Stuck? The "Excel Survey Template: Basics" tutorial walks through the same steps with another example.
