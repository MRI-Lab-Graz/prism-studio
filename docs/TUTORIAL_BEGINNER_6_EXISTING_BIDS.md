# Chapter 6: Enrich an Existing BIDS Dataset

**Time:** ~30 minutes (most of it is the dataset download) | **Outcome:** a
real published BIDS dataset, cloned and initialized without a manual
terminal step, enriched with PRISM participant and behavioral metadata

## Why enrich existing datasets?

The first five chapters showed you how to build a PRISM project from scratch: create the structure, import data, add metadata, score, and validate. But you'll often work the opposite direction — you have a real BIDS dataset already published or in progress, and you want to add or fix metadata, attach behavioral scores, or complete missing participant info.

Good news: PRISM handles both paths with the same tools. This chapter shows that enriching an existing BIDS dataset is exactly the same workflow as building one from zero.

<div class="prism-persona-note" data-persona-note>
<p class="prism-persona-note-empty" data-persona-empty>Picked a persona on the <a href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">intro page</a>? This note speaks to it.</p>

<div class="prism-persona-note-content" data-persona="student" hidden>
<span class="prism-persona-note-badge">👩🏽‍🎓 The enthusiastic student <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

*Everything so far has been on `wellbeing_study`, a dataset you built and
already understand.* This chapter is the real test: a dataset you had no
part in creating. If the last five chapters actually taught you something
transferable, this is where that shows.

</div>

<div class="prism-persona-note-content" data-persona="pi" hidden>
<span class="prism-persona-note-badge">👨🏿‍🔬 The skeptical PI <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

*Your lab doesn't only produce data — it inherits it, from collaborators,
from students who've graduated, from datasets you're asked to extend for a
new grant.* This is the scenario "every project goes through PRISM" was
actually meant for.

</div>

<div class="prism-persona-note-content" data-persona="future" hidden>
<span class="prism-persona-note-badge">🧑🏻 Future-you <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

*This chapter is a simulation of exactly what you've been preparing for
since Chapter 1* — opening a dataset that isn't fresh in your memory and
still being able to work with it.

</div>
</div>

## Prerequisites

You need a BIDS dataset to work with. We'll use a real one from OpenNeuro:
**ds003138**, a small structural-imaging study of slackline training
(coincidentally from the same lab that maintains PRISM) — 52 subjects,
3 sessions each, MRI data only. It already ships with a `participants.tsv`
(age/sex/group), but nothing else — no survey or behavioral data — which is
exactly the kind of gap this chapter is about filling in.

This time, PRISM Studio can fetch the dataset itself — no separate terminal
clone needed. That said, it still calls DataLad under the hood for an
OpenNeuro dataset like this one, so DataLad and `git-annex` need to be
installed first; see [DATALAD](DATALAD.md) if you don't have them yet (all
major OS supported). If you'd rather clone it yourself ahead of time, the
old two-step path (`datalad install
https://github.com/OpenNeuroDatasets/ds003138.git`, or a `git clone
--filter=blob:none --sparse` + `sparse-checkout` to skip the `.nii.gz`
files) still works — just point **Init PRISM on BIDS Dataset**'s **BIDS
Dataset Root** at the resulting folder instead of using the remote-URL
fields below.

## Init PRISM on the dataset

From the Studio landing page, select **Create or Open a Project** to reach
the **Projects** page — same as [Chapter 1](TUTORIAL_BEGINNER_1_NEW_PROJECT.md),
except this time use the **Init PRISM on BIDS Dataset** card instead of
**Create New Project**. This is the one that matters for an existing
dataset: it only adds the PRISM files a BIDS dataset doesn't already have
(`project.json`, `.prismrc.json`, etc.) and never overwrites anything
that's already there — unlike **Open Existing Project**, which requires a
`project.json` to already exist and will reject a plain BIDS clone outright
since it doesn't have one yet.

