# Reasoning foundation, step B: the shared meaning block in every modality schema

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every prism modality schema (survey, biometrics, biosample, environment, events, physio) can carry the same optional meaning fields (`IsAbout` with relation, direction, source, check date and status; `LevelIsAbout`; `ValueMappings`; the object form of `TermURL`), defined once and added by a script, with a check that fails when a modality lacks them.

**Architecture:** One source file holds the block; a second names, per modality, where its column and file definitions are. A script in prism-specification reads both and edits each latest stable schema **in place as text** (the schema files are hand-formatted, a re-dump would rewrite most lines), reusing the release procedure of `scripts/release_patch.py` (archive the old schema unchanged, bump the minor version and `$id`, regenerate the spec page tables). `check_modalities.py` runs the same logic in check mode. Studio then syncs the tag.

**Tech Stack:** Python 3 stdlib plus `jsonschema` (already used by the repository's tests), JSON Schema draft 7. Repositories: prism-specification (Tasks 1 to 6), prism-studio (Task 7).

**Spec:** `docs/superpowers/specs/2026-11-14-reasoning-foundation-design.md` (sections 2 "The meaning block", 5 "Versioning rule", 6 "Rollout: B", and "Calls made after the builder check" items 1, 4, 5, 6, 9, 10). Steps C to G are separate plans.

## Global Constraints

- "Within a major version a schema only adds optional things." Nothing in this plan removes or tightens anything; no existing file becomes invalid.
- The block is "defined once in prism-specification and added to every modality schema by a generator, with a test that fails when a modality lacks it."
- "Only the latest stable schema of each modality. Archived schemas are frozen by rule and are never modified. BIDS passthrough data (MRI, EEG and others) does not get the block: BIDS owns those names."
- "Each modality schema that gains the block gets a minor bump of its own `version` (as CONTRIBUTING.md requires for an added optional field); the specification repository gets a patch tag per release (v1.5.x)." The tag is created only after the user confirms.
- `TermURL`: "`oneOf` in the schema: a string (the BIDS reading, a definition URL) or an object `{system: URL}`. The system is never guessed from the URL."
- `Match` follows the SKOS mapping vocabulary (exact, broader, narrower, related); `Higher` is `more` or `less`; `Status` is `reviewed` or `unreviewed`; `Checked` is a date.
- "The value level exists only where a variable has enumerated values (`Levels`)." No new structure is added to schemas without `Levels`.
- "The template-slimming releases (removing `Subscales`, `ItemCount`, `Reversed` from the survey schema) go first; the meaning block for the survey schema follows." Survey is done in Task 6, after prism-specification PR #32 (schema 2.2.0) is merged.
- Stable schema files are edited in place so the diff shows only the new version, the new `$id` and the additions (CONTRIBUTING.md); `python scripts/check_schema_versions.py origin/main HEAD` and `python scripts/generate_schema_reference.py --check` must pass.
- The vendored specification is never edited in prism-studio: release here, tag, then `python scripts/sync_specification.py --tag <tag>`.
- Stdlib-only for the scripts (they are vendored into Studio's `scripts/specification/`). TDD for every task.

## Review Focus

1. **Existing documents stay valid.** Every document that validated against a modality schema before the release validates after it (Task 5 test over the repository's own fixtures and examples).
2. **No clobbering.** A column definition that already has `IsAbout`, `LevelIsAbout` or `ValueMappings` with a different definition makes the script refuse (Task 2); `TermURL` is replaced only when the existing definition is a plain string type (optionally with `format`), and a stricter existing definition (a `pattern`, an `enum`, a length) is a refusal.
3. **Idempotent.** Running the release twice never produces a second bump or a duplicate property; the check passes on an already stamped schema (Task 2, Task 3).
4. **Only where it belongs.** `LevelIsAbout` is added only to column definitions that have `Levels`; BIDS passthrough modalities and non-modality schemas (`entities`, `dataset_description`) are never touched (Task 2, Task 3).
5. **Frozen archives.** The archived copy is byte-identical to the previous stable file and the previous version is archived exactly once (Task 5, `check_schema_versions.py`).

## File Structure

prism-specification:
- Create `schemas/shared/meaning-block.json`: the block (the only definition).
- Create `schemas/shared/meaning-locations.json`: per modality, where its column and file definitions are, plus a `pending` map of modalities not yet stamped, each with its reason.
- Create `scripts/meaning_block.py`: load the two files, stamp one schema text, check, release one modality.
- Modify `scripts/release_patch.py`: `_span` also accepts array indices.
- Modify `scripts/check_modalities.py`: the meaning-block rule.
- Modify the five (later six) `schemas/stable/*.schema.json`, add `schemas/archive/<modality>/<old>.schema.json`, regenerate `specs/<modality>.md`.
- Create `specs/meaning.md`; modify `CONTRIBUTING.md`.
- Tests: `tests/test_meaning_block.py` (new), `tests/test_release_patch.py` (extended, or the file that already tests `release_patch`; find it), `tests/test_check_modalities.py` (extended).

prism-studio (Task 7): vendored copy via the sync script, pins, any reader of schemas that the new fields confuse.

## The block (pinned; the implementer writes it into `schemas/shared/meaning-block.json` exactly)

```json
{
  "version": "1.0.0",
  "link": {
    "type": "array",
    "minItems": 1,
    "description": "What this is about: one or more concepts, each with how close the match is and which way a higher value points.",
    "items": {
      "type": "object",
      "required": ["Concept"],
      "additionalProperties": false,
      "properties": {
        "Concept": {"type": "string", "pattern": "^(prism:[a-z][a-z0-9.-]*|https?://\\S+)$", "description": "A PRISM concept ID (prism:<slug>) or the absolute URL of a concept in an external vocabulary."},
        "Match": {"type": "string", "enum": ["exact", "broader", "narrower", "related"], "description": "How closely the concept matches (SKOS: exactMatch, broadMatch, narrowMatch, relatedMatch). Default: exact."},
        "Higher": {"type": "string", "enum": ["more", "less"], "description": "Whether a higher value means more or less of the concept."},
        "Source": {"type": "string", "minLength": 1, "description": "Who or what made the link (a person, a paper, a tool)."},
        "Checked": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$", "description": "Date the link was last checked (YYYY-MM-DD)."},
        "Status": {"type": "string", "enum": ["reviewed", "unreviewed"], "description": "Default: unreviewed."}
      }
    }
  },
  "column": {
    "IsAbout": "<link>",
    "LevelIsAbout": {"type": "object", "description": "Concept links for single values, keyed by the level code of Levels.", "additionalProperties": "<link>"},
    "ValueMappings": {
      "type": "array", "minItems": 1,
      "description": "Named, sourced rules that turn a value into a state a reasoner can use. Several may exist and may disagree; none is the truth.",
      "items": {"type": "object", "required": ["Name", "Rules"], "additionalProperties": false, "properties": {
        "Name": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
        "Source": {"type": "string", "minLength": 1},
        "Rules": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["When", "State"], "additionalProperties": false, "properties": {
          "When": {"type": "object", "required": ["Op", "Value"], "additionalProperties": false, "properties": {
            "Op": {"type": "string", "enum": ["==", "!=", ">=", ">", "<=", "<", "in"]},
            "Value": {"type": ["number", "string", "array"]}}},
          "State": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$", "description": "For example present, absent, high, low."}}}}}}
    },
    "TermURL": {
      "type": ["string", "object"],
      "description": "A string is a URL of a definition (the BIDS reading). An object maps a vocabulary name to the URL of this same thing in that vocabulary.",
      "additionalProperties": {"type": "string", "pattern": "^https?://\\S+$"}
    }
  },
  "file": {"IsAbout": "<link>"}
}
```

`"<link>"` means: the `link` definition above, written out in full where it is used (no `$ref`: no stable schema uses `$ref`, and Studio's schema readers walk `properties` directly). The script does that expansion.

`schemas/shared/meaning-locations.json` (pinned shape; paths are JSON key lists to the schema object whose `properties` receives the fields, integers index arrays):

```json
{
  "modalities": {
    "biometrics":  {"column": [["additionalProperties"]], "file": [["properties", "Study"]]},
    "biosample":   {"column": [["additionalProperties"]], "file": [["properties", "Study"]]},
    "environment": {"column": [["additionalProperties"]], "file": [["properties", "Study"]]},
    "events":      {"column": [["additionalProperties"], ["properties", "trial_type"], ["properties", "onset"], ["properties", "duration"], ["properties", "response_time"], ["properties", "stim_file"]],
                    "file": []},
    "physio":      {"column": [["properties", "Channels", "additionalProperties"]], "file": [["properties", "Recording"]]}
  },
  "pending": {"survey": "waits for the slim-survey release (prism-specification PR #32, schema 2.2.0); its column location is ['additionalProperties', 'oneOf', 0] and its file location ['properties', 'Study']"}
}
```

---

### Task 1: `release_patch._span` accepts array indices

**Files:**
- Modify: `scripts/release_patch.py` (`_span`, and `_member` if needed)
- Test: the existing release_patch test file (find it: `grep -ln release_patch tests/*.py`)

**Interfaces:**
- Produces: `_span(text: str, keys: list[str | int]) -> tuple[int, int]`; an `int` key selects the n-th element of an array value; `_extend_object(text, keys, properties)` therefore works for `["additionalProperties", "oneOf", 0, "properties"]`. Needed by Task 6 (survey's item definition is `oneOf[0]`); the five modalities of Task 5 do not need it, so this task can be done after them if the schedule requires.

- [ ] **Step 1: Write the failing test.** A small JSON text with an array of objects (`{"a": {"oneOf": [{"properties": {"X": {}}}, {"properties": {}}]}}`, hand-formatted with 2-space indentation and one compact line) and `_extend_object(text, ["a", "oneOf", 0, "properties"], {"Y": {"type": "string"}})`: the result parses, equals the original plus `Y` in element 0 only, and every other line of the text is byte-identical.
- [ ] **Step 2: Run it** (`python -m pytest tests -k release_patch -q`). Expected: FAIL (`_member` raises on a non-string key or `ValueError: not an object`).
- [ ] **Step 3: Implement** the array-index step in `_span` (find the n-th element's span with the existing `_skip` and `_end_of_value`); string keys behave as before.
- [ ] **Step 4: Run** the release_patch tests. Expected: PASS, including the existing ones.
- [ ] **Step 5: Commit** `feat(release): _span can step into array elements`.

### Task 2: The block, the locations and the stamping logic

**Files:**
- Create: `schemas/shared/meaning-block.json`, `schemas/shared/meaning-locations.json` (contents above, verbatim)
- Create: `scripts/meaning_block.py`
- Test: `tests/test_meaning_block.py` (new)

**Interfaces:**
- Consumes: `release_patch._extend_object`, `_replace_value`, `_span` (import the sibling script the way `release_patch.py` imports its siblings, by path).
- Produces (in `scripts/meaning_block.py`):
  - `load_block(shared_dir: Path) -> dict`, `load_locations(shared_dir: Path) -> dict`
  - `stamp(text: str, modality: str, block: dict, locations: dict) -> tuple[str, list[str]]`: the schema text with the missing block properties added at every location of `modality` (column fields at column locations, `IsAbout` at file locations), and the list of problems (empty when fine). Rules: add only properties that are absent; `LevelIsAbout` only where the location's `properties` has `Levels`; `TermURL` replaced only when the existing definition has `type == "string"` and no keys other than `type`, `description` and `format` (events and physio say `"format": "uri"`; the block's definition has no `format`, which only loosens: a JSON Schema validator ignores `format` unless a format checker is switched on) and then it takes the block's definition; a present property whose definition equals the block's is left alone; any other present property with a different definition is a problem, and nothing is changed. Idempotent.
  - `missing(text: str, modality: str, block: dict, locations: dict) -> list[str]`: one line per block property that `stamp` would still add (empty means the schema carries the block).
  - `release(source_root, dest_root, modality: str) -> list[str]`: like `release_patch.release`: archives `schemas/archive/<modality>/<old>.schema.json` unchanged, edits the stable text with `stamp`, bumps the MINOR version and the `$id`, regenerates `specs/<modality>.md` through `generate_schema_reference`; refuses when nothing is missing, when the version is not major.minor.patch, or when the archive exists; returns the paths written.

- [ ] **Step 1: Write the failing tests** in `tests/test_meaning_block.py`. Use small synthetic schema texts (hand-formatted, with a column definition that has `Levels` and one that has not, a `Study` object, and an existing plain-string `TermURL`) and the real block and locations files:

```python
def test_stamp_adds_the_block_at_column_and_file_locations_and_nothing_else_changes():
    new, problems = stamp(SYNTH, "demo", BLOCK, LOCATIONS)
    assert problems == []
    doc = json.loads(new)
    col = doc["additionalProperties"]["properties"]
    assert {"IsAbout", "LevelIsAbout", "ValueMappings", "TermURL"} <= set(col)
    assert "IsAbout" in doc["properties"]["Study"]["properties"]
    assert col["IsAbout"]["items"]["required"] == ["Concept"]
    # every original line is still there (the diff is additions only, plus the TermURL replacement)
    assert set(SYNTH.splitlines()) - set(new.splitlines()) <= TERMURL_OLD_LINES

def test_level_is_about_only_where_levels_exist(): ...      # a column location without Levels gets no LevelIsAbout
def test_stamp_is_idempotent_and_missing_is_empty_afterwards():
    once, _ = stamp(SYNTH, "demo", BLOCK, LOCATIONS)
    twice, _ = stamp(once, "demo", BLOCK, LOCATIONS)
    assert once == twice and missing(once, "demo", BLOCK, LOCATIONS) == []
def test_a_conflicting_existing_property_is_a_problem_and_changes_nothing():
    text = SYNTH_WITH_OWN_ISABOUT   # IsAbout declared as {"type": "string"}
    new, problems = stamp(text, "demo", BLOCK, LOCATIONS)
    assert new == text and any("IsAbout" in p for p in problems)
def test_a_stricter_termurl_is_a_problem():
    text = SYNTH_WITH_PATTERNED_TERMURL   # type string plus a pattern
    ...                                    # problems mention TermURL; text unchanged
def test_a_plain_string_termurl_is_replaced_by_the_one_of_form():
    ...                                    # old string documents still validate with jsonschema; an object value now validates too;
                                           # parametrize the old definition: {type,description} and {type,format:uri} (events/physio)
def test_the_repository_block_and_locations_are_consistent():
    # every modality of locations['modalities'] and 'pending' is a prism modality of entities.schema.json;
    # no passthrough modality appears; each location path resolves in the schema's JSON
def test_the_block_itself_is_a_valid_draft7_schema_fragment(): ...   # Draft7Validator.check_schema on each expanded property
def test_release_archives_bumps_and_regenerates(tmp_path):
    # copy the repository's schemas/ specs/ scripts/ into tmp_path, release 'biosample' there:
    # archive == old stable bytes, stable version minor+1 and $id suffix match, 'missing' is empty, rerun refuses
```
  (Fill the elided tests the same way; each asserts exactly what its name says. Build `SYNTH` once at the top of the file.)
- [ ] **Step 2: Run to verify they fail.** Run: `python -m pytest tests/test_meaning_block.py -q`. Expected: FAIL (`meaning_block` does not exist, shared files missing).
- [ ] **Step 3: Implement** `scripts/meaning_block.py` and write the two shared JSON files exactly as pinned above. Approach: expand `"<link>"` placeholders; for each location compute the key path `keys + ["properties"]` and call `_extend_object` with the missing properties; `TermURL` replacement through `_replace_value` on its span; `json.loads` the result and compare it to the in-memory expected schema, falling back to refusing (not to a full rewrite) if the text edit cannot be done exactly: a full rewrite would hide the reviewable diff.
- [ ] **Step 4: Run to verify they pass.** Run: `python -m pytest tests/test_meaning_block.py tests -k "release_patch or meaning" -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(meaning): the shared meaning block, its locations and the stamping logic`.

### Task 3: The command and the check

**Files:**
- Modify: `scripts/meaning_block.py` (add `main(argv)` and the `__main__` hook)
- Modify: `scripts/check_modalities.py`
- Test: `tests/test_meaning_block.py` (CLI), `tests/test_check_modalities.py` (rule)

**Interfaces:**
- Produces: `python scripts/meaning_block.py check` (prints one line per modality that lacks the block or is not registered; exit 1 when there is any); `python scripts/meaning_block.py release --modality <name> [--dest DIR]` (calls `release`; prints the written paths). `check_modalities.check(entities, schema_dir, terms_dir=None, shared_dir=None)` gains the rule: every prism modality in `entities` is either in `locations["modalities"]` with `missing(...) == []`, or in `locations["pending"]`; a modality in neither is a problem ("register the new modality in schemas/shared/meaning-locations.json and run meaning_block.py release"); a `pending` entry whose modality does not exist is a problem; a passthrough modality in the locations is a problem.

- [ ] **Step 1: Write the failing tests:** `test_check_reports_a_modality_without_the_block` (a tmp copy of the schemas with one modality unstamped and not pending: the problem names it and the fix); `test_check_accepts_a_pending_modality`; `test_check_rejects_an_unregistered_new_modality` (add a fake prism modality to a copy of `entities`); `test_the_repository_passes` already exists and must keep passing; `test_cli_check_exit_code`.
- [ ] **Step 2: Run to verify they fail.** Run: `python -m pytest tests/test_check_modalities.py tests/test_meaning_block.py -q`. Expected: the new tests FAIL; note that `test_the_repository_passes` will FAIL too until Task 5 stamps the schemas: that is expected, and the reason Task 3's commit must not be merged alone (see the ruling below).
- [ ] **Step 3: Implement** the CLI and the rule.
- [ ] **Step 4: Run to verify the new tests pass** (the repository test stays red until Task 5).
- [ ] **Step 5: Commit** `feat(meaning): meaning_block.py check/release and the modality check rule`.

**Ruling for the executor:** Tasks 1 to 5 land together in one pull request (the repository check is red between Task 3 and Task 5 by design); the pull request is not merged until Task 5's stamped schemas are in it.

### Task 4: The page and the rules in CONTRIBUTING

**Files:**
- Create: `specs/meaning.md`
- Modify: `CONTRIBUTING.md` ("Changing a schema" and "Proposing a new kind of data")
- Test: `tests/test_meaning_block.py` (the page lists every field of the block)

- [ ] **Step 1: Write the failing test** `test_the_meaning_page_documents_every_block_field`: for each key of `block["column"]` and `block["file"]` and each property of the link items, the text of `specs/meaning.md` contains the name in backticks.
- [ ] **Step 2: Run** it. Expected: FAIL (page missing).
- [ ] **Step 3: Write `specs/meaning.md`** in plain words: what the block is for (one paragraph: facts for any reasoner, not a reasoner); a table of the fields with the pinned descriptions; the `Match` words and their SKOS meaning; `Higher` (relative to a concept); `ValueMappings` (named, sourced, several allowed, none is the truth); `TermURL` (string versus object, no guessing); the three data states as a statement of intent ("missing is not no", the projection comes in a later step); where the block appears (file level, column level, value level only with `Levels`); and that BIDS passthrough data is out. In `CONTRIBUTING.md`, "Changing a schema": add the rule "Within a major version a schema only adds optional things; a file written against an older minor version stays valid"; and a short "Adding the meaning block": a new modality is registered in `schemas/shared/meaning-locations.json` and stamped with `python scripts/meaning_block.py release --modality <name>`; `python scripts/check_modalities.py` fails otherwise. In "Proposing a new kind of data": one sentence that the maintainer stamps the block when building the schema (the proposal form itself is step G).
- [ ] **Step 4: Run** the test and `python scripts/generate_schema_reference.py --check`. Expected: PASS.
- [ ] **Step 5: Commit** `docs(meaning): the meaning page and the additive-only rule`.

### Task 5: Release the block into the five modalities

**Files:**
- Modify: `schemas/stable/{biometrics,biosample,environment,events,physio}.schema.json`
- Create: `schemas/archive/{biometrics,biosample,environment,events,physio}/<old>.schema.json`
- Modify: `specs/{biometrics,biosample,environment,events,physio}.md` (regenerated)
- Test: `tests/test_meaning_block.py` (backward compatibility)

- [ ] **Step 1: Write the failing test** `test_every_existing_document_still_validates_after_the_release`: for each of the five modalities, validate (draft 7) every fixture and example the repository has for it (the `BASE` documents and example dicts in `tests/test_*_schema.py` and files under `examples/` if any: find them with `grep -rln "schemas/stable" tests`) against the **archived** (old) schema and the new stable schema; both must give the same result (valid stays valid). Plus `test_the_modality_check_passes_with_survey_pending` (`check_modalities.main([]) == 0`) and `test_five_schemas_carry_the_block` (`missing(...) == []` for each).
- [ ] **Step 2: Run** them. Expected: FAIL (the schemas are not stamped yet; the archives do not exist).
- [ ] **Step 3: Release** each modality, one command and one commit each: `python scripts/meaning_block.py release --modality biometrics` (then biosample, environment, events, physio). Read each diff: only the version, the `$id`, the added properties and (for events and physio) the replaced `TermURL` may change; the archive is the previous file byte for byte.
- [ ] **Step 4: Run** `python -m pytest tests -q && python scripts/check_modalities.py && python scripts/check_schema_versions.py origin/main HEAD && python scripts/generate_schema_reference.py --check`. Expected: all PASS, no output from the two checks.
- [ ] **Step 5: Commit** each release as `feat(<modality>): meaning block (schema <new version>, <old version> archived)`.

**Then, with the user's confirmation** (outward-facing): run `/ponytail:ponytail-audit`, push the branch, open the pull request in prism-specification, merge when green, and tag the next patch version (check `git tag`; expected v1.5.6 or later depending on PR #32).

### Task 6: Survey (after prism-specification PR #32 is merged)

**Files:**
- Modify: `schemas/shared/meaning-locations.json` (move survey from `pending` into `modalities` with column `[["additionalProperties","oneOf",0]]` and file `[["properties","Study"]]`)
- Modify: `schemas/stable/survey.schema.json`, create the archive of the then-current version, regenerate `specs/survey.md`
- Test: `tests/test_survey_schema.py`, `tests/test_meaning_block.py`

**Interfaces:**
- Consumes: Task 1 (`_span` into array elements), Task 2 and 3, and the merged state of PR #32 (survey schema 2.2.0 or later). **Do not start before it is merged**: rebase on `origin/main` first and read the current survey schema version.

- [ ] **Step 1: Write the failing tests:** the survey item definition (`oneOf[0]`) accepts `IsAbout`, `LevelIsAbout`, `ValueMappings`, a `TermURL` object, and still accepts a document that has none (use the `BASE` document of `tests/test_survey_schema.py`); an alias item (`oneOf[1]`, `AliasOf` only) is unchanged; `Study` accepts `IsAbout`; `check_modalities.main([]) == 0` with `pending` empty.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Edit the locations file, run** `python scripts/meaning_block.py release --modality survey`, read the diff (additions only, plus the `TermURL` replacements for `Study.TermURL` and the item `TermURL`; the latter two are plain string definitions today).
- [ ] **Step 4: Run** the full checks of Task 5 Step 4. Expected: PASS.
- [ ] **Step 5: Commit** `feat(survey): meaning block (schema <new>, <old> archived)`; pull request, merge and tag as in Task 5 (confirmation first).

### Task 7: Studio takes the release

**Files (prism-studio):**
- Sync output (`app/schemas/**`, `docs/specs/**`, `scripts/specification/**`, `specification.lock.json`), `tests/test_vendored_specification.py` (pin)
- Whatever the wider test run shows (expect: the template editor and tests that pin schema versions)

**Interfaces:** Consumes the tag from Task 5 or Task 6 (run this task once per tag).

- [ ] **Step 1: Write the failing pin test** (`tests/test_vendored_specification.py`: the expected tag). Run it. Expected: FAIL (lock still on the previous tag).
- [ ] **Step 2: Sync:** `python scripts/sync_specification.py --tag <tag>` in a worktree from `origin/main`; never edit the vendored files by hand.
- [ ] **Step 3: Run the wider tests** (survey, recipe, term, vendored, specification, template, cli, validation, version, schema, issues, runner: the same `-k` set used for earlier steps) plus the JavaScript tests of the template editor. For every failure, find the cause first (systematic debugging) and fix it test first. Two are likely: (a) the template editor builds fields from the schema; `Study/IsAbout` (an array of objects) must not appear as a broken input: add it to the editor's skip list with a test in `app/static/js/template-editor/` until a widget exists (the project page's chip widgets are the model, a later step); (b) tests that pin a schema version.
- [ ] **Step 4: Run** `python tests/verify_repo.py --check dual-tree-drift --no-fix` and the wider tests again. Expected: PASS.
- [ ] **Step 5: Commit** `chore(specification): sync prism-specification <tag> (meaning block)`; pull request, merge when green (the user confirms).

---

## Self-Review

- **Spec coverage:** section 2's fields (`IsAbout`, `Match`, `Higher`, `Source`, `Checked`, `Status`, `LevelIsAbout`, `ValueMappings`, `TermURL` both forms) are the pinned block; section 5's additive-only rule is Task 4 (CONTRIBUTING) and the whole design of Task 5; calls 4, 5, 6, 9, 10 are the `TermURL` rule, the `Levels`-only value level, latest-stable-only and no passthrough, the minor bump per schema with a patch tag, and survey after template slimming. Section 6 B's "test that fails when a modality lacks it" is Task 3 plus Task 2's `missing`. Not in this plan, by design: `Term` (stays modality-specific, step E), the concept registry (C), the projection (D), the proposal form (G).
- **Checked against the real schemas before writing:** every pinned location resolves to an object with `properties`; `Levels` exists at the biometrics, biosample, environment and events column locations and at events `trial_type`, not at `onset`, `duration`, `response_time`, `stim_file` or the physio channels; the existing `TermURL` definitions are `{type: string, ...}` in survey (item and Study), events and physio (the last two with `format: uri`).
- **Rulings made here (the user may overrule):** edit the schema text in place (the files are hand-formatted; a JSON re-dump would rewrite most lines, checked: only `environment` round-trips byte-identically); no `$ref` (no stable schema uses one); `Term` is not part of the block; `ValueMappings` rules are structured (`Op` and `Value`) instead of an expression string, so no consumer has to parse a grammar; `IsAbout` entries only require `Concept`; a `pending` map lets the repository check pass while survey waits for PR #32; one pull request for Tasks 1 to 5.
- **Names used across tasks:** `load_block`, `load_locations`, `stamp`, `missing`, `release`, `meaning-block.json`, `meaning-locations.json` are the same in every task.
- **Proportion:** seven tasks over two repositories; the pinned block is the largest piece and is spec content, not code.
