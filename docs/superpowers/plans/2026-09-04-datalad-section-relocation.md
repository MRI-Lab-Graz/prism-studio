# DataLad Section Relocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the "DataLad Version Control" block out of the blue "Project Loaded" summary panel on the Project Manager page (`/projects`) into its own collapsed-by-default card on the same page (matching the existing Study Metadata / Generate Methods Section / Global Settings accordion pattern), leaving only a compact status line + link in the "Project Loaded" panel.

**Architecture:** No new state, no new endpoints. The DataLad status/action markup (badge, hint text, progress bars, Enable/Save buttons) currently lives inside a JS template string in `renderLoadedProjectState()` (`open-project.js`) and is re-injected into the DOM every time a project loads. All of that markup's element IDs are already looked up fresh via `document.getElementById()` on every call (never cached), and the two button click handlers are already bound idempotently (`dataset.bound !== '1'` guard) — so the same markup can move into a static, always-present (but hidden-until-a-project-is-loaded) Jinja template section without touching the rendering/state logic itself. The "Project Loaded" panel keeps only a short link-out row (mirroring the existing "Need a full dataset check? → Open Validator" row already in that same panel) that expands the new card and scrolls to it.

**Tech Stack:** Flask/Jinja templates, vanilla JS (ES modules), Bootstrap 5 collapse, no new dependencies.

**Spec:** No separate spec document — this plan is scoped directly from a live UI review in this conversation. The user's ask: "put the datalad part out of the blue box, this is more a general decision than something we want to show as a summary of a project... hide it in general settings rather than popping up each time... maybe with a link." Decision made during investigation (see rationale below): a dedicated collapsed-by-default card on the *same* Project Manager page, not the literal "Global Settings" card and not the Share & Archive page.

**Why not Global Settings or Share & Archive:**
- Global Settings (`app/templates/includes/projects/settings_section.html`) is app-wide configuration (toggles, global library paths) submitted via one shared "Save Settings" form — it has no concept of "the current project" and isn't the right home for a per-project live-status widget with its own async actions.
- Share & Archive (`app/templates/share.html`) is gated behind having actual subject data (`nav-link ... title="No subjects found — add data before sharing"` in `app/templates/base.html:545`) — but DataLad should be enable-able immediately after creating an empty project, before any data exists. Putting it there would hide it exactly when it's most useful.
- A new card on the Project Manager page, collapsed by default like every other section already there, satisfies both stated goals: out of the "Project Loaded" summary, and not popping up every time.

## Global Constraints

- Every element ID referenced by existing DataLad JS (`projectBoxDataladStateBadge`, `projectBoxDataladEnableBtn`, `projectBoxDataladSaveBtn`, `projectBoxDataladProgressWrap`, `projectBoxDataladProgressBar`, `projectBoxDataladProgressLabel`, `projectBoxDataladSaveProgressWrap`, `projectBoxDataladSaveProgressBar`, `projectBoxDataladSaveProgressLabel`, `projectBoxDataladFeedback`) must be preserved exactly — do not rename any of them, since `renderProjectBoxDataladState()`, `bindProjectBoxDataladActions()`, and the save-progress helpers all look them up by these exact strings.
- No behavior change to DataLad enable/save/polling logic itself — only where its markup lives and how it's shown/hidden.
- Follow the existing accordion pattern verbatim (see `app/templates/includes/projects/study_metadata.html:1-16` and `app/templates/includes/projects/settings_section.html:1-9`): outer `<div id="...Card" style="display: none;">`, header with `data-bs-toggle="collapse" data-bs-target="#...Section" role="button" tabindex="0" aria-expanded="false" aria-controls="...Section"`, chevron `<i class="fas fa-chevron-down text-muted" id="...Chevron">`, inner `<div class="collapse" id="...Section"><div class="card-body">`.
- Tests: this repo has no JS unit-test runner; the established pattern for JS/template wiring is source-text assertions in `tests/test_projects_workflow_wiring.py` (e.g. `test_open_project_loaded_state_owns_datalad_actions`, `test_loaded_project_state_links_to_full_validator`). Follow that pattern — add `assertIn`/`assertNotIn` checks against the raw file contents, no placeholders.
- Every step in this plan must leave `python3 -m pytest tests/test_projects_workflow_wiring.py -q` passing.

---

## File Structure

