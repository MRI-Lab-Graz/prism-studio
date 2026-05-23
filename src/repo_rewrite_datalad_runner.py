from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from src.bids_entity_rewriter import BidsEntityRewriter
from src.datalad_execution import (
    is_datalad_dataset,
    parse_json_from_output,
)
from src.datalad_mutation_policy import build_pythonpath_env, run_tracked_mutation
from src.subject_code_rewriter import SubjectCodeRewriter


def _run_wrapped_command_or_raise(
    *,
    project_root: Path,
    message: str,
    command: list[str],
    get_paths: list[str],
    get_recursive: bool,
    get_no_data: bool,
) -> dict[str, Any]:
    mutation_result = run_tracked_mutation(
        project_root,
        get_paths=get_paths,
        run_message=message,
        command=command,
        get_timeout_seconds=1800,
        run_timeout_seconds=3600,
        get_recursive=get_recursive,
        get_no_data=get_no_data,
        env=build_pythonpath_env(),
    )

    run_info = mutation_result.get("run") if isinstance(mutation_result, dict) else {}
    payload = parse_json_from_output(str((run_info or {}).get("stdout") or ""))
    if not isinstance(payload, dict):
        raise ValueError(
            "DataLad run finished, but PRISM could not parse rewrite output."
        )

    payload["datalad"] = {"used_run": True, **mutation_result}
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
    get_paths = sorted(
        {
            str(item.get("from") or "").strip()
            for item in list(preview.get("file_renames") or [])
            if isinstance(item, dict) and str(item.get("from") or "").strip()
        }
        | {
            str(item.get("from") or "").strip()
            for item in list(preview.get("directory_renames") or [])
            if isinstance(item, dict) and str(item.get("from") or "").strip()
        }
    )
    if not get_paths:
        get_paths = ["."]
    return _run_wrapped_command_or_raise(
        project_root=root,
        message=run_message,
        command=[sys.executable, "-c", script],
        get_paths=get_paths,
        get_recursive=True,
        get_no_data=True,
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
    get_paths = sorted(
        {
            str(item.get("from") or "").strip()
            for item in list(preview.get("renames") or [])
            if isinstance(item, dict) and str(item.get("from") or "").strip()
        }
    )
    if not get_paths:
        get_paths = ["."]
    return _run_wrapped_command_or_raise(
        project_root=root,
        message=run_message,
        command=[sys.executable, "-c", script],
        get_paths=get_paths,
        get_recursive=False,
        get_no_data=True,
    )
