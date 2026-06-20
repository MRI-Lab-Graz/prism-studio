# Repo Notes for Claude

## Git-annex / DataLad text-file policy

Text-format and small-codebook files must **never** be tracked by git-annex
(DataLad) in any PRISM project — this includes `sourcedata/`, not just the
BIDS dataset proper. Affected extensions: `.csv`, `.tsv`, `.json`, `.jsonl`,
`.ndjson`, `.txt`, `.xml`, `.yaml`/`.yml`, `.toml`, `.cfg`, `.md`, `.xlsx`,
`.xls`, `.ods`, plus key root files (`.gitattributes`, `.bidsignore`,
`.prismrc.json`, `dataset_description.json`, `project.json`, `README.md`,
`CHANGES`, `CITATION.cff`).

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
