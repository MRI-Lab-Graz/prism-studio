# Proposing a metric — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `prism_tools.py terms propose --sidecar F --column C [--open]` builds a one-JSON proposal from a sidecar column and opens a prefilled "Propose a metric" issue in `prism-specification`, where a bot checks it and (for trusted authors) opens a draft pull request with the term files.

**Architecture:** Part A (repository `prism-specification`, released as `v1.1.0`): `scripts/term_proposal.py` (format, validation, issue parsing, writing term files), the issue form, the two-job workflow, docs. Part B (Studio): sync `v1.1.0`, `src/term_proposal.py` (sidecar column → proposal, issue URL), the `terms propose` command that validates with the vendored script, bundle packaging, docs.

**Tech Stack:** Python stdlib, pytest, GitHub issue forms + Actions.

**Spec:** `docs/superpowers/specs/2026-10-23-metric-proposal-design.md` (builds on the registry and repository designs of 2026-10-22).

## Global Constraints

- Proposal JSON: `{"modality": "biosample", "terms": [<term>, ...]}`, at most 2 terms, at most 20000 bytes (UTF-8).
- Allowed term fields: `TermID, Level, Label, Aliases, Description, Parent, SpecimenType, Units, AlternativeUnits, MinValue, WarnMaxValue, LOINC, Equivalents`. `Status` and `ReplacedBy` are not allowed (the merge sets `Status: "official"`); any other key is an error.
- Proposed `TermID`s use the `prism:` prefix only; the local part must pass the registry slug rule before any file name is derived from it.
- The proposed terms are checked **together with the current registry** (same `check_registry` rules as CI), so collisions with official IDs, aliases and labels fail.
- The issue form field ids/labels: textarea `proposal` (label "Proposal"), checkboxes "licence" and "no personal data" must be ticked; template file `propose-metric.yml`, label `type: new-metric`.
- Issue body is untrusted text: never executed, never put in a `run:` line via `${{ }}`; workflow jobs follow the modality bot (`check`: `contents: read`, no credentials; `report`: treats the artifact as plain data, verifies no links/special files); draft PR only for `OWNER`, `MEMBER`, `COLLABORATOR`.
- `terms propose` sends nothing unless `--open`, never calls the GitHub API, opens the issue form URL of `MRI-Lab-Graz/prism-specification` only; URL limit 6000 characters, otherwise it prints the proposal and the form URL separately.
- Studio's specification files are vendored: never edit `docs/specs/`, `app/schemas/`, `official/library/terms/`, `scripts/specification/` in Studio; change them in `prism-specification`, release a tag, run `python scripts/sync_specification.py --tag <tag>` (see CLAUDE.md).
- Both repos: TDD (failing test first, watch it fail), ponytail, commits end with the attribution line from the session. Part A needs the user's explicit go before pushing to `prism-specification` `main`, tagging and releasing `v1.1.0` (public, outward-facing: **stop and ask at Task A4**). Studio's `/ponytail:ponytail-audit` runs before its merge.

## Review Focus

- **Hostile issue body:** oversize, no JSON, two JSON blocks, JSON that is a list, a `TermID` like `prism:../x`, extra fields, `Status` set, `bids:` IDs. Pinned in Task A1.
- **Proposing something already official** (same ID, a label or alias an official term owns): fails with the colliding term named. Pinned in Task A1.
- **Child-only proposal whose parent does not exist** fails; with an official parent it passes. Pinned in Task A1.
- **Workflow injection:** no `${{ }}` inside any `run:`; the report job never executes anything from the artifact. Pinned in Task A3.
- **Unicode and long values in the issue URL** are percent-encoded; over the cap there is a fallback, not a truncated proposal. Pinned in Task B2.
- **Packaged app:** `scripts/specification` must be bundled, or `terms propose` fails in the frozen build. Pinned in Task B3.

---

## Part A — `prism-specification` (`/Users/karl/work/github/prism-specification`, branch `feat/term-proposal`)

### Task A1: Proposal format and validation

