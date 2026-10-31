"""Pick one of the recent projects by the name the user typed (`prism-studio -rp NAME`)."""

from __future__ import annotations


def find_recent_project(projects: list[dict], query: str) -> dict | None:
    """The project named `query` (case-insensitive); else the most recent one whose name contains it.

    `projects` is the recent list, most recent first. A blank query or no match gives None.
    """
    needle = (query or "").strip().casefold()
    if not needle:
        return None
    names = [(str(p.get("name") or "").casefold(), p) for p in projects]
    return next((p for name, p in names if name == needle), None) or next(
        (p for name, p in names if needle in name), None
    )


def recent_project_notice(projects: list[dict], query: str) -> str:
    """The line the launcher prints: which project opens, or why none does and what the list holds."""
    project = find_recent_project(projects, query)
    if project:
        return f"Opening recent project '{project['name']}' ({project['path']})"
    names = ", ".join(str(p.get("name")) for p in projects) or None
    seen = f"recent: {names}" if names else "the recent list is empty"
    return f"No recent project matches '{query}' ({seen}); starting as usual"
