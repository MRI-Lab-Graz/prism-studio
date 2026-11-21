# DataLad: version control moves to Worldline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PRISM Studio stops shipping a second version-control GUI. Syncing, getting data, opening from a server
and publishing move to Worldline Desktop. PRISM keeps only the DataLad work that needs PRISM/BIDS knowledge.

**Architecture:** Two PRs, in order. PR 1 (Worldline repo, `/Volumes/Evo/software/DataLad-desktop`) adds the
`sourcedata/` public-host push guard that today only PRISM has. PR 2 (prism-studio) deletes the generic DataLad
commands, routes, page parts and JS, and points users to Worldline. PR 2 merges only after a Worldline release that
contains PR 1, because PR 2 removes the only guard users have today.

**Tech Stack:** Python 3 / argparse / Flask (PRISM), Node `node --test` + Electron (Worldline).

**Spec:** the decision in chat on 2026-11-21: "PRISM keeps what needs PRISM knowledge, Worldline does the general
version control". There is no separate design doc; this section and the lists below are the spec.

## What stays in PRISM, what goes

**Stays (PRISM-specific or needed to write a valid project):**
- `.gitattributes` text policy (`DATALAD_TEXT_POLICY_REQUIRED_LINES`, `app/src/project_manager.py`)
- `prism_tools datalad enable`, `datalad save`, `save-gate`, `datalad doctor` (+ `/api/projects/datalad/preflight`,
  `/doctor`), `datalad identity` (+ `/api/settings/git-identity`), `/api/projects/datalad/state` (navbar badge)
- DataLad-aware changes to files: `repo_rewrite_datalad_runner.py`, `datalad_mutation_policy.py`, `save_gate.py`,
  `datalad_project_copy.py`, `bids_file_deleter.py`, `/api/projects/datalad/remove-scans-tsv`
- Export repository modes (`datalad_free` / `datalad_preserving` / `git_lfs`), rsync (no DataLad), Share & Archive page

**Goes (Worldline already does it: status, push/pull, get, clone, remotes):**
- CLI: `datalad sync`, `datalad put-on-server`, `datalad open-from-server`, `datalad get-data`, `datalad update`,
  `datalad status`, and the top-level `publish` command (incl. `--check`, `--install-hook`)
- Routes: everything in `app/src/web/blueprints/projects_datalad_server_blueprint.py` (sync/start, sync status/cancel,
  put-on-server, get-data, open-from-server, datalad-server/publish); in `projects.py`: `/api/projects/datalad/status-deep`,
  `/api/projects/datalad/update`
- Backend: `src/datalad_clone.py`, `src/datalad_get_data.py`; from `src/share_publish.py` every push/publish/hook
  function (`publish_to_server`, `sync_with_server`, `put_on_server`, `location_problem`, `_local_folder_in_use`,
  `_push_refusal`, `_publish_refusal`, `_is_public_target`, `_PUBLIC_HOSTS`, `install_hook`, `check_for_hook`,
  `_hook_script`, `_hooks_dir`, `HookExistsError`, `NotAGitRepoError`, and audit helpers left without a caller)
- JS: `app/static/js/modules/datalad/job.js`, `app/static/js/shared/datalad-update.js`, `app/static/js/publish.js`
  (and their `.test.js`), the server/get-data parts of `modules/datalad/page.js` and `render-state.js`

## Global Constraints

- THE RULE (CLAUDE.md): what Studio keeps is a trigger for a CLI command; removing a CLI command removes its route too,
  and the other way round. No route may survive without its command.
- Public hosts list, copied verbatim from `src/share_publish.py`:
  `github.com, gitlab.com, gin.g-node.org, bitbucket.org, codeberg.org, openneuro.org`; plus every `http://`,
  `https://`, `git://` URL; a `<tool>+` prefix (`git+ssh://`) is stripped first; a trailing `.` on the host is ignored.
- Refusal text (Worldline): `"<remote> is a public host and this project tracks sourcedata/ (raw data). Send it only to the internal lab server."`
- Worldline link text in PRISM: `"Sync, server copies and getting data: use Worldline Desktop"` linking
  `https://worldline-desktop.readthedocs.io/`.
- Delete, never stub: no "moved to Worldline" placeholder commands or routes returning 410.
- Every subagent runs on Sonnet 5.5 (`claude-sonnet-5-5`), set explicitly.

## Review Focus

1. `datalad push` with no `--to` in Worldline: the guard must check every remote of the project, not just `origin`
   (test in Task 1).
2. scp-style URL `git@github.com:lab/study.git` and `git+ssh://github.com/...` must count as public (Task 1).
3. `sourcedata/` tracked only as a gitlink to a nested dataset (`sourcedata/sub-01`) still counts as tracked (Task 1).
4. Studio pages that linked to removed routes (navbar DataLad toggle, `settings.html`, `push_server_section.html`,
   `results.html` Publish button) must not 404 or show dead buttons (Task 4 test).
5. Kept features still work after `share_publish.py` is cut down: `save-gate` and `datalad enable` (Task 3 runs their
   existing tests).

---