**Files:**
- Create: `scripts/term_proposal.py`, `tests/test_term_proposal.py`
- Modify: `scripts/check_terms.py` (add `specimen_types`, use it in `main`), `tests/test_check_terms.py` (one test for it)

**Interfaces:**
- Consumes: `check_terms.check_registry(registry: dict[str, dict], specimen_types: list[str]) -> list[str]` and `load_terms` (loaded with `importlib.util.spec_from_file_location` from the script's own folder, as the tests do).
- Produces in `check_terms.py`: `specimen_types(schema_file: Path) -> list[str]` (the `Technical.SpecimenType` enum).
- Produces in `term_proposal.py` (stdlib only): `MAX_BYTES = 20000`, `MAX_TERMS = 2`, `ALLOWED_FIELDS: frozenset[str]`, `class ProposalError(ValueError)`, `extract_proposal(issue_body: str) -> dict` (reads the section `### Proposal`, accepts the JSON bare or inside a fenced block, requires both checkboxes ticked, raises `ProposalError` with a user-facing message), `check_proposal(proposal: dict, registry: dict[str, dict], specimens: list[str]) -> tuple[list[dict], list[str]]` (returns the terms with `Status: "official"` added, and the problems; problems are the shape rules of Global Constraints plus `check_registry` on `registry + new terms`).

- [ ] **Step 1: Write failing tests** in `tests/test_term_proposal.py` (module loaded by path; registry from `terms/biosample` via `check_terms.load_terms`; specimens via `check_terms.specimen_types`): `test_extract_reads_fenced_and_bare_json`, `test_extract_requires_both_checkboxes`, `test_extract_rejects_missing_oversize_and_two_blocks`, `test_valid_parent_and_child_pass_and_get_status_official`, `test_child_only_with_official_parent_passes`, `test_child_only_without_parent_fails`, `test_already_official_id_fails_naming_the_term`, `test_alias_or_label_owned_by_an_official_term_fails`, `test_status_replacedby_and_unknown_fields_fail`, `test_bids_prefix_and_traversal_ids_fail` (`bids:x`, `prism:../x`, `prism:A`), `test_more_than_two_terms_fails`, `test_proposal_that_is_not_an_object_or_has_no_terms_fails`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_term_proposal.py -q -p no:cacheprovider`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `specimen_types` (move the lines out of `main`) and `term_proposal.py` as specified.
- [ ] **Step 4: Run** `python3 -m pytest -q -p no:cacheprovider`. Expected: PASS (all repository tests).
- [ ] **Step 5: Commit** `feat(terms): proposal format and validation`.

### Task A2: Command line, bundle and PR text

**Files:**
- Modify: `scripts/term_proposal.py`, `tests/test_term_proposal.py`

**Interfaces:**
- Consumes: Task A1 functions.
- Produces: `write_terms(terms: list[dict], out_dir: Path, modality: str) -> list[Path]` (`<out_dir>/<modality>/<local>.json`, JSON with 2-space indent and trailing newline; the local part is re-validated against the slug rule before it becomes a file name), `pr_body(issue_number: int, log: str) -> str` (a **draft** note, the warnings from the log as inline code spans, and the maintainer checklist: ID sensible and final/frozen; user's name in `Aliases`; units UCUM; no invented ranges or LOINC codes; CI green), `main(argv) -> int` with subcommands `check --terms DIR --schema FILE --out DIR [--file F]` (reads `$ISSUE_BODY` unless `--file`, which holds the bare proposal JSON; writes `<out>/status` = `ok`/`failed`, `<out>/log`, and on success the term files under `<out>/terms/`; exit 0 whenever it wrote a bundle, 1 only on usage errors) and `pr-body` (reads `ISSUE_NUMBER`, `LOG_FILE`).

- [ ] **Step 1: Write failing tests**: `test_write_terms_creates_one_file_per_term_and_passes_the_registry_check` (write into a copy of `terms/`, then `check_terms` on it returns no problems), `test_write_terms_refuses_a_bad_local_part`, `test_check_cli_with_issue_body_env_writes_an_ok_bundle`, `test_check_cli_failure_writes_status_failed_and_the_reasons`, `test_check_cli_file_mode_equals_issue_mode`, `test_pr_body_is_a_draft_with_the_checklist_and_neutralised_warnings` (a backtick or `@mention` in a warning stays inert).
- [ ] **Step 2: Run** the test file. Expected: FAIL.
- [ ] **Step 3: Implement** `write_terms`, `pr_body`, `main` (argparse subcommands).
- [ ] **Step 4: Run** `python3 -m pytest -q -p no:cacheprovider`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(terms): proposal command line, bundle and pull request text`.

### Task A3: Issue form, workflow, docs

**Files:**
- Create: `.github/ISSUE_TEMPLATE/propose-metric.yml`, `.github/workflows/propose-metric.yml`, `tests/test_propose_metric_workflow.py`
- Modify: `specs/biosample.md` (the sentence "Sharing itself is not available yet." becomes: share with `python prism_tools.py terms propose` from PRISM Studio, or open the issue form), `CONTRIBUTING.md` (new section "Proposing a metric with PRISM Studio or the issue form"), `README.md`, `.github/workflows/ci.yml` (nothing to add unless the tests need `pyyaml`, already installed)

**Interfaces:**
- Consumes: `term_proposal.py check` and `pr-body` (Task A2); the modality bot in Studio's `.github/workflows/propose-modality.yml` as the structural model.
- Produces: the form (title `"[Metric]: "`, labels `["type: new-metric", "status: needs-triage"]`, textarea id `proposal`, two required checkboxes) and workflow `Propose metric` (on `issues: opened`, jobs `check` then `report` as in Global Constraints; branch name `metric/issue-<n>-<run id>`; commit/PR title "Propose metric (issue #<n>)").

- [ ] **Step 1: Write failing tests** (`yaml.safe_load` of both files): form has a textarea with id `proposal`, two required checkboxes, label `type: new-metric`; workflow runs only for that label; `check` has `permissions: {contents: read}` and `persist-credentials: false`; no `run` step in either job contains `${{`; the `report` job verifies the bundle is plain files and opens the PR only for `OWNER`/`MEMBER`/`COLLABORATOR`; every `uses:` is pinned to a commit SHA.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_propose_metric_workflow.py -q -p no:cacheprovider`. Expected: FAIL.
- [ ] **Step 3: Write** the form and the workflow (copy the modality bot's two-job shape: `check` runs `python scripts/term_proposal.py check --terms terms/biosample --schema schemas/stable/biosample.schema.json --out bundle` with the issue body in `env:`; `report` comments on failure + `needs-changes` label, opens the draft PR on success for trusted authors, comments "a maintainer will take over" for others), and the docs edits.
- [ ] **Step 4: Run** `python3 -m pytest -q -p no:cacheprovider` and `python3 scripts/generate_schema_reference.py --check`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(terms): propose-metric issue form and bot`.

### Task A4: Release v1.1.0 — STOP and ask first

- [ ] **Step 1: Ask the user** for an explicit go to merge `feat/term-proposal` into `main`, push, tag `v1.1.0` and publish the release (public).
- [ ] **Step 2: On go**: merge `--no-ff`, `git push origin main`, `git tag -a v1.1.0`, `git push origin v1.1.0`, `gh release create v1.1.0 --repo MRI-Lab-Graz/prism-specification --notes "Adds the propose-metric issue form and bot and scripts/term_proposal.py."`.
- [ ] **Step 3: Verify**: `curl -sfIL https://github.com/MRI-Lab-Graz/prism-specification/archive/refs/tags/v1.1.0.tar.gz` → 200; CI on `main` green; open one test issue from the form with the example proposal as the owner and confirm a draft PR appears and fails nothing; close both without merging.

## Part B — Studio (branch `feat/terms-propose`, from `main`)

### Task B1: Adopt v1.1.0

**Files:**
- Run: `python scripts/sync_specification.py --tag v1.1.0`
- Modify: `tests/test_vendored_specification.py` (expected tag), `app/schemas/PRISM_SPECIFICATION_LICENSE` only through the sync

- [ ] **Step 1: Write the failing test change**: `test_lock_matches_tree_and_v1` expects tag `v1.1.0` (rename it `…_and_the_pinned_tag`).
- [ ] **Step 2: Run** it. Expected: FAIL (lock still `v1.0.0`).
- [ ] **Step 3: Sync**; `git diff --stat` shows only `scripts/specification/term_proposal.py` (+ `check_terms.py`, `docs/specs/biosample.md`) and the lock.
- [ ] **Step 4: Run** `python3 -m pytest tests/test_vendored_specification.py tests/test_check_specification_lock.py tests/test_check_terms.py -q -p no:cacheprovider` and `python3 scripts/ci/check_specification_lock.py`. Expected: PASS / exit 0.
- [ ] **Step 5: Commit** `chore(specification): adopt prism-specification v1.1.0`.

### Task B2: Sidecar column → proposal, issue URL

**Files:**
- Create: `src/term_proposal.py`, `tests/test_term_proposal.py`
- Check first: `find src app/src -name term_proposal.py` (must find only the new file)

**Interfaces:**
- Consumes: `src.term_registry.resolve_column`, `Resolution` (registry dict from `load_registry()`).
- Produces: `class ProposalError(ValueError)`; `slugify(text: str) -> str` (lowercase, runs of non-`[a-z0-9]` become `-`, trimmed; `ProposalError` if the result does not start with a letter); `build_proposal(registry: dict[str, dict], sidecar: dict, column: str, label: str | None = None, modality: str = "biosample") -> dict`; `issue_url(proposal: dict, repo: str = "MRI-Lab-Graz/prism-specification", limit: int = 6000) -> str | None` (`https://github.com/<repo>/issues/new?template=propose-metric.yml&title=…&proposal=<percent-encoded compact JSON>`; `None` when longer than `limit`).

`build_proposal` cases (from `resolve_column(registry, column, col_def, specimen)`): `unknown` → parent + child; `known_analyte_new_specimen` → child only with `Parent` = that term's `TermID`; `term`, `suggestion`, `deprecated`, `specimen_mismatch` → `ProposalError` naming the term to use / the message. A missing column, a non-object column, no `Technical.SpecimenType`, or no `Units` (and no term to supply them) → `ProposalError`. The user's column name goes into the parent's `Aliases` (not for child-only proposals); the child takes `Units`, `MinValue`, `WarnMaxValue`, `LOINC` from the column when present; the parent's `Description` is the column `Description` when it is a string.

- [ ] **Step 1: Write failing tests** with a small in-test registry like `tests/test_term_registry.py`: `test_unknown_metric_becomes_parent_and_child`, `test_known_analyte_new_specimen_becomes_child_only`, `test_official_term_is_refused_with_the_term_to_use` (alias `cort`, and a column with `Term`), `test_label_option_changes_the_slug_not_the_alias`, `test_missing_specimen_units_or_column_is_an_error`, `test_slugify`, `test_issue_url_encodes_unicode_and_json`, `test_issue_url_over_the_limit_is_none`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_term_proposal.py -q -p no:cacheprovider`. Expected: FAIL.
- [ ] **Step 3: Implement** as specified (stdlib `urllib.parse.quote`, `json.dumps(separators=(",", ":"), ensure_ascii=False)`).
- [ ] **Step 4: Run** the same command plus `tests/test_validator_manifest_closure.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(terms): build a metric proposal from a sidecar column`.

### Task B3: `terms propose` command, packaging, validator hint

**Files:**
- Modify: `app/src/cli/commands/terms.py`, `app/src/cli/parser.py` (`propose` under `terms`), `app/src/cli/dispatch.py` (+ `terms_propose` route), `app/src/cli/entrypoint.py` (handler), `tests/test_cli_dispatch_routing.py` (case), `scripts/build/build_app.py` (bundle `scripts/specification`), `tests/test_bundle_packaging_guards.py`, `app/src/validator.py` (`_check_biosample_terms`: the unknown-metric INFO ends with the command to run, `prism_tools.py terms propose --sidecar <sidecar> --column <col>`), `scripts/validator_manifest.txt` only if `tests/test_validator_manifest_closure.py` demands it
- Test: `tests/test_cli_terms.py`, `tests/test_validator_biosample_terms.py`

**Interfaces:**
- Consumes: `src.term_proposal.build_proposal`, `issue_url` (Task B2); the vendored `scripts/specification/term_proposal.py` `check_proposal` and `check_terms.specimen_types` (loaded with `importlib.util.spec_from_file_location` from `<repo root>/scripts/specification/`, falling back to `<_MEIPASS>/scripts/specification/` when frozen).
- Produces: `prism_tools.py terms propose --sidecar FILE --column NAME [--label TEXT] [--modality biosample] [--open] [--json]`; handler `cmd_terms_propose(args)`. Exit 0 with the proposal printed (text: the JSON, the similar official terms, the notice that maintainers may change the name, and the form URL or the fallback text); exit 1 with the message on `ProposalError` or when the vendored validation reports problems (nothing is opened). `--json` → `{"success", "proposal", "issue_url", "similar", "problems"}`. `--open` calls `webbrowser.open(url)` only when the URL exists and validation passed.

- [ ] **Step 1: Write failing tests**: in `tests/test_cli_terms.py` (real subprocess, sidecar written to `tmp_path`): `test_propose_prints_a_valid_proposal_and_opens_nothing`, `test_propose_json_has_issue_url_and_no_problems`, `test_propose_official_metric_exits_1`, `test_propose_open_calls_webbrowser` (in-process with `webbrowser.open` monkeypatched, using the handler directly), `test_propose_validation_problem_exits_1_and_opens_nothing`; routing case `terms propose` in `tests/test_cli_dispatch_routing.py`; `test_build_script_bundles_the_vendored_specification_scripts` in `tests/test_bundle_packaging_guards.py` (reads `scripts/build/build_app.py` text, expects `scripts/specification`); in `tests/test_validator_biosample_terms.py`: `test_unknown_metric_notice_names_the_propose_command` (the INFO contains `terms propose` and the column name).
- [ ] **Step 2: Run** `python3 -m pytest tests/test_cli_terms.py tests/test_cli_dispatch_routing.py tests/test_bundle_packaging_guards.py tests/test_validator_biosample_terms.py -q -p no:cacheprovider`. Expected: FAIL.
- [ ] **Step 3: Implement** the handler (thin: load registry, read sidecar JSON, `build_proposal`, vendored `check_proposal`, print/open), parser/dispatch/entrypoint wiring as `terms list` does, the `build_app.py` data entry (`scripts/specification` → `scripts/specification`), and the validator hint.
- [ ] **Step 4: Run** the same command plus `tests/test_cli_command_import_boundaries.py tests/test_validator_manifest_closure.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(terms): terms propose command`.

### Task B4: Docs, changelog, release checks

**Files:**
- Modify: `docs/CLI_REFERENCE.md` (the `terms propose` section), `CHANGELOG.md` (Unreleased: Added), `docs/SPECIFICATIONS.md` only if it still says sharing is unavailable
- Test: `tests/test_docs_*` already guarding docs must stay green

- [ ] **Step 1: Write the docs** (no test of its own; wording from the design: nothing is sent without `--open`, maintainers may rename, the user's name becomes an alias).
- [ ] **Step 2: Run** the full suite `python3 -m pytest tests -q -p no:cacheprovider --ignore=tests/e2e`, `python3 scripts/ci/check_specification_lock.py`, `python3 tests/verify_repo.py --check dual-tree-drift --no-fix` (delete the report file it writes). Expected: all green.
- [ ] **Step 3: Run `/ponytail:ponytail-audit`** on the branch (repo rule), apply what is worth it, re-run the suite, then ask before merging.
- [ ] **Step 4: Commit** `docs(terms): terms propose`.
