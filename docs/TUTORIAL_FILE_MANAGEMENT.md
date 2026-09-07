# File Management: Bulk Rename, Reorganize, and Clean Up

**Time:** ~35 minutes | **Outcome:** comfortable using every tool on the File
Management page — renaming raw files into BIDS filenames, reorganizing them
into folders, reshaping a wide spreadsheet, bulk-editing subject/session IDs
and filename parts, closing run-number gaps, deleting files by filter, and
undoing the last mutation — safely, with a real (throwaway) project.

```{mermaid}
flowchart LR
    A["📁 Messy raw files<br/>001_s1.txt, 002_s2.txt, ..."] --> B["🪄 Filename Renamer<br/>rename by example"]
    B --> C["🗂️ PRISM project<br/>sub-*/ses-*/survey/"]
    C --> D["✏️ Rename IDs & Parts<br/>+ Renumber Runs"]
    C --> E["🗑️ Delete Files<br/>(filtered)"]
    D --> F["↩️ Undo"]
    E --> F
```

## Why this tutorial, and why it's not a chapter

The [Getting Started](TUTORIAL_BEGINNER.md) series builds a project from raw
data through to a validated result — six chapters, one running example,
start to finish. File Management is different: it's a toolbox you reach for
*after* files already exist somewhere, whenever you need to bulk-rename,
reorganize, reshape, or delete them. There's no single narrative arc across
its tools, so this isn't Chapter 7 — it's a standalone reference you can
work through on its own, in any order, whenever one of these tools is
relevant to what you're doing.

Every tool here follows the same **preview-first** pattern: a dry preview
that changes nothing, then a separate, explicit apply step. Nothing mutates
on the first click, anywhere on this page.

## Prerequisites

- PRISM Studio installed and launchable — see
  [Installation](INSTALLATION.md) if you haven't done this yet.
- No prior chapters required. We'll create a small throwaway project here so
  nothing you do in this tutorial touches any real project you already have.
- The example files used below ship with the repository under
  `examples/file_management/` — ten subjects' worth of arbitrarily-named
  `.txt` files, deliberately messy (some subjects have one session, some
  have two) to mirror what a real raw-data folder looks like.

```{note}
**DataLad is optional here, and this tutorial calls out where it matters.**
Every tool below works identically whether or not the project you're
using has **Use DataLad version control** checked. The one difference:
on a DataLad-tracked project, each mutation is also committed automatically
(per-subject, where that applies) on top of PRISM's own Undo log — so you
get two safety nets instead of one. Nothing you click changes based on this;
it's worth knowing about so DataLad commit messages in your project history
don't come as a surprise later.
```

## Set up a scratch project

From the Studio landing page, **Create or Open a Project** → **Create New
Project**:

- **Project Name**: `file_management_demo`
- **Use DataLad version control**: check it if you have DataLad installed
  (see [DATALAD](DATALAD.md)) — optional, not required for anything below.
- Fill in the other required fields as in
  [Chapter 1](TUTORIAL_BEGINNER_1_NEW_PROJECT.md) and create the project.

Leave it open — every section below uses this same project.

## 1. Filename Renamer — turn raw files into BIDS filenames

**Tab:** Rename Filenames → Filename Renamer.

This is the tool for files that don't have BIDS names yet. You give it one
example file, describe where the subject/session are in its name, describe
the output pattern you want, and it applies that rule to every selected
file at once.

1. **Select Files or Folder to Rename** → choose the whole
   `examples/file_management/` folder.
2. **Subject/Session Source**: `Filename` (the IDs are in the filenames
   here, not the folder path).
3. **Structure**: leave **Organize into PRISM structure** checked — this
   writes straight into `sub-<label>/ses-<label>/<modality>/` instead of a
   flat dump.
4. **Project Destination**: `PRISM root`.
5. PRISM picks one file as the example — e.g. `001_s1.txt` — and shows
   **5. Define Renaming Rule by Example**:
   - **Task**: `demo`
   - **Modality**: `Survey`
   - **Subject string in this example**: `001`
   - **Session string in this example**: `s1`
   - **Output Filename Template**: `sub-{subject}_ses-{session}_task-demo_survey.txt`
6. Click **Preview renames**. You should see all 15 files matched, split
   across 10 subjects, some with both `ses-s1` and `ses-s2`, some with only
   one (`sub-007` only has an `s2` file — that's intentional, real datasets
   are rarely perfectly balanced).
7. Click **Copy to Project**.

**Expected outcome:** your project now has
`sub-001/ses-s1/survey/sub-001_ses-s1_task-demo_survey.txt` and similar
files for every subject/session pair found — the original files in
`examples/file_management/` are untouched (this tool copies, or offers a
ZIP download; it never modifies your source files).

