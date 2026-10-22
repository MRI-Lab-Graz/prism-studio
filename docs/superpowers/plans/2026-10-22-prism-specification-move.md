# prism-specification repository — move and vendoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The community schemas, their archive, the term registry and the spec pages live in a new public repo `MRI-Lab-Graz/prism-specification` (tag `v1.0.0`), and Studio carries a hash-locked copy of that tag at today's paths, refreshed only by a sync script.

**Architecture:** First make the three data-check scripts layout-independent inside Studio (tasks 1-2), then extract the files with history into a local `prism-specification` checkout and add its repo files (task 3), publish it after an explicit go (task 4), then give Studio a sync script, a lock file and a drift check and switch CI over (tasks 5-7). Everything that reads `app/schemas`, `official/library/terms` or `docs/specs` today keeps reading the same paths.

**Tech Stack:** Python stdlib (`urllib`, `tarfile`, `hashlib`, `json`), `git filter-repo` (installed), `gh` (logged in), pytest.

**Spec:** `docs/superpowers/specs/2026-10-22-prism-specification-repo-design.md`

**Not in this plan (own plans later):** `terms propose` + Share button + "Propose a metric" form/bot (design steps 4), moving the modality-proposal form/bot (step 5). Until step 5 the existing `propose-modality` bot in Studio would edit vendored files; it has never been used (0 issues) and stays as is.

## Global Constraints

- Repo: `MRI-Lab-Graz/prism-specification`, public, not announced. Licence split as BIDS: CC-BY 4.0 for `schemas/`, `terms/`, `specs/`; MIT for `scripts/`. One `LICENSE` file states the split and carries both texts (CC-BY 4.0 legal code from `https://creativecommons.org/licenses/by/4.0/legalcode.txt`).
- Layout of the new repo: `schemas/{stable,archive,v0.1,v0.2}/`, `terms/<modality>/`, `specs/*.md`, `scripts/`, `tests/`, `.github/`.
- Moves: community schemas survey, biometrics, biosample, environment, events, eyetracking, physio, entities, dataset_description (all version folders), the archive, `official/library/terms/`, `docs/specs/*.md` except `project.md`, the three scripts with their tests.
- Stays in Studio (`STUDIO_OWNED`): `project`, `recipe.survey`, `tool-limesurvey`, `instrument-registry` schemas in every version folder, `docs/specs/project.md`, `app/schemas/README.md`, `app/schemas/citation_cff/`.
- Studio path mapping (spec → Studio): `schemas/` → `app/schemas/`, `terms/` → `official/library/terms/`, `specs/` → `docs/specs/`, `scripts/` → `scripts/specification/`, `LICENSE` → `app/schemas/PRISM_SPECIFICATION_LICENSE`. Nothing else is copied (not `tests/`, not `.github/`).
- In vendored `specs/*.md` the sync rewrites `](../schemas/` to `](../../app/schemas/`; that is the only content change.
- Lock file `specification.lock.json` at Studio's root: `{"repository": "MRI-Lab-Graz/prism-specification", "tag": "...", "files": {"<studio path>": "<sha256>"}}`. Hashes are over the bytes with `\r\n` normalised to `\n` (Windows checkouts).
- Downloads only from `https://github.com/MRI-Lab-Graz/prism-specification/archive/refs/tags/<tag>.tar.gz`; tar members must be regular files with relative paths and no `..`.
- No submodule, no new runtime dependency, nothing in Studio needs network except `sync_specification.py`.
- Creating and pushing the public repo is **outward-facing: stop and ask before Task 4**.
- TDD per repo rules (failing test first, watch it fail). Commits end with the attribution line from the session.

## Review Focus

- **Hostile or odd archive members** (absolute path, `..`, symlink, a top folder other than `prism-specification-<tag>/`): sync refuses and writes nothing. Pinned in Task 5.
- **Studio-owned files in shared folders** (`app/schemas/stable/project.schema.json`, `docs/specs/project.md`): sync never overwrites or deletes them; drift check never flags them. Pinned in Tasks 5 and 6.
- **Re-running the sync with the same tag** changes nothing (byte-identical files, identical lock). Pinned in Task 5.
- **A file dropped from the specification in a new tag** is removed from Studio only if the old lock listed it. Pinned in Task 5.
- **Windows line endings**: a CRLF checkout of a vendored file still passes the drift check. Pinned in Task 6.

---

### Task 1: Field-table generator takes its paths as arguments (Studio)

**Files:**
- Modify: `scripts/generate_schema_reference.py`
- Test: `tests/test_schema_docs_in_sync.py`

