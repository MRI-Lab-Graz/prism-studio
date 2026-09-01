import os
from pathlib import Path

import pytest


def _load_verify_repo_module():
    import importlib.util

    module_path = Path(__file__).with_name("verify_repo.py")
    spec = importlib.util.spec_from_file_location("verify_repo", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_pair(tmp_path, rel_path, src_content, app_content):
    src_file = tmp_path / "src" / rel_path
    app_file = tmp_path / "app" / "src" / rel_path
    src_file.parent.mkdir(parents=True, exist_ok=True)
    app_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text(src_content, encoding="utf-8")
    app_file.write_text(app_content, encoding="utf-8")
    return src_file, app_file


def test_flags_unresolved_independent_duplicate(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    _make_pair(
        tmp_path,
        "converters/widget.py",
        "def build():\n    return 'src version'\n",
        "def build():\n    return 'app version'\n",
    )

    verify_repo.check_dual_tree_drift(str(tmp_path))
    output = capsys.readouterr().out

    assert "converters/widget.py" in output
    assert "Unresolved dual-tree duplicate" in output


def test_accepts_symlinked_pair(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    src_file, app_file = _make_pair(
        tmp_path,
        "converters/widget.py",
        "def build():\n    return 'canonical'\n",
        "def build():\n    return 'canonical'\n",
    )
    src_file.unlink()
    try:
        src_file.symlink_to(os.path.relpath(app_file, src_file.parent))
    except OSError:
        pytest.skip("Symlinks not supported in this environment")

    verify_repo.check_dual_tree_drift(str(tmp_path))
    output = capsys.readouterr().out

    assert "widget.py" not in output
    assert "passed" in output


def test_accepts_delegation_shim_pair(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    _make_pair(
        tmp_path,
        "converters/widget.py",
        "def build():\n    return 'canonical'\n",
        "from src._compat import load_canonical_module\n"
        "load_canonical_module(current_file=__file__, "
        "canonical_rel_path='converters/widget.py', alias='converters.widget')\n",
    )

    verify_repo.check_dual_tree_drift(str(tmp_path))
    output = capsys.readouterr().out

    assert "widget.py" not in output
    assert "passed" in output


def test_ignores_init_py_duplicates(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    _make_pair(
        tmp_path,
        "maintenance/__init__.py",
        '"""Maintenance utilities."""\n',
        "from .sync_keys import sync_keys\n",
    )

    verify_repo.check_dual_tree_drift(str(tmp_path))
    output = capsys.readouterr().out

    assert "__init__.py" not in output
    assert "passed" in output


def test_skipped_when_trees_missing(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    verify_repo.check_dual_tree_drift(str(tmp_path))
    output = capsys.readouterr().out

    assert "skipped" in output
