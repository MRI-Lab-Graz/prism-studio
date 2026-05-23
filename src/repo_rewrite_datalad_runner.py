from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from src.bids_entity_rewriter import BidsEntityRewriter
from src.datalad_execution import (
    DATALAD_INSTALL_HINT,
    DATALAD_DOCS_URL,
    is_datalad_dataset,
    parse_json_from_output,
    resolve_datalad_executable,
    run_datalad_get_recursive,
    run_datalad_run,
)
from src.subject_code_rewriter import SubjectCodeRewriter


def _build_pythonpath_env() -> dict[str, str]:
    repo_root = str(Path(__file__).resolve().parents[1])
    existing = str(os.environ.get("PYTHONPATH") or "").strip()
    if existing:
        return {"PYTHONPATH": f"{repo_root}{os.pathsep}{existing}"}
    return {"PYTHONPATH": repo_root}


def _ensure_datalad_available_or_raise(project_root: Path) -> str:
    datalad_executable = resolve_datalad_executable()
    if datalad_executable:
        return datalad_executable
    raise ValueError(
        "This project is tracked by DataLad and rewrite changes require DataLad run. "
        f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
    )


def _run_wrapped_command_or_raise(
    *,
    project_root: Path,
    datalad_executable: str,
    message: str,
    command: list[str],
) -> dict[str, Any]:
    get_result = run_datalad_get_recursive(
        project_root,
        datalad_executable=datalad_executable,
        timeout_seconds=1800,
    )
    if not get_result.get("success"):
        raise ValueError(
            str(get_result.get("message") or "DataLad get failed before rewrite.")
        )

    run_result = run_datalad_run(
        project_root,
        message=message,
        command=command,
        datalad_executable=datalad_executable,
        timeout_seconds=3600,
        env=_build_pythonpath_env(),
    )
    if not run_result.get("success"):
        raise ValueError(
            str(run_result.get("message") or "DataLad run failed for rewrite.")
        )

    payload = parse_json_from_output(str(run_result.get("stdout") or ""))
    if not isinstance(payload, dict):
        raise ValueError(
            "DataLad run finished, but PRISM could not parse rewrite output."
        )

    payload["datalad"] = {
        "used_run": True,
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
        },
    }
    return payload


def apply_subject_rewrite(
    project_root: Path,
    *,
    mode: str,
    example_subject: str | None,
    keep_fragment: str | None,
    allow_many_to_one: bool,
) -> dict[str, Any]:
    root = Path(project_root)
    rewriter = SubjectCodeRewriter(root)

    preview = rewriter.preview(
        mode=mode,
        example_subject=example_subject,
        keep_fragment=keep_fragment,
        allow_many_to_one=allow_many_to_one,
    )

    should_use_datalad_run = (
        is_datalad_dataset(root)
        and (
            int(preview.get("file_rename_count") or 0) > 0
            or int(preview.get("directory_rename_count") or 0) > 0
        )
    )
    if not should_use_datalad_run:
        return rewriter.apply(
            mode=mode,
            example_subject=example_subject,
            keep_fragment=keep_fragment,
            allow_many_to_one=allow_many_to_one,
        )

    datalad_executable = _ensure_datalad_available_or_raise(root)
    script = (
        "import json;"
        "from pathlib import Path;"
        "from src.subject_code_rewriter import SubjectCodeRewriter;"
        f"result=SubjectCodeRewriter(Path({json.dumps(str(root))})).apply("
        f"mode={json.dumps(mode)},"
        f"example_subject={json.dumps(example_subject)},"
        f"keep_fragment={json.dumps(keep_fragment)},"
        f"allow_many_to_one={json.dumps(bool(allow_many_to_one))}"
        ");"
        "print(json.dumps(result, ensure_ascii=False))"
    )

    run_message = "PRISM: Rewrite subject IDs"
    return _run_wrapped_command_or_raise(
        project_root=root,
        datalad_executable=datalad_executable,
        message=run_message,
        command=[sys.executable, "-c", script],
    )


def apply_entity_rewrite(
    project_root: Path,
    *,
    modality: str,
    entity: str,
    operation: str,
    current_value: str | None,
    replacement: str | None,
) -> dict[str, Any]:
    root = Path(project_root)
    rewriter = BidsEntityRewriter(root)

    preview = rewriter.preview(
        modality=modality,
        entity=entity,
        current_value=current_value,
        operation=operation,
        replacement=replacement,
    )

    should_use_datalad_run = (
        is_datalad_dataset(root)
        and int(preview.get("rename_count") or 0) > 0
    )
    if not should_use_datalad_run:
        return rewriter.apply(
            modality=modality,
            entity=entity,
            current_value=current_value,
            operation=operation,
            replacement=replacement,
        )

    datalad_executable = _ensure_datalad_available_or_raise(root)
    script = (
        "import json;"
        "from pathlib import Path;"
        "from src.bids_entity_rewriter import BidsEntityRewriter;"
        f"result=BidsEntityRewriter(Path({json.dumps(str(root))})).apply("
        f"modality={json.dumps(modality)},"
        f"entity={json.dumps(entity)},"
        f"operation={json.dumps(operation)},"
        f"current_value={json.dumps(current_value)},"
        f"replacement={json.dumps(replacement)}"
        ");"
        "print(json.dumps(result, ensure_ascii=False))"
    )

    run_message = "PRISM: Rewrite BIDS filename entity"
    return _run_wrapped_command_or_raise(
        project_root=root,
        datalad_executable=datalad_executable,
        message=run_message,
        command=[sys.executable, "-c", script],
    )
