# The specification structure for reasoning: one pull request to prism-specification

Date: 2026-11-17. Status: draft for approval. Detail of "The specification structure" and "Phases and PRs, item 2" of
`2026-11-17-survey-fingerprints-design.md` (revision 2), after reading the real files. **Where this document disagrees
with revision 2, this document wins** (section "Corrections to revision 2").

## Intent and why

PRISM is to be a neutral base for reasoning and ontologies: data carries IDs, meaning lives in sourced mapping files. For a
reasoner outside PRISM (AIDA-Path, SSSOM and OWL tools) to use the specification without PRISM code, three things must
hold: every ID is a record with a lifecycle, IDs are web addresses, and mappings can be exported in a standard format.
For instruments that cannot ship (copyright), the specification also needs the official half of the fingerprints: the
format, the stored records of accepted applications, and the check the team runs on an application.

## What the files do today (verified in the vendored copy, v1.5.12)

- **Records exist for survey IDs already.** `scripts/specification/survey_ids.py::build_survey_registry` builds, for every
  library instrument, item and score, a record `{TermID, Level, Parent, Label, Description, Status: "official"}` in memory
  from the templates and recipes. `official/library/survey/term-ids.txt` (2,249 lines) is the frozen list of the IDs.
  So survey IDs have the same shape as biosample and environment terms; they are derived, not stored.
- **A lifecycle exists.** `scripts/specification/check_terms.py` allows `Status` `official` or `deprecated`, and a
  deprecated term must carry `ReplacedBy`, which must be a term of the registry. It is applied to terms, not to survey
  IDs (all survey records are `official`).
- **Mappings already carry who and when.** `docs/specs/mappings.md`: `Measures` entries have `Source` (who made the
  link), `Checked` (date) and `Status` (`reviewed` / `unreviewed`), plus `Match` (`exact`, `broader`, `narrower`,
  `related`) and `Higher` (`more` / `less`). `SameAs` is `{vocabulary: URL}`. The checker is `check_mappings.py`.
- **Prefixes:** `check_terms.ID_PREFIXES = ("prism", "bids")`. There is no declared base IRI.
- **`TermURL`** is a free link in templates, not checked by any mapping rule.

## Goals, non-goals, anti-goals

Goals
- Survey instruments that are **not in the library** can have stored records (with fingerprints) after the team accepts
  an application; the check and the format are in the specification, so Studio and other tools share one definition.
- The fingerprint hash is defined **once, normatively**, with test vectors, so another tool (AIDA-Path) can compute it.
- A lifecycle for survey IDs, with the same words as terms (`deprecated`, `ReplacedBy`).
- Every ID has an IRI. Mappings export as SSSOM.

Non-goals
- No new fields in mapping files, no migration of the 8 existing mapping files.
- No reasoner, no disorders or criteria. No item text, ever.
- No change to how library IDs are derived or frozen.

Anti-goals
- A second implementation of the hash (it must not be possible for Studio and the specification to disagree).
- An ID whose meaning changes. A change of an item makes a new ID.

## Corrections to revision 2

1. **"One record shape" is mostly already true.** The registry builds the shape for survey IDs. The change is only that
   accepted non-library instruments get **stored** records; library records stay derived and are never stored twice.
2. **`deprecated`, not `obsolete`.** Reuse `Status: deprecated` and `ReplacedBy` exactly as terms do. A survey ID is
   deprecated by an entry in a new small file `ids/survey-deprecated.json` (`{id: {"ReplacedBy": id}}`), because the
   record of a library item is derived from the template and holds no status. `term-ids.txt` still never loses a line.
3. **No `Author` / `Justification` fields.** `Source` and `Checked` already say who and when; `Status: reviewed` is the
   curation signal. The SSSOM export derives `mapping_justification` (manual curation) and the confidence from those.
