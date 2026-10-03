# Save gate: a DataLad snapshot is only allowed on a valid dataset

Date: 2026-10-02 · Status: draft for review · Builds on
`2026-10-02-share-publish-design.md` (branch `feat/share-publish`, reuses
`validate_for_publish`).

## Context

The publish gate stops invalid datasets reaching the server, but invalid
snapshots can still be created locally (and, on a share, by anyone using
`datalad save`). Decision: **a save (commit) is allowed only if the dataset
validates**, independent of any sibling. The gate is **always on**, strictly
(zero validator errors), with no per-dataset setting.

Verified by spike (DataLad 1.6.3):
- `datalad save` runs git hooks: a failing `pre-commit` blocks the commit.
- Hooks are per repository: a nested dataset created later has no hook, and
  its save succeeds. Every dataset (super and nested) needs the hook.
- A blocked save leaves changes staged/dirty, and the next `datalad run`
  refuses ("clean dataset required").
- The validator validates each subject, then derives cross-subject checks
  (consistency, procedure) from shared statistics, so "skip unchanged
  subjects" needs per-subject issues **and** statistics cached.

## Goals

1. Any commit in a PRISM dataset (superdataset or nested `sub-*`), made through
   PRISM or manual `datalad save` / `git commit`, is refused when it would
   leave the dataset with validator errors.
2. Nested datasets are not re-validated needlessly: only datasets whose HEAD or
   working tree changed since they were last validated are re-validated.

## Non-goals

- Server-side enforcement; defeating `--no-verify` (the deliberate escape
  hatch, documented).
- A ratchet / "no new errors" mode (decided: strict).
- A per-dataset off switch (decided: always on). Consequence in Risks.

## Design

### 1. Rule

`check_save(root)` → `SaveCheck(allowed: bool, errors: list[str], reason: str)`.
Strict: any validator **error** refuses; warnings never block. BIDS validator
is off (same as publish). Exemptions, exhaustive:
1. The initial commit of a new dataset (a repo with no commits, or only
   DataLad's initial `[DATALAD] new dataset` commit and no PRISM project yet).
2. PRISM's project-creation scaffold save (called with an explicit internal
   flag from the create-project flow only).

Exemption 1 exists because an empty scaffold does not validate: the validator
reports `No subjects found in dataset (no sub-* folders)` as an ERROR (kept on
purpose: it catches a wrong folder). From the first real commit on, every save
must leave the dataset valid; datasets that predate this gate are expected to
be valid, and `save-gate --status/--check` shows their errors before a save is
attempted.

Everything else is gated, including PRISM's emergency save for partial
mutations (recommendation: gated; revisit in review, see Open items).

### 2. Backend: `src/save_gate.py` (one implementation)

- `check_save(root, *, exempt=False)`: applies the rule using
  `validate_for_publish` (Phase 1) or the incremental validator (Phase 2).
- `run_datalad_save` and `run_datalad_run` (`src/datalad_execution.py`) call it
  before touching git. Refusal returns `success: False`, `reason:
  "validation_errors"`, the errors, and the message "Not saved: N validation
  error(s). Fix them, then save." Changes stay in the working tree.
- **Fixing after a refusal must work through PRISM.** A refused save leaves the
  tree dirty, and plain `datalad run` refuses a dirty dataset, so PRISM's own
  edit operations (rename, convert, fix) would be unusable exactly when the user
  is trying to make the dataset valid. Requirement: PRISM operations run on a
  tree that is dirty only because of a refused save (e.g. `datalad run
  --explicit` with declared outputs, or edit-then-single-save), and the save at
  the end is gated as usual. Mechanism to be settled when planning Phase 1.
- Callers of `datalad run` check cleanliness first and report "dataset has
  unsaved changes from a refused save" instead of DataLad's generic message.

### 3. Enforcement for manual saves: git `pre-commit` hook

