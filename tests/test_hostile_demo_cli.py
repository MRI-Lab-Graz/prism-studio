from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from src.cli.commands.hostile_demo import cmd_dataset_build_hostile_demo


def _namespace(output: Path, **overrides) -> Namespace:
    base = dict(
        output=str(output),
        seed=1,
        domains="all",
        use_datalad=False,
        name="hostile_demo",
        guide=False,
        json=True,
    )
    base.update(overrides)
    return Namespace(**base)


def test_cli_builds_hostile_dataset_and_emits_json(tmp_path: Path, capsys) -> None:
    output = tmp_path / "hostile_demo"
    cmd_dataset_build_hostile_demo(_namespace(output))

    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["case_count"] > 0
    assert output.exists()


def test_cli_writes_demo_guide_when_requested(tmp_path: Path, capsys) -> None:
    output = tmp_path / "hostile_demo"
    cmd_dataset_build_hostile_demo(_namespace(output, guide=True))

    capsys.readouterr()
    guide_path = output / "DEMO_GUIDE.md"
    assert guide_path.exists()
    content = guide_path.read_text(encoding="utf-8")
    assert "socio_age_out_of_range" in content


def test_cli_rejects_unknown_domain(tmp_path: Path, capsys) -> None:
    output = tmp_path / "hostile_demo"
    try:
        cmd_dataset_build_hostile_demo(_namespace(output, domains="not_a_domain"))
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("expected SystemExit for unknown domain")
