"""CLI commands for Studio actions that previously had no CLI equivalent.

Every non-Projects GUI action must be runnable from prism_tools and reach the
same backend code as the GUI.
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

import src.cli.commands.dataset as dataset_cmds  # noqa: E402
import src.cli.commands.participants as participants_cmds  # noqa: E402
import src.cli.commands.recipes as recipes_cmds  # noqa: E402
import src.cli.commands.survey as survey_cmds  # noqa: E402
from src.cli.parser import build_prism_tools_parsers  # noqa: E402


def _touch(path: Path, content: bytes = b"data") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _args(**overrides) -> SimpleNamespace:
    defaults = dict(dry_run=False, yes=True, json=False)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.parametrize(
    "argv, attr, value",
    [
        (
            ["dataset", "rename-sessions", "--project", "p", "--example-session", "ses-1", "--keep-fragment", "1"],
            "action",
            "rename-sessions",
        ),
        (["dataset", "renumber-runs", "--project", "p"], "action", "renumber-runs"),
        (["dataset", "undo", "--project", "p"], "action", "undo"),
        (["survey", "import-lsq", "--input", "q.lsq", "--output", "o.json"], "action", "import-lsq"),
        (["participants", "fix-bids", "--file", "participants.tsv"], "action", "fix-bids"),
        (["recipes", "save", "--project", "p", "--recipe", "r.json"], "kind", "save"),
    ],
)
def test_parser_accepts_new_commands(argv, attr, value):
    parser, _ = build_prism_tools_parsers(APP_ROOT)
    args = parser.parse_args(argv)
    assert getattr(args, attr) == value


# --- dataset rename-sessions -------------------------------------------------


def _session_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    _touch(root / "sub-001" / "ses-baseline1" / "func" / "sub-001_ses-baseline1_task-rest_bold.nii.gz")
    return root


def _session_args(root: Path, **overrides) -> SimpleNamespace:
    values = dict(
        project=str(root),
        example_session="ses-baseline1",
        keep_fragment="baseline",
        add_text=None,
        add_position=None,
        allow_many_to_one=False,
    )
    values.update(overrides)
    return _args(**values)


def test_rename_sessions_dry_run_leaves_files(tmp_path, capsys):
    root = _session_project(tmp_path)
    dataset_cmds.cmd_dataset_rename_sessions(_session_args(root, dry_run=True))

    assert (root / "sub-001" / "ses-baseline1").exists()
    assert "ses-baseline1 -> ses-baseline" in capsys.readouterr().out


def test_rename_sessions_apply_renames_session(tmp_path):
    root = _session_project(tmp_path)
    dataset_cmds.cmd_dataset_rename_sessions(_session_args(root))

    assert not (root / "sub-001" / "ses-baseline1").exists()
    assert (root / "sub-001" / "ses-baseline" / "func" / "sub-001_ses-baseline_task-rest_bold.nii.gz").exists()


def test_rename_sessions_keeps_similar_numeric_labels_distinct(tmp_path):
    root = tmp_path / "project"
    (root / "sub-001" / "ses-1").mkdir(parents=True)
    (root / "sub-002" / "ses-01").mkdir(parents=True)

    dataset_cmds.cmd_dataset_rename_sessions(
        _session_args(
            root,
            example_session="ses-1",
            keep_fragment=None,
            add_text="visit",
            add_position="prepend",
        )
    )

    assert (root / "sub-001" / "ses-visit1").exists()
    assert (root / "sub-002" / "ses-visit01").exists()


# --- dataset renumber-runs / dataset undo ------------------------------------


def _run_gap_project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "project"
    func = root / "sub-001" / "ses-01" / "func"
    _touch(func / "sub-001_ses-01_task-rest_run-01_bold.nii.gz")
    _touch(func / "sub-001_ses-01_task-rest_run-03_bold.nii.gz")
    return root, func


def test_renumber_runs_closes_gap(tmp_path):
    root, func = _run_gap_project(tmp_path)
    dataset_cmds.cmd_dataset_renumber_runs(_args(project=str(root)))

    assert (func / "sub-001_ses-01_task-rest_run-02_bold.nii.gz").exists()
    assert not (func / "sub-001_ses-01_task-rest_run-03_bold.nii.gz").exists()


def test_renumber_runs_dry_run_leaves_files(tmp_path):
    root, func = _run_gap_project(tmp_path)
    dataset_cmds.cmd_dataset_renumber_runs(_args(project=str(root), dry_run=True))

    assert (func / "sub-001_ses-01_task-rest_run-03_bold.nii.gz").exists()
    assert not (func / "sub-001_ses-01_task-rest_run-02_bold.nii.gz").exists()


def test_undo_reverses_last_operation(tmp_path):
    root, func = _run_gap_project(tmp_path)
    dataset_cmds.cmd_dataset_renumber_runs(_args(project=str(root)))
    dataset_cmds.cmd_dataset_undo(_args(project=str(root)))

    assert (func / "sub-001_ses-01_task-rest_run-03_bold.nii.gz").exists()
    assert not (func / "sub-001_ses-01_task-rest_run-02_bold.nii.gz").exists()


def test_undo_with_nothing_to_undo_exits_with_error(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    with pytest.raises(SystemExit) as exc_info:
        dataset_cmds.cmd_dataset_undo(_args(project=str(root)))
    assert exc_info.value.code == 1


# --- survey import-lsq -------------------------------------------------------

_MINIMAL_LSQ = """<?xml version="1.0" encoding="UTF-8"?>
<document>
  <questions><rows>
    <row>
      <qid>10</qid>
      <gid>1</gid>
      <type>L</type>
      <title>MOOD</title>
      <question>How do you feel today?</question>
      <question_order>1</question_order>
      <mandatory>Y</mandatory>
      <parent_qid>0</parent_qid>
      <other>N</other>
      <preg></preg>
    </row>
  </rows></questions>
  <answers><rows>
    <row><qid>10</qid><code>1</code><answer>Good</answer><language>en</language></row>
    <row><qid>10</qid><code>2</code><answer>Bad</answer><language>en</language></row>
  </rows></answers>
  <question_attributes><rows></rows></question_attributes>
  <subquestions><rows></rows></subquestions>
