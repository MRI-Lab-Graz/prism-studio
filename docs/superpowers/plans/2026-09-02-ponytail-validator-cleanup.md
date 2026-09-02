# Ponytail Validator Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the four over-engineering findings from the ponytail review of the standalone PRISM validator package (`app/src/validator.py`, `app/src/core/validation.py`, `app/src/plugins.py`) — each a small, self-contained deletion with no behavior change except removing genuinely dead flexibility.

**Architecture:** No architectural change. Each task is a local simplification inside an existing module: collapse a dead conditional, deduplicate an inline closure into a shared module-level helper, remove a zero-value wrapper function, and delete a dataclass field that is read but never set. Tasks are independent of each other and can be done in any order.

**Tech Stack:** Python 3, pytest. No new dependencies.

**Spec:** This plan implements the four findings from the ponytail-review pass run earlier in this conversation (no separate spec document — the findings below are the spec).

## Global Constraints

- Every fix must be behavior-preserving except where the finding explicitly says a branch is dead code (i.e., no test that passes today may fail after the fix, except tests that were asserting the *old*, over-engineered shape itself — none exist here).
- Follow this repo's existing test-file convention: each `tests/*.py` file that imports from `app/src/*` does its own `sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))` before importing (see `tests/test_runner.py`, `tests/test_core_boundary.py`). Do not add a `conftest.py` — none exists in `tests/` today and adding one is out of scope.
- `app/src/validator.py` has no same-named file under top-level `src/` (verified via `find src -name validator.py` — no match), so no dual-tree drift check applies to Tasks 1–2. `app/src/core/validation.py` and `app/src/plugins.py` are likewise single-copy modules — no drift check needed for Tasks 3–4.
- Per `CLAUDE.md`: session labels are free-form strings — none of these tasks touch session-label logic, so this doesn't apply here, noted only because Task 1/2 are in the same file as that logic; don't let it bleed into these edits.

---

### Task 1: Collapse the dead ternary in `_is_empty_levels_label`

**Files:**
- Modify: `app/src/validator.py:617-636` (method `DatasetValidator._is_empty_levels_label`)
- Test: `tests/test_validator_levels_labels.py` (new file)

**Interfaces:**
- Consumes: nothing new — `_is_empty_levels_label(self, label) -> bool` keeps its exact existing signature and is called only from `_check_empty_levels_labels` (line 646), which is unchanged.
- Produces: nothing new for other tasks to consume.

**Background:** The final branch of the dict case currently reads:

```python
return True if has_any_value or not label else True
```

Both arms of that ternary return `True`, so the condition is evaluated for nothing and `has_any_value` becomes dead once you delete it. Every dict that reaches this line (i.e., every value in the dict was either `None` or an empty/whitespace string, or the dict had no values that returned `False` earlier) is genuinely an "empty label" — so `True` is the correct, unconditional answer.

- [ ] **Step 1: Write the failing test**

Create `tests/test_validator_levels_labels.py`:

```python
"""Unit tests for DatasetValidator._is_empty_levels_label.

Covers the dict-label branch directly, since the only prior coverage was
indirect (via _check_empty_levels_labels through a full validation run in
tests/test_multiversion_survey.py). These pin down every input the dead
ternary in that branch used to obscure: an all-None dict and an empty dict
both still route to "empty" once the ternary is collapsed to `return True`.
"""

import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src")
)

from validator import DatasetValidator


def _validator() -> DatasetValidator:
    return DatasetValidator()


def test_none_label_is_empty():
    assert _validator()._is_empty_levels_label(None) is True


def test_blank_string_label_is_empty():
    assert _validator()._is_empty_levels_label("   ") is True


def test_nonempty_string_label_is_not_empty():
    assert _validator()._is_empty_levels_label("Male") is False


def test_empty_dict_label_is_empty():
    assert _validator()._is_empty_levels_label({}) is True


def test_dict_with_only_none_values_is_empty():
    assert _validator()._is_empty_levels_label({"en": None, "de": None}) is True


def test_dict_with_only_blank_string_values_is_empty():
    assert _validator()._is_empty_levels_label({"en": "", "de": "   "}) is True


def test_dict_with_nonempty_string_value_is_not_empty():
    assert _validator()._is_empty_levels_label({"en": "Male", "de": ""}) is False


def test_dict_with_non_string_non_none_value_is_not_empty():
    assert _validator()._is_empty_levels_label({"en": 5}) is False
```

