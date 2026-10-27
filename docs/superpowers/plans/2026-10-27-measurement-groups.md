# Measurement groups on the Propose page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** The Propose page's measurement list is clustered (group first, then the variable), shows short labels, and never overflows its card; the groups are part of the specification (an optional `Group` on every term).

**Architecture:** prism-specification gets an optional term field `Group` (+ the 31 environment terms grouped), released as v1.4.1 together with two approved follow-ups (`check_modalities.py --terms`, "a `count` window column is unitless" in the environment schema 2.1.0). Studio syncs the tag; `spec_catalog()` metrics carry `group`; the page shows a group pull-down, then the measurements of that group (`label (unit)` only; id and level codes in a line under the choice); proposals can carry a group.

**Tech Stack:** Python 3, JSON Schema, vanilla JS, pytest, Playwright e2e.

**User decision (2026-10-27):** groups come from the specification (term files), not a Studio-only table. Complaint: the select spilled out of its card (`w-auto` = as wide as the longest option, the moon-phase level list) and the lines were too long.

## Global Constraints
- Both repos' CLAUDE.md apply (TDD, one implementation: CLI = backend, GUI thin adapter; vendored spec never hand-edited in Studio; spec change = spec repo first, tag, then `scripts/sync_specification.py --tag`).
- Spec: the environment groups, verbatim (6 groups, every one of the 31 environment terms in exactly one):
  - `Temperature and humidity`: air-temperature, apparent-temperature, dew-point-temperature, relative-humidity, heat-status
  - `Wind, pressure and rain`: surface-air-pressure, wind-speed, precipitation, cloud-cover, weather-regime
  - `Sun and light`: shortwave-radiation, uv-index, daylight-duration, hours-since-daylight, sun-phase
  - `Air quality`: european-aqi, pm25, pm10, nitrogen-dioxide, ozone
  - `Pollen`: pollen-birch, pollen-grass, pollen-mugwort, pollen-ragweed, pollen-total, pollen-risk
  - `Place and time`: elevation, season, time-of-day, moon-phase, moon-illumination
- `Group` is optional for every term (biosample has none; its list stays one list), a string of 1-60 characters without newline; proposals may carry it (the maintainer can change it).
- Biosample behaviour unchanged. A kind whose metrics carry no `group` shows one flat list, as today.
- Page option text: `label (unit)` or just `label` for a levels term; id, unit and level codes appear after the choice in a detail line. No select may be wider than its card (`w-100`, no `w-auto`).
- JS: DOM text via textContent; no kind names or group names in JS (groups come from the catalog).
- `count` window columns are unitless (`Units "1"`; already done in Studio): the spec states it.

## Review Focus
1. A term with `Group` of the wrong type, empty, over 60 characters or with a newline → problem (spec `check_terms`).
2. A proposal term with `Group` passes `term_proposal` (ALLOWED_FIELDS) and the `Group` reaches the bundle file.
3. `check_modalities.py --terms DIR` checks that folder; default stays REPO/terms.
4. Page: kind without groups (biosample) → flat list as before; kind with groups → group select first; "Missing: add a measurement…" reachable without choosing a group.
5. Choosing another group/kind clears the previous measurement and the detail line; no stale id.

---

### Task 1: Specification v1.4.1 (repo prism-specification, worktree `../prism-specification-groups`, branch `feat/term-groups`)

**Files:** `scripts/check_terms.py` (`Group` type/length rule in `type_problems` or `check_registry`), `scripts/term_proposal.py` (ALLOWED_FIELDS += Group), `scripts/check_modalities.py` (`--terms DIR`), `terms/environment/*.json` (add `Group`), `schemas/stable/environment.schema.json` → 2.1.0 (Statistic description: a `count` is a number of hours, unitless, `Units "1"`), `schemas/archive/environment/2.0.0.schema.json` (byte copy of the previous stable), `specs/environment.md` (prose sentence; regenerate the table), `CONTRIBUTING.md` (one line: optional `Group`), tests.

**Interfaces:** Produces term field `Group` (str, optional). `check_modalities.main(argv)` accepts `--terms DIR` (default `REPO/terms`) and passes it to `check(entities, schema_dir, terms_dir)`.

