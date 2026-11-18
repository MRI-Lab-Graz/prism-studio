# Instrument IDs: who gets one, and what stays private

Design note. Status: agreed, not yet implemented (IRIs and `local:` IDs: last section).

## The ID

An instrument ID is `prism:<slug>`; its items are `prism:<slug>.<item>` (for example `prism:ads` and
`prism:ads.ads01`). The ID carries **no modality**: the modality is a property of the term (the folder
`terms/<modality>/`), and an ID never changes once released. A hand-made `prism:survey:ads` form is not valid.

IDs are listed in `ids/survey-ids.txt`, frozen, added by pull request. The IRI form is
`https://w3id.org/prism-specification/terms/<modality>/<id>` (see "IRIs and `local:` IDs" below; the ID stays `prism:<slug>`).

## One library entry per instrument

The library holds a template for **every** instrument that has an ID, so there is one public place to look an ID up.

| Licence of the instrument | What the library holds |
|---|---|
| Redistributable | the full template: metadata, items, levels, scoring |
| Restricted | a **stub**: citation/DOI, abbreviation, licence, item IDs and item count, response scale (levels), public scoring, and **no item texts** |

A stub is a normal library entry, so a local project that holds its own licensed copy of the items validates
against the same IDs as everyone else.

## The private store

The full item texts of **all** instruments, including the restricted ones, are kept in a private store that only
the maintainer can read. It is never part of this repository, of PRISM Studio, or of a project's `sourcedata/`.
Its one job: before a new ID is handed out, compare the incoming items with what is already known, to decide
whether this is an instrument that already has an ID. The maintainer must hold the right to keep the texts.

## Same ID or new ID

When a survey is added locally:

1. Search the library by name, abbreviation, DOI/citation. A match: use that ID. Two projects using the same
   licensed survey therefore end up with the same ID without the items being shared.
2. No match: send it for review (private store comparison); a new ID is minted only if it is a new instrument.

Rule for "same instrument":

- **Same ID**: a translation whose items correspond one to one (same number, order and meaning) with the original.
  A translation never changes the ID; the language is stated in the template, not in the ID.
- **New ID** (pointing back to the original in its mapping): a short form, added or removed items, a changed
  response scale, or an adaptation that changes the item content.

Because translations share the ID, item IDs are language-independent: `prism:ads.ads01` is item 1 in every language.
Matching therefore uses citation, abbreviation, item count and response scale, never item wording alone.

## Item fingerprints

A stub carries a fingerprint (SHA-256 hash) of every item text, **one per item and per language**, keyed by the item ID:

```json
"prism:ads.ads01": {"de": "sha256:3f9a...", "en": "sha256:b71c..."}
```

- The text is **normalised** before hashing (Unicode NFC, lower case, whitespace collapsed, punctuation removed), by one
  function, so that formatting differences do not change the hash. The text cannot be recovered from the hash.
- The fingerprints are created from the private store by a command, never by hand. Which language a set belongs to is
  recorded; a translation not yet in the store has no fingerprints and can only be matched by review.

How a local survey is linked to an ID:

1. The user's items are hashed locally (nothing is uploaded) and compared with the stubs, item by item.
2. **All items match** one stub: the ID is certain; it is used automatically.
3. **Some or none match** (typo, other edition, short form, new translation): the case goes to the maintainer, who
   decides in the private store (same ID, or a new one). A mismatch never produces a wrong ID; it only costs a review.
   The partial result (how many items match) is shown to help that review.

A hash only confirms text someone already has; it is not a secret and gives away nothing of the licensed content.

## IRIs and `local:` IDs

Design note, status: agreed, not yet implemented. The w3id.org base `https://w3id.org/prism-specification/` is
registered and redirects (302) to this repository, but **deeper paths all land on the front page**. Until the per-term
redirect below is live, nothing may link to a term IRI.

`prism:<slug>` only means something inside PRISM. An IRI gives outside tools a unique, persistent, resolvable identity
(mappings, citations, FAIR). The base stays fixed while the redirect target can move.

### The prefix

`prism:` is defined **once**, as a prefix map (or JSON-LD context) in this repository:

```
prism: https://w3id.org/prism-specification/terms/
```

An ID carries no modality, but the IRI does: `prism:ads.ads01` expands to
`https://w3id.org/prism-specification/terms/survey/ads.ads01`, `prism:cortisol.saliva` to
`.../terms/biosample/cortisol.saliva`. So an IRI is **not** prefix + ID; the modality comes from the term's folder
(`terms/<modality>/`), and the one function that expands an ID looks it up. This only works while an ID is unique
across all modalities; the slug rule must enforce that (it holds today, checked 2026-11-18, but no check exists yet). Templates, terms and mappings keep the
short form; a full IRI is never written into a template. Only exports and mapping files that leave PRISM expand it.

All modalities are treated alike. Survey is only the first one to be built.

### Decisions

1. **Pattern** `https://w3id.org/prism-specification/terms/<modality>/<id>`, the same for every modality. `<id>` is
   the part after `prism:`, including item suffixes. This is the pattern already registered with w3id.org, so no
   reserved-word list is needed: `terms/` is the fixed namespace.
2. **Items** keep the dot form: `<id>` is `<slug>.<item>`, IRI `.../terms/<modality>/<slug>.<item>`.
3. **Official vs local.** Official IDs are `prism:<slug>`; IDs that exist only in one project are
   `local:<slug>` (items `local:<slug>.<item>`). `local:` is never registered, never expanded to an IRI and never
   leaves the project.
   - A `local:<slug>` whose slug is also an official slug is a **warning**: "now official, use `prism:<slug>`".
   - The same check runs when a local term is created (the promotion path): creating `local:x` while `prism:x`
     exists is reported at once.
   - Specification change: a project's local terms (`code/specification/terms/`) are today validated as
     `prism:<slug>`; they become `local:<slug>`.
4. **Redirect rules**: one per modality, all of the form `^terms/<modality>/<id>$` to the file that defines the term
   (no per-term entries; a new modality adds one line). A single regex for all modalities is not possible because the
   repository stores them differently: `terms/<modality>/<id>.json` for biosample and environment,
   `library/<modality>/survey-<slug>.json` for surveys, where the item suffix is dropped and the instrument file is the
   target. For a restricted instrument the IRI resolves to its **stub**, never to full texts.

### What gets an IRI, what does not

| Gets an IRI | Gets none |
|---|---|
| official instruments and their items; biosample and environment terms | project-local (`local:`) IDs |
| schemas (`$id`, today `https://prism.org/schemas/...`, a domain we do not own), with the next schema version bump | data, projects, Studio pages |
| the `prism:` prefix itself, defined once | raw GitHub URLs, the private item store |

### External links

External vocabularies (SNOMED, LOINC, ...) are linked in `mappings/<modality>/*.json` as full IRIs under `SameAs`,
keyed by PRISM ID, checked against `mappings/vocabularies.json`. That is the one style to build on. The bare
`"LOINC": "30522-7"` field in `terms/biosample/` and the short `snomed:123` IDs of `participants.json` (which uses two
different SNOMED bases, probably a bug) move to `mappings/` once the prefix map exists.

### Order

1. This note, plus the prefix definition.
2. Redirect pull request to perma-id (one rule per modality).
3. Schema `$id` change together with the next schema change (a version bump per modality).
4. Only then IRIs in mappings, exports and Studio.
