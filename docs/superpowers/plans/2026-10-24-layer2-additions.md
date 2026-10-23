# Layer 2: additive changes to a modality (e.g. a new specimen) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A user whose data uses something an existing modality does not allow yet (a specimen `sweat` in biosample, an extra optional field) can add it to their project, validate right away, and share it: a maintainer-reviewed pull request that the bot prepares, including the schema release steps (archive, version bump, regenerated docs).

**Architecture:** One patch format, implemented once in `prism-specification` (`scripts/schema_patch.py`: validate and apply; vendored into Studio, like the term rules). Studio keeps a project's patches in `code/specification/patches/<modality>.json`, applies them to a copy of the run's schemas (`Specification.schemas`), and shares them as a proposal file `patches/<modality>.json` in format v2. The bot applies the same patch to the real schema and prepares the release.

**Tech Stack:** Python stdlib, jsonschema (already used), GitHub Actions, pytest.

**Spec:** `docs/superpowers/specs/2026-10-23-specification-contributions-design.md` (layer 2, phase 3). Builds on phase 0-2 (Studio `main` 454dbee0, prism-specification v1.2.1).

## Decisions (mine, check them)

- **Patch file:** `{"operations": [ ... ]}`, at most 20 operations. Only two operations exist, both additive:
  - `{"op": "add_enum_values", "path": "Technical.SpecimenType", "values": ["sweat"]}` — at most 20 values; each matches `^[a-z][a-z0-9-]{0,62}$`.
  - `{"op": "add_optional_properties", "path": "Technical", "properties": {"SweatRate": {"type": "number", "description": "..."}}}` — at most 20 properties; names match `^[A-Z][A-Za-z0-9]{0,62}$`; a definition may only use the keys `type` (`string|number|integer|boolean`), `description` (string, at most 500 characters), `enum` (list of strings); never `required`.
- **Path:** dotted sidecar field names (`Technical.SpecimenType`), resolved to `properties.Technical.properties.SpecimenType` of the modality schema. The path must exist and be an enum (first op) or an object with `properties` (second).
- **Only additions:** values or properties the schema already has are not errors: they are reported as "already official" and skipped (the official one wins, as for terms). A patch with nothing left to add is an error.
- **Local:** `code/specification/patches/<modality>.json` (modality: `biosample` for now, the only one with terms and the cleanest enums). Like term files it is untrusted project data: invalid → skipped and reported, never a crash.
- **Upstream path in format v2:** `patches/<modality>.json` joins the allow-list. The bot applies the patch to `schemas/stable/<modality>.schema.json`, archives the old version, bumps the **minor** version (and the `$id` suffix), regenerates the spec page's field tables — exactly the release procedure `check_schema_versions.py` enforces — and the pull request contains those files for a maintainer to review.
- **Bundle layout changes** (released together with the bot): the bot's artifact holds `bundle/status`, `bundle/log` and `bundle/files/<repository path>` for every file the pull request adds or changes (terms, archive, schema, spec page).
- **Terms over patched enums:** a child term whose `SpecimenType` is added by a patch in the same proposal is checked against the patched enum (bot) / the run's patched schema (Studio).
- **Not now:** removing or renaming values, changing types, layer 1 (new modalities), non-biosample modalities.

## Global Constraints

- One implementation: Studio runs the vendored `scripts/specification/schema_patch.py`; the wheel, the Docker image and the frozen build carry it (`scripts/build_validator_wheel.py`, `Dockerfile`, the image/bundle tests).
- Untrusted input never reaches a shell or a path without the allow-list regexes (`re.fullmatch`); patches never write outside the repository paths named above; the bot's verify step allow-lists exactly: `status`, `log`, `files/terms/<modality>/<id>.json`, `files/schemas/stable/<modality>.schema.json`, `files/schemas/archive/<modality>/<x.y.z>.schema.json`, `files/specs/<modality>.md`.
- Studio's vendored specification files are never edited by hand (change them upstream, tag, `python scripts/sync_specification.py --tag <tag>`).
- TDD; the Studio suite (`python3 -m pytest tests -q -p no:cacheprovider --ignore=tests/e2e`, baseline 6135 passed / 6 skipped) and the prism-specification suite (141) stay green; `/ponytail:ponytail-audit` before each merge; **stop and ask before the public steps (merge, tag, release of prism-specification; Task A4)**.

