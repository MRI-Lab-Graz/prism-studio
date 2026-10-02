import stat
import subprocess

import pytest

import src.save_gate as sg
from src.datalad_mutation_policy import SaveGateRefusedError, run_tracked_mutation

pytestmark = pytest.mark.skipif(
    not (subprocess.run(["which", "datalad"], capture_output=True).returncode == 0
         and subprocess.run(["which", "git-annex"], capture_output=True).returncode == 0),
    reason="needs datalad and git-annex",
)


@pytest.fixture
def ds(tmp_path, monkeypatch):
    root = tmp_path / "ds"
    subprocess.run(["datalad", "create", "-c", "text2git", str(root)], check=True, capture_output=True)
    (root / "a.txt").write_text("hello\n")
    subprocess.run(["datalad", "save", "-m", "a"], cwd=root, check=True, capture_output=True)
    # fake tool: invalid while a file named BAD exists
    tool = tmp_path / "prism_tools"
    tool.write_text('#!/bin/sh\nif [ -e BAD ]; then echo "PRISM save gate: 1 validation error(s)." ; exit 1; fi\nexit 0\n')
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PRISM_TOOLS", str(tool))
    sg.install_save_hook(root)
    return root


def git_status(root):
    return subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True).stdout


def test_mutation_on_a_tree_dirty_from_a_refused_save_applies_the_change_but_is_not_saved(ds):
    (ds / "BAD").write_text("1")  # dataset is now invalid ...
    (ds / "a.txt").write_text("edited\n")  # ... and dirty inside the mutation scope
    with pytest.raises(SaveGateRefusedError) as info:
        run_tracked_mutation(
            ds, get_paths=["a.txt"], run_message="write out",
            command=["sh", "-c", "echo y > out.txt"],
        )
    assert "not saved" in str(info.value).lower()
    assert (ds / "out.txt").exists()                       # the change was applied
    assert "out.txt" in git_status(ds)                      # ... and is uncommitted
    # now fix the dataset and save once: the gated save goes through
    (ds / "BAD").unlink()
    subprocess.run(["datalad", "save", "-m", "fixed"], cwd=ds, check=True, capture_output=True)
    assert git_status(ds).strip() == ""


def test_clean_valid_tree_still_uses_the_normal_run(ds):
    result = run_tracked_mutation(
        ds, get_paths=["a.txt"], run_message="write out", command=["sh", "-c", "echo y > out.txt"],
    )
    assert result["used_run"] and git_status(ds).strip() == ""


def test_mutation_on_another_file_while_a_refused_change_stays_dirty(ds):
    (ds / "x.txt").write_text("x\n")
    subprocess.run(["datalad", "save", "-m", "x"], cwd=ds, check=True, capture_output=True)
    (ds / "BAD").write_text("1")
    (ds / "x.txt").write_text("x edited\n")  # X: dirty and invalid
    with pytest.raises(SaveGateRefusedError):
        run_tracked_mutation(
            ds, get_paths=["a.txt"], run_message="write out",
            command=["sh", "-c", "echo y > a.txt"],
        )
    assert (ds / "a.txt").read_text() == "y\n"
    status = git_status(ds)
    assert "a.txt" in status and "x.txt" in status
    assert (ds / "x.txt").read_text() == "x edited\n"
    (ds / "BAD").unlink()
    subprocess.run(["datalad", "save", "-m", "fixed"], cwd=ds, check=True, capture_output=True)
    assert git_status(ds).strip() == ""


def test_annexed_content_path_mutation_on_invalid_tree(tmp_path, monkeypatch):
    root = tmp_path / "ds2"
    subprocess.run(["datalad", "create", str(root)], check=True, capture_output=True)
    (root / "big.bin").write_bytes(b"\x00\x01binary")
    subprocess.run(["datalad", "save", "-m", "big"], cwd=root, check=True, capture_output=True)
    tool = tmp_path / "prism_tools"
    tool.write_text('#!/bin/sh\nif [ -e BAD ]; then echo "PRISM save gate: 1 validation error(s)." ; exit 1; fi\nexit 0\n')
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PRISM_TOOLS", str(tool))
    sg.install_save_hook(root)
    (root / "BAD").write_text("1")
    with pytest.raises(SaveGateRefusedError):
        run_tracked_mutation(
            root, get_paths=["big.bin"], content_paths=["big.bin"], run_message="rewrite",
            command=["sh", "-c", "printf 'new' > big.bin"],
        )
    assert (root / "big.bin").read_bytes() == b"new"
