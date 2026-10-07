#!/usr/bin/env python3
"""Build the CLI-only ``prism-validator`` wheel for PyPI.

Stages exactly the files listed in scripts/validator_manifest.txt (the import
closure of app/prism.py) plus app/schemas under ``prism_validator/``, keeping the
repo-relative app/ + src/ layout the code relies on, then builds the wheel.
Version and dependencies come from src/__init__.py and requirements-validator.txt.

Refresh the manifest after changing what the validator imports: run
app/prism.py on a dataset and list the loaded app/ and src/ files.
tests/test_validator_manifest_closure.py enforces that every local import of a
manifest file (lazy, function-level imports included) is itself listed.
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CLI = '''import os
import runpy
import sys
from pathlib import Path


def main():
    app = Path(__file__).resolve().parent / "app"
    os.environ.setdefault("PRISM_SKIP_VENV_CHECK", "1")
    sys.path.insert(0, str(app))
    sys.argv[0] = "prism-validator"
    runpy.run_path(str(app / "prism.py"), run_name="__main__")
'''

PYPROJECT = """[build-system]
requires = ["setuptools>=64"]
build-backend = "setuptools.build_meta"

[project]
name = "prism-validator"
version = "{version}"
description = "PRISM dataset validator (command line only)"
readme = "README.md"
requires-python = ">=3.10"
license = {{text = "AGPL-3.0-only"}}
authors = [{{name = "MRI-Lab-Graz"}}]
dependencies = {deps}
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Science/Research",
    "Topic :: Scientific/Engineering",
    "License :: OSI Approved :: GNU Affero General Public License v3",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
]

[project.urls]
Homepage = "https://github.com/MRI-Lab-Graz/prism-studio"
Issues = "https://github.com/MRI-Lab-Graz/prism-studio/issues"

[project.scripts]
prism-validator = "prism_validator.cli:main"

[tool.setuptools.packages.find]
include = ["prism_validator*"]

[tool.setuptools.package-data]
"*" = ["*.json", "*.md"]
"""


def stage(dest: Path) -> None:
    pkg = dest / "prism_validator"
    files = (ROOT / "scripts" / "validator_manifest.txt").read_text().split()
    for rel in files:
        target = pkg / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)  # follows symlinks
    shutil.copytree(ROOT / "app" / "schemas", pkg / "app" / "schemas")
    (pkg / "__init__.py").write_text("")
    (pkg / "cli.py").write_text(CLI)
    src_init = (ROOT / "src" / "__init__.py").read_text(encoding="utf-8")
    version = re.search(r'__version__ = "([^"]+)"', src_init).group(1)
    deps = [
        line.strip()
        for line in (ROOT / "requirements-validator.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    (dest / "pyproject.toml").write_text(
        PYPROJECT.format(version=version, deps=repr(deps).replace("'", '"'))
    )
    shutil.copy2(ROOT / "README.md", dest / "README.md")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    out = parser.parse_args().out.resolve()
    with tempfile.TemporaryDirectory() as tmp:
        stage(Path(tmp))
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps",
             "-q", "-w", str(out), tmp],
            check=True,
        )


if __name__ == "__main__":
    main()
