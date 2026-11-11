# Term IDs for every modality, down to the single survey item

Date: 2026-11-11. Status: DRAFT, waiting for the user's approval. Written for the builder who plans and implements it.
Open questions for the user are in the last section; everything marked "(my call)" was decided by the author, not the user.

## Intent

PRISM data should be usable for big data: one day somebody asks a whole PRISM database (many projects) for "every
subject with this property", and a reasoning step finds them through ontology links, not through column names.

This design does **not** build that query. It makes sure every dataset carries what such a query needs: a stable
identity for every relevant part of the data, a link from that identity to a concept, and enough about a value to
read it. Identifying single survey items is the special part; the user knows no other database that does it.

## What the user decided

- Every relevant part of the data gets an ID. If it is reasonable to identify single items of a survey, do it; the same
  for other modalities.
- IDs are `prism:<slug>`, readable, never numeric. One ID names one concept and is unique across all modalities; the
  modality is part of the URL (`https://w3id.org/prism-specification/terms/<modality>/<local-id>`), not of the ID.
- Small steps, each released on its own (specification releases bump the patch version).
- Order: (1) links reach the data [done, PR #234], (2) IDs for surveys, (3) what a value means, (4) ontology links for
  surveys, (5) the remaining modalities.
- Identity before meaning: an ID must not depend on which ontology is chosen later.

## What the reasoning has to tell apart (agreed list)

1. **Level**: a questionnaire, a score computed from it, a single item.
2. **The thing asked vs the concept it is about**: the item is not the concept.
3. **Same item, different form**: a translation is the same item; an item reused in a short form is another ID that
   points to its origin.
4. **How to read a value**: direction, range, reversed scoring.
5. **Context of the answer**: who answered, about which period.
6. **Strength of a link**: exact concept or only a broader one.

## What exists already

- Term registry for biosample and environment (`official/library/terms/`, vendored from prism-specification):
  `TermID`, `Level`, `Parent`, `TermURL` (`{system: URL}`, v1.5.4), `check_terms.py` (ID rules, one ID in one modality),
  `expand()` (ID to URL). `src/term_registry.py`: `find_term`, `resolve_column`, `term_links`.
- Survey library (Studio-owned, `official/library/survey/`): 103 templates, 1,268 items. Every item key (`AQ1001`,
  `TIPI02`, `ADS-K01`) is unique across the whole library today and turns into a valid slug by lowercasing. Per item:
  `Description` (en/de), `Levels`, `MinValue`, `MaxValue`, `Reversed`, `ScaleType`; the schema also allows `TermURL`
  (a string, the BIDS meaning), `Aliases`/`AliasOf`, `ItemVersion`, `ApplicableVersions`, `VariantScales`.
- Per instrument: `Study.TaskName` (the stable slug, falls back to the file stem), `ShortName`, `Version`,
  `VariantDefinitions`, `Construct`, `Subscales`, `TermURL`; `Technical.Respondent` (required in a project copy only).
- Instrument registry (`src/instrument_registry.py`, `official/library/survey/index.json`): identity of instruments from
  `TaskName`/`Version`/`DOI`. It says "no new ID scheme"; this design gives it one.
- Recipes (`official/recipe/survey/`): 111 scores (`Name`, `Method`, `Items`, `Range`), mostly `Total`; inverted items.
- Nothing has a `prism:` ID or a concept link in surveys, biometrics, events, physio.

## Goals

- Every instrument, score and item of the official survey library has a frozen `prism:` ID.
- A project's survey column can be resolved to that ID, or the tool says why it cannot.
- A value can be read without the questionnaire's manual: direction, range, respondent, period.
- Instruments, scores and items can carry concept links with a stated relation.
- The same mechanism covers the other PRISM modalities.

## Non-goals

- The query or reasoning engine, a central database, a triple store, JSON-LD export.
- MRI/EEG and other BIDS passthrough data: BIDS owns those names (`bids:` prefix exists for that).
- Curating all 1,268 items in one go; step 4 delivers the mechanism and a first batch.
- Translations of terms beyond what the library has.

## Anti-goals (a failure even if it works)

- An ID that changes or disappears after a release.
- A project item that was edited (other wording, other answer scale) presented as the official item.
- A second copy of the 1,268 item definitions that can drift from the library.
- Ontology codes that nobody looked up (the rule from CONTRIBUTING.md: none are invented).
- Logic in a Studio route or in JavaScript: every part is a backend function with a CLI command.

## Design

### Step 2: IDs for surveys (identity only)

- **Shape (my call)**: instrument `prism:<taskname>`; item `prism:<taskname>.<item-key>`; score
  `prism:<taskname>.<score-name>`. `<item-key>` and `<score-name>` are the existing key/name lowercased with `_` written
  as `-` (`TIPI02` -> `prism:tipi.tipi02`, `tipi_extraversion` -> `prism:tipi.tipi-extraversion`, `Total` ->
  `prism:tipi.total`). It is the two-segment grammar the registry already has (`prism:cortisol.serum`), so `check_terms`
  and `expand()` need no new ID rule. `Level` is `instrument`, `item` or `score`.
- **Derived, not stored (my call)**: the library template and the recipe stay the only place an item or a score is
  defined. One backend function builds the survey term registry from them (the same dict shape `load_registry` returns),
  so `find_term`, `term_links` and `terms list|show --modality survey` work unchanged. No term file per item.
  A recipe without a library template (there are 104 recipes and 103 templates) gives no score IDs and is reported.
- **Frozen**: a committed list of every released survey ID (one per line). A test fails when a released ID is missing
  from the derived registry (renamed key, removed item, renamed task) and when an item key and a score name of one
  instrument collide. New IDs are added to the list by a command, never by hand.
- **One concept, one ID**: a Studio test runs the cross-registry rule over biosample, environment and the derived
  survey registry.
- **Short forms and variants**: one template with `VariantDefinitions` is one instrument; its items keep one ID and
  `ApplicableVersions` says where they occur. Two templates (for example a short form shipped as its own file) are two
  instruments; an item copied from another instrument names its origin in a new optional item field `DerivedFrom`
  (a `prism:` item ID). Translations never get an ID of their own.
- **In a project**: a function resolves a survey sidecar column to an official ID when the sidecar's `Study.TaskName`
  is a library instrument and the column is one of its items, **and** the item is unchanged in what makes it that item:
  the answer values (`Levels` keys, `MinValue`, `MaxValue`) and, where the sidecar has the library's language, the item
  text. Otherwise the result is "no official ID" with the reason (unknown instrument, unknown item, changed scale,
  changed wording). CLI: `terms resolve --sidecar <file> [--json]`, one line per column. Nothing is written into the
  sidecar; the validator's verdict does not change.

### Step 3: what a value means

Mostly making explicit what is implicit, in the survey schema (prism-specification, a schema release):

- **Direction**: `Reversed` exists per item. A score gets `HigherMeans` (short text, en) in the recipe, for example
  "more depressive symptoms"; an item's direction follows from the score it belongs to and `Reversed`.
- **Respondent**: `Technical.Respondent` exists; nothing new.
- **Period**: new optional `Study.RecallPeriod` (for example "past 2 weeks"; an ISO 8601 duration where it is one).
  An item that deviates may set its own.
- **Range**: exists (`MinValue`, `MaxValue`, `Levels`; `Range` on scores).

The exact field names and value rules are settled in step 3's own plan; the list above is the content.

### Step 4: concept links for surveys

- `TermURL` keeps its v1.5.4 meaning: this term **is** that thing in another vocabulary (cortisol is the SNOMED
  substance). That is always an exact statement, so it needs no relation.
- **New `IsAbout` (my call)**: what an item, a score or an instrument measures or asks about. A list of
  `{"TermURL": <URL>, "Label": <text>, "Match": "exact" | "broader" | "narrower" | "related"}`. It answers points 2 and 6
  of the list. The name follows the Neurobagel annotation Studio already reads for participants
  (`src/participants_backend.py`).
- Inheritance for reading, like `term_links`: an item without `IsAbout` shows its score's, then its instrument's, each
  with where it comes from.
- Allowed vocabularies are the `_TERMURL` list of `check_terms.py`, extended there as needed (constructs will need more
  than SNOMED; which ones is decided in step 4's own design).
- Curation: links are added instrument by instrument, each looked up by a person and cited in the pull request.

### Step 5: the remaining modalities

- **biometrics**: template-based like survey (one template today); the survey mechanism applies as is.
- **events, physio**: columns and channels are few and generic; they get small term registries of `Level: variable`,
  the way environment has, in prism-specification.
- An ID is given where a single column means the same thing in every project. Free, project-specific columns get none.

## Constraints

- THE RULE: logic once in `src/`, exposed by `prism_tools.py`; Studio only triggers; a parity test where Studio gets a
  button.
- The vendored specification is edited in prism-specification, released, then synced.
- Project files are untrusted data: bad types are reported, never a crash.
- Session and item labels are exact strings; nothing is normalized beyond the stated lowercasing for the ID.
- TDD for every step; one small PR per step or sub-step.

## Left to the builder

Function and file names, the wording of messages, where the released-ID list lives, how step 2 is cut into pull
requests (suggested: library IDs and the freeze first, project resolution second).

## Open questions for the user

1. **Item ID shape**: mechanical from the existing key (`prism:tipi.tipi02`; repeats the instrument name but can never
   disagree with the data column) or shortened (`prism:tipi.02`; nicer, but needs a rule per instrument)?
2. **Edited items**: is "changed wording or scale = no official ID" the rule you want, or should an edited item keep the
   ID with a "modified" mark?
3. **`IsAbout` next to `TermURL`**: agree with two fields (is the thing / is about the thing), or one field for both?
4. **Where survey terms resolve**: the survey library is Studio's, the namespace URL points at prism-specification.
   Should the survey library move into the specification later, or should the URL for survey IDs point at Studio?
