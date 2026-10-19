# One behaviour for add-a-row controls on the Projects page

## Problem

The Study Metadata form mixes three behaviours. Authors, Funding, the list fields
and Missing files capture what is typed immediately, and show a red cross that only
deletes. The recruitment-location picker and the DOI/ORCID lookups need a click, and
typed text is lost without it. The new Checked Criteria rows use a green check and a
red cross. Users cannot tell whether they must click somewhere after typing or
choosing, and some lose input that way.

## Decision

Every add-a-row control follows one rule:

1. A new row is a **draft**: green check (accept) and gray **Cancel**. The check is
   disabled until the row is complete, and a short hint says what is missing.
2. Accepting makes the row **defined**: only now it shows the red cross, which deletes.
3. A row with no check never needs a click. A row with a check always does.
4. Rows loaded from `project.json` are defined.
5. Saving is **blocked** while any draft with content is pending (see below).

## Goals

- One implementation of the rule, shared by all row types, with its pure logic unit
  tested (vitest runs in node, so the DOM part stays thin).
- The Checked Criteria rows (already built on this branch) move onto the shared code.
- Core/FAIR counts and badges count defined rows only (already true for criteria).
- No data format changes: `project.json` is written exactly as before.

## Non-goals

- No autosave and no new save button.
- No redesign of the fields themselves or their validation rules.
- Other pages (Settings, Export, DataLad, Open project) are not touched.

## Row types

| Row type | Where | Complete when | Notes |
|---|---|---|---|
| Authors | `addAuthorRow` | first and last name | Corresponding/email rules stay as they are. ORCID lookup stays a helper inside the draft. |
| List rows | `addOverviewListRow`, `OVERVIEW_LIST_FIELDS` (Inclusion, Exclusion, IV/DV/CV/QA, QC, References) | text not empty | DOI rows keep their lookup button as an optional helper; the check accepts what was typed. |
| Two-field rows | `addTwoFieldRow` (Known issues) | at least one field filled | |
| Missing files | `addMissingFilesRow` | what the row needs today to be meaningful | Builder reads `combineMissingFilesRow`. |
| Funding | `addFundingRow` | agency filled | Grant number stays optional. |
| Recruitment location | `addRecLocationRow`, picker | n/a: a staged control | The picker's Add button is the check: styled green with a check icon. Text typed or a result chosen but not added counts as pending. |
| Checked Criteria | `eligibility-criteria.js` | existing `isComplete` | Move onto the shared code. |

## Shared module

New `app/static/js/modules/projects/row-state.js`:

- Pure: `rowState(row)` returns `draft` or `defined`; `isPendingWithContent(row)`;
  `pendingSummary(rows)` returns the message text ("3 rows are not accepted yet: ...").
  Each row type supplies its own `isComplete` and `hasContent` functions.
- DOM (thin): `renderRowActions(rowEl, {...})` builds the check/Cancel/cross group;
  `pendingRows(form)` finds draft rows and staged controls with content, using
  `data-row-state="draft"` and `data-row-pending`; `highlightPending(rows)` marks them
  and scrolls to the first.

## Saving

Both submit paths (the create-project handler in `create-project.js` and the study
metadata handler in `metadata.js`) call one guard first. Any pending row blocks the
save: nothing is sent, the pending rows are highlighted, and `showTopFeedback`
(warning) says what to do: click the green check, or Cancel. This covers Create
Project, Preliminary Save and Save for an opened project.

## Constraints

- GUI-only state: draft/defined is not persisted and is not business logic, so it
  stays in the GUI (CLAUDE.md). Nothing about what the data becomes changes.
- CLAUDE.md: extract focused, tested functions out of the large `metadata.js` instead
  of growing it; test first for every task.
- Accessibility: icon buttons keep `aria-label` and `title`.

## Calls made without asking

- A completely **empty** draft is discarded silently on save (nothing typed, nothing
  lost) and does not block.
- Cancel is a gray button, never red, so the red cross always means "delete something
  that is defined".
- The check button is disabled, not hidden, while a row is incomplete, so users see
  where it will be.
- DOI and ORCID lookups remain optional helpers inside the draft state.

## Build order

1. `row-state.js` with its unit tests; move Checked Criteria onto it.
2. List rows and two-field rows (most common).
3. Authors and Funding.
4. Missing files.
5. Recruitment location picker and the lookups.
6. The save guard on both submit paths.
7. Docs, changelog, and an end-to-end test per row type.

## Tests

- Unit: `rowState`, `isPendingWithContent` (empty draft does not block, draft with
  content does), `pendingSummary` wording and counts.
- End to end, per row type: a new row shows the check and no red cross; accepting
  swaps it for the red cross; Cancel discards; a loaded row is defined.
- End to end, save guard: with a pending draft, Create Project, Preliminary Save and
  Save send nothing and highlight the row; after accepting, the save goes through.

## Addendum: green chips (user feedback, 2026-10-16)

The CRediT roles pattern (an input, accepted entries become green chips below, the input
stays ready for the next one, click a chip to remove it) replaces accepted *rows* for
every add-a-row list except authors:

- Plain-text lists (variables, inclusion/exclusion, quality control): done, `chip-list.js`.
- Structured lists: funding (agency + grant), known issues (two fields), missing files
  (five fields), recruitment locations (the search picker) and Checked Criteria. Each keeps
  one persistent **entry row** (the existing inputs plus the check); accepting adds a chip
  with a short summary and clears the entry row. The stored format is unchanged: chips hold
  the same serialized strings the hidden fields already use ("FWF, P12345",
  "file | issue", "sub | ses | mod | reason | detail"); Checked Criteria hold the criterion
  objects.
- Authors stay cards (too much detail per entry for a chip).
- DOI and URL reference lists keep rows (each row shows lookup feedback).
- Not kept: drag-reordering of these entries, and per-list "Add" buttons.
- Errors in the "Dataset description issues" box link to the field they name.
