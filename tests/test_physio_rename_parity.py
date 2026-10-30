"""Studio's Physio Renamer dry-run and the command's preview give the same results (THE RULE, CLAUDE.md)."""

import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from flask import Flask  # noqa: E402

from src.physio_renamer import plan_rename  # noqa: E402

CASES = [
    ("a plain organize", ["sub-001_ses-1_physio.tsv.gz"], r"^(.*)$", r"\1", "physio", True),
    ("no organize", ["sub-001_ses-1_physio.tsv.gz"], r"physio", "beh", "physio", False),
    ("events have no folder", ["sub-001_ses-1_events.tsv"], r"^(.*)$", r"\1", "events", True),
    ("task-bound physio does not go to physio/", ["sub-001_ses-1_task-rest_physio.tsv.gz"], r"^(.*)$", r"\1", "physio", True),
    ("an empty new name", ["sub-001_ses-1_physio.tsv.gz"], r"^.*$", "", "physio", False),
    ("a path separator in the new name", ["sub-001_ses-1_physio.tsv.gz"], r"physio", "a/b", "physio", False),
]


def _studio_dry_run(names, pattern, replacement, modality, organize):
    handlers = importlib.import_module("src.web.blueprints.conversion_physio_handlers")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    app.add_url_rule("/api/physio-rename", view_func=handlers.api_physio_rename, methods=["POST"])
    response = app.test_client().post(
        "/api/physio-rename",
        data={
            "pattern": pattern, "replacement": replacement, "dry_run": "true", "modality": modality,
            "organize": "true" if organize else "false", "filenames[]": names,
        },
    )
    assert response.status_code == 200, response.get_data(as_text=True)[:200]
    return response.get_json()["results"], handlers.parse_bids_filename


@pytest.mark.parametrize("label, names, pattern, replacement, modality, organize", CASES, ids=[c[0] for c in CASES])
def test_the_dry_run_and_the_command_agree(label, names, pattern, replacement, modality, organize):
    studio, parse_bids_filename = _studio_dry_run(names, pattern, replacement, modality, organize)
    command, _warnings = plan_rename(
        [(n, n) for n in names], pattern=pattern, replacement=replacement, modality=modality, organize=organize,
        parse_bids_filename=parse_bids_filename,
    )
    assert studio == command
