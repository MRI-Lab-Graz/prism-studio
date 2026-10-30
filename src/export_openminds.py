"""openMINDS export with bids2openminds: the run, the description patch and the task list, for the command and Studio."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


class OpenMindsError(Exception):
    """The export could not be made; the message says why."""


def find_bids2openminds() -> str | None:
    """The bids2openminds command: next to the running Python (same environment), else on PATH."""
    from src.cross_platform import get_executable_extension

    candidate = Path(sys.executable).parent / f"bids2openminds{get_executable_extension()}"
    return str(candidate) if candidate.is_file() else shutil.which("bids2openminds")


def openminds_tasks(project_path) -> list[str]:
    """Task names of the project, for the export's pre-flight form."""
    project_json = Path(project_path) / "project.json"
    if not project_json.exists():
        return []
    return sorted(json.loads(project_json.read_text(encoding="utf-8")).get("TaskDefinitions", {}).keys())


def patch_openminds_descriptions(output_path: Path, protocol_descriptions: dict) -> None:
    """Fill in the behavioral protocol descriptions a bids2openminds .jsonld leaves at "To be defined"."""
    if not output_path.exists() or not protocol_descriptions:
        return
    data = json.loads(output_path.read_text(encoding="utf-8"))
    modified = False

    def _str_val(v):
        if isinstance(v, str):
            return v
        if isinstance(v, list) and len(v) == 1 and isinstance(v[0], dict):
            return v[0].get("@value", "")
        if isinstance(v, dict):
            return v.get("@value", "")
        return ""

    def _set_val(node, key, new_val):
        old = node[key]
        if isinstance(old, list) and len(old) == 1 and isinstance(old[0], dict):
            old[0]["@value"] = new_val
        elif isinstance(old, dict):
            old["@value"] = new_val
        else:
            node[key] = new_val

    def _patch_node(node):
        nonlocal modified
        if not isinstance(node, dict):
            return
        name_val = desc_key = None
        for k, v in node.items():
            k_lower = k.lower()
            if k_lower == "name" or k_lower.endswith("/name") or k_lower.endswith(":name"):
                if sv := _str_val(v):
                    name_val = sv
            if k_lower == "description" or k_lower.endswith("/description") or k_lower.endswith(":description"):
                if _str_val(v) == "To be defined":
                    desc_key = k
        if name_val and desc_key and name_val in protocol_descriptions:
            if new_desc := protocol_descriptions[name_val].strip():
                _set_val(node, desc_key, new_desc)
                modified = True

    graph = data.get("@graph", [])
    for node in graph if isinstance(graph, list) else [data]:
        _patch_node(node)
    if modified:
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def run_openminds_export(project_path, data: dict) -> dict:
    """Export to openMINDS next to the project; raises OpenMindsError with the reason when it cannot."""
    project = Path(project_path)
    tool = find_bids2openminds()
    if not tool:
        raise OpenMindsError("bids2openminds is not installed. Install it with: pip install bids2openminds")

    single_file = bool(data.get("single_file", True))
    supplements = data.get("supplements", {}) or {}
    output_path = project.parent / (f"{project.name}_openminds.jsonld" if single_file else f"{project.name}_openminds")
    cmd = [tool, str(project), "-o", str(output_path), "--single-file" if single_file else "--multiple-files", "--quiet"]
    if data.get("include_empty", False):
        cmd.append("--include-empty-properties")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as exc:
        raise OpenMindsError("Export timed out (>5 min)") from exc
    if result.returncode != 0:
        raise OpenMindsError((result.stderr or result.stdout or "bids2openminds conversion failed").strip())

    if (descriptions := supplements.get("protocol_descriptions", {})) and single_file:
        patch_openminds_descriptions(output_path, descriptions)
    notes = {}
    if ethics := str(supplements.get("ethics_category", "")).strip():
        notes["ethics_assessment"] = ethics
    if notes and single_file:
        (output_path.parent / (output_path.stem + "_supplements.json")).write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "success": True,
        "output_path": str(output_path),
        "single_file": single_file,
        "message": "openMINDS export completed successfully",
        "has_notes": bool(notes),
    }
