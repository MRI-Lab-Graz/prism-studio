# Tutorial Router and Screenshot Density — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "where do I start?" router to the top of the beginner tutorial so a reader with a specific artifact in hand (survey data to import, an existing BIDS dataset, a questionnaire to author) doesn't have to guess which of PRISM's two parallel tutorial tracks covers their case. Separately, correct this plan's own scope on checkpoint density after finding it was based on an incomplete first pass, and leave a precisely-specified, verified-safe slice of screenshot work plus a scoped-out list for what still needs a live Studio instance.

**Architecture:** A compact table inserted near the top of `docs/TUTORIAL_BEGINNER.md`, above the existing persona picker. No new files, no toctree changes.

**Tech Stack:** MyST Markdown; the existing Playwright capture script (`scripts/capture_studio_docs_screenshots.py`) for any new screenshots.

**Spec:** `docs/superpowers/specs/2026-09-12-documentation-expansion-design.md`, Sections E2 and E3.

## Why E3's scope changed while writing this plan

The spec's E3 (screenshot and checkpoint density) was written assuming both
halves were equally underserved. Reading all six beginner chapters in full
while starting this plan found that's only true for one half:

- **Checkpoint density is already strong** — it just doesn't use the literal
  phrase this plan's own spec-writing pass searched for ("you should now
  see"). Real, working checkpoint mechanisms already exist throughout: a
  deliberate dry-run preview step before every real write (Ch. 2 step 5,
  Ch. 3 step 4), a deliberate "inject an error, see it caught, fix it,
  re-validate" exercise (Ch. 5 step 5) — a stronger checkpoint than a
  passive sentence would be — a shipped comparison file to check your own
  saved output against (Ch. 4 step 6), and a "Common mistakes" section
  closing every chapter. Adding generic "you should now see X" sentences on
  top of this would be padding, not improvement — the same lesson the
  Global Settings plan drew from over-trusting line counts and dates for
  Section D1.
- **Screenshot density is a real, confirmed gap.** Counted directly:
  Chapters 2-6 average roughly one screenshot each across 200-270 lines and
  5-7 interactive steps per chapter; Chapter 6 has zero. This part of E3
  stands.

So this plan delivers E2 in full, corrects the checkpoint half of E3 in the
spec, and scopes the screenshot half of E3 down to what can actually be
verified without starting a live Studio instance and running a browser
against it in this session — a bigger, riskier action than anything else in
this documentation project, and one this plan does not take unprompted.
Task 2 below is a precise specification for whoever does have a running
instance, not fabricated Playwright selector code guessed from templates
that were never exercised live.

## Global Constraints