- **Git / DataLad URL**: `https://github.com/OpenNeuroDatasets/ds003138.git`
- **Clone Destination**: an empty folder, e.g. `~/prism_projects/ds003138`
- Leave the other fields at their defaults — PRISM recognizes the
  `OpenNeuroDatasets` URL pattern and installs it with DataLad
  automatically, whether or not you check **Use DataLad version control**.
- Click **Init PRISM on This Dataset**.

```{note}
**"No participants.tsv yet" doesn't always hold — and that's fine.**
Earlier drafts of this chapter assumed the example dataset had no
`participants.tsv`. ds003138 actually already has one, with real age/sex/
group data for all 52 subjects — a very common real-world case. Chapter 2's
Merge workflow (Step 1 below) is exactly the tool for extending a
`participants.tsv` that already exists, rather than starting from empty.
```

PRISM streams progress as it clones and initializes, then loads the project
automatically. You'll see:
- `dataset_description.json` and the existing `sub-*` folders, untouched
- `participants.tsv` already populated (age, sex, group)
- No survey or behavioral data anywhere — that's what Step 2 adds

```{note}
**Why did PRISM mention un-annexing files?** If you used the DataLad path,
check the Init log for a line like "Un-annexed N text-format file(s) that
arrived already tracked by git-annex in the source dataset." OpenNeuro's
DataLad datasets sometimes have small text-format files (like
`participants.tsv` itself) stored as git-annex symlinks alongside the large
binary MRI data. PRISM's policy is that text/small-codebook files should
never be annexed — they need to be directly readable and diffable — so
Init automatically un-annexes any that arrive that way, without you having
to notice or fix it yourself.
```

## Step 1: extend the existing participants.tsv with Merge

`participants.tsv` already exists here, so this is Chapter 2's **Merge**
workflow in a real setting, not the fresh-create path — a good chance to
use it for something other than a made-up exercise.

Pretend you've been handed a handedness assessment for three of the
subjects. Create a small spreadsheet, `handedness_update.xlsx`:

| participant_id | handedness |
|---|---|
| sub-82KK02101 | right |
| sub-82KK02102 | left |
| sub-82KK02103 | right |

