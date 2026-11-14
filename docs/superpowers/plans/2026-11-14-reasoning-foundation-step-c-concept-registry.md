# Reasoning foundation, step C: the concept registry

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Every subagent runs on Sonnet 5.5 (`claude-sonnet-5-5`), set explicitly; no other model without the user's approval (CLAUDE.md).**

**Goal:** PRISM owns a registry of concepts (fatigue, loss of energy, serum cortisol level, ...): one JSON file per concept with a frozen `prism:` ID, a kind, a label, optional links to external vocabularies and an optional same-kind parent, checked by a script, and readable in Studio with `terms list|show --modality concept`.

**Architecture:** A new top-level folder `concepts/` in prism-specification (not under `terms/`: concepts are not a data modality and `entities.schema.json` describes data modalities). A new stdlib-only script `scripts/check_concepts.py` reuses the helpers of `scripts/check_terms.py` (by path, as the other scripts do). The existing `prism:<id>` expansion and the "one ID names one concept" rule are extended to cover concepts. Studio vendors the folder with the sync script and reads it with the existing registry functions.

**Tech Stack:** Python 3 stdlib (scripts), pytest, git. Repositories: prism-specification (Tasks 1 to 4), prism-studio (Tasks 5 and 6). The proposal route (issue form and bot) is its own plan after this one (see the end).

**Spec:** `docs/superpowers/specs/2026-11-14-reasoning-foundation-design.md` (section 3 "The concept registry", the decisions "PRISM owns the concept registry" and "calls made after the builder check" item 3).

## Global Constraints

