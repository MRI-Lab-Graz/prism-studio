# Chapter 6: Export to LimeSurvey

**Time:** ~30 minutes | **Outcome:** a real `.lss` file, ready to import into a
LimeSurvey installation, with per-question presentation configured.

```{mermaid}
flowchart LR
    W["📄 survey-recovery.json<br/>(full version)"]
    W --> E["📤 Survey Export"]
    E --> C["🎛️ Customizer<br/>grouping, per-question settings"]
    C --> L["📦 recovery_full_en_de.lss"]
    L -.-> LS["🖥️ LimeSurvey<br/>(not covered here)"]
```

## One export target, not the only one

LimeSurvey gets this chapter because it's the one delivery tool fully
wired into Studio today — a real export button, no code to write. It
isn't the point of PRISM, though: the template you built in Chapters 2–5
is the reusable core, and LimeSurvey export is one way to turn it into
something people can actually fill out. The `SoftwarePlatform` field you
set back in Chapter 2 already recognizes `PsychoPy` and `Pavlovia` as
valid administration platforms alongside LimeSurvey — direct Pavlovia
export is in progress but not yet reachable from the Studio GUI, which is
the only reason this chapter doesn't walk through it too.

## Quick Export vs. Customize & Export

Open `/survey-generator` — the app still calls this route `survey-generator`,
but the page itself is labeled **Survey Export**. In the toolbar, set **Base
Language** to `en`, and check both boxes under **Export Languages** (`en` and
`de`) so the bilingual work from Chapter 4 actually makes it into the export.
Leave **LS Version** on its default (`5.x / 6.x`) unless you know your
installation is older.

Under **Survey Questionnaires**, find `recovery` and check its box. Expanding
the row shows every item with its own checkbox — this is also where "which
version" gets decided, since Survey Export doesn't have a separate `full`/
`short` selector: all ten items are checked by default, which is the `full`
set. (For a `short` export, you'd uncheck the five items that Chapter 5's
`ApplicableVersions` tags as `full`-only: `rec_motiv`, `rec_stress`,
`rec_appetite`, `rec_hydration`, `rec_satisf`.) Leave all ten checked.

Two buttons become active once a template is checked:

- **"Quick Export (.lss)"** downloads a ready-to-import file immediately,
  with default presentation — no grouping, no per-question overrides, one
  page.
- **"Customize & Export"** hands the same selection to the Survey Customizer
  first.

Both produce a valid `.lss`. This tutorial uses **Customize & Export**,
because the point of this chapter is to show what's actually configurable
before the file leaves PRISM.

## Group and order questions

The Customizer opens with a **Groups** panel on the left and the question
list on the right. Click the **+** button at the top of the Groups panel
(tooltipped "Add new group") and create two groups:

- **Recovery Ratings** — for the nine Likert items
- **Pain** — for `rec_pain`

Each click opens a small "name this group" prompt; type the name and confirm.
Once both groups exist, drag questions from the ungrouped list into the
group they belong to, and drag the group headers themselves to set the order
groups will appear in the exported survey (Recovery Ratings first, Pain
second, say). LimeSurvey groups become actual question groups in the
`.lss` — this is the structural skeleton the rest of the chapter configures.

## Per-question LimeSurvey settings

Pick `rec_pain` and click the gear icon next to it labeled **LS** (tooltip:
"LimeSurvey settings") to expand its tool-settings panel. This is where
LimeSurvey-specific properties live, separately from the **Required** switch
that sits on the question row itself (Chapter 4's `rec_pain` doesn't need to
change — this is purely about how it displays and behaves at survey-runtime,
not the question's data model). For `rec_pain`, set:

- **Question Type** — leave it on "Auto-detect", or override it explicitly
  (e.g. force `N - Numerical` instead of the auto-detected slider) if you
  want LimeSurvey's rendering to differ from PRISM's own Preview.
- **Required** — toggle the row-level **Required** switch on, so LimeSurvey
  won't accept a submission that skips it.
- **Relevance (Logic)** — a conditional-display equation. For example, if
  this study had a screening question asking whether the session included a
  training bout, you might enter something like `session_training == 'Y'` so
  the pain item only appears for sessions where it applies. Treat this as
  illustrative — nothing about the template you built in Chapters 1–5
  requires a relevance equation to validate or export correctly.
- **Hidden** — leave unchecked; this is for calculated/metadata questions
  that shouldn't be shown to the respondent at all.
- **Page break** — check this if you want `rec_pain` to start a new page in
  LimeSurvey, separate from the Recovery Ratings matrix.

## Matrix grouping

Enable **"Group questions with identical options into matrices"** and
**"Global matrix grouping (all identical options, not just consecutive)"**
— both are checked by default.

This only does something useful because of a fact Chapter 4 already
established: all nine Recovery Ratings items share the exact same `Levels`
map — one 1–5 Likert scale reused across items, not nine separately-defined
scales that happen to look alike. Matrix Mode groups questions with
*identical* answer options into a single LimeSurvey array/matrix question, so
those nine collapse into one compact table instead of nine separate radio
questions. `rec_pain` doesn't join that matrix — it's a VAS item with no
`Levels` map at all, a different kind of measurement, not a smaller or
larger version of the same scale — so it stays as its own question, exactly
as Chapter 4 distinguished it.

## Welcome text and export

Scroll to **LimeSurvey Survey Settings → Text & Messages**. Either write your
own **Welcome Message** and **End Message** by hand, or pick **"Standard
Welcome"** from the template dropdown and a matching end-message template to
populate both fields for you.

Then fill in **Survey Name** (required — this feeds the downloaded
filename) and click **"Export Survey"**. The browser downloads
a `.lss` file named from your Survey Name plus today's date; save or rename
it to `recovery_full_en_de.lss` to keep this tutorial's naming convention
going. That file is this chapter's deliverable — a complete LimeSurvey
structure file with your groups, per-question overrides, matrix grouping, and
welcome/end text baked in.

## What happens next (not covered here)

From here, the remaining steps are: import `recovery_full_en_de.lss` into a
running LimeSurvey installation, activate it, collect real responses, export
a `.lsa` archive from LimeSurvey, and import that archive back into PRISM via
**Converter → Survey**. None of that is covered in this tutorial — it stops
deliberately at the `.lss` file, and no LimeSurvey instance is required to
complete it. For the full round trip, with screenshots, see
[LimeSurvey Integration](LIMESURVEY_INTEGRATION.md).

## What you just did

You exported the bilingual, ten-item `full` version of the recovery template
through the Survey Customizer: grouped its items into two LimeSurvey question
groups, configured `rec_pain`'s type, relevance, and page-break behavior,
grouped the nine shared-scale Likert items into a single matrix question, set
welcome/end text, and exported a real, importable `recovery_full_en_de.lss`.

## What's next

- [Chapter 7: Validation](TUTORIAL_SURVEY_7_VALIDATION.md) — catching schema
  problems before they reach an export like this one
- [LimeSurvey Integration](LIMESURVEY_INTEGRATION.md) — the full round trip
  this chapter stopped short of: importing the `.lss`, collecting data, and
  bringing responses back into PRISM
