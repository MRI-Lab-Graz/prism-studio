import os
import sys
import tempfile
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")

if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.bids_integration import check_and_update_bidsignore


def test_check_and_update_bidsignore_adds_prism_and_legacy_rules() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dataset_root = Path(tmp)

        check_and_update_bidsignore(str(dataset_root), ["survey"])

        bidsignore_path = dataset_root / ".bidsignore"
        assert bidsignore_path.exists()

        content = bidsignore_path.read_text(encoding="utf-8")
        assert "derivatives/" in content
        assert "code/" in content
        assert "code/library/" in content
        assert "code/recipes/" in content
        assert "recipes/" in content
        assert "library/" in content
        assert "CITATION.cff" not in content


def test_check_and_update_bidsignore_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dataset_root = Path(tmp)

        check_and_update_bidsignore(str(dataset_root), ["survey"])
        first = (dataset_root / ".bidsignore").read_text(encoding="utf-8")

        check_and_update_bidsignore(str(dataset_root), ["survey"])
        second = (dataset_root / ".bidsignore").read_text(encoding="utf-8")

        assert first == second


def test_check_and_update_bidsignore_keeps_eyetracking_visible_to_bids() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dataset_root = Path(tmp)

        check_and_update_bidsignore(str(dataset_root), ["survey", "eyetracking"])

        content = (dataset_root / ".bidsignore").read_text(encoding="utf-8")
        assert "eyetracking/" not in content
        assert "**/eyetracking/" not in content
        assert "*_eyetrack.*" not in content
        assert "task-*_eyetrack.json" not in content


def test_check_and_update_bidsignore_adds_all_prism_modality_folders() -> None:
    """prism_folders is now derived from src/entity_rules.py's
    prism_modalities (survey, biometrics, environment, physio,
    physiological, events) instead of a hardcoded 8-item set - confirms the
    6 real entries still produce ignore-rules regardless of what's passed
    in as supported_modalities."""
    with tempfile.TemporaryDirectory() as tmp:
        dataset_root = Path(tmp)

        check_and_update_bidsignore(str(dataset_root), [])

        content = (dataset_root / ".bidsignore").read_text(encoding="utf-8")
        for folder in ("survey", "biometrics", "environment", "physio", "physiological", "events"):
            assert f"{folder}/" in content, folder


def test_check_and_update_bidsignore_never_mentions_dead_eeg_or_metadata() -> None:
    """The old prism_folders set had "eeg" (dead - already in
    STANDARD_BIDS_FOLDERS, so it never survived the filter) and
    "metadata" (unreferenced anywhere else in the codebase) entries.
    Neither should ever produce a bidsignore line, before or after
    removing them from the now entity_rules-derived set."""
    with tempfile.TemporaryDirectory() as tmp:
        dataset_root = Path(tmp)

        check_and_update_bidsignore(str(dataset_root), [])

        content = (dataset_root / ".bidsignore").read_text(encoding="utf-8")
        assert "eeg/" not in content
        assert "metadata/" not in content
