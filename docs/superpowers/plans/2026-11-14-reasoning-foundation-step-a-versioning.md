# Reasoning foundation, step A: an older minor schema version stops warning

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A file that declares an older minor version of a schema than the validator's, with the same major version, no longer produces PRISM005; the version parser no longer crashes on a two-part or odd version.

**Architecture:** One function decides compatibility (`is_compatible_version` in `app/src/schema_manager.py`), used by the validator and the runner through `validate_schema_version`. The rule becomes "same major version"; `parse_version` always returns three integers. Nothing else changes: pins, the 0.0.1 defect of the validation matrix, and newer-major files keep warning.

**Tech Stack:** Python 3, pytest. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-14-reasoning-foundation-design.md` (section 5 "Versioning rule"; decision "an older minor version stops warning", 2026-11-14). Steps B to G are separate plans (outline at the end).

## Global Constraints

- TDD: a failing test first, watched failing for the expected reason.
- "Within a major version a schema only adds optional things. The validator no longer warns when a file declares an older minor version of a schema with the same major version. A different major version still warns."
- Project, sidecar and library files are untrusted data: "wrong types are reported, never a crash."
- THE RULE (CLAUDE.md): the logic stays once in `app/src/schema_manager.py`; the CLI and Studio already reach it through the validator, no Studio code changes.
- Dual-tree check (CLAUDE.md): `schema_manager.py` is imported as `src.schema_manager` and as bare `schema_manager` (runner); confirm with `find src -name schema_manager.py` and `python -c "import src.schema_manager as m; print(m.__file__)"` which file is live before editing.
- A file that declares a *newer* minor than the validator's keeps passing silently (unchanged behaviour).

## Review Focus

1. Older minor, same major (file `2.0.0`, schema `2.1.0`): no PRISM005 (Task 1, Task 2).
2. Older or newer **major**, and the matrix defect `0.0.1`: still PRISM005 (Task 1, Task 2).
3. A version that is `"2.1"` (two parts), `"abc"`, empty, a number or a list (project data): no exception; unparseable ones still warn (Task 1).
4. A project pinned to an older schema version (validated against the archived schema, schema version = the pinned one): no warning when file and schema agree (Task 1).
5. The official library templates keep validating, and no test forces a rewrite of 103 files at the next minor release (Task 2).

## File Structure

- Modify `app/src/schema_manager.py`: `parse_version`, `is_compatible_version`, the message in `validate_schema_version`.
- Modify `app/src/issues.py`: the `PRISM005` fix hint (wording only).
- Modify `docs/ERROR_CODES.md`: the `PRISM005` row.
- Modify `tests/test_official_survey_library_valid.py`: the library version test (same major, not the exact version).
- Create `tests/test_schema_version_compat.py`: the rule, end to end.

---

### Task 1: The rule and a parser that cannot crash

**Files:**
- Modify: `app/src/schema_manager.py:38-60` (`parse_version`, `is_compatible_version`) and the message at `:185-192`
- Modify: `app/src/issues.py:114-117` (hint wording)
- Test: `tests/test_schema_version_compat.py` (new)

**Interfaces:**
- Produces: `parse_version(version_string) -> tuple[int, int, int]` (always three integers; anything that is not a string of dotted integers gives `(0, 0, 0)`; fewer than three parts are padded with 0, more than three are cut to three); `is_compatible_version(required_version, provided_version) -> bool` (true when the major versions are equal and the provided version parsed); `validate_schema_version(metadata, schema) -> list[tuple[str, str]]` unchanged signature.
- Consumed by: `app/src/validator.py:1452`, `app/src/runner.py:317`, `src/modality_versions.py` (`parse_version` ordering of versions: a three-tuple compares as before).

- [ ] **Step 1: Write the failing tests** in `tests/test_schema_version_compat.py`. Import with the same path trick other tests use (`sys.path` insert of the repo root, then `from src.schema_manager import ...`; read how `tests/test_modality_version_pins.py` does it and copy it). Tests:

```python
import pytest
from src.schema_manager import is_compatible_version, parse_version, validate_schema_version

SCHEMA = {"_validator_info": {"schema_version": "2.1.0"}}

def _issues(meta_version):
    return validate_schema_version({"Metadata": {"SchemaVersion": meta_version}}, SCHEMA)