</document>
"""


def test_import_lsq_writes_template_with_question(tmp_path):
    source = tmp_path / "mood.lsq"
    source.write_text(_MINIMAL_LSQ, encoding="utf-8")
    output = tmp_path / "survey-mood.json"

    survey_cmds.cmd_survey_import_lsq(SimpleNamespace(input=str(source), output=str(output), json=False))

    template = json.loads(output.read_text(encoding="utf-8"))
    assert "MOOD" in template


def test_import_lsq_rejects_other_file_types(tmp_path):
    source = tmp_path / "mood.txt"
    source.write_text(_MINIMAL_LSQ, encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        survey_cmds.cmd_survey_import_lsq(
            SimpleNamespace(input=str(source), output=str(tmp_path / "out.json"), json=False)
        )
    assert exc_info.value.code == 1


# --- participants fix-bids ---------------------------------------------------


def _participants_tsv(tmp_path: Path) -> Path:
    path = tmp_path / "participants.tsv"
    path.write_text("participant_id\tsex\nsub-01\t1\nsub-02\t2\n", encoding="utf-8")
    return path


def test_fix_participants_tsv_maps_numeric_sex_codes(tmp_path):
    from src.participants_bids_fix import fix_participants_tsv

    path = _participants_tsv(tmp_path)
    result = fix_participants_tsv(path)

    assert result["changes"][0]["column"] == "sex"
    assert path.read_text(encoding="utf-8").splitlines() == [
        "participant_id\tsex",
        "sub-01\tM",
        "sub-02\tF",
    ]


def test_fix_participants_tsv_dry_run_does_not_write(tmp_path):
    from src.participants_bids_fix import fix_participants_tsv

    path = _participants_tsv(tmp_path)
    result = fix_participants_tsv(path, dry_run=True)

    assert result["dry_run"] is True
    assert "sub-01\t1" in path.read_text(encoding="utf-8")


def test_cli_fix_bids_rewrites_file(tmp_path):
    path = _participants_tsv(tmp_path)
    participants_cmds.cmd_participants_fix_bids(SimpleNamespace(file=str(path), dry_run=False, json=False))
    assert "sub-01\tM" in path.read_text(encoding="utf-8")


def test_cli_fix_bids_missing_file_exits_with_error(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        participants_cmds.cmd_participants_fix_bids(
            SimpleNamespace(file=str(tmp_path / "missing.tsv"), dry_run=False, json=False)
        )
    assert exc_info.value.code == 1


def test_gui_fix_participants_handler_rewrites_file_and_reports_success(tmp_path):
    # The default sex mapping mixes int and str keys; Flask sorts JSON keys, so
    # returning it unconverted made the GUI report an error after fixing the file.
    from flask import Flask

    from src.web.blueprints.tools_post_conversion_handlers import handle_fix_participants_bids

    path = _participants_tsv(tmp_path)
    with Flask(__name__).app_context():
        response = handle_fix_participants_bids({"file_path": str(path)})

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert "sub-01\tM" in path.read_text(encoding="utf-8")


# --- recipes save ------------------------------------------------------------


def _write_recipe(tmp_path: Path, task: str, items: list[str], method: str = "mean") -> Path:
    path = tmp_path / "recipe.json"
    path.write_text(
        json.dumps(
            {
                "RecipeVersion": "1.0",
                "Kind": "survey",
                "Survey": {"TaskName": task},
                "Scores": [{"Name": f"{task}_total", "Method": method, "Items": items}],
            }
        ),
        encoding="utf-8",
    )
    return path


def _recipe_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    library = root / "code" / "library" / "survey"
    library.mkdir(parents=True)
    (library / "survey-ads.json").write_text(json.dumps({"Study": {"TaskName": "ads"}}), encoding="utf-8")
    return root


def test_recipes_save_writes_recipe_into_project(tmp_path):
    root = _recipe_project(tmp_path)
    recipe = _write_recipe(tmp_path, "ads", ["ADS01", "ADS02"])

    recipes_cmds.cmd_recipes_save(SimpleNamespace(project=str(root), recipe=str(recipe), modality=None, json=False))

    saved = root / "code" / "recipes" / "survey" / "recipe-ads.json"
    assert json.loads(saved.read_text(encoding="utf-8"))["Scores"][0]["Name"] == "ads_total"


def test_recipes_save_rejects_invalid_recipe(tmp_path):
    root = _recipe_project(tmp_path)
    recipe = _write_recipe(tmp_path, "ads", ["ADS01", "ADS02"], method="median")

    with pytest.raises(SystemExit) as exc_info:
        recipes_cmds.cmd_recipes_save(SimpleNamespace(project=str(root), recipe=str(recipe), modality=None, json=False))

    assert exc_info.value.code == 1
    assert not (root / "code" / "recipes" / "survey" / "recipe-ads.json").exists()


def test_recipes_save_finds_official_library_template(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    recipe = _write_recipe(tmp_path, "phq9", ["PHQ901", "PHQ902"])

    recipes_cmds.cmd_recipes_save(SimpleNamespace(project=str(root), recipe=str(recipe), modality=None, json=False))

    assert (root / "code" / "recipes" / "survey" / "recipe-phq9.json").exists()


# --- survey customizer-groups -----------------------------------------------


def test_customizer_groups_feeds_export_lss_customized(tmp_path):
    template = tmp_path / "survey-mini.json"
    template.write_text(
        json.dumps(
            {
                "Study": {"OriginalName": "Mini"},
                "Questions": {
                    "Q1": {"Description": {"en": "How are you?"}, "Levels": {"1": "ok"}},
                    "Q2": {"Description": "Sleep well?", "Levels": {"1": "yes"}},
                },
            }
        ),
        encoding="utf-8",
    )
    groups_path = tmp_path / "groups.json"
    survey_cmds.cmd_survey_customizer_groups(
        SimpleNamespace(template=[str(template)], output=str(groups_path), language="en", runs=2)
    )

    groups = json.loads(groups_path.read_text(encoding="utf-8"))["groups"]
    assert [g["name"] for g in groups] == ["Mini (Run 1)", "Mini (Run 2)"]
    assert [q["questionCode"] for q in groups[0]["questions"]] == ["Q1", "Q2"]
    assert groups[0]["questions"][0]["description"] == "How are you?"

    lss_path = tmp_path / "out.lss"
    survey_cmds.cmd_survey_export_lss_customized(
        SimpleNamespace(
            customization_json=str(groups_path),
            output=str(lss_path),
            language="en",
            languages=None,
            base_language=None,
            ls_version="6",
            survey_title="Mini",
            no_matrix=False,
            no_matrix_global=False,
        )
    )
    assert lss_path.is_file()


def test_customizer_groups_rejects_template_without_questions(tmp_path):
    template = tmp_path / "empty.json"
    template.write_text(json.dumps({"Study": {}}), encoding="utf-8")
    with pytest.raises(SystemExit):
        survey_cmds.cmd_survey_customizer_groups(
            SimpleNamespace(template=[str(template)], output=str(tmp_path / "g.json"), language="en", runs=1)
        )


def test_customizer_groups_uses_requested_display_language(tmp_path):
    template = tmp_path / "survey-bi.json"
    template.write_text(
        json.dumps({"Questions": {"Q1": {"Description": {"en": "Hello", "de": "Hallo"}}}}),
        encoding="utf-8",
    )
    groups_path = tmp_path / "groups.json"
    survey_cmds.cmd_survey_customizer_groups(
        SimpleNamespace(template=[str(template)], output=str(groups_path), language="de", runs=1)
    )

    groups = json.loads(groups_path.read_text(encoding="utf-8"))["groups"]
    assert groups[0]["questions"][0]["description"] == "Hallo"
