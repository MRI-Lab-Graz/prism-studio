# DataLad Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A DataLad navbar entry and page where a team shares one project through the lab server: put on server, open from server, get latest, sync, get data, with invalid sends possible only when acknowledged.

**Architecture:** Every action is a `prism_tools.py datalad ...` command whose logic lives in `src/` (never in `app/src/web/**` or JavaScript); Studio routes and JS only collect input, call the same function and show the result. The page is state-driven (layout B): the backend returns a `next_step`, JavaScript renders it. The server is the git remote `origin` of each user's own clone; nothing about it is stored in the project.

**Tech Stack:** Python 3.12, Flask, DataLad + git-annex (real, via local folders as servers in tests), pytest, vanilla ES modules + vitest, the Studio theme (`studio-theme.css`, `includes/ui/macros.html`, `studio-theme.js`, `chip-list.js`).

**Spec:** `docs/superpowers/specs/2026-11-05-datalad-page-design.md` (approved). Read it first; the "Calls made by the author" list (items 1 to 13) is binding.

## Global Constraints

- THE CLI EXECUTES, STUDIO ONLY TRIGGERS: logic in `src/`, CLI in `app/src/cli/`, routes in `app/src/web/blueprints/`. Same options and defaults in both. Each new command gets a row in `tests/route_cli_map.json` and a parity test in the style of `tests/test_cli_studio_parity_lifecycle.py`.
- TDD: write the failing test, run it, see it fail for the right reason, then the minimal code. Real DataLad tests use a local folder as the server (pattern: `tests/test_datalad_update.py`, `tests/test_datalad_sync.py`) and `pytest.mark.skipif` without `datalad`/`git-annex`.
- Text files are never annexed (`annex.largefiles=nothing` rules, `DATALAD_TEXT_POLICY_REQUIRED_LINES`); test data text must be real text with a trailing newline (a bare `x` is annexed).
- Any new push path goes through the sourcedata/public-host guard (`_is_public_target` in `src/share_publish.py`). Locations are untrusted input: no leading `-`; `http(s)://` and `git://` refused.
- The server is `origin` by default; no server address, name or email in `.prismrc.json`.
- No symlinks; no new dependencies; code works on macOS, Linux and Windows (a location may be `C:\\share\\x`, not an ssh target).
- Same page behaviour as the project page: one widget per kind of field, theme macros and `studio-theme.js` builders, no second copy of a themed part.
- Every task: update `CHANGELOG.md` (Unreleased) and the docs it touches. Before each merge run `ponytail:ponytail-audit`; tasks 1, 3 and 4 also `/security-review`. Commit trailer: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Work in a git worktree per task group; run JS tests with the repo's vitest (`node_modules/.bin/vitest run`).

## Review Focus

1. A fresh clone has **no save-gate hook** (git hooks are not cloned): an invalid commit would pass unnoticed. Pinned in Task 4.
2. Put on server **interrupted after the sibling was created**: a rerun must not fail on "exists"; status then shows a connected server and Sync completes it. Pinned in Task 3.
3. Locations that look like ssh but are Windows drive paths (`C:\\x`), contain spaces, or start with `-`. Pinned in Task 3.
4. Projects with nested `sub-*` datasets: put-on-server must create the sibling recursively; open-from-server must install the nested datasets (no content). Pinned in Tasks 3 and 4.
5. The acknowledgement variable must exist only for the one acknowledged command and be gone afterwards, even after an exception; a normal save right after is gated again. Pinned in Task 1.
6. A server that cannot be reached must never be an error state on the page or block Save. Pinned in Tasks 2 and 6.

## File Structure

- `src/save_gate.py` (modify): `ACK_INVALID_ENV`, honoured by the check. `src/share_publish.py` (modify): `allow_invalid`, `put_on_server`, `location_problem`.
- `src/datalad_state.py` (create): `datalad_state()`. `src/datalad_clone.py` (create): `open_from_server()`. `src/export_selection.py` (create): the filter logic extracted from the export. `src/datalad_get_data.py` (create): `get_data()`.
- `src/datalad_execution.py` (modify): `run_datalad_clone`; later delete RIA code.
- `app/src/cli/{parser,dispatch,entrypoint}.py`, `app/src/cli/commands/datalad.py` (modify): new commands and flags.
- `app/src/web/blueprints/projects.py` and `projects_datalad_server_blueprint.py` (modify): routes; `app/templates/datalad.html` (create); `app/static/js/modules/datalad/` (create): `render-state.js` (pure), `page.js`.
- Delete in Task 6: `app/static/js/modules/projects/datalad-card.js`, `datalad_server.js`, `app/templates/includes/projects/datalad_section.html`, the DataLad part of `push_server_section.html`.