- **Create** `app/templates/includes/projects/datalad_section.html` — the new static, collapsed-by-default card. Owns the DataLad markup that used to live inside the `renderLoadedProjectState()` JS template string.
- **Modify** `app/templates/includes/projects/page_sections.html` — add the new include, right after `open_form.html` (DataLad is project-scoped, so it belongs with "Project", not buried after Global Settings).
- **Modify** `app/static/js/modules/projects/open-project.js` — remove the DataLad `<div class="alert alert-light...">` block from `renderLoadedProjectState()`'s template string, replace with a compact link-out row; add `showDataladCard()` (mirrors `showMethodsCard()` in `metadata-methods.js:29-39`); call it after project load; add a delegated click handler that expands the new card and scrolls to it; return `showDataladCard` from `initOpenProjectController(...)`.
- **Modify** `app/static/js/modules/projects/core.js` — thread `showDataladCard` from `openProjectController` into `initProjectsPageBootstrap({...})`, same way `showMethodsCard`/`showStudyMetadataCard` are already threaded.
- **Modify** `app/static/js/modules/projects/page-bootstrap.js` — call `showDataladCard()` at initial page load (next to `showStudyMetadataCard(); showMethodsCard();`); add `{ element: 'dataladSection', chevron: 'dataladSectionChevron' }` to the existing chevron-rotation `sections` array (no new JS needed for the chevron flip — it's already generic).
- **Modify** `tests/test_projects_workflow_wiring.py` — add path constant + assertions for the new template and the relocated wiring.

---

### Task 1: Static DataLad card template

**Files:**
- Create: `app/templates/includes/projects/datalad_section.html`
- Modify: `app/templates/includes/projects/page_sections.html`
- Test: `tests/test_projects_workflow_wiring.py`

**Interfaces:**
- Produces: a card in the DOM, hidden by default (`id="dataladSectionCard" style="display: none;"`), containing the exact element IDs `projectBoxDataladStateBadge`, `projectBoxDataladStatus`, `projectBoxDataladHint`, `projectBoxDataladProgressWrap`, `projectBoxDataladProgressBar`, `projectBoxDataladProgressLabel`, `projectBoxDataladSaveProgressWrap`, `projectBoxDataladSaveProgressBar`, `projectBoxDataladSaveProgressLabel`, `projectBoxDataladFeedback`, `projectBoxDataladEnableBtn`, `projectBoxDataladSaveBtn`. Collapse target `id="dataladSection"`, chevron `id="dataladSectionChevron"`. Task 2 shows/hides `dataladSectionCard` and Task 2's page-bootstrap change wires the chevron.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_projects_workflow_wiring.py`, right after the `EXPORT_SECTION_TEMPLATE` constant (around line 123):

```python
DATALAD_SECTION_TEMPLATE = (
    REPO_ROOT / "app" / "templates" / "includes" / "projects" / "datalad_section.html"
)
```

Add a new test method to `TestProjectsWorkflowWiring` (put it right after `test_open_project_loaded_state_owns_datalad_actions`, around line 224):

```python
    def test_datalad_section_template_owns_static_datalad_markup(self):
        self.assertTrue(DATALAD_SECTION_TEMPLATE.exists())
        content = DATALAD_SECTION_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="dataladSectionCard"', content)
        self.assertIn('style="display: none;"', content)
        self.assertIn('data-bs-target="#dataladSection"', content)
        self.assertIn('aria-controls="dataladSection"', content)
        self.assertIn('id="dataladSectionChevron"', content)
        self.assertIn('class="collapse" id="dataladSection"', content)
        self.assertIn('id="projectBoxDataladStateBadge"', content)
        self.assertIn('id="projectBoxDataladStatus"', content)
        self.assertIn('id="projectBoxDataladHint"', content)
        self.assertIn('id="projectBoxDataladProgressWrap"', content)
        self.assertIn('id="projectBoxDataladProgressBar"', content)
        self.assertIn('id="projectBoxDataladProgressLabel"', content)
        self.assertIn('id="projectBoxDataladSaveProgressWrap"', content)
        self.assertIn('id="projectBoxDataladSaveProgressBar"', content)
        self.assertIn('id="projectBoxDataladSaveProgressLabel"', content)
        self.assertIn('id="projectBoxDataladFeedback"', content)
        self.assertIn('id="projectBoxDataladEnableBtn"', content)
        self.assertIn('id="projectBoxDataladSaveBtn"', content)
        self.assertIn('href="https://www.datalad.org/"', content)

        page_sections_content = PAGE_SECTIONS_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn(
            "{% include 'includes/projects/datalad_section.html' %}",
            page_sections_content,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_projects_workflow_wiring.py::TestProjectsWorkflowWiring::test_datalad_section_template_owns_static_datalad_markup -v`
Expected: FAIL — `DATALAD_SECTION_TEMPLATE` does not exist yet (`AssertionError` on `self.assertTrue(...)`, or a `NameError` if the constant itself isn't defined yet — either failure mode confirms the test is exercising code that doesn't exist yet).

- [ ] **Step 3: Create the template**

Create `app/templates/includes/projects/datalad_section.html`:

```html
    <!-- DataLad Version Control Card -->
    <div class="card shadow-sm mt-4" id="dataladSectionCard" style="display: none;">
        <div class="card-header bg-light" data-bs-toggle="collapse" data-bs-target="#dataladSection"
             role="button" tabindex="0" aria-expanded="false" aria-controls="dataladSection">
            <h5 class="mb-0 d-flex justify-content-between align-items-center">
                <span><i class="fas fa-code-branch text-secondary me-2"></i>DataLad Version Control</span>
                <i class="fas fa-chevron-down text-muted" id="dataladSectionChevron"></i>
            </h5>
        </div>
        <div class="collapse" id="dataladSection">
        <div class="card-body">
            <div class="d-flex flex-column flex-lg-row justify-content-between align-items-lg-start gap-3">
                <div>
                    <div class="d-flex align-items-center gap-2 flex-wrap">
                        <span class="badge rounded-pill bg-light text-muted border" id="projectBoxDataladStateBadge">Not tracked</span>
                        <a href="https://www.datalad.org/" target="_blank" rel="noopener noreferrer" class="small text-muted" title="What is DataLad?">(?)</a>
                    </div>
                    <div class="small text-muted mt-2" id="projectBoxDataladStatus">Checking DataLad status...</div>
                    <div class="small text-muted mt-1" id="projectBoxDataladHint">DataLad version control is not enabled for this project.</div>
                    <div class="mt-2 d-none" id="projectBoxDataladProgressWrap">
                        <div class="small text-muted mb-1" id="projectBoxDataladProgressLabel"></div>
                        <div class="progress" style="height: 0.7rem;">
                            <div class="progress-bar bg-success" id="projectBoxDataladProgressBar" role="progressbar" style="width: 0%;" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
                        </div>
                    </div>
                    <div class="mt-2 d-none" id="projectBoxDataladSaveProgressWrap">
                        <div class="small text-muted mb-1" id="projectBoxDataladSaveProgressLabel"></div>
                        <div class="progress" style="height: 0.85rem;">
                            <div class="progress-bar bg-primary progress-bar-striped progress-bar-animated" id="projectBoxDataladSaveProgressBar" role="progressbar" style="width: 0%;" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
                        </div>
                    </div>
                    <div class="small mt-2 d-none" id="projectBoxDataladFeedback" aria-live="polite"></div>
                </div>
                <div class="d-flex gap-2 flex-wrap justify-content-lg-end">
                    <button type="button" class="btn btn-sm btn-outline-primary" id="projectBoxDataladEnableBtn">
                        <i class="fas fa-plus me-1"></i>Enable DataLad
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-success" id="projectBoxDataladSaveBtn">
                        <i class="fas fa-floppy-disk me-1"></i>Save DataLad Snapshot
                    </button>
                </div>
            </div>
        </div>
        </div>
    </div>
```

Then modify `app/templates/includes/projects/page_sections.html` (currently 6 lines):

```html
    {% include 'includes/projects/create_form.html' %}
    {% include 'includes/projects/init_bids_form.html' %}
    {% include 'includes/projects/open_form.html' %}
    {% include 'includes/projects/datalad_section.html' %}
    {% include 'includes/projects/study_metadata.html' %}
    {% include 'includes/projects/methods_section.html' %}
    {% include 'includes/projects/settings_section.html' %}
```

(only the new line after `open_form.html` is new — the rest is unchanged, just shown for context.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_projects_workflow_wiring.py::TestProjectsWorkflowWiring::test_datalad_section_template_owns_static_datalad_markup -v`
Expected: PASS

- [ ] **Step 5: Run the full workflow-wiring suite to check nothing else broke**

Run: `python3 -m pytest tests/test_projects_workflow_wiring.py tests/test_shared_section_card_template_rendering.py -q`
Expected: all PASS. (At this point the card is dead markup — nothing shows or hides it yet, and `renderLoadedProjectState()` still renders its own copy of the same IDs into the blue box, so the page has two elements with the same ID. That duplication is resolved in Task 2 and is why Task 2 must land before this is deployed — do not ship Task 1 alone.)

- [ ] **Step 6: Commit**

```bash
git add app/templates/includes/projects/datalad_section.html app/templates/includes/projects/page_sections.html tests/test_projects_workflow_wiring.py
git commit -m "feat: add static DataLad Version Control card to Project Manager page"
```

---

### Task 2: Remove the inline DataLad block from the "Project Loaded" panel, replace with a compact link, wire show/hide

**Files:**
- Modify: `app/static/js/modules/projects/open-project.js:1097-1173` (the `renderLoadedProjectState()` function and its DataLad block)
- Modify: `app/static/js/modules/projects/open-project.js:29-39` region and `:1236-1268` region (new `showDataladCard()` function + calling it + returning it)
- Modify: `app/static/js/modules/projects/core.js:238-254`
- Modify: `app/static/js/modules/projects/page-bootstrap.js:1-26,73-92`
- Test: `tests/test_projects_workflow_wiring.py`

**Interfaces:**
- Consumes: `getCurrentProjectState()` (already a constructor param of `initOpenProjectController`, used elsewhere in the same file, e.g. line 691).
- Produces: `showDataladCard()` — exported from `initOpenProjectController(...)`'s return object (alongside the existing `getOpenProjectActionPath`, `loadProjectWithoutValidation`), takes no arguments, returns nothing. Toggles `#dataladSectionCard`'s `style.display` between `'block'` and `'none'` based on whether `getCurrentProjectState().path` is truthy — exact same condition `showMethodsCard()` already uses in `metadata-methods.js:38`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_projects_workflow_wiring.py`, right after `test_loaded_project_state_links_to_full_validator` (around line 864):

```python
    def test_loaded_project_state_links_out_to_datalad_card_instead_of_inlining_it(self):
        content = PROJECTS_OPEN_PROJECT_MODULE.read_text(encoding="utf-8")

        # The old inline block must be gone from renderLoadedProjectState's template.
        self.assertNotIn("DataLad Version Control</strong>", content)
        self.assertNotIn(
            "DataLad adds Git-based version control to your project, useful for tracking changes over time. Click Enable DataLad to get started.",
            content,
        )

        # A compact link-out row takes its place, matching the existing
        # "Need a full dataset check?" pattern already in the same panel.
        self.assertIn('id="projectLoadedManageDataladLink"', content)
        self.assertIn('href="#dataladSection"', content)
        self.assertIn("DataLad adds Git-based version control any time", content)

        # showDataladCard mirrors showMethodsCard's show/hide-on-project-loaded logic.
        self.assertIn("function showDataladCard()", content)
        self.assertIn("dataladSectionCard", content)
        self.assertIn("return {", content)
        self.assertIn("showDataladCard,", content)

    def test_datalad_card_visibility_is_wired_through_bootstrap_like_methods_card(self):
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")
        bootstrap_content = PROJECTS_BOOTSTRAP_MODULE.read_text(encoding="utf-8")

        self.assertIn("const showDataladCard = openProjectController.showDataladCard;", core_content)
        self.assertIn("showDataladCard,", core_content)

        self.assertIn("showDataladCard();", bootstrap_content)
        self.assertIn(
            "{ element: 'dataladSection', chevron: 'dataladSectionChevron' }",
            bootstrap_content,
        )
```

(`PROJECTS_OPEN_PROJECT_MODULE` (line 70) and `PROJECTS_BOOTSTRAP_MODULE` (line 61) already exist as constants earlier in this file — reuse them, don't add duplicate path constants.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_projects_workflow_wiring.py -k "datalad_card or links_out_to_datalad" -v`
Expected: FAIL on both new tests — the old inline block is still there, `showDataladCard` doesn't exist anywhere yet.

- [ ] **Step 3: Replace the inline block in `renderLoadedProjectState()`**

In `app/static/js/modules/projects/open-project.js`, replace lines 1124-1157 (the entire `<div class="alert alert-light border mt-3 mb-0" role="status">...DataLad Version Control...</div>` block, from the opening `<div class="alert alert-light border mt-3 mb-0" role="status">` through its matching closing `</div>` right before `<div class="d-flex flex-column align-items-end mt-2">`) with:

```javascript
                <div class="alert alert-light border mt-3 mb-0 d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2" role="status">
                    <div>
                        <strong><i class="fas fa-code-branch me-1"></i>Version control</strong>
                        <span class="ms-1">DataLad adds Git-based version control any time you're ready &mdash; no rush.</span>
                    </div>
                    <a href="#dataladSection" class="btn btn-sm btn-outline-secondary" id="projectLoadedManageDataladLink">
                        <i class="fas fa-arrow-down me-1"></i>Manage DataLad
                    </a>
                </div>
```

- [ ] **Step 4: Add `showDataladCard()` and call it after a project loads**

In `app/static/js/modules/projects/open-project.js`, add a new function right after `getOpenProjectActionPath` (currently ends around line 1164, just before `async function loadProjectWithoutValidation(...)`):

```javascript
    function showDataladCard() {
        const card = document.getElementById('dataladSectionCard');
        if (!card) return;
        card.style.display = getCurrentProjectState().path ? 'block' : 'none';
    }
```

Then, inside `loadProjectWithoutValidation`, find this existing block (originally around line 1229-1231):

```javascript
            showStudyMetadataCard();
            updateCreateProjectButton();
            showMethodsCard();
```

and change it to:

```javascript
            showStudyMetadataCard();
            updateCreateProjectButton();
            showMethodsCard();
            showDataladCard();
```

- [ ] **Step 5: Return `showDataladCard` from the controller**

At the bottom of `initOpenProjectController(...)` (originally around line 1263-1266):

```javascript
    return {
        getOpenProjectActionPath,
        loadProjectWithoutValidation,
    };
```

Change to:

```javascript
    return {
        getOpenProjectActionPath,
        loadProjectWithoutValidation,
        showDataladCard,
    };
```

- [ ] **Step 6: Add the delegated "Manage DataLad" click handler**

`#projectLoadedManageDataladLink` is re-created every time `renderLoadedProjectState()` runs (same situation as `#projectBoxDeleteBtn`, see the delegation comment at the top of `delete-project.js`), so bind on `document` once, near the other module-level listener registrations in `open-project.js` (right after the `const openProjectForm = ...` block, before the final `return { ... }`):

```javascript
    document.addEventListener('click', function(event) {
        const link = event.target.closest ? event.target.closest('#projectLoadedManageDataladLink') : null;
        if (!link) return;
        event.preventDefault();

        const collapseEl = document.getElementById('dataladSection');
        const cardEl = document.getElementById('dataladSectionCard');
        if (!collapseEl || !cardEl) return;

        cardEl.style.display = 'block';
        if (window.bootstrap && typeof window.bootstrap.Collapse === 'function') {
            window.bootstrap.Collapse.getOrCreateInstance(collapseEl).show();
        }
        cardEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
```

- [ ] **Step 7: Thread `showDataladCard` through `core.js`**

In `app/static/js/modules/projects/core.js`, right after (currently around line 254):

```javascript
const getOpenProjectActionPath = openProjectController.getOpenProjectActionPath;
const loadProjectWithoutValidation = openProjectController.loadProjectWithoutValidation;
```

add:

```javascript
const showDataladCard = openProjectController.showDataladCard;
```

Then in the `initProjectsPage()` function's call to `initProjectsPageBootstrap({...})` (currently starting around line 278), add `showDataladCard,` to the object — put it next to the existing `showMethodsCard,` line (around line 287):

```javascript
        showStudyMetadataCard,
        showMethodsCard,
        showDataladCard,
```

- [ ] **Step 8: Wire it into `page-bootstrap.js`**

In `app/static/js/modules/projects/page-bootstrap.js`, add `showDataladCard` to the destructured parameters of `initProjectsPageBootstrap({...})` (currently lines 1-26) — add it next to `showMethodsCard,` (line 10):

```javascript
    showStudyMetadataCard,
    showMethodsCard,
    showDataladCard,
```

Then call it at init, next to the existing calls (currently lines 75-76):

```javascript
    showStudyMetadataCard();
    showMethodsCard();
    showDataladCard();
```

Finally, add the new section to the chevron-rotation list (currently lines 86-92):

```javascript
    const sections = [
        { element: 'openProjectSection', chevron: 'openProjectChevron' },
        { element: 'studyMetadataSection', chevron: 'studyMetadataChevron' },
        { element: 'methodsSectionBody', chevron: 'methodsSectionChevron' },
        { element: 'dataladSection', chevron: 'dataladSectionChevron' },
        { element: 'exportSection', chevron: 'exportChevron' },
        { element: 'settingsSection', chevron: 'settingsChevron' }
    ];
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_projects_workflow_wiring.py -q`
Expected: all PASS, including the two new tests from Step 1.

- [ ] **Step 10: Manual browser verification**

Per this repo's UI-change policy, start the dev server and drive the real flow before treating this as done — a passing text-assertion test does not prove the feature works:

```bash
cd app && python3 prism-studio.py --no-browser --port 5099 &
```

Then, in a browser (or via the same Playwright pattern already used earlier in this session):
1. Create a fresh project. Confirm the "Project Loaded" panel's DataLad block is now a single compact line ending in a "Manage DataLad" button, not the full badge/progress/buttons block.
2. Confirm a new "DataLad Version Control" card appears further down the page (after "Project", before "Study Metadata"), collapsed by default.
3. Click "Manage DataLad" in the "Project Loaded" panel. Confirm the DataLad card expands (chevron flips down→up) and the page scrolls to it.
4. Click the DataLad card's own header. Confirm it collapses/expands like every other section on the page.
5. Click "Enable DataLad" from inside the new card. Confirm the existing enable flow (confirmation dialog, progress bar, badge updating to "Tracked") still works exactly as before — this proves Task 1/2 didn't change any DataLad *logic*, only where its markup lives.
6. Reload the page with `?preserve_current=1` (the URL the top nav uses when a project is already loaded — see `app/src/web/blueprints/projects.py:273`). Confirm the DataLad card is visible (not hidden) on a fresh page load, not just after an in-page project load.

Stop the dev server afterward:

```bash
kill %1
```

- [ ] **Step 11: Commit**

```bash
git add app/static/js/modules/projects/open-project.js app/static/js/modules/projects/core.js app/static/js/modules/projects/page-bootstrap.js tests/test_projects_workflow_wiring.py
git commit -m "refactor: move DataLad controls into their own collapsed card, link out from Project Loaded panel"
```

---

## Self-Review

**1. Spec coverage:**
- "put the datalad part out of the blue box" → Task 2 Step 3 removes it from `renderLoadedProjectState()`.
- "this is more a general decision... hide it... rather than popping up each time" → Task 1 creates it as collapsed-by-default (`aria-expanded="false"`, no `.show` class), matching Study Metadata / Methods / Settings.
- "any better place for datalad" → addressed in the plan header's rationale (own card on the same page, not Global Settings or Share & Archive, with reasons grounded in actual gating/semantics found in the code).
- "with a link (you can convert your project into datalad: follow the link here)" → Task 2 Steps 3 and 6 add the "Manage DataLad" link and its expand+scroll behavior.

**2. Placeholder scan:** No TBD/TODO/"add appropriate X" phrasing; every step has literal code. `PROJECTS_OPEN_PROJECT_MODULE` (line 70) and `PROJECTS_BOOTSTRAP_MODULE` (line 61) were confirmed to exist under those exact names in `tests/test_projects_workflow_wiring.py` — Task 2 Step 1 uses them directly, no lookup left for the executor.

**3. Type consistency:** `showDataladCard` — zero-argument function, defined once in `open-project.js`, threaded by reference (not re-implemented) through `core.js` and into `page-bootstrap.js`'s destructured params; same name used everywhere. Element IDs (`dataladSectionCard`, `dataladSection`, `dataladSectionChevron`, `projectLoadedManageDataladLink`) are each defined in exactly one place (Task 1's new template, or Task 2's new compact link) and referenced by the same string everywhere else — no drift between a `Card`/`Section`/`Chevron` triad here and a differently-named one elsewhere, matching the existing `studyMetadataCard`/`studyMetadataSection`/`studyMetadataChevron` and `methodsSectionCard`/`methodsSectionBody`/`methodsSectionChevron` triads already in the codebase.
