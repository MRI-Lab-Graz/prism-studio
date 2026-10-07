"""bids-validator-deno for real: no mocks (spec 2026-10-07). Skipped locally when the engine
is not installed, but CI must have it (the dependency is an ordinary one)."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

import bids_validator

ROOT = Path(__file__).resolve().parents[1]
ENGINE = bids_validator.find_bids_engine()
needs_engine = pytest.mark.skipif(ENGINE is None, reason="bids-validator-deno is not installed")


def test_engine_is_installed_in_ci():
    if os.environ.get("CI"):
        assert ENGINE is not None, "CI must install bids-validator-deno (requirements-runtime.txt)"


@needs_engine
def test_a_minimal_dataset_has_no_bids_error(tmp_path):
    (tmp_path / "dataset_description.json").write_text(
        json.dumps({"Name": "T", "BIDSVersion": "1.9.0", "DatasetType": "raw", "Authors": ["A", "B"]})
    )
    issues = bids_validator.run_bids_validator(str(tmp_path))
    assert not [i for i in issues if i[0] == "ERROR"], issues


@needs_engine
def test_a_real_bids_error_is_reported_as_an_error(tmp_path):
    # no BIDSVersion: the engine reports JSON_KEY_REQUIRED as an error
    (tmp_path / "dataset_description.json").write_text(json.dumps({"Name": "T"}))
    issues = bids_validator.run_bids_validator(str(tmp_path))
    assert [i for i in issues if i[0] == "ERROR" and "JSON_KEY_REQUIRED" in i[1]], issues
    assert not any(i[1].startswith("PRISM902") for i in issues)


@needs_engine
def test_prism_folders_of_the_demo_dataset_draw_no_false_not_included_errors():
    info = {}
    issues = bids_validator.run_bids_validator(
        str(ROOT / "examples" / "wellbeing_multi_demo"), backend_info=info
    )
    assert info["engine"] == "bids-validator-deno" and info["version"] != "unknown"
    not_included = [i[1] for i in issues if i[1].startswith("[BIDS] NOT_INCLUDED")]
    assert all("/survey/" not in m for m in not_included), not_included
    # filtering is selective: a genuinely foreign file is still reported
    assert any("/DEMO_GUIDE.md" in m for m in not_included), not_included
    assert not any(i[1].startswith("PRISM902") for i in issues)
