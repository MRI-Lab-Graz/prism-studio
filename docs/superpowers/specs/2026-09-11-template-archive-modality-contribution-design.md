# Template Archive & Modality Contribution Design

Date: 2026-09-11
Status: Approved, ready for implementation planning

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

Per direction from the repo owner: the actual infrastructure below ships
*before* the paper is written or submitted, so the paper describes real,
checkable infrastructure rather than a target architecture.

## Scope of this design

In scope:
1. Extracting the template/schema library into its own repository.
2. How prism-studio consumes that library.
3. The contribution contract a PR must satisfy to add a new survey template
   or an entirely new modality (e.g. skin temperature).
4. A low-effort, guided contribution path so non-technical contributors
   don't have to hand-author JSON Schema.

Explicitly out of scope (deferred to later phases, not designed here):
- A richer standalone GUI application for the archive repo.
- The actual Aperture paper rewrite.
- Any university GitLab mirror/archival copy.
- Generalizing "observation unit" beyond a human subject.

## 1. Repo split

Two repositories going forward:

- **prism-studio** (existing, unchanged in kind) — the Flask app, CLI,
  validator, converters. Its docs (`docs/WHAT_IS_PRISM.md`,
  `docs/PROJECT_OVERVIEW.md`) stop presenting survey as the flagship modality
  and instead lead with the file+sidecar principle, listing existing
  modalities as instances of it.
- **prism-template-archive** (new, GitHub, same org as prism-studio) — the
  actual content library that PRs land against:
  - `official/library/{survey,biometrics,...}/` (moved from prism-studio)
  - `official/create_new_survey/` (moved from prism-studio)
  - `app/schemas/stable/*.schema.json` and version folders (moved from
    prism-studio)
  - A modality meta-schema (new, see §3) and the CI validation workflow
    (new, see §3/§4)

Hosting: GitHub, not university GitLab, so outside contributors can fork/PR
with a normal GitHub account. (A GitLab mirror for institutional archival
purposes is explicitly deferred — not part of this phase.)

## 2. How prism-studio consumes the archive

prism-studio embeds prism-template-archive as a **git submodule**, pinned to
a tagged release/commit, at the paths that previously held this content
(`official/`, `app/schemas/`). Bumping the pin to a newer archive release is
an explicit, single-line, reviewable commit in prism-studio.

This is a deliberate contrast with the namespace-package merge pattern
documented in this repo's `CLAUDE.md` (`src/` vs `app/src/` dual-tree
drift): a submodule is a real directory checked out at a known commit, not
two trees resolved implicitly at import time, so it cannot develop the same
silent-drift failure mode. No compatibility shim, symlink, or
`load_canonical_module` bridge is needed for this content because it was
never Python import machinery to begin with — it's data files.

## 3. Contribution contract

A PR against prism-template-archive — for a new survey template *or* an
entirely new modality — must include:

1. `<modality>.schema.json` — a JSON Schema in the same shape as the
   existing `app/schemas/stable/*.schema.json` files: field name, datatype,
   required/optional, units where applicable, allowed data-file extensions.
   This is the "BIDS-style spec" contract: contributors describe fields the
   same way `survey.schema.json` / `biometrics.schema.json` already do.
2. One example sidecar (`.json`) with real, filled-in fields — not just
   placeholders.
3. One tiny example data file + its matching sidecar, small enough to live
   in the repo as a fixture.

### CI validation (in prism-template-archive)

Two checks, both required to pass before merge is possible:

- **Meta-schema check**: a schema-for-schemas (new, small, added to the
  archive repo) confirms the submitted `<modality>.schema.json` itself is
  well-formed and follows PRISM's existing schema conventions (e.g. the
  `Study`/`Technical`-equivalent structural split already used by
  `survey.schema.json`).
- **Validator check**: the example data+sidecar pair from item 3 above is
  run through the existing `prism-validator` CLI (already shipped by
  prism-studio, reused here rather than reimplemented) against the new
  schema, proving the schema actually validates something real rather than
  being untestable JSON.

CI passing is necessary but not sufficient. A maintainer still reviews and
signs off before merge — CI can't catch "the units are semantically wrong"
or "this duplicates an existing modality under a different name."

## 4. Guided contribution path (Issue Form + Action bot)

To avoid requiring non-technical contributors to hand-write JSON Schema,
prism-template-archive ships a GitHub Issue Form
(`.github/ISSUE_TEMPLATE/propose-modality.yml`), following the same YAML
Issue Form pattern prism-studio already uses under its own
`.github/ISSUE_TEMPLATE/`. The form asks, per field (repeatable):

- Field name
- Datatype
- Required? (yes/no)
- Unit (optional)
- Allowed file extension(s) for the data file

A GitHub Action, triggered on form submission:

1. Parses the structured issue body.
2. Generates a draft `<modality>.schema.json` and example sidecar from a
   code template using the submitted fields.
3. Runs the CI validation from §3 against the generated draft.
4. Opens a draft PR under the contributor's account with the generated
   files, linking back to the originating issue.

The contributor and a maintainer then iterate on that draft PR normally
(including hand-editing the generated schema if the auto-draft needs
correction). No new hosted application is introduced; this reuses GitHub's
existing Issue Forms and Actions infrastructure entirely.

## Testing

- Meta-schema and validator CI checks get their own test fixtures in
  prism-template-archive: at least one fixture that should pass and one
  that should fail each check, so the CI gate itself is proven to catch
  what it claims to catch.
- The Issue-Form-to-draft-PR Action gets an integration test (or a recorded
  fixture run) confirming a filled-out form produces a schema+example pair
  that passes the CI checks above, so the guided path and the manual path
  are held to the same contract.
- prism-studio gets a smoke test confirming the submodule content resolves
  and loads correctly after a pin bump (catching, e.g., a moved/renamed
  file in the archive breaking a hardcoded path in prism-studio).

## Open items for the implementation plan

- Exact submodule path layout (one `library/` submodule vs. two, mirroring
  today's `official/` + `app/schemas/` split).
- Where the meta-schema itself lives and how versioned (does it get its own
  `stable`/`v0.x` folders like the modality schemas do today?).
- Whether existing survey/biometrics content moves via `git mv` + history
  rewrite into the new repo, or is reseeded fresh (affects whether git
  blame/history for those files is preserved).
