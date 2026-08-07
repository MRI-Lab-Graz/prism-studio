"""Tests for `prism_tools.py participants neurobagel-schema`.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P2, Neurobagel) found that
the Studio GUI's Neurobagel widget's real value beyond a raw
--neurobagel-schema passthrough flag — fetching/augmenting the external
Neurobagel controlled vocabulary and sampling local participants.tsv
columns for categorical mapping suggestions — had no CLI equivalent at
all. src.web.neurobagel.sample_local_participant_columns was extracted
from app/src/web/blueprints/neurobagel.py's inline pandas logic in the
same change so both the GUI route and this CLI command share it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.cli.commands.participants as participants_cli  # noqa: E402
from src.cli.commands.participants import (  # noqa: E402
    cmd_participants_neurobagel_schema,
)


def _args(**overrides) -> SimpleNamespace:
    defaults = dict(project=None, output=None, json=False)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


FAKE_VOCAB = {
    "properties": {
        "participant_id": {"Description": "A participant ID"},
        "sex": {"Description": "Biological sex"},
    }
}


@pytest.fixture(autouse=True)
def _mock_neurobagel_network(monkeypatch):
    import src.web.neurobagel as neurobagel_module

    monkeypatch.setattr(
        neurobagel_module, "fetch_neurobagel_participants", lambda: dict(FAKE_VOCAB)
    )


class TestNeurobagelSchema:
    def test_missing_project_directory_exits(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cmd_participants_neurobagel_schema(
                _args(project=str(tmp_path / "missing"))
            )
        assert exc_info.value.code == 1
        assert "not a directory" in capsys.readouterr().out

    def test_prints_summary_without_output_or_json(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()
        pd.DataFrame({"participant_id": ["001"], "sex": ["F"]}).to_csv(
            project / "participants.tsv", sep="\t", index=False
        )

        cmd_participants_neurobagel_schema(_args(project=str(project)))

        out = capsys.readouterr().out
        assert "sex" in out
        assert "participant_id" in out or "sex" in out

    def test_json_mode_emits_full_payload(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()
        pd.DataFrame({"participant_id": ["001"], "sex": ["F"]}).to_csv(
            project / "participants.tsv", sep="\t", index=False
        )

        cmd_participants_neurobagel_schema(
            _args(project=str(project), json=True)
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload["local_columns"]["sex"] == ["F"]
        assert "participant_id" in payload["vocabulary"]["properties"]

    def test_output_file_writes_combined_json(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()
        pd.DataFrame({"participant_id": ["001"], "sex": ["F"]}).to_csv(
            project / "participants.tsv", sep="\t", index=False
        )
        output_path = tmp_path / "schema.json"

        cmd_participants_neurobagel_schema(
            _args(project=str(project), output=str(output_path))
        )

        assert output_path.exists()
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["local_columns"]["sex"] == ["F"]
        assert "Wrote Neurobagel schema data" in capsys.readouterr().out

    def test_no_participants_tsv_yields_empty_local_columns(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()

        cmd_participants_neurobagel_schema(
            _args(project=str(project), json=True)
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload["local_columns"] == {}
