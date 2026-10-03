"""One release version everywhere: the PyPI wheel, citation and docs must agree."""

import json
import re
from pathlib import Path

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
