"""`survey convert` and Studio's convert take the same options with the same defaults (THE RULE, CLAUDE.md)."""

import argparse
import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src.cli.parser import build_prism_tools_parsers  # noqa: E402
from src.survey_workflow_service import SurveyWorkflowStageOptions  # noqa: E402

# Studio option -> the CLI flag's dest (renamed only where the CLI had a name first)
RENAMED = {
    "input_path": "input", "output_root": "output", "library_dir": "library", "language": "lang",
    "alias_file": "alias", "template_version_overrides": "template_versions", "task_value_offsets": "value_offsets",
    "project_path": "project", "id_map_file": "id_map",
}
# set by the adapter or internal, not an option the user picks
INTERNAL = {"suffix", "fallback_project_path", "log_fn", "skip_participants"}


def _convert_parser():
    _root, parsers = build_prism_tools_parsers(Path(__file__).resolve().parents[1] / "app")
    sub = [a for a in parsers["survey"]._actions if isinstance(a, argparse._SubParsersAction)][0]
    return sub.choices["convert"]


def _options():
    return {f.name: f for f in dataclasses.fields(SurveyWorkflowStageOptions) if f.name not in INTERNAL}


def test_every_studio_option_has_a_cli_flag():
    flags = {a.dest for a in _convert_parser()._actions}
    missing = sorted(name for name in _options() if RENAMED.get(name, name) not in flags)
    assert not missing, f"Studio options with no `survey convert` flag: {missing}"


def test_shared_options_have_the_same_default():
    parser, differing = _convert_parser(), []
    cli_defaults = {a.dest: a.default for a in parser._actions}
    for name, field in _options().items():
        dest = RENAMED.get(name, name)
        if dest not in cli_defaults or field.default is dataclasses.MISSING:
            continue
        studio, cli = field.default, cli_defaults[dest]
        if (studio or None) != (cli or None):  # () / "" / None / False all mean "not given"
            differing.append((name, studio, cli))
    assert not differing, f"different defaults (option, Studio, CLI): {differing}"


def _run_cli(tmp_path, monkeypatch, input_name, **flags):
    """Run `survey convert` with fake converters; return the arguments the converter received."""
    from types import SimpleNamespace

    from src.cli.commands.survey import cmd_survey_convert

    library = tmp_path / "library"
    library.mkdir(exist_ok=True)
    (library / "survey-pss.json").write_text("{}", encoding="utf-8")
    seen = {}

    def converter(**kw):
        seen.update(kw)
        return SimpleNamespace(
            id_column="id", session_column=None, run_column=None, tasks_included=[], missing_items_by_task={},
            missing_cells_by_subject={}, unknown_columns=[], dry_run_preview=None, detected_sessions=[], task_runs={},
            data_issues=[], conversion_warnings=[], template_matches={}, column_mapping={},
        )

    monkeypatch.setattr("src.converters.survey.convert_survey_file_to_prism_dataset", converter)
    monkeypatch.setattr("src.converters.survey.convert_survey_lsa_to_prism_dataset", converter)
    args = dict(
        input=str(tmp_path / input_name), output=str(tmp_path / "out"), library=str(library), lang=None, survey=None,
        id_column=None, session_column=None, run_column=None, sheet=None, unknown="warn", dry_run=False, force=None,
        name=None, authors=None, alias=None, project=None, template_versions=None, value_offsets=None,
        strict_levels=False, allow_near_item_match=False, near_match_tasks=None, separator=None, id_map=None,
    )
    args.update(flags)
    try:
        cmd_survey_convert(SimpleNamespace(**args))
    except SystemExit:
        pass  # the report of a fake result may not render; the converter call is what counts
    return seen


def test_the_new_flags_reach_the_converter(tmp_path, monkeypatch):
    seen = _run_cli(
        tmp_path, monkeypatch, "answers.csv", separator="semicolon", allow_near_item_match=True,
        near_match_tasks="pss, gad7", id_map=str(tmp_path / "ids.tsv"),
    )
    assert seen["separator"] == "semicolon"
    assert seen["allow_near_item_match"] is True
    assert seen["near_match_tasks"] == ["pss", "gad7"]
    assert Path(seen["id_map_file"]) == tmp_path / "ids.tsv"


def test_strict_levels_reaches_the_lsa_converter(tmp_path, monkeypatch):
    assert _run_cli(tmp_path, monkeypatch, "survey.lsa", strict_levels=True)["strict_levels"] is True
    assert _run_cli(tmp_path, monkeypatch, "survey.lsa")["strict_levels"] is None  # Studio: None unless asked


def test_force_is_on_for_a_project_and_off_otherwise_unless_given(tmp_path, monkeypatch):
    assert _run_cli(tmp_path, monkeypatch, "a.csv")["force"] is False
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "project.json").write_text("{}", encoding="utf-8")
    assert _run_cli(tmp_path, monkeypatch, "a.csv")["force"] is True
    assert _run_cli(tmp_path, monkeypatch, "a.csv", force=False)["force"] is False
