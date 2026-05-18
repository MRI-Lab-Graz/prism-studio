# Frontend Structural Assessment - Home Page (Phase 3.6)

Date: 2026-05-15

Synchronization status (2026-05-17):

- Cross-checked against latest converter refactor baseline in [docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md](docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md).
- No page-specific finding severity changes in this synchronization pass.
- Existing remediation slices and validation scope below remain authoritative.


Scope:

- Home page shell, shared section-card includes, and beginner quick-start help behavior
- Render-path ownership for root route and interaction with global no-project guard
- Template composition resilience when optional tool blueprints are absent
- Navigation intent clarity between Home, Projects, and core workflows

Key files:

- [app/templates/home.html](app/templates/home.html)
- [app/prism-studio.py](app/prism-studio.py)
- [app/templates/includes/home/hero.html](app/templates/includes/home/hero.html)
- [app/templates/includes/home/highlights.html](app/templates/includes/home/highlights.html)
- [app/templates/includes/home/before_after.html](app/templates/includes/home/before_after.html)
- [app/templates/includes/home/structure.html](app/templates/includes/home/structure.html)

## Backend Command Ownership Map

Current ownership status: compliant for render-only informational page.

Primary action -> backend command/endpoint mapping:

- Open Home page -> `/`
- Navigate to Projects from Home flow -> `/projects`
- Navigate to Validator from Home flow -> `/validate`

Assessment note:

- Home page has no business-logic execution endpoints.
- Frontend behavior is template composition plus shared help-panel mode wiring.

## Current Stability Findings

### High - Home route accessibility depends on global no-project guard policy outside page module

Affected:

- [app/prism-studio.py](app/prism-studio.py)
- [app/templates/home.html](app/templates/home.html)

Risk:

- Root route rendering is influenced by global project guard behavior; policy drift can change whether users land on Home or get redirected to Projects.
- This can affect onboarding flow predictability and documentation assumptions.

Current guardrails:

- Route handler itself is minimal and deterministic (`render_template('home.html')`).
- Template render tests validate shared-section content appears when route is reachable.

### High - Home page behavior is distributed across multiple include templates

Affected:

- [app/templates/home.html](app/templates/home.html)
- [app/templates/includes/home/hero.html](app/templates/includes/home/hero.html)
- [app/templates/includes/home/highlights.html](app/templates/includes/home/highlights.html)
- [app/templates/includes/home/before_after.html](app/templates/includes/home/before_after.html)
- [app/templates/includes/home/structure.html](app/templates/includes/home/structure.html)

Risk:

- Structural/content regressions can occur if include composition changes without corresponding render-coverage updates.

Current guardrails:

- Shared section-card rendering tests assert major content blocks remain present.
- Beginner help-panel default mode wiring is covered by dedicated tests.

## Runtime Smoke Checklist (Phase 3.6)

1. Open Home route and verify shared page header and quick-start help panel render correctly.
2. Toggle beginner-help mode and verify Home quick-start panel follows expected default behavior.
3. Verify Home renders correctly when optional tool blueprints are not registered.
4. Verify navigation path from Home to Projects/Validator remains intact in no-project and active-project states.
5. Confirm home section include blocks render in expected order and maintain key content anchors.

## Remediation Slices

### Slice A - Stabilize Home route policy contract with project-guard behavior

Acceptance:

- Desired root-route behavior (render vs redirect) is explicitly documented and covered by focused tests.
- Guard changes cannot silently alter onboarding entry behavior.

Validation:

- Keep route/template render coverage for Home in template rendering suites.

### Slice B - Preserve include composition integrity

Acceptance:

- Major home include sections remain present and ordered for intended narrative flow.
- Beginner quick-start help linkage remains intact.

Validation:

- Maintain assertions in [tests/test_shared_section_card_template_rendering.py](tests/test_shared_section_card_template_rendering.py).
- Maintain assertions in [tests/test_beginner_help_panel_mode_defaults.py](tests/test_beginner_help_panel_mode_defaults.py).

## Exit Criteria for Home Page Assessment

- Critical findings: none open.
- High findings: either resolved or tracked with explicit remediation slices and tests.
- Runtime smoke checklist completed and documented.
