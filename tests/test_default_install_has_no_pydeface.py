"""The default install (requirements.txt) must not pull in pydeface: it needs FSL to run, drags in
nipype/traits (a C compiler on ARM Linux) and makes every install slow. Defacing is a documented extra."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _requirements(name):
    for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line.startswith("-r "):
            yield from _requirements(line[3:].strip())
        elif line:
            yield line


def test_default_install_does_not_include_pydeface():
    assert not [r for r in _requirements("requirements.txt") if r.lower().startswith("pydeface")]
