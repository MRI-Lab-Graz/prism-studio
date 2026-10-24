"""Editable defaults 1, 2, 3 for unmapped session labels; a proposal, never written unasked."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.cli.commands.session_map import cmd_session_map_suggest  # noqa: E402
from src.session_map import load_session_map, suggest_session_map  # noqa: E402


def test_ascending_from_one_in_order_of_appearance():
    assert suggest_session_map(["pre", "post", "follow-up", "pre"], {}) == {
        "pre": "1", "post": "2", "follow-up": "3"
    }


def test_skips_numbers_already_used_and_mapped_labels():
    assert suggest_session_map(["pre", "post"], {"pre": "1"}) == {"post": "2"}
    assert suggest_session_map(["x"], {"a": "1", "b": "3"}) == {"x": "2"}


def test_blank_label_gets_no_suggestion_and_labels_are_exact():
    assert suggest_session_map(["", "1", "01"], {}) == {"1": "1", "01": "2"}


@pytest.fixture
def proj(tmp_path):
    (tmp_path / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "multiple"}}))
    return tmp_path


def _suggest(proj):
    return SimpleNamespace(project=str(proj), label=["pre", "post"], apply=False, json=True)


def test_cli_suggest_prints_and_does_not_write(proj, capsys):
    cmd_session_map_suggest(_suggest(proj))
    assert json.loads(capsys.readouterr().out) == {"suggested": {"pre": "1", "post": "2"}}
    assert load_session_map(proj) == {}


def test_cli_suggest_apply_writes_the_map(proj):
    cmd_session_map_suggest(
        SimpleNamespace(project=str(proj), label=["pre", "post"], apply=True, json=False)
    )
    assert load_session_map(proj) == {"pre": "1", "post": "2"}
