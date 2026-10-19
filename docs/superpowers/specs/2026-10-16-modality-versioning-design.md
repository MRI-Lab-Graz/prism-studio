# Per-modality schema versions, pinned in project.json

Decided 2026-10-16. Builds on `2026-10-16-modality-naming-docs-design.md`
(modality proposals start at schema version `1.0.0`).

## Intent

PRISM modalities change over time and new ones arrive from outside. A dataset
must keep validating the way it did when it was created, unless its owner
decides otherwise. BIDS versions all modalities as one block; PRISM versions
each modality on its own:

- every modality schema has its own version (`major.minor.patch`), starting at
  `1.0.0` when it is proposed;
- the validator uses the **latest** version of each modality by default;
- a project **pins** the version of each modality it uses in `project.json`;
- a user can override one modality for one run on the command line;
- when PRISM ships a newer version of a pinned modality the user is told once
  and decides: update to it, or freeze the current one.

Out of scope: pinning the filename rules (they live in the shared
`entities.schema.json` and always follow the latest; they only grow), per-file
versions chosen in a sidecar, tooling that migrates data between versions,
schema diff viewers.

## 1. Storage: `stable/` is latest, old versions are archived

- `app/schemas/stable/<name>.schema.json` is always the newest version
  (unchanged, so every existing loader keeps working). Its `version` field is the
  modality's current version.
- Before a modality schema changes, its previous version is copied to
  `app/schemas/archive/<name>/<x.y.z>.schema.json` and is never edited again.
  Versions that existed before this feature (e.g. survey 1.1.1) have no archive
  entry until the first change, so they can only be pinned at their current
  value. The legacy global bundles `v0.1` and `v0.2` stay as they are.
- Scope: the community modality schemas (`COMMUNITY_MODALITY_SCHEMAS` in
  `tests/verify_repo.py`: survey, biometrics, environment, physio, eyetracking,
  events and every registered proposal). App-internal schemas
  (`project`, `dataset_description`, `entities`, recipes) are not per-modality
  versioned.
- The archive ships with the app (`app/schemas` is already bundled whole by the
  PyInstaller build and the validator package; verified in the plan).

## 2. Resolution (one function, one place)

New backend module `src/modality_versions.py` (single implementation; CLI and
Studio call it):

- `current_versions() -> dict[str, str]`: modality -> version of its stable
  schema.
- `available_versions(name) -> list[str]`: archive plus current, sorted by
  semver.
- `load_modality_schema(name, version)`: stable file if `version` equals its
  current version, else the archive file; an unknown version is an **error**
  listing the available versions (never a silent fallback).
- `resolve_modality_versions(project_pins, overrides) -> dict[str, str]`:
  per modality: command-line override, else the `project.json` pin, else the
  latest.

`schema_manager.load_all_schemas(schema_dir, version=None)` gains an optional
`modality_versions: dict[str, str] | None` and uses `load_modality_schema` for
those names; everything else is unchanged. `--schema-version` keeps its meaning
(a whole legacy bundle as the base); per-modality versions are applied on top.
The version used per modality, and where each came from (`cli`, `project.json`
or `latest`), is kept in the validation statistics (`validator_info`), which
Studio stores in the project's validation record; the command-line `--json`
report does not list it yet.

## 3. The pin in project.json

Two new optional objects in `project.json` (and in `project.schema.json`, which
forbids unknown keys today):

    "SchemaVersions": {"survey": "1.1.1", "biometrics": "1.1.1"},
    "SchemaVersionsAcknowledged": {"survey": "1.1.1"}

Values match `^\d+\.\d+\.\d+$`; keys are modality names.

- **Pin on first import.** The first time a modality is imported or converted
  into a project, PRISM writes the modality's current version into
  `SchemaVersions` (idempotent: an existing pin is never changed). The function
  is `pin_modality(project_root, name)`; every converter entry point that
  writes a modality into a project calls it (survey, biometrics, physio,
  environment, eyetracking, events and the proposal-generated ones; the plan
  enumerates the call sites and tests each).
