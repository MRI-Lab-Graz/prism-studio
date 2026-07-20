from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.datalad_execution import (
    DATALAD_DOCS_URL,
    DATALAD_INSTALL_HINT,
    is_datalad_dataset,
    paths_have_uncommitted_changes,
    resolve_datalad_executable,
    run_datalad_get_paths,
    run_datalad_run,
    run_datalad_save,
    run_datalad_unlock,
)


class MutationNotFullySavedError(ValueError):
    """Raised when the wrapped command errored partway through but may have
    already mutated files on disk before failing.

    `datalad run` does not save anything when the wrapped command exits
    non-zero ("no modifications will be saved" per its own docs) -- but a
    command that partially completes (e.g. deletes/copies several files
    before crashing on one) still leaves those changes sitting in the
    working tree, uncommitted. Callers must not treat this the same as "the
    command failed and nothing happened": an emergency save was attempted to
    capture whatever partial state exists, and the caller needs to surface
    that distinctly rather than silently continuing as if the tree is clean.
    """


def build_pythonpath_env() -> dict[str, str]:
    repo_root = str(Path(__file__).resolve().parents[1])
    existing = str(os.environ.get("PYTHONPATH") or "").strip()
    if existing:
        return {"PYTHONPATH": f"{repo_root}{os.pathsep}{existing}"}
    return {"PYTHONPATH": repo_root}


