# University Course Plan

An eight-unit university course that teaches PRISM Studio to complete
beginners, built on the existing tutorials. This page is the instructor's
side: schedule, what to do in each unit, and the Moodle homework for each one.
Students follow the linked chapters; there is no separate course text.

**Format:** 8 units × 3 hours, one unit every 14 days. **Audience:** students
with ordinary computer experience only — no terminal, no BIDS, mostly no
macOS. **Devices:** preinstalled university iMacs (limited access) plus
students' own laptops (macOS or Windows). **Outcome:** each student builds a
complete PRISM project around their own questionnaire — designed,
exported to LimeSurvey, fielded, imported, scored, validated, exported.

## How the course works

- **One thread, one project.** Units 1–4 follow the tutorial's
  `wellbeing_study`, so students see the same screens as the docs. From
  unit 2 each student also invents a *mini-study*; each homework repeats the
  unit's steps on it, so the final project grows unit by unit.
- **GUI first, terminal last.** The terminal appears only as an optional demo
  in unit 8.
- **Fixed unit shape.** 15–20 min recap quiz on the last unit → hands-on
  following the docs, with checkpoints on the board → homework briefing. See
  [Workshop](WORKSHOP.md) for delivery tips (checkpoints on the board,
  red/green cards, recruiting fast finishers).
- **Homework is done at home.** Every student therefore needs a working own
  install before unit 2 (homework 1). Each homework ships a *starter pack*
  (zip on Moodle) so nobody depends on class data. Submissions are a zipped
  project folder and/or a screenshot.
- **Deadlines.** Homework is due 12 days after the unit — two days before the
  next one — so you can spot problems before class. The final submission is
  due 7 days after unit 8.
- **Fallback.** A student who cannot get the app running posts in the
  "I'm stuck" forum (OS, chip, step number, screenshot) and uses a lab iMac.
  Engaging with the fallback counts as full credit for homework 1.

## Overview

| Unit | Topic | Docs | Homework |
|---|---|---|---|
| 1 | Mac basics, BIDS structure, install | [What is PRISM](WHAT_IS_PRISM.md), [Concepts](CONCEPTS.md), [Chapter 0](TUTORIAL_BEGINNER_0_INSTALL.md) | Install + proof it runs |
| 2 | Projects and participants | [Ch. 1](TUTORIAL_BEGINNER_1_NEW_PROJECT.md), [Ch. 2](TUTORIAL_BEGINNER_2_PARTICIPANTS.md) | Mini-study project with participants |
| 3 | Survey import | [Ch. 3](TUTORIAL_BEGINNER_3_SURVEY_IMPORT.md), [Survey 1](TUTORIAL_SURVEY_1_CONCEPTS.md) | Import a messy spreadsheet |
| 4 | Recipes and validator | [Ch. 4](TUTORIAL_BEGINNER_4_RECIPE.md), [Ch. 5](TUTORIAL_BEGINNER_5_VALIDATOR.md) | Fix a broken dataset |
| 5 | Design your own questionnaire | [Survey 2](TUTORIAL_SURVEY_2_EXCEL_TEMPLATE.md), [3](TUTORIAL_SURVEY_3_TEMPLATE_EDITOR.md), [4](TUTORIAL_SURVEY_4_LANGUAGES_SCALES.md) | Validated 10-item questionnaire + proposal |
| 6 | LimeSurvey export | [Survey 6](TUTORIAL_SURVEY_6_LIMESURVEY_EXPORT.md), [LimeSurvey Integration](LIMESURVEY_INTEGRATION.md) | Publish the survey, collect ≥ 8 responses |
| 7 | Real data in: import, score, validate | [LimeSurvey Integration](LIMESURVEY_INTEGRATION.md), [Ch. 4](TUTORIAL_BEGINNER_4_RECIPE.md), [Ch. 5](TUTORIAL_BEGINNER_5_VALIDATOR.md), [File Management](TUTORIAL_FILE_MANAGEMENT.md) | Milestone: scored, validated project |
| 8 | Export, hygiene, peer review, presentations | [Export](studio/export.md), [Data Reference](DATA_REFERENCE.md) | Final submission |

## Unit 1 — Mac basics, BIDS structure, install

**Goal:** students know what PRISM is for, can find their way around macOS
folders, understand the BIDS folder/filename logic, and know how to install
Studio at home.