- **Told once.** `pending_updates(project) -> list[(name, pinned, latest)]`
  returns modalities whose latest version is newer than the pin **and** not equal
  to the acknowledged version. `update_modality(project_root, name)` sets the pin
  (and acknowledgement) to the latest; `freeze_modality(project_root, name)`
  sets the acknowledgement to the latest and keeps the pin. A later, even newer
  version triggers a new notice. The user must re-validate after an update
  (PRISM does not migrate data).
- Projects without pins keep working and validate against the latest.
- Text-format policy: `project.json` stays plain git (already in the
  `annex.largefiles=nothing` rules); no `.gitattributes` change.

## 4. Command line and Studio

Every action is a command (repo rule); Studio only calls it.

- `prism.py <dataset> --modality-version survey=1.0.3` (repeatable). The
  validator also reads `SchemaVersions` from `<dataset>/project.json` when
  present. `--list-versions` additionally lists the versions per modality.
- `prism_tools modality-version status|update <name>|freeze <name>|list [name]`
  (same options in Studio). `status` prints the pins and any pending update.
- A pending update is shown as a single stderr line by `prism.py` (it never
  blocks, so scripts and CI are unaffected) until the user decides, and as a
  notice with two buttons ("Update" / "Keep current version") on the Studio
  project page.

## 5. CI guard for frozen versions

`scripts/ci/check_schema_versions.py <base> <head>` (run in CI on pull
requests, like the other `scripts/ci` helpers) fails when, between base and
head, for a community modality schema:

- a file under `app/schemas/archive/` is modified or deleted;
- the stable schema changed but its `version` did not;
- the version was bumped but the previous version is missing from the archive.

New archive files and new modalities (first version `1.0.0`, no archive) pass.
`REGISTRATION.md` (proposal workflow) keeps registering the schema at `1.0.0`;
the docs for maintainers (`docs/SCHEMA_VERSIONING.md`) describe how to release
a new modality version: bump `version` and `$id`, archive the previous file.

## 6. Documentation

`docs/SCHEMA_VERSIONING.md` is rewritten around per-modality versions: what a
version is, defaults, pins in `project.json`, the update/freeze decision, the
command-line override, how to release a new modality version (maintainers), and
the legacy `v0.1`/`v0.2` bundles. The modality proposal docs say new modalities
start at `1.0.0`. The `modality-docs` check is unchanged.

## Clarifications from the plan

- **Pins and the base.** Project pins apply only on the stable base. An explicit
  legacy `--schema-version v0.x` ignores them; `--modality-version` applies on any base.
- **Older projects.** `prism_tools modality-version pin <project>` exists so projects
  created before pinning can be pinned.
- **Validation is read-only.** It never writes pins; only imports and the `pin`,
  `update` and `freeze` commands write `project.json`.
- **Studio notice.** The Studio notice with Update / Keep current version buttons is a
  follow-up plan. Until then the decision is made with `modality-version update` /
  `freeze`, and the stderr hint from `prism.py` is the notice.
- **Pin on import** is wired at the converter functions, `copy_files_into_project`
  (all Studio imports) and `perform_environment_conversion`.
- **CI guard.** It does not guard deletion or renaming of a stable modality schema.

## Testing

TDD per piece: `src/modality_versions.py` (current/available versions,
resolution precedence, unknown version error), `load_all_schemas` with
per-modality versions on top of a legacy base, pin on first import (and
idempotence) for each converter entry point, `pending_updates`/update/freeze
state machine including a second newer version, `project.schema.json` accepts
and validates the new keys, CLI flags and commands (`--json` contract kept),
the stderr hint, the Studio route that calls the same commands, the CI guard
(each failure mode and the passing cases), and an end-to-end test: pin survey
at an archived version, change stable, validate with and without the pin and
with a CLI override.
