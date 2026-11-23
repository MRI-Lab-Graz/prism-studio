# Recipe Builder formula helper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build formula scores and best-of-N (`Transforms.Derived`) in the Recipe Builder, with a check and a rendered-math display, all run by CLI commands that Studio only triggers.

**Architecture:** Two pure functions in `src/` (`check_formula`, `formula_to_latex`) reuse the engine's own AST walker; CLI commands and Flask routes are thin callers; the builder JS adds a formula/Best-of-N UI that calls those routes and renders the returned LaTeX with vendored KaTeX.

**Tech Stack:** Python (ast, pytest), Flask, vanilla JS modules (vitest), KaTeX (vendored under `app/static/vendor/`).

**Spec:** `docs/superpowers/specs/2026-11-23-recipe-formula-helper-design.md`

## Global Constraints

- THE RULE: no formula parsing, evaluation, rendering or defaults in JS or a Flask route; the same input gives the same output in CLI and Studio (parity test).
- The stored `Formula` string and the engine's operators/functions do not change; no LaTeX is ever saved in a recipe.
- Display only: `formula_to_latex` rejects exactly what the engine rejects.
- Same widgets as the project page: pull-down + green chips via `app/static/js/modules/projects/chip-list.js`; headings via theme macros / `studio-theme.js`; no page-local styling.
- Messages in English, one text for CLI and Studio.
- TDD: failing test first, see it fail, then the code. Commit per task. Work in the worktree `../prism-studio-formula-helper` (branch `feat/recipe-formula-helper`).
- Before `src/` vs `app/src/` edits, check which file answers: `python3 -c "import src.<mod> as m; print(m.__file__)"`. New `src/` modules have no `app/src/` copy.
- Subagents (if used) run on Sonnet 5.5 (`claude-sonnet-5-5`), model set explicitly.

## Review Focus

- A formula with a name not in `Items` (`{x}` unlisted): the check says so by name, the score is not saved as "valid".
- An item that is empty or `n/a` in the example values: result "empty because ... is missing", never `0`.
- Division by zero (`/{leg_length}` = 0) and `log` of 0: check reports an error text, no crash, no traceback.
- Hostile input (`__import__('os')`, attribute access, huge exponent): check and LaTeX both refuse.
- Item names with underscores/digits (`ant_r_1`) render as readable text in LaTeX, not as a subscript.
- Loading a recipe that already has `Transforms.Derived`, `Formula` scores, `Invert`: save round-trips them unchanged.

---

### Task 1: Validator rejects `max`/`min` as a score method

**Files:**
- Modify: `src/recipe_validation.py` (the Scores method check)
- Test: `tests/test_recipe_validation_score_max.py`

**Interfaces:**
- Consumes: the existing validator entry the other `tests/test_recipe_validation_*.py` call.
- Produces: error text containing `Transforms.Derived` for a score with `Method` `max` or `min`.

- [ ] **Step 1: Write the failing tests** `test_max_score_is_rejected_with_hint` and `test_min_score_is_rejected_with_hint` (recipe with one score `{"Name":"s","Method":"max","Items":["a","b"]}`; assert one error mentions `Transforms.Derived`), and `test_max_derived_is_still_valid` (same entry under `Transforms.Derived` gives no error). Copy the recipe/validator call style from `tests/test_recipe_validation_warnings.py`.
- [ ] **Step 2: Run** `pytest tests/test_recipe_validation_score_max.py -v`; expect the two rejection tests FAIL.
- [ ] **Step 3: Implement** the rejection in the Scores loop of `src/recipe_validation.py` (message: `Scores[i] "<name>": Method "max" works only in Transforms.Derived; use a formula or move it there`). Confirm the live file with the `__file__` check first.
- [ ] **Step 4: Run** the new tests plus `pytest tests/test_recipe_validation_warnings.py tests/test_recipe_builder_handlers.py -q`; expect PASS.
- [ ] **Step 5: Commit** `fix(recipes): max/min as a score method is an error, not a silent n/a`.

