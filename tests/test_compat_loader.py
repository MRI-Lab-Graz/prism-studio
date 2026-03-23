from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

COMPAT_FILE = Path(__file__).resolve().parents[1] / "app" / "src" / "_compat.py"


def _load_module_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_canonical_module_uses_repo_src_file(tmp_path: Path):
    compat = _load_module_from_path("compat_for_success", COMPAT_FILE)

    repo_root = tmp_path / "repo"
    src_dir = repo_root / "src"
    app_src_dir = repo_root / "app" / "src"
    src_dir.mkdir(parents=True)
    app_src_dir.mkdir(parents=True)

    canonical = src_dir / "participants_converter.py"
    canonical.write_text("VALUE = 123\n", encoding="utf-8")

    mirror_file = app_src_dir / "participants_converter.py"
    mirror_file.write_text("# mirror placeholder\n", encoding="utf-8")

    loaded = compat.load_canonical_module(
        current_file=str(mirror_file),
        canonical_rel_path="participants_converter.py",
        alias="prism_backend_participants_converter",
    )

    assert getattr(loaded, "VALUE", None) == 123


def test_load_canonical_module_falls_back_to_mirrored_module_when_missing(
    tmp_path: Path, monkeypatch
):
    compat = _load_module_from_path("compat_for_fallback", COMPAT_FILE)

    repo_root = tmp_path / "repo"
    app_src_dir = repo_root / "app" / "src"
    app_src_dir.mkdir(parents=True)

    mirror_module = app_src_dir / "mirror_module.py"
    mirror_module.write_text(
        textwrap.dedent("""
            LOCAL_CONST = 42

            _loaded = compat.load_canonical_module(
                current_file=__file__,
                canonical_rel_path='participants_converter.py',
                alias='prism_backend_participants_converter'
            )
            FALLBACK_VALUE = getattr(_loaded, 'LOCAL_CONST', None)
            """).strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(sys, "path", [str(repo_root)])

    spec = importlib.util.spec_from_file_location("mirror_module", str(mirror_module))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    module.compat = compat
    sys.modules["mirror_module"] = module
    spec.loader.exec_module(module)

    assert module.FALLBACK_VALUE == 42


def test_resolve_canonical_path_ignores_current_file_in_sys_path(
    tmp_path: Path, monkeypatch
):
    compat = _load_module_from_path("compat_for_self_skip", COMPAT_FILE)

    repo_root = tmp_path / "repo"
    app_src_dir = repo_root / "src"
    app_src_dir.mkdir(parents=True)

    mirror_file = app_src_dir / "recipes_surveys.py"
    mirror_file.write_text("VALUE = 1\n", encoding="utf-8")

    monkeypatch.setattr(sys, "path", [str(repo_root)])

    resolved = compat._resolve_canonical_path(
        mirror_file,
        "recipes_surveys.py",
    )

    assert resolved is None


def test_load_canonical_module_does_not_self_load_from_sys_path(
    tmp_path: Path, monkeypatch
):
    compat = _load_module_from_path("compat_for_self_guard", COMPAT_FILE)

    runtime_root = tmp_path / "_internal"
    src_dir = runtime_root / "src"
    src_dir.mkdir(parents=True)

    mirrored_file = src_dir / "recipes_surveys.py"
    mirrored_file.write_text("# packaged mirrored module\n", encoding="utf-8")

    monkeypatch.setattr(sys, "path", [str(runtime_root)])

    loaded = compat.load_canonical_module(
        current_file=str(mirrored_file),
        canonical_rel_path="recipes_surveys.py",
        alias="prism_backend_recipes_surveys",
    )

    # In packaged layouts, this must fall back instead of recursively loading itself.
    assert loaded is sys.modules[__name__]
