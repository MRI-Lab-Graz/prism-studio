# The reasoning foundation: one neutral description of meaning for every modality

Date: 2026-11-14. Status: direction approved by the user on 2026-11-14 in conversation ("great plan - let's do this");
field names and details below are marked as sketches where they are not decided. This replaces steps 4 and 5 of
`2026-11-11-term-ids-all-modalities-design.md` (steps 1 to 3 of that design are done and merged).

## Why

PRISM describes almost any data the same way: a data file plus a description of it (TSV + JSON), and users can propose
new kinds of data. The next level is to **combine properties across modalities and projects**: "select the participants
with fatigue", "everyone with a high cortisol level and a low sleep score". Somebody will build the reasoning that does
this, and it will not be one reasoner: a set-based one such as AIDA-Path (Salzburg; machine-actionable DSM-5 criteria),
an ontology reasoner over SNOMED, a statistical model, a rule engine.

PRISM's job is not to reason. It is to make sure that every dataset says, in one neutral and machine-readable way,
**what each variable is, what concept it is about, what its values mean, and under which conditions it was recorded**,
so that any reasoner can start from the same facts. The user asked for "one agnostic specification that can be used with
different reasoning models later".

## What the user decided

- One mechanism for every modality, participants included. Neurobagel is then one vocabulary and one export format among
  many, not the model.
- The specification must stay agnostic about content (today much psychology; that may change) and about reasoning model.
- The AIDA-Path approach is a good consumer, not the model of the specification (string symptoms, binary presence, rules
  in code). It is the first real partner: an author is a friend of the user and joins the project.
- **A canonical projection is part of the specification**: a defined export of the facts that any reasoner reads, with a
  conformance test. Not only a Studio tool.
- A file that declares an older minor version of a schema must not produce a warning while the major version matches.
- Small steps; each released on its own (specification releases bump the patch version).
- Earlier decisions that still stand: `prism:<slug>` IDs, readable and frozen once released; `TermURL` means "is that thing
  in another vocabulary"; `IsAbout` means "is about that concept"; survey item IDs are derived; the survey library does not
  move into prism-specification yet; session labels stay exact strings.

## Goals

1. Every described variable of every modality can carry the same small **meaning block** (below), written once and shared.
2. A **concept registry** gives concepts stable `prism:` IDs, with links to external vocabularies where a code exists, and
   a proposal route like terms have today.
3. A defined **projection**: one function, no per-modality code, that turns any PRISM dataset into a canonical long table
   and linked data (JSON-LD), plus a conformance test on every modality.
4. A **versioning rule**: within a major version, a schema only adds optional things, and an older minor in a file is no
   warning.
5. A newly proposed modality gets the block, the registry and the projection without extra work.

## Non-goals

- The reasoner, the query language, inference, a central database, a cross-project index of "who has which property".
- Diagnoses, cutoffs as truth, DSM or other licensed criteria text. PRISM stores IDs, codes, our own labels and the
  user's data, never vocabulary content.
- Curating the whole survey library. Content arrives with the data and by proposal; the mechanism is what ships.
- Replacing BIDS, or changing what BIDS names mean (`bids:` stays for passthrough data).

## Anti-goals (a failure even if it works)

- An ID or a link that silently changes meaning after a release.
- A reasoner-specific shape in the specification (binary matrix, OWL classes, SQL) instead of neutral facts.
- A missing value read as "no". Unknown must stay unknown all the way through the projection.
- A second implementation of the projection in Studio. The backend (`src/`) has it once; the CLI runs it; Studio triggers.
- Participant values in a default export. The default projection is the variable catalogue; values are opt-in.
- Ontology codes nobody looked up.

## Design

### 1. Three layers

1. **Facts (the specification).** The meaning block on every variable, the concept registry, the term registries.
2. **Projection (the specification, plus the one implementation).** A defined, versioned export of the facts.
3. **Reasoners (outside).** They read the projection and derive their own view (a binary matrix, an RDF graph, a data
   frame). Their rules, thresholds and queries live in their own documents and refer to PRISM concept IDs.

### 2. The meaning block (sketch; the names are the builder's to settle with the constraints below)

A variable is a column (or channel, or item) described in a sidecar. The block can attach at three levels: a file or
recording ("an ECG at rest"), a column, and a single value of a column (`sex = female`).

On a column (all optional, additive):

- `Term` (exists for biosample and environment): the `prism:` ID of the variable. Survey items have a derived ID.
- `TermURL` (exists as a string in BIDS sidecars): the BIDS reading stays valid. The registry form is an object
  `{system: URL}`. The block accepts both and says which is which, so BIDS files stay valid BIDS files.
- `IsAbout`: a **list** of `{ "Concept": <prism concept ID or URL>, "Match": exact | broader | narrower | related,
  "Higher": more | less, "Source": <who or what made the link>, "Checked": <date>, "Status": reviewed | unreviewed }`.
  `Match` follows the SKOS mapping vocabulary (exactMatch, broadMatch, narrowMatch, relatedMatch). A list, because one item
  can be about two concepts (a questionnaire item "tired or little energy" is both fatigue and loss of energy). `Higher`
  says whether a higher value means more or less of that concept, because a direction only means something relative to a
  concept.
