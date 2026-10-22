"""The validator image must carry every file the validator reads at run time (the wheel and the frozen build have their own tests)."""

from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[1] / "Dockerfile"


def _copied_sources() -> set[str]:
    return {parts[1] for parts in (line.split() for line in DOCKERFILE.read_text(encoding="utf-8").splitlines()) if parts[:1] == ["COPY"]}


def test_the_image_copies_the_vendored_specification_scripts_the_overlay_loads():
    assert "scripts/specification/" in _copied_sources()


def test_the_image_still_copies_the_schemas_and_terms():
    assert {"app/schemas/", "official/library/terms/"} <= _copied_sources()
