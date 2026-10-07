"""CLI contract: --format json and --json agree on `valid`, exit code follows it (#162)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ENV = {**os.environ, "PRISM_SKIP_VENV_CHECK": "1"}
PRISM = Path(__file__).resolve().parents[1] / "app" / "prism.py"


def _run(ds, *flags):
    return subprocess.run(
        [sys.executable, str(PRISM), str(ds), *flags],
        capture_output=True, text=True, env=_ENV,
    )


@pytest.mark.parametrize("make_valid", [True, False])
def test_both_json_modes_agree_on_valid_and_exit_code(tmp_path, make_valid):
    ds = tmp_path / "ds"
    ds.mkdir()
    if make_valid:
        (ds / "dataset_description.json").write_text(
            '{"Name":"Test dataset","BIDSVersion":"1.9.0","DatasetType":"raw",'
            '"Authors":["X"],"Keywords":["a","b","c"]}'
        )
        (ds / "sub-01" / "beh").mkdir(parents=True)
        (ds / "sub-01" / "beh" / "sub-01_task-demo_beh.tsv").write_text("a\n1\n")
    a, b = _run(ds, "--format", "json"), _run(ds, "--json")
    ja, jb = json.loads(a.stdout), json.loads(b.stdout)
    assert isinstance(ja["valid"], bool) and ja["valid"] == jb["valid"]
    assert ja["valid"] is make_valid
    assert a.returncode == b.returncode == (0 if make_valid else 1)


@pytest.mark.parametrize("engine", ["broken", "missing"])
@pytest.mark.parametrize("flags", [["--json"], ["--format", "json"]])
def test_bids_machine_output_is_pure_json_and_fails_closed(
    tmp_path, monkeypatch, capsys, flags, engine
):
    if engine == "broken" and sys.platform == "win32":
        pytest.skip("needs a POSIX shell stub")
    app = str(PRISM.parent)
    for p in (os.path.join(app, "src"), app):
        if p not in sys.path:
            sys.path.insert(0, p)
    import bids_validator
    import prism

    ds = tmp_path / "ds"
    ds.mkdir()
    script = tmp_path / "bids-validator-deno"
    script.write_text("#!/bin/sh\necho engine exploded >&2\nexit 1\n")
    script.chmod(0o755)
    found = str(script) if engine == "broken" else None
    monkeypatch.setattr(bids_validator, "find_bids_engine", lambda: found)
    monkeypatch.setattr(sys, "argv", ["prism", str(ds), "--bids", *flags])
    with pytest.raises(SystemExit) as exc:
        prism.main()
    out = json.loads(capsys.readouterr().out)  # stdout must be JSON only
    assert out["valid"] is False
    assert any(i["code"] == "PRISM902" for i in out["issues"])
    assert exc.value.code == 1


@pytest.mark.parametrize("flags", [["--json"], ["--format", "json"]])
def test_broken_config_file_keeps_stdout_json_only(tmp_path, flags):
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / ".prismrc.json").write_text("{bad")
    proc = _run(ds, *flags)
    assert "valid" in json.loads(proc.stdout)
