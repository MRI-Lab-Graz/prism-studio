"""The project's README.md and CITATION.cff, written from its metadata.

One implementation for Studio's "Generate README" / "Regenerate citation" buttons and `prism_tools project ...`.
"""

from __future__ import annotations

from pathlib import Path


def remove_legacy_contributor_files(project_root: Path) -> None:
    """Delete legacy contributor files once project.json is canonical (best effort, never fails a save)."""
    for name in ("contributors.json", "contributor.json"):
        try:
            (project_root / name).unlink(missing_ok=True)
        except OSError:
            pass


def generate_readme(project_root: Path) -> dict:
    """Write README.md from project.json. Raises FileNotFoundError when there is no project.json."""
    from src.readme_generator import ReadmeGenerator

    if not (project_root / "project.json").exists():
        raise FileNotFoundError("project.json not found")
    generator = ReadmeGenerator(project_root)
    path = generator.save()
    message = "README.md generated successfully"
    if generator.merge_note:
        message = f"README.md generated and updated. {generator.merge_note}"
    return {"path": str(path), "message": message, "merge_note": generator.merge_note}


def regenerate_citation(project_root: Path, project_manager=None) -> dict:
    """Write CITATION.cff from the project's metadata and report its health."""
    if project_manager is None:
        from src.project_manager import ProjectManager

        project_manager = ProjectManager()
    project_manager.regenerate_citation_cff(project_root)
    remove_legacy_contributor_files(project_root)
    return {"message": "CITATION.cff regenerated successfully", **project_manager.get_citation_cff_status(project_root)}
