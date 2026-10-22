# Biosample term registry — phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Biosample columns can be mapped to shipped, versioned terms; the validator inherits term definitions, reports unknown metrics as a notice with similar official terms, and `prism_tools.py terms list|show|suggest` exposes the same logic.

**Architecture:** A JSON-only backend module `src/term_registry.py` loads one file per term from `official/library/terms/<modality>/` and resolves a sidecar column to a term. `app/src/validator.py` calls it in two places (the effective column definitions, and the once-per-sidecar biosample check). The CLI is a thin adapter over the same functions. No GUI work in this phase (the Validator page already shows validator issues).

**Tech Stack:** Python stdlib + `jsonschema` (already used), pytest.

**Spec:** `docs/superpowers/specs/2026-10-22-biosample-term-registry-design.md`

## Global Constraints

- Two term levels only: parent = analyte, child = analyte in one specimen (spec "Terms").
- Identity is the prefixed term ID, never the label: `prism:cortisol`, `prism:cortisol.saliva`; allowed prefixes `prism` and `bids`; local part `^[a-z][a-z0-9-]*$`, child = `<parent local>.<specimen>`; the file stem is the local part (`cortisol.saliva.json`). IDs are frozen once released: rename = change `Label`, wrong ID = deprecate with `ReplacedBy`.
- Units are UCUM strings (`nmol/L`, `ug/dL`). The validator never converts units.
- Severity table is exactly the spec's: unknown metric = `INFO`; different declared unit = `INFO`; specimen mismatch = `ERROR`; deprecated term = `WARNING` (with `ReplacedBy`); unresolvable `Term` without `Units` = `ERROR`.
- User files are never rewritten. Name similarity only suggests, never applies.
- Registry loading is JSON only: the validator image has no pandas (`validator-image-has-no-pandas`).
- Loader and notice logic never contain the word "biosample" except as the default `modality` argument; registry path is `official/library/terms/<modality>/`.
- Backend logic lives in top-level `src/` (verified: no same-named file under `app/src/`); import it as `src.term_registry`. Re-run `find src app/src -name 'term_registry.py'` before the first edit.
- TDD per repo rules: failing test first, watch it fail. Session labels and ids are exact strings, never normalized.
- Only `.json` files are added; nothing here touches git-annex rules.

## Review Focus

- **Non-analyte columns** (`sample_id`, `collection_time`, `fasting`, any column with `Units: "n/a"`) must not trigger unknown-metric notices. Pinned in Task 4.
- **Notice flood:** one notice set per sidecar, not per TSV file or row (reuse the `_biosample_warned` pattern). Pinned in Task 4.
- **Missing registry folder** (frozen build, validator image): empty registry, no crash, no notices about similar terms. Pinned in Task 1.
- **Alias collisions:** two terms claiming `cort`, or an alias equal to another term's ID, is a registry error, not a silent first-wins. Pinned in Task 2.
- **Case:** `Cort`, `CORT` and `cort` find the same alias; term IDs in `Term` are matched exactly then case-insensitively. Pinned in Task 3.
- **Parent term with no/other `SpecimenType` in the sidecar:** notice "known analyte, new specimen", never a crash. Pinned in Task 3.

---

### Task 1: Registry loader

**Files:**
- Create: `src/term_registry.py`
- Create: `tests/test_term_registry.py`

**Interfaces:**
- Produces: `DEFAULT_TERMS_ROOT: Path` (`<repo>/official/library/terms`); `load_registry(modality: str = "biosample", root: Path | None = None) -> dict[str, dict]` mapping the file stem (the local part of the `TermID`) to the parsed term dict. A missing folder returns `{}`; an unreadable or non-JSON file is skipped (the checker in Task 2 reports it).

- [ ] **Step 1: Write failing tests** in `tests/test_term_registry.py` using `tmp_path`: `test_load_registry_reads_one_file_per_term` (two files → keys equal stems, values equal parsed JSON), `test_load_registry_missing_folder_is_empty` (`load_registry(root=tmp_path / "nope") == {}`), `test_load_registry_skips_broken_json` (a `bad.json` containing `{` is absent from the result, the good file is present).
- [ ] **Step 2: Run** `pytest tests/test_term_registry.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `load_registry` in `src/term_registry.py` with `json` and `Path.glob("*.json")`; `root` defaults to `DEFAULT_TERMS_ROOT`, term folder is `root / modality`.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat(terms): load the term registry`.

