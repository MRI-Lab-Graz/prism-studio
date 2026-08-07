"""Tests for `prism_tools.py survey export-lss` / `export-lss-customized` /
`export-questionnaire-docx`.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P2) found that
src.limesurvey_exporter.generate_lss (Survey Generator "Quick Export"),
generate_lss_from_customization (Survey Customizer "Export"), and
src.questionnaire_renderer.render_questionnaire_docx ("Export Word", shared
by Template Editor and Survey Customizer) all had zero CLI callers despite
being pure, Flask-independent functions.
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.cli.commands.survey import (  # noqa: E402
    cmd_survey_export_lss,
    cmd_survey_export_lss_customized,
    cmd_survey_export_questionnaire_docx,
)

GAD7_PATH = (
    Path(__file__).resolve().parent.parent
    / "official"
    / "library"
    / "survey"
    / "survey-gad7.json"
)


def _args(**overrides) -> SimpleNamespace:
    defaults = dict(
        files=[],
        output=None,
        language="en",
        languages=None,
        base_language=None,
        ls_version="3",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.skipif(not GAD7_PATH.exists(), reason="Global library not available")
class TestExportLss:
    def test_exports_lss_file_from_template(self, tmp_path, capsys):
        output = tmp_path / "export.lss"
        cmd_survey_export_lss(
            _args(files=[str(GAD7_PATH)], output=str(output))
        )

        assert output.exists()
        root = ET.fromstring(output.read_bytes())
        assert root.tag == "document"
        assert "written" in capsys.readouterr().out

    def test_missing_file_exits(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_export_lss(
                _args(
                    files=[str(tmp_path / "missing.json")],
                    output=str(tmp_path / "out.lss"),
                )
            )
        assert exc_info.value.code == 1
        assert "not found" in capsys.readouterr().out

    def test_languages_flag_parses_comma_separated_list(self, tmp_path, monkeypatch):
        captured = {}

        def _fake_generate_lss(files, output_path, **kwargs):
            captured.update(kwargs)

        import src.cli.commands.survey as survey_cli

        monkeypatch.setattr(survey_cli, "generate_lss", _fake_generate_lss)

        cmd_survey_export_lss(
            _args(
                files=[str(GAD7_PATH)] if GAD7_PATH.exists() else ["x.json"],
                output=str(tmp_path / "out.lss"),
                languages="en,de",
            )
        )
        assert captured["languages"] == ["en", "de"]


class TestExportLssCustomized:
    def _write_customization_json(self, tmp_path) -> Path:
        template_path = tmp_path / "survey-template.json"
        template_path.write_text(
            json.dumps(
                {
                    "Study": {"OriginalName": "Template Survey"},
                    "Questions": {
                        "q1": {
                            "Description": {"en": "How are you today?"},
                            "InputType": "radio",
                            "Levels": {"1": "Not at all", "2": "Very much"},
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        customization = {
            "groups": [
                {
                    "id": "group-1",
                    "name": "Template Survey",
                    "order": 0,
                    "sourceFile": str(template_path),
                    "questions": [
                        {
                            "id": "question-1",
                            "sourceFile": str(template_path),
                            "questionCode": "q1",
                            "description": "How are you today?",
                            "displayOrder": 0,
                            "mandatory": True,
                            "enabled": True,
                            "runNumber": 1,
                            "levels": {"1": "Not at all", "2": "Very much"},
                            "originalData": {
                                "Description": {"en": "How are you today?"},
                                "InputType": "radio",
                                "Levels": {"1": "Not at all", "2": "Very much"},
                            },
                        }
                    ],
                }
            ],
            "survey_title": "Customized Survey",
        }
        customization_path = tmp_path / "customization.json"
        customization_path.write_text(json.dumps(customization), encoding="utf-8")
        return customization_path

    def test_exports_lss_from_customization_json(self, tmp_path, capsys):
        customization_path = self._write_customization_json(tmp_path)
        output = tmp_path / "export.lss"

        cmd_survey_export_lss_customized(
            _args(
                customization_json=str(customization_path),
                output=str(output),
                ls_version="6",
                no_matrix=True,
                no_matrix_global=True,
                survey_title=None,
            )
        )

        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "Customized Survey" in content
        assert "How are you today?" in content

    def test_missing_customization_file_exits(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_export_lss_customized(
                _args(
                    customization_json=str(tmp_path / "missing.json"),
                    output=str(tmp_path / "out.lss"),
                    no_matrix=True,
                    no_matrix_global=True,
                )
            )
        assert exc_info.value.code == 1

    def test_invalid_json_exits(self, tmp_path, capsys):
        bad_path = tmp_path / "bad.json"
        bad_path.write_text("not json", encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_export_lss_customized(
                _args(
                    customization_json=str(bad_path),
                    output=str(tmp_path / "out.lss"),
                    no_matrix=True,
                    no_matrix_global=True,
                )
            )
        assert exc_info.value.code == 1

    def test_bare_array_is_accepted_as_groups(self, tmp_path, capsys):
        template_path = tmp_path / "survey-template.json"
        template_path.write_text(json.dumps({"Study": {}}), encoding="utf-8")
        groups = [
            {
                "id": "group-1",
                "name": "G",
                "order": 0,
                "sourceFile": str(template_path),
                "questions": [],
            }
        ]
        customization_path = tmp_path / "customization.json"
        customization_path.write_text(json.dumps(groups), encoding="utf-8")

        cmd_survey_export_lss_customized(
            _args(
                customization_json=str(customization_path),
                output=str(tmp_path / "out.lss"),
                no_matrix=True,
                no_matrix_global=True,
            )
        )
        assert (tmp_path / "out.lss").exists()


class TestExportQuestionnaireDocx:
    LIKERT_TEMPLATE = {
        "Study": {
            "OriginalName": {"en": "Test Questionnaire", "de": "Test-Fragebogen"},
            "ShortName": "TQ",
        },
        "Technical": {"StimulusType": "Questionnaire", "Language": ""},
        "TQ01": {
            "Description": {"en": "I feel happy"},
            "Levels": {"0": {"en": "Never"}, "1": {"en": "Always"}},
            "DataType": "integer",
        },
    }

    def test_renders_docx_file(self, tmp_path, capsys):
        template_path = tmp_path / "template.json"
        template_path.write_text(json.dumps(self.LIKERT_TEMPLATE), encoding="utf-8")
        output = tmp_path / "out.docx"

        cmd_survey_export_questionnaire_docx(
            SimpleNamespace(
                template=str(template_path),
                output=str(output),
                language="en",
                variant_id=None,
                options_json=None,
            )
        )

        assert output.exists()
        from docx import Document

        doc = Document(str(output))
        assert len(doc.paragraphs) > 0
        assert "written" in capsys.readouterr().out

    def test_missing_template_exits(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_export_questionnaire_docx(
                SimpleNamespace(
                    template=str(tmp_path / "missing.json"),
                    output=str(tmp_path / "out.docx"),
                    language="en",
                    variant_id=None,
                    options_json=None,
                )
            )
        assert exc_info.value.code == 1

    def test_options_json_inline_string_applied(self, tmp_path):
        template_path = tmp_path / "template.json"
        template_path.write_text(json.dumps(self.LIKERT_TEMPLATE), encoding="utf-8")
        output = tmp_path / "out.docx"

        cmd_survey_export_questionnaire_docx(
            SimpleNamespace(
                template=str(template_path),
                output=str(output),
                language="en",
                variant_id=None,
                options_json='{"show_item_codes": true}',
            )
        )
        assert output.exists()

    def test_invalid_options_json_exits(self, tmp_path):
        template_path = tmp_path / "template.json"
        template_path.write_text(json.dumps(self.LIKERT_TEMPLATE), encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_export_questionnaire_docx(
                SimpleNamespace(
                    template=str(template_path),
                    output=str(tmp_path / "out.docx"),
                    language="en",
                    variant_id=None,
                    options_json="not-json",
                )
            )
        assert exc_info.value.code == 1