@pytest.mark.parametrize("provided", ["2.0.0", "2.0.9", "2.1.0", "2.1.5", "2.7.0"])
def test_same_major_never_warns(provided):
    assert _issues(provided) == []

@pytest.mark.parametrize("provided", ["1.9.9", "3.0.0", "0.0.1"])
def test_other_major_still_warns(provided):
    (level, message), = _issues(provided)
    assert level == "WARNING" and "mismatch" in message.lower() and provided in message

@pytest.mark.parametrize("provided", ["2.1", "2", "abc", "", "v2.0.0", 5, ["2.0.0"], None])
def test_odd_versions_never_raise(provided):
    _issues(provided)                      # must not raise
    assert isinstance(is_compatible_version("2.1.0", provided), bool)

def test_two_part_version_is_read_as_major_minor_zero():
    assert parse_version("2.1") == (2, 1, 0) and parse_version("2.1.4.9") == (2, 1, 4)
    assert is_compatible_version("2.1.0", "2.0") is True

def test_unparseable_versions_warn():
    for bad in ("abc", "v2.0.0", 5):
        assert _issues(bad) != []          # (0,0,0) is another major

def test_a_pinned_older_schema_matches_its_own_files():
    pinned = {"_validator_info": {"schema_version": "2.0.0"}}
    assert validate_schema_version({"Metadata": {"SchemaVersion": "2.0.0"}}, pinned) == []

def test_no_version_declared_is_no_issue():
    assert validate_schema_version({"Metadata": {}}, SCHEMA) == []
```

- [ ] **Step 2: Run to verify it fails.** Run: `.venv/bin/python -m pytest tests/test_schema_version_compat.py -q -p no:cacheprovider`. Expected: `test_same_major_never_warns[2.0.0]` and `[2.0.9]` FAIL (an issue is returned), `test_odd_versions_never_raise[2.1]`/`[2]` FAIL with `ValueError: not enough values to unpack`, `test_two_part_version...` FAIL; the "other major" and "no version" tests already pass.
- [ ] **Step 3: Implement** in `app/src/schema_manager.py`: `parse_version` pads/cuts to three integers and returns `(0, 0, 0)` for non-strings and anything with a non-integer part; `is_compatible_version` compares the major only (keep the docstring honest: "same major version; minor and patch may differ"). In `validate_schema_version` change the message tail to "Consider upgrading metadata." only when the provided major differs (it is the only case that can reach it now); keep the text "Schema version mismatch" (the code mapping in `app/src/issues.py:507` matches on it). Update the `PRISM005` fix hint in `app/src/issues.py` to say the metadata uses a different **major** schema version than the validator.
- [ ] **Step 4: Run to verify it passes.** Run: `.venv/bin/python -m pytest tests/test_schema_version_compat.py tests/test_modality_version_pins.py tests/test_validation_matrix.py -q -p no:cacheprovider`. Expected: PASS (the matrix still detects its `0.0.1` defect).
- [ ] **Step 5: Commit** `fix(validator): an older minor schema version no longer warns (same major); parse_version never crashes`.

### Task 2: End to end, and the library test follows the rule

**Files:**
- Modify: `tests/test_official_survey_library_valid.py:29-38` (the test added with the 2.1.0 release)
- Modify: `tests/test_schema_version_compat.py` (one integration test)

**Interfaces:**
- Consumes: `src.validation_matrix`: `Defect`, `NONE`, `SIDECAR`, `_json`, `build_clean_project(root: Path) -> None`, `run_matrix(clean: Path, defects: list[Defect] | None) -> dict` (rows with keys `id`, `expected`, `got`, `status`); read the module for the exact `Defect` field order before writing the test.

- [ ] **Step 1: Write the failing integration test** in `tests/test_schema_version_compat.py`:

```python
def test_a_sidecar_with_an_older_minor_version_passes_the_whole_validator(tmp_path):
    from src.validation_matrix import NONE, SIDECAR, Defect, _json, build_clean_project, run_matrix
    clean = tmp_path / "control"
    build_clean_project(clean)
    older = Defect("sidecar_older_minor", "the sidecar declares an older minor schema version", NONE,
                   _json(SIDECAR, lambda d: d["Metadata"].__setitem__("SchemaVersion", "2.0.0")))
    row = run_matrix(clean, [older])["rows"][0]
    assert "PRISM005" not in row["got"], row