- [ ] **Step 2: Run test to verify it passes even before the edit**

Run: `python -m pytest tests/test_validator_levels_labels.py -v`
Expected: PASS — all 8 cases already pass against the current (dead-ternary) implementation, since the ternary's two arms are equal. This step exists to prove the fix is a pure simplification, not a behavior change: if any of these failed here, the "always True" claim would be wrong and the fix would need to change behavior, not just delete code.

- [ ] **Step 3: Simplify the implementation**

In `app/src/validator.py`, replace lines 617-636:

```python
    def _is_empty_levels_label(self, label) -> bool:
        """Return True when a Levels label is effectively empty."""
        if label is None:
            return True
        if isinstance(label, str):
            return label.strip() == ""
        if isinstance(label, dict):
            has_any_value = False
            for value in label.values():
                if value is None:
                    continue
                if isinstance(value, str):
                    if value.strip():
                        return False
                    has_any_value = True
                    continue
                # Non-string values are considered non-empty payloads.
                return False
            return True if has_any_value or not label else True
        return False
```

with:

```python
    def _is_empty_levels_label(self, label) -> bool:
        """Return True when a Levels label is effectively empty."""
        if label is None:
            return True
        if isinstance(label, str):
            return label.strip() == ""
        if isinstance(label, dict):
            for value in label.values():
                if value is None:
                    continue
                if isinstance(value, str):
                    if value.strip():
                        return False
                    continue
                # Non-string values are considered non-empty payloads.
                return False
            return True
        return False
```

- [ ] **Step 4: Run the test again to confirm nothing broke**

Run: `python -m pytest tests/test_validator_levels_labels.py -v`
Expected: PASS — identical results to Step 2, confirming the simplification changed no behavior.

- [ ] **Step 5: Run the existing integration test that exercises this path**

Run: `python -m pytest tests/test_multiversion_survey.py -v -k empty`
Expected: PASS (the existing assertion at `tests/test_multiversion_survey.py:178` checking for `"empty Levels label"` in the warning message still holds).

- [ ] **Step 6: Commit**

```bash
git add app/src/validator.py tests/test_validator_levels_labels.py
git commit -m "refactor: collapse dead ternary in _is_empty_levels_label"
```

---

### Task 2: Deduplicate the `_value_candidates` closure

**Files:**
- Modify: `app/src/validator.py:173-235` (`resolve_sidecar_path`) and `app/src/validator.py:257-378` (`_find_inherited_root_sidecar`)
- Test: `tests/test_validator_value_candidates.py` (new file)

**Interfaces:**
- Produces: a new module-level function `_value_candidates(base_value: str | None, acq_value: str | None) -> list[str]` in `app/src/validator.py`, placed directly above `resolve_sidecar_path`. This is the same name the two existing local closures already use, so no caller-facing rename is needed — only their definition moves and gains an explicit `acq_value` parameter instead of closing over it.

**Background:** `resolve_sidecar_path` and `_find_inherited_root_sidecar` each define an identical nested function:

```python
    def _value_candidates(base_value):
        if not base_value:
            return []
        candidates = []
        if acq_value:
            candidates.append(f"{base_value}_acq-{acq_value}")
        candidates.append(base_value)
        return candidates
```

Both closures reference a local `acq_value` computed the same way in each function (`_extract_entity_value(stem, "acq")`), one line earlier in each case. Pulling this out to module level with `acq_value` as an explicit parameter removes the duplication.

- [ ] **Step 1: Write the failing test**

Create `tests/test_validator_value_candidates.py`:

