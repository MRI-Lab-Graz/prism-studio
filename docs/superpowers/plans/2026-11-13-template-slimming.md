# Template Slimming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subscales and reversal move out of the survey template into the recipe; `ItemCount` becomes derived; the vendored survey schema then drops the three fields.

**Architecture:** Phase 1 (this repo, no spec change) makes recipes carry the facts and stops reading them from templates, while old templates keep loading. Phase 2 (prism-specification repo, gated on the user) removes the fields from the vendored schema. Phase 3 (this repo) syncs the tag and deletes leftovers. All logic in `src/`; CLI first, Studio triggers.

**Tech Stack:** Python, JSON schema, Flask, vanilla JS (vitest), prism-specification sync script.

**Spec:** `docs/superpowers/specs/2026-11-13-template-slimming-design.md`

## Global Constraints

- THE RULE (CLAUDE.md): the CLI executes, Studio only triggers; a Studio/CLI difference is a bug, parity test required for anything Studio triggers.
- Vendored files (`app/schemas/stable/survey.schema.json`, `docs/specs/`, `scripts/specification/`, `official/library/terms/`) are never edited here; only through prism-specification + `scripts/sync_specification.py --tag <tag>`.
- Local and editable: `app/schemas/stable/recipe.survey.schema.json`, `official/library/survey/*.json`, `official/recipe/survey/*.json`.
- Phase 1 must not break a template or recipe that still has the old fields.
- A reversal is never lost: the migration (Task 4) lands and is verified before any reader stops using `Reversed` (Task 5).
- Session IDs, text-format/annex policy and dual-tree rules of CLAUDE.md apply; TDD for every task; before merge `/ponytail:ponytail-audit`, `/code-review`.
- Branch `feat/template-slimming` in a worktree, started from main after `feat/item-map` is merged.
- Nothing is pushed, tagged or opened as a pull request in prism-specification without the user's explicit go-ahead.

## Review Focus

1. A template with `Reversed: true` items whose recipe already has a different `Transforms.Invert` list: the migration must merge, never overwrite or duplicate. (Task 4)
2. A recipe `Scores` entry without `Label` (all 104 official ones today): reporting falls back to `Name` and never crashes or prints "None". (Task 1)
3. A report language the label does not have: falls back to `en`, then `Name`. (Task 1)
4. A template with `ItemCount` that disagrees with its items: the shown count is the real one. (Task 3)
5. Templates still carrying `Study.Subscales`/`Reversed`/`ItemCount` validate clean in phase 1 and are simply ignored. (Tasks 1, 3, 5)

---

### Task 1: Recipe `Scores[].Label`; reporting reads the recipe (replaces `Study.Subscales`)

**Files:**
- Modify: `app/schemas/stable/recipe.survey.schema.json` (`Scores[].Label`), `app/src/reporting.py:~1246` (the "subscales" sentence), `src/recipe_builder.py` (save path keeps `Label`)
- Test: `tests/test_recipe_score_label.py`, extend a reporting test

**Interfaces:**
- Produces: `Scores[].Label: {"en": str, ...}` (object, `en` required, other keys language codes, optional). `score_label(score: dict, lang: str) -> str` in `src/recipes_surveys.py`: the label in `lang`, else `en`, else `Name`.
- Consumes: the project's recipes as `load_recipe(dataset_path, task)` / the same recipe lookup the reporting already uses (`summary["recipes"]` at `app/src/reporting.py:658`; read how it is built and reuse it).

- [ ] **Step 1: Failing tests.** `score_label({"Name": "tipi_extraversion"}, "de") == "tipi_extraversion"`; `{"Name": "x", "Label": {"en": "Extraversion", "de": "Extraversion (D)"}}` gives the `de` text for `de`, the `en` text for `fr`; a recipe with `Label` lacking `en` fails schema validation; the methods text for a task whose recipe has two scores contains `The instrument has the subscales: Extraversion, Agreeableness.` (English report) built from the recipe, and no longer from `Study.Subscales` (a template whose `Study.Subscales` says `["Old"]` does not print "Old").
- [ ] **Step 2: Run** `python -m pytest tests/test_recipe_score_label.py -q`; expected FAIL.
- [ ] **Step 3: Implement** the schema property, `score_label`, and in `reporting.py` replace the `study.get("Subscales")` branch by the labels of the task's recipe scores in the report language (only when the recipe has more than one score, as a single total is not a "subscale").
- [ ] **Step 4: Run** the new tests plus `python -m pytest tests -q -k "reporting or recipe"`; expected PASS.
- [ ] **Step 5: Commit** `feat(recipes): Scores[].Label per language; methods text reads subscales from the recipe`

---

### Task 2: Recipe builder: a Label per score and language

