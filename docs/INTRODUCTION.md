# Introduction

Psychological and neuroscience studies routinely combine two kinds of data:
imaging and physiological recordings that [BIDS](https://bids.neuroimaging.io/)
already standardizes well, and questionnaires, sociodemographic data,
biometrics, and scoring rules that BIDS deliberately leaves open. That
second category usually ends up in spreadsheets and lab-specific folder
conventions — workable until someone else has to reuse, validate, or
reproduce a derived score from it.

PRISM Studio's bet is that closing that gap needs more than a schema. It
needs a schema that does not need to know your instruments in advance, a
validator that is trustworthy enough to build a pipeline on, tooling for
the unglamorous conversion work in between, and an interface a
non-programmer will actually finish using. This page states that bet
directly, in four parts.

## Open-ended by construction

Most schemas for survey data work by enumerating what a valid item looks
like: a fixed list of instrument IDs, a fixed list of response scales.
PRISM's survey schema does not do this. It declares a *shape* a survey item
must satisfy — required keys, allowed types — via JSON Schema's
`additionalProperties`, rather than a closed list of the instruments
PRISM's authors have seen. A questionnaire PRISM has never shipped, in a
language it does not ship, validates fully on day one, with no schema
change and no PRISM update.

The mechanisms that make this practical, not just possible:

- **`ApplicableVersions` / `VariantScales` / `Aliases`** let one instrument
  definition cover multiple study versions and item variants without
  duplicating the whole instrument per version.
- **Two validation profiles** (`x-prism.officialOnlyRequired` and
  `x-prism.projectOnlyRequired`) mean the same schema validates a shared
  library template and a specific project's in-progress data with
  different, appropriate strictness — a template need not yet carry the
  fields only a live project has, and a live project need not carry the
  fields only the shared library standard requires.
- **Three schema versions coexist** (`stable`, `v0.1`, `v0.2`) so a
  project started under an older schema keeps validating without a forced
  migration.
- **Validator plugins**: a project can add its own checks — a Python
  module returning a list of issues — via `.prismrc.json` or a
  `validators/` folder, for lab-specific rules PRISM will never ship.

## A validator, not a linter

Validation is not a single pass of pattern-matching. PRISM runs two
independent layers: its own schema and cross-file checks, and the real
upstream [BIDS Validator](https://github.com/bids-standard/bids-validator)
— invoked, never reimplemented, so PRISM datasets are held to the same
standard every other BIDS tool checks against.

Around that core: five machine-readable report formats (JSON, SARIF,
JUnit, Markdown, CSV) so validation slots into CI the way any other check
does; a `--fix`/`--dry-run` pair that previews an auto-fix before writing
it, rather than mutating a dataset silently; template validation for the
library layer, independent of any specific dataset; and version pinning so
a validator run states which schema version it checked against.

## Fifteen helper commands for the unglamorous work

Between a raw export and a valid dataset is a long tail of mundane,
error-prone wrangling that no standard addresses and that researchers
otherwise solve with one-off scripts: detecting which spreadsheet column
holds the participant ID, reshaping a wide questionnaire export into long
format, stripping subject data from a validated project to seed the next
study, recomputing a derived score with its provenance attached instead of
trusting a methods-section description.

PRISM ships this as fifteen command groups under `prism_tools`, each
available both in Studio and as a scriptable CLI subcommand: `convert`,
`wide-to-long`, `participants`, `environment`, `survey`, `biometrics`,
`physio`, `recipes`, `dataset`, `anonymize`, `template-export`, `library`,
`file-management`, `json-editor`, `demo`. Individually these are small.
Collectively they are the difference between a data standard that is
theoretically satisfiable and one a lab actually satisfies on a deadline.
See [CLI Reference](CLI_REFERENCE.md) for the full command set.

## User experience as a design goal

BIDS defines a structure; it does not make that structure easy to reach.
The typical entry point is not a clean slate but a LimeSurvey archive, an
Excel codebook of uncertain provenance, and a folder of scanner output,
held by a researcher whose expertise is psychology rather than data
engineering. PRISM Studio treats the resulting last-mile problem as part
of the job, through three conventions that run across its screens:

- **Guidance where the domain knowledge is needed.** Converters ask
  domain questions — which column identifies the participant, which
  session a file belongs to — instead of requiring files pre-arranged into
  a BIDS layout the user must first learn. Correct BIDS names are derived
  from entity rules, not typed by hand.
- **Preview before commit.** Conversions, ID normalization, entity
  renames, validator fixes, and exports all show a preview of what will
  change before it changes. Operations that could collide or lose data
  report the conflict instead of resolving it silently.
- **Parity between the interface and the command line.** Every Studio
  action is reachable from the CLI, so interactive exploration and a
  scripted, reproducible pipeline are the same operation, not two
  implementations that can drift apart.

## What's next

- [What is PRISM?](WHAT_IS_PRISM.md) — the data and metadata model, and how
  it relates to BIDS
- [Project Overview](PROJECT_OVERVIEW.md) — the repo and feature map
- [Getting Started](TUTORIAL_BEGINNER.md) — the hands-on tutorial
- [Studio Guide](studio/index.md) — every screen, in depth