def run_tracked_mutation(
    project_root: Path,
    *,
    get_paths: Sequence[str],
    run_message: str,
    command: Sequence[str],
    get_timeout_seconds: int = 1800,
    run_timeout_seconds: int = 3600,
    get_recursive: bool = False,
    get_no_data: bool = True,
    content_paths: Sequence[str] = (),
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    root = Path(project_root)
    if not is_datalad_dataset(root):
        return {
            "tracked": False,
            "used_run": False,
            "message": "Project is not tracked by DataLad.",
        }

    datalad_executable = resolve_datalad_executable()
    if not datalad_executable:
        raise ValueError(
            "This project is tracked by DataLad and mutation changes require DataLad run. "
            f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
        )

    # `datalad run` refuses to execute against a dirty working tree (it needs a
    # clean baseline to detect what the wrapped command changed), so any
    # changes left over from earlier actions must be saved first. Scoped to
    # this mutation's own paths: an unscoped `datalad save -r` re-walks every
    # registered subdataset, which turns a per-subject/per-item caller loop
    # (bids_file_deleter.py, datalad_project_copy.py) into O(n^2) work once
    # the dataset has many nested subdatasets.
    autosave_scope_paths = [*get_paths, *content_paths]
    autosave_result = run_datalad_save(
        root,
        message=f'PRISM: autosave pending changes before "{run_message}"',
        datalad_executable=datalad_executable,
        timeout_seconds=max(1, int(run_timeout_seconds)),
        paths=autosave_scope_paths,
    )
    if not autosave_result.get("success"):
        raise ValueError(
            str(
                autosave_result.get("message")
                or "DataLad autosave failed before mutation."
            )
        )

    get_result = run_datalad_get_paths(
        root,
        paths=list(get_paths),
        datalad_executable=datalad_executable,
        timeout_seconds=max(1, int(get_timeout_seconds)),
        recursive=bool(get_recursive),
        no_data=bool(get_no_data),
    )
    if not get_result.get("success"):
        raise ValueError(
            str(get_result.get("message") or "DataLad get failed before mutation.")
        )

    # `content_paths` are files the wrapped command will read+rewrite in
    # place (e.g. updating subject IDs inside a .tsv/.json). Those need full
    # content present locally (not just `-n` presence) and need to be
    # unlocked, since annexed files are normally read-only symlinks.
    content_get_result: dict[str, Any] = {"attempted": False, "success": True, "message": "", "command": ""}
    unlock_result: dict[str, Any] = {"attempted": False, "success": True, "message": "", "command": ""}
    normalized_content_paths = list(content_paths)
    if normalized_content_paths:
        content_get_result = run_datalad_get_paths(
            root,
            paths=normalized_content_paths,
            datalad_executable=datalad_executable,
            timeout_seconds=max(1, int(get_timeout_seconds)),
            recursive=False,
            no_data=False,
        )
        if not content_get_result.get("success"):
            raise ValueError(
                str(
                    content_get_result.get("message")
                    or "DataLad get (content) failed before mutation."
                )
            )

        unlock_result = run_datalad_unlock(
            root,
            paths=normalized_content_paths,
            datalad_executable=datalad_executable,
            timeout_seconds=max(1, int(get_timeout_seconds)),
        )

        # `datalad unlock` is treated as best-effort (it's a harmless no-op
        # for files that aren't annexed), so its own exit code can't be
        # trusted to tell us whether the file actually became writable.
        # Check the real, ground-truth condition that caused the original
        # bug instead of trusting the tool's report.
        still_locked = [
            path_text
            for path_text in normalized_content_paths
            if (root / path_text).exists() and not os.access(root / path_text, os.W_OK)
        ]
        if still_locked:
            raise ValueError(
                "These files are still read-only after 'datalad unlock' and "
                "the wrapped command would fail trying to write to them: "
                f"{', '.join(still_locked)}. DataLad unlock said: "
                f"{unlock_result.get('message') or '(no message)'}"
            )

    # `datalad unlock` itself changes the working tree (a symlink becomes a
    # regular file), which dirties the dataset again even though we just
    # autosaved above. `datalad run` needs a clean baseline immediately
    # before it starts, so autosave once more right before it.
    pre_run_autosave_result: dict[str, Any] = {
        "attempted": False,
        "success": True,
        "no_changes": True,
        "message": "",
        "command": "",
    }
    if normalized_content_paths:
        pre_run_autosave_result = run_datalad_save(
            root,
            message=f'PRISM: autosave unlock state before "{run_message}"',
            datalad_executable=datalad_executable,
            timeout_seconds=max(1, int(run_timeout_seconds)),
            paths=normalized_content_paths,
        )
        if not pre_run_autosave_result.get("success"):
            raise ValueError(
                str(
                    pre_run_autosave_result.get("message")
                    or "DataLad autosave (post-unlock) failed before mutation."
                )
            )

    run_result = run_datalad_run(
        root,
        message=run_message,
        command=list(command),
        datalad_executable=datalad_executable,
        timeout_seconds=max(1, int(run_timeout_seconds)),
        env=env,
    )
    if not run_result.get("success"):
        run_message_detail = str(run_result.get("message") or "DataLad run failed for mutation.")
        # The wrapped command may have partially deleted/copied/renamed files
        # before erroring; `datalad run` itself won't have saved any of that
        # ("no modifications will be saved" on error, per its own docs).
        # Checked *before* the emergency save below, since a successful save
        # would make the tree clean again and hide the very thing we're
        # trying to detect.
        mutated = paths_have_uncommitted_changes(root, paths=autosave_scope_paths)
        emergency_save = run_datalad_save(
            root,
            message=f'{run_message} (partial run failure -- emergency save)',
            datalad_executable=datalad_executable,
            timeout_seconds=max(1, int(run_timeout_seconds)),
            paths=autosave_scope_paths,
        )
        if mutated:
            saved_note = (
                "Partial on-disk changes were captured via an emergency "
                "'datalad save'."
                if emergency_save.get("success")
                else "An emergency 'datalad save' ALSO failed "
                f"({emergency_save.get('message') or 'unknown error'}) -- "
                "these changes are still uncommitted."
            )
            raise MutationNotFullySavedError(
                f"DataLad run failed partway through ({run_message_detail}). "
                f"{saved_note} This operation is INCOMPLETE and needs manual "
                "review."
            )
        raise ValueError(run_message_detail)

    return {
        "tracked": True,
        "used_run": True,
        "executable": datalad_executable,
        "autosave": {
            "attempted": bool(autosave_result.get("attempted")),
            "success": bool(autosave_result.get("success")),
            "no_changes": bool(autosave_result.get("no_changes")),
            "message": str(autosave_result.get("message") or ""),
            "command": str(autosave_result.get("command") or ""),
        },
        "get": {
            "attempted": bool(get_result.get("attempted")),
            "success": bool(get_result.get("success")),
            "message": str(get_result.get("message") or ""),
            "command": str(get_result.get("command") or ""),
        },
        "content_get": {
            "attempted": bool(content_get_result.get("attempted")),
            "success": bool(content_get_result.get("success")),
            "message": str(content_get_result.get("message") or ""),
            "command": str(content_get_result.get("command") or ""),
        },
        "unlock": {
            "attempted": bool(unlock_result.get("attempted")),
            "success": bool(unlock_result.get("success")),
            "message": str(unlock_result.get("message") or ""),
            "command": str(unlock_result.get("command") or ""),
        },
        "pre_run_autosave": {
            "attempted": bool(pre_run_autosave_result.get("attempted")),
            "success": bool(pre_run_autosave_result.get("success")),
            "no_changes": bool(pre_run_autosave_result.get("no_changes")),
            "message": str(pre_run_autosave_result.get("message") or ""),
            "command": str(pre_run_autosave_result.get("command") or ""),
        },
        "run": {
            "attempted": bool(run_result.get("attempted")),
            "success": bool(run_result.get("success")),
            "message": str(run_result.get("message") or ""),
            "command": str(run_result.get("command") or ""),
            "stdout": str(run_result.get("stdout") or ""),
            "stderr": str(run_result.get("stderr") or ""),
        },
    }