### Task 2: Registry check and seed terms

**Files:**
- Modify: `src/term_registry.py`
- Create: `official/library/terms/biosample/` with `cortisol.json`, `cortisol.saliva.json`, `cortisol.serum.json`, `alpha-amylase.json`, `alpha-amylase.saliva.json`, `crp.json`, `crp.serum.json`, `il6.json`, `il6.serum.json`, `tnfa.json`, `tnfa.serum.json`
- Test: `tests/test_term_registry.py`

**Interfaces:**
- Consumes: `load_registry` (Task 1).
- Produces: `check_registry(registry: dict[str, dict]) -> list[str]` returning human-readable problems (empty list = valid). `TermID` is the full prefixed ID. Optional `Equivalents`: list of external codes such as `loinc:2143-6`. Term shape: parent `{"TermID","Level":"analyte","Label","Aliases":[...],"Description","Status"}`; child `{"TermID","Level":"analyte-specimen","Parent","SpecimenType","Units","AlternativeUnits":[...],"MinValue","Status"}`; optional `WarnMaxValue`, `LOINC` (pattern `^\d+-\d$`), `ReplacedBy` (required when `Status` is `deprecated`). `Status` is `official` or `deprecated` in the shipped registry. Problems reported: `TermID` has an unknown prefix or a local part outside the pattern; the local part of `TermID` differs from the file stem; a child ID is not `<parent local>.<SpecimenType>`; an `Equivalents` entry equals another term's ID or equivalent; child without existing parent; child `SpecimenType` outside the biosample schema's `SpecimenType` enum (read the enum from `app/schemas/stable/biosample.schema.json`, do not copy it); `ReplacedBy` missing or dangling; alias that equals another term's ID or another term's alias (case-insensitive); child `Units` missing.

- [ ] **Step 1: Write failing tests**: `test_shipped_registry_is_valid` (`check_registry(load_registry()) == []` and the seed IDs above are all present); `test_check_registry_flags_orphan_child`; `test_check_registry_flags_alias_collision` (two parents both listing `Cort`); `test_check_registry_flags_bad_specimen`; `test_check_registry_flags_deprecated_without_replacedby`; `test_check_registry_flags_id_not_matching_filename`; `test_check_registry_flags_bad_id_format` (uppercase local part, unknown prefix `foo:`, child ID not matching parent and specimen).
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** `check_registry`. **Create the seed terms**: take units, `MinValue`, `WarnMaxValue` and `LOINC` for `crp`, `il6`, `tnfa` from `official/library/biosample/biosample-inflammation.json` (do not retype them). Cortisol: saliva `Units` `nmol/L`, `AlternativeUnits` `["ug/dL"]`; serum same. Alpha-amylase saliva `U/mL`. Cortisol/amylase get `MinValue: 0` and **no** `WarnMaxValue` or `LOINC` (maintainers add clinical ranges and codes at review; do not invent them). Parent aliases: cortisol `["cort","corts","hydrocortisone"]`; others none.
- [ ] **Step 4: Run** `pytest tests/test_term_registry.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(terms): registry check and seed terms`.

### Task 3: Resolving a sidecar column

**Files:**
- Modify: `src/term_registry.py`
- Test: `tests/test_term_registry.py`

**Interfaces:**
- Consumes: registry dict from `load_registry`.
- Produces: `@dataclass(frozen=True) class Resolution` with `kind: str` (one of `"term"`, `"specimen_mismatch"`, `"known_analyte_new_specimen"`, `"suggestion"`, `"deprecated"`, `"unknown"`), `term: dict | None` (the resolved child, or the parent when no child exists), `similar: tuple[str, ...]` (similar official term IDs), `message: str`. And `resolve_column(registry: dict[str, dict], column: str, col_def: dict, specimen: str | None) -> Resolution`.

Rules (spec "How a sidecar column refers to a term"), in order:
1. `col_def["Term"]` names a child: equal `specimen` → `"term"`; different → `"specimen_mismatch"`.
2. `Term` names a parent: the child with that `Parent` and `SpecimenType == specimen` → `"term"`; none → `"known_analyte_new_specimen"` (also when `specimen` is `None`).
3. No `Term` (or `Term` not in the registry): if `column` equals, case-insensitively, a term ID, local slug, label, alias or equivalent → `"suggestion"` with `similar` = that term's ID; else `"unknown"` with `similar` = IDs whose label/alias contains the column name or vice versa (case-insensitive, substring only; no edit distance).
4. A matched term with `Status == "deprecated"` → `"deprecated"` (message names `ReplacedBy`), checked before rules 1-3 return `"term"`.
`Term` and column-name matching: exact full ID, then the bare local slug (so `Term: cortisol` finds `prism:cortisol`), then label, alias and `Equivalents`, each case-insensitive.

