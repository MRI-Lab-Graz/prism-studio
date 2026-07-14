# Specifications

The in-app Specifications screen (`/specifications`) is a **navigation hub**, not a
schema reference viewer — if you want the actual schema documentation (required
fields, filename patterns, schema versions), that's a separate ReadTheDocs page this
screen links out to; nothing on this screen itself defines the schema.

## What's on it

- **PRISM Studio: 2-Tab Model** card, with two columns of shortcut buttons:
  - **Core**: [Projects](projects.md), [Validator](validator.md), Converter (disabled
    if unavailable), [Template Editor](template_editor.md), [File
    Management](file_management.md), [JSON Editor](json_editor.md).
  - **Derivatives**: [Survey Export](survey_generator.md), Recipes — both greyed out
    with a tooltip until a project is loaded.
- **The Core Concept** card explaining BIDS-compatible vs. PRISM-enhanced data.
- **Key Principles** — three generic cards: Standardized Structure, Rich Metadata,
  Validation First.
- **Detailed Schema Documentation** card — a single button, **Open PRISM Schema
  Docs**, linking out to this ReadTheDocs site's schema specs
  (`specs/survey`, `specs/biometrics`, `specs/events`, `specs/environment`).

## What's next

- The schema reference itself: [specs/survey](../specs/survey.md),
  [specs/biometrics](../specs/biometrics.md), [specs/events](../specs/events.md),
  [specs/environment](../specs/environment.md)
- [Home](home.md) for the full navigation map
