"""Studio carries a hash-locked copy of a tagged prism-specification release."""

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _check_module():
    spec = importlib.util.spec_from_file_location("check_specification_lock", REPO / "scripts/ci/check_specification_lock.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_lock_matches_tree_and_the_pinned_tag():
    lock = json.loads((REPO / "specification.lock.json").read_text(encoding="utf-8"))
    assert lock["repository"] == "MRI-Lab-Graz/prism-specification" and lock["tag"] == "v1.3.0"
    assert _check_module().check(REPO, lock) == []