---

### Task 1: Acknowledged invalid (save, sync, publish, both hooks)

**Files:** Modify `src/save_gate.py`, `src/share_publish.py`, `app/src/project_manager.py` (`_save_datalad_snapshot_locked`), `app/src/cli/commands/publish.py`, `app/src/cli/commands/datalad.py`, `app/src/cli/parser.py`, `projects_datalad_server_blueprint.py` (sync job and publish route), `app/static/js/shared/datalad-save.js` (unchanged contract). Test: `tests/test_ack_invalid.py`, extend `tests/test_datalad_sync.py`.

**Interfaces:**
- Produces: `ACK_INVALID_ENV = "PRISM_ACK_INVALID"` in `src/save_gate.py`; `ack_invalid()` context manager (sets the variable to `"1"`, always restores); `publish_to_server(..., allow_invalid: bool = False)`, `sync_with_server(..., allow_invalid: bool = False)`; result `reason` `"pushed_with_errors"` when sent despite errors, `errors` still listing them.

- [ ] **Step 1: Failing tests** in `tests/test_ack_invalid.py`: `test_the_save_check_passes_an_invalid_dataset_only_when_acknowledged` (same project, `check_save` refuses without the variable, returns `SaveCheck(True, errors, "acknowledged")` with it); `test_ack_invalid_restores_the_environment_even_after_an_exception`; `test_publish_check_honours_the_acknowledgement_too` (the pre-push hook path); `test_a_real_acknowledged_save_gets_through_the_installed_hook` (real DataLad, hook installed, `PRISM_TOOLS` set, `save_datalad_snapshot(allow_invalid=True)` succeeds, message ends `[saved with N validation error(s)]`, and the next normal save is refused again); `test_publish_with_allow_invalid_sends_and_audits_pushed_with_errors` (audit line `result == "pushed_with_errors"`, `error_count == 2`); `test_publish_without_allow_invalid_still_refuses`.
- [ ] **Step 2:** Run `python3 -m pytest tests/test_ack_invalid.py -q`; expect failures on missing names/behaviour.
- [ ] **Step 3: Implement** the variable check in the save-gate check function and in `check_for_hook`; wrap the single `datalad save` call in `ack_invalid()` only when the dataset has errors and `allow_invalid`; add `allow_invalid` to `publish_to_server`/`sync_with_server` (skip the `validation_errors` refusal, push, audit `pushed_with_errors`), wrapping the push in `ack_invalid()` so the pre-push hook passes.
- [ ] **Step 4:** CLI `--allow-invalid` on `publish` and `datalad sync` (same help text as `datalad save`); sync job and publish route read `allow_invalid` from the request body; the sync job's error result keeps `reason` and `errors`. Parity test `test_the_cli_and_studio_send_an_acknowledged_invalid_dataset_the_same_way` in `tests/test_datalad_sync.py`.
- [ ] **Step 5:** Run the new tests plus `tests/test_save_gate*.py tests/test_share_publish_gate.py tests/test_cli_studio_parity_lifecycle.py`; all pass (the lifecycle test must now pass deterministically).
- [ ] **Step 6:** Docs (`docs/DATALAD.md`, CLI reference), changelog, `/security-review`, commit.

### Task 2: `datalad status` with `next_step`

**Files:** Create `src/datalad_state.py`; modify `app/src/cli/commands/datalad.py` (`cmd_datalad_status`), `app/src/cli/parser.py`, `app/src/web/blueprints/projects.py` (new `GET /api/projects/datalad/state`); `tests/route_cli_map.json`. Test: `tests/test_datalad_state.py`.

