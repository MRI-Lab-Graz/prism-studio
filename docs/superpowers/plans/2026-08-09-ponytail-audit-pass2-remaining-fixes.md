# Ponytail Audit Pass 2 — Remaining Findings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the remaining unstarted findings (#8–#17) from `PONYTAIL-AUDIT.md`'s pass-2 report — dedup near-identical functions, delete dead JS options, and shrink a couple of hand-rolled string builders — without changing any observable behavior.

**Architecture:** Each finding is an independent dedup/shrink in an existing file; no new modules, no new dependencies. Where implementations differ only in a small policy knob (an edge case, a key prefix, a fallback message), the canonical version gains a keyword parameter and the call sites pass what they need — call sites keep their exact current behavior.

**Tech Stack:** Python 3 (backend, `pytest`), vanilla ES6 modules (frontend, no test runner covers these files — verify with `node --check` and manual reasoning about call sites).

## Global Constraints

- **Dual-tree gotcha** (`CLAUDE.md`): `src/` (top-level) and `app/src/` can silently diverge because `src.converters`/`src.web` etc. are namespace-package merges. Before editing any file this plan names, run `python3 -c "import <module> as m; print(m.__file__)"` for its import path and confirm it resolves to the file you're about to edit. Every file this plan touches was already verified to resolve to its physical `app/src/...` or `src/...` path at planning time (see each task's Files section) — re-verify before editing in case anything changed.
- **Test-monkeypatch gotcha** (learned earlier this session, the hard way): in `app/src/web/blueprints/`, route handlers of the shape `def api_x(): return _x()` are NOT dead passthrough wrappers — tests do `patch.object(module, "_x")`, which only works because the wrapper does a late name lookup of `_x` in the module namespace at call time. **Do not** touch any function matching that shape. None of the tasks below touch blueprint route wrappers, but if a task's diff accidentally lands near one, leave it alone.
- **No format-locked YAML/text builders**: two CITATION.cff YAML builders were already assessed in pass 1 — one (`src/converters/anc_export.py`) was safely converted to `yaml.safe_dump`; the other (`app/src/project_manager.py`) was deliberately left alone because 27+ tests lock its exact per-field quote formatting and a YAML folded block-scalar style that `yaml.safe_dump` can't reproduce without a custom representer that's equally complex. Don't reopen that one.
- **Preserve public signatures**: every task below is a refactor, not a behavior change. Any function/variable that appears in a test file's `import` statement, or is read via `getattr`/`monkeypatch.setattr` by name, must keep that exact name and call signature.
- **Verify before editing every file** in this plan with the one-liner in the dual-tree bullet above — do not skip it because this plan already ran it once; the codebase can move between planning and execution.
- Run the specific test file(s) named in each task immediately after that task's edit, before moving to the next task. Run the full suite only once, in the final task.

---

### Task 1: Dedup `_sanitize_answer_code_for_ls` in `survey.py`

**Files:**
- Modify: `app/src/converters/survey.py:175-214` (delete duplicate function + its constant, add an alias)
- Test: `tests/test_survey_value_offsets.py`, `tests/test_survey_base.py`, or run the full survey conversion suite (see step 4) — there is no test file dedicated to this private function by name.

**Interfaces:**
- Consumes: `app/src/converters/survey_processing.py`'s existing `_sanitize_answer_code_for_ls(code: str) -> str` (module-level, already defined at `survey_processing.py:85-96`, byte-identical logic to the copy being deleted).
- Produces: `survey.py`'s module-level name `_sanitize_answer_code_for_ls` continues to exist (as an alias), so the existing call site at `survey.py:246` (`sanitized = _sanitize_answer_code_for_ls(key)`, inside `_find_matching_level_key`) needs no change.

**Background:** `survey.py` already does `from . import survey_processing as _survey_processing` at line 91 and uses it elsewhere (e.g. `_survey_processing._normalize_item_value` at line 2212). It separately hand-rolls a second, byte-identical copy of `_sanitize_answer_code_for_ls` and its `_LS_ANSWER_CODE_MAX_LENGTH = 5` constant at lines 177 and 191-214. Delete the duplicate, alias the name instead.

- [ ] **Step 1: Verify the live file and confirm the two functions are still identical**

```bash
python3 -c "import app.src.converters.survey as m; print(m.__file__)"
python3 -c "import app.src.converters.survey_processing as m; print(m.__file__)"
```
Expected: both resolve under `app/src/converters/`.

```bash
sed -n '175,215p' app/src/converters/survey.py
sed -n '80,97p' app/src/converters/survey_processing.py
```
Confirm the two `_sanitize_answer_code_for_ls` bodies are still byte-identical (same regex, same truncation math, same `"n/a"/"na"` special case). If they've diverged, stop and re-plan this task — do not force a merge.

- [ ] **Step 2: Delete the duplicate and alias the canonical version**

In `app/src/converters/survey.py`, replace:

```python
_MISSING_TOKEN = "n/a"  # noqa: S105 - placeholder value for missing survey answers, not a credential
# LimeSurvey answer code max length (used for reverse lookup)
_LS_ANSWER_CODE_MAX_LENGTH = 5


def _normalize_run_id(value: object) -> str | None:
    text = sanitize_id(str(value).strip())
    if not text or text.lower() == "nan":
        return None
    label = text[4:] if text[:4].lower() == "run-" else text
    label = re.sub(r"[^A-Za-z0-9]+", "", label)
    if not label:
        return None
    return f"run-{label}"


def _sanitize_answer_code_for_ls(code: str) -> str:
    """Apply LimeSurvey answer code sanitization (for reverse lookup).

    This mirrors the logic in limesurvey_exporter._sanitize_answer_code()
    to allow matching truncated codes back to original level keys.

    LimeSurvey truncates answer codes to 5 chars using: first 3 + last 2 chars
    after removing non-alphanumeric characters.
    """
    # Handle n/a specially
    if code.lower() in ("n/a", "na"):
        return "na"

    # Remove non-alphanumeric characters
    sanitized = re.sub(r"[^a-zA-Z0-9]", "", code)

    if len(sanitized) <= _LS_ANSWER_CODE_MAX_LENGTH:
        return sanitized.lower()

    # For long codes: first 3 chars + last 2 chars
    prefix_len = _LS_ANSWER_CODE_MAX_LENGTH - 2  # 3
    suffix_len = 2
    abbreviated = sanitized[:prefix_len] + sanitized[-suffix_len:]
    return abbreviated.lower()
```

with:

```python
_MISSING_TOKEN = "n/a"  # noqa: S105 - placeholder value for missing survey answers, not a credential

# Reuse the canonical implementation (survey_processing already imported as
# _survey_processing above) instead of hand-rolling a second copy.
_sanitize_answer_code_for_ls = _survey_processing._sanitize_answer_code_for_ls


def _normalize_run_id(value: object) -> str | None:
    text = sanitize_id(str(value).strip())
    if not text or text.lower() == "nan":
        return None
    label = text[4:] if text[:4].lower() == "run-" else text
    label = re.sub(r"[^A-Za-z0-9]+", "", label)
    if not label:
        return None
    return f"run-{label}"
```

