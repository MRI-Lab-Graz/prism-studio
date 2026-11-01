# Studio theme: one look for every page — design

Date: 2026-11-01. Status: draft for approval.

## Why

Each page grew on its own. The project page has field headings with a REQUIRED/CORE/OPTIONAL badge, an
uppercase label and an ⓘ tooltip, section headers with Required/Core/FAIR tally badges, and flat fields on a grey
card. The template editor looks close but is built differently (sentence-case labels with a red `*`, a `✓ complete`
badge, REQ/FAIR rings, every field in its own green-edged card). Converters, recipes and the survey pages drift the
same way. The result looks unprofessional: no corporate identity, and every fix has to be made once per page.

`CLAUDE.md` already says "the project page is the reference" and "same field, same widget". That is a rule without a
mechanism. This design gives it one.

## Goals

- One theme: a set of shared parts (CSS classes, a Jinja macro, a small JS builder) that every page uses. A page
  supplies content only: field names, tooltip text, counts.
- The project page is the reference. Its look becomes the theme; it is moved, not redesigned.
- Pages that build markup in JavaScript (the template editor, the survey customizer) use the same parts through the JS
  builder, so server-rendered and JS-rendered pages cannot differ.
- A test fails when a page builds its own copy of a themed part.

## Non-goals

- No new visual design, no new colours or fonts. `app/static/css/studio-theme.css` (tokens, `.studio-theme`) stays the
  base; the theme extends it.
- No big-bang rewrite of every page. Pages move one at a time; the template editor goes first.
- No change to what a page does, only to how its parts look and where their styles live.

## Anti-goals

- A second stylesheet system next to `studio-theme.css`.
- A macro and a JS builder that drift apart. If both exist, one is generated from, or tested against, the other.
- Page CSS that restyles a themed part (a page may lay parts out, not recolour them).

## The parts (first set)

| Part | Today on the project page | Shared name (proposal) |
|---|---|---|
| Field heading | `<label class="form-label fw-bold small text-muted text-uppercase">` + tier badge + `.info-tip` ⓘ | `studio-field-label` (+ macro `field_label(tier, text, tip)` and `StudioTheme.fieldLabel(...)`) |
| Tier badge | `badge bg-danger` REQUIRED, `badge-tier-core` CORE, `bg-secondary` OPTIONAL | `studio-tier` (`required`/`core`/`optional`) |
| Section header | `.sm-section-group*` card with title, one-line copy, Required/Core/FAIR tally | `studio-section` (+ macro and builder) |
| Tally badge | Required 3/3, Core 0/2, FAIR 1/3 | `studio-tally` |
| Readiness | `.sm-fair-ring`, `.sm-readiness-row` | `studio-readiness` |
| Field body | flat inputs on the grey card | `studio-field` (no per-field card) |
| Hint | ⓘ tooltip beside the heading (done in Study Metadata) | `studio-field-label` option `tip` |
| Beginner-only text | `data-help-panel data-help-default-mode="beginner"` | stays as is |

`.sm-*` classes that are really theme parts are renamed to `studio-*` when they move; page-specific ones stay `sm-*`.
Class names are a proposal; the plan fixes them.

## Where it lives

- CSS: a new section of `app/static/css/studio-theme.css`, or a `studio-theme-components.css` loaded right after it
  in `base.html` (the plan decides by file size; one stylesheet is preferred). Tokens only, no hard-coded colours.
- Macro: `app/templates/includes/ui/macros.html` (already holds `help_panel`, `path_picker`, `section_card`).
- JS builder: `app/static/js/studio-theme.js` (`StudioTheme.fieldLabel`, `.sectionHeader`, ...), loaded by `base.html`;
  it emits exactly the markup the macro emits.

## Order of work

1. Extract field heading + tier badge + section header + tally from the project page into the theme; the project
   page uses them (no visual change; screenshot compare).
2. Template editor: switch field headings and section headers to the theme (the part the user asked for first).
3. Parity test: macro output and builder output are the same markup for the same input.
4. Guard test: themed class names are defined only in the theme stylesheet; the pages listed in the test do not
   define their own copy.
5. Later, one page per branch: converters, recipes, survey customizer, survey generator.

## Constraints

- `CLAUDE.md` rules stay: the CLI executes, Studio only triggers. This is presentation only.
- Beginner-mode gating and the ⓘ tooltips keep working (tooltips are initialised per page; the builder must tell the
  page to initialise the ones it adds).
- Dark/contrast and the existing Playwright e2e tests (`tests/e2e`) must still pass.

## Left to the builder

Exact class names, whether one stylesheet or two, how the parity test compares markup, and the order of the later
pages.

## Open questions for the user

- Should the template editor's per-field cards (green left border) go, so fields are flat like the project page? (My
  default: yes, flat, because the project page is the reference.)
- The editor's REQ/FAIR rings versus the project page's readiness bar: use the bar everywhere? (My default: yes.)