| Time | Block |
|---|---|
| 0:00 | Welcome, device poll (Mac / Windows, Apple Silicon / Intel), course overview |
| 0:15 | Why PRISM — the before/after story ([What is PRISM](WHAT_IS_PRISM.md)) |
| 0:40 | Mac basics on the lab iMacs: Finder, Downloads vs Documents, creating folders, extracting a zip, showing file extensions, quitting an app. Everyone creates a `prism-course` folder in Documents. |
| 1:10 | Break |
| 1:20 | BIDS structure in depth: `sub-` / `ses-` folders, paired files, naming ([Concepts](CONCEPTS.md)) |
| 1:50 | Install discussion (below), first look at Studio on the preinstalled lab copy |
| 2:30 | Concept quiz and recap |
| 2:45 | Homework briefing: walk through the Moodle assignment live |

**Install discussion** (follow [Chapter 0](TUTORIAL_BEGINNER_0_INSTALL.md)):

1. Download the right file — check the chip first (Apple menu → About This
   Mac); Windows has its own ZIP.
2. Extract before running. Windows: "Extract All", never run from inside the
   zip. Mac: run from the extracted folder. Keep it in Documents, not
   Downloads.
3. Expect the security warning — the build is not code-signed
   ([why](INSTALLATION_SECURITY.md)). Mac: `Prism Studio Installer.app`, or
   right-click → Open. Windows: "More info" → "Run anyway". Show both on your
   own machine or with screenshots.
4. The terminal window *is* the app: closing it quits PRISM Studio.
5. Closing the browser tab does not stop the app.
6. How to ask for help: OS, chip, step number, screenshot.

**Homework 1 — Install (due unit 1 + 12 days).**

1. Install PRISM Studio on your own device following Chapter 0.
2. Upload a screenshot of Studio open in the browser, with
   `localhost:5001` visible in the address bar.
3. Quit and relaunch. Answer in a form: did it open without a warning the
   second time?
4. Device form: OS, Mac chip or Windows, anything that went wrong.
5. Quiz (5 questions, auto-graded): where to extract, what closing the
   terminal window does, what `sub-01` means, …
6. Stuck? Post in the forum and book a lab iMac slot (full credit).

## Unit 2 — Projects and participants

| Time | Block |
|---|---|
| 0:00 | Recap quiz, HW1 problems — resolve every install failure now |
| 0:30 | [Chapter 1](TUTORIAL_BEGINNER_1_NEW_PROJECT.md): create `wellbeing_study` (~15 min), then look at what was created in Finder |
| 1:00 | [Chapter 2](TUTORIAL_BEGINNER_2_PARTICIPANTS.md): participants (~20 min) |
| 1:45 | Mini-study kickoff: each student picks a topic — one sentence, variables, 8 invented participants |
| 2:30 | Homework briefing |

**Homework 2 — Your mini-study (due +12 days).** Repeat Chapters 1–2 on your
own mini-study. Upload a zip of the project folder and a screenshot of its
`participants.tsv`.

## Unit 3 — Survey import

Confirm everyone has Excel or LibreOffice (the lab iMacs may only have
Numbers).

| Time | Block |
|---|---|
| 0:00 | Recap, spreadsheet check |
| 0:20 | [Chapter 3](TUTORIAL_BEGINNER_3_SURVEY_IMPORT.md) (~25 min) with the starter files from `examples/workshop/` |
| 1:00 | [Survey 1 — Concepts](TUTORIAL_SURVEY_1_CONCEPTS.md): what a template and a sidecar are |
| 1:40 | Troubleshooting round: wrong delimiter, missing IDs, mismatched columns |
| 2:30 | Homework briefing |

**Homework 3 — Messy import (due +12 days).** Starter pack: a messy response
spreadsheet. Import it into your mini-study. Upload the project zip plus three
sentences on what you had to fix.

## Unit 4 — Recipes and validator

| Time | Block |
|---|---|
| 0:00 | Recap quiz |
| 0:20 | [Chapter 4](TUTORIAL_BEGINNER_4_RECIPE.md) — scoring recipe (~20 min) |
| 1:00 | [Chapter 5](TUTORIAL_BEGINNER_5_VALIDATOR.md) — validator (~20 min) |
| 1:40 | "Thirteen broken files" detective session in pairs (`examples/workshop/chapter_5_validator/`) |
| 2:30 | Homework briefing |

**Homework 4 — Fix it (due +12 days).** Starter pack: a project with planted
errors. Fix them and upload the clean validator report. Also run a scoring
recipe on your mini-study.

## Unit 5 — Design your own questionnaire

