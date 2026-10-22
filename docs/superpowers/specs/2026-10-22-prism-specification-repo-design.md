# prism-specification repository (term registry phase 2) — design

Date: 2026-10-22
Status: design agreed in chat; awaiting written-spec review. Nothing built.
Builds on: `2026-10-22-biosample-term-registry-design.md` (phase 1 merged).

## Why

PRISM should grow mainly through other people: new metrics, later new
modalities and rules. Contributors should send a small pull request against
the specification only, without reading or building Studio's code. BIDS works
this way: the specification and its schema live in their own repository, and
the validator reads the rules from the schema, so most specification changes
need no validator code.

Today PRISM's schemas, terms and spec pages live inside `prism-studio`, and
17 of the 19 schema commits since April also changed Python code. The split
gives contributors a clean place now; moving rules from Python into the schema
(later) is what makes more and more changes possible from outside without code.

## Goals

- A new public GitHub repository, `MRI-Lab-Graz/prism-specification`, holding the
  PRISM specification: community schemas, their archive, the term registry and
  the spec pages.
- A new metric is proposed as a data-only pull request there, prepared by
  Studio (`terms propose`), reviewed by a person, merged, released.
- Studio keeps working offline and unchanged for everything that reads these
  files today: it carries a plain copy from a tagged release.
- One implementation of every check: the data checks move with the data.

## Non-goals

- Moving the validator. It is ~22,600 lines (53-file import closure) of rule
  logic and stays in `prism-studio` (it already ships separately as the
  `prism-validator` wheel and Docker image).
- Adopting the BIDS YAML schema format or `bidsschematools`.
- Moving the instrument library (`official/library/survey`, `biometrics`).
  It carries third-party licences and has its own, separate split plan.
- A reader package in the new repo (term/schema loading stays in Studio's
  `src/`) — revisit once another tool needs it.
- Moving rules from Python into `x-prism` annotations (later step, see
  "Afterwards").

## Anti-goals

- A git submodule: GitHub ZIP downloads omit submodules, so a ZIP of Studio
  would have no schemas (the repo already lost Windows/ZIP installs to
  symlinks, see CLAUDE.md).
- Two editable copies. After the move, Studio's copy is never edited by hand;
  the drift check fails if it is.
- Studio needing network access at run time or build time beyond the sync.

## What moves, what stays

Moves (with history, `git filter-repo` on these paths):

| From `prism-studio` | To `prism-specification` |
|---|---|
| `app/schemas/stable/` community schemas: survey, biometrics, biosample, environment, events, eyetracking, physio, plus `entities` and `dataset_description` | `schemas/stable/` |
| `app/schemas/archive/` | `schemas/archive/` |
| `app/schemas/v0.1/`, `app/schemas/v0.2/` (the community files in them) | `schemas/v0.1/`, `schemas/v0.2/` |
| `official/library/terms/` | `terms/` |
| `docs/specs/*.md` (spec text belongs with the schema) | `specs/` |
| `scripts/ci/check_schema_versions.py` | `scripts/check_schema_versions.py` |
| `check_registry` (+ its tests) from `src/term_registry.py` | `scripts/check_terms.py` |
| `scripts/generate_schema_reference.py` | `scripts/generate_schema_reference.py` |

Spec pages link to schema files with repo-relative paths
(`../../app/schemas/stable/...`); in `prism-specification` they point at
`../schemas/stable/...`, and the generator writes the new form. Studio's
offline Specifications page must still resolve them (builder: rewrite on
sync or resolve both forms; pick one and test it).

Stays in Studio (app-internal formats, the existing
`RESTRICTED_SCHEMA_FILENAMES` split minus the two spec files above):
`project`, `recipe.survey`, `tool-limesurvey`, `instrument-registry` schemas,
`citation_cff/`, and their `v0.2` copies. `entities` and `dataset_description`
move but keep core-maintainer review through `CODEOWNERS` in the new repo
(the "restricted" idea carries over).

Studio keeps `load_registry`, `find_term`, `resolve_column` (the validator
uses them).

## How Studio carries the specification

- **Same paths as today.** The sync writes the files back to
  `app/schemas/...`, `official/library/terms/` and `docs/specs/`, so the
  validator, `schema_manager`, the wheel, the Docker image, the PyInstaller
  build and the offline Specifications page (`app/src/web/spec_docs.py`) need
  no change.
- **Lock file** `schema.lock.json` at the repo root: source repo, tag, commit,
  and a sha256 per vendored file.
