# Roadmap: IDs for everything, meaning from anyone

Date: 2026-11-24 (revision 2). Based on the code at vendored prism-specification **v1.5.25**. Each step is a small
release (spec patch version), specification first, then a Studio sync PR.

## The principle (revision 2)

PRISM is not built for one ontology or one consumer. **The interface is the IDs plus the open files**: every
measurement has a stable, resolvable `prism:` ID; its template gives the structure (levels, units, ranges, scoring,
parent instrument); links to vocabularies are optional curation that anyone can write, in PRISM's `mappings/`
or in their own files keyed by PRISM IDs. Exports (SSSOM today) are adapters, never the model.

So the first priority is that **every template of every modality has IDs**. An ID cannot carry meaning by itself
(someone still decides "this item measures that concept"), but everything structural follows from the template.

## Where we are (verified in code)

| Kind of data | IDs | How |
|---|---|---|
| survey | yes (838 shipped, 2,249 released) | derived from templates + recipes, frozen in `term-ids.txt` |
| biosample | yes (27) | shared terms, `terms/biosample/` |
| environment | yes (31) | shared terms, `terms/environment/` |
| biometrics | **no** | `biometrics-fitness.json` columns (`resting_hr`, `grip_strength_left`, ...) have no ID |
| physio, eyetracking, events, others | **no** | not described per column today |

Built on branch `worktree-feat-mappings-in-specification` (not merged): steps 1, 2, 3 (report), 5 (Studio half).

## Steps

### 0. Shared terms for biometrics (spec, then Studio sync) - NEW, first priority
- **Decided (2026-11-24):** biometrics measures are **shared terms**, like biosample analytes (`prism:resting-heart-rate`,
  `prism:grip-strength`), not template-derived IDs. Two templates measuring the same thing share one ID; that is what
  lets data combine across studies.
- **Do (prism-specification):** add the `terms` declaration to `biometrics` in `entities.schema.json` (as
  biosample/environment have; `nonTermColumns` for the ID columns, a `contextField` only if one is needed, e.g. side
  or protocol); create `terms/biometrics/<slug>.json` for the measures of the shipped template; `check_terms` covers them
  without new code. Laterality / protocol variants: a child term (`prism:grip-strength.left`) the way specimens are
  children of an analyte, or a context field; decide on the real columns, not in advance.
- **Studio:** sync the tag. Nothing modality-specific to write: the validator, `terms list|show|coverage|propose`,
  `spec local add-term`, the Contribute page and `export-links` read `term_modalities` from the rules. A test proves a
  biometrics sidecar column resolves to its term, and the coverage report lists biometrics.
- **Done when:** every column of `biometrics-fitness.json` resolves to a term (or is a declared non-term column).

### 0b. Physio, eyetracking, events and the other modalities (design only)
- Decide per kind what is a measurement that needs an ID: e.g. the physio `recording` values (`ecg`, `resp`, `eda`, ...)
  are already a controlled list and are natural shared terms; events and eyetracking may have none. Same mechanism as
  step 0 (a `terms` declaration plus term files), no new code path. A short design note first, no code.

### 1. Mappings in the `Specification` - DONE (branch, `2f9d1b6f`)
`Specification.mappings` / `mappings_for(id)`, official + the project's own for that run only, official wins.

### 2. Exports - DONE as one adapter (branch, `987feb3e`)
`terms export-links` writes SSSOM (`SameAs` -> `skos:exactMatch`, `Measures` -> the SKOS match of `Match`). It is one
export among possible others (JSON-LD, OWL), added only when a consumer needs it. Open: validate the file with an SSSOM
tool; a `license` in the header (which licence applies to the specification?).

### 3. Mapping coverage - report DONE (branch, `12b2aec6`); data open
`terms coverage`: today biosample 10 linked / 8 via parent / 9 none, environment 0/0/31, survey 63/0/775.
Open: the concepts that matter first (Barbara / AIDA-Path), the links themselves (spec repo), reviewing the 63 DASS
links (`unreviewed` -> `reviewed`), a coverage check in the spec CI once the set is agreed. Links may also live in a
partner's own repository keyed by PRISM IDs; PRISM does not need to host them.

### 4. One fingerprint implementation (spec), Studio loads it
`scripts/specification/fingerprint.py` (text SHA-256 for stubs) and `src/survey_fingerprints.py` (wording + scale hashes)
differ. One definition with test vectors in the spec repo, Studio loads it. Needs decision A.

### 5. Survey ID lifecycle - Studio half DONE (branch, `a6b14840`); spec half open
Studio reads `deprecated.json` (Status, ReplacedBy; a deprecated released ID may leave the template; sync maps
`ids/survey-deprecated.json`). Spec repo: the file, `check_library` (ReplacedBy released, no line lost),
`check_mappings` warning on a link to a deprecated ID. Open in Studio: `terms resolve` should name the replacement.

### 6. Accepted records for instruments that cannot ship (spec + Studio)
`fingerprints/<task>.json` (hashes only), `check_fingerprints.py`, IDs appended on acceptance. Depends on 4 and decision B.

### 7. `TermURL` clean-up (spec + Studio)
Mark legacy; maintainer-only `--propose` turns existing `TermURL`s into `relatedMatch` proposals; the editor shows ID
and mappings instead.

### 8. A canonical projection of a dataset (design after 0 and 3 run on real data)
With every column carrying an ID that resolves to its template, the projection is small: one long table (subject,
session, ID, value, unit) for every modality, no per-modality code. A consumer joins it with whatever links it
uses. Design first, after Barbara has used IDs + export on real data.

### 9. Docs
README, ReadTheDocs, `docs/ONTOLOGY_READY.md` (IDs for every modality, `coverage`, `export-links`, lifecycle). One pass
at the end.

## Decisions

- **Decided:** biometrics = shared terms (step 0).
- **A. Fingerprint normalisation:** keep Studio's (NFKC, punctuation to space; vectors from the current code) or the
  spec script's (NFC, symbols removed)? Recommended: Studio's, no existing hash changes.
- **B. Hash licensing:** may hashes of restricted instruments be published? Gates step 6 only.
- **C. Library scope:** 23 survey templates ship; the 2026-11-14 decision said DASS only. Licence basis of the rest?
- **D. Spec repo work:** steps 0, 3 (data), 4, 5 (spec half), 6 start in prism-specification: yours or mine?
- **E. Biometrics variants (step 0):** left/right and protocol as child terms or as a context field; decided on the
  real columns.

## Suggested sequence

Review + merge the branch (1, 2, 3 report, 5 Studio) -> 0 (biometrics terms) -> 3 data with Barbara -> 0b design ->
5 spec half -> 4 -> 7 -> 6 (after B) -> 8 -> 9.

## Process (per CLAUDE.md)

TDD, a CLI command and a parity test per Studio-facing step, one `/code-review` and one `ponytail-audit` per finished
branch. One chat per step; this file is the handoff.
