# Chapter 5: Use the Validator

Chapter 5 of [Getting Started — Your First PRISM Project](TUTORIAL_BEGINNER.md).
This is about running PRISM's built-in checks against `wellbeing_study` and
learning to read what they report — not about fixing every possible finding,
which will vary by project.

**Time:** ~20 minutes. **Outcome:** a validation run against
`wellbeing_study`, hands-on experience causing and clearing a real error,
and enough understanding of the results to know what to do next.

```{mermaid}
flowchart LR
    A["📁 wellbeing_study<br/>as built so far"] --> B["🔧 Validator<br/>PRISM + BIDS checks"]
    B --> C["✅ Findings read & fixed<br/>a dataset you can trust"]
```

<div class="prism-persona-note" data-persona-note>
<p class="prism-persona-note-empty" data-persona-empty>Picked a persona on the <a href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">intro page</a>? This note speaks to it.</p>

<div class="prism-persona-note-content" data-persona="student" hidden>
<span class="prism-persona-note-badge">👩🏽‍🎓 The enthusiastic student <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

*Four chapters of doing things "properly" are about to get checked by
someone other than you.* This is the moment `wellbeing_study` stops being
"what you believe is correct" and starts being "what PRISM can verify is
correct" — that gap is exactly what a reviewer or reuser would otherwise
find for you, later, less kindly.

</div>

<div class="prism-persona-note-content" data-persona="pi" hidden>
<span class="prism-persona-note-badge">👨🏿‍🔬 The skeptical PI <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

*This is the step that didn't exist three years ago, when the undocumented
Excel files went out the door unchecked.* Findings on a first pass are
normal — the only unacceptable outcome is not running this at all before
something leaves the lab.

</div>

<div class="prism-persona-note-content" data-persona="future" hidden>
<span class="prism-persona-note-badge">🧑🏻 Future-you <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

*This is the closest thing to a guarantee you get: a record, made today,
that everything checked out.* Whatever this run reports, eighteen-months-
from-now-you will be glad it exists either way.

</div>
</div>

## 1. Open the Validator

![PRISM Studio Validator start screen](_static/screenshots/prism-studio-validator.png)

**Validate current project** should already be pre-selected, showing
`wellbeing_study`'s name and path.

## 2. Leave Advanced Options at their defaults (for now)