- Installed in **every** dataset root (superdataset and all nested). Same
  hook script contract as the publish hook: fail closed when `prism_tools` is
  not found (`PRISM_TOOLS`), refuse to overwrite a foreign hook, no baked-in
  paths (`git rev-parse --show-toplevel`), runs `prism_tools save-gate
  --check --project <toplevel>`.
- Installed when PRISM creates a dataset or subdataset, and by
  `prism_tools save-gate --install-hooks` for existing projects (walks all
  dataset roots).
- Nested hook validates **only that subject** (see 4); superdataset hook runs
  the incremental project check.

### 4. Nested data: validate only what changed (Phase 2)

- Refactor `_validate_subject` accumulation so a subject can be validated
  alone with a fresh `DatasetStats` that is then merged into the project
  statistics (`DatasetStats.merge`). This is required by Phase 1's nested hook
  too (a nested commit must not trigger a full-project validation, which would
  be quadratic over a 150-subject conversion).
- Cache `<git-dir>/prism/validated.json` of the superdataset: per nested
  dataset, `{head, issues, stats}` of its last passing/failed validation,
  keyed by dataset HEAD. A superdataset save validates root-level files,
  re-validates subjects whose HEAD differs from the record or whose working
  tree is dirty (`git status`), reuses cached issues/stats for the rest, then
  runs the cross-subject checks on the merged statistics.
- The cache is an optimization, never an authority: a missing, unreadable or
  mismatching entry means re-validate. Validator or schema version change
  invalidates the whole cache (store the schema version in the file).
- Phase 1 (gate + hooks + full validation, nested hook subject-only) and
  Phase 2 (cache) ship as separate plans from this one spec.

### 5. CLI and GUI

- `prism_tools save-gate --check --project P` (hook entry; exit 0 allowed,
  1 refused for validation errors, 2 other errors), `--install-hooks`,
  `--status` (hook present per dataset, last validated HEAD per dataset),
  `--json`.
- Studio surfaces the refusal where PRISM saves (the existing operation result
  messages); no new page. Per CLAUDE.md there is no separate GUI logic.

### 6. Audit

Reuse the publish audit file `<git-dir>/prism/publish.jsonl` with a `kind`
field (`save` / `publish`) and the same identity resolution; refused saves are
logged. Log write failures stay non-fatal.

## Testing (TDD, real git/DataLad fixtures as in the spike)

- Invalid dataset: `datalad save` blocked by the hook; nothing committed;
  audit line.
- Valid dataset: save succeeds.
- Initial commit and project-creation scaffold exempt; a normal later save is not.
- Hook in a nested dataset blocks; hook missing in a new subdataset created
  by PRISM is installed; foreign hook not overwritten; missing `prism_tools`
  fails closed.
- `run_datalad_save` / `run_datalad_run` return the refusal; dirty tree is
  reported clearly on the next run.
- Phase 2: unchanged subjects reuse the cache (validator not called for them);
  a changed subject HEAD, a dirty subject, and a schema version change each
  force re-validation; cache corruption falls back to full validation;
  merged statistics yield the same issues as a full validation (equivalence
  test on a fixture dataset).

## Risks and open items

- **Workflow cost of "always on":** new projects are invalid until they have
  subjects, participants and descriptions, so PRISM's stepwise
  create/import/convert saves will be refused until the dataset validates
  (after a refusal the next `datalad run` also refuses until the tree is
  cleaned). Users must finish the setup in the working tree and save once, or
  use `--no-verify` knowingly. Accepted by the owner; a "setup phase" (gate
  engages after the first valid save) is the known, cheap fix if this hurts.
- Emergency save for partial mutations is gated by recommendation; if it must
  always succeed it needs an explicit exemption flag.
- `datalad save -r` of many subdatasets fires one hook per nested commit.
- Hooks are per clone, and the cache lives in `.git`: a fresh clone is
  ungated until `--install-hooks` runs.
- Unverified: exact cost and merge semantics of `DatasetStats`; to be read
  when planning Phase 2.
