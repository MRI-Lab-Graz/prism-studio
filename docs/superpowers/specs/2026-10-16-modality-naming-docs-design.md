# New modalities: fixed filename pattern, docs gate, no rationale

Follow-up to `2026-10-15-modality-registration-design.md`, decided 2026-10-16.

## Intent

A contributor proposing a modality should not have to think about filename
conventions. PRISM gives every new modality one fixed pattern; the maintainer
refines it per modality later (schemas will change with usage). The Read the
Docs documentation must be up to date the moment a modality arrives. "Why this
modality?" is dropped: the answer is always "PRISM had none for it".

## 0. Two kinds of proposal: new suffix in an existing modality, or a new modality

The contributor fills the same workbook; the `Name` field decides:

- **`Name` is an existing PRISM modality** (kind `prism`, e.g. `physio`,
  `biometrics`): *extension proposal*. The contributor suggests only the
  filename ending (`Suffix`, e.g. `blood`) and, if needed, `Extensions`. The
  suffix joins that modality's `suffixes` list in `entities.schema.json`; its
  extensions join the modality's `extensions` (the sidecar schema and the
  extension list belong to the modality, not to a suffix, so added extensions
  are then allowed for every suffix of it: known limit). No new schema file, no
  new folder. Entities and the sidecar schema stay the modality's own.
- **`Name` is new**: *new modality* (the existing flow): the contributor
  suggests both the modality name (its folder) and its suffix.
- **`Name` is a BIDS modality** (`anat`, `func`, `eeg`, `beh`, ...): refused with
  "BIDS owns this folder; propose the suffix to BIDS upstream".

`environment` is not extendable this way: its fixed column set, `ses-*/environment/`
folder and required `recording` entity cannot be met by a generated fixture, so a
proposal naming it is refused with advice to propose a new modality.

Collision rules stay: a suffix already used by any modality or BIDS is refused,
and the message says what it belongs to. Example columns and the sample are
still required in both kinds (they drive the example sidecar and fixture).

Output differs: an extension proposal produces the registration-entry change
(`suffixes`/`extensions` additions), the example sidecar, a fixture under the
existing modality folder and a docs snippet; no `<name>.schema.json`.

## 1. Fixed filename pattern

    sub-<label>[_ses-<label>][_task-<label>][_acq-<label>][_run-<index>]_<suffix>.<ext>

- `task` is **optional** (required only for survey/biometrics). The generated
  fixture no longer writes `task-<name>`.
- `acq` tells variants apart (`acq-fasting`), `run` counts repeats.
- Labels are free-form strings (session-ID rule applies: never normalised).

Enforcement: the registration entry carries a new optional per-modality key
`allowedEntities` (default `["task", "acq", "run"]`, order from `entityOrder`).
For a modality that has it, the validator reports an **ERROR** for any other
entity or a wrong order; without it behaviour is unchanged (existing modalities
untouched). The maintainer later narrows/widens it, adds `optionalEntityValues`
(like `physio`'s `recording`) or a new entity by editing that one entry.

`src/entity_rules.py` reads the key; `app/src/validator.py` consumes it.

## 2. Optional entity-value suggestions (contributor)

New optional workbook sheet `Entities` (YAML/JSON: `entities:`), one row per
suggested value: `Entity` (`task` or `acq`), `Value`, `Description`.
Example: `acq | fasting | Drawn after at least 8 h without food`.

- Checked like `Types`: entity must be `task`/`acq`, value `[A-Za-z0-9]+`, no
  duplicates. Never required.
- Written to the registration entry as `optionalEntityValues.<entity>` with
  `enum` + `allowOther: true` (same shape as `physio`), so docs and fix hints
  show them while other labels still pass. They are suggestions, not a closed
  list; the maintainer decides.
- Listed with descriptions in the generated docs page.

## 3. Rationale removed

Drop the `Rationale` column from the workbook/YAML/JSON, its non-empty check,
and the issue form's "Why this modality?" box. `Description` stays. Existing
inputs that still carry `rationale` are accepted and ignored (no breakage).

## 4. Docs are part of the registration

- The generator also writes `docs/specs/<name>.md` (new modality) or a snippet
  to add to the existing modality's page (extension proposal) in the style of
  `docs/specs/biometrics.md`: purpose (from `Description`), filename pattern,
  entity suggestions, example columns/types, example sidecar, link to the
  contribution guide. `REGISTRATION.md` gains the steps "copy it to
  `docs/specs/<name>.md`" and "add it to the toctree in `docs/index.rst`".
- New `verify_repo` check `modality-docs`: every registered `kind: prism`
  modality in `entities.schema.json` (survey, biometrics, environment, events,
  physio and community ones) has `docs/specs/<name>.md` and appears in
  `docs/index.rst`, and every registered suffix (`_<suffix>`) appears in that
  modality's page. CI fails otherwise, so docs cannot fall behind. Modalities
  that have no page today get one in this change, or are listed in an explicit
  exemption set with a comment (decided during planning from what is missing).

## 5. Small items

- Bot PR body says `Closes #N` (issue closes on merge).
- Docs (`MODALITY_PROPOSALS.md`, `MODALITY_WORKFLOW.md`), CLI reference,
  `examples/modality_proposal/*`, the shipped template workbook and the
  bot's issue parser/tests are updated for 1-4.

## Out of scope

- Per-suffix extensions or per-suffix sidecar schemas inside one modality.

- Issue-list/form look-and-feel (labels, titles, comment layout): separate,
  after this lands.
- A `modality register` command: registration stays manual until a few real
  proposals have gone through.
- Per-modality refinement such as `sample-`: a later maintainer edit.

## Testing

TDD for each piece: extension vs new-modality routing (existing name, new
name, BIDS name, suffix collision), entity-rule loader (`allowedEntities`), validator
(accepts the fixed pattern incl. no `task`; errors on a foreign entity/order),
`Entities` reader and checks, generator output (registration entry, docs page,
fixture filename without `task`), `modality-docs` check (fails on a missing
page/toctree entry), rationale no longer required, form/parser, PR body.
The end-to-end registration test keeps proving that the fixture validates.