**Interfaces:**
- Produces: `main(argv: list[str] | None = None) -> int` with options `--schemas DIR`, `--specs DIR`, `--link-prefix STR`, `--label-prefix STR`, `--page NAME=FILE` (repeatable; replaces `PAGES` when given), `--check` (exit 1 and print the stale pages instead of writing). Defaults reproduce today's Studio output exactly (`app/schemas/stable`, `docs/specs`, `../../app/schemas/stable/`, `app/schemas/stable/`, the current `PAGES`).

- [ ] **Step 1: Write failing tests**: `test_default_run_is_byte_identical` (run `main(["--check"])` → 0 on the current tree), `test_custom_layout` (tmp `schemas/stable/x.schema.json` + `specs/x.md` with the BEGIN/END markers, `main(["--schemas", ..., "--specs", ..., "--link-prefix", "../schemas/stable/", "--label-prefix", "schemas/stable/", "--page", "x=x.md"])` → the page contains `](../schemas/stable/x.schema.json)` and `` `schemas/stable/x.schema.json` ``), `test_check_reports_stale_page` (edit a generated row → `--check` returns 1).
- [ ] **Step 2: Run** `python3 -m pytest tests/test_schema_docs_in_sync.py -q -p no:cacheprovider`. Expected: FAIL (no `main(argv)` / options).
- [ ] **Step 3: Implement** with `argparse`; keep the table code untouched.
- [ ] **Step 4: Run** the same command and `python3 scripts/generate_schema_reference.py` (expect `changed: none`). Expected: PASS.
- [ ] **Step 5: Commit** `refactor(specs): schema reference generator takes its paths as arguments`.

### Task 2: Registry check becomes a standalone script (Studio)

**Files:**
- Create: `scripts/check_terms.py`, `tests/test_check_terms.py`
- Modify: `src/term_registry.py` (remove `check_registry`, `_specimen_types`, `_SCHEMA`, `_LOINC`, `_STATUSES`, `ID_PREFIXES`, `_SLUG` if unused), `tests/test_term_registry.py` (remove the `check_registry` tests, keep loader/resolver tests)

**Interfaces:**
- Produces: `check_registry(registry: dict[str, dict], specimen_types: list[str]) -> list[str]` (same rules and messages as today; the enum is passed in), `load_terms(folder: Path) -> dict[str, dict]` (stem → parsed JSON; an unreadable file is reported as a problem, not skipped), `main(argv) -> int` with required `--terms DIR` and `--schema FILE` (the modality schema whose `Technical.SpecimenType` enum is used); prints problems, exit 1 if any. Stdlib only, no import from `src` (it must run in the new repo). Ruling to record: the 6-line file reading is repeated in `src/term_registry.load_registry`; the two repos cannot import each other, and reading JSON files is not a rule.

