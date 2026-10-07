# DataLad server as the home of a study

Status: draft for review. Nothing is implemented.

## Problem

A study starts on one machine, but MRI data is too large to keep locally and the study team needs a
shared, backed-up copy from day one. Today the "Push to Server" card (GUI only) can create a RIA or
plain sibling and push to it. It cannot do what the lab needs:

- no CLI (breaks the one-implementation rule in CLAUDE.md),
- push only: two people syncing one study get "non-fast-forward" errors,
- no `--shared` on store creation, so one member's files are not writable by another,
- no way to free local disk while keeping the server copy usable,
- no link between study authors and server accounts.

## Decisions (agreed 2026-10-02)

1. **Local first, server immediately.** A study is created locally; the first sync creates it on the
   server. PRISM never creates a dataset on the server first.
2. **Skeleton model.** The server holds all data. Locally the user may drop the large annexed files
   and keep the project as a skeleton (real text/JSON/TSV files + symlinks), then `get` on demand.
   The sibling stays registered; "Finalize & disconnect" is the end-of-study cut, not part of daily use.
3. **Members read and write.** Members are the study authors. One person administers the server.
4. **Manual account setup.** PRISM never creates server accounts. It lists which authors still lack
   a server user; the admin creates accounts and keys by hand.
5. **No silent conflict resolution.** A diverged sync stops and reports; it never overwrites.
6. **CLI parity.** Every operation is a backend function exposed by the CLI; the GUI card calls it.

## Safety rules

- `drop-local` never drops a file unless git-annex confirms another copy (`git annex drop` checks
  the sibling itself). It never uses `--force`. `--dry-run` lists what would be freed.
- The server then holds the only copy of the big files. The server needs its own backup; PRISM
  cannot provide one. The docs say so.
- `drop-local` and `get` need the sibling reachable and registered; both fail with a clear message
  otherwise.
- Text-format files stay un-annexed (CLAUDE.md git-annex policy); `drop-local` only ever touches
  annexed content, so the skeleton always contains every JSON/TSV.

## Components

All logic in `src/datalad_execution.py` (plus `ProjectManager` glue where it already lives); the
GUI blueprint and CLI both call it.

| # | Piece | Behaviour |
|---|-------|-----------|
| 1 | `sync` (CLI + existing GUI) | Connect if needed, `datalad update --merge` from the sibling, then push. Conflict -> stop, name the files. Keeps `--verify`. |
| 2 | `--shared group` | Passed to `create-sibling-ria` (and the plain sibling equivalent) so every member can write. |
| 3 | `drop-local` | `datalad drop -r` over the project and its `sub-*` datasets; options `--path`, `--subject`, `--dry-run`. Reports freed size and refused files. |
| 4 | `get` | `datalad get` for `--path` / `--subject`; the validator must still pass on a skeleton. |
| 5 | `members list` | Reads authors from study metadata, shows optional `server_user` per author, flags authors without one. Read-only; it prints, never changes the server. |
| 6 | Start study | Project creation option: set URL + sibling, run first sync. |
| 7 | Auto sync | A CLI call meant for cron or a PRISM post-action trigger. Last, after 1-4 are proven. |

`finalize` stays as is; add `--drop-local` as an optional flag after step 3 exists.

## Out of scope

Creating server accounts or keys, per-study access control (one shared group is enough for one
admin), automatic conflict resolution, a file watcher, server-side backup.

## Testing

Every piece starts with a failing test (CLAUDE.md TDD rule). Tests use a real DataLad dataset and a
`ria+file://` store in a tmp dir, the same pattern as `tests/test_datalad_execution.py`: a second
clone plays the second member (conflict test), and `drop-local` is checked by file content going
missing and coming back via `get`. A final manual demo against the real server uses a throwaway
store.

## Open items for the implementation plan

- Exact flag for `--shared` on the plain (non-RIA) sibling path.
- Where `server_user` lives (project settings vs. author object) -- decide when writing tests for #5.
