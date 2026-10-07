"""CLI contract: --format json and --json agree on `valid`, exit code follows it (#162)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PRISM = Path(__file__).resolve().parents[1] / "app" / "prism.py"


def _run(ds, *flags):
    return subprocess.run(
        [sys.executable, str(PRISM), str(ds), *flags], capture_output=True, text=True
    )


@pytest.mark.parametrize("make_valid", [True, False])
def test_both_json_modes_agree_on_valid_and_exit_code(tmp_path, make_valid):
    ds = tmp_path / "ds"
    ds.mkdir()
    if make_valid:
        (ds / "dataset_description.json").write_text(
            '{"Name":"T","BIDSVersion":"1.9.0","DatasetType":"raw"}'
        )
    a, b = _run(ds, "--format", "json"), _run(ds, "--json")
    ja, jb = json.loads(a.stdout), json.loads(b.stdout)
    assert isinstance(ja["valid"], bool) and ja["valid"] == jb["valid"]
    assert a.returncode == b.returncode == (0 if ja["valid"] else 1)


@pytest.mark.skipif(sys.platform == "win32", reason="needs a POSIX shell stub")
@pytest.mark.parametrize("flags", [["--json"], ["--format", "json"]])
def test_bids_machine_output_is_pure_json_and_fails_closed(tmp_path, flags):
    ds = tmp_path / "ds"
    ds.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    deno = bindir / "deno"
    deno.write_text("#!/bin/sh\nexit 1\n")
    deno.chmod(0o755)
    env = {**os.environ, "PATH": str(bindir)}
    proc = subprocess.run(
        [sys.executable, str(PRISM), str(ds), "--bids", *flags],
        capture_output=True, text=True, env=env,
    )
    out = json.loads(proc.stdout)  # stdout must be JSON only
    assert out["valid"] is False
    assert any(i["code"] == "PRISM902" for i in out["issues"])
    assert proc.returncode == 1
