"""
Utilities for scanning PRISM / BIDS project structure.

Provides information about available sessions and modalities
within a project directory, used for selective export/sharing.
"""

from pathlib import Path
from typing import Dict, List, Set


def get_project_modalities_and_sessions(project_path: Path) -> Dict[str, object]:
    """
    Scan a PRISM/BIDS project and return the available sessions and modalities.

    Returns a dict with:
        sessions: sorted list of session labels (e.g. ["ses-01", "ses-02"]),
                  empty list when no session level is used.
        modalities: sorted list of modality folder names (e.g. ["eeg", "survey", "func"]).
    """
    sessions: Set[str] = set()
    modalities: Set[str] = set()

    for sub_dir in sorted(project_path.iterdir()):
        if not (sub_dir.is_dir() and sub_dir.name.startswith("sub-")):
            continue
        for child in sub_dir.iterdir():
            if not child.is_dir():
                continue
            if child.name.startswith("ses-"):
                sessions.add(child.name)
                # modalities live one level deeper when sessions are present
                for modality_dir in child.iterdir():
                    if modality_dir.is_dir() and not modality_dir.name.startswith("."):
                        modalities.add(modality_dir.name)
            elif not child.name.startswith("."):
                # no session level — child IS the modality folder
                modalities.add(child.name)

    return {
        "sessions": sorted(sessions),
        "modalities": sorted(modalities),
    }
