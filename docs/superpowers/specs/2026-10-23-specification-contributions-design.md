# Specification contributions: local overlay and the Propose page — design

Date: 2026-10-23
Status: workflow agreed in chat ("great workflow"); awaiting written-spec review. Nothing built.
Builds on: `2026-10-22-biosample-term-registry-design.md`, `2026-10-22-prism-specification-repo-design.md`,
`2026-10-23-metric-proposal-design.md` (layer 3, built and released as prism-specification v1.1.x).

## Why

A user meets something PRISM does not know, in one of two ways:

1. **Data first:** they already have data in a modality, field value or metric PRISM does not know.
2. **Upfront:** they know it is missing and want to set it up before collecting data.

Both must end in one place, a pull request on `prism-specification`, and in the meantime the user's
data must keep validating (agreed: "allow local validation"). Same principle as for metrics: allow now,
harmonize later.

## The three layers

| Layer | What changes in prism-specification | Example | Status before this design |
|---|---|---|---|
| 1. New modality | new `schemas/stable/<name>.schema.json`, a new entry in `entities.schema.json` (folder, suffix, extensions), a spec page | `skinconductance` | workbook + `modality propose` + bot, upstream only, bot still in Studio |
| 2. Addition to a modality | an additive change to an existing schema: new enum values (e.g. `Technical.SpecimenType: sweat`), new optional fields; version bump + archive | `sweat` in biosample | no route; an unknown enum value is a schema error |
| 3. New metric | term files in `terms/<modality>/` | DHEA-S in saliva | built (`terms propose`, form, bot) |

Layers depend on each other: a metric needs its specimen value (2), a specimen value needs its modality (1).
One proposal may carry several layers (a new modality plus its first metrics).

## Goals

- A **project overlay**: local additions per project, with the layout of `prism-specification`, read by the
  validator together with the vendored official copy. The user's data validates immediately.
- **One proposal per project overlay**: everything local and not yet official, sent as one pull request.
- **Detection in the validator** of the lowest missing layer, with a notice that names the command.
- **A Studio page** with three tabs (one per layer), each with *from my data* and *upfront*, writing to the
  overlay and offering *Propose…*. It replaces the separate metric Share button (not built).
- **Commands first** (GUI/CLI parity): every page action is a `prism_tools.py spec ...` command; the page only
  calls the backend functions those commands use.
- When an item becomes official, the official one wins and the user is told the local copy can go.

## Non-goals

- Editing or removing official definitions locally (no overrides, only additions).
- Non-additive schema changes (renames, removals, stricter types): those stay maintainer work in
  prism-specification.
- Moving validator rules into `x-prism` (the planned separate step); a layer-1 modality that needs Python
  rules still needs a Studio pull request.
- A web GUI hosted by prism-specification (the issue forms serve people without Studio).

## Anti-goals

- A second proposal format per layer, or a second copy of the checks: the bot and Studio run the same scripts.
- A local item silently winning over an official one.
- Local additions that reach other projects (the overlay is per project).

## The project overlay

Location (my call): `code/specification/` in the project. `code/` is the YODA code folder, already ignored by
BIDS and kept in plain git (JSON is never annexed). Layout mirrors prism-specification:

```
code/specification/
  schemas/stable/skinconductance.schema.json   layer 1: the schema
  entities/skinconductance.json                layer 1: the entity-rule entry, same shape as
                                               entities.schema.json["modalities"][<name>]
  patches/biosample.json                       layer 2: allowed additive operations (below)
  terms/biosample/dhea-s.json, dhea-s.saliva.json   layer 3: term files, same as the registry
```

- **Layer 2 operations (allow-list, my call):** `add_enum_values` (path to an enum, values) and
  `add_optional_properties` (path to an object, property definitions). Nothing else.
- **Precedence:** official first, the overlay only adds. An overlay item whose ID, name or value the official
  copy already has is ignored, with an INFO "now official in <tag>; remove the local copy".
- **Notices:** each local item that a validation uses gives one INFO per run:
  "uses local <layer> <item> (not official yet); propose it: prism_tools.py spec propose --project <P>".
- Strict mode (`.prismrc.json` `strictMode`) turns these notices into warnings (my call).
- The overlay is part of the project (plain git, not annexed), so a shared or published dataset carries it
  and validates the same way for others; exports keep `code/specification/`.

## Validator integration (the risky part)

Today the entity rules are loaded once (`load_entity_rules()` is cached) and the validator derives module-level
constants from them at import (`_ENTITY_RULES`, `PRISM_MODALITIES`, `BIDS_MODALITIES`, `MODALITY_PATTERNS`,
used in `validator.py`, `runner.py`, `fixer.py`, `project_manager.py`; 13 direct `load_entity_rules()` calls).
A per-project overlay needs per-run rules:

