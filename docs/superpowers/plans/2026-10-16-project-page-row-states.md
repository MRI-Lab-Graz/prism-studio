# Project Page Row States Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every add-a-row control on the Projects page uses one behaviour: new rows are drafts (green check, Cancel), accepted rows are defined (red cross), and saving is blocked while a draft with content is pending.

**Architecture:** One new module `row-state.js` holds the pure model (which buttons show, what counts as pending, the message) plus a small HTML renderer and a save guard. Each row builder in `metadata.js` gets a `slot` for the buttons, an `accepted` parameter (loaded rows true, rows added by the user false) and syncs its hidden field from accepted rows only.

**Tech Stack:** Vanilla JS modules (vitest in node, so DOM code is covered by Playwright e2e), Flask templates.

**Spec:** `docs/superpowers/specs/2026-10-16-project-page-row-states-design.md`

## Global Constraints

- Draft: green check (`data-f="accept"`, disabled until complete) and gray Cancel (`data-f="cancel"`, never red). Defined: red cross (`data-f="remove"`) only.
- Rows loaded from `project.json` are defined; `project.json` format is unchanged.
- Drafts are counted and saved nowhere: hidden fields, Core/FAIR counts and badges use defined rows only.
- A completely empty draft is discarded silently on save and never blocks.
- Saving (Create Project, Preliminary Save, Save for an opened project) is blocked while any draft with content or staged control with content is pending; `showTopFeedback(message, 'warning')` says to click the check or Cancel; pending rows get class `row-pending`.
- Icon buttons keep `aria-label` and `title`.
- GUI-only state; new logic goes into small tested functions, `metadata.js` does not grow beyond wiring (CLAUDE.md).
- Test first for every task. Existing e2e and wiring tests that add rows and then save must be updated to accept the rows.

## Review Focus

- Funding always keeps one empty placeholder row: it must not block saving, must not be saved, and must come back after the last row is deleted or cancelled. (Task 3)
- Loading a project and saving again without touching rows must not change `project.json` or the Core counts (all loaded rows defined). (Tasks 2, 3, 4)
- A draft with content is not in the hidden field, not in the Core count, and not in the saved payload until accepted. (Tasks 2, 3, 4)
- Typed text in the location search box or a chosen, not yet added result blocks the save; an empty search box or "online only" does not. (Task 5)
- Drag-reordering and switching projects keep drafts consistent: a project switch leaves no stale drafts behind. (Tasks 2, 6)

---

### Task 1: Shared module and Checked Criteria

**Files:**
- Create: `app/static/js/modules/projects/row-state.js`
- Create: `app/static/js/modules/projects/row-state.test.js`
- Modify: `app/static/js/modules/projects/eligibility-criteria.js` (use `rowActionsHtml`; its `accepted` flag stays), `app/static/css/` projects stylesheet (find with `grep -rn "required-field-empty" app/static/css`) for `.row-pending`

**Interfaces:**
- Produces:
  - `rowActionsModel({ state: 'draft'|'defined', complete: boolean }) -> { accept: {visible: boolean, disabled: boolean}, cancel: {visible: boolean}, remove: {visible: boolean} }`
  - `rowActionsHtml(model) -> string` buttons with `data-f` accept/cancel/remove, icons, aria-label/title (check = `btn-outline-success`, cancel = `btn-outline-secondary` text "Cancel", remove = `btn-outline-danger`).
  - `isPending({ state, hasContent }) -> boolean` (true only for a draft with content).
  - `pendingMessage(count: number) -> string`, containing the count and the words "green check" and "Cancel".
  - `bindRowActions(slot: Element, { onAccept, onCancel, onRemove })` one delegated click listener on `slot` keyed by `data-f`.
  - `findPending(form: Element) -> Element[]`: rows with `data-row-state="draft"` whose `el._row.hasContent()` is true, plus registered staged controls (see Task 5).
  - `discardEmptyDrafts(form)`: calls `el._row.discard()` for drafts without content.
  - `guardSave(form, showFeedback: (msg, type) => void) -> boolean`: discards empty drafts; if pending rows remain, adds `row-pending`, scrolls the first into view, calls `showFeedback(pendingMessage(n), 'warning')` and returns `false`; otherwise returns `true`.
  - Row contract used by all builders: a row element has `dataset.rowState` and `el._row = { hasContent(): boolean, discard(): void }`.

