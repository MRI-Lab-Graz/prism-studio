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

**Scope (decided 2026-11-25):** term IDs are for sociodemographics, survey, biometrics and biosample. This narrows
"every template of every modality" above. Environment already has 31 released IDs; they stay (IDs are never removed).

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

### 0. Shared terms for biometrics - DONE (2026-11-25, specification v1.5.26 and Studio sync)

Built as described below, plus one general rule: in a modality without a context field a flat term may have variants
(`<parent>.<variant>`). Existing biometrics sidecars without `Term` now take part in the term notices.

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

### 0b. Physio, eyetracking, events and the other modalities - DECIDED (2026-11-25): no IDs
Nothing to build. Analysis, should this be reopened: `2026-11-25-ids-physio-events-design.md`.

### 0c. Sociodemographics - open, needs a design
`official/participants.json` (`age`, `sex`, `handedness`, `education_level`, `height`, `weight`, `bmi`, ...) has no
term IDs. IDs are unique across modalities, so `bmi` must reuse `prism:bmi`, not get a second one.

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

### 5. Survey ID lifecycle - DONE (specification v1.5.27 and Studio sync)
`ids/survey-deprecated.json` (`{"prism:old": {"ReplacedBy": "prism:new"}}`, `ids/README.md`; appears with the first
deprecation). `check_mappings` validates it and warns on a link to a deprecated ID; `check_schema_versions` fails when
`survey-ids.txt` loses a line. Studio marks the ID and lets it leave the template.
Open: Studio `terms resolve` should name the replacement; spec CI does not report a released item that left its template
without a deprecation entry; the DASS, demo and SBI-D tests require every released item.

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
- **Decided D (2026-11-25):** Claude does the spec-repo work (steps 0, 3 data, 4, 5 spec half, 6).
- **Decided E (2026-11-25):** biometrics variants are child terms with dot notation (`prism:grip-strength.left`). IDs use
  `-` (never `_`); data columns keep their names and are listed in the term's `Aliases`. Terms for
  `biometrics-fitness.json`: `resting-heart-rate`, `step-test-heart-rate`, `grip-strength` (+ `.left`, `.right`),
  `plank-duration`, `sit-and-reach`, `vo2max-estimated`, `bmi`. Check first that a column resolves to a child term
  without a context field (biosample resolves its children by specimen).

## Suggested sequence

Review + merge the branch (1, 2, 3 report, 5 Studio) -> 0 (biometrics terms) -> 3 data with Barbara -> 0b design ->
5 spec half -> 4 -> 7 -> 6 (after B) -> 8 -> 9.

## Process (per CLAUDE.md)

TDD, a CLI command and a parity test per Studio-facing step, one `/code-review` and one `ponytail-audit` per finished
branch. One chat per step; this file is the handoff.