| Time | Block |
|---|---|
| 0:00 | Recap quiz |
| 0:20 | [Survey 2](TUTORIAL_SURVEY_2_EXCEL_TEMPLATE.md): Excel template (~30 min) |
| 0:55 | [Survey 3](TUTORIAL_SURVEY_3_TEMPLATE_EDITOR.md): template editor (~25 min) |
| 1:25 | [Survey 4](TUTORIAL_SURVEY_4_LANGUAGES_SCALES.md): languages and scales — keep short |
| 1:50 | Break |
| 2:00 | Build your own 10-item questionnaire |
| 2:30 | Peer feedback: a neighbour finds one unclear item |

**Homework 5 — Your questionnaire (due +12 days).** Finish and validate the
questionnaire. Upload the template JSON and a one-paragraph study proposal.
Optional: [variants](TUTORIAL_SURVEY_5_VARIANTS.md).

## Unit 6 — LimeSurvey export

| Time | Block |
|---|---|
| 0:00 | Recap; review HW5 questionnaires |
| 0:20 | [Survey 6](TUTORIAL_SURVEY_6_LIMESURVEY_EXPORT.md): Quick vs Customize & Export, grouping, matrix, welcome text. Set the LS version to **6.x** (the university's server). |
| 1:20 | Import the `.lss` into the university LimeSurvey; check; activate a test survey |
| 2:15 | Pilot: fill in each other's surveys, note two problems |
| 2:45 | Homework briefing |

**Homework 6 — Field it (due +12 days).** Fix the problems from the pilot,
publish, and collect at least 8 responses (invented answers are fine).
Upload the `.lss`, a screenshot of the activated survey, and the LimeSurvey
response export (`.lsa`).

## Unit 7 — Real data in

| Time | Block |
|---|---|
| 0:00 | Recap; check everyone has a usable `.lsa` |
| 0:20 | Import the responses ([LimeSurvey Integration](LIMESURVEY_INTEGRATION.md)) |
| 1:10 | Scoring recipe on your own questionnaire, then validate |
| 2:00 | Slim [File Management](TUTORIAL_FILE_MANAGEMENT.md): Filename Renamer, Rename Subject IDs, Undo |
| 2:20 | Clinic: fix whatever the real data broke |

**Homework 7 — Milestone (due +12 days).** Project with real responses,
scored and validated. Upload the zip and the validator report.

## Unit 8 — Export, hygiene, peer review

| Time | Block |
|---|---|
| 0:00 | Export (SPSS/CSV/codebooks, anonymization), README and dataset description ([Export](studio/export.md)) |
| 0:40 | Peer review: swap project zips and validate each other's |
| 1:30 | Presentations, ~5 min each: the study, the questionnaire, one problem, one fix |
| 2:40 | Feedback and reflection. Optional 15-min CLI demo ([CLI Workflows](CLI_WORKFLOWS.md)) |

**Final submission (due unit 8 + 7 days).** Final project zip, a validator
report with no errors, an export, and a half-page reflection.

## Grading suggestion

| Part | Weight |
|---|---|
| Homework 1–7, pass/fail | 40 % |
| Final project | 40 % |
| Peer review and presentation | 20 % |

## Moodle structure

Per unit: a *Before class* block (reading links), an *After class* block (the
assignment and starter pack), and a recap quiz for the next session. One
forum thread per unit ("I'm stuck") for questions — encourage students to
answer each other.

## Windows notes

The course is Mac-first, but every unit has to work on Windows too: file paths
in screenshots differ, and the released ZIP is a `.exe` instead of a `.app`.
Keep Mac-only tricks (Finder shortcuts) out of assignments, and mention the
Windows equivalent (File Explorer, "Extract All") whenever you show one.

## Before the course

- Download the release ZIP on both a Mac and a Windows machine and test it.
- Have screenshots of both security warnings ready.
- Create the Moodle assignments, forum and quizzes.
- **At least one week before unit 6:** do a real round trip on the
  university's LimeSurvey 6 — export from Studio, import the `.lss`, activate
  and fill it in, export the `.lsa`, import it back. (Done once for this
  course; repeat if the server is upgraded.)
- Confirm students can create surveys on the university LimeSurvey, or ask IT
  to enable accounts.

## If you fall behind

Cut in this order: Survey 4 (languages), the variants and the LimeSurvey
extras, the CLI demo, File Management in unit 7. The core path is install →
project → participants → survey import → recipe → validator → own
questionnaire → LimeSurvey → import → export.

Self-study, not taught: [Chapter 6 — existing BIDS](TUTORIAL_BEGINNER_6_EXISTING_BIDS.md),
[Survey 5](TUTORIAL_SURVEY_5_VARIANTS.md), [Survey 7](TUTORIAL_SURVEY_7_VALIDATION.md),
[DataLad](DATALAD.md).
