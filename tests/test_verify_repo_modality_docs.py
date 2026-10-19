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


def _repo(tmp_path: Path, *, page=True, toctree=True, card=True, row=True, suffix_in_page=True) -> Path:
    (tmp_path / "app/schemas/stable").mkdir(parents=True)
    (tmp_path / "app/schemas/stable/entities.schema.json").write_text(
        json.dumps({"modalities": {"biosample": {"kind": "prism", "suffixes": ["bloodchem"]},
                                   "anat": {"kind": "bidsPassthrough"}}}),
        encoding="utf-8",
    )
    specs = tmp_path / "docs/specs"
    specs.mkdir(parents=True)
    if page:
        (specs / "biosample.md").write_text("pattern ..._bloodchem.tsv" if suffix_in_page else "nothing", encoding="utf-8")
    (tmp_path / "docs/index.rst").write_text("   specs/biosample\n" if toctree else "", encoding="utf-8")
    (tmp_path / "docs/SCHEMA_SPECIFICATIONS.md").write_text('href="specs/biosample.html"' if card else "", encoding="utf-8")
    (specs / "entities.md").write_text("| `biosample` | prism |" if row else "", encoding="utf-8")
    return tmp_path


def _run(repo, capsys):
    _load_verify_repo_module().check_modality_docs(str(repo))
    return capsys.readouterr().out


def test_passes_when_everything_is_documented(tmp_path, capsys):
    out = _run(_repo(tmp_path), capsys)
    assert "[✗]" not in out and "documented" in out


def test_bids_passthrough_modalities_are_not_required(tmp_path, capsys):
    assert "anat" not in _run(_repo(tmp_path), capsys)


def test_each_gap_is_reported(tmp_path, capsys):
    for kw, needle in (
        (dict(page=False), "docs/specs/biosample.md"),
        (dict(toctree=False), "docs/index.rst"),
        (dict(card=False), "SCHEMA_SPECIFICATIONS.md"),
        (dict(row=False), "entities.md"),
        (dict(suffix_in_page=False), "_bloodchem"),
    ):
        repo = tmp_path / needle.replace("/", "_")
        repo.mkdir()
        out = _run(_repo(repo, **kw), capsys)
        assert "[✗]" in out and needle in out
