# Split survey.py's Three Oversized Functions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `app/src/converters/survey.py`'s three oversized functions — `_convert_survey_dataframe_to_prism_dataset` (668 lines), `_map_survey_columns` (371 lines), `_write_survey_participants` (225 lines) — into small, named, independently-tested functions, extending existing sibling modules (`survey_core.py`, `survey_lsa.py`, `survey_participants_logic.py`) and adding one new file (`survey_column_mapping.py`).

**Architecture:** For the orchestrator (`_convert_survey_dataframe_to_prism_dataset`), extract three genuinely-new function boundaries via TDD, using dependency injection (`_fn`/`_cls` keyword parameters) for anything that would otherwise require a sibling module to import back from `survey.py` — this repo's own established idiom (already used throughout this exact file, e.g. `normalize_sub_fn=`, `missing_id_mapping_error_cls=`) and the same technique that resolved a real circular-import bug during the companion participants-blueprint split. For `_map_survey_columns` and `_write_survey_participants` — both fully self-contained, no existing delegation — move each wholesale into its natural sibling module, then split each internally into 3 TDD-tested phase functions.

**Tech Stack:** Python 3, pandas, pytest.

## Global Constraints

- `src/converters/survey.py` is a confirmed symlink to `app/src/converters/survey.py` — no dual-tree drift risk for this file. New files created by this plan (`survey_column_mapping.py`) must be verified to have no `src/`-side shadow the same way: `python3 -c "import src.converters.survey_column_mapping as m; print(m.__file__)"` must print a path under `app/src/converters/`.
- No behavior change anywhere in this plan — every task is either a pure move (verified against the existing ~12,000-line regression suite covering the public entry points, listed per-task below) or a TDD extraction of already-existing logic into a new function boundary (verified by a dedicated new unit test, per `CLAUDE.md`'s extract-and-test rule).
- Dependency injection over cross-module coupling: when an extracted function needs something that lives in a module that already imports *from* the extracted function's new home (a circular-import risk), pass it in as a parameter (`_fn`/`_cls` suffix, matching this file's existing convention) rather than importing it directly. Every task below that has this concern names the exact resolution — do not improvise a different one without checking for a cycle first.
- Regression command for pure-move tasks: `pytest tests/test_web_blueprints_conversion.py tests/test_survey_preview_regressions.py tests/test_lsa_import_integration.py tests/test_converter_project_save_contracts.py tests/test_cli_survey_commands_remaining.py tests/test_survey_value_offsets.py tests/test_hostile_demo_pipeline.py tests/test_survey_converter_version_plan_acq.py tests/test_hostile_survey_pipeline.py tests/test_survey_template_version_persistence.py tests/test_unicode_normalization_consistency.py -q` — record the pass count before each move and confirm it's identical after.

---

### Task 1: `build_survey_id_normalizers` — TDD, survey_core.py

**Files:**
- Modify: `app/src/converters/survey_core.py`
- Modify: `app/src/converters/survey.py` (orchestrator; also relocates `_resolve_existing_project_root`)
- Test: `tests/test_survey_id_normalizers.py` (new)

**Interfaces:**
- Produces: `SurveyIdNormalizers` (dataclass with fields `normalize_sub`, `normalize_ses`, `normalize_run`, `is_missing`, each a callable) and `build_survey_id_normalizers(project_path: str | Path | None) -> SurveyIdNormalizers`, both in `survey_core.py`.

**Step 0 — relocate `_resolve_existing_project_root` first (prerequisite, avoids a circular import):**

`_resolve_existing_project_root` currently lives in `survey.py` (grep `^def _resolve_existing_project_root` to find its current line — it's a small, self-contained 14-line function with no dependencies beyond `Path`). It has exactly two call sites in `survey.py`: one inside `_build_participant_registry_warning` (stays in `survey.py`, out of this plan's scope) and one inside the closures block you're about to extract in this task. `build_survey_id_normalizers` needs it, and if it stays in `survey.py`, `survey_core.py` would have to import back from `survey.py` — which `survey.py` already imports *from* (`from .survey_core import (...)`), a real cycle.

- [ ] **Step 0.1: Move `_resolve_existing_project_root` to `survey_core.py`, verbatim.**

Cut it from `survey.py`, paste into `survey_core.py` (anywhere reasonable, e.g. near other path-resolution helpers).

- [ ] **Step 0.2: Update `survey.py`'s import block to pull it back in.**

Add `_resolve_existing_project_root` to the existing `from .survey_core import (...)` block (the one starting around line 52) — its remaining call site in `_build_participant_registry_warning` stays textually unchanged.

- [ ] **Step 0.3: Run the regression command from Global Constraints, confirm the pass count is unchanged, then commit this sub-step alone.**

```bash
git add app/src/converters/survey_core.py app/src/converters/survey.py
git commit -m "refactor: relocate _resolve_existing_project_root to survey_core.py"
```

**Now the TDD part:**

- [ ] **Step 1: Write the failing tests**

Create `tests/test_survey_id_normalizers.py`:

```python
from src.converters.survey_core import build_survey_id_normalizers


def test_normalize_sub_adds_sub_prefix_and_strips_non_alnum():
    normalizers = build_survey_id_normalizers(project_path=None)
    assert normalizers.normalize_sub("A-01!") == "sub-A01"


def test_normalize_sub_treats_nan_string_as_empty():
    normalizers = build_survey_id_normalizers(project_path=None)
    assert normalizers.normalize_sub("nan") == ""


def test_normalize_sub_matches_existing_project_participant_by_numeric_id(tmp_path):
    (tmp_path / "participants.tsv").write_text("participant_id\nsub-001\n")

    normalizers = build_survey_id_normalizers(project_path=tmp_path)

    # A bare "1" in source data should resolve to the existing "sub-001"
    # folder rather than creating a duplicate "sub-1".
    assert normalizers.normalize_sub("1") == "sub-001"


def test_normalize_ses_defaults_to_ses_1_for_missing_value():
    normalizers = build_survey_id_normalizers(project_path=None)
    assert normalizers.normalize_ses("") == "ses-1"
    assert normalizers.normalize_ses("nan") == "ses-1"


def test_normalize_ses_adds_ses_prefix():
    normalizers = build_survey_id_normalizers(project_path=None)
    assert normalizers.normalize_ses("baseline") == "ses-baseline"


def test_normalize_run_returns_none_for_missing_value():
    normalizers = build_survey_id_normalizers(project_path=None)
    assert normalizers.normalize_run("") is None
    assert normalizers.normalize_run("nan") is None


def test_normalize_run_adds_run_prefix():
    normalizers = build_survey_id_normalizers(project_path=None)
    assert normalizers.normalize_run("2") == "run-2"


def test_is_missing_detects_nan_and_blank_string():
    import pandas as pd

    normalizers = build_survey_id_normalizers(project_path=None)
    assert normalizers.is_missing(float("nan")) is True
    assert normalizers.is_missing("   ") is True
    assert normalizers.is_missing("value") is False
    assert normalizers.is_missing(pd.NA) is True
```

Note: `test_normalize_sub_matches_existing_project_participant_by_numeric_id` needs `load_existing_participant_ids` (called inside `build_survey_id_normalizers`) to find `tmp_path / "participants.tsv"` and parse `sub-001` out of it — this mirrors real usage exactly (`build_survey_id_normalizers` is only ever called with a real `project_path`), so no mocking is needed; if this test fails because `load_existing_participant_ids`'s expected file format differs, check `src/subject_id_matching.py::load_existing_participant_ids` for the exact expected column name and fix the fixture, not the implementation.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_survey_id_normalizers.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_survey_id_normalizers'`.

- [ ] **Step 3: Implement `build_survey_id_normalizers`**

Add to `survey_core.py` (needs `import re`, `import unicodedata`, `from dataclasses import dataclass` — `dataclass` is likely already imported; `from ..utils.naming import sanitize_id`; `from ..subject_id_matching import build_subject_id_matcher, load_existing_participant_ids` — check which of these `survey_core.py` doesn't already have and add them):

```python
@dataclass(frozen=True)
class SurveyIdNormalizers:
    normalize_sub: Any
    normalize_ses: Any
    normalize_run: Any
    is_missing: Any


def build_survey_id_normalizers(project_path: str | Path | None) -> SurveyIdNormalizers:
    """Build the subject/session/run-ID normalizers and missing-value check
    shared across survey conversion.

    normalize_sub additionally resolves against the project's existing
    participants.tsv IDs (via build_subject_id_matcher) so e.g. a bare "1"
    in the source data lands in an existing "sub-001" folder rather than
    creating a duplicate "sub-1".
    """

    def _normalize_sub_id_raw(val) -> str:
        s = str(val).strip()
        if not s:
            return s
        if s.lower() == "nan":
            return ""
        # Normalize to NFC before stripping non-ASCII chars so a name like
        # "José" sanitizes the same way regardless of which Unicode
        # normalization form the source system used.
        s = unicodedata.normalize("NFC", s)
        label = s[4:] if s[:4].lower() == "sub-" else s
        label = re.sub(r"[^A-Za-z0-9]+", "", label)
        if not label:
            return ""
        return f"sub-{label}"

    existing_project_root_for_matching = _resolve_existing_project_root(project_path)
    subject_id_match = build_subject_id_matcher(
        load_existing_participant_ids(existing_project_root_for_matching)
        if existing_project_root_for_matching is not None
        else set()
    )

    def normalize_sub(val) -> str:
        normalized = _normalize_sub_id_raw(val)
        if not normalized:
            return normalized
        return subject_id_match(normalized) or normalized

    def normalize_ses(val) -> str:
        s = sanitize_id(str(val).strip())
        if not s:
            return "ses-1"
        if s.lower() == "nan":
            return "ses-1"
        label = s[4:] if s[:4].lower() == "ses-" else s
        label = re.sub(r"[^A-Za-z0-9]+", "", label)
        if not label:
            return "ses-1"
        return f"ses-{label}"

    def normalize_run(val) -> str | None:
        s = sanitize_id(str(val).strip())
        if not s or s.lower() == "nan":
            return None
        label = s[4:] if s[:4].lower() == "run-" else s
        label = re.sub(r"[^A-Za-z0-9]+", "", label)
        if not label:
            return None
        return f"run-{label}"

    def is_missing(val) -> bool:
        if pd.isna(val):
            return True
        if isinstance(val, str) and val.strip() == "":
            return True
        return False

    return SurveyIdNormalizers(
        normalize_sub=normalize_sub,
        normalize_ses=normalize_ses,
        normalize_run=normalize_run,
        is_missing=is_missing,
    )
```

`is_missing` uses the module-level `pd` already imported at the top of `survey_core.py` (`try: import pandas as pd / except ImportError: pd = None`) — do not add a local `import pandas` inside this function. If `Any` isn't already imported from `typing` in `survey_core.py`, add it (it already imports several `typing` names).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_survey_id_normalizers.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Wire into the orchestrator**

In `survey.py`'s `_convert_survey_dataframe_to_prism_dataset`, replace the block from `# Determine normalization logic` through the `_is_missing_value` function definition (locate by content — grep `def _normalize_sub_id_raw` inside this function) with:

```python
    id_normalizers = _survey_core.build_survey_id_normalizers(project_path)
    _normalize_sub_id = id_normalizers.normalize_sub
    _normalize_ses_id = id_normalizers.normalize_ses
    _normalize_run_id = id_normalizers.normalize_run
    _is_missing_value = id_normalizers.is_missing
```

