# Specifications

PRISM Studio organizes a project around two tiers: **Core** — the validated PRISM/
BIDS dataset itself (Projects, Validator, Converter, Template Editor, File
Management, JSON Editor) — and **Derivatives** — outputs computed from that dataset
(Survey Export, Recipes), which only become available once a project with data is
loaded. The Specifications screen is where Studio explains that split and points you
at both the tools and the underlying schema.

![PRISM Studio Specifications screen](../_static/screenshots/prism-studio-specifications.png)

## Core vs. Derivatives

Every workflow in Studio belongs to one tier or the other. Core tools work with your
project's actual BIDS-compatible data and are always reachable. Derivatives tools —
Survey Export and Recipes — compute new outputs *from* that data, so they need a
project with real content loaded first; until then they show disabled with a
tooltip explaining why.

Underneath that split is PRISM's core relationship to BIDS: your dataset stays
BIDS-compatible at its core, with PRISM's schema-driven additions layered on top for
survey, biometrics, and other open-ended modalities — standardized
structure, rich metadata, and validation are the three principles that hold the
whole model together.

## Finding the schema itself

This screen doesn't define the schema — it links out to it. The bottom card has one
button per specification page (Survey, Biometrics, Biosample, Physio, Eyetracking,
Environment, Events, `project.json`, `dataset_description.json`, filename rules), plus
the list of [validation errors and warnings](../ERROR_CODES.md) and the
[specification overview](../SPECIFICATIONS.md). Each spec page ends with a field
reference generated from the shipped schema, so it matches what the validator enforces.

## Propose changes (local metrics)

*Specifications → Propose changes* is where a metric PRISM does not know yet becomes usable in your project, and
where you can share it. The page works on the open project, and its **New metric** tab does two things:

- **Found in your data:** columns of your biosample files that neither the official registry nor your project
  knows. *Add to this project* makes the metric a local term (optionally with a name of your choice), so the
  next validation uses it. It is stored in the project at `code/specification/terms/`, and the same action is
  `prism_tools.py spec local add-term`.
- **Local metrics in this project:** each with its status. *Share…* shows the proposal and opens a prefilled
  form on GitHub in a new tab (or lets you download `proposal.json`). **Nothing is sent from Studio**; you
  submit the form yourself, and the maintainers may choose a different ID or name. *Remove* deletes the local
  copy; a metric the official registry has since adopted is marked *now-official* and can be removed.

The tabs *New modality* and *Addition to a modality* are announced and not available yet.

## What's next

- [Projects](projects.md) · [Validator](validator.md) · [Template Editor](template_editor.md)
- [Recipe Builder](recipe_builder.md) · [Survey Export](survey_generator.md)
