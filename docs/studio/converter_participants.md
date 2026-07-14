# Converter — Participants / Sociodemographics

Imports a sociodemographics/participants source file and produces `participants.tsv`
+ `participants.json` together for your project.

## Step 1 — Select file and ID column

- File input accepts `.xlsx`, `.csv`, `.tsv`, `.sav`, `.rds`, `.rdata`, `.rda`, `.lsa`.
  CSV/TSV files expose a separator selector; Excel files expose a sheet selector.
- **Participant ID Column** defaults to "Auto-detect", which recognizes
  `participant_id`, `participantid`, `prism_participant_id`, `prismparticipantid`, and
  falls back to `subject_id`, `sub_id`, `subject`, `sub`, `id`, or any column whose
  name contains both "participant" and "id".

## Step 2 — Review Participant Fields

Click **Review Participant Fields** to preview detected columns and sample values
before anything is written.

## Step 2b — Add More Columns (optional)

**Add More Columns (Optional)** lets you pull in source columns beyond the
automatically-detected participant-relevant set.

## Value recoding — what actually happens

There is no source-value transform step in the current UI or converter. Raw values
from your source file are preserved as-is in `participants.tsv`. Recoding/labeling now
happens only at the **metadata layer**: the "Participant Annotation" card lets you
attach NeuroBagel-style term mappings and `Levels` descriptions to `participants.json`
— this describes what the raw codes mean, it does not rewrite the values themselves.
Saving this annotation is optional ("Save Draft Metadata (Optional)") — unsaved edits
in that panel are still applied when you create the files in Step 3.

## Step 3 — Create Participant Files

Writes `participants.tsv` and `participants.json` together — every conversion path
writes both, never just one. If either file already exists in the project, you'll see
a warning and must check "I understand … will be overwritten" before proceeding.

### `participant_id` canonicalization

Values are trimmed, Unicode-normalized, a leading `sub-` is stripped if present, all
non-alphanumeric characters are removed, and the result is re-prefixed with `sub-`.
IDs are sanitized, never renumbered. Rows with no resolvable ID are dropped with a
warning. Output is collapsed to one row per `participant_id` (a BIDS requirement) —
session/run-like columns (`ses`, `session`, `visit`, `run`, ...) are dropped before
collapsing.

## Where a saved mapping file is looked for

If you save a reusable `participants_mapping.json`, it's discovered in this order
(first match wins):

1. `<project_root>/participants_mapping.json`
2. `<project_root>/code/participants_mapping.json`
3. `<project_root>/code/library/participants_mapping.json`
4. `<project_root>/code/library/survey/participants_mapping.json`

Saving from the Studio UI targets `code/library/participants_mapping.json`.

## Common failures

- **Wrong ID column picked** — override auto-detect explicitly if your source file
  uses an unusual column name.
- **Duplicate participant rows after canonicalization** — two source IDs that differ
  only in punctuation/case collapse to the same `participant_id`; check your source
  data if you see unexpected duplicate-row conflicts.
- **Expecting value recoding in `participants.tsv`** — this is not supported; use the
  NeuroBagel annotation panel to describe/label codes instead.

## What's next

- [Survey Import](converter_survey.md)
- [Projects](projects.md)
