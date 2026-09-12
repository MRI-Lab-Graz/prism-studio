# Documentation Expansion — Design

**Date:** 2026-09-12
**Status:** Approved, pending implementation plan

## Problem

The ReadTheDocs site is in good shape and builds clean under RTD's exact
config (`sphinx-build -W`, verified 2026-09-12): 70 pages, no broken
toctrees, no orphan warnings, actively maintained through 2026-09-07. This
is not a rewrite. Three gaps and three factual errors need closing.

**Factual errors (blocking — the docs currently say things that are false):**

1. The privacy tagline "without your data ever leaving your own computer"
   appears in `docs/index.rst:13`, `docs/studio/home.md:4`, and
   `README.md:25`. It is false when the optional environment-enrichment
   feature runs, which queries Open-Meteo
   (`app/src/web/blueprints/conversion_environment_handlers.py:114-116`).
   The paper already caught and corrected this overclaim
   (`paper/main.tex:411-417`); the docs did not follow.
2. `survey export-pavlovia` (added 2026-08, commit `a2643448`) is absent
   from `docs/CLI_REFERENCE.md`. It is the only one of 61 argparse
   subparsers (53 distinct command names) that is undocumented.
3. `docs/index.rst` advertises "Sync to a remote DataLad server … with one
   click". The feature exists
   (`app/src/web/blueprints/projects_datalad_server_blueprint.py`) but
   `docs/DATALAD.md` (79 lines) never mentions RIA stores, siblings, or
   remote push.

**Gaps:**

- **No function-level reference.** `sphinx.ext.autodoc` is enabled in
  `docs/conf.py:17` but zero autodoc directives exist anywhere in the tree.
  The `docs/studio/*.md` pages average ~60 lines (`converter.md` is 21) —
  orientation blurbs, not references.
- **No introduction that makes the project's argument.** `index.rst` and
  `WHAT_IS_PRISM.md` sell "BIDS plus surveys". The four points the paper
  deliberately stresses (`paper/main.tex`, commit `b4b1e3db`) —
  open-endedness, the two-layer validator, the helper command groups, UX as
  a contribution — appear nowhere.
- **No entry ramp.** `docs/INSTALLATION.md` contains zero words about
  Gatekeeper, notarization, SmartScreen, or quarantine — one buried line,
  "if the OS blocks the app, right-click → Open". The binaries are
  unsigned and will stay unsigned for budget reasons. Tutorial Chapter 1
  assumes the app is already open.

## Non-goals

- **Python API autodoc.** Explicitly ruled out. Docstring coverage is
  unaudited and the `src/` vs `app/src/` namespace-package mirror (see
  `CLAUDE.md`) makes autodoc target paths ambiguous. Not worth it for an
  audience of researchers.
- Restructuring the existing tutorial chapters or the Studio Guide
  navigation. Both work.
- Paying for code signing. Out of scope by constraint, not by preference.

## Design

### A. Corrections

Small and blocking — everything downstream depends on the docs being honest.

- Replace the tagline in all three locations with wording matching
  `paper/main.tex:411-417`: data stays on the researcher's machine and is
  neither uploaded nor sent to a remote service, with the single exception
  of the optional, off-by-default environment enrichment, which sends
  coordinates and dates to a public weather service and no participant-level
  data.
- Add `survey export-pavlovia` to `docs/CLI_REFERENCE.md` under "Survey
  conversion, templates, and i18n".

Superseded by D2 if the CLI reference generator lands first; do it by hand
now rather than blocking on D2.

### B. Introduction

New `docs/INTRODUCTION.md`, first page under the Concepts toctree, above
`WHAT_IS_PRISM.md` (which stays as the model explainer). Each of the paper's
four points stated as a user-facing consequence, not a claim:

1. **Open-ended by construction.** The survey schema defines a shape
   contract via `additionalProperties`, not an enumeration of instruments.
   Consequence: an instrument PRISM has never seen, in a language it does
   not ship, validates fully on day one. Supporting mechanisms to name:
   `ApplicableVersions`/`VariantScales`/`Aliases`, the `x-prism`
   `officialOnlyRequired`/`projectOnlyRequired` validation profiles, three
   coexisting schema versions, user-supplied validator plugins.
2. **A validator, not a linter.** Two independent layers — PRISM's own
   checks plus the upstream BIDS Validator, invoked rather than
   reimplemented. Five report formats for CI, preview-before-write repair,
   template validation, version pinning.
3. **Helpers for the unglamorous work.** The `prism_tools` command groups,
   framed as the long tail between a raw export and a valid dataset.
   **Verify the count before writing**: `paper/main.tex:374` says "fourteen"
   and then lists fifteen (`convert`, `wide-to-long`, `participants`,
   `environment`, `survey`, `biometrics`, `physio`, `recipes`, `dataset`,
   `anonymize`, `template-export`, `library`, `file-management`,
   `json-editor`, `demo`). Use the count verified against
   `app/src/cli/parser.py`, and report the discrepancy so the paper can be
   fixed too.
4. **UX as a deliberate contribution.** Guided converters that ask domain
   questions instead of demanding a pre-arranged layout; preview before
   commit on every destructive operation; full CLI/GUI parity.

The `index.rst` hero gains a short honest privacy line (from A).

This page is the docs' argument for the project and should match the paper's
voice. Draft it first and get review before the rest of the section work.

### C. Installation and code signing