**Interfaces:**
- Produces: `datalad_state(project_root, *, check_server: bool = False, validate: bool = False) -> dict` with keys `enabled`, `available`, `unsaved_count`, `server` (`{"name", "url", "reachable"}` or `None`), `other_servers: list[str]`, `valid` / `error_count` (only with `validate`), `next_step` in `{"enable", "put_on_server", "save", "sync", "up_to_date", "install_datalad"}`. CLI flags `--check-server`, `--validate`, `--json`. A path with no project is handled by the caller (the page shows "open from server").

- [ ] **Step 1: Failing tests:** `test_next_step_enable_when_not_a_dataset`; `..._put_on_server_when_dataset_has_no_origin`; `..._save_when_unsaved_changes_and_server`; `..._sync_when_clean_and_server`; `test_an_unreachable_server_is_reported_not_raised` (`reachable == False`, `next_step` unchanged, bounded by a timeout); `test_a_server_not_called_origin_is_reported_with_its_name` (`other_servers == ["ria-store"]`); `test_validate_flag_adds_error_count`. Parity: CLI `--json` equals the route's body for the same project.
- [ ] **Step 2:** Run; expect ImportError.
- [ ] **Step 3: Implement** reusing `check_datalad_clean_status`, `has_sibling`, `_git`; reachability by `git ls-remote --exit-code origin` with a short timeout only when `check_server`.
- [ ] **Step 4:** Run tests; pass. Changelog, docs, commit.

### Task 3: `datalad put-on-server`

**Files:** Modify `src/share_publish.py`, `src/datalad_execution.py` (reuse `run_datalad_create_sibling_plain`), CLI files, blueprint (job `kind="put"` via the existing job helpers; rename `_start_ria_job` to `_start_job`), `route_cli_map.json`. Test: `tests/test_datalad_put_on_server.py`.

**Interfaces:**
- Produces: `location_problem(location: str) -> str` (empty string when acceptable; refuses empty, leading `-`, `http(s)://`, `git://`); `put_on_server(project_root, location, *, sibling_name="origin", allow_invalid=False, identity=None, line_callback=None) -> dict` (same result shape as `publish_to_server`; new `reason` values `bad_location`, `location_exists`, `sibling_failed`).
- Consumes: Task 1's `allow_invalid`.

- [ ] **Step 1: Failing tests** (real DataLad, folder as server): `test_put_on_server_creates_the_dataset_and_sends_it` (a clone of the server folder shows the files); `test_it_refuses_a_location_that_already_holds_a_dataset` (nothing changed there); `test_it_refuses_an_invalid_dataset_before_creating_anything_on_the_server` (server folder not created); `test_it_refuses_unsaved_changes`; `test_it_refuses_web_locations_and_dash_locations` (parametrized: `https://x/y`, `git://x/y`, `-oProxy=x`, `""`); `test_a_windows_drive_path_is_a_folder_not_an_ssh_target` (`location_problem(r"C:\share\x") == ""`); `test_public_host_with_tracked_sourcedata_is_refused_before_any_command` (`user@github.com:o/r`); `test_a_nested_subject_dataset_is_created_recursively`; `test_a_second_run_after_an_interrupted_put_is_a_sync` (sibling exists, `datalad_state(...)["next_step"] == "sync"`, `sync_with_server` completes the push). CLI/Studio parity on a refusal and on a success.
- [ ] **Step 2:** Run; expect ImportError.
- [ ] **Step 3: Implement** order: location check, dataset/sibling-exists check, saved-and-valid check (shared with `publish_to_server`, factor the refusal helper out of it rather than copying), public-host guard, create sibling with `existing="error"`, `publish_to_server`.
- [ ] **Step 4:** CLI `datalad put-on-server --project --location [--sibling-name] [--allow-invalid] [--as] [--json]`; route `POST /api/projects/datalad/put-on-server` starting a job; JS later (Task 6).
- [ ] **Step 5:** Tests pass; `/security-review`; docs, changelog, commit.

### Task 4: `datalad open-from-server`

**Files:** Create `src/datalad_clone.py`; modify `src/datalad_execution.py` (`run_datalad_clone(location, target, *, datalad_executable="", timeout_seconds=3600, line_callback=None) -> dict`), CLI, blueprint, `route_cli_map.json`. Test: `tests/test_datalad_open_from_server.py`.

