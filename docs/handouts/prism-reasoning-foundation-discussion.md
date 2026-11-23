# PRISM as a neutral foundation for reasoning and ontologies: what changed, what is open

*Discussion starter, 17 November 2026 (revision 2). The idea of a machine-readable layer between data and diagnostic
criteria is Barbara's (AIDA-Path). This note says what PRISM does now, what we propose to change next, and lists what we
would like to decide together. Everything marked "open" is open; everything marked "proposed" is not built.*

## 1. The idea in one paragraph

PRISM keeps **what was measured** (identity) apart from **what it means** (interpretation). Data, templates and terms
carry only stable, readable IDs. Meaning (this item is about fatigue; an answer of 2 or more counts as "present") lives in
separate, sourced mapping files that can disagree with each other and can be replaced without touching any data. PRISM
then stays neutral: it holds no disorders, no criteria and no symptom list, and a reasoner such as AIDA-Path can sit on
top of it.

A mapping can only point at something that has an ID, and a reasoner outside PRISM can only use our files if the IDs and
mappings follow standard formats. The changes below are about both: every measured thing gets a name that is stable,
shareable and free of copyrighted text, and the files become readable without our code.

## 2. What we changed (built)

| Before | Now |
|---|---|
| The questionnaire library lived inside Studio and had no stable identity. | The **library, recipes and ID list moved into the specification repository** (prism-specification, release **v1.5.12**), versioned and hash-locked. Studio ships one release of it, offline; a later opt-in "library update" is designed, not built. |
| Items and scores had no global name. | Every item and score **in the library** has a frozen ID: `prism:<task>.<item>` (an item, for example `prism:kse.kse04`) and `prism:<task>.score-<name>` (a score). The same rule exists for the other modalities where terms are defined (for example `prism:cortisol.saliva`). **2,249 survey IDs are released.** |
| `TermURL` pointed anywhere. | The PRISM ID is shown next to `TermURL` in the template editor. `TermURL` stays an external link; the PRISM ID is the internal name. |
| No way to say "this is the same as SNOMED / LOINC". | A **`mappings/` layer** with four fields (section 3) and a checker. External vocabularies (SNOMED, LOINC, ...) are registered as data (`mappings/vocabularies.json`), never hard-coded. |
| A language version was a separate template. | **A language is a property of the template**, never part of its name. The German DASS is now a language of `dass21` with the same IDs. Each language can carry its own licence (`Study.LicenseByLanguage`). |
| Third-party scales of unclear licence were in the library. | Only templates with a documented, redistributable licence ship. 19 German templates from the Open Test Archive (ZPID, CC BY-SA 4.0) were added, each with its licence evidence, authors, citation, quality criteria text and a scoring recipe where the authors state one. |
| An instrument that cannot ship (copyright) had no identity, so nothing could be mapped to it, and two projects using it could not tell they held the same items. | A project can register **fingerprints** of an instrument: hashes of each item's wording (with its answer labels) and answer scale, per language, **never the text**. Items are matched one by one, in any order, and every language counts equally. It works **inside one project**, via the commands `spec local add-survey`, `spec local remove-survey` and `terms resolve --project`; it is merged into Studio's main branch but not yet released. Until an instrument is accepted by the PRISM team, its items carry a project-local name (`local:<task>.<item>`) that can never be mistaken for an official ID. Sharing fingerprints between projects is designed, not built (sections 5 and 6). |

State today: 23 templates, 113 recipes, 2,249 survey IDs. **Mapped so far: only eight lab values** (SameAs to
SNOMED/LOINC). No questionnaire item is mapped to a concept yet; that is the first piece of curation work.

### How the fingerprint matching works

- **What is hashed.** The wording of an item and its answer labels, per language (case, quote style, punctuation and
  spacing are ignored, so two labs typing the same item from paper still match), and, separately, its scale (answer codes,
  minimum, maximum). Item order and study metadata are not hashed. Labels are hashed because a reversed scale (1 = "never"
  against 1 = "always") has the same codes but turns every rule such as "2 or more = present" around.