4. **`SameAs` is not renamed in the JSON.** The SSSOM export writes it as `skos:exactMatch`, and `Match` values
   (`exact`, `broader`, `narrower`, `related`) as `skos:exactMatch`, `broadMatch`, `narrowMatch`, `relatedMatch`. The
   field names stay, the 8 files stay, and the standard form is what the export gives a reasoner. The one-line spec page
   states the translation, so nobody reads `SameAs` as `owl:sameAs`. (If you want the rename anyway, it is 8 files and
   one checker constant; it would be a second, separate change.)

## The changes (all in prism-specification; Studio syncs the tag)

### 1. IRI: already decided, extend it to survey IDs
The base is **`https://w3id.org/prism-specification/`**, decided in `2026-11-11-term-ids-all-modalities-design.md` and built:
`check_terms.NAMESPACE = "https://w3id.org/prism-specification/terms/"` and `check_terms.expand()`, which turns
`prism:cortisol` into `https://w3id.org/prism-specification/terms/biosample/cortisol` by finding the term's file. (Revision 2
proposed `https://w3id.org/prism/`; that was wrong, it ignored this decision and a name that is not ours.) The gap:
`expand()` raises "not a term of this repository" for a survey ID, because survey records are derived and have no file. The
change: `expand()` also accepts an ID of `ids/survey-ids.txt` or of an accepted fingerprint record and returns
`https://w3id.org/prism-specification/terms/survey/<local>`. `specs/identifiers.md` states the rule for every modality in one
place. **The w3id registration does not exist yet** (checked 2026-11-17: `https://w3id.org/prism-specification/` answers 404, there
is no `prism-specification` or `prism` directory in `perma-id/w3id.org`, and no open pull request names it). The IRIs are
valid identifiers today, but they do not resolve. Registering is a pull request to `perma-id/w3id.org` that adds
`prism-specification/.htaccess` (a rewrite from `/prism-specification/terms/<modality>/<local>` to the published page or
file) and a `README.md` naming the contact; whoever submits it is the owner. No ID changes.

### 2. Fingerprints: one normative definition
- `specs/fingerprints.md`: the format (`Version`, `Task`, `Items` with `Wording` per language and `Scales`), what is
  hashed (the revision 2 rules: NFKC, casefold, punctuation to space, whitespace collapsed; wording hash covers the
  description and the answer labels per language; scale hash covers the codes and min/max), and the matching reasons.
- `scripts/fingerprint.py` (stdlib): the **reference implementation**: `normalize_text`, `scale_hash`, `wording_hashes`,
  `fingerprint_sidecar`, `item_matches`. Studio's `src/survey_fingerprints.py` is replaced by a thin load of this script
  (the same way Studio already loads `check_terms` and `schema_patch`): one implementation, as THE RULE asks.
- `tests/fingerprint-vectors.json`: input sidecar fragments and their expected hashes, including the typing variants
  (curly vs straight quotes, case, trailing full stop, non-breaking space), the reversed scale, the string/object/absent
  label shapes and integer-valued floats. Generated **once from the current Studio code** (so the move to the
  specification changes no hash), then fixed. Any other tool proves conformance with the same vectors.

### 3. Stored records for accepted applications
- Location: `fingerprints/<task>.json`, one file per instrument (small reviewable pull requests, no conflicts), vendored to
  `official/library/survey/fingerprints/`. (Revision 1 had one file `ids/survey-fingerprints.json`; one file per task is
  my call.)
- A file is the revision 2 fingerprint file plus, per item, the record fields the derived ones have (`Label` = item key,
  `Status`), and `Instrument` metadata (`Label`, `Description` of the instrument *as name only*, no item text).
- The IDs of accepted instruments are appended to `ids/survey-ids.txt` (frozen) at acceptance.

### 4. The acceptance check
`scripts/check_fingerprints.py` (stdlib, run in CI and by the team on an application): file name equals `Task`; `Task` is
a valid single-segment slug and is not a library task; `Version` is exactly 1; every hash is 64 lowercase hex; every item
key gives a valid ID; no `Wording` language is empty; an application for an existing task may only **add** languages or
scales, never change an existing hash (a changed item is a new ID and a deprecation, point 5); the IDs are not already in
`term-ids.txt` under a different task. The check validates shape; it does not recompute hashes (it has no text).

