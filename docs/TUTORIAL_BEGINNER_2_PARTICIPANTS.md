# Beginner Tutorial 2 — Import Sociodemographic Data

Chapter 2 of [Getting Started — Your First PRISM Project](TUTORIAL_BEGINNER.md).
This is about getting per-participant demographic fields (age, sex,
education, handedness, ...) into `participants.tsv`/`participants.json` —
it's not about the survey items in the same source file, which come in
chapter 3.

**Time:** ~15 minutes. **Outcome:** `participants.tsv` and
`participants.json` written into `wellbeing_study`, one row per participant.

## 1. Look at the source file

Open `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx`. It has
one row per participant with columns like `participant_id`, `session`,
`age`, `sex`, `education`, `handedness`, `WB01`-`WB05`, `completion_date`.
Only the demographic columns matter for this chapter — `WB01`-`WB05` are the
survey items, imported separately in chapter 3.

## 2. Open Converter → Sociodemographics

With `wellbeing_study` loaded, go to **Converter**. The **Sociodemographics**
tab is the default/first tab.

![PRISM Studio Participants converter tab](_static/screenshots/prism-studio-converter-participants.png)

## 3. Select the file and ID column

- Upload `wellbeing.xlsx`. Excel files expose a sheet selector if there's
  more than one sheet.
- **Participant ID Column** defaults to "Auto-detect", which recognizes
  `participant_id` directly here — no need to override it for this file.

## 4. Review Participant Fields

Click **Review Participant Fields** to preview detected columns and sample
values before anything is written. You should see `age`, `sex`, `education`,
`handedness` among the detected fields.

If `WB01`-`WB05` show up as available-but-not-selected columns, leave them
out here — pulling survey items into `participants.tsv` would mix
one-time-per-participant demographics with repeated-measure survey data,
which don't belong in the same file. Use **Add More Columns (Optional)**
only if you want to bring in additional demographic-style columns beyond
what's auto-detected — not for the survey items.

## 5. Create Participant Files

Click **Create Participant Files**. This writes `participants.tsv` and
`participants.json` together — every import path writes both, never just
one. Since neither file exists yet in a fresh project, you won't see the
overwrite warning this time.

Behind the scenes, each `participant_id` value is trimmed, Unicode-normalized,
had any leading `sub-` stripped, then non-alphanumeric characters removed,
and re-prefixed with `sub-` — so a source ID like `DEMO001` becomes
`sub-DEMO001` in the output. IDs are sanitized, never renumbered.

## Common mistakes

- **Including `WB01`-`WB05` as participant fields** — they're repeated
  survey responses, not one-time demographics; keep them out of
  `participants.tsv` and import them via the Survey converter in chapter 3
  instead.
- **Re-running this step later without noticing the overwrite warning** — if
  `participants.tsv`/`.json` already exist, you'll be asked to confirm before
  they're overwritten; read that warning rather than clicking through it.
- **Expecting raw demographic codes to be relabeled automatically** — there
  is no value-recoding step here. Raw values (e.g. a numeric sex code) are
  preserved as-is in `participants.tsv`; labeling what a code means happens
  separately via the "Participant Annotation" panel into `participants.json`,
  and turning coded values into readable labels project-wide is covered by
  the optional participant-mapping workflow (see
  `examples/workshop/exercise_5_participant_mapping/` for a worked example) —
  not required for this tutorial.

## What's next

- [Chapter 3 — Import a survey via Excel](TUTORIAL_BEGINNER_3_SURVEY_IMPORT.md)
- [Converter — Participants](studio/converter_participants.md) — full
  reference for this screen
