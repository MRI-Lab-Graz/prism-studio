# Instrument IDs: who gets one, and what stays private

Design note. Status: agreed, not yet implemented.

## The ID

An instrument ID is `prism:<slug>`; its items are `prism:<slug>.<item>` (for example `prism:ads` and
`prism:ads.ads01`). The ID carries **no modality**: the modality is a property of the term (the folder
`terms/<modality>/`), and an ID never changes once released. A hand-made `prism:survey:ads` form is not valid.

IDs are listed in `ids/survey-ids.txt`, frozen, added by pull request. The IRI form is
`https://w3id.org/prism-specification/<slug>` (redirect registered with w3id.org; the ID stays `prism:<slug>`).

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
