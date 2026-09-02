# Chapter 3: Import Survey Response Data

Chapter 3 of [Getting Started — Your First PRISM Project](TUTORIAL_BEGINNER.md).
This is about turning the five wellbeing-survey columns (`WB01`-`WB05`) in
`wellbeing.xlsx` into real survey response files inside your project. It has
two parts: getting a survey **template** in place (the JSON that describes
what the instrument and its items are), then actually **importing the
response data** against that template.

```{tip}
This tutorial's running example happens to be an Excel workbook, but Survey
Import isn't an Excel-only feature. The Converter accepts `.xlsx`, `.csv`,
`.tsv`, `.sav` (SPSS), `.rds`/`.rdata`/`.rda` (R), and `.lsa` (LimeSurvey
Archive) — see the format note in Part B, step 3.
```

**Time:** ~25 minutes. **Outcome:** survey response files for every
participant, written into subject-level folders under `wellbeing_study`.

<div class="prism-persona-note" data-persona-note>
<p class="prism-persona-note-empty" data-persona-empty>Picked a persona on the <a href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">intro page</a>? This note speaks to it.</p>

<div class="prism-persona-note-content" data-persona="student" hidden>
<span class="prism-persona-note-badge">👩🏽‍🎓 The enthusiastic student <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

*Demographics were the easy part. This is the chapter where "FAIR" actually
gets tested.* This is where PRISM stops treating your survey responses as
"just another spreadsheet" and starts treating them as documented,
scoreable instrument data — the difference between a file and a shareable
dataset.

</div>

<div class="prism-persona-note-content" data-persona="pi" hidden>
<span class="prism-persona-note-badge">👨🏿‍🔬 The skeptical PI <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

*You've watched three different students write three different one-off
import scripts for the same questionnaire over the years, each one leaving
with them.* This is the chapter where that stops: every instrument gets a
template now, saved in the project, not on anyone's laptop.

</div>

<div class="prism-persona-note-content" data-persona="future" hidden>
<span class="prism-persona-note-badge">🧑🏻 Future-you <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

*Of everything in this tutorial, this chapter is the one future-you will be
most grateful for.* `WB01`-`WB05` mean nothing on their own eighteen months
from now — the template you attach here is what makes them mean something
again.

</div>
</div>

## Part A — Get a template

A survey import needs a template to map columns against. There are two ways
to get one; do whichever suits you, then move on to Part B either way.

### Fast path: use the ready-made template

Copy `examples/workshop/exercise_4_templates/survey-wellbeing.json` into
your project at `code/library/survey/survey-wellbeing.json` (create the
`survey/` subfolder if it doesn't exist yet). That's it — this file already
defines everything the import needs:

- `Study.TaskName`: `wellbeing`
- Five items, `WB01`-`WB05`, each with a 6-point response scale (0-5) and
  bilingual (en/de) labels
- Citation and license info for the underlying instrument (a WHO-5 adaptation)

Open **Template Editor** → Modality `survey` → Project Templates and confirm
`wellbeing` now shows up there, to check the copy landed correctly.

### Alternative: build your own template from a spreadsheet

If you'd rather practice authoring a template yourself instead of using the
ready-made one — useful once you have your own instrument, not just this
tutorial's example — follow [Excel Survey Template —
Basics](EXCEL_TEMPLATE_BASICS.md) end to end, using its own example workbook.
That tutorial covers the `Items`/`General` workbook format and the Template
Editor import flow in full detail; there's no need to repeat it here. Come
back to this page for Part B once you have a saved template either way.

## Part B — Import the response data

### 1. Open Converter → Survey

![PRISM Studio Survey converter tab](_static/screenshots/prism-studio-converter-survey.png)

### 2. Choose the source file

Select `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx` as
the **Survey File**.

```{tip}
The same folder also has `wellbeing.tsv` — the identical data as a plain
tab-separated file. If you'd rather try the CSV/TSV path than Excel, select
that file instead: a **Separator** dropdown appears for delimited files
(auto-detect gets tab-separated files right, so you shouldn't need to
change it). Everything from here on works the same either way — the two
files convert to the same output.
```

### 3. Confirm the required mapping

- **Participant ID Column** — select `participant_id` explicitly rather than
  relying on auto-detect (auto-detect is tuned for files already exported by
  PRISM; a plain spreadsheet like this one is safer to map by hand).
- **Session Column (optional)** — select `session` (the source file has one,
  with the same value `baseline` for every row).
- **Session ID \*** (required) — type `baseline` to match the data. Only one
  session converts per run — this file only has one, so you're done here.

Leave **Advanced options** collapsed — this file only contains one
instrument, so there's nothing to narrow down.

### 4. Preview (dry-run)

