"""scripts/ci/check_specification_lock.py: the vendored specification must equal its lock."""

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sync_mod = _load("sync_specification", "scripts/sync_specification.py")
check_mod = _load("check_specification_lock", "scripts/ci/check_specification_lock.py")


def _studio(tmp_path):
    src, studio = tmp_path / "src", tmp_path / "studio"
    for rel, text in {
        "schemas/stable/survey.schema.json": '{"version": "1.0.0"}\n',
        "terms/biosample/cortisol.json": '{"TermID": "prism:cortisol"}\n',
        "specs/survey.md": "text\n",
        "LICENSE": "licence\n",
    }.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    (studio / "docs/specs").mkdir(parents=True)
    (studio / "docs/specs/project.md").write_text("studio owned\n", encoding="utf-8")
    lock = sync_mod.sync(src, studio, "v1.0.0")
    return studio, lock


def test_clean_tree_passes(tmp_path):
    studio, lock = _studio(tmp_path)
    assert check_mod.check(studio, lock) == []


def test_edited_vendored_file_fails(tmp_path):
    studio, lock = _studio(tmp_path)
    (studio / "app/schemas/stable/survey.schema.json").write_text('{"version": "9"}\n', encoding="utf-8")
    problems = check_mod.check(studio, lock)
    assert len(problems) == 1 and "survey.schema.json" in problems[0] and "prism-specification" in problems[0]


def test_missing_file_fails(tmp_path):
    studio, lock = _studio(tmp_path)
    (studio / "official/library/terms/biosample/cortisol.json").unlink()
    assert any("cortisol.json" in p and "missing" in p for p in check_mod.check(studio, lock))


def test_extra_file_in_vendored_folder_fails(tmp_path):
    studio, lock = _studio(tmp_path)
    (studio / "official/library/terms/biosample/new.json").write_text("{}\n", encoding="utf-8")
    assert any("new.json" in p for p in check_mod.check(studio, lock))


def test_studio_owned_files_are_allowed(tmp_path):
    studio, lock = _studio(tmp_path)
    (studio / "app/schemas/stable").mkdir(parents=True, exist_ok=True)
    (studio / "app/schemas/stable/project.schema.json").write_text("{}\n", encoding="utf-8")
    (studio / "docs/specs/project.md").write_text("edited by Studio\n", encoding="utf-8")
    assert check_mod.check(studio, lock) == []


def test_crlf_checkout_passes(tmp_path):
    studio, lock = _studio(tmp_path)
    p = studio / "docs/specs/survey.md"
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    assert check_mod.check(studio, lock) == []


def test_main_reports_a_missing_lock(tmp_path, capsys):
    assert check_mod.main([str(tmp_path)]) == 1
    assert "specification.lock.json" in capsys.readouterr().out


def test_main_passes_on_a_clean_tree(tmp_path):
    studio, _lock = _studio(tmp_path)
    assert check_mod.main([str(studio)]) == 0


def test_os_junk_in_vendored_folders_is_ignored(tmp_path):
    studio, lock = _studio(tmp_path)
    (studio / "app/schemas/.DS_Store").write_bytes(b"\x00")
    (studio / "official/library/terms/biosample/._cortisol.json").write_bytes(b"\x00")
    (studio / "docs/specs/Thumbs.db").write_bytes(b"\x00")
    assert check_mod.check(studio, lock) == []
