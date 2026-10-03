"""Validating a dataset someone sent you must not run Python shipped inside it.

Plugins (<dataset>/validators/*.py, or paths listed in the dataset's
.prismrc.json) are arbitrary code, so they load only with an explicit --plugins.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PRISM = Path(__file__).resolve().parents[1] / "app" / "prism.py"


def _dataset(tmp_path: Path) -> Path:
    ds = tmp_path / "ds"
    (ds / "validators").mkdir(parents=True)
    (ds / "dataset_description.json").write_text(
        json.dumps({"Name": "x", "BIDSVersion": "1.9.0"})
    )
    (ds / "validators" / "evil.py").write_text(
        f"from pathlib import Path\nPath({str(tmp_path / 'pwned')!r}).write_text('x')\n"
    )
    return ds


def _run(ds: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PRISM_SKIP_VENV_CHECK": "1"}
    return subprocess.run(
        [sys.executable, str(PRISM), str(ds), "--json", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def test_plugins_do_not_run_by_default(tmp_path):
    ds = _dataset(tmp_path)
    _run(ds)
    assert not (tmp_path / "pwned").exists()


def test_list_plugins_alone_does_not_run_them(tmp_path):
    ds = _dataset(tmp_path)
    _run(ds, "--list-plugins")
    assert not (tmp_path / "pwned").exists()


def test_plugins_run_with_explicit_flag(tmp_path):
    ds = _dataset(tmp_path)
    _run(ds, "--plugins")
    assert (tmp_path / "pwned").exists()
