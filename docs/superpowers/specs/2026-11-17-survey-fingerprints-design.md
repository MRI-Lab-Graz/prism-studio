# Survey IDs for instruments that are not in the library: fingerprints and applications

Date: 2026-11-17. Status: draft for approval. Brainstormed with the user on 2026-11-17.

## Intent and why

Since the licensing decision (`2026-11-14-template-licensing-decision.md`) the library ships only the templates PRISM may
redistribute (`dass`, `dass21`). Every other instrument (ADS, PHQ-9, ...) is used in projects as a **project-only
template** that cannot be shared. Today such an instrument gets no ID at all: `resolve_survey_sidecar`
(`src/survey_terms.py`) compares a project column with the *library template*, so without a template the answer is
`unknown instrument`, even when the ID is already in the released list (`ids/survey-ids.txt` in prism-specification,
vendored as `official/library/survey/term-ids.txt`). That list holds ID strings only: no wording, no scale.

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
- Same match, same messages in the CLI and in Studio (THE RULE): one function in `src/`, a `spec` command, a thin route.
- A project can use its own fingerprints at once (before acceptance) for itself; they never become official unasked.

Non-goals
- No matching by wording alone (a project that names its columns `q3` instead of `ads03` does not match by finding the
  text). Item key = item key, as today. Revisit if it is wanted; it needs its own decision.
- No automatic judgement that a translation is faithful. A hash cannot tell; the team does.
- No change to scoring: recipes use item keys (`Items: ["KSE01", ...]`), item order is not part of any ID or fingerprint.
- No change to the frozen-ID rule: an accepted ID is released and never deleted or reused.

Anti-goals (would make this a failure even if it works)
- Item text, or anything that lets the text be rebuilt without already having it, ending up in the specification or in
  Studio's repository. See the open licensing question below; **nothing ships before it is answered.**
- An ID that claims "unchanged official item" for an item that is not.

## Constraints

- THE RULE: logic in `src/`, `prism_tools.py spec ...` runs it, Studio only triggers; parity test in
  `tests/test_cli_studio_parity.py`.
- The specification is vendored and hash-locked: the fingerprint file format, the check and the accepted data live in
  prism-specification first (tag, then `scripts/sync_specification.py --tag`). Studio never edits `official/library/`.
- Project data is untrusted (`code/specification/` travels with shared projects): skip and report invalid files, never
  crash; file names come from validated `prism:<slug>` IDs with `re.fullmatch`.
- Session labels and similar are untouched; the DataLad text policy applies to the new JSON files (plain git, not annex).
- Validation reads one current `Specification` (`current_specification()`); a project's local fingerprints must apply to
  that project's run only and never leak into the next project in the same process.

## Approaches considered

1. **Reuse the existing proposal mechanism (chosen).** Local files in `code/specification/` (read by
   `src/spec_overlay.py`), exported by `spec propose`, accepted by the team into a vendored file. Reuses the one path
   terms already use, and gives "local at once, official only on acceptance" for free.
2. Put fingerprints into `survey-ids.txt`. Rejected: one ID per line cannot hold per-language hashes, and it would change
   the freeze check.
3. A separate survey-registry workflow. Rejected: a second pipeline, against the one-implementation rule.

## The design

### Fingerprint (the part the team must confirm)

Per item key, two kinds of hash, so today's messages `changed scale` / `changed wording` survive:

```json
{
  "Task": "ads",
  "Items": {
    "ads03": {
      "Wording": {"en": "<sha256>", "de": "<sha256>"},
      "Scales":  ["<sha256>", "<sha256>"]
    }
  }
}
```

- **Wording hash** (per language): SHA-256 of the item's `Description` in that language after Unicode NFC and whitespace
  collapse (the existing `_collapse` in `src/survey_terms.py`). Case and punctuation are kept.
- **Scale hash**: SHA-256 of the canonical form of the answer codes (the set of `Levels` keys, as strings), `MinValue`
  and `MaxValue`; the same things `_scale_matches` compares today. `Scales` has one hash for the item and one per
  `VariantScales` entry. Level labels are not part of it.
- Not in it: item order, study metadata, notes, references, other languages.
- Equality is exactly what `_scale_matches` and `_item_reason` use today (answer codes compared as strings, min/max as
  given, an integer-valued float counts as that integer); a difference there is a bug to fix in that one function, not a
  second rule. Canonical form = JSON with sorted keys and no whitespace. The file carries `"Version": 1` because the
  accepted format is frozen. An item without a `Description` is matched on its scale alone.