```python
"""Unit tests for validator._value_candidates, the shared helper that
resolve_sidecar_path and _find_inherited_root_sidecar both use to build
acq-qualified sidecar name candidates."""

import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src")
)

from validator import _value_candidates


def test_with_acq_value_prepends_acq_qualified_variant():
    assert _value_candidates("bfi", "s") == ["bfi_acq-s", "bfi"]


def test_without_acq_value_returns_base_only():
    assert _value_candidates("bfi", None) == ["bfi"]


def test_empty_base_value_returns_empty_list():
    assert _value_candidates("", "s") == []
    assert _value_candidates(None, "s") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_validator_value_candidates.py -v`
Expected: FAIL with `ImportError: cannot import name '_value_candidates' from 'validator'` — the function doesn't exist at module level yet.

- [ ] **Step 3: Add the module-level helper**

In `app/src/validator.py`, insert this function directly above `def resolve_sidecar_path(...)` (currently line 173):

```python
def _value_candidates(base_value: str | None, acq_value: str | None) -> list[str]:
    """Return name-lookup candidates for base_value, acq-qualified variant first."""
    if not base_value:
        return []
    candidates = []
    if acq_value:
        candidates.append(f"{base_value}_acq-{acq_value}")
    candidates.append(base_value)
    return candidates
```

- [ ] **Step 4: Remove the local closure from `resolve_sidecar_path` and update its call sites**

In `resolve_sidecar_path`, delete the nested `def _value_candidates(base_value): ...` block (the six lines directly after `acq_value = _extract_entity_value(stem, "acq")`), and update the three call sites in that function from `_value_candidates(survey_value)` / `_value_candidates(biometrics_value)` / `_value_candidates(task_value)` to pass `acq_value` explicitly:

```python
    label_candidates = []
    for survey_candidate in _value_candidates(survey_value, acq_value):
        label_candidates.append(("survey", survey_candidate))
    for biometrics_candidate in _value_candidates(biometrics_value, acq_value):
        label_candidates.append(("biometrics", biometrics_candidate))
    if task_value:
        for task_candidate in _value_candidates(task_value, acq_value):
            label_candidates.append(("task", task_candidate))
        if not survey_value and not biometrics_value:
            for task_candidate in _value_candidates(task_value, acq_value):
                label_candidates.append(("survey", task_candidate))
                label_candidates.append(("biometrics", task_candidate))
```

- [ ] **Step 5: Remove the local closure from `_find_inherited_root_sidecar` and update its call sites**

Do the same in `_find_inherited_root_sidecar`: delete its identical nested `_value_candidates` definition, and pass `acq_value` explicitly at each of its call sites:

```python
    candidate_names = []
    for survey_candidate in _value_candidates(survey_value, acq_value):
        candidate_names.append(f"survey-{survey_candidate}_{suffix}.json")
    for biometrics_candidate in _value_candidates(biometrics_value, acq_value):
        candidate_names.append(f"biometrics-{biometrics_candidate}_{suffix}.json")
    if task_value:
        for task_candidate in _value_candidates(task_value, acq_value):
            candidate_names.append(f"task-{task_candidate}_{suffix}.json")

        # Legacy physio compatibility: files named like *_task-rest_ecg.edf should
        # be allowed to inherit canonical root sidecars like
        # task-rest_recording-ecg_physio.json during migration.
        if is_physio_context and suffix not in {"physio", "survey", "biometrics"}:
            for task_candidate in _value_candidates(task_value, acq_value):
                candidate_names.append(
                    f"task-{task_candidate}_recording-{suffix}_physio.json"
                )

        # Backward-compatible fallback: some datasets use survey-/biometrics-
        # naming with task labels.
        for task_candidate in _value_candidates(task_value, acq_value):
            candidate_names.append(f"survey-{task_candidate}_{suffix}.json")
            candidate_names.append(f"biometrics-{task_candidate}_{suffix}.json")
```

- [ ] **Step 6: Run the new test to verify it passes**

Run: `python -m pytest tests/test_validator_value_candidates.py -v`
Expected: PASS.

- [ ] **Step 7: Run the existing sidecar-resolution tests to confirm no regression**

Run: `python -m pytest tests/test_runner.py -v -k sidecar`
Expected: PASS — `resolve_sidecar_path` and `_find_inherited_root_sidecar`'s external behavior is unchanged, only their internal helper moved.

- [ ] **Step 8: Commit**

