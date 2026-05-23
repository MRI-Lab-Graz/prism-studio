from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

from src.datalad_execution import is_datalad_dataset, parse_json_from_output
from src.datalad_mutation_policy import run_tracked_mutation


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"Path is outside project root: {path}") from exc


def copy_files_into_project(
    *,
    dataset_root: Path,
    copy_pairs: Sequence[tuple[Path, Path]],
    run_message: str,
) -> dict[str, Any]:
    root = Path(dataset_root)
    pairs: list[tuple[Path, Path, str]] = []
    for src, dst in copy_pairs:
        src_path = Path(src).resolve()
        dst_path = Path(dst).resolve()
        if not src_path.exists() or not src_path.is_file():
            raise ValueError(f"Source file does not exist: {src_path}")
        rel_path = _relative_to_root(dst_path, root)
        pairs.append((src_path, dst_path, rel_path))

    if not pairs:
        return {
            "copied_count": 0,
            "copied_paths": [],
            "datalad": {
                "tracked": is_datalad_dataset(root),
                "used_run": False,
                "message": "No files to copy.",
            },
        }

    if not is_datalad_dataset(root):
        copied_rel: list[str] = []
        for src_path, dst_path, rel_path in pairs:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)
            copied_rel.append(rel_path)
        return {
            "copied_count": len(copied_rel),
            "copied_paths": copied_rel,
            "datalad": {
                "tracked": False,
                "used_run": False,
                "message": "Project is not tracked by DataLad.",
            },
        }

    existing_rel_paths = [rel for _, dst_path, rel in pairs if dst_path.exists()]
    manifest = {
        "copies": [
            {"src": str(src_path), "dst": str(dst_path), "rel": rel_path}
            for src_path, dst_path, rel_path in pairs
        ]
    }

    fd, manifest_path = tempfile.mkstemp(prefix="prism_datalad_copy_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)

        script = (
            "import json, shutil, sys; "
            "from pathlib import Path; "
            "manifest = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')); "
            "copied = []; "
            "for item in manifest.get('copies', []): "
            " src = Path(item['src']); dst = Path(item['dst']); "
            " dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst); copied.append(item['rel']); "
            "print(json.dumps({'copied_count': len(copied), 'copied_paths': copied}, ensure_ascii=False))"
        )

        mutation_result = run_tracked_mutation(
            root,
            get_paths=existing_rel_paths,
            run_message=run_message,
            command=[sys.executable, "-c", script, manifest_path],
            get_timeout_seconds=1800,
            run_timeout_seconds=7200,
            get_recursive=False,
            get_no_data=False,
        )

        parsed = parse_json_from_output(
            mutation_result.get("run", {}).get("stdout") or ""
        )
        if not isinstance(parsed, dict):
            raise ValueError("Could not parse DataLad run output for copied files.")

        copied_paths = parsed.get("copied_paths")
        if not isinstance(copied_paths, list):
            copied_paths = []

        return {
            "copied_count": int(parsed.get("copied_count") or len(copied_paths)),
            "copied_paths": [str(item) for item in copied_paths],
            "datalad": {
                "tracked": True,
                "used_run": True,
                "message": str(mutation_result.get("run", {}).get("message") or ""),
                "command": str(mutation_result.get("run", {}).get("command") or ""),
                "get": mutation_result.get("get"),
            },
        }
    finally:
        Path(manifest_path).unlink(missing_ok=True)
