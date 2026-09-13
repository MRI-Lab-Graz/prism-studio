# Document Global Settings — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document the Global Settings section, currently referenced by `docs/studio/projects.md:39` but not documented anywhere.

**Architecture:** A single new `## Global Settings` section appended to the existing `docs/studio/projects.md` — not a new page. This plan supersedes the original Section D1 GUI-reference work in the spec, which turned out to already be done.

**Tech Stack:** Sphinx + MyST, no new page, no toctree/navigation changes needed.

**Spec:** `docs/superpowers/specs/2026-09-12-documentation-expansion-design.md`, Section D1 — see that section's 2026-09-12 correction for the full account of why this plan is one task instead of nineteen.

## Why this plan is this small

The spec originally scoped Section D1 as "every `docs/studio/*.md` page grows
a Reference section" (19 pages), based on line counts and commit dates
without opening most of the files. Opening all 19 while starting this plan
found 18 of them already at reference quality: exact field names and
accepted values, exact output file-path patterns, failure modes, CLI
equivalents. `converter.md` and `home.md` are correctly thin (a tab-router
page and the landing/pitch page, respectively — there's no field-level
content to add to either). `app_runner.md` documents a feature disabled by
a hardcoded flag and has nothing more to truthfully say until it ships.

The spec's proposed fix for the one real gap — a new `docs/studio/
settings.md` page — was also wrong: Global Settings has no route and no
template of its own. It's a collapsible card
(`app/templates/includes/projects/settings_section.html`) included by
`projects.html`, part of the Projects screen. Documenting it as a separate
page would misrepresent the UI.

If you (the person executing this plan) find, while working through this
task, that one of the "already done" 18 pages has actually drifted from the
current UI, fix that page's `## Reference`-equivalent section as part of
this task and note it in the commit message — but do not go looking for
more work here beyond the one section below; the spec's correction already
did that search.

## Global Constraints