---

### Task 2: `check_formula` and `formula_to_latex` in `src/`

**Files:**
- Create: `src/recipes_formula_tools.py`
- Test: `tests/test_recipes_formula_tools.py`

**Interfaces:**
- Consumes: `src.recipes_formula_engine._safe_eval_formula_expression`, `_resolve_formula_placeholder`, and the AST allow-lists `_SAFE_FORMULA_BINOPS/UNARYOPS/CMPOPS/BOOLOPS/FUNCTIONS`.
- Produces:
  - `check_formula(formula: str, items: list[str], values: dict[str, str]) -> dict` returning `{"ok": bool, "result": str | None, "message": str}`. `result` is the engine's formatted cell (`_format_numeric_cell`); `message` is empty on success, else one English sentence.
  - `formula_to_latex(formula: str) -> dict` returning `{"ok": bool, "latex": str | None, "message": str}`.

- [ ] **Step 1: Write the failing tests** (names and assertions):
  - `test_check_y_balance_composite`: formula `({a}+{b}+{c})/3`, items `[a,b,c]`, values `65,72,70` gives `ok` and `result == "69"`.
  - `test_check_relative_composite`: `({a}+{b})/(2*{leg})*100`, `65,72,90` gives `"76.11111111111111"`.
  - `test_check_name_not_in_items`: formula uses `{x}`, items `[a]` gives `ok False`, message contains `{x}` and `Items`.
  - `test_check_missing_value`: value `"n/a"` and `""` each give `ok False`, `result is None`, message names the item, no `"0"` result.
  - `test_check_division_by_zero_and_log_zero`: `ok False`, message non-empty, no exception.
  - `test_check_refuses_code`: `__import__('os')`, `{a}.real`, `{a}**99999` each give `ok False`.
  - `test_latex_fraction_and_names`: `({ybt_ant_right}+{ybt_pm_right})/3` gives `\frac{\left(\text{ybt\_ant\_right}+\text{ybt\_pm\_right}\right)}{3}` (exact string decided here, then fixed by the test).
  - `test_latex_power_max_sqrt_ifelse`: `{a}**2` → `\text{a}^{2}`; `max({a},{b})` → `\max\left(\text{a},\text{b}\right)`; `sqrt({a})` → `\sqrt{\text{a}}`; `ifelse({a}>1,1,0)` → a cases/`\begin{cases}` form.
  - `test_latex_rejects_what_engine_rejects`: same hostile inputs give `ok False`, `latex is None`.
- [ ] **Step 2: Run** `pytest tests/test_recipes_formula_tools.py -v`; expect FAIL (module missing).
- [ ] **Step 3: Implement** `check_formula` by substituting placeholders exactly as `_calculate_scores` does (missing item or unlisted name leaves it empty, with the reason named) and evaluating with the engine; catch `ZeroDivisionError`/`ValueError`/`OverflowError` into `message`. Implement `formula_to_latex` as a recursive walk over `ast.parse` (replace `{NAME}` with a safe identifier first and map back to `\text{...}` with `_` escaped), raising on any node type the engine's evaluator does not accept; do not copy the evaluator, reuse its allow-list dicts.
- [ ] **Step 4: Run** the new file plus `pytest tests/test_recipes_formula_engine_security.py tests/test_recipes_formula_missing_items.py -q`; expect PASS.
- [ ] **Step 5: Commit** `feat(recipes): check_formula and formula_to_latex`.

---

### Task 3: CLI commands and Studio routes, with a parity test

**Files:**
- Modify: `app/src/cli/commands/recipes.py` (add `cmd_recipes_formula_check`, `cmd_recipes_formula_latex`, next to `cmd_recipes_load`), `app/src/cli/entrypoint.py` (register `recipes formula-check|formula-latex`), `app/src/web/blueprints/tools.py` (routes), `app/src/web/blueprints/tools_recipe_builder_handlers.py` (two handlers)
- Test: `tests/test_recipes_formula_parity.py`

