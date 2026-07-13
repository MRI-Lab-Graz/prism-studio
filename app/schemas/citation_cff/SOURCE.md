# Citation File Format schema

`schema.json` is vendored verbatim from the official Citation File Format
project:

- Source: https://github.com/citation-file-format/citation-file-format/blob/main/schema.json
- Version: CFF 1.2.0 (`$schema`: draft-07)
- License: CC-BY-4.0 (see upstream repo)
- Fetched: 2026-07-13

Used by `ProjectManager.get_citation_cff_status()` in
`app/src/project_manager.py` to validate generated/edited `CITATION.cff`
files against the real schema, instead of ad-hoc key-presence checks.

To support a newer CFF version, replace this file with the updated
`schema.json` from the same upstream repo.
