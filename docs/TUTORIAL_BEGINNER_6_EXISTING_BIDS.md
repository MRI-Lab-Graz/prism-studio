# Chapter 6: Enrich an Existing BIDS Dataset

**Time:** ~15 minutes | **Outcome:** a BIDS dataset enriched with PRISM participant and behavioral metadata

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

You need a BIDS dataset to work with. We'll use a real one from OpenNeuro: **ds003138** (a small neuroimaging study). You have two ways to get it:

### Option A: DataLad (recommended, smaller download)

DataLad lets you clone only the metadata and structure, not the large MRI files. If you don't have DataLad installed yet, see [DATALAD](DATALAD.md) for installation instructions (all major OS supported).

Once installed:

```bash
datalad install https://github.com/OpenNeuroDatasets/ds003138.git
cd ds003138
```

This creates a `ds003138/` folder with the BIDS structure and metadata, but no .nii.gz files.

### Option B: Git sparse-checkout (no DataLad required)

If DataLad installation is tricky on your system, clone the repository and skip binary files:

```bash
git clone --filter=blob:none --sparse https://github.com/OpenNeuroDatasets/ds003138.git
cd ds003138
git sparse-checkout add '/*' '!**/*.nii.gz' '!**/*.nii' '!.git/annex'
```

Either way, you now have a local BIDS dataset with the structure intact.

## Open the dataset in PRISM

Launch PRISM Studio and open the `ds003138` folder as a project:

**Home** → **Open Project** → navigate to your `ds003138` folder → **Open**.

PRISM recognizes it as an existing BIDS project and loads the metadata. You'll see:
- `dataset_description.json` already present
- Existing subject folders (`sub-001`, `sub-002`, etc.)
- No `participants.tsv` yet (or an incomplete one) — that's what we'll add

## Step 1: Add participant demographic data

Just like in [Chapter 2](TUTORIAL_BEGINNER_2_PARTICIPANTS.md), we'll use the Converter to add participant metadata. But this time, we're enriching an existing dataset instead of creating one from scratch.

**Converter** → **Participants** tab → **Load File**.

Create a simple spreadsheet with fake demographic data for three subjects. Save it as `sample_participants.xlsx`:

| participant_id | age | sex | group |
|---|---|---|---|
| 001 | 28 | M | control |
| 002 | 35 | F | treatment |
| 003 | 31 | M | control |

(Use the IDs that match your dataset's existing subjects, e.g., `001`, `002`, `003` if your dataset has `sub-001`, `sub-002`, `sub-003`.)

**Load File** → select `sample_participants.xlsx` → map columns:
- `participant_id` → Participant ID column
- `age` → Age
- `sex` → Sex
- `group` → Group (or use the generic "Custom field" option)

**Preview** → confirm the mapping → **Save**.

PRISM writes `participants.tsv` and `participants.json` into your dataset. If `participants.tsv` already existed, PRISM merges your new data with the existing rows (matching by ID).

**Expected outcome:** `participants.tsv` now has 3 rows with demographics.

## Step 2: Add behavioral data

Now pretend these three subjects completed a brief survey (e.g., a mood or wellbeing questionnaire). We'll add it using the same Survey import workflow from [Chapter 3](TUTORIAL_BEGINNER_3_SURVEY_IMPORT.md).

Create a fake survey file (`sample_survey.xlsx`):

| participant_id | task | WB01 | WB02 | WB03 |
|---|---|---|---|---|
| 001 | wellbeing | 4 | 5 | 3 |
| 002 | wellbeing | 3 | 4 | 4 |
| 003 | wellbeing | 5 | 5 | 4 |

Where `WB01`, `WB02`, `WB03` are item responses (fake Likert scores).

**Converter** → **Survey** tab → **Load File** → select `sample_survey.xlsx`.

Confirm:
- Participant ID column: `participant_id`
- Survey item columns: `WB01`, `WB02`, `WB03`
- Task name: `wellbeing` (or match the existing task label in your dataset)

**Preview** → **Save**.

PRISM creates survey response files (`sub-001_task-wellbeing_survey.tsv`, etc.) in the respective subject folders, and adds a survey sidecar JSON for metadata.

**Expected outcome:** Survey files now sit alongside the MRI data in each subject folder.

## Step 3: Validate

Run the Validator to check that your enriched dataset is still BIDS-compliant:

**Validator** → confirm the project is selected → **Start Validation**.

You should see:
- Mostly green (no errors for the files you added)
- Possible suggestions (e.g., "consider adding task description JSON")
- No new warnings introduced by your metadata

If errors appear, they're usually about existing MRI data or missing sidecars — not your fault. You've successfully enriched the dataset without breaking it.

## What you just did

You took a published BIDS dataset and added two layers of PRISM metadata:
1. Participant demographics (age, sex, group)
2. Behavioral survey data

The workflow was identical to building a dataset from scratch in Chapters 1–5. The only difference: you started with existing MRI/BIDS structure instead of an empty folder.

This is the real-world value of PRISM: it works *on top* of BIDS, not instead of it. Whether you're creating a dataset or enhancing one, the tools stay the same.

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
