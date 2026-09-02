# Getting Started — Your First PRISM Project

A self-paced, start-from-zero walkthrough for someone who has never opened
PRISM Studio before. Six chapters take you from an empty folder through
building and scoring a project, then applying the same workflow to an existing
BIDS dataset, using one running example so you never have to switch mental
models mid-tutorial.

This sits alongside another on-ramp:
[Workshop](WORKSHOP.md) is the same core journey packaged for a live,
instructor-led session. Use this tutorial if you want the most explanation and
plan to work through it alone.

**Time:** ~100 minutes for all six chapters. **Outcome:** one new project
(`wellbeing_study`) with sociodemographic data, imported survey responses, a
working scoring recipe, validated — plus experience enriching an existing BIDS
dataset with the same tools.

## Pick a reason to be here

None of this affects the instructions below — skip it entirely if you'd
rather just get started. But six chapters go down easier with a "why"
attached. **Click one to select it** — your pick is remembered (in this
browser only) and the chapters ahead will call back to it directly:

<div class="prism-persona-grid" id="prismPersonaGrid">

<div class="prism-persona-card" data-persona="student" role="button" tabindex="0" aria-pressed="false">
<span class="prism-persona-card-check" aria-hidden="true">&check;</span>
<div class="prism-persona-card-header">
<span class="prism-persona-icon">👩🏽‍🎓</span>
<span class="prism-persona-title">The enthusiastic student</span>
</div>
<span class="prism-persona-text">

You're a grad student who just read your program's data-sharing policy and
realized "FAIR" isn't optional anymore. `wellbeing_study` is your first real
attempt at building something reusable from day one — sloppy folder
structures, undocumented column codes, and datasets nobody can open two
years from now are exactly what you're trying to avoid.

</span>
</div>

<div class="prism-persona-card" data-persona="pi" role="button" tabindex="0" aria-pressed="false">
<span class="prism-persona-card-check" aria-hidden="true">&check;</span>
<div class="prism-persona-card-header">
<span class="prism-persona-icon">👨🏿‍🔬</span>
<span class="prism-persona-title">The skeptical PI</span>
</div>
<span class="prism-persona-text">

Three years ago a collaborator sent you a folder of Excel files with columns
named `V1`, `V2`, `Sex (1=M?)`, and no codebook — it cost you a week and a
resubmission. Every project in your lab goes through PRISM before anyone
touches the data now, no exceptions. `wellbeing_study` is the newest one,
walked through end-to-end so you can see exactly where the process pays for
itself.

</span>
</div>

<div class="prism-persona-card" data-persona="future" role="button" tabindex="0" aria-pressed="false">
<span class="prism-persona-card-check" aria-hidden="true">&check;</span>
<div class="prism-persona-card-header">
<span class="prism-persona-icon">🧑🏻</span>
<span class="prism-persona-title">Future-you</span>
</div>
<span class="prism-persona-text">

It's eighteen months from now. A reviewer wants your raw data, or you need
to reanalyze `wellbeing_study` for a follow-up, and you have exactly one
sentence of memory left about what "handedness" was coded as. Everything in
this tutorial is what today-you does so that future-you doesn't have to
guess.

</span>
</div>

</div>

<p class="prism-persona-hint" id="prismPersonaHint">Pick one — chapters ahead will speak to it.</p>

<div class="prism-chapter-grid">
  <a class="prism-chapter-card" href="TUTORIAL_BEGINNER_1_NEW_PROJECT.html">
    <span class="prism-chapter-icon">1</span>
    <span class="prism-chapter-title">Create a Project</span>
    <span class="prism-chapter-outcome">A correctly-structured PRISM project with complete required metadata</span>
    <span class="prism-chapter-time">~15 min</span>
  </a>
  <a class="prism-chapter-card" href="TUTORIAL_BEGINNER_2_PARTICIPANTS.html">
    <span class="prism-chapter-icon">2</span>
    <span class="prism-chapter-title">Import Sociodemographic Data</span>
    <span class="prism-chapter-outcome"><code>participants.tsv</code> / <code>participants.json</code></span>
    <span class="prism-chapter-time">~20 min</span>
  </a>
  <a class="prism-chapter-card" href="TUTORIAL_BEGINNER_3_SURVEY_IMPORT.html">
    <span class="prism-chapter-icon">3</span>
    <span class="prism-chapter-title">Import Survey Response Data</span>
    <span class="prism-chapter-outcome">Survey response files written into subject folders</span>
    <span class="prism-chapter-time">~25 min</span>
  </a>
  <a class="prism-chapter-card" href="TUTORIAL_BEGINNER_4_RECIPE.html">
    <span class="prism-chapter-icon">4</span>
    <span class="prism-chapter-title">Prepare a Recipe</span>
    <span class="prism-chapter-outcome">A saved, working scoring recipe and its output</span>
    <span class="prism-chapter-time">~15 min</span>
  </a>
  <a class="prism-chapter-card" href="TUTORIAL_BEGINNER_5_VALIDATOR.html">
    <span class="prism-chapter-icon">5</span>
    <span class="prism-chapter-title">Use the Validator</span>
    <span class="prism-chapter-outcome">Validation findings understood and resolved</span>
    <span class="prism-chapter-time">~20 min</span>
  </a>
  <a class="prism-chapter-card" href="TUTORIAL_BEGINNER_6_EXISTING_BIDS.html">
    <span class="prism-chapter-icon">6</span>
    <span class="prism-chapter-title">Enrich an Existing BIDS Dataset</span>
    <span class="prism-chapter-outcome">Same workflow applied to a published OpenNeuro dataset</span>
    <span class="prism-chapter-time">~15 min</span>
  </a>
</div>

## Prerequisites

- PRISM Studio installed and launchable — see [Installation](INSTALLATION.md)
  if you haven't done this yet.
- No prior PRISM knowledge assumed. No prior BIDS knowledge assumed either;
  the chapters explain BIDS-specific terms (`sub-`, sessions, sidecars) as
  they come up.

## One running example, start to finish

Every chapter uses the same fictional dataset, already included in the
repository under `examples/workshop/` — you don't need to create or download
anything extra:

- `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx` — one
  spreadsheet with both demographic columns (age, sex, education,
  handedness) and five wellbeing-survey items (`WB01`-`WB05`) for the same
  fake participants. Chapter 2 uses the demographic columns; chapter 3 uses
  the survey items.
- `examples/workshop/exercise_4_templates/survey-wellbeing.json` — a
  ready-made survey template for the instrument used in chapter 3.
- `examples/workshop/exercise_3_using_recipes/recipe-wellbeing.json` — a
  working scoring recipe used as the worked example in chapter 4.

These are the same materials used by [Workshop](WORKSHOP.md) — if you've
already done that workshop, the data will look familiar, but this tutorial
explains each step in far more detail and at your own pace.

## What's next

Once you've completed all six chapters, an **Intermediate** tutorial
covering DataLad version control and bulk file/folder manipulation is
planned as the next step in this series — check back here once it's
published. In the meantime:

- [Studio Guide](studio/index.md) — full reference for every screen
- [CLI Reference](CLI_REFERENCE.md) — the same workflows from the terminal
- [Workshop](WORKSHOP.md) — the same journey as a guided group exercise
