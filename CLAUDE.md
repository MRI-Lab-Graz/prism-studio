# Repo Notes for Claude

## `src/` vs `app/src/`: dual-tree drift is a live, recurring bug source

**Intended architecture** (per `docs/PROJECT_OVERVIEW.md`): `src/` is the one
canonical backend logic tree. `app/src/` is supposed to be Flask routes and
adapter code that wires the Studio GUI to that backend — UI glue, not a second
copy of business logic. In practice this boundary has been violated in
several places, and it has already caused the exact same production bug more
than once (see `docs/_archive/MODULARIZATION_ROADMAP.md`, which diagnosed
this same failure mode on `excel_base.py` previously and recommended — but
never carried out — eliminating the mirrors).

**Why it bites silently**: `src.converters` (and sibling packages like
`src.web`) are *implicit namespace packages* whose search path is the
concatenation of `src/converters/` and `app/src/converters/` (wired in
`src/__init__.py`). When CLI code does `from src.converters.excel_to_survey
import ...` and no physical file exists at `src/converters/excel_to_survey.py`,
Python loads `app/src/converters/excel_to_survey.py` instead — but under the
`src.converters` package identity. That module's own relative imports (e.g.
`from .excel_base import ...`) then resolve against the *merged* namespace,
and a real, independently-maintained file at `src/converters/excel_base.py`
wins over the physically-adjacent file sitting right next to it in
`app/src/converters/`. Editing only the `app/src/` copy of a shared helper is
silently ineffective for anything reached through the CLI (`prism.py`,
`prism_tools.py`, `python -m src.cli.entrypoint`) — it will keep running the
stale `src/` version and you won't get an import error, just wrong behavior.

**Before editing any module under `app/src/` that isn't pure Flask
route/adapter code** (converters, validators, shared utils — anything that
looks like business logic): check whether a physically separate file exists
at the mirrored path under top-level `src/` (`find src -name '<filename>.py'`).
As of this writing, known genuinely-independent, silently-drifting pairs
include `converters/excel_base.py`, `converters/csv.py`,
`converters/survey_base.py`, and `web/utils.py` — treat this list as
non-exhaustive and re-check, since new drift can appear any time someone
edits one side and not the other. If both copies exist, either update both in
lockstep or check whether the module already uses the
`load_canonical_module`/`_compat.py` delegation pattern (many `app/src/`
modules do — e.g. `excel_to_biometrics.py`) in which case only the `src/`
copy should be edited and `app/src/` is a thin shim. A handful of modules
(e.g. `converters/survey.py`) are real symlinks rather than duplicates — those
are safe, only real independent files are the hazard.

## Git-annex / DataLad text-file policy

Text-format and small-codebook files must **never** be tracked by git-annex
(DataLad) in any PRISM project — this includes `sourcedata/`, not just the
BIDS dataset proper, and derivatives (e.g. auto-generated `.R` helper
scripts). Affected extensions: `.csv`, `.tsv`, `.json`, `.jsonl`,
`.ndjson`, `.txt`, `.xml`, `.yaml`/`.yml`, `.toml`, `.cfg`, `.ini`, `.md`,
`.xlsx`, `.xls`, `.ods`, `.R`, plus key root files (`.gitattributes`,
`.bidsignore`, `.prismrc.json`, `dataset_description.json`, `project.json`,
`README.md`, `CHANGES`, `CITATION.cff`).

This is implemented via `annex.largefiles=nothing` rules written into each
project's `.gitattributes` by `DATALAD_TEXT_POLICY_REQUIRED_LINES` in
`app/src/project_manager.py`. Only genuinely large/bulk binary formats (`.pdf`,
`.sav`, MRI data, EEG/physio recordings, etc.) should end up annexed as
symlinks into `.git/annex/objects/`.

When writing or touching any code that creates `.gitattributes`, adds files to
a DataLad/git-annex dataset, or otherwise affects what gets annexed
(`src/datalad_execution.py`, `src/repo_rewrite_datalad_runner.py`,
`app/src/project_manager.py`, file-management/entity-rewrite commands, etc.),
preserve this invariant. If you ever find a text-format file that ended up as
an annex symlink, that's a bug to flag/fix, not expected behavior — for any
extension, anywhere in the project, including `sourcedata/`.

## Session IDs are free-form strings — never normalize them

BIDS session labels (`ses-<label>`) are arbitrary strings, not numbers.
`"pre"`, `"1"`, and `"01"` are three different, equally valid, independent
labels — never coerce one into another (e.g. zero-padding `"1"` to `"01"`,
or treating `"1"` and `"01"` as "the same session"). Doing so silently
mismatches/duplicates a user's actual session naming.

A prior version of `app/src/web/blueprints/conversion_physio_handlers.py`
had a `_normalize_session_label()` helper that zero-padded bare numeric
session labels to two digits. This was wrong and was deleted; session label
extraction there now uses the same plain `_sanitize_bids_label()` used for
subject labels (alphanumeric-only, no padding/coercion). Do not reintroduce
numeric session normalization anywhere in this codebase — any session
matching/comparison logic must be an exact string comparison.

## Prefer extracting functions out of monolithic scripts

When touching a large monolithic script (e.g. `app/prism-studio.py`), prefer
slicing out the logic you're changing into a small, focused, testable
function rather than growing the monolith in place. After extracting a
function, add a dedicated test for it. This is about keeping the repo
maintainable over time — don't do large opportunistic refactors unrelated to
the task at hand, but when you're already editing a function, leave it (and
its neighborhood) more separable than you found it.