```{note}
**"Rename & Download" instead of "Copy to Project"** does the same rename
but streams a ZIP back to you instead of writing into the open project —
useful when you're prepping files for someone else's project, or don't have
one open yet.
```

## 2. Rename Subject IDs — bulk-edit IDs already in the project

**Tab:** Rename Filenames → Rename Subject IDs (Current Project).

Different from the tool above: this rewrites subject IDs that are *already*
in your project, everywhere they appear — filenames, folder names, and
metadata links (including things like `IntendedFor` inside JSON sidecars).

1. **Example Subject ID**: pick `sub-001` from the dropdown.
2. **Part to Keep**: leave empty (we're keeping the whole thing).
3. **Text to Add**: `DEMO`, **Position**: `Prepend`.
4. Click **Preview** — you should see every `sub-0XX` mapped to
   `sub-DEMO0XX`.
5. Click **Apply Rename**, confirm the dialog.

**Expected outcome:** all ten subject folders are renamed
(`sub-001` → `sub-DEMO001`, etc.), and the undo bar at the top of the page
now shows this rename as the last operation — more on that in the Undo
section below.

## 3. Rename Session IDs — the same idea, scoped to one session value

**Tab:** Rename Filenames → Rename Session IDs (Current Project), just
below Subject IDs.

This rewrites one session *value* everywhere it occurs — not one subject's
session, every subject that has it.

1. **Example Session ID**: pick `ses-s1`.
2. **Part to Keep**: `1` (strips the leading `s`).
3. **Text to Add**: `visit`, **Position**: `Prepend`.
4. **Preview** — every `ses-s1` across every subject should map to
   `ses-visit1`; `ses-s2` files are untouched, since this rewrite only
   targets the one session value you picked as the example.
5. **Apply Rename**, confirm.

```{important}
Session labels are arbitrary strings, not numbers — `ses-s1`, `ses-1`, and
`ses-01` are three different, independent labels as far as PRISM (and BIDS)
is concerned. This tool never guesses that two differently-written labels
mean the same session; it only rewrites the exact value you picked.
```

## 4. Edit BIDS Filename Parts — rename or delete one entity

**Tab:** Rename Filenames → Edit BIDS Filename Parts (Current Project).

For any filename part other than the subject ID — `_task`, `_acq`, `_run`,
etc. — one modality and one part at a time.

1. **Modality**: `survey`.
2. **Part**: `_task`.
3. **Action**: `Rename`.
4. **Current Value** should show `demo`; **New Value**: `checkin`.
5. **Preview**, then **Apply Rewrite**, confirm.

**Expected outcome:** every survey filename's `task-demo` becomes
`task-checkin`. The same panel's **Delete** action works the same way for
dropping a part entirely (e.g. removing an `_acq` no one uses) — not needed
here, so we leave it alone.

## 5. Renumber Runs — close gaps automatically

**Tab:** Rename Filenames → Renumber Runs (Current Project), at the bottom.

Our demo project has no `run-` entities, so **Preview** here will report
zero groups — which is the expected, safe result, not an error. This tool
is meant for exactly one scenario: you deleted a middle run (say `run-02`
out of `run-01, run-02, run-03`) and want the remaining runs renumbered
contiguously (`run-01, run-02`) instead of leaving a gap. It's fully
automatic — no fields to fill in, just Preview then Apply — and only
touches clean, consistently-zero-padded numeric sequences; anything
irregular is skipped and listed with a reason rather than guessed at.

## 6. Delete Files — filtered, permanent deletion

**Tab:** Delete Files.

```{warning}
Deletion here is permanent and cannot be undone by PRISM's Undo log (unlike
every rename/rewrite above). Always run Preview first, and double-check the
filter before clicking Delete.
```

1. **Modality**: `survey`.
2. **BIDS Entity Filters** → **Add Entity Filter** → `task = checkin`.
3. Leave **Subjects** empty (affects all subjects).
4. Click **Preview** — confirm the list only contains the survey files you
   expect, then click **Delete Files** and confirm.

**Expected outcome:** every `task-checkin` survey file is gone. Note the
panel's own warning: `participants.tsv` is **not** updated automatically —
if you delete every file for a subject, remove that subject from
`participants.tsv` yourself if needed.

The second card on this tab, **Delete scans.tsv Files**, is a single button
with no filters — it removes every `*_scans.tsv` file across the whole
project (including nested subject/derivatives subdatasets) in one pass,
for clearing out `scans.tsv`-related validation findings you'd rather
delete than fix. Not needed in this demo project, since we never created
any `scans.tsv` files.

## 7. Undo — the safety net

Every rename/rewrite tool above (not Delete Files) records an entry in
PRISM's Undo log before it runs. A warning bar at the top of the File
Management page shows the most recent one, with its own **Undo** button.

1. Scroll to the top of the page — the undo bar should describe your most
   recent action (the `_task` rename from Step 4, if you followed along in
   order).
2. Click **Undo**.

**Expected outcome:** the `_task` rename is reversed — filenames go back to
`task-demo`. Undo only ever reverses the *single most recent* operation
(it's a stack, not a full history browser) — click it again and it reverses
the one before that, and so on. If your project is DataLad-tracked, this
Undo is separate from (and in addition to) DataLad's own commit history —
you could also roll back further using DataLad directly, but PRISM's Undo
is the fast path for "I just made a mistake."

## Wide to Long — reshape a wide spreadsheet first

**Tab:** Wide to Long. (Not part of the numbered flow above — reach for this
*before* Survey conversion, only if your source file needs it.)

Some survey exports put every session's answers in the same row, one column
per session (`T1_mood`, `T2_mood`, ...) instead of one row per
subject-session. This tool splits those columns back out into separate rows
so Survey conversion (Chapter 3) can read them normally.

Create a tiny spreadsheet, `mood_wide.xlsx`:

| participant_id | T1_mood | T2_mood |
|---|---|---|
| 001 | 4 | 5 |
| 002 | 3 | 4 |
| 003 | 5 | 5 |

1. **1. Upload Wide Table** → select `mood_wide.xlsx`.
2. **2. ID Column**: `participant_id` (usually auto-detected).
3. **3. Session Indicators**: `T1_:baseline,T2_:followup` — this both
   matches the two column prefixes and renames them to readable session
   labels.
4. Leave **4. Run Indicators** empty — no run-level split needed here.
5. **Preview Output (first rows)** — confirm you now see 6 rows (3
   participants × 2 sessions) with one `mood` column and a `session`
   column reading `baseline`/`followup`.
6. **Convert & Save to Project**.

**Expected outcome:** a long-format file written to
`sourcedata/wide_to_long/` inside the project — ready to hand to the
Survey converter as its input.

## Organize Folders (Copy) — for files that are already named correctly

**Tab:** Organize Folders (Copy).

Skip this one if you only ever use Filename Renamer with **Organize into
PRISM structure** checked (Step 1 above already does this in one pass).
Reach for Organize Folders instead when you receive files that are *already*
validly named (`sub-012_ses-pre_task-rest_physio.edf`) but sitting flat in
one folder — e.g. unzipped from a shared drive — and just need sorting into
`sub-<label>/ses-<label>/<modality>/`. It only copies; there's no
move/delete option, so your source files are never at risk.

1. **Select Files to Organize** → pick any one file already inside your
   project, e.g.
   `sub-DEMO002/ses-visit1/survey/sub-DEMO002_ses-visit1_task-checkin_survey.txt`.
2. **Target Modality**: `Survey (TSV/JSON)`.
3. **Project Destination**: `sourcedata` (keeps this demo copy separate
   from your organized `rawdata`/PRISM-root files).
4. **Dry Run**, check the log, then **Copy to Project**.

**Expected outcome:** a second copy of that file now sits under
`sourcedata/`, organized into the same `sub-<label>/ses-<label>/survey/`
shape — a good pattern for keeping an untouched raw copy alongside your
organized project data.

## What you just did

Starting from ten subjects' worth of arbitrarily-named raw files, you:

1. Renamed them into valid BIDS filenames with Filename Renamer.
2. Bulk-edited subject IDs, a session value, and a filename entity — each
   previewed before being applied.
3. Learned what Renumber Runs and Delete scans.tsv are for, even without
   data that needed them in this demo.
4. Deleted files by filter, understanding what that does *not* clean up
   automatically (`participants.tsv`).
5. Reversed a mistake with Undo.
6. Reshaped a wide spreadsheet into long format, and reorganized an
   already-named file into a folder structure.

Every one of these tools is the same one your project's real data will need
at some point — messy raw filenames, ID harmonization, gap-closing after a
deletion, or bulk cleanup before validation. Delete the
`file_management_demo` project when you're done; nothing outside it was
touched.

## What's next

- [Getting Started Home](TUTORIAL_BEGINNER.md) — the full six-chapter series
- [Studio Guide: File Management](studio/file_management.md) — quick
  reference for every tool on this page
- [Validator](studio/validator.md) — re-run validation after any
  rename/delete pass
- [DATALAD](DATALAD.md) — more on the per-subject commit behavior mentioned
  above
