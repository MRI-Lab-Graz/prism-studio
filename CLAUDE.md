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