## Review Focus

- **Hostile patches:** unknown ops, extra keys, paths with `..`/empty segments/uppercase tricks, a path to a non-enum or to `required`, values with newlines/uppercase/long, property definitions with `$ref`, `pattern`, `additionalProperties`, `required`, nested objects, 21 ops, deep JSON. Pinned in Task A1.
- **The bot's release steps:** applying twice, a patch whose values already exist, two patches in one proposal for the same modality, a patch plus a child term on the new specimen, a stale base (the schema changed since). Pinned in A2.
- **Version mechanics:** the resulting tree passes `check_schema_versions.py` (archive is an exact copy of the previous stable file, version bumped). Pinned in A2.
- **Isolation:** project A's patch is not in project B's run (same process, thread). Pinned in B1.
- **Validator image:** a project with a patch validates in the Docker file set and degrades to a warning when the scripts are missing. Pinned in B1.

---

## Part A — prism-specification (branch `feat/schema-patches`, released as `v1.3.0`)

### Task A1: `scripts/schema_patch.py`

**Files:** Create `scripts/schema_patch.py`, `tests/test_schema_patch.py`.

**Interfaces:**
- Produces (stdlib only): `MAX_OPERATIONS = 20`, `MAX_ITEMS = 20`, `class PatchError(ValueError)`; `validate_patch(patch, schema) -> list[str]` (problems; `schema` is the modality schema the patch targets); `apply_patch(schema, patch) -> tuple[dict, list[str]]` (a deep copy with the additions applied, and the "already official" notes; `PatchError` when the patch is invalid or adds nothing); `enum_fields(schema, max_depth=2) -> list[str]` (dotted paths of the enum fields a patch may extend); `specimen_types(schema) -> list[str]` helper stays in `check_terms.py`.

- [ ] **Step 1: Write failing tests** for: both ops on the real `schemas/stable/biosample.schema.json` (the enum gains `sweat`, the original is untouched, a property appears under `Technical.properties`), every hostile case of Review Focus (parametrized, each a problem or `PatchError`, never an exception of another type), idempotence notes (`already official`), "nothing to add" error, `enum_fields` returns `Technical.SpecimenType`, `Technical.CollectionMethod`, `Technical.Anticoagulant`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_schema_patch.py -q -p no:cacheprovider`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the file and `python3 -m pytest -q -p no:cacheprovider`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(schema): additive schema patches (validate and apply)`.

### Task A2: Patches in proposals and the release steps

**Files:** Modify `scripts/term_proposal.py` (allow-list `patches/<modality>.json`; `check_proposal` validates patches and checks child terms against the patched enum; `_run_check` writes `bundle/files/...`), create `scripts/release_patch.py` (archive, bump, `$id`, regenerate the tables), `tests/test_term_proposal.py`, `tests/test_release_patch.py`.

**Interfaces:**
- Consumes: Task A1.
- Produces: `release_patch.release(repo_root: Path, modality: str, patch: dict) -> list[Path]` (writes the archive copy, the patched and re-versioned stable schema and the regenerated spec page under `repo_root`; returns the repository-relative paths); the `check` bundle holds `files/<repository path>` for terms and for those release files; `term_proposal.py check --repo DIR` (default: the repository containing the script) names where `release` works (the bot checks out the default branch, so it is the checkout).

- [ ] **Step 1: Write failing tests** (a tmp copy of the repository tree): a patch-only proposal produces archive/stable/spec files and the resulting tree passes `check_schema_versions.py` against the original; a patch plus a child term on the new specimen passes and the term file is in the bundle; a child term on an unknown specimen without the patch fails; two patch files / a patch whose values all exist / a stale patch fail with messages; v1 and term-only v2 behaviour unchanged; the bundle layout is `files/...`.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python3 -m pytest -q -p no:cacheprovider`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(terms): proposals can carry schema patches; the bot prepares the schema release`.

### Task A3: Workflow, form, docs

**Files:** Modify `.github/workflows/propose-metric.yml` (verify allow-list and `cp -R bundle/files/. .`, PR body mentions the version bump), `.github/ISSUE_TEMPLATE/propose-metric.yml`, `scripts/term_proposal.py` (`pr_body`), `CONTRIBUTING.md`, `README.md`; Test: `tests/test_propose_metric_workflow.py` (the verify step snippet is executed on good and bad bundles, as before).

