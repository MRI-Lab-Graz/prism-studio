# Biosample term registry (metric harmonization) — design

Date: 2026-10-22
Status: design agreed in chat; awaiting written-spec review. Nothing built.
Builds on: `2026-10-15-biosample-modality-design.md` (phase 1 shipped).

## Why

Biosample columns are free names today (`cort`, `corts`, `cortisol`). Two labs
measuring the same thing cannot be pooled, and the schema cannot say what a
column *is*. We want the schema to be **wide** (nobody has to wait for PRISM
to know their metric) and **narrow** (once a metric is official, everybody is
steered to one definition) at the same time. The model is Neurobagel-style
harmonization: a local column name is mapped to a controlled term; the term,
not the name, carries the meaning.

## Goals

- A registry of **terms** that ships with each release, offline.
- Any metric may be used without being in the registry. The validator tells
  the user, lists similar official terms (it may just be named differently)
  and offers to share it with the PRISM community.
- Official terms define a recommended unit; other units are allowed if
  declared.
- User files are never rewritten when a term becomes official or is renamed.
- Works from the command line first; the GUI only calls it (repo rule:
  one implementation, GUI/CLI parity).

## Non-goals

- No full ontology, no deep hierarchy (exactly two levels, see below), no
  live lookup against an external service.
- No automatic registration: a person reviews every proposal.
- No unit conversion in the validator. Conversion factors may be stored in
  the registry for later use (recipes); a missing factor means "unknown".

## Anti-goals

- Blocking a user because their metric is unknown.
- Telling a user their unit is "wrong" when it is declared and plausible.
- Silently guessing a mapping (name similarity only *suggests*).

## Terms

Two levels, nested:

- **Parent term = analyte**, e.g. `cortisol`. Holds: stable ID, current label,
  aliases (`cort`, `corts`), description, optional external anchor
  (e.g. LOINC component, ChEBI). No units, no ranges.
- **Child term = analyte in one specimen**, e.g. cortisol in saliva. Holds:
  parent ID, `SpecimenType` (same enum as `Technical.SpecimenType`),
  recommended unit, known alternative units, plausible range
  (`MinValue`/`WarnMaxValue`), optional LOINC code, optional conversion
  factors between listed units.
- **Identity is a stable ID**; the label is replaceable. A rename or merge
  never breaks a file. Deprecated terms carry `ReplacedBy`.
