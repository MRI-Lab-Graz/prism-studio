# Term IDs for every modality, down to the single survey item

Date: 2026-11-11. Status: approved by the user on 2026-11-11, part by part in the conversation (answers in the last section).
Steps 1 and 2 are merged (PR #234, `feat/survey-term-ids`). Extended later on 2026-11-11, before step 3: the agnostic
principle, what each modality has to carry, and what three sources add. Parts marked **proposal** are not yet agreed.

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
- **PRISM is agnostic about content.** There is much psychology in the library today; that may change. PRISM ships the
  mechanism (fields, IDs, checks); which concepts get linked comes with the data. Nothing in the mechanism may be
  specific to psychology, to medicine or to one modality.

## What the reasoning has to tell apart (agreed list)

1. **Level**: a questionnaire, a score computed from it, a single item.
2. **The thing asked vs the concept it is about**: the item is not the concept.
3. **Same item, different form**: a translation is the same item; an item reused in a short form is another ID that
   points to its origin.
4. **How to read a value**: direction, range, reversed scoring.
5. **Context of the answer**: who answered, about which period.
6. **Strength of a link**: exact concept or only a broader one.

## What every value has to carry, and what each modality has today

A reasoning step needs five things for any single value:

1. **Identity**: which variable this is (`prism:` ID).
2. **Concept**: what it is, or is about (a link, with relation and direction).
3. **Value meaning**: unit, range, what each category means, when a value counts as high.
4. **Context**: who answered, when, about which period, under which conditions, with which method.
5. **Subject**: whose value it is, at which timepoint.

State on 2026-11-11 (checked in the schemas and registries, not assumed):

| Modality | Identity | Concept | Value meaning | Context |
|---|---|---|---|---|
| participants | no `prism:` IDs | Neurobagel `IsAbout` per project, read by Studio | categories partly linked | - |
| survey | done: 1,478 released IDs | none | range, `Levels`, `Reversed`; direction and cutoffs only as prose (`Interpretation`) | respondent; no recall period |
| biosample | done: 27 terms | SNOMED on 8 of 13 analytes | units, minimum; no reference ranges | specimen, fasting, assay method per file |
| environment | done: 31 variables | no `TermURL`; a `CFStandardName` field | units, levels | source, resolution |
| biometrics | none (one template) | none | schema has cutoffs and norms | equipment, respondent |
| physio | none | none | units per column | rich: resting state, eyes open, caffeine and alcohol abstinence |
| events | none | none | `trial_type` levels | stimulus software |

What follows from the table:

- **Participants is a modality of this design.** It is the most direct source of subject properties and already uses
  the `IsAbout` pattern; step 4 reuses its format exactly. (**proposal**: a step of its own after surveys.)
- **Two kinds of modality.** In participants, survey, biosample and biometrics a value is a property of the subject. In
  physio, events and BIDS recordings the property is "has such a recording under such conditions": the recording type
  and its conditions need IDs and links, not each sample. Environment describes the session, not the subject.
- **"High" needs a threshold.** A link and a direction let a query rank subjects; "elevated" needs a cutoff or a
  reference range a program can read. PRISM keeps levels and ranges readable; whoever queries picks the cutoff.
- **"Not measured" is not "no".** A subject without a value is unknown, not negative. Every modality keeps a missing
  value distinguishable from a low one.
- **Out of scope, written down as such:** whether a subject in two projects is the same person.

### The example the user gave: participants with fatigue

Checked against the survey library: there is no fatigue questionnaire and no fatigue score. Fatigue exists only as
single items inside other instruments: `PHQ904` ("Feeling tired or having little energy"), `CUDOS09`, `GSQS04` ask it
directly; `OHQ16`, `WBM10`, `ZKPQ08` ask the opposite (lots of energy); `BURNOUT02` ("tired of my students"), `DASS12`
("nervous energy") and `RRS03` (brooding over fatigue) only look like it. So:

- the selection is impossible at instrument level; only the item ID (`prism:phq9.phq904`) can carry the link;
- a text search returns the look-alikes, so a link is made by a person, with relation and direction;
- PHQ-9 asks about two weeks, GSQS about this morning: the recall period is part of the property;
- a score's direction does not help here (no fatigue score); it does for "elevated depression".

It is a test case for the mechanism, not a curation programme (see the agnostic principle).

### What three sources add (read 2026-11-11)

- Kaliciński, "The ontologies you shouldn't build yourself" (Neo4j Developer Blog, 2026): reuse a slice of a standard
  and keep its identifiers; a wrong mapping is worse than none; standards deprecate and split concepts, so a link goes
  stale; crosswalks (UMLS) translate between vocabularies, so one checked link per term is enough.
- El-Sappagh et al., "SNOMED CT standard ontology based on the ontology for general medical science" (BMC Med Inform
  Decis Mak 2018, 18:76): SNOMED keeps substance, specimen, observable entity, clinical finding and scales in separate
  branches, so the kind of target matters; specific meanings are composed from parts, not pre-combined; no data means
  unknown, not negative; an ID, the idea and the real thing are three things (our `TermURL` / `IsAbout` split).
  Bridging SNOMED and the OBO ontologies is the query builder's job, not PRISM's.
- Quest for Orthologs, list of orthology databases: independent databases stay comparable through a shared reference
  set, one exchange format and a plain table of who supports what; combining is done by meta-databases on top. PRISM's
  job is the format and the stable IDs. "The same question in another questionnaire" is linked through a shared concept,
  not through an item-to-item table.

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

- **Shape (decided by the user)**: instrument `prism:<taskname>`; item `prism:<taskname>.<item-key>`; score
  `prism:<taskname>.score-<score-name>`. An item comes from the library template (one question a person answered), a
  score from the recipe (a number computed from items); the fixed `score-` prefix makes the difference readable in the
  ID and a collision impossible. `<item-key>` is the existing key lowercased with `_` written as `-`
  (`TIPI02` -> `prism:tipi.tipi02`); it deliberately repeats the instrument name so it can never disagree with the data
  column. `<score-name>` is the recipe's `Name`, lowercased, `_` as `-`, without a leading `<taskname>-`
  (`tipi_extraversion` -> `prism:tipi.score-extraversion`, `Total` -> `prism:tipi.score-total`). Checked against the
  library on 2026-11-11: all 1,268 items and 111 scores give a valid, unique ID and no item key starts with `score`.
  `score-` is reserved: an item key that starts with it is an error. It is the two-segment grammar the registry
  already has (`prism:cortisol.serum`), so `check_terms` and `expand()` need no new ID rule. `Level` is `instrument`,
  `item` or `score`.
- **Derived, not stored (agreed by the user)**: the library template and the recipe stay the only place an item or a score is
  defined. One backend function builds the survey term registry from them (the same dict shape `load_registry` returns),
  so `find_term`, `term_links` and `terms list|show --modality survey` work unchanged. No term file per item.
  A template without a recipe still gives the instrument and item IDs, only no score IDs (today all 103 templates
  have a recipe). A recipe without a library template gives no IDs at all and is reported: a score needs its
  instrument (today: `psqi`).
- **Frozen**: a committed list of every released survey ID (one per line). A test fails when a released ID is missing
  from the derived registry (renamed key, removed item, renamed task), when an item key starts with `score-` and when
  two scores of one instrument get the same ID. New IDs are added to the list by a command, never by hand.
- **One concept, one ID**: a Studio test runs the cross-registry rule over biosample, environment and the derived
  survey registry.
- **Short forms and variants**: one template with `VariantDefinitions` is one instrument; its items keep one ID and
  `ApplicableVersions` says where they occur. Two templates (for example a short form shipped as its own file) are two
  instruments; an item copied from another instrument names its origin in a new optional item field `DerivedFrom`
  (a `prism:` item ID). Translations never get an ID of their own.
- **In a project**: a function resolves a survey sidecar column to an official ID when the sidecar's `Study.TaskName`
  is a library instrument and the column is one of its items, **and** the item is unchanged in what makes it that item (decided by the user: an edited item loses the official ID, it
  is not kept with a "modified" mark):
  the answer values (`Levels` keys, `MinValue`, `MaxValue`) and, where the sidecar has the library's language, the item
  text. Otherwise the result is "no official ID" with the reason (unknown instrument, unknown item, changed scale,
  changed wording). CLI: `terms resolve --sidecar <file> [--json]`, one line per column. Nothing is written into the
  sidecar; the validator's verdict does not change.

### Step 3: what a value means

Mostly making explicit what is implicit. It is text for people; a direction a program can compare comes with the link
in step 4 (agreed by the user: text now, direction on the link later).

- **Direction**: `Reversed` exists per item. A score gets `HigherMeans` (short text, en) in the recipe, for example
  "more depressive symptoms", and an optional `LowerMeans` for two-sided scales (introversion to extraversion), where
  it is not just the negation. 102 recipes already say it as prose in `Interpretation`.
- **Respondent**: `Technical.Respondent` exists; nothing new.
- **Period**: new optional `Study.RecallPeriod` (for example "past 2 weeks"; an ISO 8601 duration where it is one).
  An item that deviates may set its own.
- **Range**: exists (`MinValue`, `MaxValue`, `Levels`; `Range` on scores).

Where the fields live (checked): `recipe.survey.schema.json` is Studio-owned, so `HigherMeans` / `LowerMeans` need no
specification release; its score object is open, existing recipes stay valid. `survey.schema.json` is vendored, so
`RecallPeriod` is a prism-specification patch release (v1.5.5) and a sync. Both are optional.

The exact field names and value rules are settled in step 3's own plan; the list above is the content.

### Step 4: concept links for surveys

- `TermURL` keeps its v1.5.4 meaning: this term **is** that thing in another vocabulary (cortisol is the SNOMED
  substance). That is always an exact statement, so it needs no relation.
- **New `IsAbout` (agreed by the user)**: what an item, a score or an instrument measures or asks about. A list of
  `{"TermURL": <URL>, "Label": <text>, "Match": "exact" | "broader" | "narrower" | "related"}`. It answers points 2 and 6
  of the list. The name follows the Neurobagel annotation Studio already reads for participants
  (`src/participants_backend.py`).
- Inheritance for reading, like `term_links`: an item without `IsAbout` shows its score's, then its instrument's, each
  with where it comes from.
- **Direction on the link (agreed by the user in principle; field name open)**: whether a higher value means more or
  less of the linked concept, for example `"Higher": "more" | "less"`. A direction only means something relative to a
  concept: PSQI total is `less` of "sleep quality" and `more` of "sleep disturbance". "Which direction is good" is a
  judgement and is not stored.
- **One mechanism for every modality**: the link fields mean the same on a survey item, a biosample analyte, a physio
  channel and a participants column.
- Curation: each link is looked up by a person and cited in the pull request. PRISM does not set out to link the whole
  library; content comes with the data.

**Proposals for step 4's own design (not yet agreed):**

- **The kind of target per level**: an analyte links to a substance, a measured level to an observable (LOINC), a
  questionnaire to a scale, a threshold result to a finding. The design says which kind each `Level` may link to.
- **Compose, do not pre-combine**: context (specimen, fasting, recall period) stays in its own field with its own link;
  no combined terms.
- **Date checked** on each link, and a periodic check that the target still exists.
- **Vocabularies as data, not code**: today `check_terms.py` knows four systems (SNOMED, LOINC, ChEBI, NCIT), each a
  pattern in code. An agnostic PRISM needs an extendable list, preferably following a public prefix registry and not a
  list of our own. Which vocabularies serve psychological constructs is researched then.
- **Local links**: a project's own terms (`code/specification/terms/`) may carry the same link fields, so a field we
  did not think of can annotate its data.
- **Test case**: the six or seven fatigue items above, to prove the format; nothing more.

### Step 5: the remaining modalities

- **biometrics**: template-based like survey (one template today); the survey mechanism applies as is.
- **events, physio**: columns and channels are few and generic; they get small term registries of `Level: variable`,
  the way environment has, in prism-specification.
- An ID is given where a single column means the same thing in every project. Free, project-specific columns get none.
- **participants** (**proposal**): the common columns get `prism:` IDs; the existing Neurobagel annotation stays the
  link format.
- For recording modalities the IDs name the recording type and its conditions (see the two kinds of modality above).

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

## Answers of the user (2026-11-11)

1. Item IDs are mechanical from the existing key: `prism:tipi.tipi02`.
2. Scores carry the `score-` prefix: `prism:tipi.score-total`.
3. An edited item (wording or answer scale) loses the official ID.
4. Two fields: `TermURL` (is the thing) and `IsAbout` (is about the thing).
5. Survey IDs are derived from template and recipe; no term file per item.
6. Step 3 as written (`HigherMeans` on a score, `RecallPeriod` on the instrument; exact names in that step's plan).
7. Whether the survey library moves into prism-specification is NOT decided ("a big decision", to wait). Until then
   survey IDs live in Studio and their URLs do not have to resolve. Nothing in steps 2 to 5 may depend on the move.
   Later the same day: keep waiting until step 3 is done, then draft a move plan and ask.
8. Step 3 is text (`HigherMeans`, optional `LowerMeans`, `RecallPeriod`); the direction a program can read goes on the
   link in step 4 ("basically yes").
9. The example selection: participants with fatigue.
10. PRISM stays agnostic about content: "we should not worry much about content - we have much psychology stuff at the
    moment, this may change."