- [ ] **Step 1: Write failing tests**: the verify step accepts the six allowed shapes and rejects everything else (a file under `files/scripts/`, `files/.github/`, a second schema path, `files/schemas/stable/../x`, symlinks, newline names); the PR body of a patch proposal tells the maintainer to review the version bump and archive; CONTRIBUTING documents `patches/<modality>.json`.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Write** the workflow and docs changes.
- [ ] **Step 4: Run** `python3 -m pytest -q -p no:cacheprovider`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(terms): bot workflow and docs for schema patches`.

### Task A4: Release v1.3.0 — STOP and ask first

- [ ] **Step 1: Ask** for an explicit go (merge, push, tag, release: public).
- [ ] **Step 2: On go:** merge `--no-ff`, push, wait for CI, `git tag -a v1.3.0`, `gh release create`, verify the archive URL.
- [ ] **Step 3: Live check as the owner:** one issue with a patch (`sweat`) plus a child term on it → a draft PR whose files are exactly the archive copy, the 1.2.0 stable schema, the spec page and the term file, and whose CI (`check_schema_versions`) passes when started; one hostile patch → a comment, no PR. Close the issues and the PR, delete the bot branch.

## Part B — Studio (branch `feat/layer2-additions`)

### Task B1: Adopt v1.3.0; patches in the specification

**Files:** `python scripts/sync_specification.py --tag v1.3.0`; Modify `tests/test_vendored_specification.py`, `src/spec_overlay.py` (`load_local_patches`, `write_local_patch`, `remove_local_values`, `_patch_target`), `src/specification.py` (`schemas` gets the patches applied to a deep copy; `local_patches: tuple`, `ignored_patches`), `scripts/build_validator_wheel.py`, `Dockerfile`, `scripts/validator_manifest.txt` only if the closure test demands it; Test: `tests/test_spec_overlay_patches.py`, `tests/test_validator_image_files.py`, `tests/test_validator_wheel.py`.

**Interfaces:**
- Consumes: the vendored `schema_patch.py` (Task A1) loaded like the other two scripts.
- Produces: `load_local_patches(project_root, modality="biosample") -> tuple[dict | None, list[str]]` (the validated patch with already-official operations dropped, and messages; an invalid or oversize file is a message, not an exception); `Specification.schemas[modality]` is the patched deep copy when the project has a patch (the official `official_specification()` is never mutated); symlinks and existing files are refused on writing as for terms.

- [ ] **Step 1: Write failing tests**: lock tag; load/validate/skip behaviour incl. hostile files and a symlinked folder; a project whose sidecar uses `SpecimenType: sweat` validates clean with the patch and with a schema error without it, in the same process, A then B and in a worker thread; the official specification is unchanged afterwards; the image file set and the staged wheel carry `schema_patch.py`; a missing scripts folder gives a warning, not a crash.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Sync v1.3.0**, implement.
- [ ] **Step 4: Run** the new tests and the full suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat(spec): the project's schema patches are part of its validation`.

### Task B2: Notices, the enum hint, terms over patched enums