- **Sync:** `python scripts/sync_schema.py --tag <tag>` downloads the tagged
  source archive from GitHub (stdlib `urllib` + `tarfile`; only
  `github.com/MRI-Lab-Graz/prism-specification` URLs), writes the files, rewrites the lock.
  It is the only way the copy changes.
- **Drift check** in Studio CI (replaces the "Modality schema versions" job):
  every vendored file matches its hash in the lock, and no unlisted file sits
  in a vendored folder. Stdlib only.
- The check scripts (`check_terms.py`, `check_schema_versions.py`) are
  vendored too, to `scripts/schema/`, locked like the data: Studio runs the
  same code (`terms propose` checks its output before anything is sent),
  without a second implementation.
- Studio pins one tag at a time; a release notes the schema tag it carries.

## Proposing a metric (user 0)

1. The validator notice (phase 1) says the metric is not official and offers
   sharing.
2. `prism_tools.py terms propose <sidecar.json> <column> [--project <dir>]`
   (and the Studio "Share" button next to the notice, a thin adapter) builds
   the term file(s) from the sidecar column: parent and child, `Label` and
   alias = the user's column name, `Units`, ranges, `SpecimenType`. It shows
   the result and states again that the maintainers may change the name.
3. It opens a prefilled "Propose a metric" issue form in `prism-specification` (issue
   form fields prefilled through URL parameters; no token, no API call). A
   user without a GitHub account can save the file and send it any other way.
4. A bot in `prism-specification` turns the issue into a draft pull request with the
   term file(s). The issue body is untrusted text: parsed only, never run,
   same rules as `scripts/ci/modality_issue_to_files.py`.
5. CI runs `check_terms.py` and `check_schema_versions.py`; a maintainer
   chooses the final ID and name (IDs are frozen once released), adds the
   user's name as an alias, merges, tags a release.
6. Studio picks the tag up with the next sync and release; the user's column
   keeps working through the alias.

## Modality proposals

The existing "Propose a new modality" issue form and bot move to
`prism-specification`, because their output lands in schema paths. The bot's code
(`src/modality_contribution.py`, `prism_tools.py modality propose`) stays in
Studio: the `prism-specification` workflow checks out `prism-studio` at the pinned
release and runs that command (my call; avoids a second copy).

## Afterwards (not in this design's build)

- Move per-modality rules from Python into `x-prism` annotations one at a
  time (candidates: biosample censored codes, recommended `Technical` fields,
  the label-must-equal-`Study.*Name` check), so the validator reads them and
  more changes need no Studio code.
- A reader package in `prism-specification` once a second tool needs the schemas.
- Library split (separate plan) decided with its own hosting questions.

## Testing

TDD per repo rules for every new script. Minimum: sync writes exactly the
locked files and refuses non-GitHub URLs; drift check fails on an edited
file, a missing file and an extra file; `terms propose` builds a term that
passes `check_terms.py` (run against the vendored copy in a test) and a
prefilled URL within GitHub's length limit; the moved checks keep their
existing tests in the new repo. Studio's full suite must stay green after the
move with the vendored copy in place.

## Order of work

1. Create the repository (the user's step, or with explicit go: it is
   public and outward-facing), with `LICENSE`, `CONTRIBUTING.md`,
   `CODEOWNERS`, the issue forms and CI.
2. Move the files with history; tag `v1.0.0` from today's content.
3. In Studio: sync script, lock, drift check, replace the old CI job, delete
   the moved check code, keep everything else reading the same paths.
4. `terms propose` + the Share button + the "Propose a metric" form and bot.
5. Move the modality-proposal form and bot.

## Decided by the user

- Name: `prism-specification` (owner `MRI-Lab-Graz`, like `prism-studio`;
  my assumption, not stated).
- Licence, as BIDS does: **CC-BY 4.0** for the specification (schemas,
  terms, spec text) and **MIT** for the scripts (`scripts/`; Creative Commons
  advises against its licences for software). `LICENSE` states the split,
  `CONTRIBUTING.md` says contributions are accepted under it. Studio stays
  AGPL-3.0; the vendored copy keeps the licence notice next to it.
- Visibility: **public** from the start (needed for unauthenticated sync and
  outside pull requests), not announced until ready.

## Decisions (mine, check them)

- Repository on GitHub, not the university GitLab (contributors have GitHub
  accounts; Zenodo DOIs).
- Vendored copy + lock + drift check, not submodule or pip package.
- Spec pages move with the schemas.
- `entities` / `dataset_description` move, guarded by `CODEOWNERS`.
- Release tags of `prism-specification` are semantic versions of the whole bundle
  (`v1.0.0`); per-modality `version` fields stay as they are.
- Modality-proposal bot runs Studio's code via a checkout, not a copy.