- **Status** per term (parent and child separately): `official` or
  `deprecated` in the shipped registry; `local` (only in a user's sidecar) and
  `proposed` (sent, not yet merged) exist on the user side. A user may propose
  a new child under an existing parent without touching the parent.
- Units are written in UCUM notation (`nmol/L`, `ug/dL`).

Registry layout (my call): one small JSON file per term under
`official/library/terms/<modality>/` (biosample first), shipped with the
release, loaded the way the existing library templates are. The loader and the
notice logic must not mention "biosample" by name (see Generalization).

## How a sidecar column refers to a term

New optional column key `Term` (ID or label). Existing `AliasOf`/`Aliases`
keep working unchanged for files that have them.

Resolution (my call on the exact order):

1. `Term` names a **child** → its `SpecimenType` must equal the sidecar's
   `Technical.SpecimenType`; a mismatch is an **error** (saliva units on a
   serum file).
2. `Term` names a **parent** → resolved to the child matching
   `Technical.SpecimenType`. If the parent exists but has no child for that
   specimen: notice "known analyte, new specimen", share offer is for the
   child only.
3. No `Term`, but the column name or an alias matches a term → **info** with
   the suggestion "looks like `cortisol`; add `Term`". Never applied silently.
4. No match → **unknown metric** (below).

The panel label in the file name (`biosample-saliva`, `biosample-cortisolsaliva`,
anything alphanumeric) stays free; harmonization lives in the term, not the
file name. The `Technical` block still applies per sidecar, so metrics from a
different lab or kit need a separate sidecar/label.

## Validator behaviour

| Situation | Severity |
|---|---|
| Unknown metric, fully defined in the sidecar | **info/notice**: not official, similar official terms listed, share offer, name may change on adoption |
| Column with no `Units` and no term to inherit from | **error** (value cannot be interpreted; unchanged rule) |
| Declared unit differs from the term's recommended unit | **info** only |
| Declared unit not declared at all in sidecar or term | **error** |
| Child term's specimen != `Technical.SpecimenType` | **error** |
| Term is `deprecated` | **warning**, with `ReplacedBy` |
| Term not found in registry | notice as for unknown metric (the sidecar may carry a `local` definition) |

Term-supplied constraints (range, `LowerLimitOfDetection` etc.) are inherited
unless the sidecar column sets its own; the sidecar wins.

## Sharing flow (user 0)

1. Validation shows the notice: "`cort` is not an official metric. Do you want
   to share it with the PRISM community to make it official?" with the list of
   similar official terms. The notice states that the maintainers may choose a
   different name (`cort` may become `cortisol`) and that the user's files keep
   working through an alias.
2. On yes, PRISM builds a proposal (parent/child, label, unit, range, aliases
   including the user's own name) and reuses the existing modality-proposal
   route: workbook/YAML → bot checks → draft PR → maintainer merges.
3. After the next release the user's name is an alias of the official term.
   No file is rewritten; tools see the official term.

## Command line and GUI

- CLI (`prism_tools.py`, implemented in `src/`): list terms, show a term,
  suggest similar terms for a column name, build a proposal from a sidecar
  column. The validator exposes the notices through the existing report.
- GUI: the Validator page shows the same notices and the share button; it calls
  the CLI function. Template Editor/converter integration follows their phases.

## Testing

TDD per repo rules. Minimum: term loading and `deprecated`/`ReplacedBy`;
resolution rules 1-4; every row of the severity table; inheritance and
sidecar override; alias round trip; shipped registry validates against its own
schema; the validator image must not need pandas (term loading is JSON only).
Dual-tree check (`find src -name ...` + import `__file__`) before editing any
module that exists under both `src/` and `app/src/`.

## Open items left to the builder (my calls, mark if you disagree)

- Exact term ID format (e.g. `prism-bs:cortisol` / `prism-bs:cortisol.saliva`).
- Term JSON schema and where it is validated (reuse `library_validator`).
- Seed set for the first release: a handful (cortisol, alpha-amylase, CRP,
  IL-6, TNF-alpha) so the machinery is exercised; not an attempt at coverage.
- Fuzzy matching method for "similar terms" (alias/label exact and
  case-insensitive match first; edit distance only if cheap).
- Whether `Term` is also accepted in biometrics (not decided; out of scope here).

## Generalization to other modalities

The idea is not biosample-specific, so the generic parts are built generic;
only biosample is built now.

- **Generic:** registry and loader, stable term ID, status lifecycle, aliases,
  "unknown metric passes with a notice and a share offer", any declared unit
  is accepted, the proposal route.
- **Per modality:** whether terms have a child level and what it is keyed by.
  Biosample: specimen. Biometrics might use a measurement context (e.g. hand
  for grip strength). A modality without such an axis has parent terms only;
  no second level is forced.
- **Candidates, strongest first:** biometrics (same tabular machinery,
  `TABULAR_MODALITIES`; build second, once biosample works end to end, as the
  test that the generic parts are generic); `participants.tsv` (age/sex/
  handedness, units and levels; its own small project, because the definitions
  already live in `participants.json`); physio and environment (sensor/channel
  types and units; later, layout differs).
- **Not a candidate:** survey. The instrument library already harmonizes at
  instrument level; item-level terms would duplicate it.

## Phases

1. Registry format + loader + validator rules + CLI list/show/suggest.
2. Proposal builder (CLI) and the GUI notice/share button.
3. Converter and Template Editor use terms (depends on biosample phases 2-3).
4. Recipes may convert units via stored factors (deferred until a use case).
