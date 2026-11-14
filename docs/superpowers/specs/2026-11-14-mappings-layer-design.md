# One meaning layer for every modality: data carries IDs, `mappings/` carries meaning

Date: 2026-11-14. Status: draft for the user's review. It **replaces steps B, C and D** of
`2026-11-14-reasoning-foundation-design.md` (the in-schema meaning block, the PRISM concept registry, and the
projection as designed there). Step A (an older minor schema version no longer warns) stands.

## Why this replaces the earlier design

The earlier design put the meaning into the data descriptions: every modality schema got optional fields
(`IsAbout`, `LevelIsAbout`, `ValueMappings`, an object `TermURL`), so each sidecar or template would carry its own
links, and the links pointed to concepts PRISM would keep itself (`prism:fatigue`). That was released in
prism-specification v1.5.6. The user's model, stated on 2026-11-14, is different:

- PRISM is the data and the IDs. A data file and its sidecar say what the columns are and use the IDs PRISM already
  has (survey item IDs, score IDs, biosample and environment term IDs). They carry no ontology links.
- All further meaning lives in a separate layer that reads those IDs: which external ontology entry an ID is the same
  as, what an item or score measures, which way a value points, how a value is read as a state.
- PRISM tags no symptoms or constructs itself. A link points to an existing external vocabulary entry.
- One solution for all modalities, biosample included: the links in the biosample term files move into the layer too.
- The survey library and the recipes move into prism-specification, so that the IDs, the definitions they come from,
  and the meaning layer are released together. (The move was deferred until step 3; step 3 is done.)

## Decided by the user (2026-11-14)

1. Data and sidecars carry IDs only; the meaning is a separate file that reads the IDs.
2. PRISM does not keep its own symptom or construct concepts; links go to external vocabularies.
3. The library (instrument templates) and the recipes move to prism-specification, next to the meaning layer.
4. One mechanism for every modality, biosample included (its `TermURL` links move into the layer).
5. Small steps, each a patch release (schema versions and repository tags bump the patch).
6. The earlier decisions that stand: `prism:` IDs, readable and frozen once released; survey item IDs are derived from
   the templates and recipes; an edited project item loses its official ID; "missing is not no"; the specification
   stays agnostic about content and about reasoning models; Sonnet 5.5 for every subagent.

## Goals

1. Every ID that PRISM releases can be given meaning in one place, with the same file format for every modality.
2. The data side never changes when the meaning changes: a mapping can be added, corrected or removed without a new
   schema version.
3. A check proves that every mapping refers to an existing ID and to a known vocabulary.
4. A project can add its own mappings for its own columns, marked as not reviewed, without touching official files.
5. Everything a reasoner needs comes out of one export (the projection, a later step) that joins data, IDs and mappings.

## Non-goals

- A PRISM list of symptoms, constructs or other concepts (the concept registry of the earlier design is dropped).
- The reasoner, the query, diagnoses, cut-offs as truth, a cross-project index of who has which property.
- Curating mappings for the whole library: content arrives by proposal; this design ships the mechanism and the
  migration of what exists (the eight SNOMED links of the biosample terms).
- BIDS passthrough data (MRI, EEG): BIDS owns those names.

## Anti-goals (a failure even if it works)

- Ontology links inside sidecars, templates or schemas.
- A mapping that refers to an ID nobody released, or to a URL nobody looked up.
- Two places that both define the meaning of one ID.
- An ID that changes or disappears because the library moved.
- Moving instrument templates under a licence that does not apply to them (see "Licensing").

## Design

### 1. The layout of prism-specification after the change

```
schemas/      what a file must look like                     (exists; loses the v1.5.6 meaning fields)
terms/        biosample and environment terms: identity only  (exists; loses TermURL)
library/      instrument templates: survey, biometrics, biosample examples   (moved from Studio)
recipes/      scores computed from items                      (moved from Studio)
mappings/     meaning of IDs: links to external vocabularies, direction, value rules   (new)
specs/        the pages, including mappings.md
scripts/      the checks and the ID derivation, stdlib only    (vendored into Studio as today)
```

Identity (what an ID is called, its unit, specimen, answer levels, wording) stays in `terms/`, `library/` and
`recipes/`. Meaning (what it is the same as, what it measures, how to read its values) is only in `mappings/`.

### 2. The mapping file

One file per ID family, in `mappings/<modality>/<family>.json`: for survey one file per instrument
(`mappings/survey/phq9.json` for the instrument, its items and its scores), for biosample one per analyte
(`mappings/biosample/cortisol.json` for `prism:cortisol` and its specimen children), for environment one per variable.
The file name is the family's ID local part. Keys are full PRISM IDs; every key must belong to the family.

