"""The validator depends on bids-validator-deno exactly where a deno wheel exists (spec 2026-10-07)."""

from pathlib import Path

import pytest

packaging_requirements = pytest.importorskip("packaging.requirements")

ROOT = Path(__file__).resolve().parents[1]


def _requirement(name):
    for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            req = packaging_requirements.Requirement(line)
            if req.name == "bids-validator-deno":
                return req
    raise AssertionError(f"bids-validator-deno missing from {name}")


@pytest.mark.parametrize("name", ["requirements-validator.txt", "requirements-runtime.txt"])
def test_bids_engine_is_declared_with_a_version_range(name):
    req = _requirement(name)
    assert req.specifier.contains("3.0.2") and not req.specifier.contains("4.0.0")
    assert req.specifier.contains("3.9.9") and not req.specifier.contains("3.0.1")


def _supported(machine, platform):
    env = {"sys_platform": platform, "platform_machine": machine, "platform_system": ""}
    return _requirement("requirements-validator.txt").marker.evaluate(env)


@pytest.mark.parametrize(
    "platform,machine,expected",
    [
        ("darwin", "arm64", True),
        ("darwin", "x86_64", True),
        ("linux", "x86_64", True),
        ("linux", "aarch64", True),
        ("win32", "AMD64", True),
        ("win32", "ARM64", False),
        ("linux", "riscv64", False),
        ("linux", "s390x", False),
    ],
)
def test_marker_matches_the_platforms_with_a_deno_wheel(platform, machine, expected):
    assert _supported(machine, platform) is expected


def test_the_unused_pypi_bids_validator_is_gone_from_both_files():
    for name in ("requirements-validator.txt", "requirements-runtime.txt"):
        names = {
            packaging_requirements.Requirement(l).name
            for l in (ROOT / name).read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.lstrip().startswith("#")
        }
        assert "bids-validator" not in names, name


def test_both_files_use_the_same_marker():
    a, b = (_requirement(n) for n in ("requirements-validator.txt", "requirements-runtime.txt"))
    assert str(a.marker) == str(b.marker)
