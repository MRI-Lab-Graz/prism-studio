import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "check_schema_versions.py"
spec = importlib.util.spec_from_file_location("check_schema_versions", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

STABLE = "app/schemas/stable/survey.schema.json"
ARCH = "app/schemas/archive/survey/1.0.0.schema.json"


def _doc(version, extra=0):
    return json.dumps({"version": version, "x": extra})


def _run(changes, base=None, head=None):
    base, head = base or {}, head or {}
    return mod.check(changes, base.get, head.get, lambda p: p in head, {"survey"})


def test_new_modality_without_archive_passes():
    assert _run([("A", STABLE)], head={STABLE: _doc("1.0.0")}) == []


def test_correct_release_passes():
    errors = _run(
        [("M", STABLE), ("A", ARCH)],
        base={STABLE: _doc("1.0.0")},
        head={STABLE: _doc("1.1.0", 1), ARCH: _doc("1.0.0")},
    )
    assert errors == []


def test_changed_content_without_a_version_bump_fails():
    errors = _run([("M", STABLE)], base={STABLE: _doc("1.0.0")}, head={STABLE: _doc("1.0.0", 1)})
    assert any("version" in e for e in errors)


def test_bump_without_archiving_the_previous_version_fails():
    errors = _run([("M", STABLE)], base={STABLE: _doc("1.0.0")}, head={STABLE: _doc("1.1.0")})
    assert any("1.0.0" in e and "archive" in e for e in errors)


def test_archived_copy_must_equal_the_previous_stable_file():
    errors = _run(
        [("M", STABLE), ("A", ARCH)],
        base={STABLE: _doc("1.0.0")},
        head={STABLE: _doc("1.1.0"), ARCH: _doc("1.0.0", 99)},
    )
    assert any("differs" in e for e in errors)


def test_editing_or_deleting_an_archive_file_fails():
    for status in ("M", "D"):
        assert _run([(status, ARCH)], base={ARCH: _doc("1.0.0")}, head={ARCH: _doc("1.0.0", 1)})


def test_unrelated_changes_pass():
    assert _run([("M", "docs/index.rst"), ("M", "app/schemas/stable/project.schema.json")]) == []
