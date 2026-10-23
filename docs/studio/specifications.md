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
button per specification page (Survey, Biometrics, Biosample, Physio,
Environment, Events, `project.json`, `dataset_description.json`, filename rules), plus
the list of [validation errors and warnings](../ERROR_CODES.md) and the
[specification overview](../SPECIFICATIONS.md). Each spec page ends with a field
reference generated from the shipped schema, so it matches what the validator enforces.

## Propose changes

*Specifications → Propose changes* is where you tell the PRISM community what is missing. Find it in the **Docs**
menu (*Propose changes*), in the sidebar of this screen, or through the call-to-action on the overview page. It
works with **no project open**: the page starts with one question, *What is missing in PRISM?*, and you choose:

- **A missing choice in a list**, for example a specimen type PRISM does not list (`sweat`). Pick the kind of
  data and the list, then type the value (lowercase letters, digits and `-`). *Share…* shows the proposal.
- **A missing measurement**, for example a hormone PRISM has no term for. Say whether it is really missing,
  then give its name, what it measures, its unit and the sample type. *Share…* shows the proposal.
- **A whole new kind of data** is announced and not available yet.

Today only the biosample kind of data is offered, because the specification checks assume a list of specimen
types; the other kinds (survey, biometrics, physio, environment) need a change in the
[prism-specification](https://github.com/MRI-Lab-Graz/prism-specification) repository first.

**Nothing is sent from Studio.** *Share…* shows the proposal and opens a prefilled form on GitHub in a new tab
(or lets you download `proposal.json`); you submit the form yourself, and the maintainers may choose a different
ID or name.

**With a project open**, the page also offers *Use in my open project*, so your own project can use the new item
right away, before the community has decided:

- **Found in your data** (measurement): columns of your biosample files that neither the official registry nor
  your project knows. Click one to fill the form, then *Use in my open project* makes the metric a local term.
  It is stored in the project at `code/specification/terms/`, and the same action is
  `prism_tools.py spec local add-term`. A measurement typed by hand can be shared, but using it in a project
  needs a column found in your data.
- **Found in your data** (list): values in your biosample files outside the allowed ones. *Use in my open
  project* allows the value for this project (stored in `code/specification/patches/biosample.json`, the same
  action as `prism_tools.py spec local add-values`), so the next validation accepts it.
- **Local metrics** and **additions in this project** list what the project carries, each with its status.
  *Share…* proposes one, *Share all…* puts every local item in one proposal (up to 40 term files), and *Remove*
  deletes the local copy. An item the official registry has since adopted is marked *now-official* and can be
  removed. A schema addition is reviewed by a maintainer and gets a new minor version.

The same steps without a browser: `prism_tools.py spec catalog`, `spec propose-values` and `spec propose-metric`
(see the [CLI reference](../CLI_REFERENCE.md)).

## What's next

- [Projects](projects.md) · [Validator](validator.md) · [Template Editor](template_editor.md)
- [Recipe Builder](recipe_builder.md) · [Survey Export](survey_generator.md)
