from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.datalad_execution import (
    DATALAD_DOCS_URL,
    DATALAD_INSTALL_HINT,
    is_datalad_dataset,
    resolve_datalad_executable,
    run_datalad_get_paths,
    run_datalad_run,
)


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

    run_result = run_datalad_run(
        root,
        message=run_message,
        command=list(command),
        datalad_executable=datalad_executable,
        timeout_seconds=max(1, int(run_timeout_seconds)),
        env=env,
    )
    if not run_result.get("success"):
        raise ValueError(
            str(run_result.get("message") or "DataLad run failed for mutation.")
        )

    return {
        "tracked": True,
        "used_run": True,
        "executable": datalad_executable,
        "get": {
            "attempted": bool(get_result.get("attempted")),
            "success": bool(get_result.get("success")),
            "message": str(get_result.get("message") or ""),
            "command": str(get_result.get("command") or ""),
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