(`_normalize_run_id` is unrelated — kept verbatim, just shown for surrounding context so the diff anchors correctly. Do not touch it in this task; it's a different function from the `_normalize_run_entity` family handled in Task 3.)

- [ ] **Step 3: Confirm no other file imports the deleted names directly**

```bash
grep -rn "from.*survey import.*_sanitize_answer_code_for_ls\|survey\._sanitize_answer_code_for_ls\|survey\._LS_ANSWER_CODE_MAX_LENGTH" --include='*.py' . --exclude-dir=node_modules --exclude-dir=.git
```
Expected: no output (already verified empty at planning time — re-confirm).

- [ ] **Step 4: Run tests**

```bash
python3 -c "import app.src.converters.survey" && echo OK
python3 -m pytest tests/ -q -k "survey and (convert or limesurvey or value)" 2>&1 | tail -30
```
Expected: all pass, no `AttributeError`/`NameError` for `_sanitize_answer_code_for_ls` or `_LS_ANSWER_CODE_MAX_LENGTH`.

- [ ] **Step 5: Commit**

```bash
git add app/src/converters/survey.py
git commit -m "dedup: alias _sanitize_answer_code_for_ls to survey_processing's canonical copy"
```

---

### Task 2: Dedup `sanitize_id()` in `cli/commands/convert.py`

**Files:**
- Modify: `app/src/cli/commands/convert.py:1-42` (delete duplicate function, import canonical version)
- Test: `tests/test_convert_physio_cli.py` (imports `cmd_convert_physio` from this module)

**Interfaces:**
- Consumes: `app/src/utils/naming.py`'s existing `sanitize_id(id_str: str) -> str` (byte-identical body, already used elsewhere via `from ..utils.naming import sanitize_id` in `survey.py` and `from src.utils.naming import sanitize_id` in `project_registration.py`).
- Produces: `convert.py`'s module-level name `sanitize_id` continues to exist (now imported, not defined), so call sites at `convert.py:242-243` need no change.

- [ ] **Step 1: Verify the live file and confirm the two functions are still identical**

```bash
python3 -c "import app.src.cli.commands.convert" 2>&1 | tail -3
```
(This import will fail standalone with `ModuleNotFoundError: No module named 'helpers'` — that's expected; this module only imports cleanly inside the full test/CLI runtime with `app/` on `sys.path`. Don't treat that failure as a dual-tree problem; it's an unrelated `sys.path` requirement. Confirm via file existence instead:)

```bash
ls -la app/src/cli/commands/convert.py app/src/utils/naming.py
find src -path "*cli/commands/convert.py" -o -path "*utils/naming.py"
```
Expected: both are real files under `app/src/`, and the `find` under top-level `src/` returns nothing (no symlink/mirror to worry about).

```bash
sed -n '26,42p' app/src/cli/commands/convert.py
sed -n '21,37p' app/src/utils/naming.py
```
Confirm both `sanitize_id` bodies are still byte-identical (same umlaut replacement dict, same loop). If diverged, stop and re-plan.

- [ ] **Step 2: Delete the duplicate and import the canonical version**

In `app/src/cli/commands/convert.py`, replace:

```python
from src.cross_platform import normalize_path
from src.entity_rules import load_entity_rules


def sanitize_id(id_str):
    """Sanitize subject/session IDs by replacing German umlauts and special characters."""
    if not id_str:
        return id_str
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
    for char, repl in replacements.items():
        id_str = id_str.replace(char, repl)
    return id_str
```

with:

```python
from src.cross_platform import normalize_path
from src.entity_rules import load_entity_rules
from src.utils.naming import sanitize_id
```

- [ ] **Step 3: Confirm no test patches `cli.commands.convert.sanitize_id` expecting a locally-defined function**

```bash
grep -rn "commands.convert.*sanitize_id\|convert\.sanitize_id" tests/ --include='*.py'
```
Expected: no output, or only usages consistent with an imported name (monkeypatching an imported name via `monkeypatch.setattr(convert_module, "sanitize_id", ...)` still works identically whether `sanitize_id` was defined locally or imported — Python doesn't distinguish the two for attribute patching purposes, so this is safe either way; this check is just to confirm no test relies on `convert.sanitize_id is not naming.sanitize_id`).

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_convert_physio_cli.py tests/test_entity_rules_write_path.py tests/test_convert_get_json_hash.py -q 2>&1 | tail -30
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/src/cli/commands/convert.py
git commit -m "dedup: import sanitize_id from src.utils.naming instead of redefining it"
```

---

### Task 3: Consolidate `_normalize_run_entity` (3 divergent copies)

**Files:**
- Modify: `app/src/converters/survey_processing.py` (add the new canonical function)
- Modify: `app/src/converters/survey_core.py:110-140` (delete nested closure, call canonical)
- Modify: `app/src/converters/survey_io.py:73-83` (delete duplicate, call canonical with a flag)
- Modify: `app/src/web/blueprints/conversion_utils.py:121-131` (delete duplicate, import and call canonical with a flag)
- Test: run the survey conversion suite (step 6) — no test imports `_normalize_run_entity` by name in any of the three files.

**Interfaces:**
- Produces: `survey_processing.normalize_run_entity(value: object, *, nan_as_none: bool = False, raise_on_empty_label: bool = False) -> str | None` — new public (no leading underscore — it's cross-module now) function.
- Consumes (by the three call sites): that same signature.

**Background — the three existing copies differ only in two edge cases**, confirmed by reading all three bodies:

`survey_core.py:120-130` (nested inside `_build_bids_survey_filename`, no import needed elsewhere):
```python
def _normalize_run_entity(value: str | int | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    label = text[4:] if text[:4].lower() == "run-" else text
    label = re.sub(r"[^A-Za-z0-9]+", "", label)
    if not label:
        return None
    return f"run-{label}"
```

`survey_io.py:73-83` (module-level, has an extra `"nan"` check):
```python
def _normalize_run_entity(value: str | int | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    label = text[4:] if text[:4].lower() == "run-" else text
    label = re.sub(r"[^A-Za-z0-9]+", "", label)
    if not label:
        return None
    return f"run-{label}"
```

`conversion_utils.py:121-131` (module-level, raises instead of returning `None` when the label is empty *after* cleaning — but still returns `None`, not raises, when the raw input itself is empty):
```python
def _normalize_run_entity(run_value: object) -> str | None:
    text = str(run_value or "").strip()
    if not text:
        return None
    label = text[4:] if text[:4].lower() == "run-" else text
    label = re.sub(r"[^A-Za-z0-9]+", "", label)
    if not label:
        raise ValueError(
            "Invalid template version selection payload. Run must contain only letters and numbers."
        )
    return f"run-{label}"
```

`str(value).strip()` and `str(value or "").strip()` are equivalent when `value is None` (both produce `""`), so a single `value is None` guard up front covers both styles.

- [ ] **Step 1: Verify all three files are physical (not dual-tree mirrors)**

```bash
python3 -c "import src.converters.survey_core as m; print(m.__file__)"
python3 -c "import src.converters.survey_io as m; print(m.__file__)"
python3 -c "import src.converters.survey_processing as m; print(m.__file__)"
python3 -c "import src.web.blueprints.conversion_utils as m; print(m.__file__)"
```
Expected: all four resolve under `app/src/`.

- [ ] **Step 2: Re-read the three current bodies to confirm they still match the snippets above**

```bash
sed -n '110,140p' app/src/converters/survey_core.py
sed -n '65,85p' app/src/converters/survey_io.py
sed -n '115,132p' app/src/web/blueprints/conversion_utils.py
```
If any has changed since planning, stop and re-derive the parameterization before proceeding.

- [ ] **Step 3: Add the canonical function to `survey_processing.py`**

`survey_processing.py` currently has no `import re` re-export concern (it already imports `re` at the top — confirm with `grep -n "^import re" app/src/converters/survey_processing.py`). Add this function anywhere among the other module-level helpers (e.g. right after `_sanitize_answer_code_for_ls`, which Task 1 left untouched in this file):

```python
def normalize_run_entity(
    value: object,
    *,
    nan_as_none: bool = False,
    raise_on_empty_label: bool = False,
) -> str | None:
    """Normalize a BIDS `run-<label>` entity value.

    Strips an existing ``run-`` prefix, removes non-alphanumeric characters,
    and re-prefixes. Two call-site-specific edge cases are opt-in:

    - ``nan_as_none``: treat the literal string ``"nan"`` (pandas' stringified
      missing-float marker) the same as an empty value.
    - ``raise_on_empty_label``: raise ``ValueError`` (instead of returning
      ``None``) when the value is non-empty but becomes empty after removing
      non-alphanumeric characters (e.g. ``"---"``).
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or (nan_as_none and text.lower() == "nan"):
        return None
    label = text[4:] if text[:4].lower() == "run-" else text
    label = re.sub(r"[^A-Za-z0-9]+", "", label)
    if not label:
        if raise_on_empty_label:
            raise ValueError(
                "Invalid template version selection payload. Run must contain only letters and numbers."
            )
        return None
    return f"run-{label}"
```

- [ ] **Step 4: Update `survey_core.py`**

`survey_core.py` does not currently import `survey_processing`. Add the import near its other `src.*`/local imports (after the `from src.entity_rules import load_entity_rules` line):

```python
from src.entity_rules import load_entity_rules
from src.converters import survey_processing as _survey_processing
```

Then replace the nested closure and its call:

```python
def _build_bids_survey_filename(
    sub_id: str,
    ses_id: str,
    task: str,
    run: str | int | None = None,
    extension: str = "tsv",
    acq: str | None = None,
) -> str:
    """Build a BIDS-compliant survey filename."""

    def _normalize_run_entity(value: str | int | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        label = text[4:] if text[:4].lower() == "run-" else text
        label = re.sub(r"[^A-Za-z0-9]+", "", label)
        if not label:
            return None
        return f"run-{label}"

    parts = [sub_id, ses_id, f"task-{task}"]
    if acq:
        parts.append(f"acq-{acq}")
    normalized_run = _normalize_run_entity(run)
    if normalized_run is not None:
        parts.append(normalized_run)
    parts.append(_SURVEY_SUFFIX)  # Add suffix without extension
    return "_".join(parts) + f".{extension}"
```

with:

```python
def _build_bids_survey_filename(
    sub_id: str,
    ses_id: str,
    task: str,
    run: str | int | None = None,
    extension: str = "tsv",
    acq: str | None = None,
) -> str:
    """Build a BIDS-compliant survey filename."""
    parts = [sub_id, ses_id, f"task-{task}"]
    if acq:
        parts.append(f"acq-{acq}")
    normalized_run = _survey_processing.normalize_run_entity(run)
    if normalized_run is not None:
        parts.append(normalized_run)
    parts.append(_SURVEY_SUFFIX)  # Add suffix without extension
    return "_".join(parts) + f".{extension}"
```

- [ ] **Step 5: Update `survey_io.py`**

`survey_io.py` already imports `from . import survey_processing as _survey_processing` (line 19). Replace:

```python
def _normalize_run_entity(value: str | int | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    label = text[4:] if text[:4].lower() == "run-" else text
    label = re.sub(r"[^A-Za-z0-9]+", "", label)
    if not label:
        return None
    return f"run-{label}"
```

with:

```python
def _normalize_run_entity(value: str | int | None) -> str | None:
    return _survey_processing.normalize_run_entity(value, nan_as_none=True)
```

(Keeping the thin module-level `_normalize_run_entity` wrapper here — rather than rewriting all 4 call sites in this file — because `survey_io.py` calls it in 4 places, including inside a `.map(_normalize_run_entity)` pandas call at line 261 that needs a plain unary callable, not a partially-applied one.)

- [ ] **Step 6: Update `conversion_utils.py`**

Add an import near its existing `src.*` imports (after `from src.utils.naming import normalize_filename`):

```python
from src.utils.naming import normalize_filename
from src.converters.survey_processing import normalize_run_entity as _normalize_run_entity
```

Then delete the duplicate function body:

```python
def _normalize_run_entity(run_value: object) -> str | None:
    text = str(run_value or "").strip()
    if not text:
        return None
    label = text[4:] if text[:4].lower() == "run-" else text
    label = re.sub(r"[^A-Za-z0-9]+", "", label)
    if not label:
        raise ValueError(
            "Invalid template version selection payload. Run must contain only letters and numbers."
        )
    return f"run-{label}"
```

Since the call sites at `conversion_utils.py:174,216` call `_normalize_run_entity(run_value)` with one positional arg and expect the raise-on-empty-label behavior, and the imported alias is a plain function (not pre-bound with `raise_on_empty_label=True`), update those two call sites too:

```bash
grep -n "_normalize_run_entity(run_value)" app/src/web/blueprints/conversion_utils.py
```
Replace both occurrences of `_normalize_run_entity(run_value)` with `_normalize_run_entity(run_value, raise_on_empty_label=True)`.

- [ ] **Step 7: Confirm no external caller imports the deleted names directly**

```bash
grep -rn "from.*survey_core import.*_normalize_run_entity\|from.*survey_io import.*_normalize_run_entity\|from.*conversion_utils import.*_normalize_run_entity" --include='*.py' . --exclude-dir=node_modules --exclude-dir=.git
```
Expected: no output (all three were confirmed module-private with no external importers at planning time).

- [ ] **Step 8: Run tests**

```bash
python3 -c "import app.src.converters.survey_core, app.src.converters.survey_io, app.src.web.blueprints.conversion_utils" && echo OK
python3 -m pytest tests/ -q -k "survey and (core or io or filename or run)" 2>&1 | tail -30
python3 -m pytest tests/test_conversion_utils_tabular_reader.py tests/test_web_blueprints_conversion.py -q 2>&1 | tail -30
```
Expected: all pass. Pay special attention to any test exercising `run-` entity edge cases (empty run after stripping non-alnum chars, `"nan"` run values) — those are exactly the behaviors this task must preserve per call site.

- [ ] **Step 9: Commit**

```bash
git add app/src/converters/survey_processing.py app/src/converters/survey_core.py app/src/converters/survey_io.py app/src/web/blueprints/conversion_utils.py
git commit -m "dedup: consolidate 3 divergent _normalize_run_entity copies into survey_processing.normalize_run_entity"
```

---

### Task 4: Consolidate `_deep_merge` (2 copies)

**Files:**
- Modify: `app/src/validator.py:238-251` (replace body with the more general algorithm)
- Modify: `app/src/web/blueprints/tools_helpers.py:256-265` (delete duplicate, import canonical)
- Test: `tests/test_participants_backend_schema_canonicalization.py`, plus the validator suite (step 5)

**Interfaces:**
- Produces: `src.validator._deep_merge(base: object, override: object) -> object` — same name, widened type signature (still correct for the narrower `dict, dict` case every call site actually uses).
- Consumes (`tools_helpers.py`): `from src.validator import _deep_merge`.

**Background:** Both implementations produce identical output for `dict, dict` input — the only case either is ever called with (confirmed: `validator.py`'s only call site is `_deep_merge(root_data, subject_data)` at line 426, both already `dict`; `tools_helpers.py`'s call sites recurse only into dict values). `tools_helpers.py`'s version (`app/src/web/blueprints/tools_helpers.py:256-265`) is strictly more general — it handles non-dict top-level arguments by returning `override` directly, which `validator.py`'s version would crash on (`base.copy()` on a non-dict). Since blueprints already import backend modules like `src.validator` elsewhere in this codebase, and `validator.py` has no dependency on `web/blueprints/`, migrate the more general body into `validator.py` and have `tools_helpers.py` import it.

- [ ] **Step 1: Verify both files are physical and re-read current bodies**

```bash
python3 -c "import src.validator as m; print(m.__file__)"
python3 -c "import src.web.blueprints.tools_helpers as m; print(m.__file__)"
sed -n '238,251p' app/src/validator.py
sed -n '256,265p' app/src/web/blueprints/tools_helpers.py
```
Confirm they still match the bodies shown above. If either changed, re-derive before proceeding.

- [ ] **Step 2: Confirm no circular import risk**

```bash
grep -n "^from\|^import" app/src/validator.py | grep -i "web\|blueprint"
```
Expected: no output (validator.py imports nothing from `web/blueprints/`, so `tools_helpers.py` importing `validator.py` is safe).

- [ ] **Step 3: Widen `validator.py`'s `_deep_merge`**

Replace:

```python
def _deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries. Override values take precedence.

    For nested dicts, recursively merge. For other types, override replaces base.
    This implements BIDS inheritance where subject-level values override root-level.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
```

with:

```python
def _deep_merge(base: object, override: object) -> object:
    """
    Deep merge two values. Override values take precedence.

    For nested dicts, recursively merge; for anything else, override replaces
    base outright. This implements BIDS inheritance where subject-level
    values override root-level values.
    """
    if isinstance(base, dict) and isinstance(override, dict):
        result = dict(base)
        for key, value in override.items():
            if key in result:
                result[key] = _deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    return override
```

- [ ] **Step 4: Update `tools_helpers.py`**

Replace:

```python
def _deep_merge(base: object, override: object) -> object:
    if isinstance(base, dict) and isinstance(override, dict):
        out = dict(base)
        for key, value in override.items():
            if key in out:
                out[key] = _deep_merge(out[key], value)
            else:
                out[key] = value
        return out
    return override
```

with an import near the top of the file (check current imports with `sed -n '1,12p' app/src/web/blueprints/tools_helpers.py` first and place it alongside the other `src.*` imports):

```python
from src.validator import _deep_merge
```

(Delete the function body entirely — this is now a bare import, no local wrapper needed, since the signature is unchanged.)

- [ ] **Step 5: Run tests**

```bash
python3 -c "import app.src.validator, app.src.web.blueprints.tools_helpers" && echo OK
python3 -m pytest tests/test_participants_backend_schema_canonicalization.py tests/test_runner.py -q 2>&1 | tail -30
python3 -m pytest tests/ -q -k "validator or template_editor" 2>&1 | tail -30
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/src/validator.py app/src/web/blueprints/tools_helpers.py
git commit -m "dedup: consolidate _deep_merge into src.validator, import it from tools_helpers"
```

---

### Task 5: Consolidate `sync_survey_keys.py` / `sync_biometrics_keys.py`

**Files:**
- Create: `app/src/maintenance/_sync_library_keys.py` (new shared implementation)
- Modify: `src/maintenance/sync_survey_keys.py` (thin wrapper)
- Modify: `src/maintenance/sync_biometrics_keys.py` (thin wrapper)
- Test: `tests/test_maintenance_scripts.py`

**Interfaces:**
- Produces: `_sync_library_keys(library_dir, *, default_library_subpath: tuple[str, ...], preferred_template_name: str, reset_study_values: bool, skip_item_prefix: bool) -> None`
- Consumes (both wrappers): that signature, plus each keeps its own public `sync_survey_keys(library_dir=None)` / `sync_biometrics_keys(library_dir=None)` entry point unchanged (both are imported by name in `app/src/cli/commands/library.py:31-37` and directly by `tests/test_maintenance_scripts.py`).

**Background — confirmed via full file reads.** `sync_survey_keys.py` (89 lines) and `sync_biometrics_keys.py` (84 lines) run the identical algorithm: pick a template JSON file from a library directory, then backfill missing top-level/`Study`/`Technical` keys into every other file in that directory. They differ only in:
1. Default library subfolder: `library/survey` vs `library/biometrics`.
2. Preferred template filename: `survey-bdi.json` vs `biometrics-cmj.json` (falls back to `files[0]` either way).
3. Top-level key copy: survey skips keys starting with `item_` (`if k not in data and not k.startswith("item_")`); biometrics does not skip any prefix (`if k not in data`).
4. After copying the `Study` block, survey additionally resets every value in it to `""`; biometrics does not.

**Important — first check where `src/maintenance/` physically lives** (this plan assumes `src/maintenance/` is a real directory, not a dual-tree mirror of `app/src/maintenance/` — verify before creating the new shared file under `app/src/maintenance/`, since if `src/maintenance/` turns out to be the live side instead, the new shared file must go there):

- [ ] **Step 1: Verify dual-tree status and re-read both files**

```bash
python3 -c "import src.maintenance.sync_survey_keys as m; print(m.__file__)"
python3 -c "import src.maintenance.sync_biometrics_keys as m; print(m.__file__)"
ls -la src/maintenance/ app/src/maintenance/ 2>&1
```
If both resolve to `src/maintenance/...` (not `app/src/...`), and there is no `app/src/maintenance/` directory at all, put the new shared helper at `src/maintenance/_sync_library_keys.py` instead of `app/src/maintenance/_sync_library_keys.py` — adjust every path in this task accordingly before continuing. Confirm with:

```bash
sed -n '1,89p' src/maintenance/sync_survey_keys.py
sed -n '1,84p' src/maintenance/sync_biometrics_keys.py
```
and check both still match the bodies described above.

- [ ] **Step 2: Write the shared implementation**

Create `src/maintenance/_sync_library_keys.py` (adjust to `app/src/maintenance/_sync_library_keys.py` if Step 1 found the live tree is under `app/src/`):

```python
"""Shared key-synchronization logic for the survey/biometrics library maintenance scripts."""

import json
import os
from pathlib import Path


def _sync_library_keys(
    library_dir,
    *,
    default_relative_path: tuple,
    preferred_template_name: str,
    reset_study_values: bool,
    skip_item_prefix: bool,
) -> None:
    if library_dir is None:
        library_dir = Path(__file__).resolve().parent.parent.parent
        for part in default_relative_path:
            library_dir = library_dir / part
    else:
        library_dir = Path(library_dir)

    if not library_dir.exists():
        print(f"Error: Library directory {library_dir} does not exist.")
        return

    files = [f for f in os.listdir(library_dir) if f.endswith(".json")]
    if not files:
        print(f"No JSON files found in {library_dir}")
        return

    template_file = preferred_template_name if preferred_template_name in files else files[0]

    with open(os.path.join(library_dir, template_file), "r") as f:
        template = json.load(f)

    template_keys = set(template.keys())
    template_study_keys = set(template.get("Study", {}).keys())
    template_tech_keys = set(template.get("Technical", {}).keys())

    for filename in files:
        if filename == template_file:
            continue

        filepath = os.path.join(library_dir, filename)
        with open(filepath, "r") as f:
            data = json.load(f)

        changed = False

        # Check top level
        for k in template_keys:
            if skip_item_prefix and k.startswith("item_"):
                continue
            if k not in data:
                if k in ["Technical", "Study", "I18n", "Metadata", "Scoring", "Normative"]:
                    data[k] = template[k].copy()
                    if reset_study_values and k == "Study":
                        for sk in data[k]:
                            data[k][sk] = ""
                    changed = True
                # else: likely an item or something else, skip

        # Check Study
        if "Study" in data:
            for k in template_study_keys:
                if k not in data["Study"]:
                    data["Study"][k] = ""
                    changed = True

        # Check Technical
        if "Technical" in data:
            for k in template_tech_keys:
                if k not in data["Technical"]:
                    data["Technical"][k] = ""
                    changed = True

        if changed:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            print(f"✅ Synchronized keys for {filename}")
        else:
            print(f"ℹ️ {filename} is already synchronized")
```

**Note the one subtlety in this merge**: the original `sync_survey_keys.py` only skips `item_`-prefixed keys in the "not in data" branch (`if k not in data and not k.startswith("item_")`), i.e. it evaluates `k not in data` first — meaning an `item_`-prefixed key that's already present is never touched either way, and one that's absent is simply never backfilled. The shared version's `if skip_item_prefix and k.startswith("item_"): continue` followed by `if k not in data:` is logically equivalent (both end up doing nothing for an absent `item_`-prefixed key when `skip_item_prefix=True`, and both back it in when `skip_item_prefix=False` — verify this with Step 4's behavior-equivalence check before trusting it blindly).

- [ ] **Step 3: Rewrite the two wrappers**

Replace the full contents of `src/maintenance/sync_survey_keys.py` with:

```python
from ._sync_library_keys import _sync_library_keys


def sync_survey_keys(library_dir=None):
    _sync_library_keys(
        library_dir,
        default_relative_path=("library", "survey"),
        preferred_template_name="survey-bdi.json",
        reset_study_values=True,
        skip_item_prefix=True,
    )


if __name__ == "__main__":
    sync_survey_keys()
```

Replace the full contents of `src/maintenance/sync_biometrics_keys.py` with:

```python
from ._sync_library_keys import _sync_library_keys


def sync_biometrics_keys(library_dir=None):
    _sync_library_keys(
        library_dir,
        default_relative_path=("library", "biometrics"),
        preferred_template_name="biometrics-cmj.json",
        reset_study_values=False,
        skip_item_prefix=False,
    )


if __name__ == "__main__":
    sync_biometrics_keys()
```

- [ ] **Step 4: Behavior-equivalence check before running the real test suite**

Write a throwaway script (do not commit) that runs both the OLD algorithm (paste the original bodies) and the NEW wrapper against the same set of temp fixture files (reuse the fixtures `tests/test_maintenance_scripts.py` builds — read that file first to see its fixture-building helpers), and diff the resulting JSON files byte-for-byte. This is the cheapest way to catch a parameterization mistake before it shows up as a subtle test failure.

```bash
sed -n '1,100p' tests/test_maintenance_scripts.py
```
Use its fixture patterns to build two temp dirs, run old vs. new, `diff -r` the outputs. Delete the throwaway script when done — it's a verification aid, not a deliverable.

- [ ] **Step 5: Run tests**

```bash
python3 -c "import src.maintenance.sync_survey_keys, src.maintenance.sync_biometrics_keys" && echo OK
python3 -m pytest tests/test_maintenance_scripts.py -q 2>&1 | tail -40
```
Expected: all pass, including the "missing Scoring/Normative/Metadata keys" and "missing keys" edge-case tests referenced at `tests/test_maintenance_scripts.py:215,246`.

- [ ] **Step 6: Confirm the CLI entrypoint still imports both by name correctly**

```bash
grep -n "sync_survey_keys\|sync_biometrics_keys" app/src/cli/commands/library.py
python3 -m pytest tests/ -q -k "library and sync" 2>&1 | tail -20
```

- [ ] **Step 7: Commit**

```bash
git add src/maintenance/_sync_library_keys.py src/maintenance/sync_survey_keys.py src/maintenance/sync_biometrics_keys.py
git commit -m "dedup: consolidate sync_survey_keys/sync_biometrics_keys into shared _sync_library_keys"
```

---

### Task 6: Consolidate `inspect_pyreadstat_write_support` / `inspect_pandas_support`

**Files:**
- Modify: `src/runtime_dependencies.py` (add shared helper, rewrite both public functions as thin callers)
- Test: `tests/test_runtime_dependencies.py`, `tests/test_tools_runtime_capabilities_route.py`

**Interfaces:**
- Produces (private, module-internal only — not imported elsewhere): `_inspect_module_support(module_name: str, bundle_root, *, write_attr: str, version_attrs: tuple, keys: dict) -> dict`
- Preserves exactly: `inspect_pyreadstat_write_support(bundle_root=None) -> dict` and `inspect_pandas_support(bundle_root=None) -> dict` — same names, same signatures, same **output dict keys** (this is the part that needs care — see Background).

**Background — the output dict keys are NOT uniformly prefixed, by design.** `app/src/web/blueprints/tools.py:1624-1625` does:
```python
payload = inspect_pyreadstat_write_support()
payload.update(inspect_pandas_support())
```
which merges both dicts into one `payload`. `inspect_pandas_support`'s keys are all `pandas_`-prefixed (`pandas_importable`, `pandas_dataframe_support`, `pandas_namespace_bundle_stub`, `pandas_module_file`, `pandas_module_path`, `pandas_available_attrs`, `pandas_bundle_entries`, `pandas_error`) specifically so they don't collide with `inspect_pyreadstat_write_support`'s keys when merged — but `inspect_pyreadstat_write_support`'s own keys are only *partially* prefixed: `pyreadstat_importable` and `pyreadstat_write_support` are prefixed, but `namespace_bundle_stub`, `module_file`, `module_path`, `available_attrs`, `bundle_entries`, `error` are **not**. `tests/test_runtime_dependencies.py` asserts these exact unprefixed key names (e.g. `details["namespace_bundle_stub"]`, `details["available_attrs"]`, `details["bundle_entries"]`, `details["error"]`) — see lines 25-28, 52-55, 78-80, 93-94. Do not "fix" this inconsistency; reproduce it exactly via an explicit key-name map.

- [ ] **Step 1: Verify the live file and re-read the current bodies**

```bash
python3 -c "import src.runtime_dependencies as m; print(m.__file__)"
cat src/runtime_dependencies.py
```
Confirm it still matches the two near-duplicate functions described above (lines 10-137 at planning time). If it changed, re-derive the key map before proceeding.

- [ ] **Step 2: Write the shared helper and rewrite both public functions**

Replace the entire contents of `src/runtime_dependencies.py` with:

```python
"""Runtime dependency probes shared by CLI, web, and bundle smoke checks."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any


def _inspect_module_support(
    module_name: str,
    bundle_root: str | Path | None,
    *,
    write_attr: str,
    version_attrs: tuple[str, ...],
    keys: dict[str, str],
) -> dict[str, Any]:
    """Describe whether `module_name` is importable and exposes `write_attr`.

    `keys` maps the generic internal field names (importable, write_support,
    namespace_bundle_stub, module_file, module_path, available_attrs,
    bundle_entries, error) to the actual output dict key names, since
    `inspect_pyreadstat_write_support` and `inspect_pandas_support` use
    different (and only partially symmetric) key-prefixing conventions so
    their results can be dict-merged into one payload without colliding.
    """

    bundle_entries: list[str] = []
    normalized_bundle_root: Path | None = None
    if bundle_root is not None:
        normalized_bundle_root = Path(bundle_root).resolve()
        bundle_entries = sorted(
            path.name for path in normalized_bundle_root.glob(f"{module_name}*")
        )

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        return {
            keys["importable"]: False,
            keys["write_support"]: False,
            keys["namespace_bundle_stub"]: False,
            keys["module_file"]: None,
            keys["module_path"]: [],
            keys["available_attrs"]: [],
            keys["bundle_entries"]: bundle_entries,
            keys["error"]: f"{type(exc).__name__}: {exc}",
        }
    except Exception as exc:
        return {
            keys["importable"]: False,
            keys["write_support"]: False,
            keys["namespace_bundle_stub"]: False,
            keys["module_file"]: None,
            keys["module_path"]: [],
            keys["available_attrs"]: [],
            keys["bundle_entries"]: bundle_entries,
            keys["error"]: f"{type(exc).__name__}: {exc}",
        }

    module_file = getattr(module, "__file__", None)
    module_path = [str(Path(path).resolve()) for path in getattr(module, "__path__", [])]
    available_attrs = [name for name in version_attrs if hasattr(module, name)]

    namespace_bundle_stub = False
    if normalized_bundle_root is not None and bundle_entries:
        bundled_namespace_path = str((normalized_bundle_root / module_name).resolve())
        namespace_bundle_stub = module_file is None and bundled_namespace_path in module_path

    return {
        keys["importable"]: True,
        keys["write_support"]: hasattr(module, write_attr),
        keys["namespace_bundle_stub"]: namespace_bundle_stub,
        keys["module_file"]: module_file,
        keys["module_path"]: module_path,
        keys["available_attrs"]: available_attrs,
        keys["bundle_entries"]: bundle_entries,
        keys["error"]: None,
    }


def inspect_pyreadstat_write_support(
    bundle_root: str | Path | None = None,
) -> dict[str, Any]:
    """Describe whether pyreadstat is importable and exposes SPSS write support."""
    return _inspect_module_support(
        "pyreadstat",
        bundle_root,
        write_attr="write_sav",
        version_attrs=("__version__", "read_sav", "write_sav", "read_dta", "write_dta"),
        keys={
            "importable": "pyreadstat_importable",
            "write_support": "pyreadstat_write_support",
            "namespace_bundle_stub": "namespace_bundle_stub",
            "module_file": "module_file",
            "module_path": "module_path",
            "available_attrs": "available_attrs",
            "bundle_entries": "bundle_entries",
            "error": "error",
        },
    )


def inspect_pandas_support(bundle_root: str | Path | None = None) -> dict[str, Any]:
    """Describe whether pandas is importable and exposes core dataframe APIs."""
    return _inspect_module_support(
        "pandas",
        bundle_root,
        write_attr="DataFrame",
        version_attrs=("__version__", "DataFrame", "Series", "read_csv"),
        keys={
            "importable": "pandas_importable",
            "write_support": "pandas_dataframe_support",
            "namespace_bundle_stub": "pandas_namespace_bundle_stub",
            "module_file": "pandas_module_file",
            "module_path": "pandas_module_path",
            "available_attrs": "pandas_available_attrs",
            "bundle_entries": "pandas_bundle_entries",
            "error": "pandas_error",
        },
    )


def has_pyreadstat_write_support() -> bool:
    """Return whether pyreadstat can write SPSS .sav files in this runtime."""

    details = inspect_pyreadstat_write_support()
    return bool(details["pyreadstat_write_support"])
```

- [ ] **Step 3: Confirm `tests/test_runtime_dependencies.py`'s monkeypatch target still exists**

That test file does `monkeypatch.setattr(runtime_dependencies.importlib, "import_module", ...)` — this still works unchanged since `_inspect_module_support` calls `importlib.import_module` at module scope in the same file. Re-read `tests/test_runtime_dependencies.py:58-65` — it also does `monkeypatch.setattr(runtime_dependencies, "inspect_pyreadstat_write_support", lambda bundle_root=None: {"pyreadstat_write_support": False})`, which still works unchanged since `inspect_pyreadstat_write_support` remains a real module-level name.

- [ ] **Step 4: Run tests**

```bash
python3 -c "import src.runtime_dependencies" && echo OK
python3 -m pytest tests/test_runtime_dependencies.py tests/test_tools_runtime_capabilities_route.py -q 2>&1 | tail -40
```
Expected: all pass, including exact key-name assertions.

- [ ] **Step 5: Sanity-check the real (non-mocked) merge still works**

```bash
python3 -c "
from src.runtime_dependencies import inspect_pyreadstat_write_support, inspect_pandas_support
payload = inspect_pyreadstat_write_support()
payload.update(inspect_pandas_support())
import json
print(json.dumps(payload, indent=2, default=str))
"
```
Expected: one combined dict with both pyreadstat's partially-prefixed keys and pandas's fully-prefixed keys, no key collisions, no `KeyError`.

- [ ] **Step 6: Commit**

```bash
git add src/runtime_dependencies.py
git commit -m "dedup: consolidate inspect_pyreadstat_write_support/inspect_pandas_support into _inspect_module_support"
```

---

### Task 7: Consolidate the import-bootstrap-retry pattern in `limesurvey.py`

**Files:**
- Modify: `src/converters/limesurvey.py:21-87`
- Test: `tests/test_limesurvey_utils.py` and the full limesurvey suite (step 5)

**Interfaces:**
- Produces (module-private): `_import_with_bootstrap(import_fn: Callable[[], Any], *, catch: tuple = (ImportError,)) -> Any`
- Behavior must stay split into two shapes: the first block (ItemRegistry/version_merger names) silently leaves everything `None` if even the bootstrapped retry fails; the second and third blocks (survey_base/naming, csv) let a second failure propagate as an uncaught exception. Preserve this difference — do not silently swallow errors in blocks 2/3.

**Background — re-read the current code first**, this task's exact line ranges may drift with earlier tasks' edits to this same file (unlikely, since Task 8 also touches this file but a different function). Re-verify:

```bash
sed -n '1,90p' src/converters/limesurvey.py
```

Current shape (confirmed at planning time, lines 21-87):

```python
def _bootstrap_import_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_root = repo_root / "app"

    for candidate in (repo_root, app_root):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)


# Import item registry for collision detection
ItemRegistry: Any = None
ItemCollisionError: Any = None
merge_survey_versions: Callable[..., Any] | None = None
save_merged_template: Callable[..., Any] | None = None
detect_version_name_from_import: Callable[..., Any] | None = None

try:
    from src.converters.item_registry import (
        ItemRegistry as _ItemRegistry,
        ItemCollisionError as _ItemCollisionError,
    )
    from src.converters.version_merger import (
        merge_survey_versions as _merge_survey_versions,
        save_merged_template as _save_merged_template,
        detect_version_name_from_import as _detect_version_name_from_import,
    )

    ItemRegistry = _ItemRegistry
    ItemCollisionError = _ItemCollisionError
    merge_survey_versions = _merge_survey_versions
    save_merged_template = _save_merged_template
    detect_version_name_from_import = _detect_version_name_from_import
except ImportError:
    _bootstrap_import_path()
    try:
        from src.converters.item_registry import (
            ItemRegistry as _ItemRegistry,
            ItemCollisionError as _ItemCollisionError,
        )
        from src.converters.version_merger import (
            merge_survey_versions as _merge_survey_versions,
            save_merged_template as _save_merged_template,
            detect_version_name_from_import as _detect_version_name_from_import,
        )

        ItemRegistry = _ItemRegistry
        ItemCollisionError = _ItemCollisionError
        merge_survey_versions = _merge_survey_versions
        save_merged_template = _save_merged_template
        detect_version_name_from_import = _detect_version_name_from_import
    except ImportError:
        pass

try:
    from src.converters.survey_base import load_survey_library as load_schemas
    from src.utils.naming import sanitize_task_name
except (ImportError, ValueError):
    _bootstrap_import_path()
    from src.converters.survey_base import load_survey_library as load_schemas
    from src.utils.naming import sanitize_task_name

try:
    from src.converters.csv import process_dataframe  # noqa: E402
except ImportError:
    _bootstrap_import_path()
    from src.converters.csv import process_dataframe  # noqa: E402
```

- [ ] **Step 1: Verify the live file**

```bash
python3 -c "import src.converters.limesurvey as m; print(m.__file__)"
```
Expected: resolves under `app/src/converters/` per the `converters.csv`-style dual-tree bridging already documented in `CLAUDE.md` — confirm, don't assume.

- [ ] **Step 2: Add the shared retry helper**

Right after `_bootstrap_import_path`'s definition, add:

```python
def _import_with_bootstrap(import_fn, *, catch=(ImportError,)):
    """Run `import_fn`; on failure, add repo/app roots to sys.path and retry once.

    If the retry also fails, the exception propagates to the caller — callers
    that want a silent fallback (leaving names as their pre-declared default)
    must wrap the call in their own try/except.
    """
    try:
        return import_fn()
    except catch:
        _bootstrap_import_path()
        return import_fn()
```

- [ ] **Step 3: Rewrite the three import blocks to use it**

Replace the entire block from `try:` (item registry) through the final `except ImportError:\n    _bootstrap_import_path()\n    from src.converters.csv import process_dataframe  # noqa: E402` with:

Use plain nested-function-with-`from`-imports (not `__import__(..., fromlist=[...])` — that style is harder to read than a plain `from ... import ...` statement and is exactly the "technically shorter, actually more complex" trap flagged in pass 1's CITATION.cff finding), matching the style already used for the item-registry block:

```python
def _import_item_registry_and_merger():
    from src.converters.item_registry import (
        ItemRegistry as item_registry_cls,
        ItemCollisionError as item_collision_error_cls,
    )
    from src.converters.version_merger import (
        merge_survey_versions as merge_survey_versions_fn,
        save_merged_template as save_merged_template_fn,
        detect_version_name_from_import as detect_version_name_from_import_fn,
    )

    return (
        item_registry_cls,
        item_collision_error_cls,
        merge_survey_versions_fn,
        save_merged_template_fn,
        detect_version_name_from_import_fn,
    )


try:
    (
        ItemRegistry,
        ItemCollisionError,
        merge_survey_versions,
        save_merged_template,
        detect_version_name_from_import,
    ) = _import_with_bootstrap(_import_item_registry_and_merger)
except ImportError:
    pass


def _import_survey_base_and_naming():
    from src.converters.survey_base import load_survey_library
    from src.utils.naming import sanitize_task_name

    return load_survey_library, sanitize_task_name


load_schemas, sanitize_task_name = _import_with_bootstrap(
    _import_survey_base_and_naming, catch=(ImportError, ValueError)
)


def _import_csv_process_dataframe():
    from src.converters.csv import process_dataframe  # noqa: E402

    return process_dataframe


process_dataframe = _import_with_bootstrap(_import_csv_process_dataframe)
```

Also keep the pre-declared `None` defaults for the item-registry names, since the `try/except ImportError: pass` fallback relies on them still being declared as module globals before the `try` block (otherwise a total failure would leave those names undefined rather than `None`, breaking any code that does `if ItemRegistry is not None:`):

```python
ItemRegistry: Any = None
ItemCollisionError: Any = None
merge_survey_versions: Callable[..., Any] | None = None
save_merged_template: Callable[..., Any] | None = None
detect_version_name_from_import: Callable[..., Any] | None = None
```
keeps living right before the `try:` block, unchanged.

- [ ] **Step 4: Confirm no other file imports the deleted intermediate names (`_ItemRegistry`, `_merge_survey_versions`, etc.)**

```bash
grep -rn "_ItemRegistry\b\|_ItemCollisionError\b\|_merge_survey_versions\b\|_save_merged_template\b\|_detect_version_name_from_import\b" --include='*.py' . --exclude-dir=node_modules --exclude-dir=.git
```
Expected: no output outside `limesurvey.py` itself (these were always block-local aliases, never module-level names).

- [ ] **Step 5: Run tests**

```bash
python3 -c "import src.converters.limesurvey as m; print(m.ItemRegistry, m.load_schemas, m.process_dataframe)"
python3 -m pytest tests/test_limesurvey_utils.py tests/test_limesurvey_structure.py -q 2>&1 | tail -40
python3 -m pytest tests/ -q -k "limesurvey" 2>&1 | tail -40
```
Expected: all pass; the inline `print` in the first command must show real values (not all `None`), confirming imports actually succeeded (not silently swallowed).

- [ ] **Step 6: Commit**

```bash
git add src/converters/limesurvey.py
git commit -m "shrink: consolidate the 3 import-bootstrap-retry blocks in limesurvey.py into one helper"
```

---

### Task 8: Remove redundant regex XML field-name parse in `limesurvey.py`

**Files:**
- Modify: `src/converters/limesurvey.py:172-173` (inside `parse_lsa_responses`)
- Test: `tests/test_limesurvey_utils.py::test_parse_lsa_responses_maps_question_titles_and_suffixes` and related

**Interfaces:** none — purely internal to `parse_lsa_responses`; `fieldnames` is a local variable, never exposed.

**Background:** `parse_lsa_responses` extracts `<fieldname>` values two ways on the same XML content: once via `re.findall(r"<fieldname>(.*?)</fieldname>", text)` on the raw decoded bytes (line 173), and separately parses the whole document with `ET.fromstring(xml_resp)` two lines later (line 176) for row extraction. Per the `.lsa` fixture structure used in tests (`tests/test_limesurvey_utils.py:558-573`), the responses XML has the shape:
```xml
<document>
    <fields>
        <fieldname>id</fieldname>
        <fieldname>1X1X10</fieldname>
        ...
    </fields>
    <responses>
        <rows>...</rows>
    </responses>
</document>
```
so `resp_root.findall(".//fieldname")` on the already-parsed `resp_root` returns the same elements, in the same document order, as the regex — replace the redundant regex pass with an XPath query on the tree that's parsed one line later anyway.

- [ ] **Step 1: Re-read the current function to confirm line numbers haven't shifted (Task 7 edited earlier lines in this same file)**

```bash
grep -n "def parse_lsa_responses" -A 45 src/converters/limesurvey.py
```
Confirm the structure still matches:
```python
    text = xml_resp.decode("utf-8")
    fieldnames = re.findall(r"<fieldname>(.*?)</fieldname>", text)

    # Parse rows by XML to preserve order and decode CDATA
    resp_root = ET.fromstring(xml_resp)
    rows = resp_root.findall("./responses/rows/row")
```

- [ ] **Step 2: Reorder so the tree is parsed once, and derive `fieldnames` from it**

Replace:

```python
    text = xml_resp.decode("utf-8")
    fieldnames = re.findall(r"<fieldname>(.*?)</fieldname>", text)

    # Parse rows by XML to preserve order and decode CDATA
    resp_root = ET.fromstring(xml_resp)
    rows = resp_root.findall("./responses/rows/row")
```

with:

```python
    # Parse once; both the fieldname list and the row data come from this tree.
    resp_root = ET.fromstring(xml_resp)
    fieldnames = [el.text or "" for el in resp_root.findall(".//fieldname")]
    rows = resp_root.findall("./responses/rows/row")
```

(`el.text or ""` guards against a self-closing/empty `<fieldname/>` element, which `re.findall`'s `(.*?)` group would have captured as an empty string too — same behavior.)

- [ ] **Step 3: Check whether `text = xml_resp.decode("utf-8")` (the now-unused local) or `re` itself is still needed elsewhere in this function/file**

```bash
grep -n "\btext\b" src/converters/limesurvey.py | sed -n '1,5p'
grep -c "re\." src/converters/limesurvey.py
```
The `text` variable was local to `parse_lsa_responses` and only fed the regex — it's fully removed by this edit, not left dangling. Confirm `re` (the module) is still used elsewhere in the file before considering removing the `import re` line — it almost certainly is (this file has many other regex uses); do not remove the import solely because of this one deletion.

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_limesurvey_utils.py -q -k "parse_lsa_responses" -v 2>&1 | tail -40
python3 -m pytest tests/ -q -k "limesurvey" 2>&1 | tail -40
```
Expected: all pass, including the field-title-mapping and suffix-handling assertions.

- [ ] **Step 5: Commit**

```bash
git add src/converters/limesurvey.py
git commit -m "shrink: derive fieldnames from the parsed XML tree instead of a redundant regex pass"
```

---

### Task 9: Inline `pollJobStatus`'s unused customization hooks

**Files:**
- Modify: `app/static/js/shared/job-polling.js:21-25,70-92` (drop 4 overridable params, replace `getFailureError` callback param with a plain `failureMessage` string)
- Modify: `app/static/js/modules/converter/biometrics.js` (~line 606, inside the `pollJobStatus({...})` call)
- Modify: `app/static/js/modules/converter/physio.js` (~line 656)
- Modify: `app/static/js/modules/converter/environment.js` (2 call sites, ~lines 662 and 1131)
- Modify: `app/static/js/modules/converter/eyetracking.js` (~line 471)
- (No change needed: `app/static/js/modules/converter/survey-workflow-convert.js` and `app/static/js/modules/converter/participants.js` — their `pollJobStatus` calls already pass none of the 5 customization hooks, so they keep working unchanged against the new defaults.)

**Interfaces:**
- `pollJobStatus(options)` — `options.failureMessage?: string` (new, defaults to `'Job failed.'`) replaces `options.getFailureError?: (status) => string`. `options.getLogs`, `options.getNextCursor`, `options.isDone`, `options.isSuccess` are removed entirely (no longer configurable — their bodies are inlined as the only behavior).

**Background — confirmed via `grep` across every call site in the repo** (7 total): `getLogs`, `getNextCursor`, `isDone`, `isSuccess` are never passed anywhere. `getFailureError` is passed at exactly 4 call sites (`biometrics.js`, `physio.js`, `environment.js` ×2, `eyetracking.js`), always in the identical shape `(status) => status.error || '<literal fallback message>'` — never anything more elaborate. `survey-workflow-convert.js` and `participants.js` pass none of the 5 hooks at all, relying entirely on defaults.

- [ ] **Step 1: Re-read the current `job-polling.js` to confirm nothing has changed since planning**

```bash
sed -n '1,157p' app/static/js/shared/job-polling.js
```

- [ ] **Step 2: Re-confirm every call site's exact `getFailureError` value (or absence) hasn't drifted**

```bash
for f in app/static/js/modules/converter/biometrics.js app/static/js/modules/converter/physio.js app/static/js/modules/converter/environment.js app/static/js/modules/converter/eyetracking.js app/static/js/modules/converter/survey-workflow-convert.js app/static/js/modules/converter/participants.js; do
  echo "=== $f ==="
  grep -n "getFailureError\|getLogs\|getNextCursor\|isDone:\|isSuccess:" "$f"
done
```
Expected output matches:
- `biometrics.js`: `getFailureError: (status) => status.error || errorMessage,`
- `physio.js`: `getFailureError: (nextStatusData) => nextStatusData.error || 'Batch conversion failed',`
- `environment.js`: two occurrences, `getFailureError: (nextStatusData) => nextStatusData.error || 'Environment conversion failed',`
- `eyetracking.js`: `getFailureError: (nextStatusData) => nextStatusData.error || 'Batch conversion failed',`
- `survey-workflow-convert.js`, `participants.js`: no matches.

If any of these has changed (different fallback string, or a `getFailureError` body that does something other than `status.error || '<literal>'`), stop and re-derive this task's approach for that call site — don't force a plain string onto a callback that has grown extra logic.

- [ ] **Step 3: Rewrite `job-polling.js`'s options destructuring and JSDoc**

Replace:

```javascript
 * @param {number} [options.maxConsecutiveErrors=4]
 * @param {AbortSignal} [options.signal]
 * @param {string} [options.abortErrorMessage='Polling aborted.']
 * @param {string} [options.timeoutErrorMessage='Job status timed out.']
 * @param {string} [options.statusFailureMessage='Failed to retrieve job status after multiple attempts.']
 * @param {(status:Object)=>Array} [options.getLogs]
 * @param {(status:Object,cursor:number,logs:Array)=>number} [options.getNextCursor]
 * @param {(status:Object)=>boolean} [options.isDone]
 * @param {(status:Object)=>boolean} [options.isSuccess]
 * @param {(status:Object)=>string} [options.getFailureError]
 * @returns {Promise<Object>} Final successful status payload.
 */
```

with:

```javascript
 * @param {number} [options.maxConsecutiveErrors=4]
 * @param {AbortSignal} [options.signal]
 * @param {string} [options.abortErrorMessage='Polling aborted.']
 * @param {string} [options.timeoutErrorMessage='Job status timed out.']
 * @param {string} [options.statusFailureMessage='Failed to retrieve job status after multiple attempts.']
 * @param {string} [options.failureMessage='Job failed.'] - Fallback used when the final status has no `.error` field.
 * @returns {Promise<Object>} Final successful status payload.
 */
```

Then replace the destructuring block:

```javascript
    const {
        fetchStatus,
        onLogs,
        onPollData,
        onRetryWarning,
        initialCursor = 0,
        intervalMs = 500,
        timeoutMs = 300000,
        maxConsecutiveErrors = 4,
        signal = null,
        abortErrorMessage = 'Polling aborted.',
        timeoutErrorMessage = 'Job status timed out.',
        statusFailureMessage = 'Failed to retrieve job status after multiple attempts.',
        getLogs = (status) => (Array.isArray(status && status.logs) ? status.logs : []),
        getNextCursor = (status, cursor, logs) => (
            Number.isInteger(status && status.next_cursor)
                ? status.next_cursor
                : cursor + logs.length
        ),
        isDone = (status) => Boolean(status && status.done),
        isSuccess = (status) => Boolean(status && status.success),
        getFailureError = (status) => (status && status.error) || 'Job failed.',
    } = options || {};
```

with:

```javascript
    const {
        fetchStatus,
        onLogs,
        onPollData,
        onRetryWarning,
        initialCursor = 0,
        intervalMs = 500,
        timeoutMs = 300000,
        maxConsecutiveErrors = 4,
        signal = null,
        abortErrorMessage = 'Polling aborted.',
        timeoutErrorMessage = 'Job status timed out.',
        statusFailureMessage = 'Failed to retrieve job status after multiple attempts.',
        failureMessage = 'Job failed.',
    } = options || {};

    const getLogs = (status) => (Array.isArray(status && status.logs) ? status.logs : []);
    const getNextCursor = (status, cursor, logs) => (
        Number.isInteger(status && status.next_cursor)
            ? status.next_cursor
            : cursor + logs.length
    );
    const isDone = (status) => Boolean(status && status.done);
    const isSuccess = (status) => Boolean(status && status.success);
    const getFailureError = (status) => (status && status.error) || failureMessage;
```

(Keeping `getLogs`/`getNextCursor`/`isDone`/`isSuccess`/`getFailureError` as local `const`s below the destructure — rather than inlining their call sites directly in the polling loop — minimizes the diff to the loop body below, which stays untouched.)

- [ ] **Step 4: Update the 4 call sites**

In `app/static/js/modules/converter/biometrics.js`, replace:
```javascript
                getFailureError: (status) => status.error || errorMessage,
```
with:
```javascript
                failureMessage: errorMessage,
```

In `app/static/js/modules/converter/physio.js`, replace:
```javascript
                    getFailureError: (nextStatusData) => nextStatusData.error || 'Batch conversion failed',
```
with:
```javascript
                    failureMessage: 'Batch conversion failed',
```

In `app/static/js/modules/converter/environment.js`, replace **both** occurrences of:
```javascript
                getFailureError: (nextStatusData) => nextStatusData.error || 'Environment conversion failed',
```
with:
```javascript
                failureMessage: 'Environment conversion failed',
```

In `app/static/js/modules/converter/eyetracking.js`, replace:
```javascript
                    getFailureError: (nextStatusData) => nextStatusData.error || 'Batch conversion failed',
```
with:
```javascript
                    failureMessage: 'Batch conversion failed',
```

- [ ] **Step 5: Syntax-check every edited file**

```bash
for f in app/static/js/shared/job-polling.js app/static/js/modules/converter/biometrics.js app/static/js/modules/converter/physio.js app/static/js/modules/converter/environment.js app/static/js/modules/converter/eyetracking.js; do
  node --check "$f" && echo "$f OK"
done
```
Expected: `OK` for every file.

- [ ] **Step 6: Confirm no other file passes the removed hooks**

```bash
grep -rn "getFailureError\|getLogs:\|getNextCursor:\|isDone:\|isSuccess:" app/static/js/ --include='*.js'
```
Expected: no output anywhere in the tree (all removed/replaced).

- [ ] **Step 7: Manual smoke check (no JS test runner covers this file)**

There is no automated test for `pollJobStatus` or its callers. Per this repo's `run` skill, launch the app and exercise one polling flow end-to-end (e.g. a biometrics or environment conversion that takes long enough to hit at least one poll cycle) to confirm progress logs still stream and a forced failure still surfaces the expected message. Note in the task's completion notes which flow was exercised.

- [ ] **Step 8: Commit**

```bash
git add app/static/js/shared/job-polling.js app/static/js/modules/converter/biometrics.js app/static/js/modules/converter/physio.js app/static/js/modules/converter/environment.js app/static/js/modules/converter/eyetracking.js
git commit -m "yagni: drop pollJobStatus's 4 never-overridden hooks, replace getFailureError callback with a plain failureMessage string"
```

---

### Task 10: Consolidate `escapeHtml` duplicates (2 call sites with zero import barrier)

**Files:**
- Modify: `app/static/js/modules/converter/survey-convert.js` (delete local `escapeHtml`, import canonical)
- Modify: `app/static/js/modules/converter/biometrics.js` (delete local `escapeHtmlForOption`, import canonical `escapeHtml`, rename call sites)

**Interfaces:** consumes `app/static/js/shared/dom.js`'s existing `export function escapeHtml(value)`.

**Background:** `shared/dom.js:220-228` already exports a canonical `escapeHtml` (escapes `&`, `<`, `>`, `"`, `'`). `survey-convert.js:1987-1995` hand-rolls a byte-identical copy under the same name. `biometrics.js:198-204` hand-rolls a near-copy under the name `escapeHtmlForOption` that's missing the `'` → `&#39;` replace (a latent under-escaping bug, fixed as a side effect of switching to the canonical version — not the point of this task, but worth noting in the commit). Both files already `import { ... } from '../../shared/*.js'` for other helpers, so there's no new import pattern to introduce.

- [ ] **Step 1: Re-read both files to confirm current line numbers and bodies**

```bash
grep -n "^import" app/static/js/modules/converter/survey-convert.js
grep -n "escapeHtml" app/static/js/modules/converter/survey-convert.js
grep -n "^import" app/static/js/modules/converter/biometrics.js
grep -n "escapeHtmlForOption\|escapeHtml" app/static/js/modules/converter/biometrics.js
```
Confirm `survey-convert.js`'s `escapeHtml` is still the same 5-replace body, and `biometrics.js`'s `escapeHtmlForOption` is still the 4-replace body (missing `'`).

- [ ] **Step 2: Update `survey-convert.js`**

Find its existing shared imports (currently, per planning-time read: `import { fetchWithApiFallback } from '../../shared/api.js';` and `import { resolveCurrentProjectPath } from '../../shared/project-state.js';` near the top). Add:

```javascript
import { escapeHtml } from '../../shared/dom.js';
```

Then delete the local definition:

```javascript
    function escapeHtml(text) {
        if (text === null || text === undefined) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
```

Every existing usage of `escapeHtml` in this file (there are several, e.g. it's passed into `createSurveyParticipantsMetadataController({ escapeHtml })`) keeps working unchanged — it's the same function reference, now imported instead of locally defined.

- [ ] **Step 3: Update `biometrics.js`**

Add to its existing shared imports:

```javascript
import { escapeHtml } from '../../shared/dom.js';
```

Delete the local definition:

```javascript
    function escapeHtmlForOption(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
```

Then rename every call site from `escapeHtmlForOption(...)` to `escapeHtml(...)`:

```bash
grep -n "escapeHtmlForOption" app/static/js/modules/converter/biometrics.js
```
Replace each occurrence (at planning time: 3 call sites, lines 164, 180, 193) — e.g.:
```javascript
options.push(`<option value="${escapeHtmlForOption(column)}">${escapeHtmlForOption(column)}</option>`);
```
becomes:
```javascript
options.push(`<option value="${escapeHtml(column)}">${escapeHtml(column)}</option>`);
```
and so on for the other 2 call sites.

- [ ] **Step 4: Syntax-check both files**

```bash
node --check app/static/js/modules/converter/survey-convert.js && echo OK
node --check app/static/js/modules/converter/biometrics.js && echo OK
```

- [ ] **Step 5: Confirm no other file imports the deleted local names**

```bash
grep -rn "escapeHtmlForOption" app/static/js/ --include='*.js'
```
Expected: no output anywhere (fully removed).

- [ ] **Step 6: Manual smoke check**

No JS test covers these files. Per the `run` skill, load a biometrics conversion page and a survey conversion page in the browser, confirm dropdown option labels and any log/status text containing special characters (e.g. a column name with `&` or `<`) still render escaped, not broken/raw HTML.

- [ ] **Step 7: Commit**

```bash
git add app/static/js/modules/converter/survey-convert.js app/static/js/modules/converter/biometrics.js
git commit -m "dedup: import canonical escapeHtml from shared/dom.js instead of two local copies"
```

---

### Task 11: Shrink `_create_bidsignore`'s string concatenation

**Files:**
- Modify: `app/src/project_manager.py:6803-6832`
- Test: `tests/test_project_manager.py::test_create_project_bidsignore_covers_prism_only_paths`, `tests/test_project_manager.py::test_init_on_existing_bids_merges_into_preexisting_bidsignore`

**Interfaces:** none — private method, same return type (`str`), byte-identical output verified below.

- [ ] **Step 1: Re-read the current method**

```bash
python3 -c "import app.src.project_manager as m; print(m.__file__)"
sed -n '6803,6832p' app/src/project_manager.py
```
Confirm it still matches:
```python
    def _create_bidsignore(self, modalities: List[str]) -> str:
        """Create .bidsignore content."""
        content = "# .bidsignore - PRISM and YODA files excluded from BIDS validation\n"
        content += (
            "# This ensures compatibility with standard BIDS tools (fMRIPrep, etc.)\n\n"
        )

        # Ignore project-level metadata
        content += "project.json\n"
        content += ".prismrc.json\n\n"

        # Ignore YODA folders (they are outside rawdata/ but just in case)
        content += "sourcedata/\n"
        content += "derivatives/\n"
        content += "analysis/\n"
        content += "paper/\n"
        content += "code/\n\n"

        # Ignore legacy/non-BIDS project folders if present
        content += "recipes/\n"
        content += "recipe/\n"
        content += "library/\n"
        content += "code/recipes/\n"
        content += "code/library/\n\n"

        for mod in modalities:
            if mod in PRISM_MODALITIES and mod not in BIDS_PASSTHROUGH_MODALITIES:
                content += f"{mod}/\n"

        return content
```

- [ ] **Step 2: Prove byte-equivalence before touching the real file**

```bash
python3 -c "
def original(modalities, PRISM_MODALITIES, BIDS_PASSTHROUGH_MODALITIES):
    content = '# .bidsignore - PRISM and YODA files excluded from BIDS validation\n'
    content += '# This ensures compatibility with standard BIDS tools (fMRIPrep, etc.)\n\n'
    content += 'project.json\n'
    content += '.prismrc.json\n\n'
    content += 'sourcedata/\n'
    content += 'derivatives/\n'
    content += 'analysis/\n'
    content += 'paper/\n'
    content += 'code/\n\n'
    content += 'recipes/\n'
    content += 'recipe/\n'
    content += 'library/\n'
    content += 'code/recipes/\n'
    content += 'code/library/\n\n'
    for mod in modalities:
        if mod in PRISM_MODALITIES and mod not in BIDS_PASSTHROUGH_MODALITIES:
            content += f'{mod}/\n'
    return content

def new(modalities, PRISM_MODALITIES, BIDS_PASSTHROUGH_MODALITIES):
    lines = [
        '# .bidsignore - PRISM and YODA files excluded from BIDS validation',
        '# This ensures compatibility with standard BIDS tools (fMRIPrep, etc.)',
        '',
        'project.json',
        '.prismrc.json',
        '',
        'sourcedata/',
        'derivatives/',
        'analysis/',
        'paper/',
        'code/',
        '',
        'recipes/',
        'recipe/',
        'library/',
        'code/recipes/',
        'code/library/',
        '',
    ]
    lines.extend(
        f'{mod}/'
        for mod in modalities
        if mod in PRISM_MODALITIES and mod not in BIDS_PASSTHROUGH_MODALITIES
    )
    return '\n'.join(lines) + '\n'

for mods in ([], ['survey'], ['survey','biometrics','physio','func']):
    PRISM_MODALITIES = {'survey','biometrics','physio'}
    BIDS_PASSTHROUGH_MODALITIES = {'physio'}
    a = original(mods, PRISM_MODALITIES, BIDS_PASSTHROUGH_MODALITIES)
    b = new(mods, PRISM_MODALITIES, BIDS_PASSTHROUGH_MODALITIES)
    print(mods, 'MATCH' if a == b else 'MISMATCH')
"
```
Expected: `MATCH` for all three cases (empty list, one modality, multiple modalities including one filtered out by `BIDS_PASSTHROUGH_MODALITIES`).

- [ ] **Step 3: Apply the edit**

Replace the body shown in Step 1 with:

```python
    def _create_bidsignore(self, modalities: List[str]) -> str:
        """Create .bidsignore content."""
        lines = [
            "# .bidsignore - PRISM and YODA files excluded from BIDS validation",
            "# This ensures compatibility with standard BIDS tools (fMRIPrep, etc.)",
            "",
            "project.json",
            ".prismrc.json",
            "",
            "sourcedata/",
            "derivatives/",
            "analysis/",
            "paper/",
            "code/",
            "",
            "recipes/",
            "recipe/",
            "library/",
            "code/recipes/",
            "code/library/",
            "",
        ]
        lines.extend(
            f"{mod}/"
            for mod in modalities
            if mod in PRISM_MODALITIES and mod not in BIDS_PASSTHROUGH_MODALITIES
        )
        return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_project_manager.py -q -k "bidsignore" 2>&1 | tail -30
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/src/project_manager.py
git commit -m "shrink: build .bidsignore content as a list + join instead of chained string concatenation"
```

---

### Task 12: Full test suite verification

**Files:** none modified — verification only.

- [ ] **Step 1: Run the complete backend suite**

```bash
python3 -m pytest tests/ -q 2>&1 | tail -30
```

- [ ] **Step 2: Compare against the known-good baseline**

This session's earlier passes established that exactly these 4 tests fail on a clean, unmodified checkout (pre-existing, unrelated to any ponytail work):
- `tests/test_cli_survey_commands_remaining.py::TestCmdSurveyConvert::test_project_path_resolved_when_file`
- `tests/test_projects_workflow_wiring.py::TestProjectsWorkflowWiring::test_backend_monitoring_verbose_toggle_is_wired`
- `tests/test_projects_workflow_wiring.py::TestProjectsWorkflowWiring::test_current_project_state_and_recent_projects_bootstrap_before_workflows`
- `tests/test_projects_workflow_wiring.py::TestProjectsWorkflowWiring::test_share_and_archive_split_into_its_own_page`

Expected: the failure list after all 11 tasks above is exactly these 4, no more, no fewer. If any other test fails, that task's edit introduced a regression — bisect by reverting tasks one at a time (in reverse commit order) and re-running until the extra failure disappears, then re-derive that task's parameterization.

- [ ] **Step 3: Lint check for stray unused imports left behind by any deletion**

```bash
ruff check --select F401,F841 app/src/converters/survey.py app/src/converters/survey_core.py app/src/converters/survey_io.py app/src/converters/survey_processing.py app/src/web/blueprints/conversion_utils.py app/src/cli/commands/convert.py app/src/validator.py app/src/web/blueprints/tools_helpers.py src/maintenance/sync_survey_keys.py src/maintenance/sync_biometrics_keys.py src/maintenance/_sync_library_keys.py src/runtime_dependencies.py src/converters/limesurvey.py app/src/project_manager.py
```
Fix anything it flags (following the same cross-repo-grep-before-deleting discipline documented in `PONYTAIL-AUDIT.md`'s pass-1 notes — some of these files re-export names consumed elsewhere; don't blind-`--fix`).

- [ ] **Step 4: Final commit (only if Step 3 found anything to fix)**

```bash
git add -A
git commit -m "fix: clean up stray unused imports from the ponytail-audit pass-2 dedup work"
```