```json
{
  "prism:cortisol": {
    "SameAs": {"snomed": "https://snomed.info/id/..."}
  },
  "prism:phq9.phq904": {
    "Measures": [
      {"URL": "https://<vocabulary>/<entry>", "Match": "exact", "Higher": "more",
       "Source": "who made the link", "Checked": "2026-11-14", "Status": "reviewed"}
    ],
    "ValueRules": [
      {"Name": "phq9-symptom-present", "Source": "PHQ-9 manual",
       "Rules": [{"When": {"Op": ">=", "Value": 2}, "State": "present"},
                 {"When": {"Op": "<",  "Value": 2}, "State": "absent"}]}
    ],
    "Levels": {
      "3": {"Measures": [{"URL": "https://<vocabulary>/<entry>", "Match": "narrower"}]}
    }
  }
}
```

Fields (names proposed in conversation; the user asked for names that say their purpose):

| Field | Meaning | Replaces |
|---|---|---|
| `SameAs` | This ID is the same thing as that entry in another vocabulary: `{vocabulary: URL}`, one URL per vocabulary. | `TermURL` in term files and the object `TermURL` of v1.5.6 |
| `Measures` | This item, score or variable measures (asks about) that concept: a list of `{URL, Match, Higher, Source, Checked, Status}`. `Match` is `exact`, `broader`, `narrower` or `related` (the SKOS mapping words); `Higher` is `more` or `less` (a higher value means more or less of that concept); `Status` is `reviewed` or `unreviewed`. Only `URL` is required. | `IsAbout` of v1.5.6 |
| `ValueRules` | Named, sourced rules that read a value as a state (`present`, `absent`, `high`, ...). Several may exist and disagree; none is the truth; a consumer picks one by name. `When.Op` is one of `==`, `!=`, `>=`, `>`, `<=`, `<`, `in`. | `ValueMappings` of v1.5.6 |
| `Levels` | The same fields for a single answer value or category, keyed by the level code as written in the data. | `LevelIsAbout` of v1.5.6 |

### 3. Known vocabularies are data

`mappings/vocabularies.json` lists every vocabulary a URL may come from: a short name (`snomed`, `loinc`, `chebi`,
`ncit`, ...) and the URL pattern. Today the four patterns live as code in `check_terms.py` (`_TERMURL`); they move here,
and adding a vocabulary is a one-line data change reviewed by a maintainer who looked the pattern up. Which
vocabularies serve psychological constructs is decided when the first mapping files are written (no list is assumed
here). A `SameAs` key must be a known vocabulary name; a `Measures` URL must match one known pattern.

### 4. The check

`scripts/check_mappings.py` (stdlib, vendored into Studio like the other checks):

- every key is an existing, released PRISM ID of the file's modality and family (the term registries, and the item and
  score IDs derived from `library/` and `recipes/` by the derivation script that moves with the library);
- every URL is known (section 3); every field has the right type and enum value; wrong types are messages, not crashes;
- `Levels` keys exist in the definition of that ID (the template's `Levels` or the term's `Levels`);
- no ID is given meaning in two files.

It runs in CI next to the other checks. A mapping file may change freely between releases (it is curation, not
identity); `Checked` and `Status` record who looked when.

### 5. A project's own mappings

A project can keep mapping files for its own columns in `<project>/code/specification/mappings/<modality>/`, using the
same file format, through the mechanism that already handles a project's local terms (`src/spec_overlay.py`). Their
links are always reported as `unreviewed`. The official file wins where both give meaning to the same official ID.
Project files are untrusted data: invalid ones are skipped and reported, never a crash; names come only from validated
IDs.

### 6. How Studio uses it

- `terms show` lists an ID's `SameAs` and `Measures` from `mappings/` (today it reads `TermURL` from the term file;
  the parent's links are still shown with their origin).
- The template editor gets no ontology fields (nothing about meaning is in a template any more).
- The projection (a later step, redesigned on top of this): for any dataset, one row per variable with its ID and the
  meaning from `mappings/`, and optionally one row per observation with value and state (observed, not applicable,
  missing). No per-modality code.

### 7. The library and recipe move

- `official/library/survey`, `official/library/biometrics`, `official/library/biosample` (the example templates) and
  `official/recipe/survey` move to `library/` and `recipes/` in prism-specification; Studio vendors them back to the
  same paths with the sync script (the path mapping gains `library/` and `recipes/`); every Studio reader keeps its
  path. Studio's `official/library/terms` is already vendored.
- The survey ID derivation (`src/survey_terms.py`, the released-ID list `term-ids.txt`, the freeze rule) moves into
  the specification's scripts so there is one implementation; Studio calls the vendored copy. The derivation must not
  depend on Studio code (today it imports a list of non-item keys from `src/template_languages.py`, which pulls pandas;
  that list moves with it).
- Proposals for new or changed instruments then happen in prism-specification, like terms and schemas.
- Studio's own drift and consistency checks over the library keep working against the vendored copy.

### 8. Licensing

The specification repository licenses `schemas/`, `terms/` and `specs/` as CC BY 4.0 and `scripts/`, `tests/` as MIT.
The instrument templates are not ours to license: 102 of the 103 survey templates carry per-instrument terms copied
from their upstream source (one is CC BY-NC), and Studio's `official/library/NOTICE.md` says so. The move must keep
that: `library/` gets its own notice and is excluded from the CC BY 4.0 grant in the repository's `LICENSE`; recipes
and mappings are our own work and can be CC BY 4.0.

