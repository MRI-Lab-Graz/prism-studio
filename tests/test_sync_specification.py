"""scripts/sync_specification.py: the only way the vendored specification changes."""

import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_specification.py"


def _load():
    spec = importlib.util.spec_from_file_location("sync_specification", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sync_mod = _load()


def _source(root: Path, extra=None):
    files = {
        "schemas/stable/survey.schema.json": '{"version": "1.0.0"}\n',
        "schemas/archive/survey/1.0.0.schema.json": '{"version": "1.0.0"}\n',
        "terms/biosample/cortisol.json": '{"TermID": "prism:cortisol"}\n',
        "specs/survey.md": "See [schema](../schemas/stable/survey.schema.json) and [x](https://a.b/c).\n",
        "scripts/check_terms.py": "print('ok')\n",
        "LICENSE": "licence text\n",
        "README.md": "not copied\n",
        "tests/test_x.py": "not copied\n",
        ".github/workflows/ci.yml": "not copied\n",
        **(extra or {}),
    }
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def _studio(root: Path):
    for rel in ("app/schemas/stable/project.schema.json", "docs/specs/project.md"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("studio owned\n", encoding="utf-8")
    return root


def _tree(root: Path):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_sync_maps_files_and_writes_lock(tmp_path):
    src, studio = _source(tmp_path / "src"), _studio(tmp_path / "studio")
    lock = sync_mod.sync(src, studio, "v1.0.0")
    assert (studio / "app/schemas/stable/survey.schema.json").is_file()
    assert (studio / "app/schemas/archive/survey/1.0.0.schema.json").is_file()
    assert (studio / "official/library/terms/biosample/cortisol.json").is_file()
    assert (studio / "scripts/specification/check_terms.py").is_file()
    assert (studio / "app/schemas/PRISM_SPECIFICATION_LICENSE").read_text(encoding="utf-8") == "licence text\n"
    for not_copied in ("README.md", "tests/test_x.py", ".github/workflows/ci.yml"):
        assert not any(k.endswith(not_copied) for k in lock["files"])
    assert not (studio / "tests").exists() and not (studio / "README.md").exists()
    on_disk = json.loads((studio / "specification.lock.json").read_text(encoding="utf-8"))
    assert on_disk == lock and lock["tag"] == "v1.0.0" and lock["repository"] == sync_mod.REPOSITORY
    path = "app/schemas/stable/survey.schema.json"
    assert lock["files"][path] == hashlib.sha256(b'{"version": "1.0.0"}\n').hexdigest()


def test_sync_rewrites_schema_links_in_specs(tmp_path):
    src, studio = _source(tmp_path / "src"), _studio(tmp_path / "studio")
    sync_mod.sync(src, studio, "v1.0.0")
    text = (studio / "docs/specs/survey.md").read_text(encoding="utf-8")
    assert "](../../app/schemas/stable/survey.schema.json)" in text and "](https://a.b/c)" in text


def test_sync_never_touches_studio_owned_files(tmp_path):
    src, studio = _source(tmp_path / "src"), _studio(tmp_path / "studio")
    lock = sync_mod.sync(src, studio, "v1.0.0")
    assert (studio / "docs/specs/project.md").read_text(encoding="utf-8") == "studio owned\n"
    assert (studio / "app/schemas/stable/project.schema.json").read_text(encoding="utf-8") == "studio owned\n"
    assert "docs/specs/project.md" not in lock["files"]


def test_source_carrying_a_studio_owned_file_is_refused(tmp_path):
    src = _source(tmp_path / "src", {"specs/project.md": "from upstream\n"})
    studio = _studio(tmp_path / "studio")
    with pytest.raises(ValueError):
        sync_mod.sync(src, studio, "v1.0.0")
    assert (studio / "docs/specs/project.md").read_text(encoding="utf-8") == "studio owned\n"


def test_sync_twice_is_a_no_op(tmp_path):
    src, studio = _source(tmp_path / "src"), _studio(tmp_path / "studio")
    sync_mod.sync(src, studio, "v1.0.0")
    first = _tree(studio)
    sync_mod.sync(src, studio, "v1.0.0")
    assert _tree(studio) == first


def test_file_dropped_upstream_is_removed_only_if_locked(tmp_path):
    src, studio = _source(tmp_path / "src"), _studio(tmp_path / "studio")
    sync_mod.sync(src, studio, "v1.0.0")
    (studio / "docs/specs/unlisted.md").write_text("mine\n", encoding="utf-8")
    (src / "terms/biosample/cortisol.json").unlink()
    lock = sync_mod.sync(src, studio, "v1.1.0")
    assert not (studio / "official/library/terms/biosample/cortisol.json").exists()
    assert "official/library/terms/biosample/cortisol.json" not in lock["files"]
    assert (studio / "docs/specs/unlisted.md").exists()  # never locked, never ours to delete


def _tar(path: Path, members):
    with tarfile.open(path, "w:gz") as tar:
        for name, kind, data in members:
            info = tarfile.TarInfo(name)
            if kind == "file":
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            elif kind == "symlink":
                info.type, info.linkname = tarfile.SYMTYPE, "/etc/passwd"
                tar.addfile(info)
            else:
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
    return path


def test_extract_reads_a_github_style_archive(tmp_path):
    arc = _tar(tmp_path / "a.tgz", [("prism-specification-1.0.0/", "dir", b""), ("prism-specification-1.0.0/LICENSE", "file", b"x")])
    top = sync_mod.extract(arc, tmp_path / "out")
    assert (top / "LICENSE").read_bytes() == b"x"


@pytest.mark.parametrize(
    "members",
    [
        [("/abs/LICENSE", "file", b"x")],
        [("prism-specification-1.0.0/../evil", "file", b"x")],
        [("prism-specification-1.0.0/link", "symlink", b"")],
        [("prism-specification-1.0.0/a", "file", b"x"), ("other-1.0.0/b", "file", b"y")],
        [("evil-1.0.0/a", "file", b"x")],
    ],
    ids=["absolute", "dotdot", "symlink", "two-top-folders", "wrong-top-folder"],
)
def test_extract_refuses_unsafe_members(tmp_path, members):
    arc = _tar(tmp_path / "a.tgz", members)
    with pytest.raises(ValueError):
        sync_mod.extract(arc, tmp_path / "out")
    assert not (tmp_path / "out").exists() or not any((tmp_path / "out").rglob("*"))


def test_download_url_is_the_tagged_github_archive():
    assert sync_mod.archive_url("v1.0.0") == "https://github.com/MRI-Lab-Graz/prism-specification/archive/refs/tags/v1.0.0.tar.gz"
    for bad in ("../x", "v1/../../x", "main", "v1.0.0?x=1", ""):
        with pytest.raises(ValueError):
            sync_mod.archive_url(bad)