New `docs/INSTALLATION_SECURITY.md`, linked prominently from
`docs/INSTALLATION.md`. Transparent line, not apologetic:

- What "unsigned" means and what it does not. It is not a malware
  detection; it means the project has not purchased an Apple Developer
  membership or a Windows signing certificate.
- Exactly what each OS shows, with screenshots: macOS "Apple could not
  verify…"; Windows SmartScreen "Windows protected your PC" → More info →
  Run anyway. Cover the quarantine attribute and the existing
  `Prism Studio Installer.app` / `Open Prism Studio.command` paths already
  shipped in the ZIP.
- **Verifying the download.** SHA-256 checksums per release asset, plus how
  to check them on each OS. This is what makes the transparency
  load-bearing rather than an apology: a user who is told to bypass a
  security warning needs an independent way to confirm what they got.
  **Dependency:** the release workflow does not currently publish
  checksums. That is a change outside `docs/` and is tracked as a separate
  task. The page ships regardless, with the verification section present and
  explicitly marked as not yet available — a user who cannot verify should
  be told so plainly rather than shown nothing.
- "Rather not bypass a security warning?" → the source install, rewritten
  for someone who has never opened a terminal. This is the honest
  alternative, offered without pressure in either direction.

`docs/INSTALLATION.md` keeps its current shape and links out; it does not
absorb this content.

### D. Function-level reference

Two tracks, both additive. No Python autodoc.

**D1 — GUI reference.** Each of the 19 `docs/studio/*.md` pages grows a
`## Reference` section: every control, its accepted values, the file it
writes and where, and its failure modes. Content read out of
`app/templates/*.html` and the corresponding blueprint handlers so it is
accurate rather than guessed. The thin pages gain the most
(`converter.md` at 21 lines, `app_runner.md` at 32,
`specifications.md` at 38).

Also new: `docs/studio/settings.md` for Global Settings, currently
referenced by `docs/studio/projects.md:39` but documented nowhere. Add to
the `studio/index.md` toctree and card grid.

**D2 — CLI reference, generated.** `app/src/cli/parser.py` already holds
every subcommand, flag, default, and help string across all 61
subparsers (53 distinct names, some reused across command groups).
Hand-maintaining that is how it goes stale. New
`scripts/gen_cli_reference.py` walks the argparse tree and emits per-command
pages under `docs/cli/`; CI fails if the committed output differs from a
fresh run, the same way other generated artifacts are guarded.
`CLI_REFERENCE.md` and `CLI_WORKFLOWS.md` stay hand-written as the narrative
layer above the generated pages, and link into them.

Note for implementation: `app/src/cli/parser.py` is under `app/src/`. Per
`CLAUDE.md`, confirm which physical file answers the import path before
assuming an edit is live — though this task only reads the parser, so the
risk is limited to reading a stale mirror.

### E. Tutorial

All four requested pieces, sequenced by cost.

**E1 — Chapter 0: Install and First Launch.** Download → the OS blocks it →
get past it → first launch → what am I looking at. Shares content with C;
Chapter 0 is the narrative walkthrough, `INSTALLATION_SECURITY.md` is the
reference. Chapter 1 currently assumes an open app; Chapter 0 removes that
assumption.

**E2 — "Where do I start?" router.** A short decision block at the top of
`docs/TUTORIAL_BEGINNER.md`: "I have a LimeSurvey export" / "I have an Excel
sheet" / "I already have a BIDS dataset" / "I need to build a
questionnaire" → the chapter to read. Reuses the existing
`prism-chapter-grid` card CSS.

**E3 — Screenshot and checkpoint density.** A screenshot per step rather
than per screen, plus explicit "you should now see X" checkpoints so a user
can tell whether they are on track. Implemented by adding entries to the
`SHOTS` tables in the existing
`scripts/capture_studio_docs_screenshots.py` (Playwright, already working,
33 screenshots) — not by manual capture.

**E4 — New tutorial tracks.** Biometrics, environment, eyetracking/physio,
and DataLad + remote sync. The DataLad track also closes correction A3's
underlying gap. Each track is roughly the size of the existing survey
tutorial series (7 chapters, ~1,000 lines), so each is a separate follow-on
project rather than part of this one.

## Sequencing

A → B → C + E1 (shared content, done together) → D → E2 → E3 → E4.

A through C is the small, high-value core. D is the bulk of the mechanical
work. E4 is open-ended and taken one track at a time.

## Testing and verification

- `cd docs && python3 -m sphinx -b html -W --keep-going . <tmp>` must stay
  clean after every step. It passes today; a regression here breaks the RTD
  build, which runs `fail_on_warning: true`.
- `scripts/gen_cli_reference.py` gets a test asserting the generated output
  matches the committed `docs/cli/` tree, wired into CI.
- Every factual claim added to `INTRODUCTION.md` is verified against the
  code before it is written, not against the paper. The paper's helper-group
  count is already known to be wrong; treat it as a source of framing, not
  of facts.
- Screenshots regenerate via the existing Playwright script against
  `examples/wellbeing_multi_demo`, so they can be re-verified rather than
  trusted.

## Open items

- Release workflow must publish SHA-256 checksums before C's verification
  section is truthful. Outside `docs/`; separate task.
- `paper/main.tex:374` helper-group count is off by one. Report; do not fix
  as part of this work.
- `docs/conf.py:11` pins `release = "1.18.0"` by hand with nothing keeping
  it in sync with `CHANGELOG.md`. Noted, not addressed here.
