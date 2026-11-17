# Survey IDs for instruments that are not in the library: fingerprints and applications

Date: 2026-11-17. Status: **revision 2, draft for approval.** Revision 1 was approved and its local half (Phase 1) is built
on `feat/survey-fingerprints`, unmerged. Revision 2 adds the structure of IDs and mappings around it (section "The
specification structure") and changes four fingerprint details (marked **rev 2**). Phase 1 needs a fix pass for those
before it merges.

## Intent and why

Since the licensing decision (`2026-11-14-template-licensing-decision.md`) the library ships only the templates PRISM may
redistribute (`dass`, `dass21`). Every other instrument (ADS, PHQ-9, ...) is used in projects as a **project-only
template** that cannot be shared. Before this work such an instrument got no ID at all: `resolve_survey_sidecar`
(`src/survey_terms.py`) compared a project column with the *library template*, so without a template the answer was
`unknown instrument`, even when the ID was already in the released list (`ids/survey-ids.txt` in prism-specification,
vendored as `official/library/survey/term-ids.txt`). That list holds ID strings only: no wording, no scale.

The larger aim is PRISM as a neutral base for reasoning and ontologies (the AIDA-Path discussion): data carries IDs,
meaning lives in sourced mapping files. A mapping can only point at an ID, so an instrument without an ID cannot be
reasoned about. Revision 2 also makes sure the IDs and mappings can be read by tools outside PRISM.

The user wants:

1. A project-only (possibly copyrighted) survey can **apply** for an official ID. It is never included automatically.
2. What is shared is the ID plus a **fingerprint** per item and language, never item text.
3. A second project using the same instrument matches its items against the fingerprints. Its template does not have to
   be identical to anyone else's, only the items it claims.
4. Languages are equally valid. Adding a language to an existing instrument is its own application, which the PRISM team
   adds.

## Goals, non-goals, anti-goals

Goals
- An item of a project-only instrument can carry an official `prism:<task>.<item>` ID once the team has accepted the
  application, verified by fingerprint, without any item text leaving the project.
- **rev 2:** Every ID, of every modality, has a record of the same shape, an IRI, and a lifecycle (an ID never changes
  meaning; it is retired and replaced).
- **rev 2:** Mappings use the standard vocabulary (SKOS match relations, SSSOM export), so a reasoner can use them
  without PRISM code.
- Same match, same messages in the CLI and in Studio (THE RULE): one function in `src/`, a `spec` command, a thin route.
- A project can use its own fingerprints at once (before acceptance) for itself; they never become official unasked.

Non-goals
- No automatic judgement that a translation is faithful. A hash cannot tell; the team does.
- No change to scoring: recipes use item keys (`Items: ["KSE01", ...]`), item order is not part of any ID or fingerprint.
- No reasoner, no disorders or criteria in PRISM (unchanged).
- ~~No matching by wording alone.~~ **rev 2:** reversed for the official list, see "Discovery".

Anti-goals (would make this a failure even if it works)
- Item text, or anything that lets the text be rebuilt without already having it, ending up in the specification or in
  Studio's repository. See the open licensing question below; **nothing ships before it is answered.**
- An ID that claims "unchanged official item" for an item that is not.
- **rev 2:** An ID whose meaning changes over time, or a project-local name that can be mistaken for an official ID.

## Constraints

- THE RULE: logic in `src/`, `prism_tools.py spec ...` runs it, Studio only triggers; parity test in
  `tests/test_cli_studio_parity.py`.
- The specification is vendored and hash-locked: record formats, the IRI base, the mapping format, the fingerprint
  format, the checks and the accepted data live in prism-specification first (tag, then
  `scripts/sync_specification.py --tag`). Studio never edits `official/library/`.
- Project data is untrusted (`code/specification/` travels with shared projects): skip and report invalid files, never
  crash; file names come from validated IDs with `re.fullmatch`.
- The DataLad text policy applies to the new JSON/TSV files (plain git, not annex).
- Validation reads one current `Specification` (`current_specification()`); a project's local fingerprints apply to that
  project's run only and never leak into the next project in the same process.

## Approaches considered

1. **Reuse the existing proposal mechanism (chosen).** Local files in `code/specification/` (read by
   `src/spec_overlay.py`), exported by `spec propose`, accepted by the team into a vendored file. Reuses the one path
   terms already use, and gives "local at once, official only on acceptance" for free.
2. Put fingerprints into `survey-ids.txt`. Rejected: one ID per line cannot hold per-language hashes, and it would change
   the freeze check.
3. A separate survey-registry workflow. Rejected: a second pipeline, against the one-implementation rule.

For the mapping format (rev 2):

1. **Keep the JSON authoring format, rename to SKOS, export SSSOM (chosen).** Small change to the 8 existing files;
   outside tools get the standard.
2. Write SSSOM TSV directly. Rejected for now: `ValueRules` and `Levels` have no SSSOM equivalent and would need a second
   file anyway.
3. Keep the PRISM-only field names. Rejected: `SameAs` reads as `owl:sameAs` (logical identity), which a reasoner would
   use to merge our measurement with the external concept.

## The specification structure (rev 2)

What the specification holds today: biosample and environment **term records** (`official/library/terms/<modality>/`,
fields `TermID`, `Label`, `Description`, `Status`, ...); survey IDs as **bare strings** derived from template keys
(`term-ids.txt`); **mappings** (`official/library/mappings/`, `SameAs` only, 8 biosample files; `vocabularies.json`
registers SNOMED, LOINC, ChEBI, NCIt); and **`TermURL`**, a free link inside templates. Five changes:

### 1. One record shape for every ID

A survey item gets a record like every other term: `TermID`, `Instrument`, `ItemKey`, `Status`, plus `ReplacedBy`
(below) and, for instruments outside the library, its fingerprint. The fingerprint is therefore not a file type of its
own: it is the content of a survey item record, and the only content a copyrighted item needs. Records of library items
are derived from the template (never stored twice); records of accepted applications are stored. `term-ids.txt` stays as
the frozen index.

### 2. Lifecycle: an ID never changes meaning

`Status` gains `obsolete`, and a record may carry `ReplacedBy: <ID>` (OBO practice). A substantive change to an item
(wording in a registered language, or its scale) means a new ID; the old record becomes `obsolete` with `ReplacedBy`.
Mappings to an obsolete ID are reported by the mapping check. The fingerprints detect such changes; whether a change is
substantive (a typo fix is not) is the team's ruling at acceptance.

### 3. `prism:` is an IRI

The specification declares the prefix: `prism:` = `https://w3id.org/prism/` (the w3id redirect is registered by the
team). `prism:ads.ads03` is then `https://w3id.org/prism/ads.ads03`. No ID string changes. Resolving the IRI to a page
is later work; declaring it now makes every ID usable in RDF, OWL and SSSOM from the start.

### 4. Mappings in SKOS terms, exported as SSSOM

- `SameAs` becomes `exactMatch`; `Measures` closeness uses `exactMatch`, `broadMatch`, `narrowMatch`, `relatedMatch`
  (the same four values under their SKOS names). Direction ("higher = more") stays a PRISM field.
- Every mapping carries `Author` and `Justification` (SSSOM's `mapping_justification`, e.g. manual curation). This
  answers "who mapped it" without a separate reviewer system.
- A `mappings export --sssom` command writes the SSSOM TSV. `ValueRules` and `Levels` stay PRISM's own; they have no
  standard equivalent.
- Survey items of standard instruments often have LOINC codes; `exactMatch` to LOINC is the first curation task.

### 5. `TermURL` is retired into mappings

Meaning stated in two places drifts. The mapping check turns an existing `TermURL` into a `relatedMatch` **proposal**
(never applied unasked); new templates get none. The template editor shows the PRISM ID and its mappings instead.
`TermURL` stays readable in old templates.

## Fingerprints

### The fingerprint (the part the team must confirm)

Per item key, two kinds of hash, so the messages `changed scale` / `changed wording` survive:

```json
{
  "Version": 1,
  "Task": "ads",
  "Items": {
    "ads03": {
      "Wording": {"en": "<sha256>", "de": "<sha256>"},
      "Scales":  ["<sha256>", "<sha256>"]
    }
  }
}
```

- **Wording hash** (per language): SHA-256 of the canonical form of the item's `Description` in that language **and,
  rev 2, its level labels in that language** (code → label). Labels belong here, not in the scale hash, because they are
  language text; and they must be hashed, because a reversed scale (1 = "never" vs 1 = "always") has the same codes but
  flips every `ValueRule`.
- **Text normalization (rev 2):** Unicode NFKC, casefold, typographic quotes and dashes mapped to ASCII, punctuation
  removed, whitespace collapsed. Two labs typing the same item from paper must match; a false match is unlikely because
  the scale must match as well. (Revision 1: NFC and whitespace only.)
- **Scale hash** (language-free): canonical form of the answer codes (as strings), `MinValue` and `MaxValue`. `Scales`
  has one hash for the item and one per `VariantScales` entry.
- Not in it: item order, study metadata, notes, references, other languages.
- Equality is exact, and therefore stricter than the library path's `_scale_matches` / `_item_reason`: a missing
  `Levels`, `MinValue` or `MaxValue` is a value of its own. An integer-valued float counts as that integer. Canonical
  form = JSON with sorted keys and no whitespace. `"Version": 1` stays, because nothing has been shared yet; it becomes
  frozen with the first accepted application. An item without a `Description` is matched on its scale alone.
- The language of a column is `Technical.Language` of the sidecar (default `en`). `add-survey --language` selects one
  language out of a multi-language sidecar, or must equal the language of a single-language one.
- Reasons: `changed wording`, `changed scale`, `language not registered`.

### Names before acceptance (rev 2)

A project-only instrument resolves to **`local:<task>.<item>`**, never `prism:`. Two labs can register different
instruments under the same task name; a `prism:` name would collide and would look official to any mapping written
against it. The mapping check refuses a non-`prism:` ID. On acceptance the team creates the `prism:` record; the
project's `local:` names are then resolved to it. (Revision 1 and Phase 1 used `prism:` with `source: local`.)

### Files

- Project (local, written by commands): `code/specification/survey/<task>.json`, the format above. Read by
  `src/spec_overlay.py` (`load_local_survey`).
- Specification (official): the survey item records (section 1), holding the fingerprints of accepted applications.
  Exact location is the specification PR's call (`ids/` or `terms/survey/`). Accepted IDs are appended to
  `ids/survey-ids.txt` (frozen).

### Resolution in `resolve_survey_sidecar`

Three sources: (1) the shipped library template (fingerprints derived), (2) official records, (3) the project's own
file. They merge per task, item and language; the library and official records always win, and a local fingerprint only
decides for a project-only task or for a language the official item lacks. Each result says which source decided it
(`library`, `official`, `local`).

### Discovery (rev 2)

Phase 1 looks an instrument up by the sidecar's `TaskName` and then by item key: it **verifies** a claim, it does not
**discover** one. A second project using ADS under another task name or other keys does not match. The official records
are therefore also indexed **by hash**: `terms resolve` reports "column `q3` matches `prism:ads.ads03`" for a column
whose wording and scale hashes match an official item, whatever its name. A discovered match is a suggestion shown to the
user, never applied unasked (the same rule as session maps). The format needs no change for this; it is a lookup in the
specification-side code.

### Commands (all in `src/`, exposed as `spec` subcommands)

```
spec local add-survey    --project <p> --sidecar <sidecar.json> [--language <code>] [--json]   (built)
spec local remove-survey --project <p> <task>                                                   (built)
terms resolve            <sidecar> [--project <p>] [--json]                                     (built)
spec propose             --project <p> --survey <task> [--out FILE] [--open] [--json]
mappings export          --sssom [--out FILE]
```

- `add-survey` with `--language` for a task that already has fingerprints adds only that language (a **language
  application**); a new task is an **instrument application**.
- `propose --survey` exports the fingerprint file as a proposal (no item text). The Contribute page gets a survey option
  that only triggers these commands.
- Acceptance is the team's step in prism-specification: a script validates the file, refuses an ID that exists with
  different fingerprints for the same language, writes the records and appends the IDs to `ids/survey-ids.txt`.

### Collisions

Two projects applying for the same task name with different fingerprints: first accepted keeps the ID; the second is told
to use another task name or to apply as a language or variant of the first. The team decides; the tool only reports.
With `local:` names (rev 2) the collision can no longer happen before acceptance.

## Open questions (need the user, outside the code)

1. **Is a hash of an item's wording acceptable under the instruments' copyright?** The text cannot be read from the hash,
   but anyone who already has a short item ("I feel sad") can confirm it. That should be put to whoever rules, as stated
   here. Until it is answered, only the specification-side formats and the local (project-only) half are built; nothing
   is shared. If the answer is no, the fallback is undecided: no sharing, or keyed hashes, which would end matching
   between projects.
2. **w3id registration** of `https://w3id.org/prism/`: who in the team owns it.

## Calls I made (the user can overrule)

- A column in a language with no fingerprint gets **no** term and the reason `language not registered`, not an
  "unverified" ID.
- Local files live in `code/specification/survey/`, next to `terms/` and `patches/`.
- The fingerprint is unsalted SHA-256 (a salt would make independent projects unable to match).
- rev 2: `local:` as the prefix for names before acceptance; NFKC + casefold + punctuation removal; labels in the wording
  hash; `https://w3id.org/prism/` as the IRI base; JSON stays the mapping authoring format, SSSOM is an export.

## Phases and PRs

1. **Phase 1 fix pass (Studio, this branch, before merge):** `local:` prefix, labels in the wording hash, the new
   normalization. Test first.
2. **Specification PR (prism-specification):** prefix declaration; one record shape including survey items; `obsolete` /
   `ReplacedBy`; mapping field renames (`SameAs` → `exactMatch`, SKOS closeness values, `Author`, `Justification`) with
   the 8 existing files migrated; fingerprint format and acceptance script; the hash index for discovery. Tag.
3. **Studio PR after the sync:** official records in `resolve`, discovery, `spec propose --survey`, `mappings export
   --sssom`, `TermURL` retirement in the editor and the check, Contribute page option, parity test.
4. **First real use:** ADS as an instrument application, then a language application. Gated on open question 1.

## Left to the builder

Exact JSON schemas and validation messages; the list of punctuation characters; where the survey records live in
prism-specification; SSSOM column subset; the Contribute page wording; test layout. The Contribute page and
`spec_catalog()` currently offer only biosample, so the survey option is a specification change first.