## PR 1: Worldline (repo `/Volumes/Evo/software/DataLad-desktop`, own worktree, own chat)

### Task 1: `sourcedata/` push guard

**Files:**
- Create: `src/datalad/sourcedata-guard.js`
- Modify: `src/gui/main.js` (in `handle('adapter:runCommand', ...)`, next to the `save` gate, for commands in `PUSHES`)
- Test: `test/sourcedata-guard.test.js`
- Docs: one line in `README.md` "Why use it?" and `CHANGELOG.md`

**Interfaces:**
- Produces: `export function isPublicTarget(url: string): boolean`
- Produces: `export async function pushRefusal({ runner, projectPath, remoteName }): Promise<string | null>`
  (returns the refusal text, or `null` when the push may go). `runner.run(cmd, args)` → `{ exitCode, stdout, stderr }`
  as in `prism-gate.js`.

- [ ] **Step 1: Write the failing tests** in `test/sourcedata-guard.test.js`:
  - `isPublicTarget` is `true` for `https://gin.g-node.org/x`, `http://lab/x`, `git://x/y`, `git@github.com:lab/s.git`,
    `ssh://git@gitlab.com/lab/s`, `git+ssh://github.com/lab/s`, `git@github.com.:lab/s`;
    `false` for `ssh://user@lab-server.uni.at/data/s`, `user@10.0.0.5:/data/s`, `/Volumes/USB/s`, `''`.
  - `pushRefusal` with a fake runner: `git ls-files -- sourcedata` prints `sourcedata/sub-01` (a gitlink line is enough)
    and remote `origin` → `git@github.com:lab/s.git` → returns the refusal text with `"origin"`.
  - same, `ls-files` empty → `null`.
  - same, remote is the lab server → `null`.
  - `remoteName` undefined, remotes `origin` (lab server) and `gh` (github) from `git remote` → refusal naming `gh`.
- [ ] **Step 2:** `node --test test/sourcedata-guard.test.js` → FAIL (module not found).
- [ ] **Step 3: Implement** `src/datalad/sourcedata-guard.js`. Remote URL via `git -C <root> remote get-url <name>`;
  remote names via `git -C <root> remote`; tracked check via `git -C <root> ls-files -- sourcedata`. Host from
  `ssh://[user@]host[:port]/...` or scp form `[user@]host:path`. Not `parseSshAddress` (it only takes `ssh://`).
  In `main.js`, for `PUSHES` commands: `const refusal = await pushRefusal({ runner: toolRunner, projectPath: request.projectPath, remoteName: request.remoteName })`;
  on refusal return the same declined-result shape the save gate returns (`gate.result` style), no push.
- [ ] **Step 4:** `npm test` → all PASS.
- [ ] **Step 5:** Commit `feat(push): refuse to send a project that tracks sourcedata/ to a public host`.

**Status 2026-11-21: Task 1 done** on branch `feat/sourcedata-push-guard` in worktree `/Volumes/Evo/software/DataLad-desktop-guard` (commit 1195131; red→green seen, `npm test` 1509 pass / 0 fail). Audit and security review done (one fix: remote name validated before git sees it). **Merged as Worldline PR #101** (squash, CI green). **Worldline 0.6.3 released** (PR #102, tag v0.6.3 pushed 2026-11-21; its release build runs on the tag). PR 1 is finished. Next: PR 2 (Tasks 2-5) in a fresh chat. Rulings: guard also checks push URLs (`get-url --push --all`) and matches subdomains of public hosts; fails closed when git errors.

PR 1 then follows the repo's own finishing steps (its CLAUDE.md) and gets released. Write the release tag into this
plan file before starting PR 2.

---

## PR 2: PRISM Studio (worktree `../prism-studio-worldline`, branch `refactor/datalad-to-worldline`, new chat)

### Task 2: Lock the target surface in one test

**Files:**
- Test: `tests/test_datalad_scope.py`

- [ ] **Step 1: Write the failing test** `tests/test_datalad_scope.py`:
  - `test_generic_datalad_commands_are_gone`: build the parser (`app/src/cli/parser.py`, as `tests/test_cli_datalad.py`
    does); `datalad` subcommands == `{"doctor", "identity", "enable", "save"}`; no top-level `publish`.
  - `test_generic_datalad_routes_are_gone`: from the Flask test app's `url_map` (as `tests/test_datalad_doctor_route.py`
    builds it), none of `/api/projects/datalad-server/`, `/api/projects/datalad/put-on-server`, `/get-data`,
    `/open-from-server`, `/status-deep`, `/update` exist; `/api/projects/datalad/save`, `/enable`, `/preflight`,
    `/doctor`, `/state`, `/remove-scans-tsv` and `/api/settings/git-identity` do.
- [ ] **Step 2:** `pytest tests/test_datalad_scope.py -v` → both FAIL.
- [ ] **Step 3:** Commit the failing test together with Task 3 (the suite stays green per commit).

### Task 3: Delete the generic commands, routes and backend

**Files:**
- Delete: `src/datalad_clone.py`, `src/datalad_get_data.py`, `app/src/web/blueprints/projects_datalad_server_blueprint.py`,
  `app/src/cli/commands/publish.py`
