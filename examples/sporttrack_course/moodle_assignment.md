# Assignment: SportTrack, from a new study to a jamovi file

**Goal:** Run a small longitudinal study through PRISM Studio from start to finish: create the project, import sociodemographics, build a survey template, import four waves of answers (after fixing errors in the data), score the questionnaire with a recipe and export anonymized long-format data for jamovi.

**Time:** plan about 3 hours. Tasks a to f build on each other: finish them in order.

## Before you start

1. Use the latest version, **PRISM Studio 1.25.0** (download the source ZIP into a **new** folder and run the installer; the version badge in the Studio window must say 1.25.0).
2. Download the folder `sporttrack_course` and keep its `raw_data` folder at hand: `sporttrack_sociodemographics.tsv`, `shq_responses.xlsx`, `survey_import_template.xlsx`. You also need `project_metadata.html`.

## The study: "SportTrack"

A made-up longitudinal study: 240 university students, tested **four times** (baseline, 3, 6 and 12 months). At baseline they run a treadmill test (VO2max); every time they fill in a questionnaire about their sport habits. Participants **dropped out** along the way, so not everyone has four sessions. That is normal.

## Task a) Create the project (about 20 min)

Open `project_metadata.html` and enter its values in **Create New Project**: name, keywords, **two authors** (you as corresponding author, Karl Koschutnig as co-author), ethics, funding, overview, eligibility, procedure.

The most important field is **Timepoints: Several timepoints (longitudinal)**. Click **Create Project** (not Preliminary Save).

## Task b) Sociodemographics (about 25 min)

**Prepare Data > Converter > Sociodemographics**, import `sporttrack_sociodemographics.tsv` (240 participants). Columns: `participant_id`, `age`, `sex`, `handedness`, `vo2max`.

1. Age, sex and handedness are found automatically. Add `vo2max` with **Add More Columns (Optional)**.
2. **Annotate for NeuroBagel**: link age, sex and handedness to their terms, harmonize the codes (sex: 1 = Female, 2 = Male, 3 = Other; handedness: 1 = Right-handed, 2 = Left-handed, 3 = Ambidextrous), unit of age = years. `vo2max` has no NeuroBagel term: describe it and give the unit (ml/kg/min).
3. Link `age` to the Age eligibility criterion (18 to 40).
4. **Create Participant Files.**

## Task c) The survey template (about 45 min)

Questionnaire: **Sport Habits Questionnaire (SHQ)**, 20 items. Participants are asked to think about the last four weeks. Instructions: *Please think about the last four weeks and tell us how much each statement applies to you.*

The items use different answer scales, so **read the Scale column of each item**:

| Scale | Answer options |
|---|---|
| **F** | 1 = never, 2 = rarely, 3 = sometimes, 4 = often, 5 = always |
| **A7** | 1 = strongly disagree, 2 = disagree, 3 = slightly disagree, 4 = neutral, 5 = slightly agree, 6 = agree, 7 = strongly agree |
| **A5** | 1 = strongly disagree, 2 = disagree, 3 = neutral, 4 = agree, 5 = strongly agree |

| ItemID | Statement | Scale |
|---|---|---|
| shq01 | I do at least 30 minutes of sport in a row | F |
| shq02 | I do sport because it is fun | A7 |
| shq03 | I lack time for sport | A5 |
| shq04 | I take the stairs instead of the lift | F |
| shq05 | I do sport to stay healthy | A7 |
| shq06 | Sport facilities are too expensive for me | A5 |
| shq07 | I go for a run or a bike ride in my free time | F |
| shq08 | I do sport to improve my appearance | A7 |
| shq09 | I am too tired after lectures to exercise | A5 |
| shq10 | I do strength or gym exercises | F |
| shq11 | I do sport to relieve stress | A7 |
| shq12 | I feel uncomfortable exercising in public | A5 |
| shq13 | I take part in team sports | F |
| shq14 | I do sport because my friends do it | A7 |
| shq15 | Bad weather keeps me from exercising | A5 |
| shq16 | I walk or cycle to university | F |
| shq17 | I feel bad when I skip a workout | A7 |
| shq18 | I do not know which exercises suit me | A5 |
| shq19 | How many hours per week do you do sport? | whole number 0 to 20, no labels |
| shq20 | Do you currently have a gym or sports club membership? | 0 = no, 1 = yes |

Steps:

1. Save a copy of `survey_import_template.xlsx` as `shq.xlsx`. Fill **Items** (one row per item: ItemID, Group `shq`, Description_en, Scale_en, Units, DataType `integer`, AllowedValues, MinValue / MaxValue) and **General**. Use these General values: OriginalName_en `Sport Habits Questionnaire`, ShortName `shq`, LicenseID `CC0-1.0`, Authors (your name), Instructions_en (the text above), Respondent `self`, AdministrationMethod `online`, SoftwarePlatform `Other`, SoftwareVersion `unspecified`, I18nLanguages and I18nDefaultLanguage `en`. Empty every other Value cell and the **Variants** sheet.
2. **Template Editor > Create or import new > survey > Import Template Source**, choose `shq.xlsx`.
3. Fill what the editor marks as missing: Citation `Made-up questionnaire for the PRISM class (2026).`, Creator (your name), Construct (English) `Sport habits, motivation and barriers`.
4. **Validate** (no errors), then **Save to Project**.

