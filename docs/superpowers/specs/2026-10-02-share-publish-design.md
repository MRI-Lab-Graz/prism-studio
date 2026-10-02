# Share → Server Publish (validity-gated push with audit identity)

Date: 2026-10-02 · Status: draft for review

## Context

A dedicated DataLad server stores all datasets (PRISM format). Each department
has a network drive ("share") holding the department's allowed datasets, each a
DataLad **sibling of the server**. PRISM interacts with the shares only, never
the server directly. Users open and edit the dataset **in place on the share**
(one shared working tree).

## Goals

1. A dataset may be pushed from the share to the server **only if it currently
   validates** (zero validator errors; warnings do not block).
2. Every change and every publish attempt is attributable to a person.

## Non-goals

- Server-side enforcement (server is out of scope).
- Per-department dataset allowlists.
- Locking/concurrency control for simultaneous in-place edits (known risk, later).
- Defending against `git push --no-verify` (documented, not prevented).

## Design

### 1. Gate: `src/share_publish.py`

`publish_to_server(project_root, sibling="server", identity=None)`:

1. Resolve identity (see 3); refuse if none.
2. Run the existing validator on `project_root`. Any error → refuse, return the
   error list, push nothing.
3. Otherwise call existing `run_datalad_push` then `run_datalad_push_verify`
   (`src/datalad_execution.py`), with the identity env applied.
4. Append an audit record (see 3) for allowed *and* refused attempts.

Validation is always re-run inside this function; callers (GUI, hook) never
pass a trusted "is valid" flag.

### 2. Enforcement: git pre-push hook

- `prism publish --install-hook` writes `.git/hooks/pre-push` in the share
  dataset. It runs `prism publish --check` (validate only, identity not
  required) and exits non-zero on errors.
- Applies to plain `git push` and `datalad push`. Only pushes whose remote is
  the server sibling are gated; other remotes pass through.
- If a `pre-push` hook already exists and is not PRISM's, install refuses with
  a message; no overwrite.

### 3. Identity and audit

- Resolution order: `--as "Name <email>"` → `PRISM_USER_NAME` /
  `PRISM_USER_EMAIL` → user's global git config → refuse (no "unknown"
  fallback).
- Applied per command via `GIT_AUTHOR_NAME/EMAIL` and `GIT_COMMITTER_NAME/EMAIL`
  env vars. **Never written to the dataset's git config** (shared tree: repo
  config would be shared by all users).
- The same env is applied in `run_datalad_save` / `run_datalad_run` so edits
  made through PRISM are attributed, not only pushes.
- Audit log: one JSON line per publish attempt appended to `.prism/publish.log`
  in the dataset: timestamp, identity, sibling, result (pushed/refused),
  validator error count. Covers refused attempts, which git history cannot show.
- Text-policy invariant (CLAUDE.md): `.prism/publish.log` is a text file and
  must not be annexed; the `.gitattributes` text rules must cover it (test).

### 4. Surfaces (one implementation)

- **CLI** (`prism_tools.py` / `src/cli`): `prism publish [--check] [--as ...]
  [--sibling NAME] [--install-hook]`.
- **GUI**: Flask route is a thin adapter over `publish_to_server`.
  - Project page: Publish button.
  - **Validator results**: Publish button beside the existing actions.
    - Shown only if the validated path is a DataLad dataset with a server
      sibling.
    - Enabled only if the results payload has `publishable == true` (zero errors
      and sibling present); otherwise disabled with "Fix N errors before
      publishing".
    - On click the backend re-validates; on errors the new errors replace the
      displayed result.
    - If no identity resolves, the dialog asks for name/email and sends them as
      `--as` for that call only.

### 5. Errors

- No identity → refuse, message says how to set one.
- Validator errors → refuse, return errors.
- Sibling missing/unreachable → push fails; reported as-is, still audited.
- Push verify fails → reported as failure (not success).

## Testing (TDD; failing test first)

Fixtures: temp dataset = "share"; local bare repo = "server" sibling.

- Invalid dataset: refused, server unchanged, audit line says refused.
- Valid dataset: server receives commits, audit line says pushed.
- Hook: `git push` to the server sibling blocked on invalid dataset, allowed on
  valid; other remote unaffected; existing foreign hook not overwritten.
- Identity: commit author/committer equal resolved identity; repo `.git/config`
  unchanged; missing identity refused; resolution order honored.
- Validator payload exposes `publishable` (true only for zero errors + sibling).
- GUI route re-validates (stale-valid request on a now-invalid dataset refused).
- `.prism/publish.log` not annexed.
- CLI/GUI parity: same options reachable from both.

## Open items / risks

- Concurrent in-place editing on the shared tree is unsolved.
- `--no-verify` bypass is accepted.
- Unverified: exact validator entry point to call for a full-dataset error count;
  to be confirmed when writing the plan.