- The language of a column is `Technical.Language` of the sidecar (default `en`, as `resolve` does today); a
  multi-language `Description` is hashed once per language it carries. `add-survey --language` selects one language out of
  a multi-language sidecar, or must equal the language of a single-language one (otherwise an error).
- A column matches an item when its wording hash is in the item's `Wording[language]` and its scale hash is in
  `Scales`. Reasons stay `changed wording`, `changed scale`; new reason `language not registered` when the instrument is
  known but no fingerprint exists for the column's language.

### Files

- Project (local, written by commands): `code/specification/survey/<task>.json`, the format above plus the project's
  claimed IDs. Read by `src/spec_overlay.py` (new loader, same validation style as `load_local_terms`).
- Specification (official): `ids/survey-fingerprints.json`, vendored to
  `official/library/survey/fingerprints.json`. Accepted applications are merged here by the team; the IDs of accepted
  instruments are also added to `ids/survey-ids.txt` (frozen).

### Resolution in `resolve_survey_sidecar`

Three sources: (1) the shipped library template (its fingerprints are *derived*, never stored twice), (2) official
fingerprints (vendored), (3) the project's own `code/specification/survey/<task>.json`. They are **merged per task, item
and language**; on a conflict the higher source wins and the conflict is reported (a local fingerprint never overrides an
official one). So an official English fingerprint plus a local German one work together for one task. A column whose item
no source knows gets `unknown item`; a task no source knows gets `unknown instrument`. Each result says which source
decided it (`library`, `official`, `local`). Local, not-yet-accepted fingerprints count as verified for this project only.

### Commands (all in `src/`, exposed as `spec` subcommands)

```
spec local add-survey   --project <p> --sidecar <sidecar.json> [--language <code>] [--json]
spec local remove       --project <p> <task>                      (existing command, extended)
spec propose            --project <p> --survey <task> [--out FILE] [--open] [--json]
```

- `add-survey` computes the fingerprints from the project's own sidecar and writes the local file. Giving
  `--language` for a task that already has fingerprints adds only that language (a **language application**); a new task
  is an **instrument application**. Both are the same kind of local file.
- `propose --survey` exports the fingerprint file as a proposal (no item text), with a form text telling the team what
  is requested. The existing Contribute page gets a survey option; it only triggers these commands.
- Acceptance is the team's step in prism-specification (a script there validates the file, refuses an ID that exists with
  different fingerprints for the same language, and appends the IDs to `ids/survey-ids.txt`).

### Collisions

Two projects applying for the same task name with different fingerprints: first accepted keeps the ID; the second is told
to use another task name or to apply as a language or variant of the first. The team decides; the tool only reports.

## Open question that blocks building (needs the user, outside the code)

**Is a hash of an item's wording acceptable under the instruments' copyright?** A short item can be guessed and
checked by anyone who has the text, but the text cannot be read from the hash. The user's own framing, "the term URL can
be shared without item text", suggests yes, but it is a licensing ruling, not an engineering one, and the user has said
they want no licensing problems. Until it is answered, only the specification-side file format and the local (project
only) half should be built; nothing is shared.

## Calls I made (the user can overrule)

- A column in a language with no fingerprint gets **no** official term and the reason `language not registered`, not an
  "unverified" ID. It keeps "an ID always means verified" simple; the project can fix it locally with `add-survey
  --language`.
- Matching is by item key only (see non-goals).
- Local files live in `code/specification/survey/`, next to `terms/` and `patches/`.
- The fingerprint is unsalted SHA-256 (a salt would make independent projects unable to match).

## Scope and PRs (my call)

Two pull requests, specification first: (1) prism-specification: the fingerprint file format and version, the validation
and acceptance script, `ids/survey-fingerprints.json`; (2) Studio: the loader, `resolve`, `spec local add-survey`,
`spec propose --survey`, the Contribute page option, the parity test, after syncing that tag.

## Left to the builder

Exact JSON schema and validation messages; hash canonicalization details (stable key order); the wording of the Contribute
page text; how the team's acceptance script is organised in prism-specification; test layout. The Contribute page and
`spec_catalog()` currently only offer biosample, so the survey option is a specification change first (see the notes on
widening beyond biosample).
