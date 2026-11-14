# The mappings layer and the two clear templates: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax. **Every subagent runs on Sonnet 5.5 (`claude-sonnet-5-5`), set explicitly; no other model without the user's approval (CLAUDE.md, PR #245).** Implementers never push, merge or tag; the controller does that with the user's go-ahead.

**Goal:** (1) take the unused in-schema meaning fields out of the six modality schemas again; (2) move only the two clearly redistributable instrument templates (`dass`, `dass21`, English only) and their recipes into prism-specification, with their licence evidence; (3) add `mappings/` (links from PRISM IDs to external vocabularies, direction, value rules) with one check, starting with biosample and environment, and move the biosample `TermURL` links into it; (4) Studio syncs and reads links from `mappings/`.

**Architecture:** prism-specification gets two new top-level folders, `library/` (templates, with their own notice, outside the CC BY 4.0 grant) and `mappings/`; the sync script maps `library/survey/` to Studio's `official/library/survey/` (it only touches files its lock lists, so Studio's other templates stay untouched) and `mappings/` to `official/library/mappings/`. Meaning is only in `mappings/`; sidecars, templates, schemas and term files carry identity only.

**Tech Stack:** Python 3 stdlib scripts, JSON, pytest, git. Repositories: prism-specification (Tasks 1 to 5), prism-studio (Tasks 6 and 7).

**Spec:** `docs/superpowers/specs/2026-11-14-mappings-layer-design.md` and `docs/superpowers/specs/2026-11-14-template-licensing-decision.md`. They replace steps B to D of `2026-11-14-reasoning-foundation-design.md`.

## Global Constraints

