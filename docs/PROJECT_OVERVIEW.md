# Project Overview

This page is the implementation starting point for the full Read the Docs rewrite.

It gives:

- a compact assessment of the repository's current capabilities
- a map of where major workflows live
- practical examples for the most common user paths

## What PRISM Studio currently provides

PRISM Studio combines a web interface and CLI around one backend engine for PRISM/BIDS-compatible dataset workflows.

| Area | What you can do |
|---|---|
| Project lifecycle | Create/open projects, maintain project metadata, generate README/CITATION/CHANGES, export/share datasets |
| Conversion/import | Convert survey and table-based inputs (including LimeSurvey and common tabular formats) into PRISM-compatible structures |
| Validation | Run PRISM validation and optional BIDS validation, with structured error categories and autofix support for selected cases |
| Tools | Edit templates/JSON metadata, build scoring recipes, and manage files |
| Analysis outputs | Produce derivatives, anonymized bundles, ANC export, and openMINDS export workflows |
| Automation path | Use CLI (`prism-*` entry points and `rtk`) for scripted or CI workflows |

## Architecture at a glance

- `src/` = canonical backend logic (validation, conversion, export, scoring workflows)
- `app/src/` = web adapter layer and route wiring to backend services
- `docs/` = Read the Docs source pages (Sphinx + MyST Markdown)

This split keeps behavior consistent between web and CLI usage.

## Typical end-to-end workflow

1. Create/open a project in **Projects**
2. Import data in **Converter**
3. Validate in **Validator**
4. Fix issues and re-validate
5. Score/export from **Tools** and project export actions

Use [STUDIO_OVERVIEW.md](STUDIO_OVERVIEW.md) for guided page-by-page navigation.

## Quick examples

### Example A — Start the web interface

```bash
python prism-studio.py
```

Then open `http://localhost:5001`.

### Example B — Validate a dataset from CLI

```bash
python prism-validator /path/to/dataset --bids
```

### Example C — Common RTK workflow

```bash
rtk studio
rtk validator /path/to/dataset --bids
rtk test -q
```

## Next documentation slices

The next rewrite slices should deepen each workflow page with:

- one minimal example
- one realistic example
- troubleshooting notes per workflow stage

For details, continue with:

- [PROJECTS.md](PROJECTS.md)
- [CONVERTER.md](CONVERTER.md)
- [SURVEY_IMPORT.md](SURVEY_IMPORT.md)
- [VALIDATOR.md](VALIDATOR.md)
- [TOOLS.md](TOOLS.md)
- [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md)