### 5. Lifecycle for survey IDs
`ids/survey-deprecated.json` as in correction 2. `check_mappings.py` reports a mapping to a deprecated ID (a warning, not
an error, naming the `ReplacedBy`); `check_library.py` verifies `ReplacedBy` is a released ID and that every line of
`term-ids.txt` is still present.

### 6. SSSOM export
`scripts/export_sssom.py` (stdlib): reads `mappings/` and writes the SSSOM TSV (`subject_id`, `predicate_id`, `object_id`,
`mapping_justification` = `semapv:ManualMappingCuration`, `confidence` from `Status`, `author_label` from `Source`,
`mapping_date` from `Checked`, and a header with the `prism:`, `skos:` and vocabulary prefixes). `ValueRules` and `Levels`
are not exported. A `tests/` fixture checks the output on the 8 existing mapping files. Studio exposes it as
`mappings export --sssom` (a thin command, parity-tested).

### 7. `TermURL`
`check_library.py` (or a new small check) lists every `TermURL` in a shipped template as a `relatedMatch` **proposal**
file under `mappings/proposals/` only when the maintainer runs it with `--propose`; nothing is applied unasked. The
template schema marks `TermURL` as legacy in its description (a schema patch release, no break). Studio stops offering
`TermURL` for new fields and shows the PRISM ID and mappings (separate Studio PR).

## Studio PR after the tag (preview, not part of this design's build)
Loads `scripts/fingerprint.py` instead of `src/survey_fingerprints.py`, reads `official/library/survey/fingerprints/`,
adds the `official` source and discovery by hash to `resolve`, `spec propose --survey`, `mappings export --sssom`, the
`TermURL` change in the editor, the Contribute page option and the parity test. The rule that the mapping check refuses a
non-`prism:` ID lives in `check_mappings.py` (it already requires a `prism:` key); the `local:` names are Studio-only.

## Constraints
- stdlib only for every script (the existing rule); the wheel, Docker image and frozen build already carry
  `scripts/specification/`.
- Hash definition changes are never silent: a change needs a new `Version` and new vectors.
- Nothing is published or shared before the licensing question is answered; this pull request adds only the **format, the
  check and the empty directory** for accepted records, not any application.

## Open questions (need the user)
1. **Hash licensing** (gates any real application, not this pull request). Unchanged from revision 2.
2. **Register `https://w3id.org/prism-specification/`**: not registered yet (see section 1). Who submits the pull request to
   `perma-id/w3id.org` and is named as contact (a lab address, not a personal one, is safer), and where the redirect should
   point (the GitHub repository files, or a page later). Decided: the base is `https://w3id.org/prism-specification/`.
3. **Correction 4**: keep the `SameAs` name and translate at export (recommended), or rename now?

## Approaches considered
1. **Specification owns the reference implementation; Studio loads it (chosen).** One definition, vectors for other tools.
2. Both repositories keep a copy and a test proving equality (the `survey_ids.py` precedent). Rejected for fingerprints: it
   is exactly the dual-tree drift CLAUDE.md warns about, and a hash must never differ.
3. Keep the hash only in Studio and describe it in prose. Rejected: another tool could not reproduce it reliably.

## Pull requests
1. **prism-specification** (this design): identifiers page, fingerprint page + script + vectors, check, deprecation file,
   SSSOM export, `TermURL` note. Tag, then `scripts/sync_specification.py --tag`.
2. **Studio** (after the sync): as in "Studio PR after the tag".

## Left to the builder
Exact JSON schema and messages of `check_fingerprints.py`; the SSSOM column order; the wording of the new spec pages;
the list of punctuation characters in `normalize_text` is whatever the current Studio code uses (the vectors fix it).