**Files:** Modify `app/src/validator.py` (the schema-error branch: an `enum` error on a patchable field adds the hint; INFO "uses the local addition ..."), `src/term_proposal.py` (`check_with_specification` takes the specimens from the run's schema when given), `src/spec_overlay.py` (`add_local_term` for a local specimen); Test: `tests/test_spec_overlay_runs.py`, `tests/test_spec_overlay_ops.py`.

- [ ] **Step 1: Write failing tests**: the enum error for `sweat` ends with the exact command (`python prism_tools.py spec local add-values --project "<root>" --field Technical.SpecimenType --value sweat`); a project using a local addition gets one INFO per run naming it and the share command; an addition that became official gets the "now official, remove it" INFO; `add_local_term` for a column in a `sweat` sidecar works once the patch exists and is refused before.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** them and the full suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat(spec): notices and hints for local schema additions`.

### Task B3: Operations and commands

**Files:** Modify `src/spec_overlay.py` (`add_local_values`, `find_unknown_values`, `list_local_items` shows layer 2 with status), `app/src/cli/commands/spec.py`, `app/src/cli/parser.py` (`spec local add-values --project P --field F --value V [--value V ...] [--modality biosample]`, `spec local remove-values --project P --field F --value V`), `app/src/cli/dispatch.py`, `app/src/cli/entrypoint.py`; Test: `tests/test_spec_overlay_ops.py`, `tests/test_cli_spec.py`, `tests/test_cli_dispatch_routing.py`.

**Interfaces:**
- Produces: `add_local_values(project_root, field: str, values: list[str], modality="biosample") -> dict` (`{"patch", "written", "skipped"}`; refuses a field that is not a patchable enum, values the schema already has are `skipped`), `find_unknown_values(project_root, modality="biosample") -> list[dict]` (`{"field", "value", "data_file"}` for sidecar values outside the patched enums, once per sidecar and value, never under `code/`, `derivatives/`, `sourcedata/`, `.git/`).

- [ ] **Step 1: Write failing tests**: add, add twice (merges, no duplicates), unknown field, official value skipped, remove-values (the last value removes the file), find_unknown_values on a project with `sweat`, the CLI commands and routing cases, `spec local list` shows layer 2.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** them and the full suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat(spec): spec local add-values and remove-values`.

### Task B4: Sharing patches

**Files:** Modify `src/term_proposal.py` (`as_v2` knows `patches/<modality>.json`), `src/spec_overlay.py` (`proposal_for_local_terms` → `proposal_for_local(project_root, term_ids=None, include_patch=True, ...)` keeps its name and gains patch files; a patch is included with `--all`, with `--patch`, never for plain `--term`), `app/src/cli/commands/spec.py` and the parser (`spec propose ... --patch`), the route body (`{"patch": true}`); Test: `tests/test_spec_overlay_ops.py`, `tests/test_cli_spec.py`, `tests/test_specification_contribute_routes.py`.

- [ ] **Step 1: Write failing tests**: `--all` on a project with a patch and two terms gives a v2 document with `patches/biosample.json` that the vendored check accepts; `--patch` alone; a patch whose values the official schema has now is skipped and reported; the size limit and the 40-file limit count the patch file.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** them and the full suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat(spec): share schema additions in a proposal`.

### Task B5: The "Addition to a modality" tab

**Files:** Modify `app/src/web/blueprints/specification_contribute.py` (`GET /api/spec/local` also returns `unknown_values`; `POST /api/spec/local/add-values`, `POST /api/spec/local/remove-values`), `app/templates/specifications_contribute.html`, `app/static/js/modules/specification/contribute.js` (the tab becomes active; "Found in your data" lists unknown values with *Add to this project*; a small form for a value of a chosen enum field; local additions with *Remove*), `app/src/web/project_ready_guard.py` (already exempts `/api/spec/`); Test: `tests/test_specification_contribute_routes.py`, `tests/e2e/test_specification_contribute_flows.py`, `tests/test_html_validity.py`.

- [ ] **Step 1: Write failing tests**: the routes (400 without a project, bad bodies, the add/list/remove round trip, an escape via `field`), the page script writes values with `textContent` only, an e2e flow with a sidecar using `sweat`: found, added, the list shows it, *Share all* contains `patches/biosample.json`, removed.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** thin adapters only.
- [ ] **Step 4: Run** them, the full suite, the e2e flows and the HTML validity test. Expected: PASS.
- [ ] **Step 5: Commit** `feat(spec): Addition to a modality tab`.

### Task B6: Docs, checks, audit

**Files:** Modify `docs/CLI_REFERENCE.md`, `docs/studio/specifications.md`, `CHANGELOG.md`, `CLAUDE.md` (the overlay note names patches), the design doc status line.

- [ ] **Step 1: Write** the docs.
- [ ] **Step 2: Run** full suite, `python3 tests/verify_repo.py --check dual-tree-drift --no-fix` (delete its report file), `python3 scripts/ci/check_specification_lock.py`, `python3 -m pytest tests/test_html_validity.py -q -p no:cacheprovider`. Expected: green.
- [ ] **Step 3: Run `/ponytail:ponytail-audit`**, apply what is worth it, re-run, ask before merging.
- [ ] **Step 4: Commit** `docs(spec): schema additions`.
