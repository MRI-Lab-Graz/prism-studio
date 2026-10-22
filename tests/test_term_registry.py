"""Term registry: loader, registry check, column resolution (docs/superpowers/specs/2026-10-22-biosample-term-registry-design.md)."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.term_registry import load_registry  # noqa: E402


def _write(root, modality, name, content):
    folder = root / modality
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(
        content if isinstance(content, str) else json.dumps(content), encoding="utf-8"
    )


def test_load_registry_reads_one_file_per_term(tmp_path):
    a = {"TermID": "prism:cortisol", "Level": "analyte"}
    b = {"TermID": "prism:cortisol.saliva", "Level": "analyte-specimen"}
    _write(tmp_path, "biosample", "cortisol", a)
    _write(tmp_path, "biosample", "cortisol.saliva", b)
    assert load_registry(root=tmp_path) == {"cortisol": a, "cortisol.saliva": b}


def test_load_registry_missing_folder_is_empty(tmp_path):
    assert load_registry(root=tmp_path / "nope") == {}


def test_load_registry_skips_broken_json(tmp_path):
    _write(tmp_path, "biosample", "bad", "{")
    _write(tmp_path, "biosample", "good", {"TermID": "prism:good"})
    assert list(load_registry(root=tmp_path)) == ["good"]
