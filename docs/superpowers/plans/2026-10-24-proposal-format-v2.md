# Proposal format v2: many terms per proposal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One proposal can carry every local metric of a project (not at most two terms), in a format that names the repository files it adds, so later layers (schema patches, new modalities) fit the same document; the bot and the checks stay one implementation.

**Architecture:** Part A (`prism-specification`, released as `v1.2.0`): `scripts/term_proposal.py` reads format v2 (and still v1), validates it against an allow-list of repository paths and the current registry, and the bot writes the files. Part B (Studio): sync `v1.2.0`, `spec propose` / the Contribute page share several local terms at once, and every proposal Studio builds is delivered as v2.

**Tech Stack:** Python stdlib, GitHub issue forms + Actions, pytest.

**Spec:** `docs/superpowers/specs/2026-10-23-specification-contributions-design.md` ("Proposal format v2 and the bot"), `2026-10-23-metric-proposal-design.md` (v1). Builds on phase 1 (merged c8263fb3) and prism-specification v1.1.2.

## Decisions (mine, check them)

- **Format v2:** `{"format": "prism-proposal/2", "files": {"terms/<modality>/<local-id>.json": <term>, ...}}`. The paths are repository paths, so the bot copies content to exactly that path. v1 (`{"modality", "terms"}`) stays accepted and is converted to v2 internally.
- **Allow-list (this phase):** only `terms/<modality>/<local>.json` with `modality` in `MODALITIES` and `<local>` matching the term ID rule; the term's `TermID` local part must equal the file stem. Later layers add their paths to the same allow-list.
- **Limits:** at most 40 files, at most 50,000 bytes (a GitHub issue-form text field holds 65,536 characters). Replaces `MAX_TERMS = 2` (v1 keeps 2).
- **No attachments (changes the design text):** a proposal too long for the prefilled link is pasted into the form's text field (up to the limit above); nothing is downloaded by the bot.
- **Parents:** a child term's `Parent` must be in the registry or in the same proposal (checked by the existing registry check on registry + proposal).
- **Studio delivers v2 always** (after syncing v1.2.0); `terms propose` and `spec propose` share `deliver_proposal`, so the conversion lives in one place.

## Global Constraints

- Allowed term fields, `prism:` IDs only, no `Status`/`ReplacedBy`, value types: unchanged (`ALLOWED_FIELDS`, `check_terms.type_problems`, `_LOCAL`).
- The issue body is untrusted text: parsed as JSON only; every path comes from the allow-list regex and is re-checked (`fullmatch`) in `write_terms`; nothing outside the bundle folder is ever written; the bot's `report` job and its bundle verification are unchanged.
- Errors are messages (a failed bundle), never tracebacks; the log stays capped at 50 problems.
- Studio's vendored specification files are never edited by hand: change them in `prism-specification`, release a tag, `python scripts/sync_specification.py --tag <tag>`.
- TDD; full suite `python3 -m pytest tests -q -p no:cacheprovider --ignore=tests/e2e` stays green (baseline 6100 passed, 6 skipped on main c8263fb3), prism-specification suite green; `/ponytail:ponytail-audit` before each merge; **stop and ask before the public steps (merge/tag/release of prism-specification, Task A3)**.

## Review Focus

- **Hostile v2 documents:** `files` not an object; keys with `..`, `/`, absolute paths, uppercase, a trailing newline, another modality, another folder (`schemas/...`, `.github/...`, `scripts/...`); values that are not objects; stem ≠ `TermID` local part; the same term under two keys; 41 files; 51,000 bytes; `format` missing or unknown. Pinned in Task A1.
- **A v2 file that collides with an official term** (ID, alias, label): rejected naming the official term. Pinned in A1.
- **v1 still works** (the modality of v1 and the 2-term cap). Pinned in A1.
- **Paste path:** a 40-term proposal is far above the prefilled-link limit and still passes through the form's text field with CRLF line endings and fences. Pinned in A2.
- **Studio:** sharing several terms whose parent is local and whose children are for different specimens; a child whose parent is official; sharing everything when some local terms are `now-official` (skipped, reported). Pinned in Task B1.

---

## Part A — prism-specification (`/Users/karl/work/github/prism-specification`, branch `feat/proposal-v2`)

### Task A1: Format v2 in `term_proposal.py`

**Files:** Modify `scripts/term_proposal.py`, `tests/test_term_proposal.py`.

**Interfaces:**
- Produces: `FORMAT_V2 = "prism-proposal/2"`, `MAX_FILES = 40`, `MAX_BYTES = 50_000`, `V1_MAX_TERMS = 2`; `normalize(proposal) -> tuple[list[tuple[str, dict]], list[str]]` (the `(repo path, term)` pairs of a v1 or v2 document and the shape problems; v1 pairs get paths `terms/<modality>/<local>.json`); `check_proposal(proposal, registry, specimens)` keeps its signature and return `(terms_with_status, problems)` but accepts both formats (terms ordered as in the document; paths available through `normalize`); `write_terms(terms, out_dir, modality)` unchanged for callers; `_run_check` writes each term to the path `normalize` derived.

- [ ] **Step 1: Write failing tests**: v2 happy path (parent + 3 children across files, the parent only in the proposal), v1 conversion gives the same terms, every hostile case of Review Focus (parametrized, each expects a problem and no files), 40 files pass / 41 fail, 50,001 bytes fail through `extract_proposal` and `--file`, official collision named, `format` missing → treated as v1, `format` other than v2 with `files` → error, `check` CLI writes `terms/biosample/<stem>.json` for v2.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_term_proposal.py -q -p no:cacheprovider`. Expected: FAIL.
- [ ] **Step 3: Implement** `normalize` and extend `check_proposal`/`_run_check`; keep v1 behaviour and messages byte-for-byte where tests pin them.
- [ ] **Step 4: Run** `python3 -m pytest -q -p no:cacheprovider`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(terms): proposal format v2 (files by repository path, up to 40)`.