- `load_entity_rules(schema_dir, version, overlay=None)` merges overlay entity entries (cache key includes the
  overlay path and its files' mtimes).
- `DatasetValidator` gets the rules of its run (official + overlay) and uses them instead of the module
  constants; the module constants stay as the official defaults for code paths without a project.
- Schemas: `load_all_schemas` adds overlay schemas (layer 1) and applies patches (layer 2) to copies.
- Terms: `load_registry` merges `code/specification/terms/<modality>/` (layer 3); collisions with official
  terms are ignored with the notice above.
- `bids_validator.prism_only_folders()` (already derived from the rules) takes the run's rules, so a local
  modality's folder draws no BIDS error.
- The builder migrates call sites one at a time behind tests; this is the part that needs the most care.

## Detection (data first)

- Unknown folder or suffix under `sub-*/[ses-*/]` that is not a BIDS datatype → INFO "`<folder>` is not a
  PRISM modality; set it up locally: prism_tools.py spec local add-modality ..." (today: silence plus BIDS
  errors).
- Value outside an enum of a known modality (e.g. `SpecimenType: sweat`) → stays an error, with the hint to add
  it locally (`spec local add-values`) and propose it.
- Unknown column → the existing layer-3 notice, now pointing at `spec local add-term` / `terms propose`.

## Commands (`prism_tools.py spec ...`)

| Command | Does |
|---|---|
| `spec local list --project P` | each overlay item, its layer, and whether it is now official |
| `spec local add-modality --project P --from <workbook.xlsx/.yml/.json> --sample F` | reuses `src/modality_contribution.py` (check, build schema, entity entry) and writes layer 1 |
| `spec local add-values --project P --modality M --field Technical.SpecimenType --value sweat` | writes a layer-2 patch |
| `spec local add-term --project P (--data F \| --sidecar F) --column C [--label L]` | reuses `build_proposal`; writes layer 3 |
| `spec local remove --project P <item>` | removes an overlay item (also used when it became official) |
| `spec propose --project P [--out F] [--open]` | one proposal with every local, not-yet-official item; checked with the vendored scripts; opens the form |

`terms propose` stays as the layer-3 shortcut.

## Proposal format v2 and the bot

- Format (my call): `{"format": "prism-proposal/2", "files": {"<repo path>": <JSON content>, ...}}`, where the
  repo paths are exactly the overlay paths mapped to prism-specification (`entities/<name>.json` is merged
  into `schemas/stable/entities.schema.json` by the bot). Allowed paths per layer are an allow-list; anything
  else is an error. The v1 metric format stays accepted.
- Size: a layer-1 schema does not fit in a URL. The form gets a file attachment field for the proposal (as the
  modality bot does today); the URL only prefills for small proposals.
- One bot workflow in prism-specification for all layers (the two-job pattern of propose-metric): it applies
  the files, runs `check_terms.py`, `check_schema_versions.py` (layer 2 gets a minor bump and an archived
  copy, done by the bot), a schema meta-check for layer 1, and opens a draft PR for trusted authors.
- The existing Studio modality bot moves there (it was step 5 of the repository design).

## The Studio page

Extends the existing Specifications page (`app/src/web/spec_docs.py`, `/specifications`) with a
**Contribute** section: tabs *New modality · Addition · New metric*; each tab has *From my data* (items the
last validation found, with *Add locally*) and *Upfront* (a form), a list of the project's overlay items with
their status, and *Propose…* (preview, *Open the prefilled form*, *Download proposal*). Every button calls a
Flask route that runs the backend function of the matching `spec` command.

## Phases (each its own plan, TDD, audit before merge)

1. Overlay for layer 3: `load_registry` merges the overlay; `spec local list/add-term/remove`; notices; the
   *New metric* tab. (Smallest; proves the overlay.)
2. Proposal format v2 and the generic bot in prism-specification (release), `spec propose`.
3. Layer 2: patches, `add-values`, the enum-error hint, the *Addition* tab.
4. Layer 1: per-run entity rules in the validator, local modality schemas, `add-modality`, detection of
   unknown folders, the *New modality* tab; move the modality bot.

## Testing

Per phase, failing tests first. Minimum: overlay precedence (official wins, notice), per-run rules do not leak
between two projects validated in one process, a local modality validates and draws no BIDS error, a patch adds
an enum value and nothing else is accepted, the v2 proposal of a mixed overlay passes the bot's checks, the
page routes return what the commands return.

## Decisions (mine, check them)

- Overlay at `code/specification/`, layout mirroring prism-specification.
- Layer-2 operations limited to adding enum values and optional properties.
- Strict mode turns local-item notices into warnings.
- Proposal format v2 = repository paths plus contents, with a per-layer path allow-list.
- The page extends the existing Specifications page instead of a new top-level page.
- Phase order 3 → 2 → 1 by layer (smallest and least risky first).