- [ ] **Step 1: Write failing tests** in `row-state.test.js`: `rowActionsModel` for draft+incomplete (accept disabled, cancel visible, remove hidden), draft+complete (accept enabled), defined (only remove); `rowActionsHtml` for a draft contains `data-f="accept"` and `disabled` when incomplete, never contains `btn-outline-danger` for a draft; `isPending` (draft with content true, empty draft false, defined false); `pendingMessage(3)` contains `3`, `green check`, `Cancel`.
- [ ] **Step 2: Run** `npx vitest run app/static/js/modules/projects/row-state.test.js` → FAIL (module missing).
- [ ] **Step 3: Implement** the pure functions and `bindRowActions`; `findPending`, `discardEmptyDrafts`, `guardSave` use `querySelectorAll` only (no jsdom needed for the pure ones). Add the `.row-pending` rule (outline in the warning colour).
- [ ] **Step 4: Run** the test file → PASS. Then replace the inline buttons in `rowHtml` of `eligibility-criteria.js` with `rowActionsHtml(rowActionsModel(...))`, keep its existing vitest and e2e green: `npx vitest run app/static/js` and `pytest tests/e2e/test_projects_eligibility_flows.py`.
- [ ] **Step 5: Commit** `feat(projects): shared row-state module; Checked Criteria use it`.

### Task 2: List rows and two-field rows

**Files:**
- Modify: `metadata.js` (`addOverviewListRow`, `OVERVIEW_LIST_FIELDS`, `_syncOverviewListField`, `setOverviewList`, `addTwoFieldRow`, `_syncTwoFieldListField`, `initOverviewListFields`, `initTwoFieldListFields`)
- Test: `tests/e2e/test_projects_row_states_flows.py` (create)

**Interfaces:**
- Consumes: Task 1 (`rowActionsModel`, `rowActionsHtml`, `bindRowActions`, row contract).
- Produces: `addOverviewListRow(fieldId, value = '', accepted = false)` and `addTwoFieldRow(fieldId, field1 = '', field2 = '', accepted = false)`; `setOverviewList` and the load paths pass `accepted = true`; the add buttons create drafts. Complete = text not empty (two-field: at least one field). `_sync*` include only rows with `dataset.rowState !== 'draft'`.

- [ ] **Step 1: Failing e2e** (`test_new_list_row_is_a_draft_until_accepted`, Inclusion Criteria): add row, type text → check enabled, no `[data-f="remove"]`, hidden `#smEligInclusion` still empty and the Core badge not green; click check → remove cross appears, hidden field holds the text, badge green; Cancel on a second draft removes it. Same for Known issues (two-field). A loaded list (write `InclusionCriteria` into `project.json` before opening) shows defined rows.
- [ ] **Step 2: Run** the new e2e → FAIL.
- [ ] **Step 3: Implement** as in Interfaces. DOI rows: the lookup button stays as an optional helper next to the check in the draft state; after accept only the cross shows; `rowAction`/`updateAction` logic must not hide or restyle the accept button.
- [ ] **Step 4: Run** the new e2e and `pytest tests/e2e/test_projects_flows.py tests/test_projects_workflow_wiring.py -q`; fix tests that add rows then save by accepting them.
- [ ] **Step 5: Commit** `feat(projects): draft/accept for list and two-field rows`.

### Task 3: Authors and Funding