### Task A2: Form, docs, paste path

**Files:** Modify `.github/ISSUE_TEMPLATE/propose-metric.yml` (text: one proposal document, one or many terms; v2), `CONTRIBUTING.md` (format v2, limits, the paste path), `README.md` if it states the 2-term limit; Test: `tests/test_term_proposal.py`, `tests/test_propose_metric_workflow.py`.

- [ ] **Step 1: Write failing tests**: a 40-file v2 body as the form submits it (CRLF, fenced, `### Proposal` / `### Agreements` sections) is extracted and checked; the form text mentions v2 and no longer says "one or two terms"; `CONTRIBUTING.md` documents `prism-proposal/2` and the limits.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Write** the text changes.
- [ ] **Step 4: Run** `python3 -m pytest -q -p no:cacheprovider`, `python3 scripts/generate_schema_reference.py --check`. Expected: PASS.
- [ ] **Step 5: Commit** `docs(terms): the form and CONTRIBUTING describe proposal format v2`.

### Task A3: Release v1.2.0 — STOP and ask first

- [ ] **Step 1: Ask** for an explicit go to merge, push, tag `v1.2.0`, publish the release (public).
- [ ] **Step 2: On go**: merge `--no-ff`, push, wait for CI green, `git tag -a v1.2.0`, `gh release create v1.2.0 --repo MRI-Lab-Graz/prism-specification --notes "..."`; verify the archive URL answers 200.
- [ ] **Step 3: End-to-end on the live repo** (as the owner): open one issue with a 3-file v2 proposal, confirm a draft PR with exactly those 3 files, then one with a forbidden path (`schemas/stable/x.json`), confirm the comment names it and no PR exists; close both issues, delete the bot branch.

## Part B — Studio (branch `feat/proposal-v2`, from `main`)

### Task B1: Adopt v1.2.0; share several local terms

**Files:** Run `python scripts/sync_specification.py --tag v1.2.0`; Modify `tests/test_vendored_specification.py` (tag), `src/term_proposal.py`, `src/spec_overlay.py`; Test: `tests/test_term_proposal.py`, `tests/test_spec_overlay_ops.py`.

**Interfaces:**
- Produces: `src.term_proposal.as_v2(proposal) -> dict` (v1 or v2 in, v2 out; paths `terms/<modality>/<local>.json`); `deliver_proposal` writes and links v2; `src.spec_overlay.proposal_for_local_terms(project_root, term_ids: list[str] | None = None, modality="biosample") -> dict` (`{"proposal", "issue_url", "problems", "skipped"}`: the named terms, or every local term when `None`, each with the local parent it needs; terms the official registry has since adopted are left out and listed in `skipped`; `OverlayError` for an unknown ID, for nothing to share, or above 40 files; checked against the OFFICIAL registry); `proposal_for_local_term(root, id)` stays as a one-ID wrapper without the 2-term limit.

- [ ] **Step 1: Write failing tests** (lock tag first → FAIL; `as_v2` for v1 and v2 input; `proposal_for_local_terms` for all terms with a local parent and three children, for a list, for a child of an official parent, skipping a `now-official` term, over 40, nothing local, unknown ID; the old 2-term error test becomes "a parent with 3 local children is shared as one proposal").
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Sync v1.2.0**, implement.
- [ ] **Step 4: Run** the new tests, `tests/test_check_specification_lock.py`, the full suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat(spec): share several local terms in one proposal (format v2)`.

### Task B2: Commands and page

**Files:** Modify `app/src/cli/commands/spec.py`, `app/src/cli/parser.py` (`spec propose --term ID` repeatable, `--all`, exactly one of the two), `app/src/web/blueprints/specification_contribute.py` (`/api/spec/propose` accepts `{"id"}`, `{"ids": [...]}` or `{"all": true}`), `app/templates/specifications_contribute.html` + `contribute.js` (a "Share all local metrics" button), `src/term_proposal.py` (`terms propose` output is delivered as v2); Test: `tests/test_cli_spec.py`, `tests/test_cli_terms.py`, `tests/test_specification_contribute_routes.py`, `tests/e2e/test_specification_contribute_flows.py`.

- [ ] **Step 1: Write failing tests**: `spec propose --all --out F` writes a v2 file the vendored `term_proposal.py check --file` accepts; `--term` twice; neither/both → exit 2; `skipped` reported; the route accepts the three body shapes and rejects bad ones (400); `terms propose --out` writes v2; e2e: two local metrics, *Share all* shows both in the dialog and a link.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement**, thin adapters only.
- [ ] **Step 4: Run** them and the full suite; e2e flows for the contribute page. Expected: PASS.
- [ ] **Step 5: Commit** `feat(spec): spec propose --all and Share all (proposal format v2)`.

### Task B3: Docs, checks, audit

**Files:** Modify `docs/CLI_REFERENCE.md` (`spec propose`, `terms propose` output), `docs/studio/specifications.md`, `CHANGELOG.md`, the design doc's "Proposal format v2" section (no attachments; limits).

- [ ] **Step 1: Write** the docs.
- [ ] **Step 2: Run** full suite, `python3 tests/verify_repo.py --check dual-tree-drift --no-fix` (delete its report), `python3 scripts/ci/check_specification_lock.py`, `python3 -m pytest tests/test_html_validity.py -q -p no:cacheprovider`. Expected: green.
- [ ] **Step 3: Run `/ponytail:ponytail-audit`**, apply what is worth it, re-run, ask before merging.
- [ ] **Step 4: Commit** `docs(spec): proposal format v2`.