- **What a match means.** Exact. A reworded item or a changed scale code does not match, and the reason is reported
  (`changed wording`, `changed scale`, `language not registered`).
- **Library first.** For an instrument in the library, the library decides. A project's own fingerprints decide only for a
  project-only instrument, or for a language the library item lacks. Each result says where it came from.
- **Adding a language** to an existing instrument is its own application, which the PRISM team adds.

## 3. The four mapping fields (built) and what we propose to change

| Field | Says | Example |
|---|---|---|
| `SameAs` | this ID is the same thing as an entry in another vocabulary | `prism:testosterone` = a SNOMED / LOINC entry |
| `Measures` | this item or score is about a concept: how close (`exact`, `broader`, `narrower`, `related`) and whether a higher value means more or less of it | item 4 of a depression scale: about "fatigue", `related`, higher = more |
| `ValueRules` | a named, sourced rule that reads a value as a state (`present`, `absent`, ...); several rules may coexist and disagree | "answer of 2 or more counts as present (source: manual)" |
| `Levels` | the same for one answer value | answer 3 = "nearly every day" = state `present` |

A script checks every mapping file: the ID must exist, the vocabulary must be registered, the types must be right. PRISM
keeps no list of symptoms or disorders. **A mapping should point only at official IDs**: a mapping to a project-local name
would break the day that instrument is registered, so the check refuses it.

**Proposed changes to this layer (not built, section 5 asks you):**
- A command **exports the mappings as SSSOM**, the standard format for sharing mappings. In the export, `SameAs` is written
  as `skos:exactMatch` (not `owl:sameAs`, which would make a reasoner merge our measurement with the external concept),
  and the four closeness values of `Measures` as `exactMatch`, `broadMatch`, `narrowMatch`, `relatedMatch`. Who made a
  mapping and when is already in the files (`Source`, `Checked`, `Status`); the export turns them into SSSOM's author, date
  and confidence. The field names in our files stay. `ValueRules` and `Levels` have no standard equivalent and stay
  PRISM's own.
- `TermURL` is retired into mappings: meaning stated in two places drifts. An existing `TermURL` becomes a `relatedMatch`
  proposal, never applied unasked.

## 4. What PRISM deliberately does not contain

Disorders, diagnostic criteria, generators, the combination rules of criteria, similarity measures, the symptom token list
itself. Three tests for every new field:

1. It must be useful to a second user who does not use AIDA-Path (harmonising two depression scales through their
   factors, cohort search, meta-analysis).
2. The specification names no disorder or symptom; only mapping files do, and only by pointing at external vocabularies.
3. It carries no copyrighted text. A fingerprint holds hashes only.

## 5. Proposed structure of IDs (not built) and open questions

### How an ID should behave (proposed)

- **One record shape for every ID.** Biosample and environment terms are stored records (ID, label, description, status).
  Survey IDs have the same shape, but it is derived from the templates and recipes and only the ID itself is stored. An
  instrument accepted by application (not in the library) gets stored records, and the fingerprint is their content.
- **An ID never changes meaning.** A substantive change to an item gets a new ID; the old one is `deprecated` with a
  `ReplacedBy`, the same words terms use today. Mappings to a deprecated ID are reported. A typo fix is not substantive;
  the PRISM team rules on it.
- **The hash is defined once**, in the specification, with test vectors, so another tool such as AIDA-Path can compute the
  same fingerprint.
- **`prism:` is a web address.** `prism:ads.ads03` is `https://w3id.org/prism-specification/terms/survey/ads.ads03` (terms already work this way, for example `prism:cortisol`). No ID changes; RDF, OWL and
  SSSOM tools can then use every ID from the start.
- **Discovery.** A second project using a copyrighted instrument under other column names is told "this column matches
  `prism:ads.ads03`" by its hashes. It is a suggestion shown to the user, never applied unasked.

