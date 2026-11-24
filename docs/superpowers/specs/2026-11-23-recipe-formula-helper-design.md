# Recipe Builder: formula helper (short design)

Status: waiting for approval. Size: a small feature (several steps, one stream).

## Intent

Subscores are often more than a sum or mean (best of three trials, then a composite, optionally relative
to leg length: the Y Balance Test sheet is the model case). The engine already supports this
(`Method: "formula"`, `Transforms.Derived`), but the Recipe Builder only offers `mean` and `sum`, loads formula scores
read-only, and has no UI for `Transforms.Derived`. Users must edit JSON. They should be able to build such a recipe
in Studio, and see what the formula means.

## Goals

- Build a formula score in the Recipe Builder: insert items, type the formula, see a check result.
- Build "best of N" (`Transforms.Derived`, `max`/`min`) in the same place, so the Y Balance recipe needs no JSON.
- Show a formula as rendered math (display only).
- Same behaviour from the CLI: the check and the rendering are CLI commands that Studio only triggers.

## Non-goals / anti-goals

- No LaTeX (or any second) **input** language. The stored `Formula` string stays exactly as the engine reads it.
- No new functions or operators in the engine; the restricted calculator is a security boundary.
- No formula logic in JavaScript or a Flask route (no parsing, no evaluation, no rendering there).
- No editor for `Transforms.Invert` changes, `map`, `irv` or other methods.

## Approaches considered

1. **Formula-only helper.** Smaller, but the Y Balance recipe still needs JSON for best-of-3.
2. **Helper plus best-of-N on the same cards (chosen).** The whole model case works in the GUI.
3. **LaTeX input, converted to the engine syntax.** Rejected: needs a parser (new dependency or hundreds of lines),
   item names such as `ant_r_1` clash with LaTeX subscripts, and it creates two formula languages.

## Design

**Backend (`src/`, the one implementation)**
- `check_formula(formula, items, example_values)`: evaluates with the engine's own functions
  (`_safe_eval_formula_expression`, `_resolve_formula_placeholder`) and returns the result or the reason it is empty
  (unknown `{NAME}`, name missing from `Items`, missing example value, parse error). One message text for CLI and Studio.
- `formula_to_latex(formula)`: walks the same AST the engine uses and writes LaTeX (`/` as fraction, `**` as
  superscript, `{NAME}` as `\text{NAME}`, `max`/`min`/`sqrt`/`ifelse` as readable forms). It rejects what the engine rejects.
- Both exposed as CLI commands (names left to the builder, in the existing recipe command group).

**Studio (adapter only)**
- Score card: Method pull-down gains `formula`; a formula score is no longer locked. Fields: formula text box, item
  pull-down that inserts `{ITEM}`, chips for the items used (reuse `chip-list.js`), a "Check with example values" line,
  and the rendered formula under the box. The checks call routes that call the two `src/` functions.
- A "Best of N" section writes `Transforms.Derived` entries (`max`/`min`, items as chips), so later formulas can use
  them as items. Same pull-down and chip widgets as the project page.
- Rendering uses a bundled KaTeX (vendored, no network use in the desktop app) or browser MathML, whichever the
  builder finds smaller; it only displays the string `formula_to_latex` returned.
- Theme macros / `studio-theme.js` for headings and badges; no page-local styling.

## Fixes bundled in

- `Method: "max"`/`"min"` as a **score** silently gives `n/a`. The builder must not offer it, and the validator should
  reject it with a message pointing to `Transforms.Derived`. (Small validator change with a test.)

## Tests (TDD, failing first)

- `src/` unit tests: `check_formula` (ok, unknown name, name not in Items, missing example value, parse error,
  disallowed code) and `formula_to_latex` (the Y Balance formulas, `ifelse`, rejected input).
- Validator test for `max`/`min` as a score.
- CLI vs Studio parity test (`tests/test_cli_studio_parity.py`): saving a Y Balance recipe through both writes the
  same file, and the check/render commands give the same output.
- JS tests for the builder module: Derived entries and formula scores load, edit and save losslessly.

## Left to the builder

- CLI command names and where they sit; KaTeX vs MathML; wording of the check messages (English, one text);
  whether the example-value inputs are one row per item or a single JSON box.
- Docs: extend the Formulas section in `docs/RECIPES.md` with the GUI steps once built.

## Open for the user

None blocking. Two calls made here, for review: (1) `max`/`min` as score becomes a validator error, not new
engine behaviour; (2) rendering is display only, so the stored recipe never contains LaTeX.
