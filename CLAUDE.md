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

**Mandatory check — every time you touch a function in `app/src/` that isn't
pure Flask route/adapter code** (converters, validators, shared utils —
anything that looks like business logic), and every time you **add** a new
function to such a module: run `find src -name '<filename>.py'` for a
same-named file at the mirrored path under top-level `src/`. If one exists,
don't assume your edit is live — confirm which physical file actually answers
for the import path you care about:

```bash
python3 -c "import src.converters.<module> as m; print(m.__file__)"
```

**Which side wins is not uniform across the tree** — it depends on whether
either side has a real `__init__.py`. `src.converters` has no `__init__.py`
on either side, so it's a pure namespace-package merge and the physical file
under top-level `src/` wins (this is what bit `excel_base.py`/
`survey_base.py`). `src.web`, by contrast, resolves to
`app/src/web/__init__.py` — a real package — because a regular package
always wins over a namespace-package portion, so for anything under
`src.web.*` it's the physically-adjacent file in `app/src/web/` that's live,
and a same-named file directly under top-level `src/web/` is the dead one
instead (this is what happened to `web/utils.py`, see below). Always check
with the one-liner below rather than assuming a direction.

If that resolves to a *different* file than the one you edited, your change
is not in effect for anything importing through `src.*` (the CLI: `prism.py`,
`prism_tools.py`, `python -m src.cli.entrypoint`). Do not just duplicate the
edit into both files as a workaround — that only adds more surface for the
next person to drift. Prefer collapsing the pair into one real file with a
symlink for the other, the way `converters/survey.py` (`src/` side is the
symlink) and, as of 2026-08-04, `converters/excel_base.py` (`src/` side is
now a symlink to `app/src/converters/excel_base.py`, matching the
`survey.py` precedent since its sibling files
`excel_to_survey.py`/`excel_template_import.py` only exist in `app/src/`)
already do. A real symlink makes the drift class structurally impossible
for that file, rather than relying on anyone remembering to edit both sides.
If a proper delegation shim already exists instead (e.g.
`load_canonical_module`/`_compat.py`, or a hand-rolled
`spec_from_file_location` bridge like `src/converters/csv.py` uses to load
`app/src/converters/csv.py`), editing the implementation side is enough —
just confirm which side that is before assuming.

This problem is not fully mapped — treat every file as unverified until you've
run the check above yourself. Status as of 2026-08-04: `converters/
excel_base.py` and `converters/survey_base.py` were genuinely drifting and
are now fixed (see below); `converters/csv.py` was spot-checked and found
already safe (explicit file-path-loading shim, verified live) — no change
needed there. `converters/survey_base.py` had a genuine three-way divergence:
`app/src/converters/survey_base.py` delegated to `app/src/converters/
survey_core.py::get_allowed_values`, while the physically-independent
`src/converters/survey_base.py` carried its own from-scratch
reimplementation, and `app/src/validator.py` carried a *third*, more
complete one (`_get_allowed_values_list` — the only one honoring explicit
`MinValue`/`MaxValue`, and the only one that never silently returned `None`
for a `Levels` column with non-numeric keys, which made
`_check_allowed_values` skip validation for that column entirely). Fixed by
making `survey_core.get_allowed_values` the one canonical implementation
(merging in the validator's stronger behavior), having `validator.py` import
it instead of keeping a private copy, and collapsing `src/converters/
survey_base.py` into a symlink like `excel_base.py`. Regression tests:
`tests/test_survey_base.py` (function-level) and
`tests/test_validator_allowed_values.py` (validator integration).

`web/utils.py` (also 2026-08-04) turned out to be the opposite failure mode:
`src/web/utils.py` was a fully independent file, but — per the `__init__.py`
rule above — completely *unreachable*, dead code; `app/src/web/utils.py` was
already the live copy everywhere (the Flask app, the CLI, and the test
suite all resolve `src.web.utils` there). Confirmed by checking
`src.web.__path__` directly and by grepping every place in this repo that
imports `src.web.utils`/`endpoint_exists` for how each one sets up `sys.path`.
Still worth reconciling before deleting: the dead file's fallback bodies
(only reached if `src.web.path_utils` itself fails to import — a real, if
rare, concern for the PyInstaller-frozen build) had two correctness fixes
the live file was missing — `os.sep` instead of a hardcoded `/`, and an
empty-path guard on `get_filename_from_path`. Ported those into
`app/src/web/utils.py`, then collapsed `src/web/utils.py` into a symlink.
Regression tests: `tests/test_web_utils_fallback.py` (forces the dormant
fallback branches directly via monkeypatch, since normal test runs never
reach them — the only way to give a safety net real coverage).

`converters/limesurvey.py` (checked 2026-09-01, during a survey-module
assessment) was flagged as an *unverified* risk going in — both
`src/converters/limesurvey.py` and `app/src/converters/limesurvey.py` exist
as physically distinct files, matching the shape of the bugs above, and it
wasn't on the "already fixed" list. Checked and found already safe: the
`app/src/` copy is a 34-line `load_canonical_module`/`_compat.py` delegation
shim (per the pattern this note already documents above) that forwards to
`src/converters/limesurvey.py` (2100 lines, canonical) by file path, and
namespace-package resolution independently picks the `src/` copy first
regardless. No divergence, no action needed — noted here only so the next
person doesn't re-spend time re-verifying it from scratch.

Don't treat the absence of a file
from this note as proof it's safe; the check above is the source of truth,
this paragraph is not a checklist.

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