- The RTD build must stay green: `cd docs && python3 -m sphinx -b html -W --keep-going . <outdir>` (matches `.readthedocs.yaml`'s `fail_on_warning: true`).
- Markdown cross-page links use `.md`, not `.html` (verified house
  convention; MyST's cross-reference checker fails a `-W` build on a
  Markdown-syntax `.html` link — see the signing-and-chapter-zero plan's
  Global Constraints for the full account of this failure mode).
- Git commit messages end with: `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`

---

### Task 1: Add a Global Settings section to `docs/studio/projects.md`

**Files:**
- Modify: `docs/studio/projects.md` (insert a new `## Global Settings`
  section between "Opening an existing project" and "What's next")

**Interfaces:** None — this is a self-contained documentation addition.

Verified facts this content relies on (checked in this working session,
2026-09-12, against `app/templates/includes/projects/settings_section.html`
and `app/src/web/blueprints/projects_library_blueprint.py`):

- The card holds exactly five toggles — backend monitoring, its verbose
  sub-toggle, dedicated startup terminal, connected-to-server, MRI-Lab Graz
  study-application import — and two path fields (global survey template
  library, global recipe library), each with their exact on-page help text
  (quoted in Step 1 below).
- Settings are stored in `prism_studio_settings.json` under a per-user
  directory resolved by `_get_user_app_settings_dir()`
  (`app/src/config.py:360-372`): `%APPDATA%\PRISM Studio\` on Windows,
  `~/Library/Application Support/PRISM Studio/` on macOS,
  `$XDG_CONFIG_HOME/prism-studio/` (falling back to `~/.config/prism-studio/`)
  on Linux. This is machine-wide, not per-project — confirmed by
  `load_app_settings`/`save_app_settings` taking only an `app_root`, no
  project path.
- `POST /api/settings/global-library` (`projects_library_blueprint.py:220`)
  validates that a submitted library/recipe path exists on disk before
  saving it, returning a 400 with `"Path does not exist: {path}"` if not.
- `enable_study_application_import` (the study-application-import toggle)
  gates the "Import from study application (survey.json)" button already
  documented above in this same file, under "Importing from a study
  application" (`docs/studio/projects.md`, existing content, currently
  around line 35-41).
- Project-level template override: `.prismrc.json`'s
  `templateLibraryPath`, and project templates take priority over global
  ones with the same name — both already stated in `settings_section.html`'s
  own help text, reused here for consistency rather than re-derived.

- [ ] **Step 1: Insert the section**

Find (the boundary between "Opening an existing project" and "What's next"):
```
Each project gets a small emoji icon (e.g. 🧬) assigned the first time it's created
or loaded. It's chosen at random from a fixed set and then persisted into that
project's `project.json`, so it stays the same on every later load; it's shown next
to the project's name in Recent Projects and in the header once loaded, purely as a
visual identifier with no other meaning.

## What's next
```

Replace with:
```
Each project gets a small emoji icon (e.g. 🧬) assigned the first time it's created
or loaded. It's chosen at random from a fixed set and then persisted into that
project's `project.json`, so it stays the same on every later load; it's shown next
to the project's name in Recent Projects and in the header once loaded, purely as a
visual identifier with no other meaning.

## Global Settings

A collapsible **Global Settings** card sits at the bottom of the Projects
page — click its header to expand it. These settings are machine-wide, not
per-project: they apply to every project you open in this installation of
Studio, and persist to a `prism_studio_settings.json` file in a per-user
settings directory — `%APPDATA%\PRISM Studio\` on Windows,
`~/Library/Application Support/PRISM Studio/` on macOS,
`$XDG_CONFIG_HOME/prism-studio/` (or `~/.config/prism-studio/`) on Linux —
not inside any project folder.

- **Backend monitoring (advanced)** — show backend request and command
  traces in the terminal. **Verbose backend monitoring**, its sub-toggle,
  also shows non-mutating frontend relays and generic request commands.
- **Dedicated startup terminal (advanced)** — opens a separate terminal
  window for startup/backend logs. Applied on next app launch, not
  immediately.
- **Connected to server** — on: always use the server-side file browser.
  Off: use your browser's/OS's native file pickers instead.
- **MRI-Lab Graz study application import** — off by default; turning it on
  is what makes the "Import from study application (survey.json)" button
  (see [Importing from a study application](#importing-from-a-study-application)
  above) appear on project creation. Specific to MRI-Lab Graz's intake
  survey — leave it off if you don't use that format.
- **Global Survey Template Library** / **Global Recipe Library** — the
  folder(s) Studio searches for shared templates/recipes; each must contain
  a `survey/` or `recipe/` subfolder respectively. Default: the app's
  bundled `survey_library/` and `official/recipe/` folders. A project can
  override the library path with `templateLibraryPath` in its own
  `.prismrc.json`; where names collide, project-level templates always win
  over global ones.

**Save Settings** writes the toggles and path fields — a submitted library
or recipe path that doesn't exist on disk is rejected rather than silently
accepted. **Use Default** restores the bundled library paths. **Clear**
empties the path fields, falling back to defaults.

## What's next
```

- [ ] **Step 2: Verify**

Run:
```bash
grep -n "## Global Settings" docs/studio/projects.md
cd docs && python3 -m sphinx -b html -W --keep-going . /tmp/prism_docs_build_check && echo BUILD_OK
grep -o "Global Settings" /tmp/prism_docs_build_check/studio/projects.html | head -1
```
Expected: the heading is found, `build succeeded.`, `BUILD_OK`, and the
rendered page contains the new heading text.

- [ ] **Step 3: Commit**

```bash
git add docs/studio/projects.md
git commit -m "docs: document the Global Settings section on Projects

Global Settings has no route or template of its own -- it's a collapsible
card on the Projects screen (settings_section.html, included by
projects.html). Documents its five toggles, two path fields, and the
per-user (not per-project) prism_studio_settings.json storage location,
verified against app/src/config.py and projects_library_blueprint.py.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Plan-level verification

```bash
cd docs && python3 -m sphinx -b html -W --keep-going . /tmp/prism_docs_build_check && echo BUILD_OK
grep -n "Global Settings" docs/studio/projects.md
```

Expected: `BUILD_OK`, and the new section present. Re-read the finished
`docs/studio/projects.md` end to end once — the inserted section should
read as a natural continuation of the page's existing voice, not a
bolted-on block.
