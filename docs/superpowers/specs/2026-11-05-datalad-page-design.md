# DataLad page: share a project with the team through the lab server

Date: 2026-11-05. Status: approved by the user (including: `worktree-feat-validated-sync` merged first, and the new page
replaces the old DataLad card and Share-page panel). Written for the builder who plans and implements it.

## Intent

A study team (a few people, mostly students) works on one PRISM project. Everybody has their own copy on their own
computer and their own account. One DataLad server in the lab holds the newest valid state. One person edits and
sends changes to the server; everyone else gets them. Students must be able to follow it without knowing DataLad.

DataLad in PRISM stays **slim**: snapshots, bound to validation, plus getting a project to and from the server.
Anything fancier belongs to the lab's separate datalad-desktop repository.

## What exists already (on `main` once `worktree-feat-validated-sync` is merged; merge it first)

- `datalad enable`, `save` (refuses an invalid dataset; `--allow-invalid` overrides and writes
  `[saved with N validation error(s)]` into the snapshot message), `status`, `identity`, `doctor`, `config`.
- `datalad update` = "Get latest": fast-forward only, never merges, refuses unsaved changes, skips a project with no server.
  Studio asks for it once per project when the DataLad card loads.
- `datalad sync` = update, then `publish_to_server` (saved, valid, to the server's sibling `origin`), via
  `sync_with_server` in `src/share_publish.py`. Studio's "Sync now" job runs the same function.
- The git name and email live in the person's git config, never in the project.
- RIA stores, Finalize and the unvalidated sync are already removed.
- Export (`export_project_to_plain_folder`) already has subject/session/modality/acq/task filters and a step that fetches
  annexed content (`materialize_annex_content`). Its filter logic is a closure inside that function.

## The rule that governs everything (repo `CLAUDE.md`)

The CLI executes, Studio only triggers. Every action below is a `prism_tools.py datalad ...` command whose logic lives in
`src/`; a Studio route and the JavaScript collect input, call the same function and show the result. A feature is done
only when the CLI does it, Studio triggers it, and `tests/test_cli_studio_parity.py`-style parity tests prove both write
the same files. Use TDD: a failing test first, watched failing, then the code. The page follows the project page
(`app/templates/projects.html`, `app/static/js/modules/projects/`) and the shared theme (`studio-theme.css`, the macros in
`includes/ui/macros.html`, `studio-theme.js`, `chip-list.js`): same widgets, same badges, no second copy of a themed part.

## Goals

1. A **DataLad entry in the navbar** opening a **DataLad page** (layout B, decided by the user): the page shows the one next
   sensible step for the current project, and everything else under "More".
2. **Put on server**: the first person puts the project on the server (creates it there, then sends it).
3. **Open from server**: anybody else gets a copy (a clone). Works with **no project open** and creates one.
4. **Get data**: fetch annexed content (MRI, physio, ...) into the project, with the **same filters as the export**
   (subjects, sessions, modalities, acq, task), "everything" by default.
5. **Sending an invalid dataset is possible, but only after an explicit acknowledgement**, in GUI and CLI, and the
   acknowledgement is recorded.
6. **Drop RIA support** completely.
7. Fix the bug on `main`: the git pre-commit save gate refuses a commit even when the user acknowledged errors
   (`--allow-invalid` / "Save anyway"), because the hook has no override.

## Non-goals

No merge or conflict-resolution UI (a diverged project stops and tells the user to ask the data steward). No automatic
fetching of annexed content on open. No several servers. No special remotes, RIA or otherwise. No new DataLad commands
beyond the list in this document.

## Anti-goals (it fails even if it technically works)

- An invalid dataset reaching the server without the user having clearly acknowledged it.
- Get latest overwriting or mixing with a user's own unsaved or saved work.
- The project file carrying anything personal or machine-specific (name, email, server address).
- A page that treats "no server yet" or "server not reachable" as an error. Many students cannot reach the server today.

## The page (layout B)

States, derived **in the backend** (`datalad status` returns a `next_step`; the CLI prints it too; JavaScript only renders):

| State | Shown as the main step | Also shown |
|---|---|---|
| No project open | "Open from server..." | |
| Project, DataLad off | "Enable DataLad" | link "Joining a team project? Open from server..." |
| DataLad on, no server | "Put on server..." (snapshots stay on this computer; not an error) | Save |
| DataLad on, server, unsaved changes | "Save", then "Sync now" | |
| DataLad on, server, nothing unsaved | "Sync now" | "Get latest" |
| Server not reachable | a plain notice, work continues | |

"More" holds Get latest, Get data, Check this computer (`datalad doctor`), and the project's name and email link to Settings.
Sync that stops on validation errors lists them and offers a clearly worded "Send anyway, I understand this dataset has N
errors" choice. Layout, badges and chips follow the project page. The navbar entry replaces the current DataLad indicator
menu; the pending-change count stays on it.

The new page **replaces** the project page's DataLad card and the DataLad panel on the Share page (the rsync panel and
Create Project's DataLad question stay). This removal is the builder's recommendation to confirm.

## Commands (all CLI first; same options and defaults in Studio)

| Command | Status |
|---|---|
| `datalad status --project [--json]` | exists; add `server`, `next_step`, `validation` summary |
| `datalad enable / save / update / sync / identity / doctor` | exist; `save` and `sync` and `publish` share one acknowledgement option |
| `datalad put-on-server --project --location [--sibling-name origin] [--allow-invalid]` | new |
| `datalad open-from-server --location --target [--get-data] [filters]` | new |
| `datalad get-data --project [same filter flags as export]` | new |

`--location` is one thing: a folder (e.g. on a network drive) or an ssh address. The code treats both the same way and
does not care which; the lab has not decided how the server is reached.

## Decisions taken (the user's)

- Dedicated navbar entry and page; layout B; students first.
- Each user has their own copy and account; one server; the server is the sibling `origin`.
- Invalid push allowed in GUI and CLI only with explicit acknowledgement. RIA dropped.
- Get data reuses the export's filtering. The CLI does the work, Studio triggers it, TDD.

## Calls made by the author (check these)

1. **Server address not stored in the project.** The location lives in the git remote `origin` of the user's own copy
   (already local, never pushed). The project config keys `riaStoreUrl`, `siblingName`, `siblingAlias` and the commands
   and routes that write them (`datalad config`, `/api/projects/datalad-server/config`) are removed; old keys are ignored.
2. **One acknowledgement mechanism** for save, sync/publish and both git hooks: the backend sets one environment variable
   only for the single command the user acknowledged; the hooks honour it. The gate stays advisory (anyone can set it in a
   terminal); the audit log and the snapshot message record every acknowledged invalid save or push
   (`pushed_with_errors`, error count).
3. **Put on server refuses a location that already holds a dataset** (it would overwrite someone's work) and says
   "open it from the server instead".
4. **Open from server** asks for an empty or new target folder, clones, then offers (does not force) Get data.
5. **The page replaces** the old DataLad card and Share-page panel (see above).
6. The shared filter logic is **extracted from the export** into one function used by export and Get data; export
   behaviour must not change (its tests stay green).

7. **The sourcedata and public-host guard applies to every new path.** `put-on-server` runs the same refusal as
   `publish_to_server` (public host or web URL while `sourcedata/` is tracked) **before** it creates anything on the
   server. A location is a local or network folder, `user@host:path`, or `ssh://...`. `http(s)://` and `git://` are refused
   by `put-on-server` and, for simplicity, by `open-from-server` too (the lab server is neither). Locations are validated as
   untrusted input (no leading `-`, same label rules as sibling names) and covered by `/security-review`.
8. **Put on server creates a plain sibling (a bare repository with the usual DataLad hooks)**, using the existing
   `run_datalad_create_sibling_plain` (works for a folder and for ssh with the same call), with `--existing error`, so a
   location that already holds a dataset is refused by DataLad itself, locally or over ssh. The push is then the validated
   publish with the existing push verification (`is_ria=False`). v1 is tested against a local folder only; ssh is the same
   call and cannot be tested here.
9. **Acknowledgement**: the single option is `--allow-invalid` (no error count to retype). It is recorded in the audit log
   (`pushed_with_errors`, error count) and, for saves, in the snapshot message (`[saved with N validation error(s)]`),
   which travels with the commit so teammates see it. The hook side stays advisory, as above; the pre-push hook passes for
   the one acknowledged command through the same mechanism.
10. **Save and Sync are two steps** in the GUI (Save needs a message; a blocked Save shows its own acknowledgement choice).
11. **Get data without a server**: a project with no `origin` gets a plain notice and exit 0 ("nothing to fetch from");
    a server that cannot be reached is an error exit with a plain sentence; files that no remote has are listed as the error.
    Filters are exactly the export's, including its include/exclude choices for derivatives, code, analysis and sourcedata,
    default everything (the same function selects the paths for both).
12. **Existing projects whose server is not called `origin`** (an old `ria-store`, or any other name): nothing is renamed.
    `status` reports "server found as 'X'; use --sibling-name X" so the user is told, and `--sibling-name` keeps working.
13. **The pending-change count** in the navbar already comes from an existing endpoint and stays; only the menu becomes a link.

## Left to the builder

File and function names, module split, the exact wording of messages (plain language, same style as existing ones),
progress reporting for long fetches (reuse the existing job pattern for Sync), whether the shared hook override is an
env var or a flag file, and test fixtures (real DataLad against a local folder as server, as in
`tests/test_datalad_update.py` and `tests/test_datalad_sync.py`).

## Suggested order (each step: failing test, then code, then parity test, then docs and changelog)

0. Merge `worktree-feat-validated-sync`.
1. Acknowledged invalid: save-gate hook override (bug on `main`); `--allow-invalid` for sync/publish and the pre-push hook;
   audit record; GUI choice.
2. `datalad status` `next_step` and server fields.
3. `put-on-server`.
4. `open-from-server`.
5. Extract the export filters; `get-data`.
6. The page, the navbar entry, replacing the old panels.
7. Drop RIA leftovers (create-sibling for RIA, `is_ria_url`, alias, config keys, `datalad config`), docs and changelog.

Security: steps 1, 3 and 4 touch `src/share_publish.py`, hooks and data read from the project, so run `/security-review`
(repo rule). Before each merge run `ponytail:ponytail-audit`.