- The RTD build must stay green: `cd docs && python3 -m sphinx -b html -W --keep-going . <outdir>` (matches `.readthedocs.yaml`'s `fail_on_warning: true`).
- Markdown cross-page links use `.md`, not `.html` (verified house convention; see the signing-and-chapter-zero plan's Global Constraints for the failure mode this causes).
- This plan runs after the signing-and-chapter-zero plan (Plan 2 in this
  series), which adds a Chapter 0 to `docs/TUTORIAL_BEGINNER.md`'s chapter
  grid and rewrites its Prerequisites section. The edits below target the
  page as Plan 2 leaves it, not the page's state before Plan 2 — if Plan 2
  has not yet run, apply it first (its Task 3), since otherwise the
  "Nothing installed yet is fine" Prerequisites text this plan does not
  touch would be missing and a reader following the router's "keep reading
  below" fallback would land on old text.
- Git commit messages end with: `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`

---

### Task 1: Add the "Where do I start?" router

**Files:**
- Modify: `docs/TUTORIAL_BEGINNER.md` (insert a new section between the
  opening Time/Outcome paragraph and "## Pick a reason to be here")

**Interfaces:** None — self-contained content addition. Links to
`TUTORIAL_BEGINNER_3_SURVEY_IMPORT.md`, `TUTORIAL_BEGINNER_6_EXISTING_BIDS.md`,
`TUTORIAL_SURVEY.md`, and (assuming Plan 2 has run)
`TUTORIAL_BEGINNER_0_INSTALL.md`, none of which this task creates.

Routing verified against each target's own stated scope, not guessed:

- **Survey response data to import** (a LimeSurvey export or an Excel/CSV/
  TSV/SPSS/R file of *responses*, not an instrument definition) — routes to
  Chapter 3. Verified: Chapter 3's own opening tip
  (`docs/TUTORIAL_BEGINNER_3_SURVEY_IMPORT.md`) states outright "Survey
  Import isn't an Excel-only feature. The Converter accepts `.xlsx`, `.csv`,
  `.tsv`, `.sav` (SPSS), `.rds`/`.rdata`/`.rda` (R), and `.lsa` (LimeSurvey
  Archive)." A LimeSurvey export and an Excel sheet of response data are the
  same case from the reader's point of view (both need Chapters 1-2 done
  first to have a project and participants to import against), so both
  route to the same place rather than being artificially split.
- **An existing BIDS dataset to enrich** — routes to Chapter 6
  (`TUTORIAL_BEGINNER_6_EXISTING_BIDS.md`), which is exactly this scenario
  already.
- **No data yet — need to build a questionnaire/instrument from scratch** —
  routes to the separate `TUTORIAL_SURVEY.md` series. Verified: that page's
  own text states "This series stands on its own: no [Getting Started]
  tutorial is required first," so this is a genuine, independent entry
  point, not a dead end.
- **Starting from zero, no specific artifact in hand** — the default case,
  routes to Chapter 0 (assumes Plan 2 has run; see Global Constraints).

- [ ] **Step 1: Insert the router**

Find:
```
**Time:** ~130 minutes for all six chapters (most of the added time is
hands-on practice, plus Chapter 6's dataset download). **Outcome:** one new
project
(`wellbeing_study`) with sociodemographic data, imported survey responses, a
working scoring recipe, validated — plus experience enriching an existing BIDS
dataset with the same tools.

## Pick a reason to be here
```

Replace with:
```
**Time:** ~130 minutes for all six chapters (most of the added time is
hands-on practice, plus Chapter 6's dataset download). **Outcome:** one new
project
(`wellbeing_study`) with sociodemographic data, imported survey responses, a
working scoring recipe, validated — plus experience enriching an existing BIDS
dataset with the same tools.

## Where do I start?

Six chapters go in order and use one shared example — but if you already
have something specific in hand, jump straight to the chapter that covers
it instead:

| You have | Start at |
|---|---|
| A LimeSurvey export to import | [Chapter 3](TUTORIAL_BEGINNER_3_SURVEY_IMPORT.md) — survey import covers LimeSurvey, Excel, CSV, SPSS, and R alike |
| An Excel sheet of response data to import | [Chapter 3](TUTORIAL_BEGINNER_3_SURVEY_IMPORT.md), same page as above |
| An existing BIDS dataset to enrich | [Chapter 6](TUTORIAL_BEGINNER_6_EXISTING_BIDS.md) |
| No data yet — you need to build a questionnaire/instrument from scratch | [Author a Survey](TUTORIAL_SURVEY.md), a separate tutorial series with no PRISM knowledge required first |

Chapters 3 and 6 both assume a project already exists. Starting completely
from zero? Begin at [Chapter 0](TUTORIAL_BEGINNER_0_INSTALL.md) below and
work through in order instead.

## Pick a reason to be here
```

- [ ] **Step 2: Verify**

Run:
```bash
grep -n "## Where do I start" docs/TUTORIAL_BEGINNER.md
cd docs && python3 -m sphinx -b html -W --keep-going . /tmp/prism_docs_build_check && echo BUILD_OK
```
Expected: the heading is found, `build succeeded.`, `BUILD_OK`.

- [ ] **Step 3: Commit**

```bash
git add docs/TUTORIAL_BEGINNER.md
git commit -m "docs: add a 'where do I start?' router to the beginner tutorial

Routes a reader who already has a specific artifact (LimeSurvey export,
Excel response data, an existing BIDS dataset, or a from-scratch
questionnaire to author) directly to the chapter or tutorial series that
covers it, instead of requiring six chapter titles to be read and guessed
at. Each destination verified against its own stated scope.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Screenshot gap list (specification only — needs a live Studio instance to execute)

**Files:** None modified by this task. This task produces a prioritized,
precise specification for a follow-up task, not a code change — see "Why
E3's scope changed" above for why this plan stops here rather than writing
unverified Playwright capture code.

**Interfaces:** Whoever executes this consumes
`scripts/capture_studio_docs_screenshots.py`'s existing patterns
(`SIMPLE_PROJECT_SHOTS` for a static page load, `capture_validator_shots`
for a multi-step interaction sequence with real clicks and waits) as the
two implementation templates to follow.

Verified counts (2026-09-12): Chapter 1 has 4 screenshots across 6 numbered
steps; Chapters 2, 3, 4, 5 have 1 screenshot each across 5-7 steps;
Chapter 6 has 0 across 3 steps. Below is where a new screenshot would
capture the tutorial's own existing teaching moment, in priority order —
each is an *interactive* mid-workflow state (a filled form, a preview
table, a caught error), which is exactly the kind of screenshot this
tutorial is missing, and exactly the kind that requires exercising the
real, running app to get right (selectors, wait conditions, and timing
that only a live Studio instance can confirm).

1. **Chapter 3, step 4 (Preview / dry-run results)** — highest priority.
   This is the tutorial's own designated checkpoint step ("catch
   column-mapping problems before anything is written"); a screenshot of
   the populated preview (participants found, tasks included, the expected
   "unmapped column: sleep" note) would show a reader exactly what
   "looking right" means before they click Convert for real.
2. **Chapter 5, step 5 ("See an error, then clear it")** — the tutorial's
   deliberate error-injection exercise; a screenshot of the validator
   results view actually showing the injected error would make this
   teaching moment concrete instead of purely textual.
3. **Chapter 2, step 5 (Review Participant Fields)** — the detected-columns
   preview table before any file is written.
4. **Chapter 4, step 4 (built Scale Canvas)** — the `Total` score
   definition (Name/Method/Items/Range) actually filled in, so a reader can
   compare their own screen against a real example before saving.
5. **Chapter 6** — currently zero screenshots across all three steps; the
   Init-on-BIDS screen and the Merge conflict-resolution view (step 1)
   would be the two highest-value additions.

To execute: start Studio (`python prism-studio.py`) against the same
`examples/workshop/` fixture the tutorial itself uses, extend
`scripts/capture_studio_docs_screenshots.py` with a dedicated capture
function per item above (following `capture_validator_shots`'s pattern of
real `page.click()`/`page.fill()` calls against the live DOM, not the
static-route `SIMPLE_PROJECT_SHOTS` pattern, since every item above needs
real interaction first), confirm each screenshot actually shows what's
described above by opening the resulting PNG, then add the corresponding
`![...](...)` reference to the matching chapter and commit both the script
change and the new image together.

- [ ] **Step 1: File this list where it will actually get picked up**

This step has no shell commands — it's a judgment call for whoever is
running this plan. If your workflow has an issue tracker, backlog, or
`ROADMAP.md`-style document for this repo, add an entry there linking back
to this section (`docs/superpowers/plans/2026-09-12-docs-tutorial-router-
and-screenshots.md`, Task 2) rather than letting it live only in a plan
file that stops being read once Task 1 ships. If no such tracker exists for
this repo, leave it here and say so explicitly when reporting this plan's
completion — do not silently mark it done.

---

## Plan-level verification

```bash
cd docs && python3 -m sphinx -b html -W --keep-going . /tmp/prism_docs_build_check && echo BUILD_OK
grep -n "## Where do I start" docs/TUTORIAL_BEGINNER.md
```

Expected: `BUILD_OK`, and the router section present. Read
`docs/TUTORIAL_BEGINNER.md` top to bottom once — the router should read as
a natural, brief detour before the persona picker, not compete with it for
attention.
