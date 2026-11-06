"""Enabling DataLad registers nested datasets in batches. The backend says whether to go on; CLI and Studio both obey."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.project_manager import enable_continuation  # noqa: E402


def test_remaining_datasets_mean_go_on():
    result = enable_continuation({"success": True, "datalad": {"subdatasets_remaining_count": 2, "subdatasets_created": ["a"]}})
    assert result["enable_continue"] is True and result["success"] is True


def test_nothing_remaining_means_done():
    assert "enable_continue" not in enable_continuation({"success": True, "datalad": {"subdatasets_remaining_count": 0}})


def test_a_batch_that_made_no_progress_and_failed_is_stuck():
    result = enable_continuation(
        {"success": True, "datalad": {"subdatasets_remaining_count": 1, "subdatasets_created": [], "subdataset_failures": ["sub-01: locked"]}}
    )
    assert result["enable_stuck"] is True and result["success"] is True and "enable_continue" not in result


def test_a_failed_call_is_never_continued():
    assert "enable_continue" not in enable_continuation({"success": False, "datalad": {"subdatasets_remaining_count": 3}})


def test_the_cli_repeats_enable_until_the_backend_says_done(capsys):
    from src.cli.commands.datalad import cmd_datalad_enable

    answers = iter([
        {"success": True, "enable_continue": True, "message": "batch 1"},
        {"success": True, "enable_continue": True, "message": "batch 2"},
        {"success": True, "message": "done"},
    ])
    manager = SimpleNamespace(enable_datalad_for_project=lambda *a, **k: next(answers))
    with patch("src.cli.commands.datalad._manager", return_value=manager):
        cmd_datalad_enable(SimpleNamespace(project="p", message=None, yes=True, json=False))
    assert next(answers, None) is None  # all three batches were used
    assert capsys.readouterr().out.strip().endswith("done")