- "A concept is an idea (fatigue, loss of energy, serum cortisol level) with a `prism:` ID, a label, optional `TermURL` links to external vocabularies, optional `Parent`, and `Status`. The proposal route, the frozen-ID rule and the cross-registry uniqueness check of terms apply unchanged."
- "The kind enumeration (substance, specimen, observable, finding, scale, construct) is fixed in the specification and checked by the registry check script plus maintainer review; a new kind is a specification change. A concept's `Parent` must be of the same kind."
- "An ID is frozen once released" (CONTRIBUTING). A released concept is never deleted or renamed; it is deprecated with `ReplacedBy`.
- "Ontology codes nobody looked up" are an anti-goal: no real external code is written into any file by the implementer; tests use synthetic examples that are clearly marked.
- PRISM is agnostic about content: this step ships the mechanism and **no seed concepts** in the real `concepts/` folder (content arrives by proposal, from partners and by the user).
- The `prism:` namespace: `prism:<local>` expands to `https://w3id.org/prism-specification/terms/<modality>/<local>` for terms; concepts expand to `https://w3id.org/prism-specification/concepts/<local>`.
- Stdlib-only scripts (vendored into prism-studio's `scripts/specification/`); the vendored copy must work in Studio's folder layout (no path relative to the repository root that Studio lacks: take the repository root as an argument with a default, like `check_terms.py --repo`).
- Spec releases bump the PATCH version (user's rule); no schema changes in this step, so no schema bump at all. Tags and merges only with the user's go-ahead.
- THE RULE (Studio): logic once in `src/`/scripts, exposed by `prism_tools.py`; Studio only triggers.
- TDD for every task.

## Review Focus

1. A concept file with a wrong type (a list as `Label`, a string as `TermURL`, a number as `Kind`) gives a message, never a crash (Task 1).
2. A `Parent` of another kind, a missing parent, and a parent cycle are refused; a deprecated concept needs an existing `ReplacedBy` (Task 1).
3. A concept ID equal to a term ID of any modality is refused, in both directions, by `check_terms.py --all` and by `check_concepts.py` (Task 2).
4. Frozen IDs: deleting or renaming a concept file (or changing its `TermID`) relative to a base ref fails the check; adding is fine (Task 2).
5. The vendored copy: `check_concepts.py --repo <dir>` works on a directory that has only `concepts/` and `schemas/stable/entities.schema.json` (Studio's layout is `official/library/concepts`; the script takes the concepts folder as an argument too) (Task 1, Task 5).

## File Structure

prism-specification:
- Create `concepts/` (empty folder with a `README.md` that says how to propose; no seed concepts).
- Create `scripts/check_concepts.py`.
- Modify `scripts/check_terms.py`: `cross_registry_problems` also receives the concepts; `expand()` finds concepts; `main --all` loads them.
- Modify `.github/workflows/ci.yml`: a "Concepts" step.
- Create `specs/concepts.md`; modify `CONTRIBUTING.md`.
- Tests: `tests/test_check_concepts.py` (new), `tests/test_check_terms.py` (extended).

prism-studio:
- Modify `scripts/sync_specification.py` (and its lock handling) to vendor `concepts/` to `official/library/concepts/`.
- Modify `src/term_registry.py`: `load_registry("concept")` reads the concepts folder; `app/src/cli/commands/terms.py` and the parser accept `--modality concept`.
- Vendored: `scripts/specification/check_concepts.py`, `official/library/concepts/`, `specification.lock.json`.
- Tests: `tests/test_term_registry.py`, `tests/test_cli_terms.py`, `tests/test_vendored_specification.py`.

## The concept file (pinned)

`concepts/<local-id>.json`, `<local-id>` matches `^[a-z][a-z0-9-]{0,62}$` (one segment; a qualification is a child concept with a `Parent`, not a dotted ID):

```json
{
  "TermID": "prism:<local-id>",
  "Level": "concept",
  "Kind": "substance | specimen | observable | finding | scale | construct",
  "Label": "short name, lower case unless a proper name",
  "Description": "one or two sentences in plain words",
  "Aliases": ["other names"],
  "Parent": "prism:<other-concept-of-the-same-kind>",
  "TermURL": {"snomed": "https://snomed.info/id/<digits>"},
  "Status": "official | deprecated",
  "ReplacedBy": "prism:<concept>"
}
```
Required: `TermID`, `Level`, `Kind`, `Label`, `Description`, `Status`. Optional: `Aliases`, `Parent`, `TermURL`, `ReplacedBy` (required when deprecated). `TermURL` systems and URL shapes are the `_TERMURL` table of `check_terms.py` (snomed, loinc, chebi, ncit); an unknown system is a problem (adding one is a one-line change there, by a maintainer who looked the pattern up). Names (`Label` and every alias, compared lower-case) are unique across the registry and not claimed by another concept.

---

### Task 1: The check script (prism-specification)

**Files:**
- Create: `scripts/check_concepts.py`, `concepts/README.md`
- Test: `tests/test_check_concepts.py` (new)

**Interfaces:**
- Produces (`scripts/check_concepts.py`):
  - `KINDS: tuple[str, ...] = ("substance", "specimen", "observable", "finding", "scale", "construct")`
  - `load_concepts(folder: Path) -> tuple[dict[str, dict], list[str]]`: `{file stem: parsed concept}` and problems for unreadable or non-object files (use `check_terms.load_terms` if it fits: read it first).
  - `check_concepts(registry: dict[str, dict]) -> list[str]`: every rule of the section "The concept file" plus: local part equals the file stem; prefix is `prism` only; `Level == "concept"`; `Kind` in `KINDS`; `Parent` exists, has the same `Kind`, no cycle (follow parents with a visited set); deprecated needs an existing `ReplacedBy` of the same kind; `TermURL` an object of known systems with matching patterns (reuse `check_terms._TERMURL`); wrong types reported before anything else is read (reuse the pattern of `check_terms.type_problems`; `Kind`, `ReplacedBy` and `Description` are strings).
  - `main(argv=None) -> int`: `python scripts/check_concepts.py [--concepts DIR] [--repo DIR]` (default concepts folder `<repo>/concepts`; `--repo` defaults to the script's parent folder); prints one line per problem; exit 1 when there is any; a missing folder is no problem (empty registry).
- Loads `check_terms.py` by path with a small `_sibling` helper (the pattern of `meaning_block.py`).

- [ ] **Step 1: Write the failing tests** in `tests/test_check_concepts.py` with a helper that writes concept files into `tmp_path`. One test per rule, each asserting the message names the file and the rule: valid minimal concept gives `[]`; wrong types (list `Label`, string `TermURL`, number `Kind`, string `Aliases`) give messages and no exception; `TermID` local part differs from the file name; prefix `bids:`; `Level` not `concept`; `Kind` outside the enum; missing `Label`/`Description`; parent missing; parent of another kind; parent cycle (a to b to a); deprecated without `ReplacedBy`, with a missing target, with a target of another kind; `TermURL` with an unknown system, with a snomed URL of the wrong shape, with a valid synthetic one (`https://snomed.info/id/123456` is a SYNTHETIC test value, comment it so); duplicate `Label` and a `Label` equal to another concept's alias (lower-case compare); `main(["--concepts", dir])` exit codes 0 and 1 and printed lines; a missing folder gives exit 0; the repository's own `concepts/` passes (empty).
- [ ] **Step 2: Run to verify failure.** Run: `python -m pytest tests/test_check_concepts.py -q -p no:cacheprovider`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `scripts/check_concepts.py` and write `concepts/README.md` (what a concept is, the file format in six lines, "no concepts are shipped yet; propose one" and a pointer to CONTRIBUTING).
- [ ] **Step 4: Run to verify it passes.** Run: `python -m pytest tests -q -p no:cacheprovider && python scripts/check_concepts.py`. Expected: PASS, no output from the script.
- [ ] **Step 5: Commit** `feat(concepts): the concept file format and its check`.

### Task 2: One namespace, one concept per ID, frozen IDs

**Files:**
- Modify: `scripts/check_terms.py` (`expand`, `cross_registry_problems`, `main --all`), `scripts/check_concepts.py` (`--base`/`--head`), `.github/workflows/ci.yml`
- Test: `tests/test_check_terms.py`, `tests/test_check_concepts.py`

**Interfaces:**
- Consumes: Task 1's `load_concepts`.
- Produces: `check_terms.expand(term_id, repo)` returns `https://w3id.org/prism-specification/concepts/<local>` for a concept (terms keep their URL; a local ID in both is already a problem); `check_terms.cross_registry_problems(registries)` is unchanged in signature and gets the concepts as one more registry (key `"concept"`) from `main --all` when `<repo>/concepts` exists; `check_concepts.frozen_problems(base_files: dict[str, dict], head_files: dict[str, dict]) -> list[str]` (a concept present at base and missing at head, or whose `TermID` changed, is a problem naming the fix: "deprecate it with ReplacedBy"); CLI `python scripts/check_concepts.py --base REF --head REF` reads `git show REF:concepts/<file>` for both refs (like `check_schema_versions.py`; read it for the git calls and its test style).

- [ ] **Step 1: Write the failing tests:** `expand("prism:fatigue")` for a concept in a tmp repo with `concepts/fatigue.json`; a concept whose local ID equals a biosample term ID makes `check_terms.main(["--all", "--repo", tmp])` fail with the existing "ID exists in both" wording naming `concept` and the modality; a concept ID unique across both passes; `frozen_problems` on dicts (deleted concept, changed `TermID`, added concept fine, edited `Description` fine, `Status` changed to deprecated fine); a git-based test that builds a tmp git repo with two commits (add, then delete a concept) and runs `main(["--repo", tmp, "--base", "HEAD~1", "--head", "HEAD"])` expecting exit 1.
- [ ] **Step 2: Run to verify failure** (`python -m pytest tests/test_check_terms.py tests/test_check_concepts.py -q -p no:cacheprovider`). Expected: the new tests FAIL.
- [ ] **Step 3: Implement.** In `ci.yml` add to the `checks` job a step "Concepts" running `python scripts/check_concepts.py`, and to the `schema-versions` job (it already fetches full history) a step "Concept IDs are frozen" running `python3 scripts/check_concepts.py --base "$BASE" --head HEAD` with the same `BASE` expression the existing step uses.
- [ ] **Step 4: Run to verify it passes:** `python -m pytest tests -q -p no:cacheprovider && python scripts/check_terms.py --all && python scripts/check_concepts.py && python scripts/check_concepts.py --base origin/main --head HEAD`. Expected: PASS, no output.
- [ ] **Step 5: Commit** `feat(concepts): concepts share the prism namespace and the one-ID rule; released concept IDs are frozen`.

### Task 3: The page and the rules

**Files:**
- Create: `specs/concepts.md`
- Modify: `CONTRIBUTING.md`
- Test: `tests/test_check_concepts.py` (the page documents every field and every kind)

- [ ] **Step 1: Write the failing test:** the text of `specs/concepts.md` contains each field name of the concept file and each of the six kinds in backticks, and `CONTRIBUTING.md` contains the heading "Proposing a concept".
- [ ] **Step 2: Run** it. Expected: FAIL.
- [ ] **Step 3: Write the page** in plain words: what a concept is (an idea, not a column, not a measurement); the six kinds with one plain example each (examples are generic words, not codes: substance "cortisol", specimen "saliva", observable "serum cortisol level", finding "fatigue", scale "depression questionnaire", construct "working memory"); the file format table; the ID rules (slug, frozen, deprecation with `ReplacedBy`); `Parent` same kind only; `TermURL` links only where a code was looked up by a person, and which systems are known; how a link in a sidecar refers to a concept (`IsAbout.Concept: "prism:fatigue"`, see `meaning.md`); how a concept is checked (`check_concepts.py`). In `CONTRIBUTING.md` add "Proposing a concept": until the proposal form exists (its own step), open an issue or a pull request with one file `concepts/<id>.json`; run `python scripts/check_concepts.py`; maintainers review the kind and the links. Do not describe a form or a bot that does not exist.
- [ ] **Step 4: Run** the test and `python scripts/generate_schema_reference.py --check`. Expected: PASS.
- [ ] **Step 5: Commit** `docs(concepts): the concept page and how to propose one`.

### Task 4: Whole-branch checks and release (with the user's go-ahead)

- [ ] **Step 1:** run `python -m pytest tests -q -p no:cacheprovider`, `python scripts/check_terms.py --all`, `python scripts/check_concepts.py`, `python scripts/check_modalities.py`, `python scripts/check_schema_versions.py origin/main HEAD`, `python scripts/generate_schema_reference.py --check`. Expected: all clean.
- [ ] **Step 2:** whole-branch review (Sonnet 5.5), ponytail audit, push, pull request, merge when CI is green. **Tag the next patch version only with the user's confirmation.**

### Task 5: Studio vendors the concepts (prism-studio)

**Files:**
- Modify: `scripts/sync_specification.py` (read it first: it copies the registries `terms/<modality>` to `official/library/terms/<modality>`, vendors scripts and writes the lock), `specification.lock.json` (by the script), `tests/test_vendored_specification.py` (pin), `scripts/ci/check_specification_lock.py` if it lists the vendored paths
- Create (by the sync): `official/library/concepts/`, `scripts/specification/check_concepts.py`

**Interfaces:**
- Consumes: the tag from Task 4.
- Produces: `official/library/concepts/<id>.json` for every concept of the tag (an empty folder with a `README.md` copy while none exist), and `scripts/specification/check_concepts.py`; both hash-locked.

- [ ] **Step 1: Write the failing tests:** the pin test (expected tag); a sync test (extend the existing sync tests) that a fake release tree with `concepts/a.json` ends up as `official/library/concepts/a.json` with its hash in the lock, and that `check_concepts.py` is vendored; a test that the vendored `check_concepts.py` passes on `official/library/concepts` called as `check_concepts.main(["--concepts", <that folder>])`.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement the sync change, run** `python scripts/sync_specification.py --tag <tag>` in a worktree from `origin/main`. Never edit vendored files by hand.
- [ ] **Step 4: Run** the vendored-specification tests, the dual-tree check (`python tests/verify_repo.py --check dual-tree-drift --no-fix`) and the wider test set used for earlier steps (survey, recipe, term, vendored, specification, template, cli, validation, version, schema, issues, runner). Expected: PASS; fix any failure the sync causes test-first (systematic debugging).
- [ ] **Step 5: Commit** `chore(specification): sync prism-specification <tag> (concept registry)`; pull request, merge when green.

### Task 6: Studio reads concepts (`terms list|show --modality concept`)

**Files:**
- Modify: `src/term_registry.py` (`load_registry`), `app/src/cli/commands/terms.py`, `app/src/cli/parser.py` (the `--modality` choices), `docs/CLI_REFERENCE.md`
- Test: `tests/test_term_registry.py`, `tests/test_cli_terms.py`

**Interfaces:**
- Consumes: `official/library/concepts` (Task 5).
- Produces: `src.term_registry.concepts_root() -> Path` (like `terms_root()`: dev, validator image, frozen build; `official/library/concepts`) and `load_registry("concept")` returning `{file stem: concept}`; `terms list --modality concept` and `terms show --modality concept <id|label|alias>` work and `terms show` prints the concept's links including the parent's (the existing `term_links`); `terms resolve`, `suggest`, `propose` keep their current modalities (a clear error for `concept`: "concepts are proposed through the concept proposal route").

- [ ] **Step 1: Write the failing tests:** with a tmp concepts folder (monkeypatch the root): `load_registry("concept")` returns the concept; `find_term` finds it by `prism:<id>`, local name, label and alias; `terms list --modality concept --json` lists it; `terms show` prints `Kind` and the parent's `TermURL` links with `from`; `terms suggest --modality concept` and `terms propose --modality concept` exit 1 with the stated message; the packaging includes `official/library/concepts` (check how `official/library/terms` is included in the wheel and the frozen build: `pyproject.toml` package data, `scripts/build/build_app.py`, the Dockerfile; add a test or extend the existing packaging test).
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement.** Reuse `term_registry` functions; the survey registry's `_registry(modality)` in `terms.py` shows where a modality-specific source is chosen.
- [ ] **Step 4: Run** `python -m pytest tests/test_term_registry.py tests/test_cli_terms.py tests/test_survey_terms.py -q -p no:cacheprovider` and the wider set. Expected: PASS.
- [ ] **Step 5: Commit** `feat(terms): terms list|show for the concept registry`; pull request, merge when green.

---

## Self-Review

- **Spec coverage:** "A new level of the term registry: Level: concept" (design section 3) is Task 1; "the proposal route, the frozen-ID rule and the cross-registry uniqueness check apply unchanged" are Task 2 (frozen, uniqueness) and the separate proposal-route plan; "the kind enumeration is fixed and a Parent must be of the same kind" is Task 1; "Studio registry readers" is Tasks 5 and 6; "no vocabulary content, no invented codes" is a global constraint and the synthetic markers in the tests. **Not in this plan, by design:** the proposal route (issue form, bot, `term_proposal.py` support for concept files, Studio `terms propose --modality concept`): its own plan, because it touches a privileged workflow and deserves its own review; resolving `IsAbout.Concept` targets against the registry (step D, the projection); seeding real concepts.
- **Rulings made here (the user may overrule):** the folder is `concepts/` at the repository root, not `terms/concept/` (concepts are not a data modality and `entities.schema.json` is core-reviewed); a concept ID is a single slug without a dot; no seed concepts; unknown `TermURL` systems are refused (adding one is a deliberate one-line change); the frozen rule is enforced by a git-based check in CI, since a directory listing cannot prove a deletion; Studio refuses `suggest`/`propose` for concepts until the proposal route exists; no schema is changed, so no version bumps; the tag is the user's decision.
- **Names used across tasks:** `KINDS`, `load_concepts`, `check_concepts`, `frozen_problems`, `concepts_root`, `official/library/concepts`, `scripts/specification/check_concepts.py` are the same in every task.
- **Proportion:** six tasks over two repositories for one registry type; each task is a small, separately testable deliverable.

## Outline of the next plan: the concept proposal route

`propose-concept.yml` issue form, a bot job reusing the structure of `propose-metric.yml` (untrusted check job with a read-only token, privileged report job that treats the artifact as data), `term_proposal.py` format support for `concepts/<id>.json` files (allow-list, size caps, slug rule for file names), `terms propose --modality concept` in Studio (builds the proposal from a column and its `IsAbout`), and the CONTRIBUTING text updated from "open an issue or a pull request" to the form. Needs this plan merged and released first.