## Task d) Fix the data and import it (about 50 min)

`shq_responses.xlsx` has one row per participant and session (`participant_id`, `session`, `shq01` ... `shq20`). **The file contains 3 wrong values.** PRISM refuses to convert until they are fixed.

1. **Session map.** The `session` column holds the labels `ses-1`, `ses-2`, `ses-3`, `ses-4`. Because the project is longitudinal, PRISM does not guess: map each label to a session in the **Session mapping** panel (`ses-1` to `1`, and so on). The result must be the folders `ses-1` to `ses-4`.
2. Open **Prepare Data > Converter > Survey**, import `shq_responses.xlsx`. Participant ID column `participant_id`, session column `session`. Run **Preview** and read it.
3. Conversion stops at a value that is not allowed. The message names the participant, session and item. Find the value in the Excel file and decide what is right: you cannot know the true answer, so an impossible value becomes an **empty cell** (missing). Save your cleaned copy as `shq_responses_clean.xlsx`; keep the original untouched.
   *Do not* use the "offset" suggestion in the message: shifting a whole scale is for a different kind of error.
4. Repeat until all 3 errors are found, then convert and run the **validator**. Warnings about missing sessions (drop-outs) are expected; errors are not.

## Task e) The recipe (about 25 min)

In the **Recipe Builder**, build a recipe for task `shq` with **4 scores**, all `sum`:

| Score | Items |
|---|---|
| **Activity** | shq01, shq04, shq07, shq10, shq13, shq16 |
| **Motivation** | shq02, shq05, shq08, shq11, shq14, shq17 |
| **Barriers** | shq03, shq06, shq09, shq12, shq15, shq18 |
| **Total** | all 18 items of the three subscales |

shq19 and shq20 are **not** part of any score. Higher scores mean more of the named thing (Barriers: more obstacles; do not reverse anything). Save the recipe. Before you move on, check one participant by hand: add up their items in the converted data and compare with the score.

## Task f) Export for jamovi (about 15 min)

**Analysis Output**: choose your recipe, all four sessions, format **csv**, layout **long** (one row per participant and session), tick **Anonymize**. Click **Create Output**.

Open the CSV in jamovi. It must have one row per participant and session, with `participant_id` as pseudonyms (no `P001`), `session` and the four scores. In jamovi, make `session` a nominal variable.

## What to hand in

1. `shq.xlsx` and the final `survey-shq.json` from your project
2. `dataset_description.json`, `participants.tsv` and `participants.json`
3. `shq_responses_clean.xlsx` **and a list of your 3 corrections**: participant, session, item, wrong value, what you did and why
4. `code/session_map.json` and `code/recipes/survey/recipe-shq.json`
5. The exported CSV (anonymized, long) and a screenshot of it opened in jamovi
6. A screenshot of the final validator result

## How it is checked

- Project: both authors, one corresponding with email, Timepoints = several, 5 or more keywords
- `participants.json`: age with unit years, sex and handedness with labelled levels and NeuroBagel terms, `vo2max` described with unit
- Template: 20 items with the right scales (items 1 to 18 as in the table, `shq19` no labels 0 to 20, `shq20` 0 = no and 1 = yes)
- Corrections: all 3 found, none "fixed" by guessing a value
- Session map: four labels mapped to sessions 1 to 4; data folders `ses-1` to `ses-4`
- Recipe: the four scores with exactly the right items; shq19 and shq20 not in any score
- Export: long format, about 900 rows (not 240), anonymized IDs, no errors in the validator

## Tips

- Do not type `n/a` or `null` in Excel cells; an empty cell is missing.
- Scale, AllowedValues, MinValue and MaxValue must agree (1 to 7 for A7, not 0 to 6).
- A 6 is wrong for a 1 to 5 item but fine for a 1 to 7 item. Check an item's scale before you decide a value is wrong.
- Session labels are free text. `1`, `01` and `ses-1` are different labels: PRISM only treats them as the same when you map them.
- Imported IDs get the prefix `sub-` (P001 becomes sub-P001). This is expected.
- Stuck? The Getting Started tutorial (chapters 1 to 5) and "Excel Survey Template: Basics" cover the same steps.

## Report PRISM Studio problems on GitHub

If something does not work and you are confident it is not your mistake, search the [issue list](https://github.com/MRI-Lab-Graz/prism-studio/issues) and then open a new issue: short title, exact steps, expected and actual result (error text and screenshot), operating system and version. Never put real personal data into an issue (the course data is fine). If you found no problem, write "I found no PRISM Studio problem" in your hand-in.