**Interfaces:**
- Produces: `open_from_server(location: str, target: Path, *, line_callback=None) -> dict` (`success`, `path`, `message`, `reason` in `bad_location`, `target_not_empty`, `clone_failed`, `no_identity`, `no_datalad`). Consumes `location_problem` from Task 3 and the preflight (`datalad_preflight`) for tools and identity; the route also sets the current project (like opening a project).

- [ ] **Step 1: Failing tests:** `test_open_clones_the_project_into_an_empty_folder`; `test_it_refuses_a_target_that_is_not_empty`; `test_it_refuses_a_web_location`; `test_the_copy_has_origin_as_its_server` (`datalad_state(...)["server"]["name"] == "origin"`); `test_nested_subject_datasets_are_installed_without_content`; `test_the_copy_has_the_save_gate_hook_in_the_project_and_nested_datasets` (Review Focus 1: install via the existing hook installer used by enable); `test_without_a_git_identity_it_stops_before_cloning`. CLI/Studio parity on a refusal and a success.
- [ ] **Step 2:** Run; expect ImportError.
- [ ] **Step 3: Implement:** preflight, location check, empty-target check, `datalad clone`, `datalad get -n -r .` for nested datasets, install hooks, return.
- [ ] **Step 4:** CLI `datalad open-from-server --location --target [--json]`; route `POST /api/projects/datalad/open-from-server`.
- [ ] **Step 5:** Tests pass; `/security-review`; docs, changelog, commit.

### Task 5: Shared export filters and `datalad get-data`

**Files:** Create `src/export_selection.py`, `src/datalad_get_data.py`; modify `app/src/project_manager.py` (`export_project_to_plain_folder`: call the extracted function), `app/src/cli/parser.py` (one helper that adds the export filter flags to both commands), CLI, blueprint, `route_cli_map.json`. Tests: `tests/test_export_selection.py`, `tests/test_datalad_get_data.py`.

