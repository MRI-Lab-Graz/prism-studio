import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.cli.commands.modality as modality_cmds  # noqa: E402
from src.cli.parser import build_prism_tools_parsers  # noqa: E402

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "modality_proposal"
PROPOSAL = EXAMPLE_DIR / "bloodwork.yml"
SAMPLE = EXAMPLE_DIR / "bloodwork_sample.tsv"


def _args(**over) -> SimpleNamespace:
    values = dict(proposal=str(PROPOSAL), sample=str(SAMPLE), out=None, check=False, json=False)
    values.update(over)
    return SimpleNamespace(**values)


def test_parser_accepts_modality_propose() -> None:
    parser, parsers = build_prism_tools_parsers(APP_ROOT)
    args = parser.parse_args(["modality", "propose", "p.yml", "--sample", "s.tsv", "--check"])
    assert (args.command, args.action, args.proposal, args.check) == ("modality", "propose", "p.yml", True)
    assert "modality" in parsers


def test_propose_writes_all_artifacts(tmp_path: Path, capsys) -> None:
    out = tmp_path / "out"
    modality_cmds.cmd_modality_propose(_args(out=str(out)))
    assert (out / "bloodwork.schema.json").is_file()
    assert (out / "REGISTRATION.md").is_file()
    assert "REGISTRATION.md" in capsys.readouterr().out


def test_check_writes_nothing(tmp_path: Path, capsys) -> None:
    out = tmp_path / "out"
    modality_cmds.cmd_modality_propose(_args(out=str(out), check=True))
    assert not out.exists()
    assert "OK" in capsys.readouterr().out


def test_invalid_proposal_exits_1_and_lists_every_problem(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.yml"
    bad.write_text(
        PROPOSAL.read_text(encoding="utf-8")
        .replace("suffix: bloodchem", "suffix: blood")
        .replace("modality: bloodwork", "modality: Bio Sample"),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as exc:
        modality_cmds.cmd_modality_propose(_args(proposal=str(bad), out=str(tmp_path / "o")))
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Modality.Name" in out and "Modality.Suffix" in out
    assert not (tmp_path / "o").exists()


def test_missing_out_without_check_exits_2() -> None:
    with pytest.raises(SystemExit) as exc:
        modality_cmds.cmd_modality_propose(_args())
    assert exc.value.code == 2


def test_unreadable_proposal_exits_1(tmp_path: Path, capsys) -> None:
    f = tmp_path / "p.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        modality_cmds.cmd_modality_propose(_args(proposal=str(f), check=True))
    assert exc.value.code == 1
    assert "unsupported" in capsys.readouterr().out


def test_json_output(tmp_path: Path, capsys) -> None:
    modality_cmds.cmd_modality_propose(_args(out=str(tmp_path / "o"), json=True))
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["modality"] == "bloodwork"
    assert any(f.endswith("REGISTRATION.md") for f in payload["files"])


def _json_exit(capsys, code, **over) -> dict:
    with pytest.raises(SystemExit) as exc:
        modality_cmds.cmd_modality_propose(_args(json=True, **over))
    assert exc.value.code == code
    return json.loads(capsys.readouterr().out)


def test_json_missing_out_is_one_json_object_exit_2(capsys) -> None:
    payload = _json_exit(capsys, 2)
    assert payload["success"] is False
    assert any(p["where"] == "--out" for p in payload["problems"])


def test_missing_out_exits_2_even_if_proposal_invalid(tmp_path: Path, capsys) -> None:
    f = tmp_path / "p.txt"
    f.write_text("x", encoding="utf-8")
    _json_exit(capsys, 2, proposal=str(f))


def test_json_non_utf8_proposal_exit_1(tmp_path: Path, capsys) -> None:
    f = tmp_path / "bad.yml"
    f.write_bytes(b"\xff\xfe\x00bad")
    payload = _json_exit(capsys, 1, proposal=str(f), check=True)
    assert payload["success"] is False


def test_json_out_is_a_file_exit_1(tmp_path: Path, capsys) -> None:
    out = tmp_path / "afile"
    out.write_text("x", encoding="utf-8")
    payload = _json_exit(capsys, 1, out=str(out))
    assert payload["success"] is False
    assert any(p["where"] == "--out" for p in payload["problems"])


def test_json_check_success_is_exactly_one_json_object(capsys) -> None:
    modality_cmds.cmd_modality_propose(_args(json=True, check=True))
    out = capsys.readouterr().out
    assert json.loads(out)["success"] is True
    assert "OK" not in out
