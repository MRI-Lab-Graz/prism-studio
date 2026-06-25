from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

from src.datalad_execution import is_datalad_dataset, parse_json_from_output
from src.datalad_mutation_policy import run_tracked_mutation

_SUBJECT_PART_PATTERN = re.compile(r"^sub-[A-Za-z0-9]+$")


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"Path is outside project root: {path}") from exc


def _extract_subject_from_rel_path(rel_path: str) -> str | None:
    parts = [part for part in Path(rel_path).parts if part]
    for part in parts:
        if _SUBJECT_PART_PATTERN.fullmatch(part):
            return part
    return None


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

    grouped_pairs: dict[str, list[tuple[Path, Path, str]]] = {}
    for src_path, dst_path, rel_path in pairs:
        subject = _extract_subject_from_rel_path(rel_path) or "__dataset_root__"
        grouped_pairs.setdefault(subject, []).append((src_path, dst_path, rel_path))

    all_copied_paths: list[str] = []
    group_results: list[dict[str, Any]] = []
    for subject, subject_pairs in sorted(grouped_pairs.items(), key=lambda item: item[0]):
        existing_rel_paths = [
            rel for _, dst_path, rel in subject_pairs if dst_path.exists()
        ]
        manifest = {
            "copies": [
                {"src": str(src_path), "dst": str(dst_path), "rel": rel_path}
                for src_path, dst_path, rel_path in subject_pairs
            ]
        }

        fd, manifest_path = tempfile.mkstemp(prefix="prism_datalad_copy_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(manifest, handle)

            script = (
                "import json, shutil, sys\n"
                "from pathlib import Path\n"
                "manifest = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
                "copied = []\n"
                "for item in manifest.get('copies', []):\n"
                "    src = Path(item['src'])\n"
                "    dst = Path(item['dst'])\n"
                "    dst.parent.mkdir(parents=True, exist_ok=True)\n"
                "    shutil.copy2(src, dst)\n"
                "    copied.append(item['rel'])\n"
                "print(json.dumps({'copied_count': len(copied), 'copied_paths': copied}, ensure_ascii=False))\n"
            )

            subject_message = (
                f"{run_message} ({subject})"
                if subject != "__dataset_root__"
                else run_message
            )
            mutation_result = run_tracked_mutation(
                root,
                get_paths=existing_rel_paths,
                run_message=subject_message,
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
            all_copied_paths.extend(str(item) for item in copied_paths)
            group_results.append(
                {
                    "subject": subject,
                    "copied_count": int(parsed.get("copied_count") or len(copied_paths)),
                    "copied_paths": [str(item) for item in copied_paths],
                    "get": mutation_result.get("get"),
                    "run": mutation_result.get("run"),
                }
            )
        finally:
            Path(manifest_path).unlink(missing_ok=True)

    return {
        "copied_count": len(all_copied_paths),
        "copied_paths": all_copied_paths,
        "datalad": {
            "tracked": True,
            "used_run": True,
            "run_per_subject": True,
            "run_count": len(group_results),
            "groups": group_results,
            "message": "DataLad run recorded subject-scoped copy commits.",
        },
    }