- [ ] **Step 1: Write failing tests** against a small in-test registry: `test_term_parent_resolves_to_specimen_child`, `test_term_child_specimen_mismatch`, `test_parent_without_matching_child_is_known_analyte_new_specimen`, `test_parent_with_no_specimen_does_not_crash`, `test_alias_suggests_not_applies` (`cort` → kind `"suggestion"`, `similar == ("prism:cortisol",)`), `test_alias_match_is_case_insensitive` (`CORT`, `Cort`), `test_term_resolves_by_bare_slug_and_equivalent` (`Term: cortisol` and `Term: loinc:2143-6` both reach the same child), `test_unknown_lists_similar` (`salivary_cortisol` → kind `"unknown"`, `"prism:cortisol" in similar`), `test_unknown_with_nothing_similar_has_empty_similar`, `test_deprecated_term_points_to_replacement`.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** `Resolution` and `resolve_column` per the rules above.
- [ ] **Step 4: Run** `pytest tests/test_term_registry.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(terms): resolve sidecar columns to terms`.

### Task 4: Validator integration

**Files:**
- Modify: `app/schemas/stable/biosample.schema.json`; `app/src/validator.py` (`_build_effective_defs`, `_check_biosample_sidecar`, the `validate_data_content` call site at ~L959); `docs/specs/biosample.md` (regenerate the schema reference block with `scripts/generate_schema_reference.py`)
- Create: `tests/test_validator_biosample_terms.py`

**Interfaces:**
- Consumes: `load_registry`, `resolve_column`, `Resolution` (Tasks 1, 3). Load the registry once per `DatasetValidator` instance (attribute set in `__init__` next to `_biosample_warned`).
- Produces: biosample columns may be `{"Term": "<ID or label>"}` with `Description` and `Units` optional; `Units`, `DataType`, `MinValue`, `WarnMaxValue`, `LOINC` are inherited from the resolved child unless the column sets them (column wins).

- [ ] **Step 1: Write failing tests** in the style of `tests/test_validator_biosample_sidecar.py` (`_template`, `_write`, `_msgs` helpers; copy their shape, do not import across test files):
  - `test_schema_accepts_term_only_column`: `{"cort": {"Term": "cortisol"}}` passes the sidecar schema; a column with neither `Term` nor (`Description` and `Units`) still fails.
  - `test_term_column_inherits_min_value`: TSV value `-1` in a `Term: cortisol` column with `SpecimenType: saliva` gives an ERROR containing `less than MinValue`.
  - `test_sidecar_value_overrides_term_default`: column sets `MinValue: -5`, `-1` passes.
  - `test_unknown_metric_is_info_with_similar_terms`: a fully defined column `salivary_cortisol` gives one `INFO` whose text contains `not an official metric` and `cortisol`.
  - `test_unknown_notice_once_per_sidecar`: three TSVs sharing one root sidecar → the notice appears once.
  - `test_non_analyte_columns_get_no_notice`: `sample_id` / `collection_time` with `Units: "n/a"` and `fasting` produce no INFO.
  - `test_specimen_mismatch_is_error`: `Term: cortisol.serum` with `SpecimenType: saliva` → ERROR.
  - `test_declared_other_unit_is_info_only`: `Term: cortisol`, `Units: "ug/dL"` → INFO, no WARNING or ERROR.
  - `test_unresolvable_term_without_units_is_error`: `Term: nonsense` and no `Units` → ERROR mentioning the term.
  - `test_deprecated_term_warns_with_replacement`: patch the validator's registry with a deprecated term.
  - `test_empty_registry_does_not_break_validation`: validator built with an empty registry validates a plain sidecar unchanged.
  - `test_existing_inflammation_template_unchanged`: the shipped example sidecar still returns no issues (no regression).