Click **Preview**. This runs the conversion against a temporary location
without touching your project — check that it reports 20 participants
found, task `wellbeing` included, and no missing items. (You'll also see a
note about one unmapped column, `sleep` — that's expected: it isn't part of
the `wellbeing` template, so Survey Import ignores it. Unmapped columns are
only a problem if a column you *expected* to be picked up is missing.) Fix
the mapping in step 3 and re-preview if anything looks off before moving
on.

### 5. Convert

Click **Convert**. This writes the real output, e.g.:

```text
sub-DEMO001/ses-baseline/survey/sub-DEMO001_ses-baseline_task-wellbeing_survey.tsv
sub-DEMO002/ses-baseline/survey/sub-DEMO002_ses-baseline_task-wellbeing_survey.tsv
...
task-wellbeing_survey.json
```

one `.tsv` per participant, but **one shared `.json` sidecar** at the
dataset root rather than one per participant — this is BIDS's inheritance
principle: a root-level sidecar applies to every matching file below it
unless a more specific one overrides it, and PRISM writes it this way
deliberately to avoid 20 identical copies of the same item descriptions.
If you used the fast-path template (already project-local), no extra copy
step happens on Convert; if the template had come from the official/global
library instead, Convert would copy it into `code/library/survey/`
automatically at this point.

<div class="prism-persona-note" data-persona-note>
<p class="prism-persona-note-empty" data-persona-empty>Picked a persona on the <a href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">intro page</a>? This note speaks to it.</p>

<div class="prism-persona-note-content" data-persona="student" hidden>
<span class="prism-persona-note-badge">👩🏽‍🎓 The enthusiastic student <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

Raw numbers per item, per participant, documented and typed. It's still not
a "score" yet, though — that's the whole point of Chapter 4.

</div>

<div class="prism-persona-note-content" data-persona="pi" hidden>
<span class="prism-persona-note-badge">👨🏿‍🔬 The skeptical PI <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

Instrument responses, templated and traceable back to their source
instrument's citation and license. Next chapter turns them into the number
that actually goes in a results table.

</div>

<div class="prism-persona-note-content" data-persona="future" hidden>
<span class="prism-persona-note-badge">🧑🏻 Future-you <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

Every response file now carries its own item labels and scale range with
it. You could open this in five years and still know what a `3` meant.

</div>
</div>

## Beyond spreadsheets: SPSS, R, and LimeSurvey

Everything above works the same for the other five formats Survey Import
accepts:

- **SPSS** (`.sav`) and **R** (`.rds`, `.rdata`, `.rda`) — select the file the
  same way; PRISM reads the labelled/typed columns directly. See
  [Converter — Survey Import](studio/converter_survey.md) for format-specific
  notes.
- **LimeSurvey** (`.lsa`, a LimeSurvey Archive export) — this is different
  enough from a plain spreadsheet (it carries its own question/answer
  structure) that it gets its own walkthrough: see
  [LimeSurvey Integration](LIMESURVEY_INTEGRATION.md).

## Common mistakes

```{warning}
**Importing before a `wellbeing` template exists in the project.** Part A
has to come first; if you skip straight to Part B, the converter won't know
how to type or label `WB01`-`WB05`.
```

```{warning}
**Item columns that don't match the template's `ItemID`s.** The template
expects exactly `WB01`-`WB05`; renamed or extra columns in a modified source
file will show up as missing/unmapped items in Preview.
```

```{note}
**A failed Preview isn't a broken file — it's the whole point of Preview.**
Adapted from the *PRISM without Panic* guide (ANC Salzburg). The most common
reasons a dry-run comes back with problems: the column names in your file
don't match the template's item keys; the participant ID column wasn't
detected correctly; session information was selected incorrectly; or the
file's format/delimiter wasn't read as expected. If the message specifically
mentions unmatched columns: open the **Template Editor**, find your survey
under Global or Project Templates, and use its read-only item view to
compare item names against your file's column headers — then fix the
naming in *your* spreadsheet, not the template, unless the template is
genuinely wrong. Re-run Preview once the names line up.
```

```{warning}
**Forgetting only one session converts per run.** If your own future data
has more than one session value in the same file, you'll need one Convert
pass per session, not one pass for everything.
```

```{warning}
**Running Convert without a participant registry yet.** If you skipped
[Chapter 2](TUTORIAL_BEGINNER_2_PARTICIPANTS.md) and `participants.tsv`
doesn't exist yet, you'll see a registry warning for IDs not already known
to the project; do Chapter 2 first.
```

## What's next

- [Chapter 4 — Prepare a recipe](TUTORIAL_BEGINNER_4_RECIPE.md)
- [Converter — Survey Import](studio/converter_survey.md) — full reference
  for this screen
- [Excel Survey Template — Basics](EXCEL_TEMPLATE_BASICS.md) /
  [— Multiple Versions](EXCEL_TEMPLATE_ADVANCED.md) — the deeper
  template-authoring tutorials referenced in Part A
