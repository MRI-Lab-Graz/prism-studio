"""remove_tree() must delete read-only trees the way git-annex leaves them.

git-annex stores annexed content as read-only objects. POSIX only needs write
permission on the parent directory to unlink a file, so a plain rmtree works
there and this whole class of bug is invisible on macOS/Linux. Windows refuses
to unlink a read-only file outright, so a failed `datalad clone` used to leave a
partial dataset behind that blocked the retry.

The read-only *file* case is forced here on every platform. The read-only
*directory* case is POSIX-only, since Windows ignores the directory write bit.
"""

import os
import shutil
import stat
import sys

import pytest

from src.cross_platform import remove_tree


def _build_readonly_tree(root):
    """A directory holding a read-only file, like an annex object store."""
    objects = root / "annex" / "objects"
    objects.mkdir(parents=True)
    payload = objects / "SHA256E-s1234--deadbeef.nii.gz"
    payload.write_text("annexed content")
    payload.chmod(stat.S_IRUSR)  # read-only, exactly as git-annex leaves it
    return payload


def test_removes_tree_containing_read_only_files(tmp_path):
    root = tmp_path / "clone"
    payload = _build_readonly_tree(root)
    assert payload.exists()

    remove_tree(root)

    assert not root.exists()


def test_plain_rmtree_is_the_thing_that_fails(tmp_path):
    """Pins why remove_tree exists, so nobody 'simplifies' it back to rmtree."""
    root = tmp_path / "clone"
    _build_readonly_tree(root)

    # shutil.rmtree(ignore_errors=True) suppresses onerror entirely, so it
    # cannot even retry: on Windows the tree would simply survive.
    shutil.rmtree(root, ignore_errors=True)
    if sys.platform.startswith("win"):
        assert root.exists(), "expected Windows to refuse the read-only unlink"
        remove_tree(root)
        assert not root.exists()


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="Windows ignores the directory write bit, so this cannot be staged there",
)
def test_removes_tree_with_read_only_directory(tmp_path):
    root = tmp_path / "clone"
    nested = root / "locked"
    nested.mkdir(parents=True)
    (nested / "file.txt").write_text("x")
    nested.chmod(stat.S_IRUSR | stat.S_IXUSR)  # no write bit: cannot unlink inside

    try:
        remove_tree(root)
    finally:
        if nested.exists():
            nested.chmod(stat.S_IRWXU)

    assert not root.exists()


def test_ignore_errors_swallows_what_it_cannot_delete(tmp_path):
    missing = tmp_path / "never-existed"

    remove_tree(missing, ignore_errors=True)  # must not raise

    with pytest.raises(OSError):
        remove_tree(missing)


def test_ignore_errors_still_deletes_read_only_content(tmp_path):
    """The flag must not cost us the chmod retry - that was the original bug."""
    root = tmp_path / "clone"
    _build_readonly_tree(root)

    remove_tree(root, ignore_errors=True)

    assert not root.exists()


def test_leaves_unrelated_siblings_alone(tmp_path):
    keep = tmp_path / "keep"
    keep.mkdir()
    (keep / "data.txt").write_text("keep me")
    doomed = tmp_path / "doomed"
    _build_readonly_tree(doomed)

    remove_tree(doomed)

    assert not doomed.exists()
    assert (keep / "data.txt").read_text() == "keep me"


def test_is_reachable_through_the_src_namespace_package():
    """CLAUDE.md dual-tree check: one physical file must answer this import."""
    import src.cross_platform as module

    assert module.__file__.endswith(os.path.join("app", "src", "cross_platform.py"))