```

  (Match the `Defect(...)` constructor to the module; the call above mirrors the existing `sidecar_old_schema_version` defect.) Also change the library test so it asserts the **major** only: rename it `test_every_official_survey_template_declares_the_current_major_schema_version`, compare `parse_version(v)[0] == parse_version(current)[0]`, and keep its failure message listing the offenders. Reason: under the new rule a minor release must not force a rewrite of 103 files.
- [ ] **Step 2: Run to verify it fails.** Run: `.venv/bin/python -m pytest tests/test_schema_version_compat.py::test_a_sidecar_with_an_older_minor_version_passes_the_whole_validator -q -p no:cacheprovider` BEFORE Task 1's change is in (use `git stash` of the source change or run on a checkout of `origin/main`) to prove it fails with `PRISM005` in `got`; with Task 1 in, it passes. If Task 1 is already committed, check the RED by temporarily reverting `is_compatible_version` and say so in the report.
- [ ] **Step 3: Run to verify it passes** with the final code: `.venv/bin/python -m pytest tests/test_schema_version_compat.py tests/test_official_survey_library_valid.py tests/test_validation_matrix.py tests/test_validation_matrix_cli.py -q -p no:cacheprovider`. Expected: PASS.
- [ ] **Step 4: Commit** `test(validator): end-to-end check for an older minor version; library test compares the major only`.

### Task 3: Docs

**Files:**
- Modify: `docs/ERROR_CODES.md:55` (the `PRISM005` row)

- [ ] **Step 1:** change the row's meaning and fix: "Schema version mismatch: the file declares a different **major** version of a schema than the validator's. An older or newer minor version of the same major version is accepted." Fix: "Update `SchemaVersion` in the metadata to the current major version, or pass `--schema-version` to match." Add one sentence under the table or in the versioning section of the docs that explains the rule ("within a major version a schema only adds optional things").
- [ ] **Step 2: Verify** `python tests/verify_repo.py --check dual-tree-drift --no-fix` still prints `Done.` and that the docs build check is not affected (`python -m pytest tests -k "docs" -q -p no:cacheprovider`). Remove any stray report file `verify_repo` leaves behind.
- [ ] **Step 3: Commit** `docs(error codes): PRISM005 is about a different major version only`.

---

## Self-Review

- **Spec coverage:** section 5 "Versioning rule" (rule, different major still warns, reason) is Tasks 1 and 2; the CONTRIBUTING sentence "within a major only optional additions" belongs to prism-specification and is part of plan B; the docs row is Task 3.
- **Type consistency:** `parse_version` returns a three-tuple everywhere (`modality_versions` compares tuples; `environment_conversion` compares to `parse_version("2.0.0")`: unaffected).
- **Rulings made here (the user may overrule):** a file declaring a *newer* minor than the validator's stays silent (unchanged; the user decided only the older-minor case); unparseable versions warn as "another major" rather than being ignored; the library test compares majors, not exact versions.
- **Proportion:** three small tasks for a one-function change; the tests carry the decisions.

## Outline of the later plans (each its own plan, written when its predecessor is merged)

| Plan | Repo | What | Needs |
|---|---|---|---|
| B. Meaning block | prism-specification, then Studio sync | one shared definition, generator adds it to every latest stable modality schema, test fails when a modality lacks it; `Match` (SKOS), `Higher`, `Status`, `Checked`; CONTRIBUTING gets the additive-only rule; sync | A; order after the template-slimming survey releases |
| C. Concept registry | both | `Level: concept` (kind enumeration, same-kind parent), check script, proposal route, Studio readers (`terms` commands for `--modality concept`) | B |
| D. Projection | prism-specification (format, context, checker, examples), Studio (`src/` producer, CLI) | variable catalogue first, then observations; conformance test over every modality's example | B, C |
| E. Adoption | Studio, then spec | survey derived IDs plus `IsAbout`; biosample and environment; biometrics, physio, events, participants (Neurobagel read/write/export) | D |
| G. Proposal route | prism-specification + Studio | new-kind form asks for the meaning, bot checks it, `check_modalities.py` rule, `terms propose` grows the meaning fields | B, C, D |
| F. AIDA-Path proof | with the Salzburg partner | a handful of PHQ-9 items linked with a named value mapping, projection read by their side | D, E (survey) |
