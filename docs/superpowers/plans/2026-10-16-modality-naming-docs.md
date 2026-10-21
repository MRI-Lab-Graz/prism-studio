# Modality Naming, Suffix Extensions and Docs Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A proposal can add a suffix to an existing modality or create a new modality; new modalities get one fixed filename pattern (task optional), optional entity-value suggestions, generated docs, and CI refuses a registered modality without documentation. "Rationale" disappears.

**Architecture:** `entities.schema.json` modality entries gain an optional `allowedEntities` list that `src/entity_rules.py` reads and `app/src/validator.py` enforces. `src/modality_contribution.py` (the one implementation; CLI and bot only call it) learns two proposal kinds (`new` / `extension`), an `Entities` sheet, and generates docs. `tests/verify_repo.py` gets a `modality-docs` check.

**Tech Stack:** Python 3, pytest, openpyxl/pandas (already used), jsonschema, GitHub Actions YAML, Sphinx/MyST docs.

**Spec:** `docs/superpowers/specs/2026-10-16-modality-naming-docs-design.md` (builds on `2026-10-15-modality-registration-design.md`).

## Global Constraints

- TDD: every task starts with a failing test, run it and see it fail first (repo rule).
- `src/` is the single backend; the Flask/GUI layer is not touched. `src/modality_contribution.py` exists only under `src/` (no `app/src/` copy).
- `python prism_tools.py modality propose ...` stays the only entry point; no GUI work.
- Session/label values are free-form strings, never normalised.
- Existing modalities (`survey`, `biometrics`, `environment`, `events`, `physio`, `eyetracking`) keep their current filename behaviour: `allowedEntities` is opt-in per entry.
- Run tests with `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest ...` (as used on this branch). Known failing on main: 3 tests in `tests/test_lsa_import_integration.py`; `tests/e2e` is out of scope.
- Commit messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Before merging: run `/ponytail:ponytail-audit` on the branch (CLAUDE.md rule).

## Review Focus

