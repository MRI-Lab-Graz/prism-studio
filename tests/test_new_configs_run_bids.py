"""Configs that Studio and the fixer write must leave the BIDS check on (it is the default)."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "app" / "src"))

from config import load_config  # noqa: E402


def test_studio_created_project_config_keeps_bids_on(tmp_path):
    from src.project_manager import ProjectManager

    content = ProjectManager()._create_prismrc()
    (tmp_path / ".prismrc.json").write_text(json.dumps(content), encoding="utf-8")
    assert load_config(str(tmp_path)).run_bids is True


def test_fixer_created_config_keeps_bids_on(tmp_path):
    from src.fixer import DatasetFixer

    fixer = DatasetFixer(str(tmp_path))
    fixer._check_config_file()
    fix = next(f for f in fixer.fixes if f.file_path.endswith(".prismrc.json"))
    assert json.loads(fix.details["content"])["runBids"] is True


def test_the_demo_config_keeps_bids_on():
    demo = ROOT / "examples" / "wellbeing_multi_demo"
    assert load_config(str(demo)).run_bids is True
