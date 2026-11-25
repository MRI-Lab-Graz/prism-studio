"""One release version everywhere: the PyPI wheel, citation and docs must agree."""

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _grep(path, pattern):
    return re.search(pattern, (ROOT / path).read_text(encoding="utf-8")).group(1)


def test_all_version_strings_match_src_version():
    version = _grep("src/__init__.py", r'__version__ = "([^"]+)"')
    found = {
        "app/src/__init__.py": _grep("app/src/__init__.py", r'__version__ = "([^"]+)"'),
        "setup.py": _grep("setup.py", r'version="([^"]+)"'),
        "CITATION.cff": _grep("CITATION.cff", r'(?m)^version: "([^"]+)"'),
        "docs/conf.py": _grep("docs/conf.py", r'release = "([^"]+)"'),
        "codemeta.json": json.loads((ROOT / "codemeta.json").read_text())["version"],
    }
    assert found == {k: version for k in found}


@pytest.mark.parametrize("package", ["src", "app/src"])
def test_each_src_package_imports_and_reports_the_version(package):
    """Both are the live ``src`` somewhere (CLI: src/, Studio: app/src/), one per process."""
    spec = importlib.util.spec_from_file_location(
        "_version_probe", ROOT / package / "__init__.py", submodule_search_locations=[str(ROOT / package)]
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.__version__ == _grep("src/__init__.py", r'__version__ = "([^"]+)"')