Keeping the four local names (`_normalize_sub_id` etc.) bound to the returned callables means every downstream reference to them in the rest of this 668-line function needs zero further changes — this is deliberate, don't rename the call sites. `survey.py` already does `from . import survey_core as _survey_core` at the top, so `_survey_core.build_survey_id_normalizers` resolves without a new import.

- [ ] **Step 6: Run the regression command from Global Constraints**

Confirm the pass count matches Step 0.3's baseline.

- [ ] **Step 7: Commit**

```bash
git add app/src/converters/survey_core.py app/src/converters/survey.py tests/test_survey_id_normalizers.py
git commit -m "refactor: extract build_survey_id_normalizers from the survey orchestrator"
```

---

### Task 2: `_load_survey_aliases_and_templates` — TDD, survey_core.py

**Files:**
- Modify: `app/src/converters/survey_core.py`
- Modify: `app/src/converters/survey.py`
- Test: `tests/test_survey_alias_template_loading.py` (new)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `SurveyAliasesAndTemplates` (dataclass: `alias_map: dict[str, str] | None`, `participant_template: dict | None`, `participant_columns_lower: set[str]`, `templates: dict[str, dict]`, `item_to_task: dict[str, str]`, `template_warnings_by_task: dict`, `warnings: list[str]`) and `_load_survey_aliases_and_templates(*, participants_converter, library_dir: Path, alias_file: str | Path | None, load_and_preprocess_templates_fn) -> SurveyAliasesAndTemplates`, both in `survey_core.py`.