(Use three real subject IDs from your cloned dataset — check any three
`sub-*` folder names if you're not using ds003138.)

1. **Converter** → **Sociodemographics** tab. Since `participants.tsv`
   already exists, you'll be asked to choose a workflow: pick **Merge**.
2. Upload `handedness_update.xlsx`, confirm `participant_id` as the ID
   column, and click **Preview Merge**.
3. The Merge Summary should show `3 matched`, `3 filled values` (one new
   `handedness` value per row), `0 new participants`, `0 conflicts` — this
   file only adds a column that didn't exist before, so there's nothing to
   conflict with.
4. Click **Apply Merge**.

**Expected outcome:** `participants.tsv` still has all 52 original rows,
now with a `handedness` column that's populated for the three subjects you
provided and empty for the other 49 — Merge only fills in what you gave it,
exactly as it did in Chapter 2.

## Step 2: add behavioral data

ds003138 genuinely has no survey/behavioral data — this is the real
enrichment opportunity, using the same Survey Import workflow from
[Chapter 3](TUTORIAL_BEGINNER_3_SURVEY_IMPORT.md). ds003138 has three
sessions per subject (`ses-1`, `ses-2`, `ses-3`); pretend these three
subjects completed a brief wellbeing check-in at `ses-1`.

Create a fake survey file, `sample_survey.xlsx`:

| participant_id | session | WB01 | WB02 | WB03 | WB04 | WB05 |
|---|---|---|---|---|---|---|
| sub-82KK02101 | 1 | 4 | 5 | 3 | 4 | 4 |
| sub-82KK02102 | 1 | 3 | 4 | 4 | 3 | 3 |
| sub-82KK02103 | 1 | 5 | 5 | 4 | 5 | 4 |

This reuses the `wellbeing` template from Chapter 3 (all five items, since
the template expects exactly `WB01`-`WB05` — see Chapter 3's Common
Mistakes if you want to try fewer items instead, which needs a different
template).

1. **Converter** → **Survey** tab → select `sample_survey.xlsx`.
2. **Participant ID Column**: `participant_id`. **Session Column**:
   `session`. **Session ID**: `1` (matching `ses-1`).
3. **Preview** — confirm 3 participants found, task `wellbeing`, no missing
   items.
4. **Convert**.

PRISM creates one `.tsv` per subject
(`sub-82KK02101/ses-1/survey/sub-82KK02101_ses-1_task-wellbeing_survey.tsv`,
etc.) plus the single shared root-level `task-wellbeing_survey.json`
sidecar — same structure as Chapter 3, just written into an existing
dataset instead of a fresh one.

**Expected outcome:** survey files now sit alongside the MRI data, only for
the three subjects and one session you provided — everyone else's folders
are untouched.

## Step 3: Validate

Run the Validator to check that your enriched dataset is still BIDS-compliant:

**Validator** → confirm the project is selected → **Start Validation**.

You should see mostly green: no errors for the `handedness` column or the
survey files you just added, since both went through the same
Merge/Convert paths already validated in Chapters 2 and 3. If the standard
BIDS/MRI side of ds003138 itself surfaces findings (some real-world
datasets do, even published ones), those predate anything you did here —
the ones worth checking are new findings on the *files you touched*:
`participants.tsv`/`.json` and the `sub-82KK02101` (etc.) survey files.
Nothing about enriching an existing dataset changes how you read results —
see [Chapter 5](TUTORIAL_BEGINNER_5_VALIDATOR.md) if you need the refresher.

## What you just did

You took a published BIDS dataset — one you didn't create, with data
already in it — and:
1. Initialized PRISM on it directly from its remote URL, without a manual
   terminal clone step.
2. Extended its existing `participants.tsv` with Merge, rather than
   overwriting it.
3. Added behavioral survey data it never had, using the same Survey Import
   workflow as Chapter 3.
4. Validated the result the same way as Chapter 5.

The tools were identical to Chapters 1–5 throughout — the only difference
was starting from an existing BIDS structure with its own data already in
it, instead of an empty folder. That's the real-world value of PRISM: it
works *on top* of BIDS, not instead of it, whether you're building a
dataset from scratch or enriching someone else's.

<div class="prism-persona-note" data-persona-note>
<p class="prism-persona-note-empty" data-persona-empty>Picked a persona on the <a href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">intro page</a>? This closing note speaks to it.</p>

<div class="prism-persona-note-content" data-persona="student" hidden>
<span class="prism-persona-note-badge">👩🏽‍🎓 The enthusiastic student <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

This is the FAIR-sharing payoff, in full: a stranger's dataset, not your
own, and you were still able to open it, understand it, and add to it
without guessing. That's what you were building toward since Chapter 1.

</div>

<div class="prism-persona-note-content" data-persona="pi" hidden>
<span class="prism-persona-note-badge">👨🏿‍🔬 The skeptical PI <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

This is the insurance policy paying out: a dataset you didn't build, from a
group you've never met, and PRISM still let you extend it safely. That's
exactly why every project in your lab goes through this now.

</div>

<div class="prism-persona-note-content" data-persona="future" hidden>
<span class="prism-persona-note-badge">🧑🏻 Future-you <a class="prism-persona-note-change" href="TUTORIAL_BEGINNER.html#pick-a-reason-to-be-here">change</a></span>

This is what it feels like from the other side — opening someone else's
(or eighteen-months-ago-you's) dataset and it just making sense. That's the
relief you were setting up back in Chapter 1.

</div>
</div>

## What's next

- [Getting Started Home](TUTORIAL_BEGINNER.md) — review the full tutorial series
- [Studio Guide](studio/index.md) — dive deeper into each converter and workflow
- [Workshop](WORKSHOP.md) — try a longer, instructor-led version
- [Error Codes](ERROR_CODES.md) — troubleshoot validation findings
- [DATALAD](DATALAD.md) — learn more about versioning your enriched datasets
