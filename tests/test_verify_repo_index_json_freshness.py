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


def _write_instrument(library_dir: Path, filename: str, task_name: str) -> None:
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / filename).write_text(
        json.dumps({"Study": {"TaskName": task_name, "OriginalName": task_name}}),
        encoding="utf-8",
    )


def test_passes_when_index_matches_library(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    library_dir = tmp_path / "official" / "library" / "survey"
    _write_instrument(library_dir, "survey-demo.json", "demo")

    from src.instrument_registry import write_registry_index

    write_registry_index(library_dir, library_dir / "index.json")

    verify_repo.check_index_json_freshness(str(tmp_path))
    output = capsys.readouterr().out

    assert "[✗]" not in output
    assert "up to date" in output


def test_fails_when_new_instrument_not_regenerated(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    library_dir = tmp_path / "official" / "library" / "survey"
    _write_instrument(library_dir, "survey-demo.json", "demo")

    from src.instrument_registry import write_registry_index

    write_registry_index(library_dir, library_dir / "index.json")

    # Contributor adds a new template but forgets to regenerate index.json.
    _write_instrument(library_dir, "survey-second.json", "second")

    verify_repo.check_index_json_freshness(str(tmp_path))
    output = capsys.readouterr().out

    assert "[✗]" in output
    assert "second" in output
    assert "out of date" in output


def test_ignores_generated_on_timestamp_only_diff(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    library_dir = tmp_path / "official" / "library" / "survey"
    _write_instrument(library_dir, "survey-demo.json", "demo")

    from src.instrument_registry import write_registry_index

    write_registry_index(library_dir, library_dir / "index.json")

    # Simulate a stale-but-content-identical GeneratedOn timestamp, e.g. from
    # a rebase that replayed the commit at a different time.
    index_path = library_dir / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["GeneratedOn"] = "2000-01-01T00:00:00+00:00"
    index_path.write_text(json.dumps(index), encoding="utf-8")

    verify_repo.check_index_json_freshness(str(tmp_path))
    output = capsys.readouterr().out

    assert "[✗]" not in output


def test_fails_when_index_json_missing(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    library_dir = tmp_path / "official" / "library" / "survey"
    _write_instrument(library_dir, "survey-demo.json", "demo")

    verify_repo.check_index_json_freshness(str(tmp_path))
    output = capsys.readouterr().out

    assert "[✗]" in output
    assert "does not exist" in output


def test_skipped_when_library_dir_missing(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    verify_repo.check_index_json_freshness(str(tmp_path))
    output = capsys.readouterr().out

    assert "skipped" in output


def test_fails_with_malformed_json(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    library_dir = tmp_path / "official" / "library" / "survey"
    library_dir.mkdir(parents=True, exist_ok=True)

    # Write malformed JSON
    index_path = library_dir / "index.json"
    index_path.write_text("{invalid json", encoding="utf-8")

    verify_repo.check_index_json_freshness(str(tmp_path))
    output = capsys.readouterr().out

    assert "[✗]" in output
    assert "not valid JSON" in output


def test_fails_with_non_dict_json(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    library_dir = tmp_path / "official" / "library" / "survey"
    library_dir.mkdir(parents=True, exist_ok=True)

    # Write valid JSON but not a dict (e.g., empty list)
    index_path = library_dir / "index.json"
    index_path.write_text("[]", encoding="utf-8")

    verify_repo.check_index_json_freshness(str(tmp_path))
    output = capsys.readouterr().out

    assert "[✗]" in output
    assert "must be an object" in output
    assert "list" in output
