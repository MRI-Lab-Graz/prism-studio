# Multi-User Web Server Roadmap (assessment, 2026-07-28)

> **Status: exploratory — not scheduled, not approved.** This is a feasibility
> assessment written to answer "could PRISM Studio be hosted as a server instance with
> user management, and what would it cost?" No implementation has started and none is
> planned as of this writing. File paths and line numbers reflect the repository state
> on 2026-07-28 and will drift.

## Context

PRISM Studio is today a **local single-user desktop app**: a Flask server bound to
`127.0.0.1:5001`, launched via `app/prism-studio.py` (1822 lines), wrapped in a pywebview
or Chromium app window, serving ~205 routes across ~20 blueprints (~38.8k LOC under
`app/src/web/`).

Scope assumed for this assessment: multiple research groups, **isolated per user/group**,
authenticating against **institutional SSO (OIDC/SAML)**.

Short answer: feasible — but it is a project of weeks, not a config flag, and the hard part
is *not* the login page. The core UX of PRISM is "the server process browses the host
filesystem and the client hands it absolute paths." That assumption is woven through 39
`expanduser()` call sites in the web layer alone, the global app-settings file, the
project-session logger, and every DataLad/rsync/ssh invocation. Making that safe for
mutually-untrusting groups inside one process is where the risk and cost concentrate.

---

## What actually blocks server deployment

Ranked by cost-to-fix:

1. **No authentication or authorization of any kind.** Zero login routes, no user model, no
   `@login_required` equivalent, no per-request identity. The only access control is
   `guard_against_remote_requests` ([app/prism-studio.py:1012-1041](../app/prism-studio.py#L1012-L1041)),
   an anti-DNS-rebinding Host-header check that is **disabled entirely when `--public` is set**.
2. **Unconfined filesystem access.** `GET /api/fs/browse`
   ([app/src/web/blueprints/tools.py](../app/src/web/blueprints/tools.py)) takes a raw `path` param,
   `Path(raw).expanduser().resolve()`, defaults to `Path.home()`, and enumerates Windows drives —
   no root confinement. `/api/fs/list-files` does recursive listing and is **not** in the loopback
   allowlist `_LOOPBACK_ONLY_PATHS` ([app/prism-studio.py:996-1000](../app/prism-studio.py#L996-L1000)).
   Project paths arrive from the client and flow into ~39 resolve sites.
3. **Server-side native file dialogs.** `/api/browse-file` and `/api/browse-folder` spawn
   **tkinter or PowerShell dialogs on the server machine**
   ([app/src/web/services/file_picker.py](../app/src/web/services/file_picker.py)). Headless-hostile;
   currently loopback-gated, so in `--public` mode file selection is simply broken. The
   `threads=8` waitress setting exists to survive their blocking
   ([app/prism-studio.py:1750](../app/prism-studio.py#L1750)).
4. **Global single-user state written from HTTP routes.** `AppSettings`
   ([app/src/config.py:365-416](../app/src/config.py#L365-L416)) lives in one home-dir file
   (`_get_user_app_settings_dir`, [app/src/config.py:346](../app/src/config.py#L346), duplicated in
   [app/src/web/blueprints/projects_helpers.py:122](../app/src/web/blueprints/projects_helpers.py#L122))
   and is mutated by routes in `projects_library_blueprint.py` — one user changing
   `global_library_root` changes it for everyone. Same for the recent-projects file.
5. **Process-global "active project" singleton.** `_PROJECT_SESSION_LOGGER`
   ([src/project_session_logging.py:186](../src/project_session_logging.py#L186)) tracks a *single*
   active project, activated from `set_current_project`
   ([app/src/web/blueprints/projects.py:196](../app/src/web/blueprints/projects.py#L196)). With N users
   the "active" project is whoever clicked last, and audit logs cross-contaminate.
6. **In-memory job stores, no ownership.** 12+ module-level dicts/`ConversionJobStore`
   instances plus ~12 `threading.Thread` spawn sites. Any user can poll any job id; jobs die on
   restart; multi-process WSGI (gunicorn workers) would break all of it.
7. **Desktop lifecycle hostile to servers.** Unauthenticated `POST /shutdown` →
   `os._exit(0)` ([app/prism-studio.py:1215](../app/prism-studio.py#L1215)); `ensure_clean_start()`
   kills whatever holds the port; `atexit` DataLad autosave; pywebview/Chromium window launch;
   root wrapper hard-requires a `./.venv`.
8. **Shared tool identity.** datalad, git-annex, ssh, rsync, apptainer all run as the server
   UID with the **server's SSH keys** — every user pushes to remote RIA/rsync stores as the same
   identity. Also note the project-switch DataLad autosave
   ([projects.py:176-180](../app/src/web/blueprints/projects.py#L176-L180)): one user switching projects
   can trigger `datalad save` on a dataset another user is mid-write on.

One genuine asset: **current project is already per-session** (`session["current_project_path"]`,
[projects.py:146-211](../app/src/web/blueprints/projects.py#L146-L211)), and `PRISM_SECRET_KEY` +
`--public` + waitress show reverse-proxy deployment was anticipated.

---

## Recommended approach: per-user container isolation, not in-process multi-tenancy

**Do not make the Flask app multi-tenant.** Instead, keep PRISM effectively single-user — which
is what it already is — and put the isolation boundary at the **container/OS level**, one PRISM
instance per user, behind an authenticating proxy. This is the JupyterHub / RStudio Server model.

```
Institutional IdP (OIDC/SAML)
        │
   oauth2-proxy ── authenticates, injects X-Forwarded-User
        │
   spawner/router ── maps user → their container
        │
   ┌────┴────┬──────────┐
 prism-alice prism-bob  prism-carol     ← one container each
   │           │           │
 /data/groupA /data/groupA /data/groupB ← only their group's volume mounted
```

**Why this over in-process multi-tenancy:** items 2-6 above mostly evaporate. Isolation is
enforced by the kernel and by which volume is mounted, not by application code being correct at
39+ path sites. For a tool handling human-subject neuroimaging data, a single missed
`expanduser().resolve()` in the multi-tenant design is a cross-group data leak; in the container
design it is contained to the user's own data. Each container also gets its **own SSH key and
git identity**, which fixes item 8 for free. The in-process alternative is realistically 3+
months and carries permanent security-review burden on every new path-taking route.

Cost: one container per *active* user (idle-cull them). At lab/multi-group scale this is fine.

---

## Phased roadmap

### Phase 0 — Server deployment mode (prerequisite for everything)
**~1 week.** Required by both architectures.

- Add `PRISM_DEPLOYMENT_MODE = desktop | server` in [app/src/config.py](../app/src/config.py), read
  once into `app.config`. Everything below branches on it.
- In `server` mode, in [app/prism-studio.py](../app/prism-studio.py): skip `ensure_clean_start()`
  (:1421), skip the `atexit` autosave (:466) and `sys.excepthook` override (:485), skip
  pywebview/`_launch_app_mode_window`/`webbrowser.open` (:1513, :1699, :1781), and **remove or
  auth-gate `POST /shutdown`** (:1215).
- Extract the launch-mode decision out of `main()` into a small testable function
  (per CLAUDE.md's "prefer extracting functions out of monolithic scripts"), and test it.
- Relax the `./.venv` hard requirement in the root [prism-studio.py](../prism-studio.py) — the
  container already provides the interpreter (`PRISM_SKIP_VENV_CHECK=1` exists; make it explicit).
- Make `PRISM_SECRET_KEY` **mandatory** in server mode (fail fast rather than randomising, so
  sessions survive restart), and drop the `PRISM_STARTUP_ID` session reset
  ([:1054-1058](../app/prism-studio.py#L1054-L1058)) in server mode.

### Phase 1 — Web-native file picker
**~2-3 weeks.** The single largest UI work item, and unavoidable in any hosted design.

- Replace the native-dialog routes in
  [app/src/web/services/file_picker.py](../app/src/web/services/file_picker.py) with a **server-side
  directory browser rendered in the browser** for server mode. The frontend already has the
  seam: [app/static/js/filesystem-mode.js](../app/static/js/filesystem-mode.js) plus the
  `connected_to_server` setting ([config.py:402](../app/src/config.py#L402)) and
  `/api/filesystem-context` ([tools.py:1645](../app/src/web/blueprints/tools.py#L1645)) already switch
  pickers between host and server mode — force it to `server` and build out the missing UI.
- Confine browsing to a configured `PRISM_DATA_ROOT` (the container's mounted volume). Add a
  single `resolve_within_data_root(client_path) -> Path` helper; route `/api/fs/browse` and
  `/api/fs/list-files` through it. Even with container isolation this is worth having as
  defence-in-depth and to stop path-traversal out of the mount.
- Strip host/`Path.home()`/hostname leakage from `/api/filesystem-context` in server mode.

### Phase 2 — Identity & SSO
**~1-1.5 weeks** in the container design (most of the work is proxy config, not app code).

- Deploy **oauth2-proxy** (or Shibboleth for SAML) in front, wired to the institutional IdP.
  `authlib` is already in `requirements-optional.txt` if in-app OIDC is preferred later.
- App-side: a `before_request` that reads the proxy-injected identity header into `g.principal`,
  **deny-by-default** with a small allowlist (`/health`, `/static/`). Trust the header **only**
  when bound to the proxy on a private network — document this loudly.
- Stamp `g.principal` into `emit_backend_request_action` and the project-session log so audit
  entries attribute to a real person.

### Phase 3 — Per-user state hygiene
**~1 week.** Small even in the container design, because each container has its own filesystem.

- Point `_get_user_app_settings_dir()` at a per-container writable path via `XDG_CONFIG_HOME`
  (already honoured, [config.py:355-357](../app/src/config.py#L355-L357)) — mostly a matter of setting
  the env var in the image and **de-duplicating** the copy in
  [projects_helpers.py:122-131](../app/src/web/blueprints/projects_helpers.py#L122-L131) into one shared
  helper.
- Drop the legacy `os.getcwd()` / `~/.prism-studio` / `~` search paths
  ([config.py:445-451](../app/src/config.py#L445-L451)) in server mode — they make settings resolution
  unpredictable in a container.
- Leave `_PROJECT_SESSION_LOGGER` as-is: one process per user makes the singleton correct again.
  (In the multi-tenant design this would be a significant refactor.)

### Phase 4 — Spawner, routing, and lifecycle
**~2 weeks.**

- Container image: PRISM + Flask/waitress + **datalad, git-annex, git, rsync, ssh** and
  optionally apptainer/pydeface/node BIDS validator. Note the existing
  [Dockerfile](../Dockerfile) is **validator-only** and explicitly excludes Flask/datalad — this is
  a new image, not an edit.
- Spawner: simplest viable is JupyterHub's `DockerSpawner` pattern, or a small
  Traefik/nginx + docker-compose router keyed on the authenticated user. Per-user volume mount
  from a group-to-path map. Generate a per-user SSH key + `git`/`datalad` identity on first spawn.
- Idle culling and resource limits (CPU/memory), so conversion jobs can't starve the host.
- Persist per-user home volume so settings/recents/job history survive a respawn.

### Phase 5 — Hardening and operations
**~1-2 weeks.**

- Audit the outbound-SSH blueprints (`projects_remote_browse_blueprint.py`,
  `projects_rsync_server_blueprint.py`, `projects_datalad_server_blueprint.py`) now that they run
  with a *per-user* key — confirm no path escapes the data root and no host is reachable that
  shouldn't be.
- Enforce the CLAUDE.md git-annex text-file policy in the server image too: verify
  `DATALAD_TEXT_POLICY_REQUIRED_LINES` ([app/src/project_manager.py](../app/src/project_manager.py)) is
  applied to projects created server-side, and that no `.csv`/`.tsv`/`.json`/`.md` ends up an
  annex symlink.
- Revisit `MAX_CONTENT_LENGTH = 1 GB` ([app/prism-studio.py:493](../app/prism-studio.py#L493)) and add
  per-user upload quotas.
- Keep jobs in-process: **single waitress process per container** is correct here. Do *not*
  introduce Celery/Redis — with one user per process the existing `ConversionJobStore` +
  `threading.Thread` pattern is sound. Document that gunicorn multi-worker must not be used.
- Deployment docs + `docker-compose.yml` (none exist today — no compose, gunicorn, systemd, or
  nginx config anywhere in the repo).

---

## Effort summary

| Phase | Work | Estimate |
|---|---|---|
| 0 | Server deployment mode | ~1 wk |
| 1 | Web-native file picker + data-root confinement | ~2-3 wks |
| 2 | SSO via authenticating proxy | ~1-1.5 wks |
| 3 | Per-user state hygiene | ~1 wk |
| 4 | Container image, spawner, routing | ~2 wks |
| 5 | Hardening, quotas, deployment docs | ~1-2 wks |
| | **Total (one developer, focused)** | **~8-11 weeks** |

For comparison, the in-process multi-tenant alternative is **~3+ months** and leaves a permanent
requirement that every new path-taking route be security-reviewed. It is only worth it if
per-user containers are ruled out by infrastructure constraints.

A useful **~2-week milestone** exists: Phase 0 + a minimal Phase 2 (oauth2-proxy in front,
deny-by-default, native pickers disabled) gives a *single-group, authenticated, shared-state*
server — useful internally and a real de-risking step, as long as it is not presented as
providing isolation between groups.

---

## Critical files

- [app/prism-studio.py](../app/prism-studio.py) — launcher, `before_request` guards, `/shutdown`, lifecycle
- [app/src/config.py](../app/src/config.py) — `AppSettings`, `_get_user_app_settings_dir`, settings search path
- [app/src/web/services/file_picker.py](../app/src/web/services/file_picker.py) — native dialogs to replace
- [app/src/web/blueprints/tools.py](../app/src/web/blueprints/tools.py) — `/api/fs/browse`, `/api/fs/list-files`, `/api/filesystem-context`
- [app/src/web/blueprints/projects.py](../app/src/web/blueprints/projects.py) — session project, `_project_manager`
- [app/src/web/blueprints/projects_helpers.py](../app/src/web/blueprints/projects_helpers.py) — duplicated settings dir, recents
- [src/project_session_logging.py](../src/project_session_logging.py) — global active-project logger
- [app/static/js/filesystem-mode.js](../app/static/js/filesystem-mode.js) — existing host/server picker seam
- [Dockerfile](../Dockerfile) — validator-only; a new Studio image is needed

## Verification (if this is ever picked up)

- **Phase 0:** unit-test the extracted launch-mode function; assert `server` mode registers no
  `/shutdown`, spawns no window, registers no `atexit` autosave. Existing suite: `pytest` per
  [pytest.ini](../pytest.ini) (207 test files).
- **Phase 1:** Flask-test-client tests that `/api/fs/browse` rejects `..`, absolute paths outside
  `PRISM_DATA_ROOT`, and symlinks escaping it. Extend
  [tests/test_tools_fs_browse_route.py](../tests/test_tools_fs_browse_route.py) and
  [tests/test_web_file_picker_service.py](../tests/test_web_file_picker_service.py).
- **Phase 2:** request with no identity header → 401/redirect on every non-allowlisted route;
  iterate the ~205 routes programmatically to prove deny-by-default has no gaps.
- **Phase 4:** end-to-end — two users log in via the IdP, each spawns a container, each creates a
  project, runs a survey conversion and a validation, and confirms via the filesystem that neither
  can see the other's data root. Then verify no text-format file became an annex symlink
  (CLAUDE.md invariant).
- **Regression:** desktop mode must remain byte-for-byte functional; run the full suite plus a
  manual desktop launch, since Phase 0 touches the shared launcher.
