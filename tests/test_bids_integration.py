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


def test_check_and_update_bidsignore_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dataset_root = Path(tmp)

        check_and_update_bidsignore(str(dataset_root), ["survey"])
        first = (dataset_root / ".bidsignore").read_text(encoding="utf-8")

        check_and_update_bidsignore(str(dataset_root), ["survey"])
        second = (dataset_root / ".bidsignore").read_text(encoding="utf-8")

        assert first == second