- A proposal whose `Name` is a BIDS modality (`anat`) or an alias (`physiological`) must get a message that says what to do instead, not "taken".
- An old workbook/YAML that still has a `Rationale` column/key must read fine (ignored), not crash.
- An extension proposal that carries `Entities` rows is an error (the modality's entities are not changed this way).
- `sub-01_acq-fasting_task-x_bloodchem.tsv` (wrong order), a duplicate `run-`, and `sub-01_foo-1_bloodchem.tsv` are each an ERROR for a modality with `allowedEntities`; `sub-01_bloodchem.tsv` (no task) is valid.
- A hyphenated label (`task-bfi-s`) must not be misread as an entity named `bfi`.
- The docs gate must also catch a modality that is documented but missing from the toctree.

---

## File Structure

- Modify `src/entity_rules.py`: `allowed_entities` on `ModalityRule`, new pure `check_entities()`.
- Modify `app/src/validator.py`: call `check_entities` in `validate_filename`.
- Modify `src/modality_contribution.py`: reader (no rationale, `Entities`), `proposal_kind`, routing in `check_proposal`, fixed-pattern generators, extension artifacts, `build_docs_page` / `build_docs_snippets`, `check_extension_fit`.
- Modify `tests/verify_repo.py`: `check_modality_docs` and its registration.
- Modify `.github/workflows/ci.yml`: add `modality-docs` to the fast check list.
- Modify `scripts/ci/modality_issue_to_files.py` (`Closes #N`), `.github/ISSUE_TEMPLATE/propose-modality.yml` (no rationale box).
- Create `docs/specs/physio.md`; modify `docs/specs/environment.md`, `docs/specs/entities.md` (only if the gate says so), `docs/SCHEMA_SPECIFICATIONS.md` (physio card), `docs/index.rst` (physio entry).
- Modify examples, shipped template workbook, README, `docs/MODALITY_PROPOSALS.md`, `docs/MODALITY_WORKFLOW.md`, `docs/CLI_REFERENCE.md`.
- New tests: `tests/test_entity_rules_allowed.py`, `tests/test_validator_allowed_entities.py`, `tests/test_modality_extension.py`, `tests/test_modality_docs_gen.py`, `tests/test_verify_repo_modality_docs.py`; existing modality tests adjusted where named below.

---

### Task 1: `allowedEntities` in the rules and the validator

**Files:**
- Modify: `src/entity_rules.py` (`ModalityRule`, new `check_entities`)
- Modify: `app/src/validator.py` (inside `validate_filename`, after the `BIDS_REGEX` check, ~line 1275)
- Test: `tests/test_entity_rules_allowed.py`, `tests/test_validator_allowed_entities.py`

**Interfaces:**
- Produces: `ModalityRule.allowed_entities: tuple[str, ...] | None`; `check_entities(base: str, allowed: tuple[str, ...], order: tuple[str, ...]) -> list[str]` (messages, empty = fine). `base` is the filename without extension, e.g. `sub-01_acq-fasting_bloodchem`.

- [ ] **Step 1: Write the failing tests**

`tests/test_entity_rules_allowed.py`:

```python
import pytest

from src.entity_rules import ModalityRule, check_entities, load_entity_rules

ORDER = ("sub", "ses", "task", "acq", "run", "rec")
ALLOWED = ("task", "acq", "run")


def _msgs(base):
    return check_entities(base, ALLOWED, ORDER)


def test_rule_reads_allowed_entities():
    rule = ModalityRule.from_json(
        "x", {"kind": "prism", "suffixes": ["x"], "extensions": ["tsv"], "allowedEntities": ["task", "acq"]}
    )
    assert rule.allowed_entities == ("task", "acq")


def test_rule_without_the_key_has_none():
    rule = ModalityRule.from_json("x", {"kind": "prism", "suffixes": ["x"], "extensions": ["tsv"]})
    assert rule.allowed_entities is None


def test_existing_modalities_have_no_allowed_entities_yet():
    rules = load_entity_rules()
    assert all(r.allowed_entities is None for r in rules.modalities.values())


@pytest.mark.parametrize(
    "base",
    [
        "sub-01_bloodchem",  # task is optional
        "sub-01_ses-pre_bloodchem",
        "sub-01_task-x_acq-fasting_run-2_bloodchem",
        "sub-01_task-bfi-s_bloodchem",  # hyphenated label is one value, not an entity
    ],
)
def test_valid_names_pass(base):
    assert _msgs(base) == []


def test_foreign_entity_is_reported():
    assert "'foo'" in " ".join(_msgs("sub-01_foo-1_bloodchem"))


def test_wrong_order_is_reported():
    assert "order" in " ".join(_msgs("sub-01_acq-a_task-x_bloodchem"))


def test_duplicate_entity_is_reported():
    assert "twice" in " ".join(_msgs("sub-01_run-1_run-2_bloodchem"))
```

`tests/test_validator_allowed_entities.py`:

```python
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

import validator as v  # noqa: E402
from src.entity_rules import ModalityRule  # noqa: E402


@pytest.fixture
def strict_modality(monkeypatch):
    rule = ModalityRule.from_json(
        "biosample",
        {"kind": "prism", "suffixes": ["bloodchem"], "extensions": ["tsv", "json"],
         "allowedEntities": ["task", "acq", "run"]},
    )
    monkeypatch.setitem(v._ENTITY_RULES.modalities, "biosample", rule)
    monkeypatch.setitem(v.MODALITY_PATTERNS, "biosample", v._ENTITY_RULES.pattern_for("biosample"))
    monkeypatch.setattr(v, "PRISM_MODALITIES", v.PRISM_MODALITIES | {"biosample"})


def _errors(name):
    issues = v.DatasetValidator().validate_filename(name, "biosample", subject_id="sub-01")
    return [m for level, m in issues if level == "ERROR"]


def test_task_is_optional(strict_modality):
    assert _errors("sub-01_bloodchem.tsv") == []
    assert _errors("sub-01_acq-fasting_bloodchem.tsv") == []


def test_foreign_entity_is_an_error(strict_modality):
    assert any("'foo'" in m for m in _errors("sub-01_foo-1_bloodchem.tsv"))


def test_modalities_without_the_key_are_unchanged():
    issues = v.DatasetValidator().validate_filename(
        "sub-01_foo-1_task-x_biometrics.tsv", "biometrics", subject_id="sub-01"
    )
    assert not any("not allowed" in m for _, m in issues)
```

- [ ] **Step 2: Run to verify failure**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_entity_rules_allowed.py tests/test_validator_allowed_entities.py`
Expected: FAIL (ImportError `check_entities`).

- [ ] **Step 3: Implement**

In `src/entity_rules.py`, add the field and parsing in `ModalityRule`:

```python
    allowed_entities: tuple[str, ...] | None = None
```
and in `from_json`, add to the constructor call:
```python
            allowed_entities=(
                tuple(data["allowedEntities"]) if "allowedEntities" in data else None
            ),
```
Add below `compile_modality_regex`:

```python
def check_entities(base: str, allowed: tuple[str, ...], order: tuple[str, ...]) -> list[str]:
    """Problems with the entities of a filename (without extension) for a modality
    that declares allowedEntities. sub/ses are always allowed."""
    keys = [t.split("-", 1)[0] for t in base.split("_")[1:] if "-" in t]
    permitted = {"sub", "ses", *allowed}
    problems = [
        f"entity '{k}-' is not allowed (allowed: {', '.join(e for e in order if e in permitted)})"
        for k in dict.fromkeys(keys)
        if k not in permitted
    ]
    problems += [f"entity '{k}-' appears twice" for k in dict.fromkeys(keys) if keys.count(k) > 1]
    ranks = [order.index(k) for k in keys if k in order]
    if ranks != sorted(ranks):
        problems.append("entities must appear in the order " + ", ".join(e for e in order if e in permitted))
    return problems
```

In `app/src/validator.py` `validate_filename`, right after the `if not BIDS_REGEX.match(base): ...` block:

```python
        rule = _ENTITY_RULES.modalities.get(modality)
        if rule is not None and rule.allowed_entities is not None:
            for message in check_entities(base, rule.allowed_entities, _ENTITY_RULES.entity_order):
                issues.append(("ERROR", f"{message}: {filename}"))
```
and extend the existing import line `from src.entity_rules import load_entity_rules` (find it near line 24) to also import `check_entities`.

- [ ] **Step 4: Run to verify pass**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_entity_rules_allowed.py tests/test_validator_allowed_entities.py tests/test_entity_rules.py tests/test_unit.py`
Expected: PASS (the last two prove nothing existing changed).

- [ ] **Step 5: Commit**

```bash
git add src/entity_rules.py app/src/validator.py tests/test_entity_rules_allowed.py tests/test_validator_allowed_entities.py
git commit -m "feat(validator): optional allowedEntities per modality

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Reader without rationale, with `Entities`; entity checks

**Files:**
- Modify: `src/modality_contribution.py` (`_finish_proposal`, `_read_workbook`, `read_proposal`, `write_proposal_workbook`, `check_proposal`)
- Modify tests: `tests/test_modality_proposal_check.py` (rationale), `tests/test_modality_proposal_reader.py`, `tests/test_modality_types.py` (anything asserting `rationale`; find with `grep -n rationale tests/test_modality_*.py`)
- Test: `tests/test_modality_extension.py` (new, entity part)

**Interfaces:**
- Produces: proposal dict has no `rationale`; has `"entities": [{"entity": str, "value": str, "description": str}]` (empty list if none). `ENTITY_SUGGESTIONS = ("task", "acq")`.

- [ ] **Step 1: Write the failing tests**

Append to a new `tests/test_modality_extension.py`:

```python
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.modality_contribution import (  # noqa: E402
    check_proposal,
    errors_only,
    read_proposal,
    write_proposal_workbook,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "modality_proposal"
NEW = EXAMPLES / "biosample.yml"


def _proposal(**over) -> dict:
    p = read_proposal(NEW)
    p.update(over)
    return p


def _messages(problems) -> str:
    return " | ".join(f"{p.where}: {p.message}" for p in errors_only(problems))


def test_old_files_with_rationale_still_read(tmp_path):
    f = tmp_path / "p.yml"
    f.write_text(
        "modality: biosample\nsuffix: bloodchem\nextensions: [tsv]\ndescription: d\n"
        "rationale: old text\ncolumns:\n  - id: crp\n    description: c\n",
        encoding="utf-8",
    )
    assert "rationale" not in read_proposal(f)


def test_entities_are_read_from_yaml_and_workbook(tmp_path):
    p = read_proposal(NEW)
    assert {"entity": "acq", "value": "fasting"}.items() <= p["entities"][0].items()
    wb = tmp_path / "p.xlsx"
    write_proposal_workbook(p, wb)
    assert read_proposal(wb)["entities"] == p["entities"]


def test_missing_description_is_the_only_text_requirement():
    msg = _messages(check_proposal(_proposal(description="")))
    assert "Modality.Description" in msg
    assert "Rationale" not in msg


@pytest.mark.parametrize(
    "entities,needle",
    [
        ([{"entity": "run", "value": "1", "description": ""}], "task"),  # only task/acq suggestable
        ([{"entity": "acq", "value": "fasting study", "description": ""}], "letters and digits"),
        (
            [{"entity": "acq", "value": "a", "description": ""}, {"entity": "acq", "value": "a", "description": ""}],
            "duplicate",
        ),
    ],
)
def test_entity_suggestions_are_checked(entities, needle):
    assert needle in _messages(check_proposal(_proposal(entities=entities)))
```

In `tests/test_modality_proposal_check.py`, change `test_extensions_description_and_rationale_are_required` to drop `rationale=""` and the `Modality.Rationale` assertion; remove `rationale` from any other test in the files listed above.

- [ ] **Step 2: Run to verify failure**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_modality_extension.py`
Expected: FAIL (`entities` missing; example still has rationale).

- [ ] **Step 3: Implement**

In `src/modality_contribution.py`:

1. Constant next to `TYPE_OTHER`: `ENTITY_SUGGESTIONS = ("task", "acq")` and, next to the other regexes, `_ENTITY_VALUE_RE = re.compile(r"^[A-Za-z0-9]+$")`.
2. After `_normalize_types` add:

```python
def _normalize_entities(raw) -> list[dict]:
    from src.converters.excel_to_biometrics import _clean_key

    out = []
    for item in raw or []:
        if not isinstance(item, dict):
            raise ProposalError("entities: every entry must be a mapping with entity, value, description")
        if isinstance(item.get("value"), bool):
            raise ProposalError(
                "entities: a value was read as a YAML boolean (yes/no/on/off/true/false); put the values in quotes"
            )
        out.append({
            "entity": (_clean_key(item.get("entity")) or "").lower(),
            "value": _clean_key(item.get("value")) or "",
            "description": _clean_key(item.get("description")) or "",
        })
    return out
```
3. `_finish_proposal(base, rows, types=None, entities=None)`: change the key tuple to `("modality", "suffix", "description")` and add `proposal["entities"] = _normalize_entities(entities)`.
4. `_read_workbook`: remove the `("rationale", "Rationale")` pair; change the return to a 4-tuple by appending, after the Types block:

```python
    entities: list[dict] = []
    if "Entities" in sheets and len(sheets["Entities"]):
        esheet = sheets["Entities"]
        eheader = [str(v) for v in esheet.iloc[0].tolist()]
        e_idx = find_column_idx(eheader, {"Entity"})
        v_idx = find_column_idx(eheader, {"Value"})
        d_idx = find_column_idx(eheader, {"Description"})
        if e_idx is None or v_idx is None:
            raise ProposalError("sheet 'Entities' needs 'Entity' and 'Value' columns")
        for i in range(1, len(esheet)):
            row = esheet.iloc[i]
            if cell(row, e_idx) or cell(row, v_idx):
                entities.append({"entity": cell(row, e_idx), "value": cell(row, v_idx), "description": cell(row, d_idx)})
    return base, rows, types, entities
```
5. `read_proposal`: `base, rows, types, entities = _read_workbook(path)` then `_finish_proposal(base, rows, types, entities)`; for YAML add `entities = raw.get("entities")` (must be a list or None, same error style as `types`) and pass it.
6. `write_proposal_workbook`: header becomes `["Name", "Suffix", "Extensions", "Description"]`, row drops `proposal["rationale"]`; after the Types sheet add:

```python
    ents = wb.create_sheet("Entities")
    ents.append(["Entity", "Value", "Description"])
    for e in proposal["entities"]:
        ents.append([e["entity"], e["value"], e["description"] or None])
```
7. `check_proposal`: replace the `for key, label in (("description", ...), ("rationale", ...))` loop with a single description check, and add after the Types block:

```python
    seen_entities: set[tuple[str, str]] = set()
    for n, e in enumerate(proposal.get("entities") or [], start=1):
        where = f"Entities.{e['entity']}-{e['value']}" if e["value"] else f"Entities row {n}"
        if e["entity"] not in ENTITY_SUGGESTIONS:
            err(where, f"only {list(ENTITY_SUGGESTIONS)} values can be suggested, got '{e['entity']}'")
        if not _ENTITY_VALUE_RE.match(e["value"]):
            err(where, f"'{e['value']}' may only contain letters and digits")
        if (e["entity"], e["value"]) in seen_entities:
            err(where, f"duplicate suggestion '{e['entity']}-{e['value']}'")
        seen_entities.add((e["entity"], e["value"]))
```
8. In `examples/modality_proposal/biosample.yml` delete the `rationale:` line and add at the end:

```yaml
entities:
  - entity: acq
    value: fasting
    description: Drawn after at least 8 hours without food
  - entity: acq
    value: nonfasting
    description: Drawn without fasting
```
Regenerate the shipped workbook (the template test requires it equals the YAML):

```bash
PYTHONPATH=app/src python3 -c "
from src.modality_contribution import read_proposal, write_proposal_workbook
write_proposal_workbook(read_proposal('examples/modality_proposal/biosample.yml'), 'official/create_new_modality/modality_proposal_template.xlsx')"
```

- [ ] **Step 4: Run to verify pass**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_modality_extension.py tests/test_modality_proposal_check.py tests/test_modality_proposal_reader.py tests/test_modality_types.py tests/test_modality_template_workbook.py tests/test_cli_modality.py`
Expected: PASS. Fix any remaining `rationale` assertions the failures point to.

- [ ] **Step 5: Commit**

```bash
git add src/modality_contribution.py tests examples official/create_new_modality
git commit -m "feat(modality): drop rationale, add optional Entities suggestions

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Two proposal kinds (new modality / suffix in an existing one)

**Files:**
- Modify: `src/modality_contribution.py` (`proposal_kind`, `check_proposal`, `_taken_names` helper split)
- Modify tests: `tests/test_modality_proposal_check.py` (the `survey` row)
- Test: `tests/test_modality_extension.py`

**Interfaces:**
- Consumes: `_taken_names(schema_dir)`, `_bids_names()`.
- Produces: `proposal_kind(proposal: dict, schema_dir: str | None = None) -> str` returning `"extension"` when `Name` is an existing modality of kind `prism`, else `"new"`; `_entities_schema(schema_dir) -> dict` (the loaded `entities.schema.json`).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_modality_extension.py`)

```python
from src.modality_contribution import proposal_kind  # noqa: E402


def _ext(**over):
    return _proposal(modality="biometrics", suffix="bloodpanel", entities=[], **over)


def test_kind_is_new_for_an_unknown_name_and_extension_for_a_prism_modality():
    assert proposal_kind(_proposal()) == "new"
    assert proposal_kind(_ext()) == "extension"


def test_extension_with_a_free_suffix_has_no_errors():
    assert errors_only(check_proposal(_ext())) == []


def test_extension_suffix_that_is_taken_is_still_rejected():
    assert "PRISM suffix 'survey'" in _messages(check_proposal(_ext(suffix="survey")))
    assert "BIDS suffix 'blood'" in _messages(check_proposal(_ext(suffix="blood")))


def test_extension_cannot_carry_entity_suggestions():
    ents = [{"entity": "acq", "value": "fasting", "description": ""}]
    assert "existing modality" in _messages(check_proposal(_ext(entities=ents)))


def test_bids_and_passthrough_names_are_refused_with_advice():
    assert "BIDS" in _messages(check_proposal(_proposal(modality="anat")))
    assert "BIDS datatype 'phenotype'" in _messages(check_proposal(_proposal(modality="phenotype")))
    assert "upstream" in _messages(check_proposal(_proposal(modality="eyetracking")))


def test_alias_points_at_the_real_modality():
    msg = _messages(check_proposal(_proposal(modality="physiological")))
    assert "PRISM alias 'physiological'" in msg and "'physio'" in msg
```

In `tests/test_modality_proposal_check.py` remove the row `("modality", "survey", "PRISM modality 'survey'")` from the parametrize list (a prism modality name is now an extension; covered above).

- [ ] **Step 2: Run to verify failure**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_modality_extension.py -k "kind or extension or refused or alias"`
Expected: FAIL (ImportError `proposal_kind`).

- [ ] **Step 3: Implement**

Add above `_taken_names`:

```python
def _entities_schema(schema_dir: str | None) -> dict:
    from src.schema_manager import DEFAULT_SCHEMA_DIR, load_schema

    return load_schema("entities", schema_dir or DEFAULT_SCHEMA_DIR, "stable") or {}


def proposal_kind(proposal: dict, schema_dir: str | None = None) -> str:
    """'extension' = add a suffix to an existing PRISM modality, else 'new'."""
    rule = _entities_schema(schema_dir).get("modalities", {}).get(proposal.get("modality"), {})
    return "extension" if rule.get("kind") == "prism" else "new"
```
Make `_taken_names` use `_entities_schema(schema_dir)` instead of its inline load (same behaviour).

In `check_proposal`, replace the `for key, label in (("modality", "Name"), ("suffix", "Suffix")):` loop by:

```python
    taken = _taken_names(schema_dir)
    entities_schema = _entities_schema(schema_dir)
    kind = proposal_kind(proposal, schema_dir)
    name, suffix = proposal.get("modality") or "", proposal.get("suffix") or ""
    aliases = entities_schema.get("aliases", {})
    bids_modalities = {
        n for n, r in entities_schema.get("modalities", {}).items() if r.get("kind") != "prism"
    }
    for value, label in ((name, "Name"), (suffix, "Suffix")):
        where = f"Modality.{label}"
        if not _NAME_RE.match(value):
            err(where, f"'{value}' must be lowercase letters and digits, starting with a letter")
    if _NAME_RE.match(name):
        if name in aliases:
            err("Modality.Name", f"{taken[name]}. Use '{aliases[name]}' as the name to add a suffix to it.")
        elif name in bids_modalities or (name in taken and kind == "new" and taken[name].startswith("BIDS")):
            err(
                "Modality.Name",
                f"{taken.get(name, name)}: BIDS owns this folder; propose the suffix to BIDS upstream "
                "(https://bids.neuroimaging.io), not here.",
            )
        elif kind == "new" and name in taken:
            err("Modality.Name", f"'{name}' is already taken: {taken[name]}. Choose another name.")
    if _NAME_RE.match(suffix) and suffix in taken:
        err("Modality.Suffix", f"'{suffix}' is already taken: {taken[suffix]}. Choose another suffix.")
    if kind == "extension" and proposal.get("entities"):
        err("Entities", "entity suggestions are not used when adding a suffix to an existing modality; remove them")
```
Note: `taken[name]` for `anat` reads "PRISM modality 'anat'"; the message therefore says "BIDS owns this folder", which is the intended advice.

- [ ] **Step 4: Run to verify pass**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_modality_extension.py tests/test_modality_proposal_check.py tests/test_cli_modality.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/modality_contribution.py tests
git commit -m "feat(modality): proposals can add a suffix to an existing modality

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Generators: fixed pattern, extension artifacts, docs

**Files:**
- Modify: `src/modality_contribution.py` (`write_minimal_dataset`, `build_schema`, `build_example_sidecar`, `registration_entry`, `build_registration_md`, `build_modality_artifacts`; new `build_docs_page`, `build_docs_snippets`, `check_extension_fit`)
- Modify tests: `tests/test_modality_build.py` (TaskName and fixture file-name assertions), `tests/test_modality_contribution.py` (none expected)
- Create: `examples/modality_proposal/bloodpanel.yml`, `examples/modality_proposal/bloodpanel_sample.tsv`
- Test: `tests/test_modality_docs_gen.py`, `tests/test_modality_extension.py` (build part), `tests/test_modality_registration_e2e.py` (extension e2e)

**Interfaces:**
- Consumes: `proposal_kind`, `_entities_schema` (Task 3), proposal `entities` (Task 2).
- Produces:
  - `registration_entry(proposal, existing: dict | None = None) -> dict`: new modality → `{"kind","suffixes","extensions","allowedEntities"[,"optionalEntityValues"]}`; with `existing` (the modality's current entry) → that entry with the suffix appended and new extensions merged.
  - `build_docs_page(proposal) -> str` (full `docs/specs/<name>.md` for a new modality), `build_docs_snippets(proposal) -> dict[str, str]` with keys `toctree`, `entities_row`, `card`.
  - `check_extension_fit(proposal, schema_dir=None) -> list[Problem]` (warnings: the example sidecar vs the target modality's own schema).
  - `build_modality_artifacts` also writes `docs/<name>.md` (new) or `docs/<modality>-<suffix>.md` (extension) into the output folder, and for an extension no `<name>.schema.json`.

- [ ] **Step 1: Write the failing tests**

`tests/test_modality_docs_gen.py`:

```python
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.modality_contribution import (  # noqa: E402
    build_docs_page,
    build_docs_snippets,
    build_registration_md,
    build_schema,
    read_proposal,
    registration_entry,
)

P = read_proposal(Path(__file__).resolve().parents[1] / "examples" / "modality_proposal" / "biosample.yml")


def test_new_entry_has_the_fixed_pattern_and_the_suggestions():
    e = registration_entry(P)
    assert e["allowedEntities"] == ["task", "acq", "run"]
    assert e["optionalEntityValues"]["acq"] == {
        "enum": ["fasting", "nonfasting"],
        "allowOther": True,
        "otherPattern": "[a-zA-Z0-9]+",
    }


def test_entry_without_suggestions_has_no_optional_values():
    assert "optionalEntityValues" not in registration_entry({**P, "entities": []})


def test_schema_text_and_study_block_make_task_optional():
    s = build_schema(P)
    assert "[_task-<label>]" in s["description"]
    assert "TaskName" not in s["properties"]["Study"]["required"]


def test_docs_page_has_pattern_suggestions_and_columns():
    page = build_docs_page(P)
    assert page.startswith("# Biosample")
    assert "sub-<label>[_ses-<label>][_task-<label>][_acq-<label>][_run-<index>]_bloodchem.<extension>" in page
    assert "`acq-fasting`" in page and "Drawn after at least 8 hours" in page
    assert "`crp`" in page and "mg/L" in page


def test_snippets_name_the_pages_the_gate_checks():
    s = build_docs_snippets(P)
    assert s["toctree"] == "   specs/biosample"
    assert s["entities_row"].startswith("| `biosample` | prism | `bloodchem` |")
    assert 'href="specs/biosample.html"' in s["card"]


def test_registration_md_lists_the_docs_steps():
    md = build_registration_md(P)
    for needle in ("docs/specs/biosample.md", "docs/index.rst", "docs/SCHEMA_SPECIFICATIONS.md",
                   "docs/specs/entities.md", "modality-docs"):
        assert needle in md
```

Append to `tests/test_modality_extension.py`:

```python
import json

from src.modality_contribution import (  # noqa: E402
    build_modality_artifacts,
    build_registration_md,
    check_extension_fit,
    registration_entry,
)

EXT = EXAMPLES / "bloodpanel.yml"
EXT_SAMPLE = EXAMPLES / "bloodpanel_sample.tsv"


def test_extension_entry_appends_to_the_existing_one():
    existing = {"kind": "prism", "suffixes": ["biometrics"], "extensions": ["tsv", "json"]}
    e = registration_entry(read_proposal(EXT), existing)
    assert e == {"kind": "prism", "suffixes": ["biometrics", "bloodpanel"], "extensions": ["tsv", "json"]}
    e2 = registration_entry({**read_proposal(EXT), "extensions": ["tsv.gz"]}, existing)
    assert e2["extensions"] == ["tsv", "json", "tsv.gz"]


def test_extension_build_writes_no_schema_and_a_modality_fixture(tmp_path):
    p = read_proposal(EXT)
    files = build_modality_artifacts(p, EXT_SAMPLE, EXT, tmp_path / "out")
    names = {f.relative_to(tmp_path / "out").as_posix() for f in files}
    assert "biometrics.schema.json" not in names
    assert "fixture/sub-01/biometrics/sub-01_bloodpanel.tsv" in names
    assert "docs/biometrics-bloodpanel.md" in names
    md = (tmp_path / "out" / "REGISTRATION.md").read_text(encoding="utf-8")
    assert '"bloodpanel"' in md and "biometrics.schema.json" not in md


def test_extension_example_sidecar_is_fitted_to_the_target_schema():
    assert [w for w in check_extension_fit(read_proposal(EXT)) if w.severity == "error"] == []


def test_new_build_fixture_has_no_task_entity(tmp_path):
    p = read_proposal(NEW)
    files = build_modality_artifacts(p, EXAMPLES / "biosample_sample.tsv", NEW, tmp_path / "o")
    assert any(f.name == "sub-01_bloodchem.tsv" for f in files)
    assert (tmp_path / "o" / "docs" / "biosample.md").is_file()
    assert json.loads((tmp_path / "o" / "example_sidecar.json").read_text())["Study"].get("TaskName") is None
```

Append to `tests/test_modality_registration_e2e.py`:

```python
def test_extension_registration_makes_the_fixture_validate(tmp_path: Path) -> None:
    sys.path.insert(0, str(REPO / "app" / "src"))
    from src.modality_contribution import build_modality_artifacts, read_proposal

    proposal = read_proposal(EXAMPLE_DIR / "bloodpanel.yml")
    out = tmp_path / "proposal"
    build_modality_artifacts(proposal, EXAMPLE_DIR / "bloodpanel_sample.tsv", EXAMPLE_DIR / "bloodpanel.yml", out)
    repo = _copy_repo(tmp_path / "repo")
    md = (out / "REGISTRATION.md").read_text(encoding="utf-8")
    snippet = json.loads(re.search(r"```json\n(.*?)\n```", md, re.S).group(1))
    entities_path = repo / "app" / "schemas" / "stable" / "entities.schema.json"
    entities = json.loads(entities_path.read_text(encoding="utf-8"))
    entities["modalities"].update(snippet)
    entities_path.write_text(json.dumps(entities, indent=2), encoding="utf-8")

    after = _validate(repo, out / "fixture")
    assert after["errors"] == []
    assert after["modalities"].get("biometrics", 0) >= 1
```

In `tests/test_modality_build.py` update: the sidecar test asserting `sidecar["Study"]["TaskName"] == "biosample"` now asserts `"TaskName" not in sidecar["Study"]`; any assertion naming `sub-01_task-biosample_bloodchem` becomes `sub-01_bloodchem`; `test_registration_entry_and_markdown` expects the new keys (`allowedEntities`, `optionalEntityValues`). The e2e test `test_following_registration_md_makes_the_fixture_validate` stays as is: it must still pass (new modality, no task in the file name).

- [ ] **Step 2: Run to verify failure**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_modality_docs_gen.py tests/test_modality_extension.py tests/test_modality_build.py`
Expected: FAIL (missing functions, example files).

- [ ] **Step 3: Implement**

Create the extension example inputs:

`examples/modality_proposal/bloodpanel.yml`:
```yaml
modality: biometrics
suffix: bloodpanel
extensions: [tsv]
description: Venous blood panel drawn at the same visit as other biometrics
columns:
  - id: sample_id
    description: Laboratory sample identifier
  - id: crp
    description: C-reactive protein
    scale: continuous
    units: mg/L
    min: 0
```
`examples/modality_proposal/bloodpanel_sample.tsv` (tab separated):
```
sample_id	crp
S001	1.2
S002	0.8
```

In `src/modality_contribution.py`:

1. `write_minimal_dataset`: change `task_name: str = "demo"` to `task_name: str | None = "demo"` and the stem line to
   `stem = f"sub-01_task-{task_name}_{suffix}" if task_name else f"sub-01_{suffix}"`.
2. `build_schema`: description filename becomes `sub-<label>[_ses-<label>][_task-<label>][_acq-<label>][_run-<index>]_{suffix}.<{'|'.join(exts)}>`; `Study` `"required": ["OriginalName"]`.
3. `build_example_sidecar`: drop `"TaskName": name` from `Study`.
4. `registration_entry`:

```python
FIXED_ENTITIES = ["task", "acq", "run"]


def registration_entry(proposal: dict, existing: dict | None = None) -> dict:
    if existing is not None:  # adding a suffix to an existing modality
        entry = dict(existing)
        entry["suffixes"] = [*existing.get("suffixes", []), proposal["suffix"]]
        entry["extensions"] = list(dict.fromkeys([*existing.get("extensions", []), *proposal["extensions"]]))
        return entry
    exts = list(dict.fromkeys([*proposal["extensions"], "json"]))
    entry = {"kind": "prism", "suffixes": [proposal["suffix"]], "extensions": exts,
             "allowedEntities": FIXED_ENTITIES}
    values: dict[str, list[str]] = {}
    for e in proposal.get("entities") or []:
        values.setdefault(e["entity"], []).append(e["value"])
    if values:
        entry["optionalEntityValues"] = {
            k: {"enum": v, "allowOther": True, "otherPattern": "[a-zA-Z0-9]+"} for k, v in values.items()
        }
    return entry
```
5. Docs generators (add after `registration_entry`):

```python
def _pattern(suffix: str) -> str:
    return f"sub-<label>[_ses-<label>][_task-<label>][_acq-<label>][_run-<index>]_{suffix}.<extension>"


def build_docs_page(proposal: dict) -> str:
    name, suffix = proposal["modality"], proposal["suffix"]
    exts = ", ".join(f"`.{e}`" for e in proposal["extensions"])
    lines = [
        f"# {name.capitalize()}", "", f"{proposal['description']}.", "",
        "## File Name Structure", "", f"`{_pattern(suffix)}`", "",
        "| Entity | Description |", "| --- | --- |",
        "| `sub` | **Required**. The subject identifier. |",
        "| `ses` | Optional. The session identifier. |",
        "| `task` | Optional. The task or protocol, when the data belong to one. |",
        "| `acq` | Optional. A variant of the acquisition. |",
        "| `run` | Optional. The repeat within a session. |",
        f"| `{suffix}` | **Required**. The suffix indicating the data. |",
        f"| extension | **Required**. One of {exts}. |", "",
    ]
    if proposal.get("entities"):
        lines += ["### Suggested values", "", "Other labels are accepted too.", ""]
        lines += [
            f"- `{e['entity']}-{e['value']}`" + (f": {e['description']}" if e["description"] else "")
            for e in proposal["entities"]
        ] + [""]
    lines += ["## Example Columns", "", "Every study defines its own columns in its own sidecar; these are examples.", "",
             "| Column | Description | Units |", "| --- | --- | --- |"]
    lines += [f"| `{c['id']}` | {c['description']} | {c['units']} |" for c in proposal["columns"]]
    lines += ["", "## Sidecar JSON", "",
              f"Each data file needs a JSON sidecar (`*_{suffix}.json`) with `Technical`, `Study` and `Metadata` blocks "
              "and one definition per column (Description, Units, optional MinValue/MaxValue/AllowedValues).", ""]
    return "\n".join(lines)


def build_docs_snippets(proposal: dict) -> dict[str, str]:
    name, suffix = proposal["modality"], proposal["suffix"]
    exts = ", ".join(f"`{e}`" for e in [*proposal["extensions"], "json"])
    return {
        "toctree": f"   specs/{name}",
        "entities_row": f"| `{name}` | prism | `{suffix}` | {exts} | optional `task`, `acq`, `run` |",
        "card": (
            '  <a class="prism-chapter-card" href="specs/%s.html">\n'
            '    <span class="prism-chapter-title">%s</span>\n'
            '    <span class="prism-chapter-outcome">%s</span>\n'
            "  </a>" % (name, name.capitalize(), proposal["description"])
        ),
    }
```
6. Extension fit check:

```python
def _fit_sidecar(sidecar: dict, schema: dict, label: str) -> dict:
    # ponytail: fills the target's required Study keys with the suffix name; a modality
    # with stricter value rules (e.g. a license enum) still needs a maintainer's edit.
    for key in schema.get("properties", {}).get("Study", {}).get("required", []):
        sidecar["Study"].setdefault(key, label)
    return sidecar


def check_extension_fit(proposal: dict, schema_dir: str | None = None) -> list[Problem]:
    """Warn when the generated example sidecar does not match the target modality's own schema."""
    from src.schema_manager import DEFAULT_SCHEMA_DIR, load_schema
    import jsonschema

    schema = load_schema(proposal["modality"], schema_dir or DEFAULT_SCHEMA_DIR, "stable")
    if not schema:
        return []
    sidecar = _fit_sidecar(build_example_sidecar(proposal), schema, proposal["suffix"])
    return [
        Problem("warning", f"{proposal['modality']}.schema.json", e.message)
        for e in jsonschema.Draft7Validator(schema).iter_errors(sidecar)
    ]
```
   (`load_schema(name, dir, version)` is the loader already used by `_entities_schema`; if the signature differs, mirror that call.) Call it at the end of `check_proposal`: `if kind == "extension": problems += check_extension_fit(proposal, schema_dir)` before `return problems`. The e2e test then proves the biometrics example has no errors; an extension's fit problems are warnings, never errors.
7. `build_registration_md(proposal, existing=None)`: keep the new-modality text but replace steps with:

```
1. Copy `{name}.schema.json` to `app/schemas/stable/{name}.schema.json`.
2. In entities.schema.json add this entry under "modalities": <snippet>
3. Add "{name}" to COMMUNITY_MODALITY_SCHEMAS in tests/verify_repo.py.
4. Documentation (CI check `modality-docs` fails without it):
   - copy `docs/{name}.md` to `docs/specs/{name}.md`;
   - add `   specs/{name}` to the "Schema Specifications" toctree in docs/index.rst;
   - add the card from `docs/snippets.md` to docs/SCHEMA_SPECIFICATIONS.md;
   - add the row from `docs/snippets.md` to the table in docs/specs/entities.md.
5. Check: schema-sync, modality-schema-conventions, modality-docs, then `python prism.py <this folder>/fixture`.
```
   For an extension (when `existing` is given): the snippet is `{modality: updated_entry}`, step 1 and 3 are dropped, step 4 reads "add the section from `docs/<modality>-<suffix>.md` to `docs/specs/<modality>.md` (the page must mention `_<suffix>`)", and a note says the example sidecar was fitted heuristically to the modality's schema and the fixture must pass `python prism.py <folder>/fixture`. Write both variants as two f-strings selected by `existing is None`; keep the closing "Review by hand ..." paragraph in both.
8. `build_modality_artifacts`: compute `kind = proposal_kind(proposal)`; `existing = _entities_schema(None)["modalities"][name]` when extension. Differences: no schema file for an extension; `sidecar = _fit_sidecar(sidecar, target_schema, suffix)` for an extension; call `write_minimal_dataset(..., task_name=None)` (fixture folder `modality=name`); the docs go to `out/"docs"/(f"{name}.md" if new else f"{name}-{suffix}.md")` from `build_docs_page` (new) or a short section `## Suffix `_{suffix}`` + the pattern + the columns table (extension; reuse `build_docs_page` body without the title: `"\n".join(build_docs_page(proposal).splitlines()[2:])` prefixed by the section heading), and `out/"docs"/"snippets.md"` containing the three snippets for a new modality. Return list includes these files and excludes the schema for an extension. `REGISTRATION.md` via `build_registration_md(proposal, existing)`.

- [ ] **Step 4: Run to verify pass**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_modality_docs_gen.py tests/test_modality_extension.py tests/test_modality_build.py tests/test_modality_registration_e2e.py tests/test_modality_contribution.py tests/test_cli_modality.py tests/test_modality_proposal_fixtures.py`
Expected: PASS. If the extension e2e reports validator errors for `biometrics`, read the messages and extend `_fit_sidecar` only as far as the target schema's required keys demand; do not special-case modality names.

- [ ] **Step 5: Commit**

```bash
git add src/modality_contribution.py tests examples
git commit -m "feat(modality): fixed filename pattern, extension artifacts, generated docs

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The `modality-docs` check and the missing pages

**Files:**
- Modify: `tests/verify_repo.py` (new `check_modality_docs`, registry entry near line 2550)
- Modify: `.github/workflows/ci.yml` (add `modality-docs` to both `--check` lists: lines ~85 and ~120)
- Create: `docs/specs/physio.md`
- Modify: `docs/specs/environment.md`, `docs/index.rst`, `docs/SCHEMA_SPECIFICATIONS.md`
- Test: `tests/test_verify_repo_modality_docs.py`

**Interfaces:**
- Produces: `check_modality_docs(repo_path, fix=False)`; for every modality of kind `prism` in `app/schemas/stable/entities.schema.json` requires `docs/specs/<name>.md`, `specs/<name>` in `docs/index.rst`, `href="specs/<name>.html"` in `docs/SCHEMA_SPECIFICATIONS.md`, `` `<name>` `` in `docs/specs/entities.md`, and `_<suffix>` for each suffix in the page.

- [ ] **Step 1: Write the failing test** `tests/test_verify_repo_modality_docs.py`

```python
import json
from pathlib import Path


def _load_verify_repo_module():
    import importlib.util

    module_path = Path(__file__).with_name("verify_repo.py")
    spec = importlib.util.spec_from_file_location("verify_repo", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _repo(tmp_path: Path, *, page=True, toctree=True, card=True, row=True, suffix_in_page=True) -> Path:
    (tmp_path / "app/schemas/stable").mkdir(parents=True)
    (tmp_path / "app/schemas/stable/entities.schema.json").write_text(
        json.dumps({"modalities": {"biosample": {"kind": "prism", "suffixes": ["bloodchem"]},
                                   "anat": {"kind": "bidsPassthrough"}}}),
        encoding="utf-8",
    )
    specs = tmp_path / "docs/specs"
    specs.mkdir(parents=True)
    if page:
        (specs / "biosample.md").write_text("pattern ..._bloodchem.tsv" if suffix_in_page else "nothing", encoding="utf-8")
    (tmp_path / "docs/index.rst").write_text("   specs/biosample\n" if toctree else "", encoding="utf-8")
    (tmp_path / "docs/SCHEMA_SPECIFICATIONS.md").write_text('href="specs/biosample.html"' if card else "", encoding="utf-8")
    (specs / "entities.md").write_text("| `biosample` | prism |" if row else "", encoding="utf-8")
    return tmp_path


def _run(repo, capsys):
    _load_verify_repo_module().check_modality_docs(str(repo))
    return capsys.readouterr().out


def test_passes_when_everything_is_documented(tmp_path, capsys):
    out = _run(_repo(tmp_path), capsys)
    assert "[✗]" not in out and "documented" in out


def test_bids_passthrough_modalities_are_not_required(tmp_path, capsys):
    assert "anat" not in _run(_repo(tmp_path), capsys)


def test_each_gap_is_reported(tmp_path, capsys):
    for kw, needle in (
        (dict(page=False), "docs/specs/biosample.md"),
        (dict(toctree=False), "docs/index.rst"),
        (dict(card=False), "SCHEMA_SPECIFICATIONS.md"),
        (dict(row=False), "entities.md"),
        (dict(suffix_in_page=False), "_bloodchem"),
    ):
        repo = tmp_path / needle.replace("/", "_")
        repo.mkdir()
        out = _run(_repo(repo, **kw), capsys)
        assert "[✗]" in out and needle in out
```

- [ ] **Step 2: Run to verify failure**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_verify_repo_modality_docs.py`
Expected: FAIL (`check_modality_docs` missing).

- [ ] **Step 3: Implement**

In `tests/verify_repo.py`, below `check_modality_schema_conventions`:

```python
def check_modality_docs(repo_path, fix=False):
    """Every PRISM modality registered in entities.schema.json must be documented."""
    print_header("Checking Modality Documentation")
    root = Path(repo_path)
    entities_path = root / "app" / "schemas" / "stable" / "entities.schema.json"
    if not entities_path.is_file():
        print_success("Modality documentation check skipped (entities.schema.json not found).")
        return

    modalities = json.loads(entities_path.read_text(encoding="utf-8")).get("modalities", {})

    def read(rel):
        path = root / rel
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    index = read("docs/index.rst")
    cards = read("docs/SCHEMA_SPECIFICATIONS.md")
    entities_doc = read("docs/specs/entities.md")
    problems = 0
    for name, rule in sorted(modalities.items()):
        if rule.get("kind") != "prism":
            continue
        page = root / "docs" / "specs" / f"{name}.md"
        if not page.is_file():
            print_error(f"{name}: docs/specs/{name}.md is missing.")
            problems += 1
            continue
        text = page.read_text(encoding="utf-8")
        for ok, message in (
            (f"specs/{name}" in index, f"{name}: not in the toctree of docs/index.rst."),
            (f'href="specs/{name}.html"' in cards, f"{name}: no card in docs/SCHEMA_SPECIFICATIONS.md."),
            (f"`{name}`" in entities_doc, f"{name}: no row in docs/specs/entities.md."),
        ):
            if not ok:
                print_error(message)
                problems += 1
        for suffix in rule.get("suffixes", []):
            if f"_{suffix}" not in text:
                print_error(f"{name}: docs/specs/{name}.md never mentions the suffix _{suffix}.")
                problems += 1
    if not problems:
        print_success("Every PRISM modality is documented (page, toctree, card, entities row, suffixes).")
```
Register: add `"modality-docs": check_modality_docs,` after `"modality-schema-conventions"` in the dict (~line 2550). In `.github/workflows/ci.yml` insert `modality-docs,` after `modality-schema-conventions,` in both `--check` lists.

- [ ] **Step 4: Run to verify the check, then document what it flags**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_verify_repo_modality_docs.py` — Expected: PASS.
Run: `python3 tests/verify_repo.py --check modality-docs --no-fix` on the real repo. Expected today: failures for `physio` (no page, no toctree, no card) and `environment` (suffix `_environment` not mentioned). Fix exactly those:

- Create `docs/specs/physio.md` (content derived from `app/schemas/stable/physio.schema.json` and the `physio` row in `docs/specs/entities.md`):

```markdown
# Physio

Physiological recordings such as ECG, EDA, respiration, PPG and EMG, with a JSON sidecar describing the recording.

## File Name Structure

`sub-<label>[_ses-<label>]_task-<label>[_recording-<label>]_physio.<tsv.gz|tsv|json|edf>`

| Entity | Description |
| --- | --- |
| `sub` | **Required**. The subject identifier. |
| `ses` | Optional. The session identifier. |
| `task` | **Required**. The task during which the signal was recorded. |
| `recording` | Optional. The signal type: `ecg`, `cardiac`, `puls`, `resp`, `eda`, `ppg`, `emg`, `temp`, `bp`, `spo2`, `trigger`, or any other alphanumeric label. |
| `physio` | **Required**. The suffix indicating the modality. |

## Sidecar JSON (`*_physio.json`)

The sidecar requires the `Technical` and `Metadata` blocks, a `Study` block with `TaskName`, and may describe `Recording`, `Channels`, `TriggerAnnotations`, `Acquisition` and `Processing`. The authoritative definition is [`physio.schema.json`](../../app/schemas/stable/physio.schema.json).
```
- `docs/specs/environment.md`: add under "Typical Artifacts" a line "Files are named `sub-<label>_ses-<label>_recording-<label>_environment.tsv` with a matching `_environment.json` sidecar." (the gate needs `_environment`; the line is true per the schema pattern and the validator rule that environment files live under `sub-*/ses-*/environment/`).
- `docs/index.rst`: add `   specs/physio` after `   specs/environment` in the "Schema Specifications" toctree.
- `docs/SCHEMA_SPECIFICATIONS.md`: add after the Environment card a card for `specs/physio.html` in the same markup (title "Physio", outcome "Physiological recordings such as ECG, EDA, respiration").

Re-run `python3 tests/verify_repo.py --check modality-docs --no-fix`. Expected: all checks passed. Run the Sphinx build: `python3 -m sphinx -q -b html docs "$TMPDIR/html" 2>&1 | grep -iE "physio|modality|error"` — Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add tests/verify_repo.py tests/test_verify_repo_modality_docs.py .github/workflows/ci.yml docs
git commit -m "ci: modality-docs check; document physio and environment

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Form, bot, template, CLI wording and user docs

**Files:**
- Modify: `.github/ISSUE_TEMPLATE/propose-modality.yml`, `scripts/ci/modality_issue_to_files.py` (`pr_body`), `official/create_new_modality/README.md`, `docs/MODALITY_PROPOSALS.md`, `docs/MODALITY_WORKFLOW.md`, `docs/CLI_REFERENCE.md` (the `modality propose` section ~line 706)
- Test: `tests/test_modality_issue_to_files.py`, `tests/test_propose_modality_issue_form.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_modality_issue_to_files.py` add to `test_pr_body_links_the_issue_and_carries_warnings`: `assert "Closes #7" in text`. In `tests/test_propose_modality_issue_form.py` add:

```python
def test_form_no_longer_asks_for_a_rationale():
    form = yaml.safe_load(FORM.read_text(encoding="utf-8"))
    labels = {item["attributes"].get("label", "") for item in form["body"] if item.get("type") != "markdown"}
    assert not any("why" in label.lower() for label in labels)
    assert {"Proposal file", "Sample data file", "Privacy"} <= labels
```
Also adjust `_body()` in `tests/test_modality_issue_to_files.py` (it still writes a "Why this modality?" section; remove those two lines so the fixture matches the new form).

- [ ] **Step 2: Run to verify failure**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_modality_issue_to_files.py tests/test_propose_modality_issue_form.py`
Expected: FAIL (`Closes #7`, rationale box).

- [ ] **Step 3: Implement**

- `pr_body`: first sentence becomes `f"Generated by the modality proposal bot from #{issue_number}. Closes #{issue_number} when merged. This is a **draft**."`.
- Form: delete the `rationale` textarea block; in the intro markdown replace item 1 with: "Download the workbook ... In `Modality`, give the **name**: an existing PRISM modality (e.g. `biometrics`) to add a new filename ending (suffix) to it, or a new name to propose a new modality (its folder). Always give the **suffix** (the ending, e.g. `bloodchem`)." Keep the other items.
- `official/create_new_modality/README.md`: remove "rationale" from the `Modality` bullet; add the `Entities` sheet (optional: suggested `task`/`acq` values, e.g. `acq | fasting`) and the existing-vs-new name rule; mention `examples/modality_proposal/bloodpanel.yml` as the extension example.
- `docs/MODALITY_PROPOSALS.md`: remove `Rationale`; add the two kinds, the `Entities` sheet, and a "Filenames" section: fixed pattern `sub-<label>[_ses-<label>][_task-<label>][_acq-<label>][_run-<index>]_<suffix>.<extension>` with `task` optional, other entities are errors, maintainers can refine per modality later. Fix the sentence about CI to match the current behaviour (already reworded; keep).
- `docs/MODALITY_WORKFLOW.md`: step 1 bullets (no `Rationale`, add `Entities`), a new "Existing modality or new one?" subsection before step 1, step 5 (outputs: docs page/snippets, no schema file for an extension), step 6 (registration now includes the docs steps and the `modality-docs` check), and "After the pull request" subsection: check out the PR branch, follow `REGISTRATION.md`, push (full CI runs), review by hand, `ponytail-audit`, mark ready, merge (issue closes automatically), shipped in the next release, project pages pick the new modality up from `entities.schema.json`.
- `docs/CLI_REFERENCE.md`: one sentence: the proposal may add a suffix to an existing modality; `--out` then writes no schema file.

- [ ] **Step 4: Run to verify pass, build the docs**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_modality_issue_to_files.py tests/test_propose_modality_issue_form.py tests/test_propose_modality_workflow.py tests/test_docs_example_paths.py`
Run: `python3 -m sphinx -q -b html docs "$TMPDIR/html" 2>&1 | grep -iE "modality|error"` — Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add .github scripts official docs tests
git commit -m "docs+bot: no rationale, Closes #N, suffix-vs-modality guidance, after-the-PR steps

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Full verification, audit, hand-over

**Files:** none new.

- [ ] **Step 1: Whole suite and repo checks**

Run (background, it takes ~3 minutes): `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q -p no:cacheprovider --ignore=tests/e2e`
Expected: PASS, apart from the three known `test_lsa_import_integration.py` failures if they reappear (report exact counts).
Run: `python3 tests/verify_repo.py --no-fix` — Expected: all checks passed (includes `modality-docs`).

- [ ] **Step 2: Try both kinds by hand**

```bash
python3 prism_tools.py modality propose examples/modality_proposal/biosample.yml --sample examples/modality_proposal/biosample_sample.tsv --out "$TMPDIR/new"
python3 prism_tools.py modality propose examples/modality_proposal/bloodpanel.yml --sample examples/modality_proposal/bloodpanel_sample.tsv --out "$TMPDIR/ext"
python3 prism_tools.py modality propose examples/modality_proposal/bloodpanel.yml --sample examples/modality_proposal/bloodpanel_sample.tsv --check
```
Expected: exit 0 each; the `new` folder has `docs/biosample.md` and `docs/snippets.md`, the `ext` folder has no schema file; read both `REGISTRATION.md` files and confirm the steps read correctly.

- [ ] **Step 3: Audit and merge**

Invoke `/ponytail:ponytail-audit` on the branch, apply what is worth it, re-run Step 1, then merge `feat/modality-naming-docs` into `main` (`--no-ff`) and push. After the merge: re-run the bot once with a new test issue using `bloodpanel.yml` to see the extension path in CI (first real run of that path).

- [ ] **Step 4: Hand over**

Report to the user: test counts, anything skipped, that the CLAUDE.md "Schema Updates Checklist" items 3-4 (`restricted_names`, `templates/index.html`) no longer exist in the repo and should be deleted from the checklist, and that closing issues #179-181 and PR #182 is still open.