**Interfaces:**
- Consumes: `check_formula`, `formula_to_latex` from Task 2.
- Produces:
  - CLI: `recipes formula-check --formula F --items a,b,c --values '{"a":"65"}'` prints the `check_formula` dict as JSON (`_print_json`); `recipes formula-latex --formula F` prints the `formula_to_latex` dict. Exit code 0 always for a reported failure (it is a result, not a crash); exit 1 only for unreadable arguments.
  - Studio: `POST /api/recipe-builder/formula-check` body `{formula, items, values}` and `POST /api/recipe-builder/formula-latex` body `{formula}`, each returning the same dict as JSON.

- [ ] **Step 1: Write the failing test** `test_cli_and_studio_give_the_same_check_and_latex`: for a list of cases (Y Balance composite, relative composite, unlisted name, missing value, hostile string) call the CLI function with `SimpleNamespace(...)` capturing stdout (`capsys`) and the Flask test client for the routes (follow `tests/test_recipe_builder_handlers.py::_build_app_and_handlers`); assert parsed JSON is equal. Add `test_commands_are_registered` asserting both subcommands parse in `entrypoint` (pattern in `tests/test_cli_parity_commands.py`).
- [ ] **Step 2: Run** `pytest tests/test_recipes_formula_parity.py -v`; expect FAIL.
- [ ] **Step 3: Implement** the four thin adapters; none of them may contain logic beyond argument parsing. Add both commands to `docs/CLI_REFERENCE.md` (one line each, same style as `recipes save`).
- [ ] **Step 4: Run** the parity test, `pytest tests/test_cli_parity_commands.py tests/test_recipe_builder_handlers.py -q`, and `python tests/verify_repo.py --check dual-tree-drift --no-fix`; expect PASS.
- [ ] **Step 5: Commit** `feat(recipes): formula-check and formula-latex commands, Studio routes call them`.

---

### Task 4: Builder data model: formula scores and `Transforms.Derived` load, edit, save losslessly

**Files:**
- Create: `app/static/js/modules/recipe-builder/formula-score.js`
- Modify: `app/static/js/recipe_builder.js` (`EDITABLE_METHODS`, `SAFE_SCORE_KEYS`, `scoreToScale`, `scaleToScore`, recipe assembly), `app/static/js/modules/recipe-builder/recipe-merge.js` only if it drops `Transforms.Derived`
- Test: `app/static/js/modules/recipe-builder/formula-score.test.js`

**Interfaces:**
- Produces (pure, no DOM, no formula logic):
  - `derivedToEntry(d) -> {id, name, method, items, original}` and `entryToDerived(entry) -> object` (method limited to `max`|`min`; keeps unknown keys from `original`).
  - `scoreHasFormula(score) -> boolean`; formula scores use `Method: "formula"`, `Formula`, `Items`; `Formula` joins `SAFE_SCORE_KEYS` so the card is no longer locked.
  - `itemsUsedIn(formula) -> string[]`: only the names between `{` `}` as written, to pre-fill chips (text scan, not evaluation).

- [ ] **Step 1: Write the failing tests** (`vitest`): `Derived` entry round-trips with an unknown key preserved; a recipe with `Transforms: {Invert, Derived}` and a formula score loads and saves byte-equal JSON (`JSON.stringify` of parsed output equals input); a `map` score stays locked; `itemsUsedIn('({a}+{b})/{a}')` gives `['a','b']`.
- [ ] **Step 2: Run** `npx vitest run app/static/js/modules/recipe-builder/formula-score.test.js`; expect FAIL.
- [ ] **Step 3: Implement** the module and wire it into `recipe_builder.js`; keep `Invert` handling untouched.
- [ ] **Step 4: Run** `npx vitest run` (all JS) and `pytest tests/test_recipe_builder_workflow_wiring.py -q`; expect PASS.
- [ ] **Step 5: Commit** `feat(recipe-builder): formula scores and Derived entries load and save without loss`.