### Questions

1. **Tokens.** Publish the AIDA-Path tokens as a vocabulary with stable URLs (fast, keeps AIDA-Path's meaning exact), or
   link each token to SNOMED / HPO or similar (useful beyond AIDA-Path)? Or both?
2. **Structure of an instrument (`Structures`, proposed, not built).** Which items belong to which scale or subscale, with
   several published structures side by side (three-factor vs bifactor), optional weights, and `Measures` on the scale as a
   whole. Recipes already know which items are summed, but a recipe is one way to compute a number, not the structure. Are
   `Parts`, `Members`, `Weights` and a three-value `Kind` (reflective / formative / grouping) what an ontology needs?
3. **Derived values.** A symptom like weight loss needs a change between two sessions. A new kind of ID, a recipe for
   non-survey data, or outside PRISM?
4. **Other modalities.** The same mechanism fits biosamples, environment, physio, biometrics and participants, but
   participants, biometrics and physio have **no IDs yet**; without an ID there is nothing a mapping can point at. Which
   first? (Participants: most studies have it.)
5. **From data to a reasoner.** A per-participant export giving each ID its value and its state under a chosen rule:
   present, absent or **missing** (missing is never absent). Does that match what AIDA-Path's recommender needs as input?
6. **Curation.** Who maps items to tokens and who reviews? With author and justification on every mapping, is
   `Status: reviewed` enough, or do we need named reviewers? A first small test case: the fatigue items of a few depression
   scales, plus `exactMatch` to LOINC for the items that already have LOINC codes.
7. **Licence and credit.** A licence file in the AIDA-Path repository would let both projects reuse each other's parts. How
   should mapping files credit their authors, and how is the joint work published?
8. **Where the line is.** If a grouping across instruments defines a clinical picture (a DSM criterion), we say it belongs
   to the reasoning model, not to PRISM. Is that the right split for AIDA-Path?
9. **Standard formats.** Does AIDA-Path (or any reasoner you use) read SSSOM, SKOS or a `https://w3id.org/prism-specification/` IRI, or
   do you need something else? The export translates our field names, so nothing in the files changes, but the translation
   (for example `SameAs` to `skos:exactMatch`) should be one you agree with.
10. **Hashes of copyrighted items (gates all sharing).** Is a hash of an item's wording acceptable under the instruments'
    copyright? The text cannot be read from the hash, but anyone who already has a short item can confirm it. If yes,
    fingerprints can be shared and a second project finds the same items. If no, the fallback is undecided: no sharing at
    all, or keyed hashes, which would end matching between projects.
11. **Mappings for instruments we cannot ship.** Can a mapping file (an ID plus a concept, no item text) for a non-shareable
    instrument be published? That would let AIDA-Path use, say, ADS items without PRISM holding the text.
12. **Applications.** Who reviews an application to register a new instrument, or a new language of an existing one?
    Proposal: the PRISM team, by application; nothing is added automatically. The web addresses
    (`https://w3id.org/prism-specification/...`) are the agreed form but are **not registered yet**, so they do not resolve;
    who in the team submits the registration?

## 6. Not built yet (so nobody is surprised)

- `Structures`.
- The per-participant state export.
- IDs for participants, biometrics and physio.
- The opt-in library update.
- Mapping any questionnaire item.
- The structure changes of sections 3 and 5 (stored records and lifecycle for survey IDs, IRI, the single hash definition,
  SSSOM export, retiring `TermURL`). Design: `docs/superpowers/specs/2026-11-17-specification-structure-design.md`.
- **Sharing fingerprints**: proposing them to the PRISM team, the official fingerprint list in the specification,
  discovery by hash, the Studio page for it, and the application process. Only the per-project half exists, and it is not
  released yet.

Nothing here is a reasoner or a diagnosis, on purpose.

*Longer paper with the AIDA-Path walk-through, step by step:* `docs/handouts/prism-mappings-for-barbara.md`.
