from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"


def test_schema_versioning_documents_per_modality_versions():
    text = (DOCS / "SCHEMA_VERSIONING.md").read_text(encoding="utf-8")
    for needle in ("--modality-version", "SchemaVersions", "modality-version update",
                   "modality-version freeze", "modality-version pin", "archive/", "1.0.0",
                   "Modality schema versions", "SchemaVersionsAcknowledged",
                   "record modality versions"):
        assert needle in text, needle


def test_cli_reference_lists_the_commands():
    text = (DOCS / "CLI_REFERENCE.md").read_text(encoding="utf-8")
    assert "--modality-version" in text
    for action in ("status", "list", "pin", "update", "freeze"):
        assert f"modality-version {action}" in text, action


def test_workflow_tells_maintainers_how_to_release_a_modality_version():
    text = (DOCS / "MODALITY_WORKFLOW.md").read_text(encoding="utf-8")
    assert "archive" in text and "bump" in text


def test_spec_has_clarifications():
    text = (DOCS / "superpowers/specs/2026-10-16-modality-versioning-design.md").read_text(encoding="utf-8")
    assert "Clarifications from the plan" in text
