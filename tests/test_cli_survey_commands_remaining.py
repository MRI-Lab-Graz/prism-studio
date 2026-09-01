"""Coverage for the survey CLI handlers not already exercised by
tests/test_cli_survey_export_commands.py: helper parsers, Excel/LimeSurvey
import, validate, i18n migrate/build/autotranslate, and the wide-table
`survey convert` command.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.cli.commands.survey as survey_cli  # noqa: E402
from src.cli.commands.survey import (  # noqa: E402
    _normalize_template_version_run,
    _parse_task_value_offset_args,
    _parse_template_version_args,
    cmd_survey_convert,
    cmd_survey_i18n_autotranslate,
    cmd_survey_i18n_build,
    cmd_survey_i18n_migrate,
    cmd_survey_import_excel,
    cmd_survey_import_limesurvey,
    cmd_survey_import_limesurvey_batch,
    cmd_survey_validate,
    parse_session_map,
)


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


class TestNormalizeTemplateVersionRun:
    def test_empty_returns_none(self):
        assert _normalize_template_version_run(None) is None
        assert _normalize_template_version_run("") is None

    def test_strips_run_prefix_and_non_alnum(self):
        assert _normalize_template_version_run("run-2") == "run-2"
        assert _normalize_template_version_run("2") == "run-2"
        assert _normalize_template_version_run("RUN-02b") == "run-02b"

    def test_raises_when_no_alnum_remains(self):
        with pytest.raises(ValueError):
            _normalize_template_version_run("run---")


class TestParseTemplateVersionArgs:
    def test_empty_input(self):
        assert _parse_template_version_args(None) == []
        assert _parse_template_version_args([]) == []

    def test_simple_task_version(self):
        result = _parse_template_version_args(["pss=v2"])
        assert result == [
            {"task": "pss", "session": None, "run": None, "version": "v2"}
        ]

    def test_task_with_session_and_run(self):
        result = _parse_template_version_args(["pss;session=ses-1;run=2=v3"])
        assert result == [
            {
                "task": "pss",
                "session": "ses-1",
                "run": "run-2",
                "version": "v3",
            }
        ]

    def test_missing_equals_raises(self):
        with pytest.raises(ValueError):
            _parse_template_version_args(["pss-v2"])

    def test_empty_selector_or_version_raises(self):
        with pytest.raises(ValueError):
            _parse_template_version_args(["=v2"])

    def test_unknown_qualifier_raises(self):
        with pytest.raises(ValueError):
            _parse_template_version_args(["pss;bogus=1=v2"])

    def test_blank_entries_skipped(self):
        assert _parse_template_version_args(["", "   "]) == []


class TestParseTaskValueOffsetArgs:
    def test_empty_input(self):
        assert _parse_task_value_offset_args(None) == {}

    def test_parses_offset(self):
        assert _parse_task_value_offset_args(["pss=-1.5"]) == {"pss": -1.5}

    def test_missing_equals_raises(self):
        with pytest.raises(ValueError):
            _parse_task_value_offset_args(["pss1"])

    def test_missing_task_or_offset_raises(self):
        with pytest.raises(ValueError):
            _parse_task_value_offset_args(["=1"])
        with pytest.raises(ValueError):
            _parse_task_value_offset_args(["pss="])

    def test_non_numeric_offset_raises(self):
        with pytest.raises(ValueError):
            _parse_task_value_offset_args(["pss=abc"])

    def test_blank_entries_skipped(self):
        assert _parse_task_value_offset_args(["", "  "]) == {}


class TestParseSessionMap:
    def test_colon_separator(self):
        assert parse_session_map("t1:ses-1,t2:ses-2") == {
            "t1": "ses-1",
            "t2": "ses-2",
        }

    def test_equals_separator(self):
        assert parse_session_map("t1=ses-1") == {"t1": "ses-1"}

    def test_underscore_separator(self):
        assert parse_session_map("t1_ses-1") == {"t1": "ses-1"}

    def test_no_separator_token_skipped(self):
        assert parse_session_map("bogus,t1:ses-1") == {"t1": "ses-1"}

    def test_blank_tokens_skipped(self):
        assert parse_session_map(" , t1:ses-1 , ") == {"t1": "ses-1"}

    def test_empty_string_returns_empty(self):
        assert parse_session_map("") == {}


# ---------------------------------------------------------------------------
# cmd_survey_import_excel
# ---------------------------------------------------------------------------


class TestCmdSurveyImportExcel:
    def test_success_with_library_root(self, tmp_path, monkeypatch):
        calls = {}
        monkeypatch.setattr(
            survey_cli,
            "process_excel",
            lambda excel, out: calls.setdefault("process_excel", (excel, out)),
        )
        monkeypatch.setattr(
            survey_cli,
            "check_uniqueness",
            lambda out: calls.setdefault("check_uniqueness", out),
        )
        excel_path = tmp_path / "in.xlsx"
        excel_path.write_text("x")

        cmd_survey_import_excel(
            SimpleNamespace(
                excel=str(excel_path),
                library_root=str(tmp_path / "library"),
                output=None,
            )
        )

        assert calls["process_excel"][1].endswith("survey")
        assert calls["check_uniqueness"] == calls["process_excel"][1]

    def test_success_with_output_dir_not_named_survey(self, tmp_path, monkeypatch):
        calls = {}
        monkeypatch.setattr(
            survey_cli,
            "process_excel",
            lambda excel, out: calls.setdefault("process_excel", (excel, out)),
        )
        monkeypatch.setattr(survey_cli, "check_uniqueness", lambda out: None)
        excel_path = tmp_path / "in.xlsx"
        excel_path.write_text("x")

        cmd_survey_import_excel(
            SimpleNamespace(
                excel=str(excel_path),
                library_root=None,
                output=str(tmp_path / "outdir"),
            )
        )
        assert calls["process_excel"][1].endswith("survey")

    def test_error_exits(self, tmp_path, monkeypatch, capsys):
        def _boom(excel, out):
            raise RuntimeError("bad excel")

        monkeypatch.setattr(survey_cli, "process_excel", _boom)
        excel_path = tmp_path / "in.xlsx"
        excel_path.write_text("x")

        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_import_excel(
                SimpleNamespace(
                    excel=str(excel_path),
                    library_root=None,
                    output=str(tmp_path / "survey"),
                )
            )
        assert exc_info.value.code == 1
        assert "Error importing Excel" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# cmd_survey_validate
# ---------------------------------------------------------------------------


class TestCmdSurveyValidate:
    def test_valid_library_exits_zero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(survey_cli, "check_uniqueness", lambda path: True)
        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_validate(SimpleNamespace(library=str(tmp_path)))
        assert exc_info.value.code == 0

    def test_invalid_library_exits_one(self, tmp_path, monkeypatch):
        monkeypatch.setattr(survey_cli, "check_uniqueness", lambda path: False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_validate(SimpleNamespace(library=str(tmp_path)))
        assert exc_info.value.code == 1

    def test_cmd_survey_validate_docstring_states_uniqueness_only_scope(self):
        doc = cmd_survey_validate.__doc__ or ""
        assert "uniqueness" in doc.lower()
        assert "does not check" in doc.lower()

    def test_survey_validate_help_states_uniqueness_only_scope(self):
        parser_source = Path("app/src/cli/parser.py").read_text(encoding="utf-8")
        validate_parser_block = parser_source.split('"validate",', 1)[1][:400]
        assert "uniqueness" in validate_parser_block.lower()


# ---------------------------------------------------------------------------
# cmd_survey_import_limesurvey / batch
# ---------------------------------------------------------------------------


class TestCmdSurveyImportLimesurvey:
    def test_success(self, tmp_path, monkeypatch):
        calls = {}
        monkeypatch.setattr(
            survey_cli,
            "convert_lsa_to_prism",
            lambda inp, out, task_name: calls.setdefault(
                "convert", (inp, out, task_name)
            ),
        )
        monkeypatch.setattr(survey_cli, "check_uniqueness", lambda out: True)

        cmd_survey_import_limesurvey(
            SimpleNamespace(
                input=str(tmp_path / "archive.lsa"),
                output=str(tmp_path / "out"),
                task="task1",
            )
        )
        assert calls["convert"][2] == "task1"

    def test_error_exits(self, tmp_path, monkeypatch, capsys):
        def _boom(inp, out, task_name):
            raise RuntimeError("bad lsa")

        monkeypatch.setattr(survey_cli, "convert_lsa_to_prism", _boom)
        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_import_limesurvey(
                SimpleNamespace(
                    input=str(tmp_path / "archive.lsa"),
                    output=str(tmp_path / "out"),
                    task="task1",
                )
            )
        assert exc_info.value.code == 1
        assert "Error importing LimeSurvey" in capsys.readouterr().out


class TestCmdSurveyImportLimesurveyBatch:
    def test_no_valid_session_map_exits(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_import_limesurvey_batch(
                SimpleNamespace(
                    session_map="bogus",
                    input_dir=str(tmp_path),
                    output_dir=str(tmp_path / "out"),
                    library=None,
                    id_map=None,
                    task="task1",
                    subject_id_col="id",
                )
            )
        assert exc_info.value.code == 1
        assert "No valid session mapping" in capsys.readouterr().out

    def test_success(self, tmp_path, monkeypatch):
        calls = {}
        monkeypatch.setattr(
            survey_cli,
            "batch_convert_lsa",
            lambda *a, **kw: calls.setdefault("args", (a, kw)),
        )
        monkeypatch.setattr(survey_cli, "check_uniqueness", lambda out: True)

        cmd_survey_import_limesurvey_batch(
            SimpleNamespace(
                session_map="t1:ses-1,t2:ses-2",
                input_dir=str(tmp_path),
                output_dir=str(tmp_path / "out"),
                library=str(tmp_path / "lib"),
                id_map=str(tmp_path / "ids.json"),
                task="task1",
                subject_id_col="id",
            )
        )
        assert calls["args"][1]["task_fallback"] == "task1"

    def test_error_exits(self, tmp_path, monkeypatch, capsys):
        def _boom(*a, **kw):
            raise RuntimeError("bad batch")

        monkeypatch.setattr(survey_cli, "batch_convert_lsa", _boom)
        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_import_limesurvey_batch(
                SimpleNamespace(
                    session_map="t1:ses-1",
                    input_dir=str(tmp_path),
                    output_dir=str(tmp_path / "out"),
                    library=None,
                    id_map=None,
                    task="task1",
                    subject_id_col="id",
                )
            )
        assert exc_info.value.code == 1
        assert "Error importing LimeSurvey" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# i18n migrate / build / autotranslate
# ---------------------------------------------------------------------------


class TestCmdSurveyI18nMigrate:
    def test_missing_src_dir_exits(self, tmp_path, capsys):
        with pytest.raises(SystemExit):
            cmd_survey_i18n_migrate(
                SimpleNamespace(
                    src=str(tmp_path / "missing"),
                    dst=str(tmp_path / "dst"),
                    languages="de,en",
                )
            )

    def test_no_survey_files_exits(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        with pytest.raises(SystemExit):
            cmd_survey_i18n_migrate(
                SimpleNamespace(src=str(src), dst=str(tmp_path / "dst"), languages="")
            )

    def test_migrates_files_and_skips_unreadable(self, tmp_path, monkeypatch, capsys):
        src = tmp_path / "src"
        src.mkdir()
        (src / "survey-a.json").write_text(json.dumps({"a": 1}))
        (src / "survey-bad.json").write_text("not json")

        monkeypatch.setattr(
            survey_cli,
            "migrate_survey_template_to_i18n",
            lambda data, languages: {"migrated": True, **data},
        )

        cmd_survey_i18n_migrate(
            SimpleNamespace(src=str(src), dst=str(tmp_path / "dst"), languages="de;en")
        )

        out = capsys.readouterr().out
        assert "Migrated 1 template" in out
        assert "Skipping unreadable JSON" in out
        assert (tmp_path / "dst" / "survey-a.json").exists()

    def test_default_languages_when_none_given(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        src.mkdir()
        (src / "survey-a.json").write_text(json.dumps({}))
        captured = {}
        monkeypatch.setattr(
            survey_cli,
            "migrate_survey_template_to_i18n",
            lambda data, languages: captured.setdefault("languages", languages) or {},
        )
        cmd_survey_i18n_migrate(
            SimpleNamespace(src=str(src), dst=str(tmp_path / "dst"), languages="")
        )
        assert captured["languages"] == ["de", "en"]


class TestCmdSurveyI18nBuild:
    def test_missing_src_dir_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            cmd_survey_i18n_build(
                SimpleNamespace(
                    src=str(tmp_path / "missing"),
                    out=str(tmp_path / "out"),
                    lang="en",
                    fallback=None,
                )
            )

    def test_no_survey_files_exits(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        with pytest.raises(SystemExit):
            cmd_survey_i18n_build(
                SimpleNamespace(
                    src=str(src), out=str(tmp_path / "out"), lang="en", fallback=None
                )
            )

    def test_builds_files_and_skips_unreadable(self, tmp_path, monkeypatch, capsys):
        src = tmp_path / "src"
        src.mkdir()
        (src / "survey-a.json").write_text(json.dumps({"a": 1}))
        (src / "survey-bad.json").write_text("not json")

        monkeypatch.setattr(
            survey_cli,
            "compile_survey_template",
            lambda data, lang, fallback_langs: {"compiled": True, **data},
        )

        cmd_survey_i18n_build(
            SimpleNamespace(
                src=str(src), out=str(tmp_path / "out"), lang="en", fallback="de"
            )
        )

        out = capsys.readouterr().out
        assert "Built 1 template" in out
        assert (tmp_path / "out" / "survey-a.json").exists()


class TestCmdSurveyI18nAutotranslate:
    def test_missing_src_dir_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            cmd_survey_i18n_autotranslate(
                SimpleNamespace(
                    src=str(tmp_path / "missing"),
                    in_place=False,
                    out=str(tmp_path / "out"),
                    provider="noop",
                )
            )

    def test_missing_out_without_in_place_exits(self, tmp_path, capsys):
        src = tmp_path / "src"
        src.mkdir()
        with pytest.raises(SystemExit):
            cmd_survey_i18n_autotranslate(
                SimpleNamespace(
                    src=str(src), in_place=False, out=None, provider="noop"
                )
            )
        assert "--out is required" in capsys.readouterr().out

    def test_translation_error_exits(self, tmp_path, monkeypatch, capsys):
        src = tmp_path / "src"
        src.mkdir()

        def _boom_provider(*a, **kw):
            raise survey_cli.TranslationError("bad provider")

        monkeypatch.setattr(survey_cli, "build_translation_provider", _boom_provider)

        with pytest.raises(SystemExit):
            cmd_survey_i18n_autotranslate(
                SimpleNamespace(src=str(src), in_place=True, out=None, provider="noop")
            )
        assert "Translation error" in capsys.readouterr().out

    def test_generic_error_exits(self, tmp_path, monkeypatch, capsys):
        src = tmp_path / "src"
        src.mkdir()
        monkeypatch.setattr(
            survey_cli, "build_translation_provider", lambda *a, **kw: object()
        )

        def _boom_translate(*a, **kw):
            raise RuntimeError("boom")

        monkeypatch.setattr(survey_cli, "autotranslate_survey_library", _boom_translate)

        with pytest.raises(SystemExit):
            cmd_survey_i18n_autotranslate(
                SimpleNamespace(src=str(src), in_place=True, out=None, provider="noop")
            )
        assert "Error: boom" in capsys.readouterr().out

    def test_success_in_place(self, tmp_path, monkeypatch, capsys):
        src = tmp_path / "src"
        src.mkdir()
        monkeypatch.setattr(
            survey_cli, "build_translation_provider", lambda *a, **kw: object()
        )
        stats = SimpleNamespace(
            files_processed=2,
            files_changed=1,
            localized_entries_added=3,
            unique_source_texts=4,
        )
        monkeypatch.setattr(
            survey_cli, "autotranslate_survey_library", lambda *a, **kw: stats
        )

        cmd_survey_i18n_autotranslate(
            SimpleNamespace(
                src=str(src),
                in_place=True,
                out=None,
                provider="noop",
                api_key=None,
                api_url=None,
                source_lang="en",
                target_lang="de",
                overwrite_existing=False,
                batch_size=10,
            )
        )
        out = capsys.readouterr().out
        assert "Auto-translation complete" in out
        assert "Files processed: 2" in out


# ---------------------------------------------------------------------------
# cmd_survey_convert
# ---------------------------------------------------------------------------


def _convert_args(tmp_path, **overrides):
    defaults = dict(
        input=str(tmp_path / "in.xlsx"),
        output=str(tmp_path / "out"),
        library=str(tmp_path / "library"),
        lang="de",
        survey="pss",
        id_column="id",
        session_column=None,
        run_column=None,
        sheet=None,
        unknown="ignore",
        dry_run=False,
        force=False,
        name=None,
        authors=None,
        alias=None,
        project=None,
        template_versions=None,
        value_offsets=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class _FakeResult:
    def __init__(self, **overrides):
        self.id_column = "id"
        self.session_column = None
        self.run_column = None
        self.tasks_included = ["pss"]
        self.missing_items_by_task = {}
        self.missing_value_token = "n/a"
        self.missing_cells_by_subject = {}
        self.unknown_columns = []
        self.dry_run_preview = None
        for key, value in overrides.items():
            setattr(self, key, value)


class TestCmdSurveyConvert:
    def _plain_library(self, tmp_path):
        library = tmp_path / "library"
        library.mkdir()
        (library / "survey-pss.json").write_text(json.dumps({"pss01": {}}))
        return library

    def test_no_library_found_exits(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(survey_cli, "_APP_ROOT", tmp_path / "no_such_root")
        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_convert(_convert_args(tmp_path, library=None))
        assert exc_info.value.code == 1
        assert "Could not find a survey template library" in capsys.readouterr().out

    def test_success_basic(self, tmp_path, monkeypatch, capsys):
        self._plain_library(tmp_path)
        monkeypatch.setattr(
            "src.converters.survey.convert_survey_xlsx_to_prism_dataset",
            lambda **kw: _FakeResult(),
        )
        cmd_survey_convert(_convert_args(tmp_path))
        out = capsys.readouterr().out
        assert "Survey conversion complete" in out

    def test_conversion_error_exits(self, tmp_path, monkeypatch, capsys):
        self._plain_library(tmp_path)

        def _boom(**kw):
            raise RuntimeError("bad convert")

        monkeypatch.setattr(
            "src.converters.survey.convert_survey_xlsx_to_prism_dataset", _boom
        )
        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_convert(_convert_args(tmp_path))
        assert exc_info.value.code == 1
        assert "Error: bad convert" in capsys.readouterr().out

    def test_with_overrides_offsets_and_warnings(self, tmp_path, monkeypatch, capsys):
        self._plain_library(tmp_path)
        monkeypatch.setattr(
            "src.converters.survey.convert_survey_xlsx_to_prism_dataset",
            lambda **kw: _FakeResult(
                session_column="session",
                run_column="run",
                missing_items_by_task={"pss": 2},
                missing_cells_by_subject={"sub-01": 3, "sub-02": 1},
                unknown_columns=["extra_col"],
            ),
        )
        cmd_survey_convert(
            _convert_args(
                tmp_path,
                template_versions=["pss=v2"],
                value_offsets=["pss=-1"],
                unknown="warn",
            )
        )
        out = capsys.readouterr().out
        assert "Versions: pss=v2" in out
        assert "Value offsets: pss=-1" in out
        assert "WARNING: Normalized 4 missing cells" in out
        assert "Unmapped columns" in out

    def test_project_path_resolved_when_file(self, tmp_path, monkeypatch):
        self._plain_library(tmp_path)
        captured = {}

        def _fake_convert(**kw):
            captured.update(kw)
            return _FakeResult()

        monkeypatch.setattr(
            "src.converters.survey.convert_survey_xlsx_to_prism_dataset", _fake_convert
        )
        project_file = tmp_path / "project.json"
        project_file.write_text("{}")
        cmd_survey_convert(_convert_args(tmp_path, project=str(project_file)))
        assert captured["project_path"] == project_file.parent

    def test_dry_run_renders_full_preview(self, tmp_path, monkeypatch, capsys):
        self._plain_library(tmp_path)
        preview = {
            "summary": {
                "total_participants": 10,
                "unique_participants": 9,
                "tasks": ["pss"],
                "session_column": "session",
                "run_column": "run",
                "total_files": 5,
            },
            "data_issues": [
                {
                    "severity": "error",
                    "type": "duplicate_ids",
                    "message": "dup ids",
                    "details": {"sub-01": 2},
                },
                {
                    "severity": "warning",
                    "type": "unexpected_values",
                    "message": "bad value",
                    "column": "pss01",
                    "task": "pss",
                    "item": "pss01",
                    "expected": ["1", "2"],
                    "unexpected": ["9"],
                },
                {
                    "severity": "warning",
                    "type": "out_of_range",
                    "message": "out of range",
                    "column": "pss02",
                    "task": "pss",
                    "item": "pss02",
                    "range": "0-4",
                    "out_of_range_count": 3,
                },
            ],
            "participants_tsv": {
                "columns": ["participant_id", "age"],
                "sample_rows": [{"participant_id": "sub-01", "age": 30}],
                "total_rows": 1,
                "mappings": {
                    "age": {
                        "source_column": "Age",
                        "has_value_mapping": True,
                        "value_mapping": {"1": "young"},
                    }
                },
                "notes": ["some note"],
                "unused_columns": [
                    {"field_code": "extra1", "description": "desc1"},
                    "extra2",
                ],
            },
            "participants": [
                {
                    "participant_id": "sub-01",
                    "session_id": "ses-1",
                    "raw_id": "1",
                    "completeness_percent": 90,
                    "total_items": 10,
                    "missing_values": 1,
                },
                {
                    "participant_id": "sub-02",
                    "session_id": "ses-1",
                    "raw_id": "2",
                    "completeness_percent": 40,
                    "total_items": 10,
                    "missing_values": 6,
                },
            ],
            "column_mapping": {
                "pss01": {
                    "run": 1,
                    "base_item": "pss01",
                    "missing_percent": 10.0,
                    "missing_count": 1,
                    "has_unexpected_values": True,
                    "task": "pss",
                }
            },
            "files_to_create": [
                {"type": "metadata", "path": "a.json", "description": "meta"},
                {"type": "sidecar", "path": "b.json", "description": "sidecar"},
                {"type": "data", "path": "c.tsv", "description": "data"},
            ],
        }
        monkeypatch.setattr(
            "src.converters.survey.convert_survey_xlsx_to_prism_dataset",
            lambda **kw: _FakeResult(dry_run_preview=preview),
        )
        cmd_survey_convert(_convert_args(tmp_path, dry_run=True))
        out = capsys.readouterr().out
        assert "DRY-RUN MODE" in out
        assert "DATA ISSUES FOUND" in out
        assert "PARTICIPANTS.TSV PREVIEW" in out
        assert "UNUSED COLUMNS" in out
        assert "PARTICIPANT SURVEY COMPLETENESS" in out
        assert "COLUMN MAPPING" in out
        assert "FILES TO CREATE" in out
        assert "No files were created" in out

    def test_dry_run_no_issues_no_preview_data(self, tmp_path, monkeypatch, capsys):
        self._plain_library(tmp_path)
        preview = {
            "summary": {
                "total_participants": 1,
                "unique_participants": 1,
                "tasks": ["pss"],
                "session_column": None,
                "run_column": None,
                "total_files": 1,
            },
            "data_issues": [],
            "participants": [],
            "column_mapping": {},
            "files_to_create": [],
        }
        monkeypatch.setattr(
            "src.converters.survey.convert_survey_xlsx_to_prism_dataset",
            lambda **kw: _FakeResult(dry_run_preview=preview),
        )
        cmd_survey_convert(_convert_args(tmp_path, dry_run=True))
        out = capsys.readouterr().out
        assert "NO DATA ISSUES DETECTED" in out

    def test_library_with_i18n_compiles(self, tmp_path, monkeypatch, capsys):
        library = tmp_path / "library"
        library.mkdir()
        (library / "survey-pss.json").write_text(
            json.dumps({"I18n": True, "pss01": {}})
        )
        monkeypatch.setattr(
            survey_cli,
            "compile_survey_template",
            lambda data, lang, fallback_langs: {"compiled": True},
        )
        monkeypatch.setattr(
            "src.converters.survey.convert_survey_xlsx_to_prism_dataset",
            lambda **kw: _FakeResult(),
        )
        cmd_survey_convert(_convert_args(tmp_path, library=str(library)))
        out = capsys.readouterr().out
        assert "i18n compiled to de" in out

    def test_default_library_discovery_compiled_candidate(
        self, tmp_path, monkeypatch, capsys
    ):
        app_root = tmp_path / "app_root"
        lib_dir = app_root / "library" / "survey_de"
        lib_dir.mkdir(parents=True)
        (lib_dir / "survey-pss.json").write_text(json.dumps({"pss01": {}}))
        monkeypatch.setattr(survey_cli, "_APP_ROOT", app_root)
        monkeypatch.setattr(
            "src.converters.survey.convert_survey_xlsx_to_prism_dataset",
            lambda **kw: _FakeResult(),
        )
        cmd_survey_convert(_convert_args(tmp_path, library=None))
        out = capsys.readouterr().out
        assert "Survey conversion complete" in out

    def test_default_library_discovery_i18n_candidate(
        self, tmp_path, monkeypatch, capsys
    ):
        app_root = tmp_path / "app_root"
        lib_dir = app_root / "library" / "survey_i18n"
        lib_dir.mkdir(parents=True)
        (lib_dir / "survey-pss.json").write_text(json.dumps({"pss01": {}}))
        monkeypatch.setattr(survey_cli, "_APP_ROOT", app_root)
        monkeypatch.setattr(
            survey_cli,
            "compile_survey_template",
            lambda data, lang, fallback_langs: {"compiled": True},
        )
        monkeypatch.setattr(
            "src.converters.survey.convert_survey_xlsx_to_prism_dataset",
            lambda **kw: _FakeResult(),
        )
        cmd_survey_convert(_convert_args(tmp_path, library=None))
        out = capsys.readouterr().out
        assert "i18n compiled to de" in out

    def test_default_library_discovery_legacy_candidate(
        self, tmp_path, monkeypatch, capsys
    ):
        app_root = tmp_path / "app_root"
        lib_dir = app_root / "library" / "survey"
        lib_dir.mkdir(parents=True)
        (lib_dir / "survey-pss.json").write_text(json.dumps({"pss01": {}}))
        monkeypatch.setattr(survey_cli, "_APP_ROOT", app_root)
        monkeypatch.setattr(
            "src.converters.survey.convert_survey_xlsx_to_prism_dataset",
            lambda **kw: _FakeResult(),
        )
        cmd_survey_convert(_convert_args(tmp_path, library=None))
        out = capsys.readouterr().out
        assert "Survey conversion complete" in out