**Files:**
- Modify: `metadata.js` (`addAuthorRow`, author list wiring, `validateAuthorsBadge` inputs, `addFundingRow`, `setFundingRows`, `_syncFundingListField`)
- Test: `tests/e2e/test_projects_row_states_flows.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `addAuthorRow(firstName, lastName, extras, accepted = false)`; complete = first and last name filled (corresponding/email rules unchanged). `addFundingRow(agency, grant, accepted = false)`; complete = agency filled. Authors collected for the payload and `validateAuthorsBadge` count accepted rows only. The one placeholder funding row is an empty draft, recreated whenever the list becomes empty.

- [ ] **Step 1: Failing e2e**: new author is a draft with check (disabled until names filled), Core/REQUIRED author badge not satisfied until accepted; loaded authors are defined; funding: empty placeholder does not block saving and is not saved, a filled draft blocks (covered fully in Task 6), deleting the last funding row brings back an empty placeholder. Review Focus: load a project with authors/funding, save without touching → `project.json` unchanged.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** the e2e plus `pytest tests/e2e/test_projects_flows.py tests/test_projects_workflow_wiring.py -q` (update tests that add authors then save).
- [ ] **Step 5: Commit** `feat(projects): draft/accept for authors and funding`.

### Task 4: Missing files

**Files:**
- Modify: `metadata.js` (`addMissingFilesRow`, `combineMissingFilesRow` usage, the list's hidden-field sync), `missing-files-row.js` only if completeness needs a pure helper (add `isMissingFilesRowComplete(fields) -> boolean` there with a vitest in `missing-files-row.test.js`)
- Test: `tests/e2e/test_projects_row_states_flows.py`

**Interfaces:**
- Consumes: Task 1. Produces: `addMissingFilesRow(fields = {}, accepted = false)`; complete = what `combineMissingFilesRow` needs to yield a meaningful entry (read it first); drafts excluded from the sync.

- [ ] **Step 1: Failing tests** (vitest for `isMissingFilesRowComplete`, e2e draft → accept → defined). **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** both plus existing `missing-files-row.test.js`. **Step 5: Commit** `feat(projects): draft/accept for missing-files rows`.

### Task 5: Recruitment location picker (staged control)

**Files:**
- Modify: `metadata.js` (`addRecLocationRow`, the picker handlers for `recLocationQuery`, `recLocationResults`, `recLocationAddBtn`), `row-state.js` (`registerStagedControl`), `study_metadata.html` (Add button styled green with a check icon)
- Test: `tests/e2e/test_projects_row_states_flows.py`, `row-state.test.js`

**Interfaces:**
- Produces: `registerStagedControl(el: Element, hasContent: () => boolean)`; `findPending` includes staged controls whose `hasContent()` is true. For locations `hasContent` = query text non-empty or a result selected and not added, and false while "online only" is checked. Added location rows stay defined with the red cross.

- [ ] **Step 1: Failing tests**: vitest for `registerStagedControl` + `findPending` ordering is covered by e2e; e2e: typing into the search box makes `guardSave` pending (checked in Task 6 flow), the Add button is green with a check icon, an added location shows only the red cross.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement. Step 4: Run** the e2e. **Step 5: Commit** `feat(projects): staged location picker uses the same accept pattern`.

### Task 6: Save guard on both submit paths

**Files:**
- Modify: `create-project.js` (the `submit` handler at `createProjectFormEl`, and `submitCreateProject` entry), `metadata.js` (the `studyMetadataForm` submit handler)
- Test: `tests/e2e/test_projects_row_states_flows.py`

**Interfaces:**
- Consumes: `guardSave(form, showFeedback)` from Task 1, `showTopFeedback` from `helpers.js`.

- [ ] **Step 1: Failing e2e**: with a draft author holding text, `Create Project`, `Preliminary Save` (modal path) and `Save` for an opened project each send no POST (assert via `page.expect_request` timeout or by checking the file on disk is unchanged), show the warning, and mark the row `row-pending`; after clicking the check the save goes through and the file contains the author. An empty draft does not block. Switching project (`prism-project-changed`) leaves no drafts: add a `clearDrafts()` hook if needed.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** the guard call at the top of both handlers (return early when `false`). **Step 4: Run** the new e2e and the whole `tests/e2e/test_projects_*` set.
- [ ] **Step 5: Commit** `feat(projects): block saving while rows are pending`.

### Task 7: Docs, changelog, full run

**Files:**
- Modify: `docs/studio/projects.md` (a short "Adding rows" section: check, Cancel, red cross, blocked save), `CHANGELOG.md` (extend the existing entry or add one), screenshots are not required.

- [ ] **Step 1:** Write the docs. **Step 2: Run** `npx vitest run`, `pytest -q` (full, including e2e) → all pass. **Step 3: Commit** `docs(projects): row states and the save guard`.

Before merging: run `/ponytail:ponytail-audit` on the branch, apply what is worth it, re-run the tests, then finish the branch (this branch also contains the earlier eligibility GUI work).
