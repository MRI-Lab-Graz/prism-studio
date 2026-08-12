# Study Metadata Badge Tier UX Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three UX problems on the Study Metadata section's REQUIRED/CORE/FAIR badge system, surfaced while testing the tier-badge logic fixes from earlier this session: (1) the "CORE" tier badge is visually indistinguishable from the green "filled/done" state because this theme's `--bs-primary` and `--bs-success` are both near-identical dark greens, (2) the REQUIRED/CORE/FAIR explainer box is invisible whenever the user has the site-wide "beginner help" toggle off, even though it's reference information, not a dismissible tip, and (3) the Ethics Approvals / Funding Yes-No toggle box renders with unexplained extra empty space now that its red "unanswered" border is actually reachable (fixed earlier this session).

**Architecture:** All three are scoped, additive fixes to `app/static/js/modules/projects/validation.js`, `app/static/css/projects/metadata.css`, and `app/templates/includes/projects/study_metadata.html` — no data model or backend changes. Task 1 introduces one new CSS class (`.badge-tier-core`) instead of touching the global `--bs-primary` theme token, which is used across the entire app and out of scope. Task 2 removes a class, no new code. Task 3 starts with a live-browser diagnosis step (the root cause isn't conclusively determined from static analysis alone) before committing to a specific CSS fix.

**Tech Stack:** Vanilla JS (ES modules), Bootstrap 5 (bootswatch-litera base + `studio-theme.css` overrides), Jinja2 templates, vitest (`node` environment, no DOM), pytest.

## Global Constraints

- Do not modify `--bs-primary` / `--studio-semantic-primary` in `app/static/css/studio-theme.css` — that token drives buttons, links, and branding across the entire app; the collision is specific to this one badge use case, not a reason to re-theme the app.
- Do not touch the `colorClass` logic in `updateCompletenessUI()` (`app/static/js/modules/projects/metadata.js`, the header progress-bar `bg-primary`/`bg-success`/`bg-warning`/`bg-danger` score-range coloring) — same green-collision family of issue, but a different, unreported code path. Out of scope for this plan.
- Every task must leave `npx vitest run app/static/js/modules/projects/` and the relevant `pytest` selection green before commit.
- Follow existing code patterns: badge coloring logic is centralized in `updateBadgeColor()` (`validation.js`); don't duplicate tier-color decisions elsewhere.

---

### Task 1: Fix CORE-tier badge/success color collision

**Files:**
- Modify: `app/static/css/projects/metadata.css`
- Modify: `app/static/js/modules/projects/validation.js:310-345` (`updateBadgeColor`)
- Modify: `app/templates/includes/projects/study_metadata.html` (9 occurrences of `bg-primary` on CORE-tier badges)
- Test: `app/static/js/modules/projects/validation.test.js`

**Interfaces:**
- Consumes: nothing new.
- Produces: CSS class `.badge-tier-core`, used wherever a CORE-tier badge is rendered (static HTML and `updateBadgeColor()`).

**Root cause:** `app/static/css/studio-theme.css:20-24` sets `--studio-semantic-primary: #1f8b5c` and `--studio-semantic-success: #2c9a62` — both dark greens, close enough in hue/lightness to be visually indistinguishable at badge size. `updateBadgeColor()` in `validation.js` applies `bg-primary` to an *unfilled* CORE badge and `bg-success` to *any filled* badge — so an empty, unanswered CORE field's badge and a genuinely-complete field's badge render the same color. (The existing debug log at `validation.js:335` already says `"turned BLUE"` — confirming the original intent was a color distinct from success-green; the theme override silently broke that.)

- [ ] **Step 1: Add the `.badge-tier-core` CSS rule**

Add to `app/static/css/projects/metadata.css` (near the other `.sm-choice-group`/badge-adjacent rules, e.g. directly after the existing rules ending around line 112):

```css
/* CORE-tier field badge - deliberately NOT bg-primary/bg-success. This
   theme's --bs-primary (#1f8b5c) and --bs-success (#2c9a62) are both dark
   greens, close enough that an unfilled CORE badge and a filled/"done"
   badge were visually indistinguishable. A true blue keeps "this is a
   CORE field" and "this field is filled" unambiguous at a glance. */
.badge-tier-core {
    background-color: #0d6efd !important;
    color: #fff !important;
}
```

- [ ] **Step 2: Update `updateBadgeColor()` to use the new class**

In `app/static/js/modules/projects/validation.js`, current code (lines 310-345):

```javascript
function updateBadgeColor(badge, isFilled) {
    if (!badge) {
        debugWarn('Badge element is null');
        return;
    }
    
    const badgeText = badge.textContent.trim();
    debugLog(`updateBadgeColor: "${badgeText}" isFilled=${isFilled}`);
    
    if (isFilled) {
        removeClass(badge, 'bg-danger');
        removeClass(badge, 'bg-warning');
        removeClass(badge, 'bg-secondary');
        removeClass(badge, 'bg-primary');
        removeClass(badge, 'text-dark');
        addClass(badge, 'bg-success');
        debugLog(`Badge "${badgeText}" turned GREEN`);
    } else {
        removeClass(badge, 'bg-success');
        const text = badge.textContent.trim();
        if (text === 'REQUIRED') {
            addClass(badge, 'bg-danger');
            debugLog(`Badge "${badgeText}" turned RED`);
        } else if (text === 'CORE') {
            addClass(badge, 'bg-primary');
            debugLog(`Badge "${badgeText}" turned BLUE (readiness-tier, not creation-blocking)`);
        } else if (text === 'RECOMMENDED') {
            addClass(badge, 'bg-warning');
            addClass(badge, 'text-dark');
            debugLog(`Badge "${badgeText}" turned YELLOW`);
        } else if (text === 'OPTIONAL') {
            addClass(badge, 'bg-secondary');
            debugLog(`Badge "${badgeText}" turned GRAY`);
        }
    }
}
```

Replace with:

```javascript
function updateBadgeColor(badge, isFilled) {
    if (!badge) {
        debugWarn('Badge element is null');
        return;
    }
    
    const badgeText = badge.textContent.trim();
    debugLog(`updateBadgeColor: "${badgeText}" isFilled=${isFilled}`);
    
    if (isFilled) {
        removeClass(badge, 'bg-danger');
        removeClass(badge, 'bg-warning');
        removeClass(badge, 'bg-secondary');
        removeClass(badge, 'bg-primary');
        removeClass(badge, 'badge-tier-core');
        removeClass(badge, 'text-dark');
        addClass(badge, 'bg-success');
        debugLog(`Badge "${badgeText}" turned GREEN`);
    } else {
        removeClass(badge, 'bg-success');
        const text = badge.textContent.trim();
        if (text === 'REQUIRED') {
            addClass(badge, 'bg-danger');
            debugLog(`Badge "${badgeText}" turned RED`);
        } else if (text === 'CORE') {
            addClass(badge, 'badge-tier-core');
            debugLog(`Badge "${badgeText}" turned BLUE (readiness-tier, not creation-blocking)`);
        } else if (text === 'RECOMMENDED') {
            addClass(badge, 'bg-warning');
            addClass(badge, 'text-dark');
            debugLog(`Badge "${badgeText}" turned YELLOW`);
        } else if (text === 'OPTIONAL') {
            addClass(badge, 'bg-secondary');
            debugLog(`Badge "${badgeText}" turned GRAY`);
        }
    }
}
```

- [ ] **Step 3: Write the failing test**

Add to `app/static/js/modules/projects/validation.test.js` (this file already stubs `globalThis.window = globalThis` and dynamically imports `validation.js` — reuse that setup, add a badge stub and import `updateBadgeColor` isn't exported today, so export it first — see Step 3a).

**Step 3a — export `updateBadgeColor`:** in `validation.js`, change `function updateBadgeColor(badge, isFilled) {` to `export function updateBadgeColor(badge, isFilled) {`. No call sites need updating (same-module callers use the bare name; ES modules allow a function to be both locally referenced and exported).

Add to `app/static/js/modules/projects/validation.test.js`:

```javascript
function stubBadge(initialText, initialClasses = []) {
    const classes = new Set(initialClasses);
    return {
        textContent: initialText,
        classList: {
            add: (c) => classes.add(c),
            remove: (c) => classes.delete(c),
            contains: (c) => classes.has(c),
        },
        classes,
    };
}

describe('updateBadgeColor', () => {
    it('gives an unfilled CORE badge a color distinct from the filled/success color', async () => {
        const { updateBadgeColor } = await import('./validation.js');
        const badge = stubBadge('CORE');

        updateBadgeColor(badge, false);
        expect(badge.classes.has('badge-tier-core')).toBe(true);
        expect(badge.classes.has('bg-success')).toBe(false);
        expect(badge.classes.has('bg-primary')).toBe(false);
    });

    it('turns a filled CORE badge bg-success and strips the tier color', async () => {
        const { updateBadgeColor } = await import('./validation.js');
        const badge = stubBadge('CORE');

        updateBadgeColor(badge, false);
        updateBadgeColor(badge, true);
        expect(badge.classes.has('bg-success')).toBe(true);
        expect(badge.classes.has('badge-tier-core')).toBe(false);
    });
});
```

- [ ] **Step 4: Run the test to verify it fails before Step 2's fix (sanity check on a clean stash), then passes after**

Run: `npx vitest run app/static/js/modules/projects/validation.test.js`
Expected after Steps 1-3: PASS (2 new tests, plus the existing 4 `setRequiredFieldBorder` tests still passing = 6 total in this file).

- [ ] **Step 5: Swap the 9 static `bg-primary` CORE badges in the template**

In `app/templates/includes/projects/study_metadata.html`, these are the exact current occurrences (verify with `grep -n 'badge bg-primary' app/templates/includes/projects/study_metadata.html` — should list lines 21, 113, 136, 143, 264, 352, 466, 521, with line 21 containing two occurrences):

Line 21 (the legend added earlier this session) — replace:
```html
<span class="badge bg-primary">CORE</span> and <span class="badge bg-secondary">OPTIONAL</span> fields never block creation &mdash; they drive the Methods Readiness / FAIR score below instead (CORE fields matter most for that score). Each section below shows its own <span class="badge bg-danger bg-opacity-75">Required</span>/<span class="badge bg-primary bg-opacity-75">Core</span>/<span class="badge bg-warning text-dark bg-opacity-75">FAIR</span> tally so you can see what's missing without expanding it.
```
with:
```html
<span class="badge badge-tier-core">CORE</span> and <span class="badge bg-secondary">OPTIONAL</span> fields never block creation &mdash; they drive the Methods Readiness / FAIR score below instead (CORE fields matter most for that score). Each section below shows its own <span class="badge bg-danger bg-opacity-75">Required</span>/<span class="badge badge-tier-core bg-opacity-75">Core</span>/<span class="badge bg-warning text-dark bg-opacity-75">FAIR</span> tally so you can see what's missing without expanding it.
```

Line 113 — replace:
```html
<span class="badge bg-primary" id="metadataEthicsRequiredBadge">CORE</span> Ethics Approvals
```
with:
```html
<span class="badge badge-tier-core" id="metadataEthicsRequiredBadge">CORE</span> Ethics Approvals
```

Line 136 — replace:
```html
<span class="badge bg-primary">CORE</span> Keywords (comma-separated)
```
with:
```html
<span class="badge badge-tier-core">CORE</span> Keywords (comma-separated)
```

Line 143 — replace:
```html
<span class="badge bg-primary" id="metadataFundingRequiredBadge">CORE</span> Funding
```
with:
```html
<span class="badge badge-tier-core" id="metadataFundingRequiredBadge">CORE</span> Funding
```

Line 264 — replace:
```html
<span class="badge bg-primary">CORE</span> Study Design Type
```
with:
```html
<span class="badge badge-tier-core">CORE</span> Study Design Type
```

Line 352 — replace:
```html
<span class="badge bg-primary" id="smRecMethodRequiredBadge">CORE</span> Method
```
with:
```html
<span class="badge badge-tier-core" id="smRecMethodRequiredBadge">CORE</span> Method
```

Line 466 — replace:
```html
<span class="badge bg-primary" id="smEligCriteriaRequiredBadge">CORE</span> Inclusion Criteria
```
with:
```html
<span class="badge badge-tier-core" id="smEligCriteriaRequiredBadge">CORE</span> Inclusion Criteria
```

Line 521 — replace:
```html
<span class="badge bg-primary">CORE</span> Overview
```
with:
```html
<span class="badge badge-tier-core">CORE</span> Overview
```

After this step, confirm no CORE-tier badge still uses bare `bg-primary`: `grep -n 'badge bg-primary' app/templates/includes/projects/study_metadata.html` must return no output.

- [ ] **Step 6: Also update `app/static/js/modules/projects/metadata.js`'s per-section "Core X/Y" badge rendering for visual consistency**

This isn't the same collision (that code uses `text-success`/`text-danger`/`bg-success`/`bg-danger` ratio coloring, not a static tier color — see Global Constraints), so no code change needed here. This step is a **verification-only** checkpoint: confirm `grep -n "Core \${reqFilled}" app/static/js/modules/projects/metadata.js` shows no `bg-primary`/`text-primary` usage (it shouldn't — this was already ratio-based, not tier-based).

- [ ] **Step 7: Run the full JS suite**

Run: `npx vitest run app/static/js/modules/projects/`
Expected: all test files pass (4 files now, up from 3), including the 2 new tests from Step 3.

- [ ] **Step 8: Manual visual check**

Use the `run` skill to start the dev server, open an existing project's Study Metadata > Basics section with Ethics Approvals/Keywords/Funding empty. Confirm: CORE badges (Ethics Approvals, Keywords, Funding, Study Design Type, Method, Inclusion Criteria, Procedure Overview) render a clearly distinct blue, not the same green as a filled/green badge elsewhere on the page (e.g. Metadata Sync / Citation Health status dots, which use `text-success`).

- [ ] **Step 9: Commit**

```bash
git add app/static/css/projects/metadata.css app/static/js/modules/projects/validation.js app/static/js/modules/projects/validation.test.js app/templates/includes/projects/study_metadata.html
git commit -m "fix: give CORE-tier badges a color distinct from the filled/success green"
```

---

### Task 2: Make the REQUIRED/CORE/FAIR legend always visible

**Files:**
- Modify: `app/templates/includes/projects/study_metadata.html:18`
- Test: `tests/test_projects_workflow_wiring.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new (removes a class).

**Root cause:** The legend box (`#smFieldTierLegend`, added earlier this session, currently at `study_metadata.html:18-22`) carries the `beginner-help-block` class, which puts it under the control of the site-wide "beginner help mode" toggle (`app/static/js/global-help-mode.js`). That toggle defaults to *on* for new users (`readMode()` returns `true` when `localStorage` has never been set — `global-help-mode.js:309-317`), but any user who has previously turned it off site-wide (e.g. an experienced user dismissing onboarding tips elsewhere in the app) loses this legend too — even though it's reference information about what the badges mean, not a dismissible beginner tip. `.beginner-help-block` itself only contributes `position: relative; padding-right: 1.75rem;` (space for the dismiss toggle button, `base.html:301-303`) — all the actual box styling (background, border, padding) comes from the `alert alert-primary border-0 bg-primary bg-opacity-10 py-2 mb-3` classes already on the div, so removing `beginner-help-block` doesn't lose any visual styling.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_projects_workflow_wiring.py` (this file already defines `STUDY_METADATA_TEMPLATE` as a path constant at line 108-110 — reuse it):

```python
    def test_field_tier_legend_is_not_gated_by_beginner_help_mode(self):
        content = STUDY_METADATA_TEMPLATE.read_text(encoding="utf-8")

        legend_match = re.search(
            r'<div class="([^"]*)" id="smFieldTierLegend">', content
        )
        self.assertIsNotNone(
            legend_match, "smFieldTierLegend element not found in template"
        )
        legend_classes = legend_match.group(1).split()
        self.assertNotIn(
            "beginner-help-block",
            legend_classes,
            "REQUIRED/CORE/FAIR legend must not be dismissible via the "
            "site-wide beginner-help-mode toggle - it's reference info, "
            "not a beginner tip, and should always be visible.",
        )
        self.assertIn("alert", legend_classes)
```

Confirm `re` is already imported at the top of `tests/test_projects_workflow_wiring.py` (grep `^import re`); add `import re` near the other stdlib imports if not present.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_projects_workflow_wiring.py::TestProjectsWorkflowWiring::test_field_tier_legend_is_not_gated_by_beginner_help_mode -v`
Expected: FAIL (current class list includes `beginner-help-block`).

- [ ] **Step 3: Remove the class**

In `app/templates/includes/projects/study_metadata.html`, current line 18:
```html
            <div class="alert alert-primary border-0 bg-primary bg-opacity-10 py-2 mb-3 beginner-help-block" id="smFieldTierLegend">
```
Replace with:
```html
            <div class="alert alert-primary border-0 bg-primary bg-opacity-10 py-2 mb-3" id="smFieldTierLegend">
```

(Note: the `bg-primary bg-opacity-10` here is Bootstrap's tinted-background alert utility, unrelated to Task 1's CORE-badge collision — leave as-is.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_projects_workflow_wiring.py::TestProjectsWorkflowWiring::test_field_tier_legend_is_not_gated_by_beginner_help_mode -v`
Expected: PASS.

- [ ] **Step 5: Manual visual check**

Use the `run` skill to start the dev server. In the browser devtools console, run `localStorage.setItem('prism_beginner_help_mode', '0')` and reload an existing project's Study Metadata section. Confirm the REQUIRED/CORE/FAIR legend is still visible at the top of the section while other `.beginner-help-block` hints elsewhere on the page (if any are visible on this page) are collapsed/hidden.

- [ ] **Step 6: Commit**

```bash
git add app/templates/includes/projects/study_metadata.html tests/test_projects_workflow_wiring.py
git commit -m "fix: always show the REQUIRED/CORE/FAIR legend, independent of beginner-help-mode"
```

---

### Task 3: Fix empty space in the Ethics/Funding Yes-No toggle box

**Files:**
- Modify: `app/static/css/projects/metadata.css` (`.sm-choice-group`, exact rule TBD by Step 1's diagnosis)
- Test: manual visual verification (no automated DOM test exists for layout/width in this repo's toolchain — `vitest` runs in a plain `node` environment, not jsdom, so CSS box-model behavior isn't unit-testable here)

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new (CSS-only).

**Context:** This box (`#metadataEthicsChoiceGroup` / `#metadataFundingChoiceGroup`, a Bootstrap `.btn-group.btn-group-sm.sm-choice-group` wrapping two `Yes`/`No` buttons) gets a 1px red border and 2px padding via `.sm-choice-group.sm-choice-missing` (`metadata.css:109-112`) whenever the field is unanswered — a state that was effectively unreachable before this session's `onlyFilled` fix (see prior conversation turns), so this is the first time anyone has seen it rendered. Static analysis of `app/static/css/projects/metadata.css:88-112` and the vendored `bootswatch-litera.min.css` did not turn up an obvious rule forcing `.btn-group` or `.sm-choice-group` to stretch full-width (Bootstrap's own `.btn-group` is `display: inline-flex`, which hugs content) — the cause needs to be confirmed live via devtools rather than guessed, since a wrong guess here would ship a fix that doesn't address the real cause.

- [ ] **Step 1: Live diagnosis**

Use the `run` skill to start the dev server (or run `python prism-studio.py` directly per `CLAUDE.md`'s Commands section) and open an existing project's Study Metadata > Basics (BIDS) section with Ethics Approvals unanswered (matches the screenshot that motivated this task). Open browser devtools, select the `#metadataEthicsChoiceGroup` element, and record:

1. Computed `width` of `#metadataEthicsChoiceGroup` itself.
2. Computed `display` of `#metadataEthicsChoiceGroup` (expect `inline-flex` per Bootstrap's `.btn-group`, unless something is overriding it to `flex` or `block`).
3. Computed `width` of each child `.btn` (`#metadataEthicsYes`, `#metadataEthicsNo`).
4. Walk up the ancestor chain (`.mb-2` → `.col-md-12` → `.row.g-3` → `.card-body`) and check whether any ancestor sets `display: flex` with `align-items: stretch` or similar that could be pulling `.btn-group`'s cross-axis or forcing a min-width down through inheritance.

- [ ] **Step 2a (if Step 1 finds `display` is `inline-flex` and child `.btn` widths are much larger than their text content, e.g. > 150px each):** the `min-width: 76px` rule at `metadata.css:92-95` is being overridden by a more specific Bootstrap rule setting a larger min/base width on `.btn-group-sm .btn`. Fix: increase specificity by adding `!important` and confirm 76px actually wins:

```css
.sm-choice-group .btn {
    min-width: 76px !important;
}
```

Re-inspect in devtools after this change; if the buttons now hug ~76px and the box shrinks accordingly, this was the fix — skip to Step 3.

- [ ] **Step 2b (if Step 1 finds `#metadataEthicsChoiceGroup`'s `display` is NOT `inline-flex`, e.g. it's `flex` or `block` and stretching to its parent's full width):** something is overriding Bootstrap's default. Fix: force it explicitly in `metadata.css`:

```css
.sm-choice-group {
    display: inline-flex !important;
    width: fit-content;
}
```

Re-inspect in devtools after this change; if the box now hugs its two buttons, this was the fix — skip to Step 3.

- [ ] **Step 2c (if neither 2a nor 2b resolves it):** record the actual computed values from Step 1 (widths, display, ancestor chain) and stop here rather than guessing further — this needs a second pass with those concrete numbers in hand rather than another blind attempt (per the project's systematic-debugging norm: 3 failed fix attempts means stop and re-diagnose, not keep guessing).

- [ ] **Step 3: Manual visual check**

Reload the page (hard refresh to bypass CSS cache) and confirm both `#metadataEthicsChoiceGroup` and `#metadataFundingChoiceGroup` now render as a compact red-bordered box hugging just the `Yes`/`No` buttons, matching the visual weight of other compact controls on the same form (e.g. the `smEligInclusion` tag input).

- [ ] **Step 4: Commit**

```bash
git add app/static/css/projects/metadata.css
git commit -m "fix: remove excess empty space in the Ethics/Funding Yes-No toggle box"
```

---

## Self-Review Notes

- **Spec coverage:** Item 1 (green-on-green badges) → Task 1. Item 2 (missing legend) → Task 2. Item 3 (empty space) → Task 3. All three user-reported issues have a task.
- **Placeholder scan:** Task 3 is the one task where the exact fix isn't pre-determined — this is intentional and documented (see its Context section) rather than a lazy placeholder: Step 1 is a concrete, fully-specified diagnostic procedure, and Steps 2a/2b give complete, ready-to-apply CSS for the two most likely outcomes, with 2c giving an explicit, honest stopping condition instead of a vague "handle it" placeholder.
- **Type/name consistency:** `.badge-tier-core` (Task 1) is used consistently across the CSS rule, the JS `updateBadgeColor()` edit, and all 9 template occurrences. `#smFieldTierLegend` (Task 2) matches the id already in place in the template from earlier this session.
