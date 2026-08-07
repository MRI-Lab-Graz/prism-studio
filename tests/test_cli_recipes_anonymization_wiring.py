"""Tests that the CLI's `recipes surveys/biometrics --anonymized` flag
actually invokes real anonymization, not just folder-name cosmetics.

See docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P1-3).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.cli.commands.recipes as recipes_cli  # noqa: E402


def _fake_result(out_root, out_format="flat"):
    return SimpleNamespace(out_root=out_root, out_format=out_format, written_files=1)


class TestRunAnonymizationIfRequested:
    def test_noop_when_anonymized_flag_not_set(self, tmp_path, monkeypatch):
        called = {}

        def _fake_anonymize(**kwargs):
            called.update(kwargs)
            return 0, tmp_path / "mapping.json"

        monkeypatch.setattr(recipes_cli, "anonymize_recipe_output", _fake_anonymize)

        args = SimpleNamespace(anonymized=False)
        recipes_cli._run_anonymization_if_requested(
            args, prism_root=tmp_path, result=_fake_result(tmp_path)
        )

        assert called == {}

    def test_calls_shared_anonymizer_with_cli_flags(self, tmp_path, monkeypatch, capsys):
        called = {}

        def _fake_anonymize(**kwargs):
            called.update(kwargs)
            return 3, tmp_path / "participants_mapping.json"

        monkeypatch.setattr(recipes_cli, "anonymize_recipe_output", _fake_anonymize)

        result = _fake_result(tmp_path / "out", out_format="csv")
        args = SimpleNamespace(
            anonymized=True,
            mask_questions=True,
            id_length=12,
            random_ids=True,
        )
        recipes_cli._run_anonymization_if_requested(
            args, prism_root=tmp_path, result=result
        )

        assert called == {
            "dataset_path": tmp_path,
            "out_root": tmp_path / "out",
            "out_format": "csv",
            "id_length": 12,
            "random_ids": True,
            "mask_questions": True,
        }
        out = capsys.readouterr().out
        assert "Anonymized 3 file(s)" in out
        assert "Masked question/item text columns" in out

    def test_defaults_when_flags_absent_on_args(self, tmp_path, monkeypatch):
        # argparse always sets these because the parser defines defaults,
        # but the helper should not crash if called with a minimal args
        # object (e.g. from a test or a future alternate entrypoint).
        called = {}

        def _fake_anonymize(**kwargs):
            called.update(kwargs)
            return 0, tmp_path / "mapping.json"

        monkeypatch.setattr(recipes_cli, "anonymize_recipe_output", _fake_anonymize)

        args = SimpleNamespace(anonymized=True)
        recipes_cli._run_anonymization_if_requested(
            args, prism_root=tmp_path, result=_fake_result(tmp_path)
        )

        assert called["id_length"] == 8
        assert called["random_ids"] is False
        assert called["mask_questions"] is False

    def test_exits_nonzero_on_anonymization_error(self, tmp_path, monkeypatch):
        def _fake_anonymize(**kwargs):
            raise FileNotFoundError("participants.tsv not found")

        monkeypatch.setattr(recipes_cli, "anonymize_recipe_output", _fake_anonymize)

        args = SimpleNamespace(anonymized=True)
        with pytest.raises(SystemExit) as exc_info:
            recipes_cli._run_anonymization_if_requested(
                args, prism_root=tmp_path, result=_fake_result(tmp_path)
            )
        assert exc_info.value.code == 1


class TestParserExposesAnonymizationFlags:
    def test_surveys_and_biometrics_share_the_same_anonymization_flags(self):
        from src.cli.parser import build_prism_tools_parsers

        parser, _ = build_prism_tools_parsers(APP_ROOT.resolve())

        for kind in ("surveys", "biometrics"):
            args = parser.parse_args(
                [
                    "recipes",
                    kind,
                    "--prism",
                    "/tmp/does-not-need-to-exist",
                    "--anonymized",
                    "--mask-questions",
                    "--id-length",
                    "10",
                    "--random-ids",
                ]
            )
            assert args.anonymized is True
            assert args.mask_questions is True
            assert args.id_length == 10
            assert args.random_ids is True

    def test_anonymization_flags_default_off(self):
        from src.cli.parser import build_prism_tools_parsers

        parser, _ = build_prism_tools_parsers(APP_ROOT.resolve())
        args = parser.parse_args(
            ["recipes", "surveys", "--prism", "/tmp/does-not-need-to-exist"]
        )
        assert args.anonymized is False
        assert args.mask_questions is False
        assert args.id_length == 8
        assert args.random_ids is False