`ParticipantsConverter` (the class whose instance is passed in as `participants_converter`) lives in `survey.py` — this function takes an already-constructed instance rather than importing the class, avoiding a cycle. Likewise, `_load_and_preprocess_templates` (survey.py's thin wrapper around `_survey_templates._load_and_preprocess_templates`, itself needing two more survey.py-local callback functions) is passed in as `load_and_preprocess_templates_fn` rather than reached for directly — same reasoning, same established pattern (this file already injects callables like this dozens of times).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_survey_alias_template_loading.py`:

```python
from pathlib import Path

from src.converters.survey_core import _load_survey_aliases_and_templates


class _FakeParticipantsConverter:
    def __init__(self, template=None, compare_result=(True, set(), set(), [])):
        self._template = template
        self._compare_result = compare_result

    def load_template(self, library_dir):
        return self._template

    def normalize_template(self, raw_template):
        return raw_template

    def compare_with_global(self, raw_template):
        return self._compare_result


def _fake_load_and_preprocess_templates(library_dir, canonical_aliases, compare_with_global=True):
    return ({"panas": {"json": {}}}, {"panas_1": "panas"}, {}, {})


def test_returns_templates_from_injected_loader(tmp_path):
    result = _load_survey_aliases_and_templates(
        participants_converter=_FakeParticipantsConverter(),
        library_dir=tmp_path,
        alias_file=None,
        load_and_preprocess_templates_fn=_fake_load_and_preprocess_templates,
    )

    assert result.templates == {"panas": {"json": {}}}
    assert result.item_to_task == {"panas_1": "panas"}
    assert result.alias_map is None


def test_participant_template_columns_are_lowercased(tmp_path):
    result = _load_survey_aliases_and_templates(
        participants_converter=_FakeParticipantsConverter(
            template={"Age": {}, "Sex": {}}
        ),
        library_dir=tmp_path,
        alias_file=None,
        load_and_preprocess_templates_fn=_fake_load_and_preprocess_templates,
    )

    assert result.participant_columns_lower == {"age", "sex"}


def test_participant_template_compare_warnings_are_collected(tmp_path):
    result = _load_survey_aliases_and_templates(
        participants_converter=_FakeParticipantsConverter(
            template={"Age": {}},
            compare_result=(False, set(), set(), ["Age column differs from global template"]),
        ),
        library_dir=tmp_path,
        alias_file=None,
        load_and_preprocess_templates_fn=_fake_load_and_preprocess_templates,
    )

    assert "Age column differs from global template" in result.warnings


def test_alias_file_builds_alias_map(tmp_path):
    alias_file = tmp_path / "aliases.csv"
    alias_file.write_text("alias,canonical\nq1,item_1\n")

    result = _load_survey_aliases_and_templates(
        participants_converter=_FakeParticipantsConverter(),
        library_dir=tmp_path,
        alias_file=alias_file,
        load_and_preprocess_templates_fn=_fake_load_and_preprocess_templates,
    )

    assert result.alias_map is not None


def test_duplicate_item_ids_raise_value_error(tmp_path):
    def _loader_with_duplicates(library_dir, canonical_aliases, compare_with_global=True):
        return ({}, {}, {"item_1": {"panas", "phq9"}}, {})

    import pytest

    with pytest.raises(ValueError, match="Duplicate item IDs"):
        _load_survey_aliases_and_templates(
            participants_converter=_FakeParticipantsConverter(),
            library_dir=tmp_path,
            alias_file=None,
            load_and_preprocess_templates_fn=_loader_with_duplicates,
        )
```

Note: `test_alias_file_builds_alias_map` writes a real CSV and relies on `_read_alias_rows`/`_build_alias_map` (already-existing functions this new function calls) to parse it — if the header names `alias,canonical` don't match what `_read_alias_rows` actually expects, check `survey_core.py::_read_alias_rows` for the real expected format and fix the fixture, not the implementation.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_survey_alias_template_loading.py -v`
Expected: FAIL with `ImportError: cannot import name '_load_survey_aliases_and_templates'`.

- [ ] **Step 3: Implement `_load_survey_aliases_and_templates`**

Add to `survey_core.py`:

```python
@dataclass(frozen=True)
class SurveyAliasesAndTemplates:
    alias_map: Optional[Dict[str, str]]
    participant_template: Optional[dict]
    participant_columns_lower: Set[str]
    templates: Dict[str, dict]
    item_to_task: Dict[str, str]
    template_warnings_by_task: dict
    warnings: List[str]


def _load_survey_aliases_and_templates(
    *,
    participants_converter,
    library_dir: Path,
    alias_file,
    load_and_preprocess_templates_fn,
) -> SurveyAliasesAndTemplates:
    """Load alias mappings and survey/participant templates for conversion.

    Raises ValueError if duplicate item IDs are found across templates.
    """
    alias_map: Optional[Dict[str, str]] = None
    canonical_aliases: Optional[Dict[str, List[str]]] = None
    if alias_file:
        alias_path = Path(alias_file).resolve()
        if alias_path.exists() and alias_path.is_file():
            rows = _read_alias_rows(alias_path)
            if rows:
                alias_map = _build_alias_map(rows)
                canonical_aliases = _build_canonical_aliases(rows)

    raw_participant_template = participants_converter.load_template(library_dir)
    participant_template = participants_converter.normalize_template(
        raw_participant_template
    )
    participant_columns_lower: Set[str] = set()
    if participant_template:
        participant_columns_lower = {
            str(k).strip().lower()
            for k in participant_template.keys()
            if isinstance(k, str)
        }

    warnings: List[str] = []
    if raw_participant_template:
        _, _, _, part_warnings = participants_converter.compare_with_global(
            raw_participant_template
        )
        warnings.extend(part_warnings)

    templates, item_to_task, duplicates, template_warnings_by_task = (
        load_and_preprocess_templates_fn(
            library_dir,
            canonical_aliases,
            compare_with_global=True,
        )
    )
    if duplicates:
        msg_lines = [
            "Duplicate item IDs found across survey templates (ambiguous mapping):"
        ]
        for it_id, tsks in sorted(duplicates.items()):
            msg_lines.append(f"- {it_id}: {', '.join(sorted(tsks))}")
        raise ValueError("\n".join(msg_lines))

    return SurveyAliasesAndTemplates(
        alias_map=alias_map,
        participant_template=participant_template,
        participant_columns_lower=participant_columns_lower,
        templates=templates,
        item_to_task=item_to_task,
        template_warnings_by_task=template_warnings_by_task,
        warnings=warnings,
    )
```

`_read_alias_rows`, `_build_alias_map`, `_build_canonical_aliases` are already defined in `survey_core.py` itself — no new import needed for those. `Optional`/`Dict`/`List`/`Set` are already imported at the top of `survey_core.py` (confirmed: `from typing import Any, Dict, Iterable, List, Optional, Set, Tuple`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_survey_alias_template_loading.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Wire into the orchestrator**

In `survey.py`, replace the block from `# --- Load Aliases and Templates ---` through the `if duplicates:` raise (locate by content) with:

```python
    participants_converter = ParticipantsConverter()
    loaded = _survey_core._load_survey_aliases_and_templates(
        participants_converter=participants_converter,
        library_dir=library_dir,
        alias_file=alias_file,
        load_and_preprocess_templates_fn=_load_and_preprocess_templates,
    )
    alias_map = loaded.alias_map
    participant_template = loaded.participant_template
    participant_columns_lower = loaded.participant_columns_lower
    templates = loaded.templates
    item_to_task = loaded.item_to_task
    template_warnings_by_task = loaded.template_warnings_by_task
    conversion_warnings: list[str] = list(loaded.warnings)
```

This replaces the original `conversion_warnings: list[str] = []` initialization too — it's now seeded with `loaded.warnings` instead of starting empty and being `.extend()`-ed. Keep every downstream reference to `alias_map`, `participant_template`, `participant_columns_lower`, `templates`, `item_to_task`, `template_warnings_by_task`, `conversion_warnings`, and `participants_converter` (the last one is still used later, at the `participants_converter.write_participants(...)` call) unchanged — this step only replaces how they get their initial values, not their names.

- [ ] **Step 6: Run the regression command from Global Constraints**

- [ ] **Step 7: Commit**

```bash
git add app/src/converters/survey_core.py app/src/converters/survey.py tests/test_survey_alias_template_loading.py
git commit -m "refactor: extract _load_survey_aliases_and_templates from the survey orchestrator"
```

---

### Task 3: `_apply_lsa_structural_matching` — TDD, survey_lsa.py

**Files:**
- Modify: `app/src/converters/survey_lsa.py`
- Modify: `app/src/converters/survey.py`
- Test: `tests/test_survey_lsa_structural_matching.py` (new)

**Interfaces:**
- Consumes: nothing from Tasks 1-2 directly, but runs after them in the orchestrator (needs `templates`/`item_to_task`/`participant_columns_lower` from Task 2's output).
- Produces: `_apply_lsa_structural_matching(*, templates: dict, item_to_task: dict, participant_columns_lower: set[str], lsa_analysis: dict | None, survey_filter: str | None, add_matched_template_fn, unmatched_groups_error_cls) -> list[str]` in `survey_lsa.py`. Mutates `templates`/`item_to_task` in place (matching the original inline behavior — this is a real, deliberate side effect, not an oversight). Returns the warnings list. Raises `unmatched_groups_error_cls(unmatched=..., message=...)` if any group is left unmatched.

`_register_participant_columns_from_lsa_group` and `_collect_unmatched_lsa_group` already live in `survey_lsa.py` — once this new function lives there too, call them unqualified (no DI needed, no import needed). `_add_matched_template` (survey.py's thin wrapper around `_survey_templates._add_matched_template`) and `UnmatchedGroupsError` (a custom exception class defined in `survey.py`, used elsewhere by callers that catch it via its `survey.py` import path — do not move the class itself) both need DI, since `survey_lsa.py` importing back from `survey.py` would cycle.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_survey_lsa_structural_matching.py`:

```python
import pytest

from src.converters.survey_lsa import _apply_lsa_structural_matching


class _FakeMatch:
    def __init__(self, is_participants=False, confidence="exact", template_key="panas",
                 overlap_count=5, template_items=5):
        self.is_participants = is_participants
        self.confidence = confidence
        self.template_key = template_key
        self.overlap_count = overlap_count
        self.template_items = template_items


class _FakeUnmatchedGroupsError(ValueError):
    def __init__(self, unmatched, message):
        super().__init__(message)
        self.unmatched = unmatched


def test_no_lsa_analysis_is_a_no_op():
    templates = {}
    item_to_task = {}
    warnings = _apply_lsa_structural_matching(
        templates=templates,
        item_to_task=item_to_task,
        participant_columns_lower=set(),
        lsa_analysis=None,
        survey_filter=None,
        add_matched_template_fn=lambda *a: None,
        unmatched_groups_error_cls=_FakeUnmatchedGroupsError,
    )
    assert warnings == []
    assert templates == {}


def test_survey_filter_set_skips_structural_matching_entirely():
    add_matched_calls = []
    lsa_analysis = {"groups": {"g1": {"match": _FakeMatch(confidence="exact")}}}

    _apply_lsa_structural_matching(
        templates={},
        item_to_task={},
        participant_columns_lower=set(),
        lsa_analysis=lsa_analysis,
        survey_filter="panas",
        add_matched_template_fn=lambda *a: add_matched_calls.append(a),
        unmatched_groups_error_cls=_FakeUnmatchedGroupsError,
    )
    assert add_matched_calls == []


def test_exact_confidence_match_calls_add_matched_template_with_no_warning():
    add_matched_calls = []
    lsa_analysis = {"groups": {"g1": {"match": _FakeMatch(confidence="exact")}}}

    warnings = _apply_lsa_structural_matching(
        templates={},
        item_to_task={},
        participant_columns_lower=set(),
        lsa_analysis=lsa_analysis,
        survey_filter=None,
        add_matched_template_fn=lambda *a: add_matched_calls.append(a),
        unmatched_groups_error_cls=_FakeUnmatchedGroupsError,
    )
    assert len(add_matched_calls) == 1
    assert warnings == []


def test_medium_confidence_match_calls_add_matched_template_and_warns():
    lsa_analysis = {
        "groups": {"g1": {"match": _FakeMatch(confidence="medium", template_key="phq9")}}
    }

    warnings = _apply_lsa_structural_matching(
        templates={},
        item_to_task={},
        participant_columns_lower=set(),
        lsa_analysis=lsa_analysis,
        survey_filter=None,
        add_matched_template_fn=lambda *a: None,
        unmatched_groups_error_cls=_FakeUnmatchedGroupsError,
    )
    assert len(warnings) == 1
    assert "medium confidence" in warnings[0]
    assert "phq9" in warnings[0]


def test_unmatched_group_raises_the_injected_error_class():
    lsa_analysis = {"groups": {"g1": {"match": None}}}

    with pytest.raises(_FakeUnmatchedGroupsError) as exc_info:
        _apply_lsa_structural_matching(
            templates={},
            item_to_task={},
            participant_columns_lower=set(),
            lsa_analysis=lsa_analysis,
            survey_filter=None,
            add_matched_template_fn=lambda *a: None,
            unmatched_groups_error_cls=_FakeUnmatchedGroupsError,
        )
    assert len(exc_info.value.unmatched) == 1


def test_is_participants_group_registers_participant_columns_not_a_template():
    add_matched_calls = []
    lsa_analysis = {
        "groups": {
            "g1": {
                "match": _FakeMatch(is_participants=True),
                "questions": {"age": {}, "sex": {}},
            }
        }
    }

    _apply_lsa_structural_matching(
        templates={},
        item_to_task={},
        participant_columns_lower=set(),
        lsa_analysis=lsa_analysis,
        survey_filter=None,
        add_matched_template_fn=lambda *a: add_matched_calls.append(a),
        unmatched_groups_error_cls=_FakeUnmatchedGroupsError,
    )
    assert add_matched_calls == []
```

Note: `test_is_participants_group_registers_participant_columns_not_a_template`'s exact fixture shape for `group_info` depends on what `_register_participant_columns_from_lsa_group` actually reads from it — check `survey_lsa.py::_register_participant_columns_from_lsa_group`'s body for the real expected keys before trusting `{"questions": {...}}` above; adjust the fixture (not the implementation) if it's wrong. The test only needs to prove `add_matched_template_fn` was NOT called for this branch — it doesn't need to assert on the participant-registration side effect itself.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_survey_lsa_structural_matching.py -v`
Expected: FAIL with `ImportError: cannot import name '_apply_lsa_structural_matching'`.

- [ ] **Step 3: Implement `_apply_lsa_structural_matching`**

Add to `survey_lsa.py` (needs `from ..utils.naming import sanitize_task_name` at the top of the file — check it's not already there before adding):

```python
def _apply_lsa_structural_matching(
    *,
    templates: dict,
    item_to_task: dict,
    participant_columns_lower: set,
    lsa_analysis,
    survey_filter,
    add_matched_template_fn,
    unmatched_groups_error_cls,
) -> list:
    """Classify each LSA structural-match group (participants / high-confidence
    match / medium-confidence match / unmatched) and register templates or
    participant columns accordingly.

    Mutates templates and item_to_task in place. Returns the warnings
    collected along the way. Raises unmatched_groups_error_cls if any group
    ends up with no usable match.
    """
    unmatched_groups: list = []
    warnings: list = []

    if lsa_analysis and not survey_filter:
        for group_name, group_info in lsa_analysis["groups"].items():
            match = group_info.get("match")
            if match and match.is_participants:
                _register_participant_columns_from_lsa_group(
                    group_info=group_info,
                    participant_columns_lower=participant_columns_lower,
                )
            elif match and match.confidence in ("exact", "high"):
                add_matched_template_fn(templates, item_to_task, match, group_info)
            elif match and match.confidence == "medium":
                add_matched_template_fn(templates, item_to_task, match, group_info)
                warnings.append(
                    f"Group '{group_name}' matched template '{match.template_key}' "
                    f"with medium confidence ({match.overlap_count}/{match.template_items} items). "
                    f"Review the match to ensure correctness."
                )
            else:
                _collect_unmatched_lsa_group(
                    group_name=group_name,
                    group_info=group_info,
                    unmatched_groups=unmatched_groups,
                    non_item_toplevel_keys=_NON_ITEM_TOPLEVEL_KEYS,
                    sanitize_task_name_fn=sanitize_task_name,
                )
                if match:
                    warnings.append(
                        f"Group '{group_name}' had low-confidence match to "
                        f"'{match.template_key}'. No suitable template found."
                    )

    if unmatched_groups:
        names = [g["group_name"] for g in unmatched_groups]
        raise unmatched_groups_error_cls(
            unmatched=unmatched_groups,
            message=(
                f"No library template found for {len(unmatched_groups)} group(s): "
                f"{', '.join(names)}. Save templates to project library first, "
                f"then re-run conversion."
            ),
        )

    return warnings
```

`_NON_ITEM_TOPLEVEL_KEYS` is already imported at the top of `survey_lsa.py` (`from .survey_core import _NON_ITEM_TOPLEVEL_KEYS`) — confirmed, no change needed there.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_survey_lsa_structural_matching.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Wire into the orchestrator**

In `survey.py`, replace the block from `# --- LSA Structural Matching ---` through the `if unmatched_groups:` raise (locate by content) with:

```python
    conversion_warnings.extend(
        _survey_lsa._apply_lsa_structural_matching(
            templates=templates,
            item_to_task=item_to_task,
            participant_columns_lower=participant_columns_lower,
            lsa_analysis=lsa_analysis,
            survey_filter=survey,
            add_matched_template_fn=_add_matched_template,
            unmatched_groups_error_cls=UnmatchedGroupsError,
        )
    )
```

`survey.py` already does `from . import survey_lsa as _survey_lsa` at the top. `_add_matched_template` and `UnmatchedGroupsError` both still live in `survey.py` (unmoved, per this task's design) so they're referenced unqualified, exactly as they are today.

- [ ] **Step 6: Run the regression command from Global Constraints**

- [ ] **Step 7: Commit**

```bash
git add app/src/converters/survey_lsa.py app/src/converters/survey.py tests/test_survey_lsa_structural_matching.py
git commit -m "refactor: extract _apply_lsa_structural_matching from the survey orchestrator"
```

---

### Task 4: Move `_map_survey_columns` wholesale to new `survey_column_mapping.py`

**Files:**
- Create: `app/src/converters/survey_column_mapping.py`
- Modify: `app/src/converters/survey.py`
- Test: none new (pure move — regression net only)

**Interfaces:**
- Produces (importable from `survey_column_mapping.py`): `ColumnMapping` (dataclass), `_map_survey_columns` (unchanged signature/behavior), plus its private support definitions.

- [ ] **Step 1: Confirm the regression baseline is green**

Run the regression command from Global Constraints, note the pass count.

- [ ] **Step 2: Create `survey_column_mapping.py`**

Cut these from `survey.py`, verbatim, in this order (locate each by name — grep, since exact current line numbers have shifted after Tasks 1-3):

- `class ColumnMapping` (a `@dataclass` with fields `task: str`, `run: int | None`, `base_item: str`)
- `_NEAR_MATCH_SEPARATOR_RE`, `_NEAR_MATCH_NON_ALNUM_RE`, `_NEAR_MATCH_DIGITS_RE` (three module-level compiled regexes)
- `_normalize_near_match_item_code`
- `_collect_primary_template_items`
- `_map_survey_columns` itself

Verify with grep that none of these five names/constants are referenced anywhere else in `survey.py` outside this block before cutting (they were confirmed isolated to this block during planning, but confirm again against the current file state — this has been true in every prior task in this project so far, but never assume).

Add this import block at the top of the new file:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

from .survey_core import _NON_ITEM_TOPLEVEL_KEYS
from .survey_processing import _parse_run_from_column
```

- [ ] **Step 3: Update `survey.py`'s imports**

Remove `class ColumnMapping`, the three regexes, `_normalize_near_match_item_code`, `_collect_primary_template_items`, and `_map_survey_columns` from `survey.py` (already cut in Step 2). Check whether `cast` (from `typing`) is still used anywhere else in `survey.py` — if not, it can be dropped from `survey.py`'s own `from typing import cast` line, but only if you've confirmed via grep it's genuinely unused elsewhere; leave it if there's any other use.

Add:

```python
from . import survey_column_mapping as _survey_column_mapping
```

matching the existing qualified-module-import style already used for `_survey_lsa`, `_survey_io`, etc.

- [ ] **Step 4: Update the orchestrator's call site**

The orchestrator currently calls `_map_survey_columns(...)` unqualified (locate by grep — it's the call that unpacks into `col_to_mapping, unknown_cols, map_warnings, task_runs, near_match_candidates, near_match_applied`). Change it to `_survey_column_mapping._map_survey_columns(...)` — same arguments, same unpacking, nothing else changes.

- [ ] **Step 5: Verify the module resolves live (drift check)**

Run: `python3 -c "import src.converters.survey_column_mapping as m; print(m.__file__)"`
Expected: prints a path ending in `app/src/converters/survey_column_mapping.py`.

- [ ] **Step 6: Run the regression command from Global Constraints**

Confirm the pass count matches Step 1's baseline.

- [ ] **Step 7: Commit**

```bash
git add app/src/converters/survey_column_mapping.py app/src/converters/survey.py
git commit -m "refactor: move _map_survey_columns into new survey_column_mapping.py"
```

---

### Task 5: TDD — extract `_match_columns_to_templates` from `_map_survey_columns`

**Files:**
- Modify: `app/src/converters/survey_column_mapping.py`
- Test: `tests/test_survey_column_mapping.py` (new)

**Interfaces:**
- Produces: `_match_columns_to_templates(*, df, item_to_task: dict[str, str], participant_columns_lower: set[str], id_col: str, ses_col: str | None, run_col: str | None) -> tuple[dict[str, ColumnMapping], list[str], dict[str, set[int | None]]]` — returns `(col_to_mapping, unknown_cols, task_run_tracker)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_survey_column_mapping.py`:

```python
import pandas as pd

from src.converters.survey_column_mapping import ColumnMapping, _match_columns_to_templates


def test_exact_match_maps_column_to_task():
    df = pd.DataFrame({"id": ["001"], "panas_1": ["3"]})

    col_to_mapping, unknown_cols, task_run_tracker = _match_columns_to_templates(
        df=df,
        item_to_task={"panas_1": "panas"},
        participant_columns_lower=set(),
        id_col="id",
        ses_col=None,
        run_col=None,
    )

    assert col_to_mapping["panas_1"] == ColumnMapping(task="panas", run=None, base_item="panas_1")
    assert unknown_cols == []
    assert task_run_tracker == {"panas": {None}}


def test_run_suffixed_column_matches_base_item():
    df = pd.DataFrame({"id": ["001"], "panas_1_run-02": ["3"]})

    col_to_mapping, unknown_cols, task_run_tracker = _match_columns_to_templates(
        df=df,
        item_to_task={"panas_1": "panas"},
        participant_columns_lower=set(),
        id_col="id",
        ses_col=None,
        run_col=None,
    )

    assert col_to_mapping["panas_1_run-02"] == ColumnMapping(task="panas", run=2, base_item="panas_1")
    assert task_run_tracker == {"panas": {2}}


def test_unmatched_column_becomes_unknown():
    df = pd.DataFrame({"id": ["001"], "mystery_col": ["x"]})

    col_to_mapping, unknown_cols, task_run_tracker = _match_columns_to_templates(
        df=df,
        item_to_task={},
        participant_columns_lower=set(),
        id_col="id",
        ses_col=None,
        run_col=None,
    )

    assert col_to_mapping == {}
    assert unknown_cols == ["mystery_col"]


def test_participant_column_is_skipped_not_treated_as_unknown():
    df = pd.DataFrame({"id": ["001"], "age": ["25"]})

    col_to_mapping, unknown_cols, task_run_tracker = _match_columns_to_templates(
        df=df,
        item_to_task={},
        participant_columns_lower={"age"},
        id_col="id",
        ses_col=None,
        run_col=None,
    )

    assert col_to_mapping == {}
    assert unknown_cols == []


def test_id_and_session_and_run_columns_are_excluded_from_matching():
    df = pd.DataFrame({"id": ["001"], "ses": ["1"], "run": ["1"], "panas_1": ["3"]})

    col_to_mapping, unknown_cols, task_run_tracker = _match_columns_to_templates(
        df=df,
        item_to_task={"panas_1": "panas"},
        participant_columns_lower=set(),
        id_col="id",
        ses_col="ses",
        run_col="run",
    )

    assert "id" not in col_to_mapping and "id" not in unknown_cols
    assert "ses" not in col_to_mapping and "ses" not in unknown_cols
    assert "run" not in col_to_mapping and "run" not in unknown_cols
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_survey_column_mapping.py -v`
Expected: FAIL with `ImportError: cannot import name '_match_columns_to_templates'`.

- [ ] **Step 3: Implement `_match_columns_to_templates`**

Add to `survey_column_mapping.py`, placed before `_map_survey_columns`:

```python
def _match_columns_to_templates(
    *,
    df,
    item_to_task: dict[str, str],
    participant_columns_lower: set[str],
    id_col: str,
    ses_col: str | None,
    run_col: str | None,
) -> tuple[dict[str, ColumnMapping], list[str], dict[str, set[int | None]]]:
    """Exact-match each non-id/session/run column against item_to_task,
    tolerating a PRISM run suffix ({item}_run-{NN})."""
    lower_to_col = {str(c).strip().lower(): str(c).strip() for c in df.columns}

    participant_fallbacks = {
        "age",
        "sex",
        "gender",
        "education",
        "handedness",
        "completion_date",
    }
    participant_columns_present = {
        lower_to_col[c]
        for c in (participant_columns_lower | participant_fallbacks)
        if c in lower_to_col
    }

    cols = [
        c for c in df.columns if c not in {id_col} and c != ses_col and c != run_col
    ]
    col_to_mapping: dict[str, ColumnMapping] = {}
    unknown_cols: list[str] = []
    task_run_tracker: dict[str, set[int | None]] = {}

    for c in cols:
        col_lower = str(c).strip().lower()

        if c in participant_columns_present or col_lower in participant_columns_present:
            continue
        if col_lower in participant_columns_lower:
            continue

        base_name, run_num = _parse_run_from_column(c)

        matched_task = None
        matched_base = c
        if c in item_to_task:
            matched_task = item_to_task[c]
            matched_base = c
        elif base_name in item_to_task:
            matched_task = item_to_task[base_name]
            matched_base = base_name

        if matched_task:
            col_to_mapping[c] = ColumnMapping(
                task=matched_task, run=run_num, base_item=matched_base
            )
            if matched_task not in task_run_tracker:
                task_run_tracker[matched_task] = set()
            task_run_tracker[matched_task].add(run_num)
        else:
            unknown_cols.append(c)

    return col_to_mapping, unknown_cols, task_run_tracker
```

`ColumnMapping` needs `eq=True` for the tests' `==` comparisons — a plain `@dataclass` (no `frozen`/`eq` overrides) already generates `__eq__`, so no change needed to the class itself.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_survey_column_mapping.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Wire into `_map_survey_columns`**

Replace the block from `lower_to_col = {str(c)...}` through the final `else: unknown_cols.append(c)` loop end (the whole exact-matching phase, locate by content) with:

```python
    col_to_mapping, unknown_cols, task_run_tracker = _match_columns_to_templates(
        df=df,
        item_to_task=item_to_task,
        participant_columns_lower=participant_columns_lower,
        id_col=id_col,
        ses_col=ses_col,
        run_col=run_col,
    )
```

Everything downstream in `_map_survey_columns` (the `warnings`/`bookkeeping`/`filtered_unknown` construction) references `col_to_mapping`, `unknown_cols`, `task_run_tracker` exactly as before — no other changes needed in this step.

- [ ] **Step 6: Run the regression command from Global Constraints**

- [ ] **Step 7: Commit**

```bash
git add app/src/converters/survey_column_mapping.py tests/test_survey_column_mapping.py
git commit -m "refactor: extract _match_columns_to_templates from _map_survey_columns"
```

---

### Task 6: TDD — extract `_find_near_match_candidates` from `_map_survey_columns`

**Files:**
- Modify: `app/src/converters/survey_column_mapping.py`
- Modify: `tests/test_survey_column_mapping.py`

**Interfaces:**
- Consumes: `ColumnMapping` from Task 5 (already in this file).
- Produces: `_find_near_match_candidates(*, filtered_unknown: list[str], templates: dict[str, dict] | None, selected_tasks: set[str] | None, col_to_mapping: dict[str, ColumnMapping]) -> tuple[list[dict[str, object]], list[str]]` — returns `(near_match_candidates, warnings)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_survey_column_mapping.py`:

```python
from src.converters.survey_column_mapping import _find_near_match_candidates


def _panas_template():
    return {
        "panas": {
            "json": {
                "panas_1": {"Description": "item 1"},
                "panas_2": {"Description": "item 2"},
            }
        }
    }


def test_single_near_match_candidate_is_found_when_it_completes_full_item_set():
    # panas has 2 primary items; panas_1 is exactly mapped already, panas-2
    # (hyphen instead of underscore) is unmapped but near-matches panas_2 --
    # applying it would give a full 1:1 item-count match, so it's approved.
    col_to_mapping = {"panas_1": ColumnMapping(task="panas", run=None, base_item="panas_1")}

    candidates, warnings = _find_near_match_candidates(
        filtered_unknown=["panas-2"],
        templates=_panas_template(),
        selected_tasks=None,
        col_to_mapping=col_to_mapping,
    )

    assert len(candidates) == 1
    assert candidates[0]["source_column"] == "panas-2"
    assert candidates[0]["target_item"] == "panas_2"
    assert candidates[0]["task"] == "panas"
    assert warnings == []


def test_partial_item_count_match_is_rejected_with_a_warning():
    # panas has 2 primary items, neither exactly mapped. Only one near-match
    # candidate exists (panas-1) -- proposing 1 item when 2 are missing is
    # not a full 1:1 match, so it's rejected.
    candidates, warnings = _find_near_match_candidates(
        filtered_unknown=["panas-1"],
        templates=_panas_template(),
        selected_tasks=None,
        col_to_mapping={},
    )

    assert candidates == []
    assert len(warnings) == 1
    assert "ignored" in warnings[0]


def test_no_templates_returns_no_candidates():
    candidates, warnings = _find_near_match_candidates(
        filtered_unknown=["panas-2"],
        templates=None,
        selected_tasks=None,
        col_to_mapping={},
    )
    assert candidates == []
    assert warnings == []


def test_selected_tasks_scopes_which_templates_are_considered():
    col_to_mapping = {"panas_1": ColumnMapping(task="panas", run=None, base_item="panas_1")}

    candidates, _ = _find_near_match_candidates(
        filtered_unknown=["panas-2"],
        templates=_panas_template(),
        selected_tasks={"phq9"},  # panas excluded from scope
        col_to_mapping=col_to_mapping,
    )

    assert candidates == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_survey_column_mapping.py -v -k near_match_candidates`
Expected: FAIL with `ImportError: cannot import name '_find_near_match_candidates'`.

- [ ] **Step 3: Implement `_find_near_match_candidates`**

Add to `survey_column_mapping.py` (needs `_normalize_near_match_item_code`, `_collect_primary_template_items`, `_parse_run_from_column` — all already in this file/its imports after Task 4's move):

```python
def _find_near_match_candidates(
    *,
    filtered_unknown: list[str],
    templates: dict[str, dict] | None,
    selected_tasks: set[str] | None,
    col_to_mapping: dict[str, ColumnMapping],
) -> tuple[list[dict[str, object]], list[str]]:
    """Find unmapped columns that near-match a template item (tolerating
    separator/casing/zero-padding differences), conservatively: only
    approved when applying every candidate for a task would produce a full
    1:1 item-count match against that task's remaining unmapped items, or
    the candidates carry explicit run context."""
    near_match_candidates: list[dict[str, object]] = []
    warnings: list[str] = []

    if not (filtered_unknown and templates):
        return near_match_candidates, warnings

    scoped_tasks = set(selected_tasks) if selected_tasks else set(templates.keys())

    task_primary_items: dict[str, set[str]] = {}
    task_alias_lookup: dict[str, dict[str, str]] = {}
    normalized_item_lookup: dict[str, set[tuple[str, str]]] = {}

    for task, template_data in templates.items():
        if task not in scoped_tasks:
            continue
        template_json = (
            template_data.get("json") if isinstance(template_data, dict) else None
        )
        if not isinstance(template_json, dict):
            continue

        primary_items = _collect_primary_template_items(template_json)
        if not primary_items:
            continue
        task_primary_items[task] = primary_items

        aliases = template_json.get("_aliases")
        alias_lookup: dict[str, str] = {}
        if isinstance(aliases, dict):
            for alias, canonical in aliases.items():
                if not isinstance(alias, str) or not isinstance(canonical, str):
                    continue
                if canonical in primary_items:
                    alias_lookup[alias] = canonical
        task_alias_lookup[task] = alias_lookup

        for item_key in primary_items:
            normalized = _normalize_near_match_item_code(item_key)
            if not normalized:
                continue
            normalized_item_lookup.setdefault(normalized, set()).add((task, item_key))

    exact_mapped_by_task: dict[str, set[str]] = {}
    for mapping in col_to_mapping.values():
        if mapping.task not in task_primary_items:
            continue
        canonical = task_alias_lookup.get(mapping.task, {}).get(
            mapping.base_item, mapping.base_item
        )
        exact_mapped_by_task.setdefault(mapping.task, set()).add(canonical)

    task_candidates: dict[str, list[dict[str, object]]] = {}
    for source_column in filtered_unknown:
        base_name, run_num = _parse_run_from_column(source_column)
        normalized_base = _normalize_near_match_item_code(base_name)
        if not normalized_base:
            continue

        target_candidates = normalized_item_lookup.get(normalized_base) or set()
        if len(target_candidates) != 1:
            continue

        task, target_item = next(iter(target_candidates))
        task_candidates.setdefault(task, []).append(
            {
                "source_column": source_column,
                "source_base_item": base_name,
                "target_item": target_item,
                "task": task,
                "run": run_num,
            }
        )

    approved_candidates: list[dict[str, object]] = []
    for task, candidates in task_candidates.items():
        if task not in task_primary_items:
            continue
        primary_items = task_primary_items[task]
        if not primary_items:
            continue

        has_explicit_run_context = any(
            candidate.get("run") is not None for candidate in candidates
        )
        proposed_items = {
            str(candidate.get("target_item", ""))
            for candidate in candidates
            if candidate.get("target_item")
        }

        if not has_explicit_run_context:
            exact_items = exact_mapped_by_task.get(task, set())
            missing_items = primary_items - exact_items
            if proposed_items != missing_items or len(candidates) != len(
                missing_items
            ):
                warnings.append(
                    f"Near-match candidates for task '{task}' were ignored because "
                    "they do not produce a full one-to-one item count match."
                )
                continue

        seen_targets: set[tuple[str, object]] = set()
        has_duplicate_targets = False
        for candidate in candidates:
            target_item = str(candidate.get("target_item", "")).strip()
            target_run = candidate.get("run")
            key = (target_item, target_run)
            if key in seen_targets:
                has_duplicate_targets = True
                break
            seen_targets.add(key)

        if has_duplicate_targets:
            warnings.append(
                f"Near-match candidates for task '{task}' were ignored due to duplicate target mappings."
            )
            continue

        approved_candidates.extend(candidates)

    near_match_candidates = sorted(
        approved_candidates,
        key=lambda candidate: (
            str(candidate.get("task", "")),
            str(candidate.get("source_column", "")),
        ),
    )

    return near_match_candidates, warnings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_survey_column_mapping.py -v`
Expected: PASS (9 tests total in this file so far).

- [ ] **Step 5: Wire into `_map_survey_columns`**

Replace the block from `near_match_candidates: list[dict[str, object]] = []` through the `near_match_candidates = sorted(...)` assignment (the whole near-match-detection phase, locate by content — it starts right after the `filtered_unknown` construction and the `if filtered_unknown and templates:` conditional) with:

```python
    near_match_candidates, near_match_find_warnings = _find_near_match_candidates(
        filtered_unknown=filtered_unknown,
        templates=templates,
        selected_tasks=selected_tasks,
        col_to_mapping=col_to_mapping,
    )
    warnings.extend(near_match_find_warnings)
```

- [ ] **Step 6: Run the regression command from Global Constraints**

- [ ] **Step 7: Commit**

```bash
git add app/src/converters/survey_column_mapping.py tests/test_survey_column_mapping.py
git commit -m "refactor: extract _find_near_match_candidates from _map_survey_columns"
```

---

### Task 7: TDD — extract `_apply_approved_near_matches` from `_map_survey_columns`

**Files:**
- Modify: `app/src/converters/survey_column_mapping.py`
- Modify: `tests/test_survey_column_mapping.py`

**Interfaces:**
- Produces: `_apply_approved_near_matches(*, near_match_candidates: list[dict[str, object]], allow_near_item_match: bool, near_match_tasks: set[str] | None, col_to_mapping: dict[str, ColumnMapping], task_run_tracker: dict[str, set[int | None]], filtered_unknown: list[str]) -> tuple[list[str], bool, list[str]]` — returns `(filtered_unknown, near_match_applied, warnings)`. Mutates `col_to_mapping` and `task_run_tracker` in place (deliberate, matching the original inline behavior — both are passed-in mutable dicts the caller keeps using afterward).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_survey_column_mapping.py`:

```python
from src.converters.survey_column_mapping import _apply_approved_near_matches


def _one_candidate():
    return [
        {
            "source_column": "panas-2",
            "source_base_item": "panas-2",
            "target_item": "panas_2",
            "task": "panas",
            "run": None,
        }
    ]


def test_allow_near_item_match_false_leaves_everything_unapplied_but_warns():
    col_to_mapping = {}
    task_run_tracker = {}

    filtered_unknown, applied, warnings = _apply_approved_near_matches(
        near_match_candidates=_one_candidate(),
        allow_near_item_match=False,
        near_match_tasks=None,
        col_to_mapping=col_to_mapping,
        task_run_tracker=task_run_tracker,
        filtered_unknown=["panas-2"],
    )

    assert applied is False
    assert col_to_mapping == {}
    assert filtered_unknown == ["panas-2"]
    assert any("available after confirmation" in w for w in warnings)


def test_allow_near_item_match_true_applies_and_removes_from_unknown():
    col_to_mapping = {}
    task_run_tracker = {}

    filtered_unknown, applied, warnings = _apply_approved_near_matches(
        near_match_candidates=_one_candidate(),
        allow_near_item_match=True,
        near_match_tasks=None,
        col_to_mapping=col_to_mapping,
        task_run_tracker=task_run_tracker,
        filtered_unknown=["panas-2"],
    )

    assert applied is True
    assert col_to_mapping["panas-2"].task == "panas"
    assert col_to_mapping["panas-2"].base_item == "panas_2"
    assert filtered_unknown == []
    assert task_run_tracker == {"panas": {None}}
    assert any("Applied near item matches" in w for w in warnings)


def test_near_match_tasks_filter_excludes_non_matching_task_candidates():
    col_to_mapping = {}
    task_run_tracker = {}

    filtered_unknown, applied, warnings = _apply_approved_near_matches(
        near_match_candidates=_one_candidate(),
        allow_near_item_match=True,
        near_match_tasks={"phq9"},  # doesn't include "panas"
        col_to_mapping=col_to_mapping,
        task_run_tracker=task_run_tracker,
        filtered_unknown=["panas-2"],
    )

    assert applied is False
    assert col_to_mapping == {}
    assert any("none matched the selected survey tasks" in w for w in warnings)


def test_already_mapped_source_column_is_not_overwritten():
    from src.converters.survey_column_mapping import ColumnMapping

    col_to_mapping = {"panas-2": ColumnMapping(task="other", run=None, base_item="other_item")}
    task_run_tracker = {}

    _apply_approved_near_matches(
        near_match_candidates=_one_candidate(),
        allow_near_item_match=True,
        near_match_tasks=None,
        col_to_mapping=col_to_mapping,
        task_run_tracker=task_run_tracker,
        filtered_unknown=["panas-2"],
    )

    assert col_to_mapping["panas-2"].task == "other"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_survey_column_mapping.py -v -k apply_approved_near_matches`
Expected: FAIL with `ImportError: cannot import name '_apply_approved_near_matches'`.

- [ ] **Step 3: Implement `_apply_approved_near_matches`**

Add to `survey_column_mapping.py`:

```python
def _apply_approved_near_matches(
    *,
    near_match_candidates: list[dict[str, object]],
    allow_near_item_match: bool,
    near_match_tasks: set[str] | None,
    col_to_mapping: dict[str, ColumnMapping],
    task_run_tracker: dict[str, set[int | None]],
    filtered_unknown: list[str],
) -> tuple[list[str], bool, list[str]]:
    """Apply near-match candidates the caller has confirmed (allow_near_item_match),
    optionally restricted to near_match_tasks. Mutates col_to_mapping and
    task_run_tracker in place. Returns the updated filtered_unknown list,
    whether anything was applied, and any warnings."""
    near_match_task_filter: set[str] | None = None
    if near_match_tasks is not None:
        near_match_task_filter = {
            str(task).strip().lower() for task in near_match_tasks if str(task).strip()
        }

    near_match_applied = False
    warnings: list[str] = []

    if near_match_candidates and allow_near_item_match:
        candidates_to_apply = near_match_candidates
        if near_match_task_filter is not None:
            candidates_to_apply = [
                candidate
                for candidate in near_match_candidates
                if str(candidate.get("task", "")).strip().lower()
                in near_match_task_filter
            ]

        applied_columns: list[str] = []
        for candidate in candidates_to_apply:
            source_column = str(candidate.get("source_column", "")).strip()
            target_item = str(candidate.get("target_item", "")).strip()
            task = str(candidate.get("task", "")).strip()
            run_value = candidate.get("run")

            if not source_column or not target_item or not task:
                continue
            if source_column in col_to_mapping:
                continue

            col_to_mapping[source_column] = ColumnMapping(
                task=task,
                run=cast(int | None, run_value),
                base_item=target_item,
            )
            task_run_tracker.setdefault(task, set()).add(cast(int | None, run_value))
            applied_columns.append(source_column)

        if applied_columns:
            near_match_applied = True
            applied_set = set(applied_columns)
            filtered_unknown = [
                col for col in filtered_unknown if col not in applied_set
            ]
            shown = ", ".join(
                f"{candidate['source_column']}->{candidate['target_item']}"
                for candidate in candidates_to_apply[:8]
            )
            more = (
                ""
                if len(candidates_to_apply) <= 8
                else f" (+{len(candidates_to_apply) - 8} more)"
            )
            warnings.append(
                f"Applied near item matches after confirmation ({len(applied_columns)}): {shown}{more}"
            )
        skipped_candidate_count = len(near_match_candidates) - len(candidates_to_apply)
        if skipped_candidate_count > 0:
            warnings.append(
                f"Skipped {skipped_candidate_count} near-match candidate(s) for unselected survey tasks."
            )
        if not candidates_to_apply and near_match_task_filter is not None:
            warnings.append(
                "Near item matches were enabled, but none matched the selected survey tasks."
            )
    elif near_match_candidates:
        shown = ", ".join(
            f"{candidate['source_column']}->{candidate['target_item']}"
            for candidate in near_match_candidates[:8]
        )
        more = (
            ""
            if len(near_match_candidates) <= 8
            else f" (+{len(near_match_candidates) - 8} more)"
        )
        warnings.append(
            f"Near item matches available after confirmation ({len(near_match_candidates)}): {shown}{more}"
        )

    return filtered_unknown, near_match_applied, warnings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_survey_column_mapping.py -v`
Expected: PASS (13 tests total in this file).

- [ ] **Step 5: Wire into `_map_survey_columns`, completing its shrink to an orchestrator**

Replace the block from `near_match_task_filter: set[str] | None = None` through the last `warnings.append(f"Near item matches available...")` (the whole apply-near-matches phase, locate by content) with:

```python
    filtered_unknown, near_match_applied, near_match_apply_warnings = (
        _apply_approved_near_matches(
            near_match_candidates=near_match_candidates,
            allow_near_item_match=allow_near_item_match,
            near_match_tasks=near_match_tasks,
            col_to_mapping=col_to_mapping,
            task_run_tracker=task_run_tracker,
            filtered_unknown=filtered_unknown,
        )
    )
    warnings.extend(near_match_apply_warnings)
```

`_map_survey_columns` should now be roughly 60-80 lines: build `lower_to_col`-independent bookkeeping/regex setup, call `_match_columns_to_templates`, filter `unknown_cols` into `filtered_unknown`, call `_find_near_match_candidates`, call `_apply_approved_near_matches`, compute final `task_runs` from `task_run_tracker`, handle `unknown_mode`, return the 6-tuple. Confirm by reading the whole function after this step that nothing beyond this shape remains inline.

- [ ] **Step 6: Run the regression command from Global Constraints**

- [ ] **Step 7: Commit**

```bash
git add app/src/converters/survey_column_mapping.py tests/test_survey_column_mapping.py
git commit -m "refactor: extract _apply_approved_near_matches from _map_survey_columns"
```

---

### Task 8: Move `_write_survey_participants` wholesale to `survey_participants_logic.py`

**Files:**
- Modify: `app/src/converters/survey_participants_logic.py`
- Modify: `app/src/converters/survey.py`
- Test: none new (pure move — regression net only)

**Interfaces:**
- Produces (importable from `survey_participants_logic.py`): `_write_survey_participants`, now taking an additional required keyword parameter `missing_token: str` (see below), plus its private support definitions (`_auto_correct_participant_value`, `_find_matching_level_key`, `_safe_eval_formula`).

`_write_survey_participants` and its three support functions reference the module-level constant `_MISSING_TOKEN` (defined in `survey.py`, value `"n/a"`) directly today. Moving them to `survey_participants_logic.py` and having that module import `_MISSING_TOKEN` back from `survey.py` would cycle (`survey.py` already imports *from* `survey_participants_logic.py`). This repo already has an established fix for exactly this shape of problem: `survey_core.py::_inject_missing_token(sidecar, *, token: str)` takes the token as a parameter instead of importing the constant. Do the same here — add `missing_token: str` as a parameter to `_write_survey_participants` (and internally to whatever uses `_MISSING_TOKEN`), and update the one call site (`ParticipantsConverter.write_participants` in `survey.py`, which also needs the same new parameter added to its own signature) to pass `missing_token=_MISSING_TOKEN` through. Confirmed via grep: `ParticipantsConverter.write_participants` has exactly one caller in the entire repo (the orchestrator itself), so this interface change is fully contained within files this plan already touches.

- [ ] **Step 1: Confirm the regression baseline is green**

Run the regression command from Global Constraints, note the pass count.

- [ ] **Step 2: Move the function chain to `survey_participants_logic.py`**

Cut these from `survey.py`, verbatim except for the `missing_token` change noted below, in this order (locate each by name):

- `_find_matching_level_key` — uses `_sanitize_answer_code_for_ls`; check via grep whether `survey.py`'s `_sanitize_answer_code_for_ls = _survey_processing._sanitize_answer_code_for_ls` module-level alias is used anywhere else in `survey.py` outside this function before deciding whether to keep that alias or have this function call `_survey_processing._sanitize_answer_code_for_ls` directly once moved (check whether `survey_participants_logic.py` already does `from . import survey_processing as _survey_processing` or needs it added).
- `_safe_eval_formula` — self-contained, no external dependencies beyond stdlib `ast`/`operator` (already imported locally inside the function).
- `_auto_correct_participant_value` — replace its one reference to the bare `_MISSING_TOKEN` (in the "Skip empty/missing values" branch, `return _MISSING_TOKEN`) with a new `missing_token: str` parameter, added to its signature: `def _auto_correct_participant_value(value, col_name: str, template: dict | None, missing_token: str) -> str:`.
- `_write_survey_participants` — add `missing_token: str` to its keyword-only parameter list (after `is_missing_fn`, before `lsa_col_renames`). Replace its two internal uses of the bare `_MISSING_TOKEN` (in the value-mapping `.map(...)` lambda, and in the `is_missing_fn` branch) with `missing_token`. Update its one call to `_auto_correct_participant_value(...)` to pass `missing_token=missing_token` through.

`_load_participants_mapping`, `_get_mapped_columns`, `_normalize_participant_template_dict`, `_participants_json_from_template` are already defined in `survey_participants_logic.py` itself (confirmed — `survey.py` currently imports all four *from* that module) — once `_write_survey_participants` lives there too, its calls to these four resolve locally; no import changes needed for them.

Add to `survey_participants_logic.py`'s import block (check which aren't already present before adding):

```python
from ..utils.io import write_json as _write_json
```

(pandas: `survey_participants_logic.py` doesn't import it at module level yet — `_write_survey_participants` currently does a local `import pandas as pd` at its own top; keep that local import, it's the file's first use of pandas and matches how `survey_core.py`/other siblings guard against pandas being unavailable at import time — check whether a bare `import pandas as pd` or the `try/except ImportError: pd = None` guarded form is more consistent with this specific file's existing style before choosing.)

- [ ] **Step 3: Update `survey.py`**

Remove the four moved definitions. Add `from . import survey_participants_logic as _survey_participants_logic` if not already present as a qualified import (check — `survey.py` already imports several *names* from this module directly; confirm whether it also already has the qualified-module form, and add it if not).

Update `ParticipantsConverter.write_participants`'s signature to add `missing_token: str,` (keyword-only, after `is_missing_fn`, before `lsa_col_renames`), and update its body's call to `_write_survey_participants(...)` — now `_survey_participants_logic._write_survey_participants(...)` — to pass `missing_token=missing_token` through alongside its existing arguments.

- [ ] **Step 4: Update the orchestrator's call site**

`participants_converter.write_participants(...)` (inside the "Write Output" section, `if not skip_participants:` branch) needs one new line added to its call: `missing_token=_MISSING_TOKEN,`. `_MISSING_TOKEN` is still a `survey.py`-local constant (unmoved) — this is its value being passed down, not an import change.

- [ ] **Step 5: Verify the module resolves live (drift check)**

Run: `python3 -c "import src.converters.survey_participants_logic as m; print(m.__file__)"`
Expected: prints a path ending in `app/src/converters/survey_participants_logic.py`.

- [ ] **Step 6: Run the regression command from Global Constraints**

Confirm the pass count matches Step 1's baseline.

- [ ] **Step 7: Commit**

```bash
git add app/src/converters/survey_participants_logic.py app/src/converters/survey.py
git commit -m "refactor: move _write_survey_participants into survey_participants_logic.py"
```

---

### Task 9: TDD — extract `_determine_participant_output_columns` from `_write_survey_participants`

**Files:**
- Modify: `app/src/converters/survey_participants_logic.py`
- Test: `tests/test_survey_participant_output.py` (new)

**Interfaces:**
- Produces: `ParticipantColumnPlan` (dataclass: `extra_cols: list[str]`, `col_output_names: dict[str, str]`, `mapping_descriptions: dict[str, str]`, `value_mappings: dict`, `template_norm: dict | None`) and `_determine_participant_output_columns(*, df, output_root: Path, id_col: str, ses_col: str | None, participant_template: dict | None, lsa_col_renames: dict[str, str] | None) -> ParticipantColumnPlan`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_survey_participant_output.py`:

```python
import pandas as pd

from src.converters.survey_participants_logic import _determine_participant_output_columns


def test_no_mapping_file_uses_only_template_columns(tmp_path):
    df = pd.DataFrame({"id": ["001"], "age": ["25"], "unrelated_col": ["x"]})

    plan = _determine_participant_output_columns(
        df=df,
        output_root=tmp_path,
        id_col="id",
        ses_col=None,
        participant_template={"age": {"Description": "Age"}},
        lsa_col_renames=None,
    )

    assert plan.extra_cols == ["age"]
    assert "unrelated_col" not in plan.extra_cols


def test_mapping_file_restricts_to_explicitly_mapped_columns(tmp_path):
    (tmp_path / "participants_mapping.json").write_text(
        """
        {
          "mappings": {
            "sociodem_income": {
              "source_column": "income",
              "standard_variable": "sociodem_income"
            }
          }
        }
        """
    )
    df = pd.DataFrame({"id": ["001"], "income": ["high"], "age": ["25"]})

    plan = _determine_participant_output_columns(
        df=df,
        output_root=tmp_path,
        id_col="id",
        ses_col=None,
        participant_template={"age": {"Description": "Age"}},
        lsa_col_renames=None,
    )

    assert plan.extra_cols == ["income"]
    assert "age" not in plan.extra_cols


def test_id_and_session_columns_are_never_included_as_extra_cols(tmp_path):
    df = pd.DataFrame({"id": ["001"], "ses": ["1"], "age": ["25"]})

    plan = _determine_participant_output_columns(
        df=df,
        output_root=tmp_path,
        id_col="id",
        ses_col="ses",
        participant_template={"id": {}, "ses": {}, "age": {"Description": "Age"}},
        lsa_col_renames=None,
    )

    assert "id" not in plan.extra_cols
    assert "ses" not in plan.extra_cols


def test_lsa_col_renames_fallback_finds_mangled_column_name(tmp_path):
    # No mapping file, template expects "age" but the LSA-mangled source
    # column is "AGEQ1" -- lsa_col_renames says AGEQ1 -> age.
    df = pd.DataFrame({"id": ["001"], "AGEQ1": ["25"]})

    plan = _determine_participant_output_columns(
        df=df,
        output_root=tmp_path,
        id_col="id",
        ses_col=None,
        participant_template={"age": {"Description": "Age"}},
        lsa_col_renames={"AGEQ1": "age"},
    )

    assert plan.extra_cols == ["AGEQ1"]
    assert plan.col_output_names["AGEQ1"] == "age"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_survey_participant_output.py -v`
Expected: FAIL with `ImportError: cannot import name '_determine_participant_output_columns'`.

- [ ] **Step 3: Implement `_determine_participant_output_columns`**

Add to `survey_participants_logic.py`:

```python
@dataclass
class ParticipantColumnPlan:
    extra_cols: list
    col_output_names: dict
    mapping_descriptions: dict
    value_mappings: dict
    template_norm: dict | None


def _determine_participant_output_columns(
    *,
    df,
    output_root: Path,
    id_col: str,
    ses_col: str | None,
    participant_template: dict | None,
    lsa_col_renames: dict | None,
) -> ParticipantColumnPlan:
    """Decide which source columns go into participants.tsv and under what
    output name.

    Mode 1 (participants_mapping.json exists): only explicitly mapped
    columns, renamed per the mapping.
    Mode 2 (no mapping): only columns present in the official participant
    template, with an LSA-mangled-name fallback lookup.
    """
    lower_to_col = {str(c).strip().lower(): str(c).strip() for c in df.columns}

    participants_mapping = _load_participants_mapping(output_root)
    mapped_cols, col_renames, value_mappings = _get_mapped_columns(participants_mapping)

    if participants_mapping:
        print(
            f"[INFO] Using participants_mapping.json from project ({len(mapped_cols)} mapped columns)"
        )
        if col_renames:
            print(f"[INFO]   Column renames: {col_renames}")
        if value_mappings:
            print(f"[INFO]   Value transformations for: {list(value_mappings.keys())}")
    else:
        print("[INFO] No participants_mapping.json found (using template columns only)")

    template_norm = _normalize_participant_template_dict(participant_template)
    template_cols = set(template_norm.keys()) if template_norm else set()
    non_column_keys = {
        "@context",
        "Technical",
        "I18n",
        "Study",
        "Metadata",
        "_aliases",
        "_reverse_aliases",
    }
    template_cols = template_cols - non_column_keys

    extra_cols: list = []
    col_output_names: dict = {}
    mapping_descriptions: dict = {}

    if participants_mapping and mapped_cols:
        for source_col_lower in mapped_cols:
            if source_col_lower in lower_to_col:
                actual_col = lower_to_col[source_col_lower]
                if actual_col not in {id_col, ses_col}:
                    extra_cols.append(actual_col)
                    output_name = col_renames.get(source_col_lower, source_col_lower)
                    col_output_names[actual_col] = output_name

        for var_name, spec in participants_mapping.get("mappings", {}).items():
            if isinstance(spec, dict):
                standard_var = spec.get("standard_variable", var_name)
                if standard_var not in template_cols and "description" in spec:
                    mapping_descriptions[standard_var] = spec["description"]
    else:
        for col in template_cols:
            if col in lower_to_col:
                actual_col = lower_to_col[col]
                if actual_col not in {id_col, ses_col}:
                    extra_cols.append(actual_col)
                    col_output_names[actual_col] = col
            elif lsa_col_renames:
                mangled = None
                for mangled_name, standard_name in lsa_col_renames.items():
                    if standard_name == col:
                        mangled = mangled_name
                        break
                if mangled and mangled in lower_to_col:
                    actual_col = lower_to_col[mangled]
                    if actual_col not in {id_col, ses_col}:
                        extra_cols.append(actual_col)
                        col_output_names[actual_col] = col

    return ParticipantColumnPlan(
        extra_cols=extra_cols,
        col_output_names=col_output_names,
        mapping_descriptions=mapping_descriptions,
        value_mappings=value_mappings,
        template_norm=template_norm,
    )
```

Note: `dataclass` should already be imported at the top of `survey_participants_logic.py` (confirmed via the file's existing imports). `_load_participants_mapping`, `_get_mapped_columns`, `_normalize_participant_template_dict` are already defined in this same file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_survey_participant_output.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Wire into `_write_survey_participants`**

Replace the block from `lower_to_col = {str(c)...}` (the very first executable line, right after the `import pandas as pd`) through the end of the column-determination `if/else` (locate by content — ends right before `df_part = pd.DataFrame({"participant_id": ...})`) with:

```python
    column_plan = _determine_participant_output_columns(
        df=df,
        output_root=output_root,
        id_col=id_col,
        ses_col=ses_col,
        participant_template=participant_template,
        lsa_col_renames=lsa_col_renames,
    )
    extra_cols = column_plan.extra_cols
    col_output_names = column_plan.col_output_names
    mapping_descriptions = column_plan.mapping_descriptions
    value_mappings = column_plan.value_mappings
    template_norm = column_plan.template_norm
```

The five destructuring lines are deliberate and temporary: they let everything below (the still-inline `df_part = pd.DataFrame(...)` construction and the `if extra_cols:` block) keep working completely unchanged for this task, using the same local names it always has. Task 10 removes these five lines again when it replaces that whole downstream block with a call to `_build_participant_output_dataframe(..., column_plan=column_plan)` — don't be surprised that they're short-lived, that's by design so this task's own regression run is meaningful on its own.

- [ ] **Step 6: Run the regression command from Global Constraints**

`_write_survey_participants` is fully functional after this step (unlike a naive version of this task that would leave it broken until Task 10) — this run must pass at the same count as every other task's.

- [ ] **Step 7: Commit**

```bash
git add app/src/converters/survey_participants_logic.py tests/test_survey_participant_output.py
git commit -m "refactor: extract _determine_participant_output_columns from _write_survey_participants"
```

---

### Task 10: TDD — extract `_build_participant_output_dataframe` from `_write_survey_participants`

**Files:**
- Modify: `app/src/converters/survey_participants_logic.py`
- Modify: `tests/test_survey_participant_output.py`

**Interfaces:**
- Consumes: `ParticipantColumnPlan` from Task 9.
- Produces: `_build_participant_output_dataframe(*, df, id_col: str, normalize_sub_fn, is_missing_fn, missing_token: str, column_plan: ParticipantColumnPlan)` — returns a pandas DataFrame (deduplicated by `participant_id`, not yet merged with any existing `participants.tsv`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_survey_participant_output.py`:

```python
from src.converters.survey_participants_logic import (
    ParticipantColumnPlan,
    _build_participant_output_dataframe,
)


def _identity_normalize_sub(val):
    return f"sub-{val}"


def _never_missing(val):
    return False


def test_builds_participant_id_column_from_normalized_id():
    df = pd.DataFrame({"id": ["001", "002"]})
    column_plan = ParticipantColumnPlan(
        extra_cols=[], col_output_names={}, mapping_descriptions={},
        value_mappings={}, template_norm=None,
    )

    result = _build_participant_output_dataframe(
        df=df, id_col="id", normalize_sub_fn=_identity_normalize_sub,
        is_missing_fn=_never_missing, missing_token="n/a", column_plan=column_plan,
    )

    assert list(result["participant_id"]) == ["sub-001", "sub-002"]


def test_extra_columns_are_included_and_renamed():
    df = pd.DataFrame({"id": ["001"], "income": ["high"]})
    column_plan = ParticipantColumnPlan(
        extra_cols=["income"], col_output_names={"income": "sociodem_income"},
        mapping_descriptions={}, value_mappings={}, template_norm=None,
    )

    result = _build_participant_output_dataframe(
        df=df, id_col="id", normalize_sub_fn=_identity_normalize_sub,
        is_missing_fn=_never_missing, missing_token="n/a", column_plan=column_plan,
    )

    assert list(result["sociodem_income"]) == ["high"]


def test_missing_values_become_the_missing_token():
    df = pd.DataFrame({"id": ["001"], "income": [""]})
    column_plan = ParticipantColumnPlan(
        extra_cols=["income"], col_output_names={"income": "income"},
        mapping_descriptions={}, value_mappings={}, template_norm=None,
    )

    result = _build_participant_output_dataframe(
        df=df, id_col="id", normalize_sub_fn=_identity_normalize_sub,
        is_missing_fn=lambda v: v == "", missing_token="n/a", column_plan=column_plan,
    )

    assert list(result["income"]) == ["n/a"]


def test_value_mapping_transforms_values():
    df = pd.DataFrame({"id": ["001"], "sex": ["1"]})
    column_plan = ParticipantColumnPlan(
        extra_cols=["sex"], col_output_names={"sex": "sex"},
        mapping_descriptions={}, value_mappings={"sex": {"1": "male", "2": "female"}},
        template_norm=None,
    )

    result = _build_participant_output_dataframe(
        df=df, id_col="id", normalize_sub_fn=_identity_normalize_sub,
        is_missing_fn=_never_missing, missing_token="n/a", column_plan=column_plan,
    )

    assert list(result["sex"]) == ["male"]


def test_duplicate_participant_ids_are_deduplicated():
    df = pd.DataFrame({"id": ["001", "001"], "income": ["high", "low"]})
    column_plan = ParticipantColumnPlan(
        extra_cols=["income"], col_output_names={"income": "income"},
        mapping_descriptions={}, value_mappings={}, template_norm=None,
    )

    result = _build_participant_output_dataframe(
        df=df, id_col="id", normalize_sub_fn=_identity_normalize_sub,
        is_missing_fn=_never_missing, missing_token="n/a", column_plan=column_plan,
    )

    assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_survey_participant_output.py -v -k build_participant_output_dataframe`
Expected: FAIL with `ImportError: cannot import name '_build_participant_output_dataframe'`.

- [ ] **Step 3: Implement `_build_participant_output_dataframe`**

Add to `survey_participants_logic.py`:

```python
def _build_participant_output_dataframe(
    *,
    df,
    id_col: str,
    normalize_sub_fn,
    is_missing_fn,
    missing_token: str,
    column_plan: ParticipantColumnPlan,
):
    """Build the deduplicated participants dataframe: participant_id plus
    the extra columns column_plan selected, with value mappings, missing-value
    substitution, and template-based auto-correction applied."""
    import pandas as pd

    df_part = pd.DataFrame(
        {"participant_id": df[id_col].astype(str).map(normalize_sub_fn)}
    )

    extra_cols = column_plan.extra_cols
    if extra_cols:
        extra_cols = list(dict.fromkeys(extra_cols))
        df_extra = df[[id_col] + extra_cols].copy()

        for c in extra_cols:
            output_name = column_plan.col_output_names.get(c, c)

            if output_name in column_plan.value_mappings:
                val_map = column_plan.value_mappings[output_name]
                df_extra[c] = (
                    df_extra[c]
                    .astype(str)
                    .map(
                        lambda v, vm=val_map: (
                            vm.get(v, v)
                            if v not in ("nan", "None", "")
                            else missing_token
                        )
                    )
                )
            else:
                df_extra[c] = df_extra[c].apply(
                    lambda v: missing_token if is_missing_fn(v) else v
                )

        df_extra[id_col] = df_extra[id_col].astype(str).map(normalize_sub_fn)
        df_extra = df_extra.rename(columns={id_col: "participant_id"})
        df_extra = (
            df_extra.groupby("participant_id", dropna=False)[extra_cols]
            .first()
            .reset_index()
        )

        rename_map = {c: column_plan.col_output_names.get(c, c) for c in extra_cols}
        df_extra = df_extra.rename(columns=rename_map)

        if column_plan.template_norm:
            for col in df_extra.columns:
                if col == "participant_id":
                    continue
                df_extra[col] = df_extra[col].apply(
                    lambda v, c=col, t=column_plan.template_norm: (
                        _auto_correct_participant_value(v, c, t, missing_token=missing_token)
                    )
                )

        df_part = df_part.merge(df_extra, on="participant_id", how="left")

    df_part = df_part.drop_duplicates(subset=["participant_id"]).reset_index(drop=True)
    return df_part
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_survey_participant_output.py -v`
Expected: PASS (9 tests total in this file).

- [ ] **Step 5: Wire into `_write_survey_participants`, completing its shrink**

`_write_survey_participants` should now read (replacing everything from the top of its body through the `df_part = df_part.drop_duplicates(...)` line, i.e. everything Task 9 and this task cover together):

```python
def _write_survey_participants(
    *,
    df,
    output_root: Path,
    id_col: str,
    ses_col: str | None,
    participant_template: dict | None,
    normalize_sub_fn,
    is_missing_fn,
    missing_token: str,
    lsa_col_renames: dict | None = None,
):
    """Write participants.tsv and participants.json.

    Column inclusion logic:
    1. If participants_mapping.json exists in project:
       - Only include columns explicitly defined in the mapping
       - Apply value transformations as specified
       - Rename columns to standard variable names
    2. If no mapping exists:
       - Only include columns that exist in the official participants template
       - No arbitrary extra columns from source data

    All columns in the output must have documentation in participants.json.
    """
    column_plan = _determine_participant_output_columns(
        df=df,
        output_root=output_root,
        id_col=id_col,
        ses_col=ses_col,
        participant_template=participant_template,
        lsa_col_renames=lsa_col_renames,
    )
    df_part = _build_participant_output_dataframe(
        df=df,
        id_col=id_col,
        normalize_sub_fn=normalize_sub_fn,
        is_missing_fn=is_missing_fn,
        missing_token=missing_token,
        column_plan=column_plan,
    )

    # Merge with existing participants.tsv if it exists (Task 11 extracts this)
    participants_tsv_path = output_root / "participants.tsv"
    if participants_tsv_path.exists():
        try:
            existing_df = pd.read_csv(participants_tsv_path, sep="\t", dtype=str)
            # ... unchanged, still inline until Task 11 ...
        except Exception as e:
            print(f"[WARNING] Could not merge with existing participants.tsv: {e}")

    df_part.to_csv(participants_tsv_path, sep="\t", index=False)

    parts_json_path = output_root / "participants.json"
    p_json = _participants_json_from_template(
        columns=[str(c) for c in df_part.columns],
        template=participant_template,
        extra_descriptions=column_plan.mapping_descriptions,
    )
    _write_json(parts_json_path, p_json)
```

(The `# ... unchanged, still inline until Task 11 ...` marker above is not real code — it stands for the existing merge-with-existing-file block, which stays exactly as it was in the original function; Task 11 extracts it next. Leave it untouched in this step.) Also update `_auto_correct_participant_value`'s and `_find_matching_level_key`'s remaining `_MISSING_TOKEN` references if any were missed in Task 8 — grep to confirm zero bare `_MISSING_TOKEN` references remain anywhere in `survey_participants_logic.py` after this step.

- [ ] **Step 6: Run the regression command from Global Constraints**

Confirm the pass count matches Task 9's baseline — this step also removes Task 9's five temporary destructuring lines, so this is the point where you're confirming that removal didn't change behavior, not recovering from a broken state.

- [ ] **Step 7: Commit**

```bash
git add app/src/converters/survey_participants_logic.py tests/test_survey_participant_output.py
git commit -m "refactor: extract _build_participant_output_dataframe from _write_survey_participants"
```

---

### Task 11: TDD — extract `_merge_with_existing_participants_tsv` from `_write_survey_participants`

**Files:**
- Modify: `app/src/converters/survey_participants_logic.py`
- Modify: `tests/test_survey_participant_output.py`

**Interfaces:**
- Produces: `_merge_with_existing_participants_tsv(*, df_part, participants_tsv_path: Path)` — returns a pandas DataFrame (the merged result, or `df_part` unchanged if no existing file, or if the existing file has no `participant_id` column, or if the merge raises).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_survey_participant_output.py`:

```python
from src.converters.survey_participants_logic import _merge_with_existing_participants_tsv


def test_no_existing_file_returns_df_part_unchanged(tmp_path):
    df_part = pd.DataFrame({"participant_id": ["sub-001"], "age": ["25"]})
    result = _merge_with_existing_participants_tsv(
        df_part=df_part, participants_tsv_path=tmp_path / "participants.tsv"
    )
    assert result.equals(df_part)


def test_new_values_preferred_over_existing_for_overlapping_participant(tmp_path):
    tsv_path = tmp_path / "participants.tsv"
    tsv_path.write_text("participant_id\tage\nsub-001\t25\n")
    df_part = pd.DataFrame({"participant_id": ["sub-001"], "age": ["26"]})

    result = _merge_with_existing_participants_tsv(
        df_part=df_part, participants_tsv_path=tsv_path
    )

    row = result[result["participant_id"] == "sub-001"].iloc[0]
    assert row["age"] == "26"


def test_existing_participants_not_in_new_data_are_kept(tmp_path):
    tsv_path = tmp_path / "participants.tsv"
    tsv_path.write_text("participant_id\tage\nsub-999\t40\n")
    df_part = pd.DataFrame({"participant_id": ["sub-001"], "age": ["25"]})

    result = _merge_with_existing_participants_tsv(
        df_part=df_part, participants_tsv_path=tsv_path
    )

    assert "sub-999" in list(result["participant_id"])
    assert "sub-001" in list(result["participant_id"])


def test_existing_file_without_participant_id_column_is_left_unmerged(tmp_path):
    tsv_path = tmp_path / "participants.tsv"
    tsv_path.write_text("subject\tage\nsub-001\t25\n")
    df_part = pd.DataFrame({"participant_id": ["sub-002"], "age": ["30"]})

    result = _merge_with_existing_participants_tsv(
        df_part=df_part, participants_tsv_path=tsv_path
    )

    assert result.equals(df_part)


def test_unreadable_existing_file_falls_back_to_df_part(tmp_path, capsys):
    tsv_path = tmp_path / "participants.tsv"
    tsv_path.write_text("not\ta valid\ttsv\nwith\x00null\tbytes\n")
    # A file with an embedded null byte reliably fails pandas' C parser.
    df_part = pd.DataFrame({"participant_id": ["sub-001"], "age": ["25"]})

    result = _merge_with_existing_participants_tsv(
        df_part=df_part, participants_tsv_path=tsv_path
    )

    assert result.equals(df_part)
    assert "Could not merge" in capsys.readouterr().out
```

Note: if the null-byte fixture in the last test doesn't actually make `pd.read_csv` raise on this pandas version, replace it with any input you've confirmed does raise (e.g. a genuinely malformed/binary file) — the point of the test is exercising the `except Exception` fallback path, not the specific corruption technique.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_survey_participant_output.py -v -k merge_with_existing`
Expected: FAIL with `ImportError: cannot import name '_merge_with_existing_participants_tsv'`.

- [ ] **Step 3: Implement `_merge_with_existing_participants_tsv`**

Add to `survey_participants_logic.py`:

```python
def _merge_with_existing_participants_tsv(*, df_part, participants_tsv_path: Path):
    """Merge df_part with an existing participants.tsv on disk, if present.
    New values win for overlapping participants/columns; falls back to the
    old value if the new one is missing. Returns df_part unchanged if there's
    no existing file, it has no participant_id column, or the merge fails."""
    import pandas as pd

    if not participants_tsv_path.exists():
        return df_part

    try:
        existing_df = pd.read_csv(participants_tsv_path, sep="\t", dtype=str)
        if "participant_id" not in existing_df.columns:
            return df_part

        merged = pd.merge(
            existing_df,
            df_part,
            on="participant_id",
            how="outer",
            suffixes=("_old", "_new"),
        )

        for col in merged.columns:
            if col.endswith("_new"):
                base_col = col[:-4]
                old_col = base_col + "_old"
                if old_col in merged.columns:
                    merged[base_col] = merged.apply(
                        lambda row: (
                            row[col]
                            if pd.notna(row[col])
                            and str(row[col]) not in ("n/a", "nan", "")
                            else (
                                row[old_col] if pd.notna(row[old_col]) else "n/a"
                            )
                        ),
                        axis=1,
                    )
                    merged = merged.drop(columns=[old_col, col])
                else:
                    merged = merged.rename(columns={col: base_col})

        merged = merged.sort_values("participant_id").reset_index(drop=True)
        print(
            f"[INFO] Merged with existing participants.tsv ({len(existing_df)} existing → {len(merged)} total)"
        )
        return merged
    except Exception as e:
        print(f"[WARNING] Could not merge with existing participants.tsv: {e}")
        return df_part
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_survey_participant_output.py -v`
Expected: PASS (14 tests total in this file).

- [ ] **Step 5: Wire into `_write_survey_participants`, finishing its shrink to an orchestrator**

Replace the `# Merge with existing participants.tsv if it exists` block (the `if participants_tsv_path.exists(): try: ... except Exception as e: ...` block, locate by content) with:

```python
    df_part = _merge_with_existing_participants_tsv(
        df_part=df_part, participants_tsv_path=participants_tsv_path
    )
```

`_write_survey_participants` should now be roughly 25-35 lines: docstring, call `_determine_participant_output_columns`, call `_build_participant_output_dataframe`, call `_merge_with_existing_participants_tsv`, write the TSV, build and write the JSON sidecar.

- [ ] **Step 6: Run the regression command from Global Constraints**

- [ ] **Step 7: Commit**

```bash
git add app/src/converters/survey_participants_logic.py tests/test_survey_participant_output.py
git commit -m "refactor: extract _merge_with_existing_participants_tsv from _write_survey_participants"
```

---

### Task 12: Final verification and cleanup pass

**Files:**
- Modify (formatting only, if needed): all files touched above.

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -q 2>&1 | tail -60`
Expected: no failures beyond whatever set is already pre-existing/unrelated on `main` at the time this plan is executed — confirm by running the same failing tests directly against `main` (not this branch) before treating any failure as acceptable, the same way this was verified for the companion participants-blueprint plan. Do not assume; check.

- [ ] **Step 2: Re-run every drift check**

```bash
python3 -c "import src.converters.survey as m; print(m.__file__)"
python3 -c "import src.converters.survey_core as m; print(m.__file__)"
python3 -c "import src.converters.survey_lsa as m; print(m.__file__)"
python3 -c "import src.converters.survey_column_mapping as m; print(m.__file__)"
python3 -c "import src.converters.survey_participants_logic as m; print(m.__file__)"
```

Expected: the first four print a path under `app/src/converters/` (matching the confirmed symlink/live-module status established during planning); `survey_participants_logic` likewise.

- [ ] **Step 3: Confirm the size changes**

Run: `wc -l app/src/converters/survey.py app/src/converters/survey_core.py app/src/converters/survey_lsa.py app/src/converters/survey_column_mapping.py app/src/converters/survey_participants_logic.py`

Expected: `survey.py` down substantially from 3,800 lines (the three functions together were ~1,264 lines; expect the file to land somewhere in the 2,700-2,900 range once the new thin orchestrator bodies and the moved-out code are both accounted for — a modest net line-count change is normal and was observed in the companion participants-blueprint plan too, from added per-file import overhead; the goal is no single function still being oversized, not an exact target line count). Confirm no oversized function remains: `awk '/^def |^class /{if(name!=""){print NR-start, name} name=$0; start=NR} END{print NR-start, name}' app/src/converters/survey.py | sort -rn | head -5` should show nothing close to the original 668/371/225-line figures.

- [ ] **Step 4: Format and lint**

Check whether `black`/`flake8` are available in the project's `.venv` first (`.venv/bin/black --version`, `.venv/bin/flake8 --version`); if not, check for a global `ruff` binary on `PATH` (`which ruff`) — this repo's companion plan found one at `/opt/homebrew/bin/ruff` when the venv-local tools were missing, and it was already in use by prior tasks' own self-checks in this session. Whichever tool is available, run its check/format on every file this plan touched:

```bash
ruff check app/src/converters/survey.py app/src/converters/survey_core.py app/src/converters/survey_lsa.py app/src/converters/survey_column_mapping.py app/src/converters/survey_participants_logic.py tests/test_survey_id_normalizers.py tests/test_survey_alias_template_loading.py tests/test_survey_lsa_structural_matching.py tests/test_survey_column_mapping.py tests/test_survey_participant_output.py
ruff format --check app/src/converters/survey.py app/src/converters/survey_core.py app/src/converters/survey_lsa.py app/src/converters/survey_column_mapping.py app/src/converters/survey_participants_logic.py tests/test_survey_id_normalizers.py tests/test_survey_alias_template_loading.py tests/test_survey_lsa_structural_matching.py tests/test_survey_column_mapping.py tests/test_survey_participant_output.py
```

If either reports findings: apply `ruff format` for pure formatting diffs (verify each resulting diff is whitespace/line-wrapping only, the same way the companion plan verified this before committing). For `ruff check` findings, do NOT delete anything that looks unused without grepping for it first — this plan's own design notes above already worked out several deliberate cross-module references (dependency-injected callables, the `_MISSING_TOKEN`-as-parameter change) that a naive unused-import scan could misread; if you hit one of those exact names, re-read this task's own notes before "fixing" it.

- [ ] **Step 5: Commit any formatting fixes**

```bash
git add -u
git commit -m "style: ruff format pass on the split survey.py files"
```

(Skip this step if `ruff format`/`black` made no changes.)
