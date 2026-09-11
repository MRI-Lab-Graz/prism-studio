# Modality Contribution Workflow Design

Date: 2026-09-11
Status: Approved, ready for implementation planning
Supersedes: the first draft of this file (repo-extraction-first), revised
after verification against the actual codebase — see "Why the sequencing
changed" below.

## Motivation

This work supports an upcoming Aperture Neuro submission that repositions
PRISM away from "a survey/questionnaire tool" and toward its actual
generalizable principle: **PRISM describes data belonging to a subject as a
data file (any extension) plus a JSON sidecar**. Surveys, biometrics, and
physiological recordings are all just modalities that already exist under
this principle — not the principle itself. The paper should stress this and
downplay questionnaires specifically, while still keeping `sub-`/`ses-`
BIDS-shaped and human-scoped (no generalization of "observation unit" beyond
a human subject in this phase).

The concrete capability that makes this claim credible to a reviewer is that
**outside researchers can contribute a new modality** (skin temperature, or
anything else) and have it validated and merged. That, not repository
topology, is the deliverable.

Per direction from the repo owner: this infrastructure ships *before* the
paper is written or submitted, so the paper describes real, checkable
infrastructure rather than a target architecture.

## Why the sequencing changed

The first draft of this spec made repository extraction — moving the
template/schema library into a separate `prism-template-archive` repo,
consumed via a pinned git submodule — the foundation, with the contribution
workflow built on top. Verification against the codebase found five problems
with that ordering:

1. **`app/schemas/` is half app-internals and cannot move wholesale.** It
   mixes community-extensible modality schemas (`survey` 601 lines,
   `environment` 455, `biometrics` 371, `physio` 332, `eyetracking` 182,
   `events` 144) with core app infrastructure (`entities` 76, `project` 364,
   `dataset_description` 350, `instrument-registry` 59, `recipe.survey` 269,
   `tool-limesurvey` 272). `src/entity_rules.py` loads
   `entities.schema.json` to derive the BIDS filename grammar itself;
   exposing that to community PRs would be a mistake.
2. **`prism-validator` validates datasets, not sidecar pairs.** Its
   interface is `prism-validator /path/to/dataset`. A CI fixture must
   therefore be a minimal valid PRISM *dataset*, not a loose data+sidecar
   pair — a materially larger ask of a contributor than the first draft
   assumed.
3. **`official/library/survey/index.json` is a committed, generated
   aggregate** (1673 lines, built by `src/instrument_registry.py`). Every
   template PR regenerates it, so every pair of concurrent PRs conflicts on
   it. For a many-contributor workflow this is a direct blocker, and the
   first draft did not mention it at all.
4. **Both PyInstaller specs bundle these paths** (`('official', 'official')`
   and `('app/schemas', 'schemas')`). A submodule not cloned `--recursive`
   produces a silently broken frozen build.
5. **The external-library consumption mechanism already exists.**
   `get_effective_library_paths()` in `app/src/config.py` already resolves an
   external library root containing `library/` and `recipe/` via a
   `globalLibraryRoot` app setting, with documented precedence. The
   submodule design reinvented shipping, tested machinery.

None of these kill extraction, but none of them block the contribution
workflow either — the workflow can ship against the existing repo, where 104
survey templates already live in `official/library/survey/`. Extraction's
real payoff (decoupling library release cadence from app release cadence,
keeping community PRs away from app internals) is genuine but not urgent,
and it is far easier to extract a library whose contribution contract has
already been proven by real PRs than to extract first and discover the
contract was wrong.

Hence: **contribution workflow first, in the existing repo; extraction
deferred to phase 2.**

## Phase 1 scope

Everything below lands in the existing `prism-studio` repository.

### 1.1 What is community-extensible

An explicit, documented boundary — this is the part reviewers and
contributors need stated plainly:

- **Open to community PRs**: instrument templates under
  `official/library/<modality>/`, and new modality schemas of the same kind
  as `survey` / `biometrics` / `environment` / `physio` / `eyetracking` /
  `events`.
- **Not open to community PRs**: `entities.schema.json`,
  `project.schema.json`, `dataset_description.schema.json`,
  `instrument-registry.schema.json`, `recipe.survey.schema.json`,
  `tool-limesurvey.schema.json`. These define app behavior, not library
  content. CI should flag PRs touching them as requiring core-maintainer
  review rather than the template-contribution path.

### 1.2 Contribution contract

A PR adding a new instrument template or a new modality must include:

1. `<modality>.schema.json` — a JSON Schema in the same shape as the
   existing modality schemas: field name, datatype, required/optional, units
   where applicable, allowed data-file extensions. (For a new *instrument
   template* rather than a new modality, this step is skipped — the existing
   modality schema already applies.)
2. One example sidecar with real, filled-in fields — not placeholders.
3. **A minimal valid PRISM dataset fixture** exercising the new
   modality/template: `dataset_description.json`, one `sub-XX/` with the
   data file and its sidecar. This is what CI actually runs, and it is
   dictated by `prism-validator`'s dataset-level interface (finding 2). The
   Issue Form generator (§1.5) produces this scaffold so contributors do not
   assemble it by hand.

