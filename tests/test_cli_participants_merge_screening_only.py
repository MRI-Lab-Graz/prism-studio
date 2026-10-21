"""`participants merge --screening-only` puts the listed ids into the screening-only group."""

import sys
from pathlib import Path
from types import SimpleNamespace

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.cli.commands.participants import cmd_participants_merge  # noqa: E402
from src.cli.parser import build_prism_tools_parsers  # noqa: E402


def _merge(tmp_path, screening_only):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "participants.tsv").write_text("participant_id\tage\nsub-1\t30\n", encoding="utf-8")
    (project / "participants.json").write_text('{"participant_id": {}, "age": {}}', encoding="utf-8")
    source = tmp_path / "in.csv"
    source.write_text("participant_id,age\n1,30\n2,40\n", encoding="utf-8")
    cmd_participants_merge(SimpleNamespace(
        input=str(source), project=str(project), apply=True, json=False,
        screening_only=screening_only,
    ))
    return (project / "participants.tsv").read_text(encoding="utf-8")


def test_listed_ids_are_marked(tmp_path):
    assert "sub-2\t40\tscreening-only" in _merge(tmp_path, "sub-2")


def test_without_the_flag_no_group_column_appears(tmp_path):
    assert "group" not in _merge(tmp_path, None)


def test_the_flag_is_on_the_merge_parser():
    args = build_prism_tools_parsers(APP_ROOT)[0].parse_args(
        ["participants", "merge", "--input", "x.csv", "--project", "p", "--screening-only", "sub-2,sub-3"]
    )
    assert args.screening_only == "sub-2,sub-3"