```bash
git add app/src/validator.py tests/test_validator_value_candidates.py
git commit -m "refactor: dedupe _value_candidates closure in validator.py"
```

---

### Task 3: Remove the zero-value `validate_dataset` wrapper in `core/validation.py`

**Files:**
- Modify: `app/src/core/validation.py:10-23`
- Test: `tests/test_core_boundary.py` (add to existing file)

**Interfaces:**
- Consumes: `runner.validate_dataset` (the canonical implementation, unchanged).
- Produces: `core.validation.validate_dataset` — same public name, same call signature (`*args, **kwargs` passthrough was never adding any transformation, so callers are unaffected), but now the *same function object* as `runner.validate_dataset` rather than a wrapper around it. Existing importers (`app/prism.py:56`, `app/src/project_manager.py:1302`, `app/src/web/validation.py:235,242`) all import it by name and are unaffected by this change.

**Background:** The module docstring calls this "a stable validation boundary" that downstream layers should consume instead of importing runner internals directly — but the function itself adds nothing beyond that naming boundary:

```python
def validate_dataset(*args, **kwargs):
    """Validate a dataset using the canonical runner implementation."""
    return _validate_dataset(*args, **kwargs)
```

The boundary is fully achieved by the import itself (`from src.runner import validate_dataset` / the frozen-build fallback `from runner import validate_dataset`) — renaming on import gives the same stable, renamed public symbol without a wrapper function in between.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_core_boundary.py` (append to the existing file, using its existing `sys.path` setup):

```python
def test_validate_dataset_is_runner_validate_dataset_directly():
    """core.validation.validate_dataset must be runner.validate_dataset itself,
    not a wrapper around it -- the module boundary comes from the import
    rename, not from an extra indirection layer."""
    import runner
    import core.validation as core_validation

    assert core_validation.validate_dataset is runner.validate_dataset
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_core_boundary.py::test_validate_dataset_is_runner_validate_dataset_directly -v`
Expected: FAIL — `core_validation.validate_dataset` is currently a distinct wrapper function, not the same object as `runner.validate_dataset`.

- [ ] **Step 3: Remove the wrapper**

In `app/src/core/validation.py`, replace lines 10-23:

```python
try:
    from src.runner import validate_dataset as _validate_dataset
except ImportError:
    from runner import validate_dataset as _validate_dataset

try:
    from src.issues import tuple_to_issue, issues_to_dict, summarize_issues
except ImportError:
    from issues import tuple_to_issue, issues_to_dict, summarize_issues


def validate_dataset(*args, **kwargs):
    """Validate a dataset using the canonical runner implementation."""
    return _validate_dataset(*args, **kwargs)
```

with:

```python
try:
    from src.runner import validate_dataset
except ImportError:
    from runner import validate_dataset

try:
    from src.issues import tuple_to_issue, issues_to_dict, summarize_issues
except ImportError:
    from issues import tuple_to_issue, issues_to_dict, summarize_issues
```

- [ ] **Step 4: Run the test again to confirm it passes**

Run: `python -m pytest tests/test_core_boundary.py::test_validate_dataset_is_runner_validate_dataset_directly -v`
Expected: PASS.

- [ ] **Step 5: Run the full existing file to confirm no regression**

Run: `python -m pytest tests/test_core_boundary.py -v`
Expected: PASS — `determine_exit_code` and `build_validation_report` tests are untouched by this change.

- [ ] **Step 6: Commit**

```bash
git add app/src/core/validation.py tests/test_core_boundary.py
git commit -m "refactor: remove zero-value validate_dataset wrapper in core.validation"
```

---

### Task 4: Delete the dead `Plugin.enabled` field

**Files:**
- Modify: `app/src/plugins.py:43` (field declaration), `:192-193` (dead guard in `run_plugin`), `:420` (status glyph in `list_plugins`)
- Test: `tests/test_plugins.py` (new file — no plugin tests exist in this repo today)

**Interfaces:**
- Consumes: `Plugin`, `PluginManager`, `PluginContext` (all existing, `app/src/plugins.py`).
- Produces: nothing new for other tasks — `Plugin` loses the `enabled` field; every constructor call already omits `enabled` (it was only ever set via its `True` default, never passed explicitly — confirmed by `grep -n "enabled=" app/src/plugins.py app/prism.py` returning no matches), so no call site needs updating.

**Background:** `Plugin.enabled` defaults to `True` and is read in two places (`run_plugin`'s `if not plugin.enabled: return []` guard, and `list_plugins`'s `✓`/`✗` status glyph) but is never set to `False` anywhere in this codebase — there's no CLI flag or config key that disables an individual plugin (only `prism.py --no-plugins`, which skips creating the `PluginManager` entirely and never touches this field). It's dead flexibility: a toggle nothing can flip.

- [ ] **Step 1: Write the failing test**

Create `tests/test_plugins.py`:

```python
"""Unit tests for app/src/plugins.py: the .prismrc.json / <dataset>/validators/
custom-validator plugin system used by the standalone PRISM validator CLI.

No prior test file covered this module -- these tests exercise the
load -> run round trip end to end via a real plugin file on disk, matching
how app/prism.py drives PluginManager.
"""