**Interfaces:**
- Produces: `select_content_paths(dataset_root: Path, *, exclude_subjects, exclude_sessions, exclude_modalities, exclude_acq, exclude_tasks, include_derivatives, include_code, include_analysis, include_sourcedata) -> list[str]` (same behaviour as today's closures in the export); `get_data(project_root: Path, **same_filters) -> dict` using `run_datalad_get_paths`. Without `origin`: `{"success": True, "skipped": True, "message": ...}`; unreachable server: `success False`.

- [ ] **Step 1 (characterization first):** `test_the_export_selects_exactly_what_it_selected_before` captures the current selection for a fixture project with several subjects, sessions, modalities, acq and task labels, and passes against the **unchanged** export. Then `test_get_data_fetches_only_the_chosen_subjects` (clone fixture with annexed binary files per subject; `--exclude-subject sub-02` leaves sub-02 empty), `test_get_data_fetches_everything_by_default`, `test_without_a_server_it_says_so_and_succeeds`, `test_an_unreachable_server_is_an_error_with_a_plain_sentence`.
- [ ] **Step 2:** Run; characterization passes, the rest fail.
- [ ] **Step 3: Extract** the closures into `select_content_paths`; the export calls it; all existing export tests stay green (run `tests/test_export*.py`).
- [ ] **Step 4: Implement** `get_data` and the CLI `datalad get-data --project` with the export's filter flags (one shared helper adds them to both parsers) and the route `POST /api/projects/datalad/get-data` (job).
- [ ] **Step 5:** Tests pass; parity test on identical clones; docs, changelog, commit.

### Task 6: The page, the navbar entry, replacing the old panels

**Files:** Create `app/templates/datalad.html`, `app/static/js/modules/datalad/render-state.js`, `render-state.test.js`, `page.js`; modify `projects.py` (route `GET /projects/datalad`), `app/templates/base.html` (the navbar DataLad item always visible, linking to the page; the pending count stays), `app/static/js/main.js`, `index.js` (remove old inits), `settings.js`/`initializeSettingsPage` (remove the DataLad card there; keep the name and email form), `share.html`; delete the files listed under File Structure. Update `tests/test_projects_workflow_wiring.py`, `tests/test_navbar_project_event_wiring.py`.

**Interfaces:**
- Consumes: `GET /api/projects/datalad/state` (Task 2), routes from Tasks 1, 3, 4, 5, `getLatestFromServer`, `saveDataladSnapshot`.
- Produces: `renderState(state: object) -> {title, text, primary: {id, label} | null, secondary: Array<{id, label}>, more: Array<{id, label}>, notice: {text, kind} | null}` (pure, no DOM).

- [ ] **Step 1: Failing tests** `render-state.test.js`: one test per `next_step` value asserting the primary action id/label (`enable` shows "Enable DataLad" plus the secondary "Open from server..."; `put_on_server` shows "Put on server..." and no error notice; `save` primary "Save" then "Sync now"; `sync` primary "Sync now"); `an unreachable server is a plain notice and does not disable Save`; `no project open leads with "Open from server..."`; `More always holds Get latest, Get data, Check this computer`; a `valid == false` state shows the count and the "Send anyway" choice. Python wiring tests for the navbar link and the removed panels.
- [ ] **Step 2:** Run vitest; expect missing module.
- [ ] **Step 3: Implement** `renderState`, then the page: cards, badges and chip lists from the theme macros/`studio-theme.js`; subject/session selection for Get data reuses the export's cards/helpers (`chip-list.js`), no new widget. Actions only `fetch` the routes above and show the job result; "Send anyway" re-sends with `allow_invalid: true` after showing the error list. Get latest runs once per project on page load and on `prism-project-opened` (the logic that used to live in `datalad-card.js`).
- [ ] **Step 4:** Remove the old card/panel files and their imports in a **separate commit** (revertable). Run the full wiring/JS suites and `tests/test_html_validity.py` (it already fails on `main` for unrelated reasons: compare the error list before and after, as done for the last change).
- [ ] **Step 5:** Manual check in a browser (states: no project, DataLad off, no server, unsaved, synced); docs `docs/studio/datalad.md` (new page, added to `docs/index.rst`), `docs/DATALAD.md`, changelog, commit.

### Task 7: Drop RIA leftovers

**Files:** Modify `src/datalad_execution.py` (delete `run_datalad_create_sibling`, `run_datalad_create_sibling_ria`, `is_ria_url`), `src/project_settings.py` (`save_datalad_server_config`), `app/src/config.py` (`riaStoreUrl`, `siblingName`, `siblingAlias`: loaded keys ignored, never written), `app/src/cli/commands/datalad.py` (`datalad config`), blueprint (`/config`, `get_ria_status`), `app/static/js/shared/ssh-target.js` if unused, tests `tests/test_datalad_execution.py`, `tests/test_datalad_sibling_labels.py`, `tests/test_ssh_host_safety.py`, `tests/route_cli_map.json`.

- [ ] **Step 1: Failing tests:** `test_old_ria_keys_in_a_project_are_ignored_and_not_rewritten` (load then save a `.prismrc.json` containing `riaStoreUrl`, `siblingName`, `siblingAlias`: keys gone, rest intact); `test_no_datalad_config_command` (parser rejects it).
- [ ] **Step 2:** Run; fail. **Step 3:** Delete the code and its tests; run `grep -rn "ria" app src --include='*.py' --include='*.js'` and expect no live reference.
- [ ] **Step 4:** Full related suite (`-k "datalad or route or wiring or parity or settings or cli"`), vitest, `tests/verify_repo.py --check dual-tree-drift --no-fix`; docs, changelog, commit.

---

## Self-review

- **Spec coverage:** goals 1 (Task 6), 2 (Task 3), 3 (Task 4), 4 (Task 5), 5 (Tasks 1, 3, 6), 6 (Task 7), 7 (Task 1); calls 1 (Tasks 2, 7), 2 (Task 1), 3 and 7 and 8 (Task 3), 4 (Task 4), 5 (Task 6), 6 (Task 5), 9 and 10 (Tasks 1, 6), 11 (Task 5), 12 (Task 2), 13 (Task 6).
- **Types:** `location_problem`, `put_on_server`, `open_from_server`, `datalad_state`, `select_content_paths`, `get_data`, `renderState` are named identically where produced and consumed.
- **Not covered:** progress reporting for long fetches reuses the existing job helpers (builder's call); ssh locations are untested (same call as a folder).
