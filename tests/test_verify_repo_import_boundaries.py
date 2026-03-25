import importlib.util
from pathlib import Path


def _load_verify_repo_module():
    module_path = Path(__file__).with_name("verify_repo.py")
    spec = importlib.util.spec_from_file_location("verify_repo", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_helper_ignores_docstring_examples() -> None:
    verify_repo = _load_verify_repo_module()

    content = '''
"""Usage::

    from app.src.converters.file_reader import read_tabular_file, ReadResult
"""

from pathlib import Path
'''

    assert verify_repo._has_forbidden_app_src_import(content) is False


def test_helper_flags_real_imports() -> None:
    verify_repo = _load_verify_repo_module()

    content = "from app.src.converters.file_reader import read_tabular_file\n"

    assert verify_repo._has_forbidden_app_src_import(content) is True


def test_check_import_boundaries_reports_runtime_import_only(
    tmp_path: Path, capsys
) -> None:
    verify_repo = _load_verify_repo_module()

    app_src = tmp_path / "app" / "src"
    app_src.mkdir(parents=True)

    (app_src / "doc_only.py").write_text(
        '''
"""Usage::

    from app.src.converters.file_reader import read_tabular_file
"""
''',
        encoding="utf-8",
    )
    (app_src / "runtime_import.py").write_text(
        "from app.src.converters.file_reader import read_tabular_file\n",
        encoding="utf-8",
    )

    verify_repo.check_import_boundaries(str(tmp_path))
    output = capsys.readouterr().out

    assert "runtime_import.py" in output
    assert "doc_only.py" not in output