- [ ] **Step 1: Failing tests:** `test_group_type_and_length` (non-string, "", 61 chars, newline → problems; "Pollen" ok); `test_group_is_allowed_in_proposals` (a v2 environment proposal term with `Group` → ok and present in the bundle file); `test_every_environment_term_has_one_of_the_six_groups` (exact group → ids table above, all 31 covered); `test_check_modalities_terms_option` (tmp repo copy with a missing declaration folder: `main(["--terms", dir])` reports it; default unchanged); `test_environment_schema_2_1_0` (version, `$id`, Statistic description mentions "unitless" / `1`).
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** implement; add `Group` to the 31 term files; schema 2.1.0 with archive copy; regenerate `specs/environment.md` (`python scripts/generate_schema_reference.py`); CONTRIBUTING line.
- [ ] **Step 4:** `python3 -m pytest -q && python3 scripts/check_terms.py --all && python3 scripts/check_modalities.py && python3 scripts/generate_schema_reference.py --check && python3 scripts/check_schema_versions.py origin/main HEAD` all pass.
- [ ] **Step 5:** commit. Then STOP for review; merge/tag v1.4.1/push/release only after the user's go.

### Task 2: Studio backend and CLI (branch `feat/measurement-groups`, after v1.4.1 is released)

**Files:** sync (`python scripts/sync_specification.py --tag v1.4.1`), `src/spec_contribute.py` (`spec_catalog` metrics get `"group": term.get("Group")`; `proposal_for_new_metric(..., group: str | None = None)` puts `Group` on the term when given, validated with the same rule), `app/src/cli/parser.py` + `app/src/cli/commands/spec.py` (`--group`), `app/src/web/blueprints/specification_contribute.py` (route passes `group`), tests (`tests/test_spec_contribute.py`, `tests/test_cli_spec.py`, route test), updated expectations of the sync.

**Interfaces:** catalog metric = `{"id", "label", "units", "levels"?, "specimens", "group"}` (`group` None when the term has none). Produces `groups` per kind: ordered unique list of the metrics' groups (`kind["groups"]`, `[]` when none).

- [ ] **Step 1: Failing tests:** `test_catalog_metrics_carry_group_and_kind_lists_groups` (environment: 6 groups, each metric's group); `test_biosample_has_no_groups`; `test_new_metric_with_group` (environment proposal with `group="Air quality"` → the term has `Group`, passes the vendored check); `test_group_refused_when_invalid`; `test_cli_propose_metric_group`.
- [ ] **Step 2:** run → FAIL. **Step 3:** sync, implement. **Step 4:** targeted tests (`-k "spec_contribute or cli_spec or term or specification"`) pass. **Step 5:** commit.

### Task 3: Page (`app/templates/specifications_contribute.html`, `app/static/js/modules/specification/contribute.js`, CSS if needed, e2e)

**Interfaces:** consumes the catalog's `kind.groups` and `metric.group`.

- [ ] **Step 1: Failing e2e tests** in `tests/e2e/test_specification_contribute_flows.py` (environment kind): (a) a group pull-down exists with the 6 groups; the measurement pull-down is disabled until a group is chosen; after choosing "Air quality" it lists only its 5 measurements, each option text is `label (unit)` (no `prism:` id, no level codes); (b) after choosing a measurement the detail line shows its id (and unit or level codes); (c) neither select is wider than its card (compare bounding boxes); (d) "Not in the list: add a measurement…" in the group pull-down opens the missing-measurement form; (e) switching kind clears group, measurement and detail line; (f) biosample: no group pull-down, flat list as before; (g) the missing-measurement form has an optional Group pull-down (the kind's groups + "Not sure") whose value goes into the proposal. Capture each RED run.
- [ ] **Step 2:** run → FAIL. **Step 3:** implement (group select above `#spec-m-pick`; `w-100` instead of `w-auto` on both; `fillPick` filters by group; short labels; detail line element; form group select sends `group`). **Step 4:** run the e2e file and the route tests. **Step 5:** commit.

### Task 4: Docs, CHANGELOG, final review, audit
- [ ] CHANGELOG (Added: groups, `--group`; Fixed: pull-down no longer overflows), docs (CLI reference `--group`, Propose page text), final review, ponytail audit, ask before merge.