- [ ] **Step 2: Run** `pytest tests/test_validator_biosample_terms.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** (a) schema: add the `Term` property (string) and change the column `required` to `anyOf: [{required: [Description, Units]}, {required: [Term]}]`; bump the biosample schema `version` and `$id` as an additive minor change following `docs/SCHEMA_VERSIONING.md` (read it first). (b) `_build_effective_defs`: after the existing alias passes, for biosample sidecars merge inherited term fields into each column that resolves to kind `"term"`, column keys win. (c) `_check_biosample_sidecar`: once per sidecar (`_biosample_warned`), iterate the column entries (skip `Technical`/`Study`/`Metadata`, skip `Units == "n/a"`, skip `sample_id`, `collection_time`, `fasting`) and emit the issues by the Global Constraints severity list; message wording starts "`<column>` is not an official metric" and ends with the share hint "the PRISM maintainers may choose a different name; your files keep working through an alias". Pass the sidecar's `Technical.SpecimenType` into `resolve_column`.
- [ ] **Step 4: Run** the new file plus `pytest tests/test_validator_biosample_sidecar.py tests/test_validator_biosample_content.py tests/test_biosample_schema.py tests/test_biosample_end_to_end.py -v`. Expected: all PASS. Re-run the docs generator and confirm `git diff docs/specs/biosample.md` only touches the generated block.
- [ ] **Step 5: Commit** `feat(terms): validator inherits term definitions and reports unknown metrics`.

### Task 5: Command line

**Files:**
- Create: `app/src/cli/commands/terms.py`
- Modify: `app/src/cli/parser.py` (a `terms` subparser next to `modality`, ~L1755), `app/src/cli/dispatch.py` (route `terms`), `app/src/cli/entrypoint.py` (register handlers)
- Test: `tests/test_cli_terms.py`

**Interfaces:**
- Consumes: `load_registry`, `resolve_column` (Tasks 1, 3). Command modules must not import other command modules or CLI wiring (`tests/test_cli_command_import_boundaries.py`).
- Produces: `prism_tools.py terms list [--modality biosample] [--json]`, `terms show <TermID> [--json]` (unknown ID: message and exit code 1), `terms suggest <column> [--specimen saliva] [--json]` (prints the `Resolution` kind and similar IDs). Handlers `cmd_terms_list`, `cmd_terms_show`, `cmd_terms_suggest`. `--json` output shape: `{"success": bool, ...}` like `modality propose`.

- [ ] **Step 1: Write failing tests** running the real entry point with `subprocess` as `tests/test_biosample_end_to_end.py` does: `test_terms_list_shows_seed_terms` (stdout contains `cortisol.saliva`), `test_terms_show_unknown_id_exits_1`, `test_terms_suggest_cort_points_to_cortisol` (`--json`, `similar == ["prism:cortisol"]`, kind `suggestion`), `test_terms_suggest_unknown_column`. The existing boundary and dispatch tests must still pass.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** the three handlers, parser entries and dispatch route, copying the `modality propose` wiring pattern (parser, `dispatch.py` branch, `entrypoint.py` handler dict).
- [ ] **Step 4: Run** `pytest tests/test_cli_terms.py tests/test_cli_command_import_boundaries.py tests/test_cli_dispatch_routing.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(terms): terms list, show and suggest commands`.

### Task 6: Docs, changelog, repo checks

**Files:**
- Modify: `docs/specs/biosample.md` (hand-written part: a "Terms" section covering `Term`, inheritance, the notice and the alias promise), `CHANGELOG.md` (Added), `docs/CLI_REFERENCE.md` (the `terms` commands)
- Test: `tests/test_verify_repo_modality_docs.py` and the dual-tree check must pass.

- [ ] **Step 1: Write the doc sections** (no test; wording follows the spec's sharing-flow text, and states that sharing a term is phase 2 and not yet available).
- [ ] **Step 2: Run** `python tests/verify_repo.py --check dual-tree-drift --no-fix`, `pytest tests/test_verify_repo_modality_docs.py tests/test_repo_symlinks.py tests/test_no_compat_shims.py -v`, then the biosample and terms test files once more. Expected: PASS.
- [ ] **Step 3: Run `/ponytail:ponytail-audit`** on the branch (repo rule before merging), apply what is worth it, re-run the tests, and only then ask whether to merge.
- [ ] **Step 4: Commit** `docs(terms): spec section, CLI reference, changelog`.

## Not in this phase

Proposal builder and the share button (phase 2), converter and Template Editor use of terms (phase 3), unit conversion (phase 4), a second modality. Clinical ranges and LOINC codes for cortisol and amylase are left to maintainer review.