**Files:**
- Modify: `app/static/js/recipe_builder.js` (and its `modules/recipe-builder/` helpers), the recipe builder template; backend only through the existing recipe save route
- Test: vitest for the pure helper, one Flask-route test that a saved recipe keeps `Label`

**Interfaces:**
- Consumes: `Scores[].Label` schema (Task 1), the languages of the template (`I18n.Languages`, from `draft_from_template` as `template_language`/`item_description_languages`).
- Produces: per score, one text input per template language plus the required English one (reuse the page's chip/pull-down helpers for the language list; look at how `item_descriptions_i18n` is shown); empty values are not sent.

- [ ] **Step 1: Read** how the builder lists scores and sends them (the save call in `recipe_builder.js` and `save_recipe_to_project`); write the failing vitest for the helper that builds the `Label` object from the inputs (empty languages dropped, `en` required, trims) and a route test saving a recipe with `Label`.
- [ ] **Step 2: Run** them; expected FAIL.
- [ ] **Step 3: Implement** the inputs and the helper; the route needs no change if `save_recipe_to_project` already validates against the schema (confirm).
- [ ] **Step 4: Run** `npx vitest run app/static/js` (recipe folders) and the route test; PASS. State that the page was not looked at in a browser if it was not.
- [ ] **Step 5: Commit** `feat(recipe-builder): enter a Label per language for each score`

---

### Task 3: `ItemCount` becomes derived

**Files:**
- Modify: readers `src/instrument_registry.py:31`, `src/template_info.py:161`; writers `src/converters/limesurvey.py` (two places), `src/converters/pavlovia_import.py:208`, `src/converters/version_merger.py` (136-139, 188, 199), `src/survey_template_normalization.py:59` if it only lists the key
- Test: `tests/test_item_count_derived.py`

**Interfaces:**
- Produces: `count_items(template: dict, version: str | None = None) -> int` in `src/template_info.py` (items = top-level keys that are not template sections; with `version`, only items whose `ApplicableVersions` contains it or has none). Readers call it; nobody writes `Study.ItemCount` or `VariantDefinitions[].ItemCount` any more.

- [ ] **Step 1: Failing tests:** a template whose `Study.ItemCount` is 99 but has 3 items is listed with 3; the wellbeing-multi official template gives 10, 7 and 10 for its three variants; the LimeSurvey and Pavlovia imports and the version merger produce templates without `ItemCount` keys (assert absence in the JSON they write).
- [ ] **Step 2: Run;** expected FAIL.
- [ ] **Step 3: Implement** `count_items`, switch the two readers, delete the writes. `template_validator`'s allowed-key list keeps `ItemCount` (old templates still validate) until Phase 3.
- [ ] **Step 4: Run** `python -m pytest tests -q -k "template_info or instrument_registry or limesurvey or pavlovia or version_merger or item_count"`; PASS.
- [ ] **Step 5: Commit** `refactor(templates): ItemCount is derived from the items, not stored`

---

### Task 4: Migrate `Reversed` into the recipes

**Files:**
- Create: `src/reversed_migration.py`; CLI `recipes migrate-reversed` (find the recipe command group with `grep -n "recipes\|\"recipe" app/src/cli/parser.py`; follow its pattern and dispatch entries)
- Test: `tests/test_reversed_migration.py`

**Interfaces:**
- Consumes: the Invert transform shape in `src/recipes_surveys.py` (read lines ~458 and ~823: `Transforms.Invert` with items and scale range) and `extract_template_reversed_items` / `extract_item_ranges_from_template` in `src/recipe_builder.py`.
- Produces: `migrate_reversed(template_path, recipe_path, *, dry_run: bool) -> dict` (`{"task", "added": [item,...], "already": [item,...], "no_scale": [item,...]}`); `migrate_library(root, *, dry_run) -> list[dict]` over a folder pair (templates, recipes); CLI `recipes migrate-reversed --templates DIR --recipes DIR [--apply]` (default dry-run: prints what would change). A task without a recipe is reported, never created.

- [ ] **Step 1: Failing tests:** (a) template with `Reversed` ADS02, ADS05 and a recipe without `Transforms.Invert` -> `added == ["ADS02","ADS05"]`, the written recipe validates against the recipe schema and its Invert covers exactly those items with the scale range of the items; (b) recipe already inverting ADS02 only -> merged list, no duplicates, existing scale kept, `already == ["ADS02"]`; (c) running twice changes nothing (idempotent, byte-identical file); (d) an item without a usable Min/MaxValue is listed in `no_scale` and not written (needs the user, never guessed); (e) `--apply` absent writes nothing; (f) a task with no recipe is reported.
- [ ] **Step 2: Run;** expected FAIL.
- [ ] **Step 3: Implement** per the signatures (one implementation; the Invert shape is read from the same builder the recipe builder uses, no copy of the JS logic).
- [ ] **Step 4: Dry-run on the real data and record the result:** `python prism_tools.py recipes migrate-reversed --templates official/library/survey --recipes official/recipe/survey` and paste the counts (templates with Reversed, recipes changed, `no_scale`, tasks without a recipe) into the commit body; stop and report to the user if `no_scale` or missing recipes are not empty, do not guess.
- [ ] **Step 5: Commit** `feat(recipes): migrate-reversed copies template reversal into the recipes`

---

### Task 5: Apply the migration; stop reading `Reversed` from templates

**Files:**
- Modify: `official/recipe/survey/*.json` (result of `--apply`, reviewed as a diff), `src/recipe_builder.py` (`draft_from_template`: drop `template_reversed_items`, the draft's reversed set comes from the existing recipe if any), `app/static/js/recipe_builder.js` (state from the loaded recipe's Invert), `app/src/questionnaire_renderer.py` (421, 463, 608: drop the "(R)" marks), `app/static/js/template-editor.js` (3975, 4083: drop the badge), `src/converters/phenotype_import.py:95` and `hostile_demo_generator.py:1163` (stop writing `"Reversed": False`), `src/converters/phenotype_export.py` (stop exporting from the template; export the recipe's Invert if it already reads recipes, else drop the field and say so)
- Test: extend the tests of each touched module

**Interfaces:**
- Consumes: `migrate_library` (Task 4). Produces: nothing reads `item["Reversed"]` in `src/` or `app/` except `template_validator` (still accepts it as a boolean).

- [ ] **Step 1: Failing tests:** `draft_from_template` has no `template_reversed_items` key and a recipe-based `reversed_items` for a task with a recipe; the questionnaire renderer output for an item with `Reversed: true` has no "(R)"; the importers write no `Reversed` key; the migrated official recipes: for every official template that had `Reversed` items, the recipe's Invert contains them (a test reading both folders; this is the guard against lost reversals).
- [ ] **Step 2: Run;** expected FAIL.
- [ ] **Step 3: Apply** `python prism_tools.py recipes migrate-reversed ... --apply`, inspect `git diff --stat official/recipe`, then make the reader changes. `grep -rn "Reversed" src app --include='*.py' --include='*.js'` must end with only the validator.
- [ ] **Step 4: Run** `python -m pytest tests -q -k "recipe or questionnaire or phenotype or template_editor or reversed"` and `npx vitest run app/static/js`; PASS.
- [ ] **Step 5: Commit** `refactor(templates): reversal is read from the recipe, not from the template item`

---

### Task 6: prism-specification change (gated: ask the user before starting)

**Files:** in the prism-specification repository: `survey.schema.json` (remove `Study.Subscales`, `Study.ItemCount`, `VariantDefinitions[].ItemCount`, item `Reversed`), `docs/specs/survey.md`, changelog; tag a release.

- [ ] **Step 1: Ask the user** to confirm opening the change in the other repository and who tags the release. Do nothing before an explicit yes.
- [ ] **Step 2:** Make the change on a branch there with the repository's own tests; open the pull request; report the link.
- [ ] **Step 3:** After the user merges and tags, note the tag for Task 7.

---

### Task 7: Sync the tag and delete the leftovers

**Files:**
- Modify: via `python scripts/sync_specification.py --tag <tag>` (vendored files only), then `official/library/survey/*.json` (script strips the three keys), `app/src/template_validator.py` (allow-lists at 68, 88 and the `Reversed` check ~656), `app/src/issues.py:128` (hint text), `app/static/js/template-editor/questionnaire-sections.js` (`Study/Subscales`, `Study/ItemCount` fields), `src/survey_template_normalization.py`, docs, CHANGELOG/release note
- Test: `tests/test_vendored_specification.py` style check passes (CI job "Vendored specification"), a test that no official template carries the three keys, the full touched-area suites

- [ ] **Step 1: Failing test:** no file in `official/library/survey` contains `"Subscales"`, `"ItemCount"` or `"Reversed"`; the validator rejects `Reversed` on an item (schema now closed) with a message pointing to the recipe.
- [ ] **Step 2: Run;** FAIL. **Step 3:** run the sync with the tag, strip the keys with a one-off script (not committed), remove the leftover allow-lists and editor fields, add the release note (breaking for templates that still carry the fields: how to migrate, `recipes migrate-reversed` stays available). **Step 4:** run `python tests/verify_repo.py --check dual-tree-drift --no-fix`, the vendored-specification check, and `python -m pytest tests -q -k "template or recipe or reporting or validator or spec"`; PASS. **Step 5: Commit** `chore(templates): drop Subscales, ItemCount and Reversed after specification <tag>`

---

### Task 8: Finish

- [ ] `/ponytail:ponytail-audit`, `/code-review`; re-run tests; browser look at the recipe builder Label inputs by the user; `superpowers:finishing-a-development-branch`. No merge or push without the user's go-ahead.