---

### Task 5: Builder UI: formula box, check line, rendered math, Best-of-N section

**Files:**
- Modify: `app/static/js/recipe_builder.js` (score card: Method pull-down gains `formula`; new Best-of-N section), `app/templates/recipe_builder.html` (section container, KaTeX assets), `app/static/js/studio-theme.js` / macros only if a new themed part is needed (add to the theme first)
- Create: `app/static/vendor/katex/` (vendored `katex.min.js`, `katex.min.css`, fonts, with its license file)
- Test: `app/static/js/modules/recipe-builder/formula-card.test.js`, extend `tests/test_recipe_builder_workflow_wiring.py`

**Interfaces:**
- Consumes: Task 3 routes; Task 4 module; `mountChipList` / `mountChipArea` from `modules/projects/chip-list.js`.
- Produces: for a `formula` scale the card shows a text box, an item pull-down that inserts `{ITEM}` at the cursor and moves the item into a chip, example-value inputs (one per item), a "Check" result line (text from the route's `message`/`result`) and the rendered formula under the box (`katex.render(latex, el, {throwOnError:false})` with the string from `formula-latex`; on `ok:false` show the message, never the raw input as HTML). The Best-of-N section lists `Derived` entries (name, `max`/`min` pull-down, item chips); entry names become selectable as items in formula cards. Use `textContent` for every server-returned string.

- [ ] **Step 1: Write the failing tests:** a vitest for the pure part of the card (insert-at-cursor helper returns the new string and cursor; an item name is added to `items` once); a wiring test asserting the template includes the KaTeX asset and the builder calls only `/api/recipe-builder/formula-check` and `/formula-latex` (no `eval`, no formula regex in JS).
- [ ] **Step 2: Run** both; expect FAIL.
- [ ] **Step 3: Implement** the UI with the project-page widgets; debounce check/latex calls (about 300 ms); vendor KaTeX (check size; if KaTeX is not acceptable, fall back to native MathML from the same LaTeX is NOT allowed here, use the spec's other option only by asking the user).
- [ ] **Step 4: Run** `npx vitest run`, `pytest tests/test_recipe_builder_workflow_wiring.py tests/test_studio_theme_parity.py -q`; then start Studio (`run` skill), build the Y Balance recipe (three `max` entries, one composite formula, one relative formula) in the browser, save, and compare the saved file with `docs/RECIPES.md`'s example; expect equal Scores/Derived.
- [ ] **Step 5: Commit** `feat(recipe-builder): formula box with check and rendered math, Best-of-N section`.

---

### Task 6: Docs, changelog, divergences, final checks

**Files:**
- Modify: `docs/RECIPES.md` (GUI steps under "Formulas"), `docs/CLI_REFERENCE.md` (if not done in Task 3), `CHANGELOG.md`, `docs/CLI_STUDIO_DIVERGENCES.md` (remove or update the Recipe builder row if it names this gap)
- Test: none new

- [ ] **Step 1:** Write the docs: how to add a formula and a Best-of-N entry in the builder, what the check line and the rendered formula mean, the `max`/`min` score error.
- [ ] **Step 2: Verify** (superpowers:verification-before-completion): run `pytest tests/test_recipes_formula_tools.py tests/test_recipes_formula_parity.py tests/test_recipe_validation_score_max.py tests/test_recipe_builder_handlers.py tests/test_cli_parity_commands.py tests/test_cli_studio_parity.py -q`, `npx vitest run`, `python tests/verify_repo.py --check dual-tree-drift --no-fix`; quote the results and say the full suite was not run.
- [ ] **Step 3:** Run `ponytail:ponytail-audit` once on the branch, apply what is worth it, re-run the checks, then `/code-review` once; then superpowers:finishing-a-development-branch.
- [ ] **Step 4: Commit** `docs(recipes): formula helper, changelog`.
