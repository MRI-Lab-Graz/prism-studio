from __future__ import annotations

import types

from src import runtime_dependencies


def test_inspect_pyreadstat_write_support_reports_writer(monkeypatch) -> None:
    fake_module = types.SimpleNamespace(
        __file__="/tmp/pyreadstat/__init__.py",
        __path__=["/tmp/pyreadstat"],
        write_sav=lambda *_args, **_kwargs: None,
        read_sav=lambda *_args, **_kwargs: None,
        __version__="1.0",
    )

    monkeypatch.setattr(
        runtime_dependencies.importlib,
        "import_module",
        lambda name: fake_module,
    )

    details = runtime_dependencies.inspect_pyreadstat_write_support()

    assert details["pyreadstat_importable"] is True
    assert details["pyreadstat_write_support"] is True
    assert details["namespace_bundle_stub"] is False
    assert details["available_attrs"] == ["__version__", "read_sav", "write_sav"]


def test_inspect_pyreadstat_write_support_detects_bundle_namespace_stub(
    monkeypatch, tmp_path
) -> None:
    bundle_root = tmp_path / "bundle"
    (bundle_root / "pyreadstat").mkdir(parents=True)
    (bundle_root / "pyreadstat.libs").mkdir()

    fake_module = types.SimpleNamespace(
        __path__=[str((bundle_root / "pyreadstat").resolve())],
    )

    monkeypatch.setattr(
        runtime_dependencies.importlib,
        "import_module",
        lambda name: fake_module,
    )

    details = runtime_dependencies.inspect_pyreadstat_write_support(bundle_root=bundle_root)

    assert details["pyreadstat_importable"] is True
    assert details["pyreadstat_write_support"] is False
    assert details["namespace_bundle_stub"] is True
    assert details["bundle_entries"] == ["pyreadstat", "pyreadstat.libs"]


def test_has_pyreadstat_write_support_returns_false_without_writer(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_dependencies,
        "inspect_pyreadstat_write_support",
        lambda bundle_root=None: {"pyreadstat_write_support": False},
    )

    assert runtime_dependencies.has_pyreadstat_write_support() is False