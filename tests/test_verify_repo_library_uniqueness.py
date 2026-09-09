import json
from pathlib import Path


def _load_verify_repo_module():
    import importlib.util

    module_path = Path(__file__).with_name("verify_repo.py")
    spec = importlib.util.spec_from_file_location("verify_repo", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_survey(library_dir, name, items):
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / name).write_text(json.dumps(items), encoding="utf-8")


def test_flags_item_id_duplicated_across_files(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    library_dir = tmp_path / "official" / "library" / "survey"

    _write_survey(library_dir, "survey-a.json", {"SLEEP01": {"DataType": "integer"}})
    _write_survey(library_dir, "survey-b.json", {"SLEEP01": {"DataType": "integer"}})

    verify_repo.check_library_uniqueness(str(tmp_path))
    output = capsys.readouterr().out

    assert "SLEEP01" in output
    assert "survey-a.json" in output and "survey-b.json" in output


def test_passes_when_all_item_ids_unique(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    library_dir = tmp_path / "official" / "library" / "survey"

    _write_survey(library_dir, "survey-a.json", {"GAD701": {"DataType": "integer"}})
    _write_survey(library_dir, "survey-b.json", {"PHQ901": {"DataType": "integer"}})

    verify_repo.check_library_uniqueness(str(tmp_path))
    output = capsys.readouterr().out

    assert "SLEEP01" not in output
    assert "unique across the official library" in output


def test_skipped_when_library_dir_missing(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    verify_repo.check_library_uniqueness(str(tmp_path))
    output = capsys.readouterr().out

    assert "skipped" in output