### 1.3 CI validation

Two required checks:

- **Meta-schema check** — a new schema-for-schemas confirming a submitted
  modality schema is well-formed and follows PRISM conventions (the
  `Study`/`Technical` structural split already used by
  `survey.schema.json`). New, small, lives alongside the existing schemas.
- **Validator check** — run the existing `prism-validator` against the
  minimal dataset fixture from §1.2. Reuses the shipping validator rather
  than reimplementing validation logic.

CI passing is necessary but not sufficient: a maintainer signs off before
merge, catching what no schema check can — semantically wrong units, a
modality duplicating an existing one under a different name, a template
whose response levels are misencoded.

### 1.4 `index.json` regeneration

Contributors do not hand-edit `official/library/survey/index.json`. Instead:

- A CI check rejects PRs that modify it manually, pointing at the generator.
- On merge to `main`, a job regenerates it via the existing
  `write_registry_index(library_dir, index_path)` in
  `src/instrument_registry.py` and commits the result.

Implementation note: the index embeds a `GeneratedOn` timestamp, so a
byte-comparison "is the index current?" check always reports a diff.
Any staleness check must compare ignoring `GeneratedOn`.

### 1.5 Guided contribution path

A GitHub Issue Form (`.github/ISSUE_TEMPLATE/propose-modality.yml`)
following the existing `.github/ISSUE_TEMPLATE/*.yml` pattern, asking per
field (repeatable): field name, datatype, required?, unit, allowed file
extension(s).

A GitHub Action triggered on submission:

1. Parses the structured issue body.
2. Generates a draft modality schema, example sidecar, **and the minimal
   dataset fixture** from a code template.
3. Runs the §1.3 checks against the generated draft.
4. Opens a draft PR, linking the issue. The PR is authored by the Actions
   bot (an Action cannot open a PR as the submitting user); the contributor
   is credited via a `Co-authored-by` trailer on the generated commit.

Contributor and maintainer then iterate on that PR normally, hand-editing
where the generated draft needs correction. No new hosted application; this
uses GitHub's own Issue Forms and Actions.

**Security**: the issue body is untrusted input arriving at a workflow that
holds repository write permission. The Action must never interpolate
`${{ github.event.issue.body }}` (or any issue field) directly into a `run:`
shell step — pass it via an environment variable and parse it in Python.
Generated field names must be validated against a strict pattern before
being written into any schema or filename.

**Scope of the form**: it covers *new modalities* only. New survey
instrument templates already have guided authoring paths — the Excel import
template and the Studio Template Editor — so contributors produce the
template JSON there and open a PR with it; the §1.3 checks apply unchanged.

### 1.6 Documentation reframe

Independent of extraction, and directly serving the paper:
`docs/WHAT_IS_PRISM.md` and `docs/PROJECT_OVERVIEW.md` lead with the
file+sidecar principle and present existing modalities as instances of it,
rather than presenting survey as the flagship. Adds a contributor-facing
page documenting §1.1's boundary and the §1.2 contract.

## Phase 2 (deferred, not designed here)

Library extraction into a separate repository, to be revisited when release
cadence coupling actually causes pain. Recorded so the cost is not
rediscovered:

- Move only the six modality schemas, never the app-internal schemas (§1.1).
- Consume via the existing `globalLibraryRoot` mechanism in
  `app/src/config.py`, not new submodule wiring.
- Resolve PyInstaller bundling for both `.spec` files before any move.
- `official/` is referenced across ~11 Python files with layered fallback
  resolution (app-level configured root → project-local → `app_root/official/`);
  a move is not a simple path rename.

Also deferred: a richer standalone authoring GUI (only if the Issue Form
proves too limited in practice), the Aperture paper rewrite itself, any
university GitLab archival mirror, and generalizing "observation unit"
beyond a human subject.

## Testing

- Meta-schema and validator CI checks each get a should-pass and a
  should-fail fixture, so the gates are proven to catch what they claim.
- The Issue-Form-to-draft-PR Action gets an integration test confirming a
  filled-out form yields artifacts that pass §1.3 — holding the guided path
  and the manual path to one contract.
- The `index.json` regeneration job gets a test covering the
  `GeneratedOn`-insensitive staleness comparison.

## Unrelated bug found during verification

Both `PrismStudio.spec` and `PrismValidator.spec` bundle a `survey_library`
directory that contains zero files. Pre-existing, unrelated to this work,
worth a separate cleanup commit.

## Open items for the implementation plan

- Where the meta-schema lives and whether it is versioned like the modality
  schemas (`stable` / `v0.x` folders).
- Whether the merge-to-`main` index regeneration commits directly or opens a
  follow-up PR (branch protection may forbid the former).
- Whether new-modality proposals warrant a lightweight written-proposal step
  before the schema PR, as `docs/BIDS_SURVEY_MODALITY_PR_DRAFT.md` did for
  the survey modality upstream — likely overkill for uncontroversial
  modalities, possibly valuable for contested ones.