- Modify: `app/src/cli/parser.py` (`datalad` subparsers ~877-985, `publish` ~851), `app/src/cli/commands/datalad.py`
  (drop `cmd_datalad_sync|put_on_server|open_from_server|get_data|status|update`), `app/src/cli/dispatch.py`,
  `app/src/cli/entrypoint.py`, `app/prism-studio.py:780` (blueprint registration),
  `app/src/web/blueprints/projects.py` (`status-deep`, `update` routes), `src/share_publish.py` (list above)
- Delete tests: `test_datalad_open_from_server.py`, `test_datalad_put_on_server.py`, `test_datalad_get_data.py`,
  `test_datalad_sync.py`, `test_datalad_update.py`, `test_projects_datalad_server_blueprint.py`, `test_cli_publish.py`,
  `test_publish_routes.py`, `test_share_publish_gate.py`, `test_share_publish_hook.py`, `test_share_public_target.py`,
  `test_share_publish_sourcedata_guard.py`, `test_datalad_push_errors.py`, `test_datalad_sibling_labels.py`
  (each one only after `grep` shows it tests removed code only; a file that also covers kept code is trimmed, not deleted)

- [ ] **Step 1:** Delete/trim as listed. Rule for `share_publish.py` and `datalad_state.py`: after the removals,
  delete every function with no remaining caller (`grep -rn "<name>" src app tests`), keep the rest.
- [ ] **Step 2:** `pytest tests/test_datalad_scope.py -v` → PASS.
- [ ] **Step 3:** `pytest tests -k "datalad or share or save_gate or git_identity or parity or export" -q > $SCRATCH/t3.log 2>&1; tail -5 $SCRATCH/t3.log` → no failures, no import errors.
- [ ] **Step 4:** `python tests/verify_repo.py --check dual-tree-drift --no-fix` → OK.
- [ ] **Step 5:** Commit `refactor(datalad): drop sync, server, get-data and publish; Worldline does them`.

### Task 4: Slim the Studio DataLad page and remove dead links

**Files:**
- Delete: `app/static/js/modules/datalad/job.js`, `app/static/js/shared/datalad-update.js`, `app/static/js/publish.js`
  (+ `.test.js` files)
- Modify: `app/static/js/modules/datalad/page.js`, `app/static/js/modules/datalad/render-state.js` (+ test),
  `app/templates/datalad.html` (drop location/job/get-data cards; add the Worldline link from Global Constraints),
  `app/templates/results.html:700` (publish script + button), `app/templates/includes/projects/push_server_section.html:25`,
  `app/templates/settings.html:71`
- Test: `tests/test_datalad_page_wiring.py` (update), `app/static/js/modules/datalad/render-state.test.js`

**Interfaces:**
- `render-state.js` actions after the change: `enable` (not a dataset) and `save` (dataset) only.

- [ ] **Step 1: Failing tests:** `render-state.test.js`: for any state, action ids ⊆ `{"enable", "save"}`;
  `test_datalad_page_wiring.py`: rendered `/projects/datalad` contains the Worldline link text and none of
  `dataladLocationStartBtn`, `dataladGetDataStartBtn`, `dataladJobCancelBtn`; `results.html` has no `publish.js`;
  every `fetch` URL in `app/static/js` exists in `url_map` (one parametrized test, regex over the JS files).
- [ ] **Step 2:** `node --test app/static/js/modules/datalad/` and `pytest tests/test_datalad_page_wiring.py` → FAIL.
- [ ] **Step 3:** Implement the deletions and edits. Navbar toggle (`base.html:409`) keeps linking to the slim page.
- [ ] **Step 4:** Both test commands → PASS; `node --test app/static/js` → PASS.
- [ ] **Step 5:** Commit `refactor(studio): DataLad page keeps enable and save, points to Worldline`.

### Task 5: Docs and repo rules

**Files:**
- Modify: `docs/DATALAD.md`, `docs/studio/datalad.md`, `docs/CLI_REFERENCE.md`, `docs/studio/export.md`,
  `docs/CLI_STUDIO_DIVERGENCES.md:123` (drop the DataLad publish/sync entry), `README.md` if it lists the removed
  commands, `CLAUDE.md` ("Consequence to keep in mind" paragraph: the `sourcedata/` publish guard now lives in Worldline
  `src/datalad/sourcedata-guard.js`; PRISM has no push path, and a new one must not be added)
- Not touched: `docs/_build/` (generated), old plans/specs under `docs/superpowers/`

- [ ] **Step 1:** `grep -rnE "put-on-server|open-from-server|get-data|datalad (sync|update|status)|prism_tools publish" docs README.md CLAUDE.md | grep -v -e _build -e superpowers -e handouts -e _archive` → empty.
- [ ] **Step 2:** `sphinx-build -W -b html docs $SCRATCH/docs` → no warnings.
- [ ] **Step 3:** Commit `docs: DataLad sync and server copies are Worldline's job`.

### Finish PR 2

`/ponytail:ponytail-audit` and `/code-review` once on the branch, then `superpowers:finishing-a-development-branch`.
Merge only after the Worldline release from PR 1 is out.