- Value meaning that exists already stays where it is: units, `MinValue`/`MaxValue`, `Levels`, `Respondent`,
  `RecallPeriod` (survey, step 3).

On a value (inside `Levels` or beside it): `IsAbout` with the same fields, for categories such as sex or diagnosis.

**Value mappings (sketch).** A named, sourced rule that turns a value into a state a reasoner can use, for example
`{ "Name": "phq9-algorithm", "Source": "...", "Rules": [{ "When": ">= 2", "State": "present" }] }`. Several can exist for one
variable and they may disagree (screening versus clinical cutoff). None is the truth; a consumer picks one by name.

**Three data states.** A cell is an observed value, not applicable (the questionnaire's own logic skipped it; survey items
already have `Relevance`), or missing. The projection reports the state; it never turns missing into a value. How
"not applicable" is derived for other modalities is left to each modality's proposal.

### 3. The concept registry

A new level of the term registry: `Level: concept`. A concept is an idea (fatigue, loss of energy, serum cortisol level)
with a `prism:` ID, a label, optional `TermURL` links to external vocabularies, optional `Parent`, and `Status`. The
proposal route, the frozen-ID rule and the cross-registry uniqueness check of terms apply unchanged. Concepts are
agnostic: any field can propose concepts. A link target may be a registry concept or an external URL directly; the
registry exists because many ideas have no external code (the AIDA-Path paper says so for symptoms).

Link targets must say what kind of thing they are (substance, specimen, observable, finding, scale, construct), because
vocabularies keep these apart (SNOMED CT does). The kind is a field of the concept, not of the link.

### 4. The projection

One function in `src/` (the CLI runs it; Studio triggers it) that reads a dataset and produces:

- a **variable catalogue** (default): one row per described variable: dataset, modality, file pattern, variable name,
  `Term`, concept links (with relation, direction, source, checked date, status, and where each link came from: the
  column, the term, or the parent term), unit, scale, levels, value mappings, context (respondent, period, conditions).
  No participant values.
- optionally the **observations** (opt-in): one row per subject, session, variable, with value and state
  (observed, not applicable, missing).
- both as a flat table (TSV) and as JSON-LD with a context file shipped in the specification.

Inheritance for reading: a link on the column wins, then the term's, then the parent term's. The projection says which.
The `terms show` links (already built) are the first step of this.

A **conformance test** runs the projection on example data of every modality and checks that the output validates against
its own schema, that no value is invented, and that missing stays missing. A new modality is not accepted without an
example that passes.

### 5. Versioning rule

Within a major version a schema only adds optional things. The validator no longer warns when a file declares an older
minor version of a schema with the same major version (`schema_manager.is_compatible_version` today reports PRISM005 when
the file's minor is lower). A different major version still warns. Reason: the 2.1.0 survey release made 103 official
templates warn until they were rewritten; small steps would repeat that for every modality.

### 6. Rollout (each a small, separately released step)

- **A. Versioning rule** in Studio's validator. Tiny, independent, unblocks the rest.
- **B. The meaning block**: defined once in prism-specification and added to every modality schema by a generator, with a
  test that fails when a modality lacks it. Additive; no existing file becomes invalid. Includes the SKOS-based
  `Match` vocabulary and the `Higher` field.
- **C. Concept registry** (`Level: concept`): the check script, the proposal route, the Studio registry readers.
- **D. The projection** in `src/` with the CLI command and the conformance test, starting with the variable catalogue
  for survey, biosample and environment, then observations.
- **E. Adoption, modality by modality**: survey (derived item IDs plus `IsAbout` in templates), biosample and
  environment, biometrics, physio, events, participants (reading the Neurobagel shape, writing ours, offering Neurobagel as
  an export).
- **F. First proof with AIDA-Path** (with the friend who joins): a handful of PHQ-9 items linked to their symptom names
  with a named value mapping, and the projection read by their side. A test of the foundation, not a feature.

## Constraints

- THE RULE: logic once in `src/` (and the vendored scripts), exposed by `prism_tools.py`; Studio only triggers; a parity
  test where Studio gets a button.
- The vendored specification is edited in prism-specification, released, then synced. The survey schema is also being
  changed by the template-slimming work (`2026-11-13-template-slimming-design.md`: removes `Subscales`, `ItemCount`,
  `Reversed`): order the two specification releases and do not let them touch the survey schema in parallel. Direction of
  an item (`Reversed`) moves to recipes there, which step B must respect: an item's direction follows its score.
- Project, sidecar and library files are untrusted data: wrong types are reported, never a crash.
- Licences: store codes, URLs and our own labels only. The AIDA-Path repository has no licence file today; ask its
  authors before reusing their symptom names.
- Privacy: the projection describes data. It is never a cross-project index; observations are opt-in and local.
- TDD for every step; the CLI/Studio parity rule for every Studio trigger.

## Left to the builder

Field spellings and the exact JSON shape of the block; the JSON-LD context details; the name and options of the CLI
command; where the concept files live; how "not applicable" is derived outside surveys; how steps B and E are cut into
pull requests; the exact wording of messages.

## Open points for the user

1. Who owns the concept vocabulary: a concept registry in prism-specification (seeded with concepts from partners), or each
   partner's own list that PRISM only links to? (Asked on 2026-11-14; the design assumes the registry, with partner lists
   linkable.)