Advanced Options is collapsed by default. Leaving it collapsed runs **Full
Validation (PRISM + BIDS)** — you don't need to opt in to get BIDS checks,
this is already the default. The one thing worth knowing about now:
**Show BIDS Warnings** is off by default, so a first run's warning count
undercounts BIDS-side warnings specifically; PRISM warnings are unaffected.
Two other fields live here if you ever need them: **Schema Version**
(defaults to `stable` — leave it unless you specifically need an older
schema) and **Template Library Root** (optional — validation auto-detects
your project's library by default).

## 3. Start Validation

Click **Start Validation**. A progress panel appears, then you land on the
results page automatically. For a project this small the run finishes in
seconds, but for a large dataset the panel also offers **Pause Updates**
(stops the live progress polling, not the validation run itself — resume
with **Resume Updates**) and **Cancel Validation**.

## 4. Read the results

![PRISM Studio Validator results screen](_static/screenshots/prism-studio-validator-results.png)

Start with the summary dashboard: Total Files / Valid / Errors / Warnings,
each split into BIDS vs. PRISM. Then use this table to decide what to act on
first:

| Level | Meaning | What to do |
|---|---|---|
| Error | Blocking problem | Fix before treating the dataset as valid |
| Warning | Important issue | Fix soon, especially before sharing the dataset |
| Suggestion | Improvement | Use when polishing, not urgent |

**Errors** and **Warnings** are grouped into collapsible sections by error
code, each showing a description, an optional fix-hint, affected
subjects/sessions, and sample file paths. A first run reporting several
findings is normal, not a failure — that's the checklist telling you what to
clean up next, not a sign something went wrong in the earlier chapters.

Codes you're likely to see on a first pass through this tutorial's data,
worth knowing by name:

- `PRISM201` — missing JSON sidecar
- `PRISM101` — invalid filename pattern
- `PRISM402` — a value not in the allowed `Levels` for its column

The full catalog, with fix hints for every code, is in
[Error Codes](ERROR_CODES.md) — every finding in the results also links
straight to its entry there.

```{note}
**If you skipped Chapter 4:** you'll also see a warning here — "Missing
survey recipes for dataset-used surveys" — pointing at `wellbeing` having
no saved recipe yet. That's the Validator noticing the same gap Chapter 4
fills; it isn't a sign anything earlier in this tutorial went wrong.
```

## 5. See an error, then clear it

Rather than describe error codes in the abstract, it's worth actually
causing and fixing one. Survey Convert (Chapter 3) writes one shared JSON
sidecar for the whole `wellbeing` survey at the project root —
`task-wellbeing_survey.json` — rather than one per participant, because
every `sub-*_task-wellbeing_survey.tsv` inherits it (BIDS's inheritance
principle). That makes it an easy, safe, single-file way to see `PRISM201`
in action:

1. In your project folder, rename `task-wellbeing_survey.json` to
   `task-wellbeing_survey.json.bak` (adding a suffix, so nothing is
   deleted).
2. Click **Re-validate**. Every `wellbeing` survey file (20 of them, one
   per participant, if you're following along with the tutorial's data)
   now has no sidecar to inherit from, and reports as a `PRISM201` error:
   "Missing sidecar for `<file>.tsv`."
3. Rename the file back to `task-wellbeing_survey.json` and **Re-validate**
   again. The 20 errors should be gone.

```{tip}
`PRISM201` is one of only three codes that are currently **auto-fixable**
from the CLI (`PRISM001`, `PRISM201`, `PRISM501` — see
[Error Codes](ERROR_CODES.md)). If you'd rather test that path than rename
the file back by hand: with the sidecar still missing, run
`prism-validator /path/to/wellbeing_study --fix --dry-run` and read the
planned actions before applying anything for real. Note it doesn't restore
your original root sidecar — it creates a fresh, minimal per-participant
stub `.json` next to each `.tsv` instead, which is a valid but different
structure than the one you started with. For this exercise, renaming the
file back is simpler and gets you back to exactly where you were.
```

## 6. Fix and re-validate

Use the **Re-validate** button in the action bar to rerun without starting
over from the Projects page. Repeat until the findings that matter to you
are gone — clearing every single suggestion isn't the bar; clearing errors,
and warnings you'd be embarrassed to ship, is.

## Equivalent from the terminal

```bash
prism-validator /path/to/wellbeing_study
```

Auto-fix for supported issues is CLI-only (no per-issue fix button exists in
the web results page yet):

```bash
prism-validator /path/to/wellbeing_study --fix --dry-run
prism-validator /path/to/wellbeing_study --fix
```

## Common mistakes

```{warning}
**Narrowing to PRISM Only or BIDS Only and thinking that's the full
picture.** Full Validation is the default and covers both; only narrow
scope deliberately, not by accident while exploring Advanced Options.
Something like a survey conversion issue only shows up as a valid file
under BIDS-Only mode.
```

```{note}
**Treating a first run's error count as a failure.** It's expected the
first time through; re-validate after each fix rather than expecting zero
findings on the first attempt.
```

```{warning}
**Missing BIDS warnings because "Show BIDS Warnings" is off.** Turn it on
in Advanced Options if you want the complete warning picture, not just
PRISM-side warnings.
```

<div class="prism-persona-note" data-persona-note>
<p class="prism-persona-note-empty" data-persona-empty>Picked a persona on the <a href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">intro page</a>? This note speaks to it.</p>

<div class="prism-persona-note-content" data-persona="student" hidden>
<span class="prism-persona-note-badge">👩🏽‍🎓 The enthusiastic student <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

This is the FAIR payoff, five chapters in. A dataset that passes these
checks is one an unfamiliar reviewer, reuser, or repository can actually
open and trust without asking you anything first — which was the entire
point since Chapter 1.

</div>

<div class="prism-persona-note-content" data-persona="pi" hidden>
<span class="prism-persona-note-badge">👨🏿‍🔬 The skeptical PI <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

This is the report that would have saved you that week three years ago —
errors caught here, before submission, instead of found by a reviewer after
it. Worth making mandatory lab-wide, not just for this one study.

</div>

<div class="prism-persona-note-content" data-persona="future" hidden>
<span class="prism-persona-note-badge">🧑🏻 Future-you <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

This is you, eighteen months from now, grateful that today-you ran this
instead of assuming everything was fine. One chapter left, and it's the one
that actually proves it.

</div>
</div>

## Wrap-up

You now have a `wellbeing_study` project with demographic data, imported
survey responses, a working scoring recipe, and at least one validation
pass — the same shape of outcome the [Workshop](WORKSHOP.md)'s core path
aims for, but built at your own pace with a full explanation at each step.

## What's next

- Back to [Getting Started overview](TUTORIAL_BEGINNER.md) — the
  Intermediate tutorial (DataLad, file/folder manipulation) is next in this
  series
- [Error Codes](ERROR_CODES.md) — the full code reference
- [CLI Reference](CLI_REFERENCE.md) — running any of these five chapters
  from the terminal instead