### 9. Order of the work (each step a patch release)

1. **Remove the v1.5.6 in-schema meaning block** from the six modality schemas (patch bump each; the archived copies
   stay), delete `scripts/meaning_block.py`, `schemas/shared/`, the check rule in `check_modalities.py` and
   `specs/meaning.md`. Studio's sync PR for v1.5.6 (prism-studio #250) is closed without merging; Studio syncs the next
   tag instead (the slim-survey release and the Studio fixes in #250 are carried over).
2. **Move the library and the recipes** (with the ID derivation, the released-ID list and the licence carve-out);
   Studio syncs them back to its paths.
3. **Add `mappings/`**: `vocabularies.json`, the check, `specs/mappings.md`; move the eight SNOMED links out of the
   biosample term files into `mappings/biosample/` and remove `TermURL` from the term files and from `check_terms.py`;
   Studio reads links from `mappings/`.
4. **Project mappings** in `code/specification/mappings/`.
5. **The projection**, redesigned on this layer.
6. **The proposal route**: a proposal for a new kind of data or a new instrument brings its mapping file.

## Constraints

- THE RULE: logic once (in the specification's scripts or Studio's `src/`), exposed by the CLI; Studio only triggers.
- The vendored specification is never edited in Studio; changes go through prism-specification, a tag, and the sync.
- Released IDs are frozen; the move must keep every survey item and score ID and the released-ID list unchanged
  (a test compares the derived IDs before and after the move).
- No real ontology code is written by an implementer; examples use placeholders.
- TDD; the CLI/Studio parity rule where Studio gets a button; Sonnet 5.5 for every subagent.

## Calls made after the builder check (mine; the user may overrule any)

A fresh reader raised eight questions. These are settled here, with what each costs if wrong.

1. **Family per modality.** Survey: one family per instrument template, named by `Study.TaskName`; its items and its
   recipe scores are in the same file; variants inside one template (`VariantDefinitions`, languages) are one family;
   a short form shipped as its own template is its own family. Biosample: one family per analyte (the analyte and its
   specimen children). Environment: one family per variable. **Biometrics is out of scope for mappings in this
   round**: its template moves with the library, but it has no derived IDs yet; it gets mappings when it gets IDs.
   Cost if wrong: one more family rule later.
2. **Inheritance.** A specimen child inherits its analyte's `SameAs` and `Measures` when it has none of its own, and
   every reader reports where a link came from (as `terms show` does today). The eight SNOMED links therefore move as
   they are, on the analytes. Cost if wrong: copies per child later.
3. **Removing the v1.5.6 fields.** Forward-only: each of the six schemas gets a new patch version without the fields;
   the v1.5.6 versions stay archived. Nothing uses the fields (released the same day; Studio never synced them), so no
   data is rejected in practice. Cost if wrong: a file written against v1.5.6 that used the fields would now fail.
4. **Studio PR #250.** Closed without merging. Carried over into the next sync, where they still apply: the biosample
   importer test and the biosample example template following the current schema version, the physio-archive test
   fix, the guard that `archive/` is no schema version, the wheel test (adjusted: no `shared/` folder any more), and
   the test that every vendored spec page is in the docs table of contents. Dropped: the `shared/` guard and the
   `meaning.md` table-of-contents entry. Studio never read the removed fields, so step 1 needs no other Studio change.
5. **Where Studio vendors mappings.** `official/library/mappings/` (next to `official/library/terms/`), read by
   `terms show` and by the project overlay; the official file wins over a project file for the same official ID.
6. **`Levels` in a mapping.** Only for an ID whose definition has `Levels` (categories or labelled answers). An item
   with a numeric range and no `Levels` gets meaning per value through `ValueRules`, not `Levels`.
7. **Step order when licensing waits.** If the licensing question (open point 1) is not settled when step 1 is done,
   the `mappings/` step runs first for biosample and environment (their IDs are already in the specification), and the
   library move and the survey mappings follow once it is settled.
8. **No real codes by implementers** (repeated from the constraints): the migration moves the eight existing links
   unchanged; new links come from people, by proposal.

## Left to the builder

Exact JSON Schema of a mapping file; the check's messages; how the derivation script is split between the two
repositories' tests; the sync script's path mapping details; the order of the commits inside each step.

## Open points for the user

1. The licensing carve-out for `library/` (section 8): is publishing the instrument templates from the specification
   repository, excluded from its CC BY 4.0 grant and with their own notice, acceptable? Step 2 depends on it.
2. The field names `SameAs`, `Measures`, `ValueRules`, `Levels` and the folder name `mappings/` (or `ontology/`, the
   user's first word): both are baked into the file format and the check; a later rename is a breaking change.
3. Whether a project's own mappings (section 5) are part of the first version or a later step (the order above
   assumes a later step).
