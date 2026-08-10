# Chapter 2: Import Sociodemographic Data

Chapter 2 of [Getting Started — Your First PRISM Project](TUTORIAL_BEGINNER.md).
This chapter imports information about the people who take part in a study,
such as age, sex, education, and handedness. It does not import their survey
responses from the same source spreadsheet; those come in chapter 3.

```{important}
**Data and its description belong together.** This is a crucial PRISM and BIDS
convention: a TSV data table stores the recorded values, and a matching JSON
file explains what its columns and values mean. The two files are a pair, not
alternatives to each other. You will use this same TSV/JSON pattern throughout
PRISM for surveys, biometrics, study environment data, and other documented
tables.
```

In this chapter, `participants.tsv` is a table with one row for each person.
`participants.json` explains columns such as `participant_id`, `age`, and
`sex`, including any codes used in the table.

**Time:** ~15 minutes. **Outcome:** a matching `participants.tsv` and
`participants.json` pair written into `wellbeing_study`.

<div class="prism-persona-note" data-persona-note>
<p class="prism-persona-note-empty" data-persona-empty>Picked a persona on the <a href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">intro page</a>? This note speaks to it.</p>

<div class="prism-persona-note-content" data-persona="student" hidden>
<span class="prism-persona-note-badge">👩🏽‍🎓 The enthusiastic student <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

*The empty scaffold from Chapter 1 is still just a promise. This is where
it becomes a real dataset.* `age`, `sex`, `education`, `handedness` — plain
columns today, but properly typed and documented, they're fields a reviewer
or reuser will actually be able to trust without emailing you to ask what
they mean.

</div>

<div class="prism-persona-note-content" data-persona="pi" hidden>
<span class="prism-persona-note-badge">👨🏿‍🔬 The skeptical PI <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

*This is the exact step your last collaborator skipped.* Their `sex` column
was an undocumented `1`/`2` code nobody could interpret two years later —
watch how little extra effort it takes to not repeat that.

</div>

<div class="prism-persona-note-content" data-persona="future" hidden>
<span class="prism-persona-note-badge">🧑🏻 Future-you <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

*The empty project from Chapter 1 gets its first real content here — and
its first permanent naming decision.* You won't remember what `DEMO001`
meant either, but `sub-DEMO001`, sanitized and consistent, is at least
something you can grep for.

</div>
</div>

## 1. Look at the source file

Open `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx`. It has
one row per participant with columns like `participant_id`, `session`,
`age`, `sex`, `education`, `handedness`, `WB01`-`WB05`, `completion_date`.
Only the demographic columns matter for this chapter — `WB01`-`WB05` are the
survey items, imported separately in chapter 3.

```{tip}
This tutorial uses an Excel (`.xlsx`) workbook as an example; it is not an
Excel-only workflow. The Participants converter also accepts CSV (`.csv`), TSV
(`.tsv`), SPSS (`.sav`), R (`.rds`, `.rdata`, `.rda`), and LimeSurvey (`.lsa`)
source files.
```

## 2. Reopen `wellbeing_study`

If Studio is still the same session you created the project in, it's
already loaded — skip to step 3. Otherwise, go to **Project Manager** and
either paste the project's path (e.g. `~/prism_projects/wellbeing_study`)
into **Select project folder or project.json** and click **Load Project**,
or click it under **Recent Projects**, which lists every project you've
created or opened before, de-duplicated by its resolved absolute path.

Each project is assigned a small emoji icon (e.g. 🧬) the first time it's
created or loaded, saved permanently into that project's `project.json`, and
shown next to its name both in Recent Projects and in the header once
loaded — it's just a visual identifier to tell projects apart at a glance,
not a status indicator.

## 3. Open Converter → Sociodemographics

With `wellbeing_study` loaded, go to **Converter**. The **Sociodemographics**
tab is the default/first tab.

![PRISM Studio Participants converter tab](_static/screenshots/prism-studio-converter-participants.png)

## 4. Select the file and ID column

- Upload `wellbeing.xlsx`. Excel files expose a sheet selector if there's
  more than one sheet.
- **Participant ID Column** defaults to "Auto-detect", which recognizes
  `participant_id` directly here — no need to override it for this file.

## 5. Review Participant Fields

Click **Review Participant Fields** to preview detected columns and sample
values before anything is written. You should see `age`, `sex`, `education`,
`handedness` among the detected fields.

If `WB01`-`WB05` show up as available-but-not-selected columns, leave them
out here — pulling survey items into `participants.tsv` would mix
one-time-per-participant demographics with repeated-measure survey data,
which don't belong in the same file. Use **Add More Columns (Optional)**
only if you want to bring in additional demographic-style columns beyond
what's auto-detected — not for the survey items.

## 6. Create Participant Files

Click **Create Participant Files**. This writes `participants.tsv` and
`participants.json` together — every import path writes both, never just
one. Since neither file exists yet in a fresh project, you won't see the
overwrite warning this time.

Behind the scenes, each `participant_id` value is trimmed, Unicode-normalized,
had any leading `sub-` stripped, then non-alphanumeric characters removed,
and re-prefixed with `sub-` — so a source ID like `DEMO001` becomes
`sub-DEMO001` in the output. IDs are sanitized, never renumbered.

<div class="prism-persona-note" data-persona-note>
<p class="prism-persona-note-empty" data-persona-empty>Picked a persona on the <a href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">intro page</a>? This note speaks to it.</p>

<div class="prism-persona-note-content" data-persona="student" hidden>
<span class="prism-persona-note-badge">👩🏽‍🎓 The enthusiastic student <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

`participants.tsv` and `.json` now exist, and every ID is consistent. The
raw survey codes (`WB01`-`WB05`) are still sitting in `wellbeing.xlsx`
untouched — Chapter 3 is where those actually become data.

</div>

<div class="prism-persona-note-content" data-persona="pi" hidden>
<span class="prism-persona-note-badge">👨🏿‍🔬 The skeptical PI <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

Demographics done properly, five minutes in. Next chapter is where most
labs' ad-hoc import scripts actually live — watch how PRISM replaces that
with something reusable instead.

</div>

<div class="prism-persona-note-content" data-persona="future" hidden>
<span class="prism-persona-note-badge">🧑🏻 Future-you <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

Every participant ID is now sanitized the same way, permanently. That's one
naming scheme you will never have to reverse-engineer later.

</div>
</div>

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