- "Data and sidecars carry IDs only; the meaning is a separate file that reads the IDs." No ontology link in a schema, sidecar, template or term file.
- "PRISM does not keep its own symptom or construct concepts; links go to external vocabularies." No concept registry (plan C and PR #249 are dropped).
- Field names (agreed 2026-11-14): `SameAs`, `Measures`, `ValueRules`, `Levels`; folder `mappings/`. Project mappings are NOT part of this plan.
- "Instrument templates ship only where PRISM is 100% sure it may redistribute them." Only `dass` and `dass21` move. **Nothing else is copied into prism-specification.** The other templates are **dropped from Studio** (user decision 2026-11-14, late): a verified copy is kept in an untracked local folder, `/Volumes/Evo/work/prism-local-library/` (shape of `official/`: `library/survey`, `recipe/survey`), which Studio reads through its `globalLibraryRoot` setting. Dropping them is Task 8, a plan of its own; until it is merged the templates stay tracked.
- The moved templates are **English only** (the German wording is not ours to ship; DASS terms require translations to be public domain and posted on the DASS site), carry the rights holder's statement verbatim with the source URL and retrieval date, and carry the DASS conditions (no modification, no sale for profit, no administration on websites open to the public). Source of the quotes: `docs/handouts/template-licence-evidence-2026-11-14.md` (executors get its text in the dispatch; it is not committed).
- Released IDs are frozen: every released `prism:dass.*` and `prism:dass21.*` ID stays exactly as it is; a test compares the IDs derived from the moved templates with `term-ids.txt`.
- Spec releases and schema versions bump the **patch** version (user's rule). Tags and merges only with the user's go-ahead.
- No real ontology code is written by an implementer: the eight existing SNOMED links are moved unchanged; test data use clearly marked placeholders.
- Stdlib-only scripts (vendored into Studio). THE RULE in Studio: logic once, CLI first, Studio only triggers. TDD for every task.

## Review Focus

1. Removing the in-schema fields leaves every schema exactly as it was before v1.5.6 plus the slim-survey change, except version and `$id` (Task 1).
2. A mapping that refers to an ID nobody released, to a vocabulary nobody listed, or with a wrong type is refused with a message, never a crash (Task 4).
3. The vendored mix: the two moved templates are locked in Studio, all other files of `official/library/survey/` are untouched by the sync (Task 6).
4. Studio shows no regression where `terms show` read `TermURL` from term files (Task 7).
5. No German text and no third-party wording other than the two DASS English templates enters prism-specification (Task 3).

## File Structure

prism-specification:
- Remove: `scripts/meaning_block.py`, `schemas/shared/`, `specs/meaning.md`, `tests/test_meaning_block.py`, the meaning-block rule in `scripts/check_modalities.py` and its tests, the meaning paragraphs of `CONTRIBUTING.md`.
- Modify: the six `schemas/stable/*.schema.json` (new patch version, block removed), `schemas/archive/<m>/…`, `specs/<m>.md` (regenerated).
- Create: `library/survey/survey-dass.json`, `library/survey/survey-dass21.json`, `library/NOTICE.md`, `recipes/survey/recipe-dass.json`, `recipes/survey/recipe-dass21.json`, `mappings/vocabularies.json`, `mappings/biosample/*.json`, `scripts/check_mappings.py`, `specs/mappings.md`, tests.
- Modify: `LICENSE` (the CC BY 4.0 grant excludes `library/`), `scripts/check_terms.py` (no `TermURL`; the vocabulary patterns move to `mappings/vocabularies.json`), `terms/biosample/*.json` (`TermURL` removed), `.github/workflows/ci.yml`.

prism-studio:
- Modify: `scripts/sync_specification.py` (mapping gains `library/survey/`, `recipes/survey/`, `mappings/`), `src/term_registry.py`, `app/src/cli/commands/terms.py`, docs, tests.
- Vendored by the sync: `official/library/survey/survey-dass*.json`, `official/recipe/survey/recipe-dass*.json`, `official/library/mappings/`, `scripts/specification/check_mappings.py`.

---

### Task 1: Take the in-schema meaning fields out again (prism-specification)

**Files:** the removal list above; new archive copies; regenerated pages.
**Interfaces:** Produces for the six schemas the versions biometrics 1.1.3, biosample 1.1.2, environment 2.1.2, events 1.1.2, physio 1.2.2, survey 2.1.3, each **equal in content to the version before the block was added** (biometrics 1.1.1, biosample 1.1.0, environment 2.1.0, events 1.1.0, physio 1.2.0, survey 2.1.1) except `version` and `$id`; the versions that carry the block stay archived (`schemas/archive/<m>/<block version>.schema.json`).

- [ ] **Step 1: Write the failing tests** (`tests/test_schema_versions_after_removal.py`): for each modality, the stable schema equals, ignoring `version` and `$id`, the archived pre-block schema; the stable schema contains none of `IsAbout`, `LevelIsAbout`, `ValueMappings` and has `TermURL` as in the pre-block schema; the stable `version` and `$id` suffix are the versions above; the archive of the block version equals what the stable file was before this task (compare with `git show origin/main:schemas/stable/<m>.schema.json`); `scripts/meaning_block.py` and `schemas/shared/` do not exist.
- [ ] **Step 2: Run to verify failure.** Expected: FAIL.
- [ ] **Step 3: Implement** with a throw-away script (not committed): for each modality copy the current stable file to `schemas/archive/<m>/<current version>.schema.json` unchanged, then write the stable file as the bytes of the pre-block archive file with only the `version` and `$id` lines changed (text edit). Delete the removal list; remove the rule from `check_modalities.py` and its tests; remove the meaning paragraphs of `CONTRIBUTING.md` (keep "Within a major version a schema only adds optional things"); regenerate the pages (`python scripts/generate_schema_reference.py`). Keep `release_patch._span` array support (harmless, tested).
- [ ] **Step 4: Run** `python -m pytest tests -q -p no:cacheprovider && python scripts/check_modalities.py && python scripts/check_schema_versions.py origin/main HEAD && python scripts/generate_schema_reference.py --check`. Expected: PASS, checks print nothing.
- [ ] **Step 5: Commit** one commit per modality for the schema (`fix(<modality>): the meaning fields are removed again (schema <new>, <old> archived)`) and one for the removals (`chore: remove meaning_block.py, schemas/shared and the meaning page`). Every message ends with the Sonnet 5.5 trailer.

### Task 2: Library folder, licence carve-out, recipes (prism-specification)

**Files:** `library/NOTICE.md`, `LICENSE`, `recipes/survey/recipe-dass.json`, `recipes/survey/recipe-dass21.json`, `.github/workflows/ci.yml`; tests.
**Interfaces:** Produces `library/` (templates, third-party terms, **not** CC BY 4.0) and `recipes/` (ours, CC BY 4.0).

- [ ] **Step 1: Write the failing tests:** `LICENSE` says the CC BY 4.0 grant covers `schemas/`, `terms/`, `specs/`, `recipes/`, `mappings/` and expressly excludes `library/`; `library/NOTICE.md` exists and names the rule ("only templates whose redistribution is verified"), the evidence requirement and the contact policy ("if you hold rights to an instrument and want it removed, write to ..."; the executor leaves the address as the placeholder `<contact address to be set by the maintainers>`); every file under `library/survey/` has `Study.LicenseID` ≠ empty, a `Study.License` with a verbatim rights-holder statement, `Study.Source`, and a retrieval date field `Study.LicenseChecked` (see Task 3); `recipes/survey/recipe-*.json` validate against the recipe schema of Studio as far as the specification can check them (use the structure test of `tests/test_recipe_value_meaning.py` in Studio only as a model: here a plain JSON check of required keys `RecipeVersion` ("x.y"), `Kind`, `Survey.TaskName`, `Scores`).
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement.** Copy the two recipes from Studio's `official/recipe/survey/`; set `RecipeVersion` to the major.minor form if needed; copy nothing else. Write `LICENSE` change and `library/NOTICE.md` (plain words; mention that PRISM grants no rights to the instruments). Add a CI step that runs the library evidence check of Task 3.
- [ ] **Step 4: Run** the whole suite and `python scripts/check_modalities.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(library): library/ and recipes/ folders, the licence carve-out and the notice`.

### Task 3: The two templates, English only, with their evidence

**Files:** `library/survey/survey-dass.json`, `library/survey/survey-dass21.json`, `scripts/check_library.py`, `tests/test_check_library.py`.
**Interfaces:** Produces `check_library.py [--repo DIR]`: every template under `library/survey/` must have (a) `Study.License` containing a quoted rights-holder statement, (b) `Study.Source` as an absolute https URL, (c) `Study.LicenseChecked` as `YYYY-MM-DD`, (d) `Study.LicenseTerms` as a list of short condition strings, (e) only `en` text (no other language key in any `Description`, `Levels`, `Instructions`, `OriginalName`), (f) no `Study.ItemCount`, `Study.Subscales` or item `Reversed`; exits 1 with one line per problem.

- [ ] **Step 1: Write the failing tests** for each rule of `check_library.py` (a template that breaks it is refused with a message naming the file) and for the two real templates: derived IDs equal the released IDs of `prism:dass.*` and `prism:dass21.*` in Studio's `term-ids.txt` (the executor receives the exact ID list in the dispatch; compare as sets, order free).
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement.** Create the two templates from Studio's `official/library/survey/survey-dass.json` and `survey-dass21.json` by a one-off script: keep only `en`; drop `ItemCount` and every `Reversed`; set `Study.License` to the rights holder's verbatim statements quoted in the evidence file (DASS: "The DASS questionnaire is in the public domain, and may be downloaded from this website." and "The DASS questionnaire forms may be downloaded and copied without restriction."; DASS-21: the same download statement, which lists the DASS-21 form); `Study.Source` = https://www2.psy.unsw.edu.au/dass/ ; `Study.LicenseChecked` = 2026-11-14; `Study.LicenseTerms` = ["The scales may not be modified or sold for profit.", "Administering the DASS on a website or app open to members of the public is not permitted; use with defined groups such as research participants is.", "Please cite the DASS website: www.psy.unsw.edu.au/dass"] (the executor copies these strings exactly); keep the item keys unchanged (the IDs derive from them). Write `check_library.py` (stdlib).
- [ ] **Step 4: Run** the new tests and the whole suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat(library): dass and dass21 (English only) with their licence evidence, and the library check`.

### Task 4: The mappings layer (prism-specification)

**Files:** `mappings/vocabularies.json`, `scripts/check_mappings.py`, `specs/mappings.md`, `CONTRIBUTING.md`, `.github/workflows/ci.yml`, tests.
**Interfaces:** Produces `check_mappings.py [--repo DIR] [--mappings DIR]` and the format of the design (section 2): files `mappings/<modality>/<family>.json`, keys = full PRISM IDs of that family, fields `SameAs` (`{vocabulary: URL}`), `Measures` (list of `{URL (required), Match (exact|broader|narrower|related), Higher (more|less), Source, Checked (YYYY-MM-DD), Status (reviewed|unreviewed)}`), `ValueRules` (list of `{Name (slug), Source, Rules: [{When: {Op (==,!=,>=,>,<=,<,in), Value}, State (slug)}]}`), `Levels` (`{level code: {Measures, ValueRules}}`). Checks: the key exists as a released ID (term registries under `terms/`, item and score IDs derived from `library/` and `recipes/` by the derivation function of Task 4 step 3); the file's family matches its name; every vocabulary name is in `mappings/vocabularies.json`; every URL matches the pattern of its vocabulary; `Levels` codes exist in the ID's definition (the term's or template's `Levels`); wrong types are messages; no ID in two files; a specimen child inherits its analyte's links (no check needed).

- [ ] **Step 1: Write the failing tests** (`tests/test_check_mappings.py`) with tmp repositories: a valid file passes; each refusal above is a test; the patterns of the four existing vocabularies are loaded from `mappings/vocabularies.json`, not from code; `check_terms.py --all` no longer accepts a `TermURL` key in a term (new rule: "links belong in mappings/").
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement.** (a) `mappings/vocabularies.json`: the four patterns of `check_terms._TERMURL` (`snomed`, `loinc`, `chebi`, `ncit`) as data `{name: {"pattern": regex, "label": ...}}`. (b) The survey ID derivation: copy the pure functions `item_local_id`, `score_local_id` and the template/recipe walk from Studio's `src/survey_terms.py` into `scripts/survey_ids.py` (stdlib only: replace the import of the non-item key list by the same constant written out; keep the behaviour identical and prove it by a test that runs both on the two templates). (c) `check_mappings.py`. (d) Move the eight `TermURL` objects out of `terms/biosample/*.json` (`estradiol`, `progesterone`, `testosterone`, `free-testosterone`, `lh`, `fsh`, `prolactin`, `shbg`) **unchanged** into `mappings/biosample/<analyte>.json` as `{"prism:<analyte>": {"SameAs": {...}}}`; remove `TermURL` from those term files and from `check_terms.py` (its LOINC agreement check stays, comparing the `LOINC` field with a `loinc` link now found in `mappings/`, if one exists). (e) `specs/mappings.md` (plain words: the layer, the four fields, the rules, what a mapping file looks like with placeholder URLs, who reviews links) and a "Adding a mapping" section in `CONTRIBUTING.md`. (f) CI steps `python scripts/check_mappings.py` and `python scripts/check_library.py`.
- [ ] **Step 4: Run** the whole suite and every check script: `python scripts/check_terms.py --all && python scripts/check_mappings.py && python scripts/check_library.py && python scripts/check_modalities.py && python scripts/check_schema_versions.py origin/main HEAD && python scripts/generate_schema_reference.py --check`. Expected: PASS, no output from the checks.
- [ ] **Step 5: Commit** in three commits: `feat(mappings): the mappings layer and its check`, `refactor(terms): the SNOMED links of the biosample terms moved to mappings/ unchanged`, `docs(mappings): the mappings page and the rules`.

### Task 5: Release (with the user's go-ahead)

- [ ] **Step 1:** run every check of Task 4 Step 4 plus `python -m pytest tests -q -p no:cacheprovider`. Whole-branch review on Sonnet 5.5, ponytail audit, push, pull request, merge when CI is green. **Tag the next patch version only with the user's confirmation.** The pull request description states plainly that this adds two third-party templates under their own licence terms and a licence carve-out.

### Task 6: Studio syncs the new tag

**Files:** `scripts/sync_specification.py` (MAPPING gains `"library/survey/": "official/library/survey/"`, `"recipes/survey/": "official/recipe/survey/"`, `"mappings/": "official/library/mappings/"`, and the `library/NOTICE.md` goes to `official/library/NOTICE_SPECIFICATION.md`), `specification.lock.json` (by the script), tests.
**Interfaces:** Consumes the tag from Task 5. Produces the vendored files listed under File Structure.

- [ ] **Step 1: Write the failing tests:** the sync test (extend `tests/test_sync_specification*.py`, find it) with a fake release tree that has `library/survey/survey-x.json`, `recipes/survey/recipe-x.json`, `mappings/biosample/a.json`: the files land at the Studio paths and in the lock; **a file `official/library/survey/survey-other.json` that is not in the lock is untouched** (written before the sync, same bytes and mtime after); a file listed in the old lock and absent from the new release is deleted only inside the mapped prefixes; the pin test for the new tag.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** the mapping change and sync (`python scripts/sync_specification.py --tag <tag>`); close PR #250 (superseded) and carry over its still-valid fixes by cherry-pick: the biosample importer test and example template following the current schema version, the physio-archive test fix, the `archive/` guard, the docs table-of-contents test (without the meaning page). Studio's `official/library/survey/survey-dass*.json` and `official/recipe/survey/recipe-dass*.json` now come from the lock; their Studio-only edits (German text) are gone by design: re-check that no Studio test or doc depends on the German DASS wording.
- [ ] **Step 4: Run** the wide set used before (survey, recipe, term, vendored, specification, template, cli, validation, version, schema, issues, runner, modality, biosample, environment, biometrics, physio, events, converter, library, participants) and the JavaScript tests. Fix every failure test first.
- [ ] **Step 5: Commit** and open the pull request; merge when green and with the user's go-ahead.

### Task 7: Studio reads links from `mappings/`

**Files:** `src/term_registry.py` (`term_links`), `app/src/cli/commands/terms.py`, `docs/CLI_REFERENCE.md`, tests.
**Interfaces:** `term_links(registry, term)` keeps its signature and result shape `{system: {"url", "from"}}`, but takes the links from `official/library/mappings/<modality>/*.json` (`SameAs`), with the parent's links inherited and `from` naming the ID that carries them; `terms show` additionally prints `Measures` and `ValueRules` of an ID when present.

- [ ] **Step 1: Write the failing tests** with a tmp mappings folder: a child inherits the analyte's `SameAs` with origin; a term without mappings has no links; a mapping file with a wrong type is skipped without a crash; `terms show --json` carries `links`, `measures`, `value_rules`.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** a small reader (`load_mappings(modality)`) next to `load_registry`; keep the output of `terms show` for the eight biosample analytes identical to before (a regression test compares the old `links` result with the new one for every analyte that had a `TermURL`).
- [ ] **Step 4: Run** `python -m pytest tests/test_term_registry.py tests/test_cli_terms.py -q -p no:cacheprovider` and the wide set. Expected: PASS.
- [ ] **Step 5: Commit** `feat(terms): terms show reads links from mappings/`; pull request; merge when green and with the user's go-ahead.

---

### Task 8 (its own plan, written after Task 6 is merged): Studio drops the third-party templates

Scope, measured on 14 November 2026 on `origin/main`: 103 survey templates, 104 recipes, `index.json`, `term-ids.txt` and `NOTICE.md` under `official/library/survey`, `official/recipe/survey`; 44 test files touch the library or recipe path, 55 name specific instruments, 33 source files read the library, 10 docs mention instruments. Done already: the local copy (`/Volumes/Evo/work/prism-local-library/`, 210 files, byte-identical to `origin/main`, checksum list kept in `/tmp/local-lib.sha`).

What the plan must settle (each is a decision or a test-first change, none is done yet):
1. **Order, safe:** (a) point Studio's `globalLibraryRoot` (the user's local settings, not tracked) at `/Volumes/Evo/work/prism-local-library/official`; (b) write our own demo template and demo recipe (made-up questionnaire, no third-party wording); (c) rewrite the tests, docs and screenshots that name specific instruments around the demo and the two DASS templates, test first; (d) only then `git rm` the templates and recipes; (e) release notes that say the library was reduced, why, and how a lab keeps its own library (the global library folder).
2. **Frozen IDs:** `term-ids.txt` stays in Studio (identifiers only) so released IDs are never lost; the survey registry (`src/survey_terms.py`, `terms list|show --modality survey`) must read the **effective** library paths (global root plus vendored), not only `official/library/survey`, and the freeze check must run where the templates are present (the local library) and not fail where they are absent.
3. **Recipes:** the 100 recipes go with their templates (they only make sense with them); the two DASS recipes stay (vendored).
4. **Instrument registry index (`index.json`)** is generated from the templates present; it is regenerated for what remains and ignored for the local library.
5. **What cannot be undone:** the files stay in git history and in published releases; whether to withdraw published releases is the user's decision, outside this plan.
6. **Users:** projects keep their own template copies; users who want the old library point `globalLibraryRoot` at a folder like the local one; the notice policy of the background preparation (acknowledgement and citation) applies to any template from a global library.

## Background preparation (not tasks of this plan; each its own small plan, none moves a template)

A. The acknowledgement and citation notice in Studio. B. The licence evidence rule for every shipped template (Task 3's check is its first form). C. The rights-holder contact policy text. D. Drafts of the letters (PsyToolkit, DASS contact, PHQ screeners, authors) for the user to send. E. A design for wording-free instrument skeletons, for legal review.

## Self-Review

- **Spec coverage:** design sections 1 to 8: layout and removal (Task 1, 2), the mapping file and fields (Task 4), vocabularies as data (Task 4), the check (Task 4), the library move and the licence carve-out (Tasks 2, 3, 6), how Studio uses it (Task 7), the order of work (the task order); project mappings are out by decision; the calls made after the builder check are applied: biometrics left out of mappings, children inherit, forward-only version bumps, Studio vendoring paths.
- **Rulings made here (the user may overrule):** the released-ID list `term-ids.txt` stays in Studio (identifiers of the unshipped instruments are not copied into the specification now; survey mappings for the unshipped instruments wait until that question is settled; the spec repo's check can only validate survey keys of the shipped templates); the derivation functions are copied into `scripts/survey_ids.py` and Studio keeps its own `src/survey_terms.py` until a later cleanup (a test keeps them equal on the two templates; two copies for now is a known cost, noted for the cleanup); `LicenseChecked` and `LicenseTerms` are new optional `Study` fields of the survey templates, **not** in the survey schema (the schema is open for extra `Study` keys; adding them to the schema is a later decision); the demo templates of our own are not part of this plan.
- **Names:** `check_mappings.py`, `check_library.py`, `survey_ids.py`, `load_mappings`, the folder names and the new versions are the same in every task.
- **Proportion:** seven tasks over two repositories; the layer and the first move are small, the preparation items are separate.
