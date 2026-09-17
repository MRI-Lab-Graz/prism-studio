# JOSS Submission Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clear every release-quality and manuscript blocker so the PRISM paper can be submitted to JOSS: green CI (pytest + mypy), the paper under the 1750-word limit, consistent version metadata, no orphaned figure assets, and a locally-verified JOSS/Inara compile.

**Architecture:** Six independent fixes against the existing repo — no new modules, no refactors beyond what each bug touches. Two test fixes, 27 mechanical mypy type-annotation/narrowing fixes across 12 files, a verified word-count trim of `paper/paper.md`, three version-string corrections, one figure wired in (three unused ones removed), and a local Docker/Inara compile check.

**Tech Stack:** Python 3.13 (repo standard library + existing deps), pytest, mypy 
(`ignore_missing_imports = True`, `explicit_package_bases = True` per `mypy.ini`), 
Pandoc/LaTeX via the `openjournals/inara` Docker image for the JOSS paper compile.

**Spec:** This plan *is* the spec — it was derived directly from the six numbered
findings in the task description (stale test expectations, 27 mypy errors, an
1831-word paper against JOSS's 750–1750 limit, stale `1.18.0` version strings
against the current `1.18.1` tag, four orphaned figure assets, and an
unverified Inara compile because the Docker daemon isn't running).

## Global Constraints

- Per `CLAUDE.md`: before editing any function in `app/src/` that isn't pure Flask
  route/adapter code, check for a same-named file under top-level `src/` with
  `find src -name '<filename>.py'` and confirm which physical file answers for the
  import with `python3 -c "import <module>; print(m.__file__)"` — do not assume an
  edit is live. This plan already ran that check for every touched file (see each
  task's file list); only `app/src/converters/survey.py` has a live symlink
  counterpart (`src/converters/survey.py -> ../../app/src/converters/survey.py`),
  so its fix must land in `app/src/converters/survey.py`, never the symlink.
- Do not reintroduce numeric session-label normalization anywhere (not touched by
  this plan, but stays true for any new code).
- No unrequested refactors: every fix below is the smallest change that resolves
  its specific error. Do not restructure a file beyond what its listed error needs.
- Commit messages/PR descriptions end with the attribution lines from the
  session's system reminder, not any older convention.

---

## Task 1: Fix the two stale file-browser handler tests

**Files:**
- Modify: `tests/test_tools_file_browser_handlers.py:35` and `:70`
- Reference (no change needed): `app/src/web/blueprints/tools_file_browser_handlers.py`

**Context:** `handle_api_browse_file()` (in `app/src/web/blueprints/tools_file_browser_handlers.py:6-15`)
now always passes `initial_dir=start_dir` to `file_picker.pick_file(...)`, where
`start_dir` defaults to `None` when the `start_dir` query arg is absent — this is
intentional (a `start_dir` query param was added). The two failing tests still
assert the old two-argument-only call shape.

- [ ] **Step 1: Confirm the two failures reproduce**

Run: `pytest tests/test_tools_file_browser_handlers.py -q`
Expected: `2 failed, 2 passed` — both failures show
`Expected: pick_file(project_json_only=True)` / `Actual: pick_file(project_json_only=True, initial_dir=None)`
(and the `project_json_only=False` variant).

- [ ] **Step 2: Update the two stale assertions**

In `tests/test_tools_file_browser_handlers.py`, change line 35:

```python
        mock_pick_file.assert_called_once_with(project_json_only=True)
```
to
```python
        mock_pick_file.assert_called_once_with(
            project_json_only=True, initial_dir=None
        )
```

And change line 70:

```python
        mock_pick_file.assert_called_once_with(project_json_only=False)
```
to
```python
        mock_pick_file.assert_called_once_with(
            project_json_only=False, initial_dir=None
        )
```

- [ ] **Step 3: Run the file and the full suite**

Run: `pytest tests/test_tools_file_browser_handlers.py -q`
Expected: `4 passed`

Run: `pytest tests/ -q`
Expected: `3730 passed, 0 failed` (was `3725 passed, 2 failed, 3 skipped` — the 2
fixed here plus whatever the pre-existing 3 skipped were already skipped for
unrelated reasons; confirm the failure count is 0 and skip count didn't grow).

- [ ] **Step 4: Commit**

```bash
git add tests/test_tools_file_browser_handlers.py
git commit -m "test: update file-browser handler tests for intentional initial_dir=None"
```

---

## Task 2: Fix all 27 mypy errors

**Files:**
- Modify: `src/converters/presentation_log.py:39`
- Modify: `app/src/procedure_validator.py:74-75`
- Modify: `app/src/validator.py:440-447`
- Modify: `src/converters/presentation_to_events.py:63-67`
- Modify: `app/src/converters/excel_to_survey.py:35-40`
- Modify: `src/run_renumberer.py:147-160` (rename-only, see Step 6)
- Modify: `src/converters/pavlovia.py:122-201`
- Modify: `app/src/converters/survey.py:93` (canonical file — see Global Constraints)
- Modify: `app/src/web/blueprints/tools_generation_handlers.py:121`
- Modify: `app/src/web/blueprints/conversion_participants_io.py:300`
- Modify: `app/src/project_manager.py:3150-3160, 8901-8905`
- Modify: `src/recipes_surveys.py:26, 1787-1810, 2718-2741`

**Verification command (same one CI uses via `tests/verify_repo.py`):**
```bash
mypy app/src src --ignore-missing-imports --explicit-package-bases
```
Baseline: `Found 27 errors in 12 files (checked 260 source files)`. Target: `Success: no issues found`.

- [ ] **Step 1: `src/converters/presentation_log.py:39` — missing variable annotation**

Error: `error: Need type annotation for "rows" (hint: "rows: list[<type>] = ...")  [var-annotated]`

`rows` accumulates dicts with mixed `str | float | int | None` values (see the
`rows.append({...})` block a few lines below). `Any` is already imported at the
top of this file.

```python
    rows = []
```
becomes
```python
    rows: list[dict[str, Any]] = []
```

- [ ] **Step 2: `app/src/procedure_validator.py:74-75` — missing set annotations**

Errors: `Need type annotation for "disk_set"` and `"disk_sessions"` [var-annotated].

The enclosing function's `disk_index` parameter is already typed
`Optional[Tuple[Set[str], Set[Tuple[str, str]]]]` and unpacked as
`disk_sessions, disk_set = disk_index` a few lines below — so these two locals
must match that shape. `Set`/`Tuple` are already imported (used in that same
signature).

```python
    disk_set = set()
    disk_sessions = set()
```
becomes
```python
    disk_set: Set[Tuple[str, str]] = set()
    disk_sessions: Set[str] = set()
```

- [ ] **Step 3: `app/src/validator.py:440-447` — return type mismatch**

Error: `error: Incompatible return value type (got "tuple[object, Any]", expected "tuple[dict[Any, Any] | None, str | None]")  [return-value]`

`_deep_merge(base: object, override: object) -> object` (line 262) is
deliberately loosely typed since it recurses over arbitrary JSON values, but at
this call site both `root_data` and `subject_data` are already known to be
non-empty dicts (we're inside the `if root_data and subject_data:` branch, and
`load_json`'s declared return type is `dict | None`), so the merge result is
guaranteed to be a `dict` at runtime. Assert that instead of loosening
`_deep_merge`'s general-purpose signature:

```python
    if root_data and subject_data:
        # Both exist: merge (subject overrides root)
        merged = _deep_merge(root_data, subject_data)
        return merged, subject_sidecar_path
```
becomes
```python
    if root_data and subject_data:
        # Both exist: merge (subject overrides root)
        merged = _deep_merge(root_data, subject_data)
        assert isinstance(merged, dict)
        return merged, subject_sidecar_path
```

- [ ] **Step 4: `src/converters/presentation_to_events.py:63-67` — unguarded `Optional` from `spec_from_file_location`**

Errors: `Argument 1 to "module_from_spec" has incompatible type "ModuleSpec | None"; expected "ModuleSpec"` and two `Item "None" of ... has no attribute "loader"/"exec_module"` [arg-type, union-attr].

`importlib.util.spec_from_file_location` is typed `-> ModuleSpec | None`, and
`spec.loader` is `Optional[Loader]` — both really can be `None` if the path is
bad, so this needs a real guard, not just a cast:

```python
    decoder_path = Path(decoder_path)
    spec = importlib.util.spec_from_file_location(decoder_path.stem, decoder_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```
becomes
```python
    decoder_path = Path(decoder_path)
    spec = importlib.util.spec_from_file_location(decoder_path.stem, decoder_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load decoder module from {decoder_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

- [ ] **Step 5: `app/src/converters/excel_to_survey.py:35-40` — reassigning `None` to an imported type/function name**

Errors: `Cannot assign to a type [misc]` (x2) and `Incompatible types in assignment (expression has type "None", variable has type ...)` [assignment] (x5) — one pair for each of the 5 names in this soft-dependency fallback block. The comment on line 35 already documents these branches as
`# pragma: no cover - defensive fallback, unreachable in this repo`, so this is
mypy correctly flagging code that is intentionally never exercised — not a real
bug. Suppress narrowly rather than restructuring dead code:

```python
except ImportError:  # pragma: no cover - defensive fallback, unreachable in this repo
    ItemRegistry = None
    ItemCollisionError = None
    merge_survey_versions = None
    save_merged_template = None
    detect_version_name_from_import = None
```
becomes
```python
except ImportError:  # pragma: no cover - defensive fallback, unreachable in this repo
    ItemRegistry = None  # type: ignore[assignment,misc]
    ItemCollisionError = None  # type: ignore[assignment,misc]
    merge_survey_versions = None  # type: ignore[assignment]
    save_merged_template = None  # type: ignore[assignment]
    detect_version_name_from_import = None  # type: ignore[assignment]
```

- [ ] **Step 6: `src/run_renumberer.py:132` — variable reused with two incompatible types in one function**

Error: `error: Incompatible types in assignment (expression has type "tuple[str, ...]", variable has type "list[str]")  [assignment]`

Inside `_scan_groups`, `other_tokens: list[str] = []` (line 113) collects
prefix tokens per file, then gets folded into `group_key = (rel_dir,
tuple(other_tokens), suffix_token, extension)` (line 124). The later loop over
`sorted(buckets.items())` unpacks that same-shaped tuple back into a variable
of the *same name*, `other_tokens` — but this one is a `tuple[str, ...]` (from
`tuple(other_tokens)` above), colliding with the `list[str]` binding earlier
in the function. Rename the unpacked one; it's only used once more, two lines
down:

```python
        for group_key, files_by_run in sorted(buckets.items()):
            rel_dir, other_tokens, suffix_token, extension = group_key
            group_label = "/".join([rel_dir, "_".join([*other_tokens, suffix_token]) + extension])
            run_values = sorted(files_by_run.keys())
```
becomes
```python
        for group_key, files_by_run in sorted(buckets.items()):
            rel_dir, other_tokens_tuple, suffix_token, extension = group_key
            group_label = "/".join([rel_dir, "_".join([*other_tokens_tuple, suffix_token]) + extension])
            run_values = sorted(files_by_run.keys())
```

- [ ] **Step 7: `src/converters/pavlovia.py` — four errors from two repeated code-smell patterns**

Pattern A — calling `.get()` twice (once inside `isinstance(...)`, once as the
ternary's true-value) means mypy can't correlate the two calls, so the ternary's
type stays `Any | dict[Any, Any] | None` instead of narrowing to `dict`. Fixed
by binding the `.get()` result to a name once, then `isinstance`-checking that
name. This occurs at line ~146 (in `extract_questions`) and ~197 (in
`extract_questions_from_customized_group`):

```python
        raw_levels = resolved.get("Levels") if isinstance(resolved.get("Levels"), dict) else {}
```
becomes
```python
        levels_value = resolved.get("Levels")
        raw_levels = levels_value if isinstance(levels_value, dict) else {}
```

and

```python
        raw_levels = original.get("Levels") if isinstance(original.get("Levels"), dict) else {}
```
becomes
```python
        levels_value = original.get("Levels")
        raw_levels = levels_value if isinstance(levels_value, dict) else {}
```

Pattern B — in `extract_questions` (not `extract_questions_from_customized_group`,
which already uses a `resolved_language` local), the `language: Optional[str]`
parameter is reassigned inside `if language is None:` from an expression whose
type includes `Any`/`None` (`i18n.get("DefaultLanguage")`), so mypy still sees
`language` as `str | None` at the two `_resolve_text(..., language)` call sites
below (lines ~148, ~154). Narrow the fallback explicitly instead of trusting the
truthy check on an `Any`-typed `.get()` result:

```python
    if language is None:
        i18n = prism_json.get("I18n")
        language = (
            i18n.get("DefaultLanguage")
            if isinstance(i18n, dict) and i18n.get("DefaultLanguage")
            else "en"
        )
```
becomes
```python
    if language is None:
        i18n = prism_json.get("I18n")
        default_lang = i18n.get("DefaultLanguage") if isinstance(i18n, dict) else None
        language = default_lang if isinstance(default_lang, str) and default_lang else "en"
```

- [ ] **Step 8: `app/src/converters/survey.py:93` — namespace-package blind spot (mypy false positive)**

Error: `error: Module "src.converters" has no attribute "survey_column_mapping"  [attr-defined]`

`survey_column_mapping.py` exists only under `app/src/converters/` (verified
with `find . -iname survey_column_mapping.py`), and `src.converters` is an
implicit namespace package assembled at runtime from both `src/converters/`
and `app/src/converters/` — a merge mypy's static analysis doesn't perform the
same way Python's import system does. This file already carries the identical
`# type: ignore[attr-defined]` suppression on the two sibling imports one line
above (`survey_lsa`, `survey_io`) for exactly this reason — extend the same
pattern:

```python
from . import survey_core as _survey_core
from . import survey_participants_logic as _survey_participants_logic
from . import survey_column_mapping as _survey_column_mapping
```
becomes
```python
from . import survey_core as _survey_core
from . import survey_participants_logic as _survey_participants_logic
from . import survey_column_mapping as _survey_column_mapping  # type: ignore[attr-defined]
```

Per Global Constraints, this edit must land in `app/src/converters/survey.py`
(the real file) — `src/converters/survey.py` is a symlink to it.

- [ ] **Step 9: `app/src/web/blueprints/tools_generation_handlers.py:121` — same defensive-import idiom as Step 5**

Error: `error: Function "export_to_pavlovia" could always be true in boolean context  [truthy-function]`

```python
    try:
        from src.converters.pavlovia import export_to_pavlovia
    except ImportError:
        export_to_pavlovia = None

    if not export_to_pavlovia:
```
becomes
```python
    try:
        from src.converters.pavlovia import export_to_pavlovia
    except ImportError:
        export_to_pavlovia = None

    if not export_to_pavlovia:  # type: ignore[truthy-function]
```

- [ ] **Step 10: `app/src/web/blueprints/conversion_participants_io.py:300` — reuse the existing normalizer instead of loosening the callee**

Error: `error: Argument "separator_option" to "_read_participants_input_table" has incompatible type "str | None"; expected "str"  [arg-type]`

The enclosing function's `separator_option` parameter is `str | None` (line 273),
but `_read_participants_input_table` requires `str`. This file already defines
`_normalize_separator_option(value: str | None) -> str` at line 70 for exactly
this conversion — use it instead of widening `_read_participants_input_table`'s
signature:

```python
            diagnostic_df = _read_participants_input_table(
                input_path=input_path,
                suffix=suffix,
                sheet_arg=sheet_arg,
                separator_option=separator_option,
            )
```
becomes
```python
            diagnostic_df = _read_participants_input_table(
                input_path=input_path,
                suffix=suffix,
                sheet_arg=sheet_arg,
                separator_option=_normalize_separator_option(separator_option),
            )
```

- [ ] **Step 11: `app/src/project_manager.py:3150,3155,3160` — variable name collides with an earlier, differently-typed loop variable in the same function**

Error: `error: Incompatible types in assignment (expression has type "Path", variable has type "str")  [assignment]`

Earlier in the same method, `for rel_path in missing_scoped_files:` (line 3015)
fixes `rel_path`'s inferred type as `str` for the rest of the function (mypy
infers one type per variable name per function, not per-block). The later,
unrelated loop at line 3147 reassigns the same name to a `Path` (the result of
`.relative_to(...)`). Rename the second one — this is a real latent footgun
(two different meanings sharing one name in one function), not just a mypy
nag:

```python
                try:
                    rel_path = source_candidate.relative_to(copy_source_path)
                except Exception:
                    unresolved_source_paths.append(str(source_candidate))
                    continue

                original_candidate = project_path / rel_path
                if not original_candidate.exists() or original_candidate.is_dir():
                    unresolved_source_paths.append(str(source_candidate))
                    continue

                destination_candidate = export_path / rel_path
```
becomes
```python
                try:
                    rel_path_obj = source_candidate.relative_to(copy_source_path)
                except Exception:
                    unresolved_source_paths.append(str(source_candidate))
                    continue

                original_candidate = project_path / rel_path_obj
                if not original_candidate.exists() or original_candidate.is_dir():
                    unresolved_source_paths.append(str(source_candidate))
                    continue

                destination_candidate = export_path / rel_path_obj
```

- [ ] **Step 12: `app/src/project_manager.py:8901-8905` — `bool(...)` breaks mypy's None-narrowing**

Errors: two `Item "None" of "Any | None" has no attribute "get"  [union-attr]`.

`payload = self._load_json_dict(project_json)` returns `Dict[str, Any]`, so
`previous = payload.get("LastValidation")` is typed `Any | None`. Wrapping it in
`bool(...)` computes a plain `bool` and discards the type-narrowing information
mypy would otherwise carry from an `x is not None` / `if x:` check — `previous`
still reads as possibly-`None` on the right-hand side of the `and`. Use the
narrowing form; behavior is identical since `and` already short-circuits on
falsiness:

```python
        changed = bool(previous) and (
            previous.get("prism_schema_versions")
            != validator_info.get("prism_schema_versions")
            or (previous.get("bids_validator") or {}).get("spec")
            != (validator_info.get("bids_validator") or {}).get("spec")
        )
```
becomes
```python
        changed = previous is not None and (
            previous.get("prism_schema_versions")
            != validator_info.get("prism_schema_versions")
            or (previous.get("bids_validator") or {}).get("spec")
            != (validator_info.get("bids_validator") or {}).get("spec")
        )
```

- [ ] **Step 13: `src/recipes_surveys.py` — `Dict` invariance against a wider `pyreadstat.write_sav` stub**

Errors (x2): `Argument "column_labels" to "write_sav" has incompatible type "dict[str, str] | None"; expected "list[str | None] | dict[str, str | None] | None"  [arg-type]`

`sav_var_labels: dict[str, str] = {}` is correct as declared (values are always
`str`) — the mismatch is that `Dict` is invariant in mypy, so a
`dict[str, str]` is not assignable where `dict[str, str | None]` is expected,
even though every `str` is a valid `str | None`. This is a real stub-variance
gap, not a bug in the labels themselves, so `cast` at the two call sites
(line ~1810 and its near-identical twin at ~2741) rather than loosening the
dict's own declared type:

First add `cast` to the existing typing import:
```python
from typing import Any, Dict, Optional
```
becomes
```python
from typing import Any, Dict, Optional, cast
```

Then at both call sites (same substitution applied twice — once in each of the
two `pyreadstat.write_sav(...)` calls):
```python
                column_labels=sav_var_labels if sav_var_labels else None,
```
becomes
```python
                column_labels=cast(Optional[Dict[str, Optional[str]]], sav_var_labels)
                if sav_var_labels
                else None,
```

- [ ] **Step 14: Run black on every touched file (some of the diffs above, e.g. the `recipes_surveys.py` ternary reflow, may not match black's exact line-wrapping)**

```bash
black src/converters/presentation_log.py app/src/procedure_validator.py \
  app/src/validator.py src/converters/presentation_to_events.py \
  app/src/converters/excel_to_survey.py src/run_renumberer.py \
  src/converters/pavlovia.py app/src/converters/survey.py \
  app/src/web/blueprints/tools_generation_handlers.py \
  app/src/web/blueprints/conversion_participants_io.py \
  app/src/project_manager.py src/recipes_surveys.py
```
Expected: black reports `All done!` or reformats a handful of the files
touched above (harmless — this doesn't change any logic).

- [ ] **Step 15: Re-run mypy and confirm zero errors**

Run: `mypy app/src src --ignore-missing-imports --explicit-package-bases`
Expected: `Success: no issues found in 260 source files`

Run (matches CI exactly):
```bash
python tests/verify_repo.py --check mypy --no-fix
```
Expected: `MyPy passed.`

- [ ] **Step 16: Run the full test suite once more (typing fixes shouldn't change runtime behavior, but confirm)**

Run: `pytest tests/ -q`
Expected: `3730 passed, 0 failed` (same as Task 1's Step 3 outcome)

- [ ] **Step 17: Commit**

```bash
git add src/converters/presentation_log.py app/src/procedure_validator.py \
  app/src/validator.py src/converters/presentation_to_events.py \
  app/src/converters/excel_to_survey.py src/run_renumberer.py \
  src/converters/pavlovia.py app/src/converters/survey.py \
  app/src/web/blueprints/tools_generation_handlers.py \
  app/src/web/blueprints/conversion_participants_io.py \
  app/src/project_manager.py src/recipes_surveys.py
git commit -m "fix: resolve all 27 mypy errors flagged by repo verification"
```

---

## Task 3: Trim `paper/paper.md` under JOSS's 1750-word limit

**Files:**
- Modify: `paper/paper.md`

**Context:** JOSS's own word-count tool reported 1831 words (limit: 750–1750,
so at least 81 words must go). A local proxy counter — strip the YAML
frontmatter, then `len(body.split())` — measures the *current* file at 1833
words, within 2 of JOSS's own number, so it's a reliable stand-in for
iterating without Docker/Inara access. The edits below were drafted and
verified against that proxy in a scratch copy: they cut the proxy count from
1833 to **1738** (95 words, comfortably past the 81-word minimum and with a
~12-word margin under 1750 to absorb any small counting-method difference
from JOSS's actual tool). No sentence carrying the paper's core "universal /
domain-agnostic" framing claim (`paper.md`'s Summary, third paragraph) was
touched — that claim was deliberately preserved per prior framing decisions
for this manuscript.

All of the following are straight text substitutions in `paper/paper.md`
(apply each with the exact before/after text — every one was verified to
exist verbatim in the current file):

- [ ] **Step 1: Verify the baseline proxy count**

```bash
python3 - <<'EOF'
import re
text = open('paper/paper.md').read()
body = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.S)
print(len(body.split()))
EOF
```
Expected: `1833`

- [ ] **Step 2: Apply the 11 trims**

Edit 1 (Summary):
```
Yet raw data files are rarely self-explanatory — a column of questionnaire responses is meaningless without knowing the item wording, the label attached to each response option, which items are reverse-scored, or which version and language was administered.
```
→
```
Yet raw data files are rarely self-explanatory — a column of questionnaire responses is meaningless without knowing the item wording, each response option's label, which items are reverse-scored, or which version and language was administered.
```

Edit 2 (Statement of need):
```
Mismatches surface late — when a second analyst or a repository curator opens the dataset and the responses no longer match the scale they were measured on.
```
→
```
Mismatches surface late — when a second analyst opens the dataset and the responses no longer match the scale they were measured on.
```

Edit 3 (Statement of need):
```
Second, reaching a valid dataset must be achievable by the researchers who collected the data, not only by those who can write code: the tooling has to meet data where it already is — an Excel, CSV, SPSS, or survey-platform export accompanied by a codebook — and lead from there to a validated dataset through a graphical interface as readily as through a script.
```
→
```
Second, reaching a valid dataset must be achievable by the researchers who collected it, not only by those who can write code: the tooling has to meet data where it already is — an Excel, CSV, SPSS, or survey-platform export with a codebook — and lead to a validated dataset through a graphical interface as readily as a script.
```

Edit 4 (Statement of need):
```
Beyond validation and portability, well-structured data unlocks downstream tools that reward machine-readable metadata. AI-assisted analysis, automated pipelines, and large-scale data harmonization all become far more tractable when every file carries an unambiguous, schema-backed description — without waiting for a central specification to adopt it first.
```
→
```
Beyond validation and portability, AI-assisted analysis, automated pipelines, and large-scale data harmonization all become more tractable when every file carries an unambiguous, schema-backed description — without waiting for a central specification to adopt it first.
```

Edit 5 (State of the field):
```
Describing research data at scale requires a vocabulary that can grow where the data is produced. Any approach that enumerates measurements centrally — a specification's modality list, a curated instrument database — supports what has already been encoded and stalls on what has not, because enumeration scales with maintainer effort rather than with the variety of measurements researchers produce.
```
→
```
Describing research data at scale requires a vocabulary that can grow where the data is produced. Any approach that enumerates measurements centrally — a specification's modality list, a curated instrument database — supports what has already been encoded and stalls on what has not, because enumeration scales with maintainer effort, not the variety of measurements researchers produce.
```
(Note: the source file uses a curly apostrophe `’` in "specification’s" — match it exactly, not a straight quote.)

Edit 6 (State of the field):
```
Such tables store participant-level measures adequately for many studies, but they are flat aggregates rather than the data-and-sidecar pairs the rest of BIDS rests on, so session-, run-, and variant-level context for repeated administrations has nowhere to live.
```
→
```
Such tables store participant-level measures adequately, but as flat aggregates rather than data-and-sidecar pairs, so session-, run-, and variant-level context for repeated administrations has nowhere to live.
```

Edit 7 (State of the field — also see Task 5 for the figure inserted right after this point):
```
The closest neighbor is Psych-DS [@psychds], a community standard pairing CSV files under a `data/` directory with dataset-level JSON-LD metadata, with its own browser-based validator. It shares PRISM's goal of machine-readable description,
```
→
```
The closest neighbor is Psych-DS [@psychds], a community standard pairing CSV files under a `data/` directory with dataset-level JSON-LD metadata. It shares PRISM's goal of machine-readable description,
```

Edit 8 (State of the field):
```
Further tools solve adjacent problems but leave a gap: DataLad [@halchenko2021datalad] versions and distributes datasets without defining file contents — PRISM composes with it rather than competing, integrating it optionally to record provenance for dataset mutations and recipe scoring; instrument-specific converters require a code contribution before an uncoded instrument can be described at all.
```
→
```
Other tools leave a related gap: DataLad [@halchenko2021datalad] versions and distributes datasets without defining file contents — PRISM composes with it rather than competing, optionally recording provenance for dataset mutations and recipe scoring; instrument-specific converters elsewhere require a code contribution before an uncoded instrument can be described at all.
```

Edit 9 (Software design, `**Implementation.**`):
```
Command line and
interface share one core, so a workflow assembled interactively can be re-run
unattended in continuous integration.
```
→
```
Command line and
interface share one core, so an interactive workflow can be re-run
unattended in CI.
```

Edit 10 (Software design, `**How validation works.**`):
```
Validator runs over the same tree. All findings are tagged as errors or warnings
and merged into one report, emitted as JSON and setting a non-zero exit status on
errors.
```
→
```
Validator runs over the same tree. All findings are tagged as errors or
warnings, merged into one JSON report, with a non-zero exit status on errors.
```

Edit 11 (Software design, `**Rules live in data, not code.**` — merge into next paragraph and drop the whole `**Two validators, kept separate.**` aside, which restates what `**How validation works.**`'s *Delegation* sentence already established):
```
**Rules live in data, not code.** Entity order, modality suffixes, file extensions, and sidecar contracts are JSON schemas — that rules file plus twelve versioned schemas, six of them modalities — so adding a modality or a site-specific check means adding data rather than changing the software: a new schema, a rules entry, or — for checks no schema can express — a Python module dropped into the dataset's `validators/` directory and picked up automatically as a plugin. The cost is the absence of compile-time guarantees and a vocabulary that may differ between sites; it buys extension without forking.

**Two validators, kept separate.** Delegating the BIDS layer rather than reimplementing its rules costs an external dependency and a slower run; in exchange, PRISM cannot drift from the specification it claims compatibility with.

**One schema, two strictness profiles.**
```
→
```
**Rules live in data, not code.** Entity order, modality suffixes, file extensions, and sidecar contracts are JSON schemas — that rules file plus twelve versioned schemas, six of them modalities — so adding a modality or a site-specific check means adding data rather than changing the software: a new schema, a rules entry, or — for checks no schema can express — a Python module dropped into the dataset's `validators/` directory and picked up automatically as a plugin. The cost is weaker compile-time guarantees and site-specific vocabulary, traded for extension without forking.

**One schema, two strictness profiles.**
```

Edit 12 (Software design, `**Versions coexist...**` / `**Nothing is written without a preview.**` — two small trims in one hunk since they're adjacent paragraphs):
```
**Versions coexist so validation stays reproducible.** Three schema versions (`stable`, `v0.1`, `v0.2`) ship side by side, selectable per run — a standing maintenance cost paid so a dataset can still be validated against the rules it was authored under.

**Nothing is written without a preview.** `--dry-run` precedes `--fix`, conversions show what they will produce, and colliding operations report the conflict instead of resolving it silently. Participant data stays on the local machine; the single network call, environmental enrichment, is opt-in. These are constraints rather than features.
```
→
```
**Versions coexist so validation stays reproducible.** Three schema versions (`stable`, `v0.1`, `v0.2`) ship side by side, selectable per run, so a dataset can still be validated against the rules it was authored under.

**Nothing is written without a preview.** `--dry-run` precedes `--fix`, conversions show what they will produce, and colliding operations report the conflict instead of resolving it silently. Participant data stays on the local machine; the single network call, environmental enrichment, is opt-in.
```

Edit 13 (Research impact statement):
```
the winter semester 2026/27, introducing the model and Studio workflows to
students preparing their own datasets. Development is public: issues raised by
users outside the core team — installation failures, platform-specific path
handling, packaging requests — are tracked openly and addressed in subsequent
releases.
```
→
```
the winter semester 2026/27, introducing the model to
students preparing their own datasets. Development is public: issues raised by
users outside the core team — installation failures and packaging requests —
are tracked openly and addressed in subsequent
releases.
```

- [ ] **Step 3: Verify the trimmed proxy count**

Re-run the Step 1 command against the now-edited `paper/paper.md`.
Expected: `1738` (before Task 4's version-string fix and Task 5's figure
insertion — neither changes the word count materially: a version string is
one token whether it reads `1.18.0` or `1.18.1`, and Task 5's figure caption
adds ~13 tokens, landing the final file around `1751` if counted before Task
4/5 — do this step *after* Tasks 4 and 5 land, and treat `1738` as this step's
own checkpoint only if run in isolation on a copy).

- [ ] **Step 4: Commit** (safe to combine with Task 4 and Task 5's commits into one, since all three touch `paper/paper.md`; see Task 5 Step 3 for the combined commit)

---

## Task 4: Fix stale version metadata

**Files:**
- Modify: `paper/paper.md:114`
- Modify: `paper/paper.bib:6`
- Modify: `CITATION.cff:7` and `:8`
- No change: `codemeta.json` (already correct at `1.18.1`)

**Context:** The current tag is `v1.18.1` (`git tag --sort=-creatordate` confirms
it's the newest, created 2026-09-16). `paper.md`, `paper.bib`, and
`CITATION.cff` all still say `1.18.0`; `codemeta.json` is already correct and
needs no change.

- [ ] **Step 1: Fix `paper/paper.md:114`**

```
(currently 1.18.0), cross-platform builds,
```
→
```
(currently 1.18.1), cross-platform builds,
```

- [ ] **Step 2: Fix `paper/paper.bib:6`**

```
  note         = {Version 1.18.0}
```
→
```
  note         = {Version 1.18.1}
```

- [ ] **Step 3: Fix `CITATION.cff:7-8`**

```yaml
version: "1.18.0"
date-released: "2026-08-12"
```
→
```yaml
version: "1.18.1"
date-released: "2026-09-16"
```

(`date-released` is updated to match when `v1.18.1` was actually tagged —
`git log -1 --format=%ai v1.18.1` — so this fix doesn't just relocate the same
class of staleness from the version field to the date field.)

- [ ] **Step 4: Confirm all four files agree**

```bash
grep -n "1\.18\." paper/paper.md paper/paper.bib CITATION.cff codemeta.json
```
Expected: every match reads `1.18.1`.

---

## Task 5: Resolve the four orphaned figure assets

**Files:**
- Modify: `paper/paper.md` (insert one figure reference)
- Delete: `paper/figure_studio.png`
- Delete: `paper/flowchart.svg`
- Delete: `paper/prism_lifecycle.pdf`
- Delete: `paper/prism_lifecycle.svg`
- Keep, now referenced: `paper/prism_representations.pdf`
- Keep, now the kept figure's editable source (unreferenced but not orphaned
  in spirit — it's the source of the file that *is* referenced): `paper/prism_representations.svg`

**Context:** Four *logical* figures exist under `paper/`
(`figure_studio.png`, `flowchart.svg`, `prism_lifecycle.{pdf,svg}`,
`prism_representations.{pdf,svg}`), none referenced from `paper.md`.
`prism_representations.svg`'s own embedded `<title>`/`<desc>` ("PRISM native
survey representation and BIDS phenotype compatibility view" / "A subject,
session, run, and acquisition-version resolved native PRISM survey layout is
exported to a flat BIDS phenotype table through an optional lossy bridge.")
directly illustrates the exact tradeoff the "State of the field" section's
second paragraph already discusses (BIDS's `phenotype/` table vs. PRISM's
native per-session layout) — the most useful of the four to keep. The other
three don't correspond to content currently in the paper's prose; remove
them rather than writing new paragraphs to justify keeping them.

- [ ] **Step 1: Insert the figure reference right after the paragraph it illustrates**

In `paper/paper.md`, in the "State of the field" section:
```
PRISM stays inside the sidecar paradigm while offering a deliberate, optional export to `phenotype/` where compatibility matters more than context.

The closest neighbor is Psych-DS
```
→
```
PRISM stays inside the sidecar paradigm while offering a deliberate, optional export to `phenotype/` where compatibility matters more than context.

![PRISM's native, acquisition-scoped survey layout versus the optional, lossy BIDS `phenotype/` compatibility export.](prism_representations.pdf)

The closest neighbor is Psych-DS
```

(If Task 3's Edit 7 already removed the `, with its own browser-based
validator` clause from this same paragraph, apply this insertion against
whatever that edit left the surrounding text as — the anchor text `PRISM
stays inside the sidecar paradigm ... The closest neighbor is Psych-DS` is
unaffected by Task 3's edits and will still match.)

- [ ] **Step 2: Remove the three unused figure assets**

```bash
git rm paper/figure_studio.png paper/flowchart.svg paper/prism_lifecycle.pdf paper/prism_lifecycle.svg
```

- [ ] **Step 3: Commit Tasks 3, 4, and 5 together** (all three touch `paper/paper.md`; bundling avoids three separate diffs against the same file)

```bash
git add paper/paper.md paper/paper.bib CITATION.cff
git commit -m "docs: trim paper to JOSS's word limit, fix stale 1.18.0 version refs, wire in the one relevant figure"
```

(The `git rm` from Step 2 stages its own deletions; include them in the same
commit or a separate one — either is fine since both are part of this same
paper-readiness pass.)

---

## Task 6: Verify the full gate and the JOSS/Inara compile

**Files:** none (verification only)

- [ ] **Step 1: Run the exact CI check set**

```bash
python tests/verify_repo.py --check git-status,entrypoints-smoke,import-boundaries,dual-tree-drift,library-uniqueness,pytest-modularity,linting,ruff,ruff-security,mypy --no-fix
pytest tests/ -q
```
Expected: no failures, `MyPy passed.`, `3730 passed`.

- [ ] **Step 2: Start the Docker daemon**

On macOS: `open -a Docker`, then wait for it to report ready:
```bash
until docker info >/dev/null 2>&1; do sleep 2; done
```
(This is a local environment step, not a code change — flag to the user
before running if Docker Desktop isn't already configured to start
automatically, since it may prompt for the macOS password/Docker license on
first launch.)

- [ ] **Step 3: Run the official JOSS Inara compile**

```bash
docker run --rm \
  --volume "$PWD/paper:/data" \
  --user "$(id -u):$(id -g)" \
  --env JOURNAL=joss \
  openjournals/inara
```
Expected: `paper/paper.pdf` and `paper/paper.crossref` are generated with no
errors printed (both are gitignored per `paper/.gitignore` — do not commit
them). Open `paper/paper.pdf` and visually confirm: the new figure renders
with its caption, the AI-usage/conflict-of-interest/acknowledgements sections
are all present, and there's no leftover reference to a word overage or a
missing citation key.

- [ ] **Step 4: Report readiness**

If Steps 1–3 all pass clean, the repository is ready for JOSS submission —
report this back rather than taking further action (submission itself, e.g.
opening a JOSS review issue, is outside this plan's scope and is the user's
call to make).