import dataclasses
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src")
)

from plugins import Plugin, PluginContext, PluginManager


def test_plugin_has_no_enabled_field():
    """Plugin.enabled was read in two places but never set to False anywhere
    in this codebase -- dead flexibility, deleted. This test pins the
    dataclass shape so it isn't silently reintroduced."""
    field_names = {f.name for f in dataclasses.fields(Plugin)}
    assert "enabled" not in field_names


def test_run_plugin_executes_a_discovered_plugin(tmp_path):
    validators_dir = tmp_path / "validators"
    validators_dir.mkdir()
    (validators_dir / "custom_check.py").write_text(
        "def validate(dataset_path, context):\n"
        "    return [('WARNING', 'test issue')]\n"
    )

    manager = PluginManager(str(tmp_path))
    manager.discover_local_plugins()
    assert len(manager.plugins) == 1

    context = PluginContext(
        dataset_path=str(tmp_path),
        schema_version="stable",
        subjects=[],
        sessions=[],
        tasks=[],
        modalities={},
    )
    issues = manager.run_plugin(manager.plugins[0], context)

    assert len(issues) == 1
    assert issues[0].message == "[custom_check] test issue"
```

- [ ] **Step 2: Run test to verify current state**

Run: `python -m pytest tests/test_plugins.py -v`
Expected: `test_run_plugin_executes_a_discovered_plugin` PASSES (the load/run round trip already works). `test_plugin_has_no_enabled_field` FAILS — `enabled` is still present on `Plugin`.

- [ ] **Step 3: Remove the field, the guard, and the status glyph**

In `app/src/plugins.py`, in the `Plugin` dataclass (around line 43), delete:

```python
    enabled: bool = True
```

In `run_plugin` (around lines 192-193), delete the now-always-true guard:

```python
        if not plugin.enabled:
            return []

```

In `list_plugins` (around line 420), replace:

```python
    for plugin in manager.plugins:
        status = "✓" if plugin.enabled else "✗"
        has_validate = "✓" if plugin.has_validate else "✗"
        print(f"  {status} {plugin.name} v{plugin.version}")
```

with:

```python
    for plugin in manager.plugins:
        has_validate = "✓" if plugin.has_validate else "✗"
        print(f"  {plugin.name} v{plugin.version}")
```

- [ ] **Step 4: Run the tests again to confirm both pass**

Run: `python -m pytest tests/test_plugins.py -v`
Expected: PASS — both tests.

- [ ] **Step 5: Commit**

```bash
git add app/src/plugins.py tests/test_plugins.py
git commit -m "refactor: delete dead Plugin.enabled field"
```

---

## Final verification

- [ ] Run the full validator-adjacent test slice to confirm no cross-task regression:

Run: `python -m pytest tests/test_validator.py tests/test_validator_levels_labels.py tests/test_validator_value_candidates.py tests/test_validator_allowed_values.py tests/test_core_boundary.py tests/test_plugins.py tests/test_runner.py tests/test_multiversion_survey.py -v`
Expected: all PASS.