- [ ] **Step 1: Move the `check_registry` tests** from `tests/test_term_registry.py` into `tests/test_check_terms.py`, loading the script with `importlib.util.spec_from_file_location` (as `tests/test_schema_docs_in_sync.py` does), passing the enum explicitly; add `test_cli_passes_on_shipped_terms` (`main(["--terms", "official/library/terms/biosample", "--schema", "app/schemas/stable/biosample.schema.json"]) == 0`) and `test_unreadable_term_file_is_a_problem`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_check_terms.py -q -p no:cacheprovider`. Expected: FAIL (script missing).
- [ ] **Step 3: Implement** `scripts/check_terms.py` by moving the code out of `src/term_registry.py`.
- [ ] **Step 4: Run** `python3 -m pytest tests/test_check_terms.py tests/test_term_registry.py tests/test_validator_biosample_terms.py tests/test_cli_terms.py tests/test_validator_manifest_closure.py -q -p no:cacheprovider`. Expected: PASS.
- [ ] **Step 5: Commit** `refactor(terms): registry check is a standalone script`.

### Task 3: Build the local prism-specification repository

**Files (new repo at `/Users/karl/work/github/prism-specification`):**
- Created by extraction: `schemas/`, `terms/`, `specs/`, `scripts/check_terms.py`, `scripts/check_schema_versions.py`, `scripts/generate_schema_reference.py`, `tests/test_check_terms.py`, `tests/test_check_schema_versions.py`, `tests/test_schema_docs_in_sync.py`
- Create: `LICENSE`, `README.md`, `CONTRIBUTING.md`, `CODEOWNERS`, `.github/pull_request_template.md`, `.github/workflows/ci.yml`
- Modify there: the three scripts' defaults and the tests' paths to the new layout; the 13 links in `specs/*.md` that point into Studio docs.

- [ ] **Step 1: Extract with history** from a fresh clone of Studio's `main`:
  `git clone --no-local <studio> <new>`; `git filter-repo` keeping exactly the moved paths (Global Constraints), then a second pass `--invert-paths` dropping every `STUDIO_OWNED` schema and `docs/specs/project.md`, then `--path-rename app/schemas/:schemas/ --path-rename official/library/terms/:terms/ --path-rename docs/specs/:specs/ --path-rename scripts/ci/check_schema_versions.py:scripts/check_schema_versions.py`. Delete every tag carried over from Studio (`git tag -l | xargs git tag -d`). Check: `git log --oneline | wc -l` > 0 and `find . -name project.schema.json` is empty.
- [ ] **Step 2: Adapt to the layout**: `check_schema_versions.py` constants → `schemas/stable/`, `schemas/archive/`, `schemas/stable/entities.schema.json`; generator defaults → `schemas/stable`, `specs`, `../schemas/stable/`, `schemas/stable/`, `PAGES` without `project`; tests' `REPO_ROOT` paths likewise. Re-run the generator (only the "Generated from" lines change). Replace the 13 relative links into Studio docs (`../CLI_REFERENCE.md`, `../ERROR_CODES.md`, `../studio/...`, `../SCHEMA_VERSIONING.md`, `../EXCEL_TEMPLATE_*.md`, `../examples/...`, `../../official/...`) with `https://prism-studio.readthedocs.io/en/latest/<page>.html[#anchor]`; for the two `.xlsx` files use `https://github.com/MRI-Lab-Graz/prism-studio/raw/main/<path>`.
- [ ] **Step 3: Repo files**: `LICENSE` (split statement + CC-BY 4.0 legal code + MIT text, copyright "PRISM contributors"); `README.md` (what it is, layout, how Studio uses tags, how to propose); `CONTRIBUTING.md` (contributions accepted under the licence split; release procedure moved from Studio's `docs/SCHEMA_VERSIONING.md` "Releasing a new modality version"; term IDs frozen once released); `CODEOWNERS` (`* @karl-koschutnig`; `schemas/stable/entities.schema.json`, `schemas/stable/dataset_description.schema.json` same owner, marked core review); PR template (what changed, synthetic example, licence agreement tick); `ci.yml` on push/PR: `pytest`, `python scripts/generate_schema_reference.py --check`, `python scripts/check_terms.py --terms terms/biosample --schema schemas/stable/biosample.schema.json`, and `check_schema_versions.py` with the same base logic as Studio's `ci.yml` job (`fetch-depth: 0`, pinned `actions/checkout` SHA copied from Studio).
- [ ] **Step 4: Verify** in the new repo: `python3 -m pytest -q -p no:cacheprovider`, `python3 scripts/generate_schema_reference.py --check`, the `check_terms.py` command above. Expected: all PASS / exit 0. `grep -rn "](\.\./\.\./\|](\.\./[A-Z]" specs` returns nothing.
- [ ] **Step 5: Commit** there `chore: repository files, layout and licence` and keep the branch `main`.

### Task 4: Publish — STOP and ask first

- [ ] **Step 1: Ask the user** for an explicit go to create the public repo and push (outward-facing).
- [ ] **Step 2: On go**: `gh repo create MRI-Lab-Graz/prism-specification --public --source <new> --push --description "PRISM specification: modality schemas, term registry, spec pages"`; `git tag -a v1.0.0 -m "prism-specification 1.0.0"`; `git push origin v1.0.0`; `gh release create v1.0.0 --repo MRI-Lab-Graz/prism-specification --notes "First release, moved from prism-studio"`.
- [ ] **Step 3: Verify**: `curl -sfIL https://github.com/MRI-Lab-Graz/prism-specification/archive/refs/tags/v1.0.0.tar.gz` → 200; the repo's CI run on `main` is green (`gh run list --repo MRI-Lab-Graz/prism-specification --limit 1`).

### Task 5: Sync script (Studio)

**Files:**
- Create: `scripts/sync_specification.py`, `tests/test_sync_specification.py`

**Interfaces:**
- Produces: `MAPPING: dict[str, str]` and `STUDIO_OWNED: frozenset[str]` (Global Constraints, Studio paths), `REPOSITORY = "MRI-Lab-Graz/prism-specification"`, `extract(archive: Path, dest: Path) -> Path` (safe extraction, returns the single top folder), `sync(source: Path, studio_root: Path, tag: str) -> dict` (writes the mapped files, rewrites the spec links, removes files listed in the previous lock that are gone, writes and returns the lock), `main(argv) -> int` with `--tag TAG` and optional `--source DIR` (a local checkout; skips the download) and `--studio-root DIR` (default: repo root).

- [ ] **Step 1: Write failing tests** with a tmp source tree in the new layout and a tmp Studio root that already holds `app/schemas/stable/project.schema.json` and `docs/specs/project.md`:
  - `test_sync_maps_files_and_writes_lock` (files at mapped paths; lock lists them with sha256; `tests/` and `.github/` not copied)
  - `test_sync_rewrites_schema_links_in_specs` (`](../schemas/stable/x` → `](../../app/schemas/stable/x`)
  - `test_sync_never_touches_studio_owned_files`
  - `test_sync_twice_is_a_no_op` (byte-identical tree and lock)
  - `test_file_dropped_upstream_is_removed_only_if_locked`
  - `test_extract_refuses_unsafe_members` (absolute path, `..`, symlink, two top folders → `ValueError`, nothing written)
  - `test_download_url_is_the_tagged_github_archive` (the URL builder returns exactly the Global Constraints URL; a tag with `/` or `..` is rejected)
- [ ] **Step 2: Run** `python3 -m pytest tests/test_sync_specification.py -q -p no:cacheprovider`. Expected: FAIL (script missing).
- [ ] **Step 3: Implement** with `urllib.request`, `tarfile` (validate every member before extracting, no `extractall` on unvalidated input), `hashlib`, `json`; write the lock with sorted keys and a trailing newline.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat(specification): sync the vendored specification from a tagged release`.

### Task 6: Drift check and CI switch (Studio)

**Files:**
- Create: `scripts/ci/check_specification_lock.py`, `tests/test_check_specification_lock.py`
- Modify: `.github/workflows/ci.yml` (job `schema-versions` → `specification-lock`, name "Vendored specification")

**Interfaces:**
- Consumes: the lock format, `MAPPING` and `STUDIO_OWNED` from `scripts/sync_specification.py` (Task 5), loaded with `importlib.util.spec_from_file_location`; the vendored folders are the folders of the `MAPPING` targets.
- Produces: `check(studio_root: Path, lock: dict) -> list[str]` (a locked file missing or with a different normalised hash; a file inside a vendored folder that is neither locked nor `STUDIO_OWNED`), `main(argv) -> int`.

- [ ] **Step 1: Write failing tests**: `test_clean_tree_passes`, `test_edited_vendored_file_fails` (message names the file and says "edit it in prism-specification, then sync"), `test_missing_file_fails`, `test_extra_file_in_vendored_folder_fails`, `test_studio_owned_files_are_allowed`, `test_crlf_checkout_passes`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_check_specification_lock.py -q -p no:cacheprovider`. Expected: FAIL.
- [ ] **Step 3: Implement**; replace the `schema-versions` job in `ci.yml` with one running `python3 scripts/ci/check_specification_lock.py` on push and PR (no `fetch-depth: 0` needed).
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat(specification): drift check for the vendored copy replaces the schema-version job`.

### Task 7: Studio adopts v1.0.0

**Files:**
- Run: `python3 scripts/sync_specification.py --tag v1.0.0` (creates `specification.lock.json`, `scripts/specification/`, `app/schemas/PRISM_SPECIFICATION_LICENSE`, rewrites the vendored files)
- Delete: `scripts/check_terms.py`, `scripts/ci/check_schema_versions.py`, `scripts/generate_schema_reference.py`, `tests/test_check_schema_versions.py`
- Modify: `tests/test_check_terms.py` (keep only `test_cli_passes_on_shipped_terms`, pointing at `scripts/specification/check_terms.py`; the rule tests live in prism-specification), `tests/test_schema_docs_in_sync.py` (keep only one test: `scripts/specification/generate_schema_reference.py --check --schemas app/schemas/stable --specs docs/specs --link-prefix ../../app/schemas/stable/ --label-prefix app/schemas/stable/ --page project=project.md` exits 0; the generator's unit tests live in prism-specification), `docs/SCHEMA_VERSIONING.md` (release procedure now in prism-specification), `CLAUDE.md` (short section: the specification is vendored, edit it in prism-specification, then sync; never edit the copy), `CHANGELOG.md`, `scripts/build_validator_wheel.py` / `PrismStudio.spec` only if a test shows a path changed

- [ ] **Step 1: Write the failing test** `tests/test_vendored_specification.py::test_lock_matches_tree_and_v1` (lock `tag == "v1.0.0"` and `check_specification_lock.check(...) == []`). Run it. Expected: FAIL (no lock yet).
- [ ] **Step 2: Sync** with the command above. Expected: `git diff app/schemas official/library/terms` is empty apart from the new licence file; `git diff docs/specs` shows only the 13 links that became absolute URLs and the "Generated from" labels (`schemas/stable/...`); `docs/specs/project.md` is unchanged.
- [ ] **Step 3: Delete and adapt** the files listed above.
- [ ] **Step 4: Run** the full suite `python3 -m pytest tests -q -p no:cacheprovider --ignore=tests/e2e`, `python3 scripts/ci/check_specification_lock.py`, `python3 tests/verify_repo.py --check dual-tree-drift --no-fix`. Expected: all green, same pass count minus the moved tests plus the new ones.
- [ ] **Step 5: Commit** `feat(specification): Studio carries prism-specification v1.0.0`, then run `/ponytail:ponytail-audit` on the branch (repo rule), apply what is worth it, re-run the suite, and ask before merging.
