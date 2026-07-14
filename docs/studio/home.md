# Home

The landing page at `/`. It's static/marketing-style content, not a dashboard — there
is no current-project summary or dynamic quick-links list here. Home works whether or
not a project is currently loaded.

## What's on it

- A hero section with a one-line pitch and a single call to action: **Create or Open a
  Project**, linking to [Projects](projects.md).
- A dismissible "Quick Start" help panel (only shown in beginner-help mode): *"Run
  validation early, then convert and export from the same project context."*
- A "Raw study files → analysis-ready PRISM project" before/after comparison.
- A "Why Researchers Use PRISM Studio" feature list.
- A static directory-tree example showing the multimodal project layout.

The only dynamic, project-aware element on screen is in the persistent top navbar
(current project name/icon, or "No project loaded", plus a DataLad status pill) — not
inside the Home page content itself.

## Navigation

This is the real navigation structure (`app/templates/base.html`), in order:

1. **Home** — this page.
2. **Project** — "Go to Project" (only shown once a project is loaded), "Open Project
   Manager", and a "Recent Projects" list.
3. **Prepare Data** — Converter, Template Editor, Recipe Builder.
4. **Modify in PRISM** — Validator, File Management (needs a loaded project), JSON
   Editor.
5. **Export Derivatives** — Survey Export, Analysis Outputs, PRISM App Runner. The
   whole dropdown is disabled unless a project with a path is loaded and at least one
   derivative tool is available.
6. **Share & Archive** — a single link, disabled unless the loaded project has data.
7. **Docs** — Online Docs (external, this site) and Specs (the in-app
   [Specifications](specifications.md) screen).

There is no "Tools" menu and no "Results" nav item — if you've seen either mentioned
in older docs, that's stale; this is the current structure.

## Beginner help mode

A global toggle (persisted in the browser) shows or hides beginner-oriented help
panels and highlights required form inputs across Studio. It's on by default. Home's
only beginner-mode element is the Quick Start panel described above — there's no
guided tour or walkthrough.

## What's next

- [Projects](projects.md) to create or open your first project
