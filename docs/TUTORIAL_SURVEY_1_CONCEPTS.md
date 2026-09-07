# Chapter 1: Survey Concepts You Need First

**Time:** ~15 minutes | **Outcome:** a clear grasp of official vs.
project-local templates — including exactly what happens when you save one
— and a fresh scratch project ready for Chapter 2.

```{mermaid}
flowchart LR
    A["📚 official/library/survey/<br/>shared instrument"] --> B["🛠️ Template Editor<br/>loads it"]
    B -- "Save to Project" --> C["🗂️ code/library/survey/<br/>this project's fork"]
```

## If you haven't done the Beginner tutorial

You don't need to have completed [Getting Started](TUTORIAL_BEGINNER.md) to
follow this series, but a couple of its concepts will make the next six
chapters click faster: a PRISM project stores everything under a
`sub-*/ses-*/<modality>/` layout, and survey response data eventually lands
in `sub-*/ses-*/survey/`. `participant_id` is the value that ties a
participant's survey answers to every other modality collected for them.
Treat the Beginner tutorial as optional background, not a prerequisite —
come back to it any time.

## Official vs. project-local templates

Every survey template in PRISM lives in one of two places, and mixing them
up is the single most confusing thing about the Template Editor if nobody
tells you about it up front:

- `official/library/<modality>/` holds shared, reusable instrument
  definitions — think of this as *what a validated, licensed questionnaire
  actually is*, independent of any one study.
- `code/library/<modality>/` holds **this project's own copy** — the one
  actually used for import/export in that project.

**The Template Editor always forks on save.** Load a Global (official)
template and click **Save to Project**, and PRISM writes a brand-new copy
into `code/library/<modality>/`. It never overwrites the official one — the
original in `official/library/` is read-only from the Template Editor's
point of view. Consistent with that, the **Delete** button is hidden
entirely for anything that isn't project-local; you can't delete a shared
official template from inside a project, only your own project's fork of
one.

```{important}
This project/official split is exactly why editing "the same" template in
two different projects never collides. Both projects can load the same
official template, and both get their own independent fork in their own
`code/library/<modality>/` the moment either one saves — there's no shared
mutable copy for two projects to step on.
```

## What a template actually is

A template is a JSON file matching PRISM's `survey.schema.json`. The Excel
workbook you'll use in Chapter 2 is *one* authoring format for producing
that JSON — a convenient one, not the format itself. You could just as
easily hand-write the JSON directly, or import an existing instrument from
LimeSurvey XML. Keep that in mind as you go through Chapter 2: you're
learning the Excel path because it's the easiest way in, not because it's
the only way in.

## The scenario: Recovery Check-In

Across this tutorial series you'll build a fictional exercise-recovery
study called **Recovery Check-In**. It has a **Full** version — a 10-item
evening, post-training-session check-in covering mood, soreness, sleep
quality, motivation, stress, fatigue, appetite, hydration, and satisfaction
(all 5-point Likert items), plus a pain intensity item on a 0–100 VAS
(visual analogue scale) — and a **Short** version, a 5-item same-day quick
follow-up (mood, soreness, pain intensity, fatigue, sleep quality) that's a
true subset of the Full item set. Later chapters make the study bilingual,
English and German. For now, all you need is the project it will live in.

## Set up a scratch project

From the Studio landing page, **Create or Open a Project** → **Create New
Project**:

- **Project Name**: `recovery_check_in_demo`
- **Use DataLad version control**: check it if you have DataLad installed
  (see [DATALAD](DATALAD.md)) — optional, not required for anything in this
  series.
- Fill in the other required fields as in
  [Chapter 1](TUTORIAL_BEGINNER_1_NEW_PROJECT.md) of the Beginner tutorial
  and create the project.

Leave it open — nothing you do in this tutorial touches any project you
already have, and every later chapter in this series assumes
`recovery_check_in_demo` is the project you have open.

## What you just did

You learned where PRISM keeps shared instrument definitions versus your own
project's working copies, and why saving from the Template Editor always
forks rather than overwrites. You also created the `recovery_check_in_demo`
scratch project that the rest of this series builds on.

## What's next

- [Chapter 2: Prepare a New Questionnaire in Excel](TUTORIAL_SURVEY_2_EXCEL_TEMPLATE.md) —
  fill in the Recovery Check-In Full version and import it
- [Author a Survey](TUTORIAL_SURVEY.md) — back to the series overview
- [Templates](TEMPLATES.md) — the full reference for the template JSON
  model this chapter introduced
