"""Using a library template saves the survey's item codes in the project item map, not as Aliases."""

import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_library_wording_match import library_file  # noqa: E402
from test_template_import_pipeline import ADS, ADS_LEVELS, FIXTURE_LSS, _client, _template  # noqa: E402

from src.converters import survey_templates as st  # noqa: E402
from src.converters.library_wording_match import apply_library_template, best_library_match  # noqa: E402
from src.converters.template_import import finish_import  # noqa: E402


@pytest.fixture
def library(tmp_path, monkeypatch):
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    project = tmp_path / "project"
    monkeypatch.setattr(st, "_load_global_library_path", lambda: global_dir)
    library_file(project / "code" / "library" / "survey", texts=ADS, levels=ADS_LEVELS)
    return project


def _tree(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in sorted(root.rglob("*")) if p.is_file()}


def test_apply_library_template_adds_no_aliases(library):
    match = best_library_match(_template(), str(library))
    template = apply_library_template(match)
    assert not any("Aliases" in v for v in template.values() if isinstance(v, dict))


def test_use_library_saves_the_item_map(library):
    payload = finish_import(_template(), "ADS", str(library), use_library=True)
    saved = json.loads((library / "code" / "item_maps" / "ads.json").read_text(encoding="utf-8"))
    assert saved == {"ads_01": "ADS1_1", "ads_02": "ADS1_2"}
    assert payload["item_map"] == {"task": "ads", "path": "code/item_maps/ads.json", "entries": 2}


def test_identical_codes_write_no_map(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "_load_global_library_path", lambda: tmp_path)
    project = tmp_path / "p"
    library_file(project / "code" / "library" / "survey", texts=ADS, levels=ADS_LEVELS, codes=["ADS1_1", "ADS1_2"])
    payload = finish_import(_template(), "ADS", str(project), use_library=True)
    assert payload["item_map"] is None
    assert not (project / "code" / "item_maps").exists()


def test_without_use_library_there_is_no_item_map(library):
    assert finish_import(_template(), "ADS", str(library))["item_map"] is None
    assert not (library / "code" / "item_maps").exists()


def test_use_library_without_a_project_needs_one(library):
    with pytest.raises(ValueError, match="project item map"):
        finish_import(_template(), "ADS", use_library=True)


def test_studio_and_cli_leave_the_same_files(library, tmp_path):
    from src.cli.commands.survey import cmd_survey_import_limesurvey

    studio_project = tmp_path / "studio_project"
    shutil.copytree(library, studio_project)
    out = tmp_path / "out"
    cmd_survey_import_limesurvey(SimpleNamespace(
        input=str(FIXTURE_LSS), split="group", list=False, select=["g30"], output=str(out),
        project=str(library), use_library=True, name=None))
    resp = _client().post(
        "/api/template-editor/import-limesurvey", content_type="multipart/form-data",
        data={"file": (FIXTURE_LSS.open("rb"), "s.lss"), "split": "group", "key": "g30",
              "project_path": str(studio_project), "use_library": "1"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert _tree(library) == _tree(studio_project) and "code/item_maps/ads.json" in _tree(library)
    assert json.loads((out / body["suggested_filename"]).read_text(encoding="utf-8")) == body["template"]


def test_the_use_library_route_without_a_project_is_a_400(library):
    resp = _client().post(
        "/api/template-editor/import-limesurvey", content_type="multipart/form-data",
        data={"file": (FIXTURE_LSS.open("rb"), "s.lss"), "split": "group", "key": "g30", "use_library": "1"})
    assert resp.status_code == 400 and "project item map" in resp.get_json()["error"]


def test_converting_with_the_imported_codes_works_after_the_import(library):
    from src import item_map

    finish_import(_template(), "ADS", str(library), use_library=True)
    assert item_map.item_alias_map(str(library)) == {"ADS1_1": "ads_01", "ADS1_2": "ads_02"}


def _cli_import(project, out, select):
    from src.cli.commands.survey import cmd_survey_import_limesurvey

    cmd_survey_import_limesurvey(SimpleNamespace(
        input=str(FIXTURE_LSS), split="group", list=False, select=select, output=str(out),
        project=str(project), use_library=True, name=None))


def test_cli_failure_on_a_later_key_leaves_no_item_map(library, tmp_path):
    with pytest.raises(SystemExit):
        _cli_import(library, tmp_path / "out", ["g30", "g20"])  # g20 has no library match
    assert not (library / "code" / "item_maps").exists()
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").iterdir())


def test_cli_existing_target_leaves_no_item_map(library, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "survey-ads.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit):
        _cli_import(library, out, ["g30"])
    assert not (library / "code" / "item_maps").exists()


def test_cli_success_writes_the_maps_after_the_templates(library, tmp_path):
    _cli_import(library, tmp_path / "out", ["g30"])
    assert (tmp_path / "out" / "survey-ads.json").exists()
    assert (library / "code" / "item_maps" / "ads.json").exists()


def _seed(project, mapping):
    path = project / "code" / "item_maps" / "ads.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping), encoding="utf-8")
    return path


def test_an_existing_map_is_merged_not_replaced(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "_load_global_library_path", lambda: tmp_path)
    project = tmp_path / "p"
    library_file(project / "code" / "library" / "survey", texts=ADS, levels=ADS_LEVELS,
                 codes=["ads_01", "ads_02", "ads_03"][:2])
    path = _seed(project, {"ads_02": "OLD", "ads_01": "KEEP"})
    finish_import(_template(), "ADS", str(project), use_library=True)
    assert json.loads(path.read_text(encoding="utf-8")) == {"ads_02": "ADS1_2", "ads_01": "ADS1_1"}


def test_other_entries_of_an_existing_map_survive(library):
    path = _seed(library, {"ads_99": "X99"})
    # ads_99 is not an item of the template: the merged map is refused, not silently dropped
    with pytest.raises(ValueError, match="ads_99"):
        finish_import(_template(), "ADS", str(library), use_library=True)
    assert json.loads(path.read_text(encoding="utf-8")) == {"ads_99": "X99"}


def test_other_item_entries_survive_when_the_template_has_them(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "_load_global_library_path", lambda: tmp_path)
    project = tmp_path / "p"
    library_file(project / "code" / "library" / "survey", texts=ADS + ["war ich froh"],
                 levels=ADS_LEVELS, codes=["ads_01", "ads_02", "ads_03"])
    path = _seed(project, {"ads_03": "F3"})
    from src.converters.template_import import store_library_item_map
    payload = {"template": {"ads_01": {}, "ads_02": {}, "ads_03": {}},
               "item_map": None, "library_match": {"template_key": "ads", "source": "project"},
               "_item_map_pending": {"task": "ads", "mapping": {"ads_01": "A1"}}}
    store_library_item_map(payload, str(project))
    assert json.loads(path.read_text(encoding="utf-8")) == {"ads_03": "F3", "ads_01": "A1"}


def test_the_print_comes_after_the_write(library, capsys):
    finish_import(_template(), "ADS", str(library), use_library=True, store_map=False)
    assert "saved to the project item map" not in capsys.readouterr().out
    finish_import(_template(), "ADS", str(library), use_library=True)
    assert "2 item code(s) saved to the project item map" in capsys.readouterr().out


def test_studio_and_cli_merge_identically(library, tmp_path):
    _seed(library, {"ads_01": "OLD"})
    studio_project = tmp_path / "studio_project"
    shutil.copytree(library, studio_project)
    _cli_import(library, tmp_path / "out", ["g30"])
    resp = _client().post(
        "/api/template-editor/import-limesurvey", content_type="multipart/form-data",
        data={"file": (FIXTURE_LSS.open("rb"), "s.lss"), "split": "group", "key": "g30",
              "project_path": str(studio_project), "use_library": "1"})
    assert resp.status_code == 200
    assert _tree(library) == _tree(studio_project)


def test_cli_collision_with_an_existing_map_fails_in_planning(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "_load_global_library_path", lambda: tmp_path)
    project = tmp_path / "p"
    library_file(project / "code" / "library" / "survey", texts=ADS, levels=ADS_LEVELS, codes=["ADS1_1", "ads_02"])
    path = _seed(project, {"ADS1_1": "ADS1_2"})  # the column the new pair ads_02 -> ADS1_2 needs
    out = tmp_path / "out"
    with pytest.raises(SystemExit) as exc:
        _cli_import(project, out, ["g30"])
    assert exc.value.code == 1
    assert not out.exists() or not list(out.iterdir())
    assert json.loads(path.read_text(encoding="utf-8")) == {"ADS1_1": "ADS1_2"}


def test_the_saved_path_is_relative_to_the_project_when_given_project_json(library):
    from src.converters.template_import import store_library_item_map

    (library / "project.json").write_text("{}", encoding="utf-8")
    payload = finish_import(_template(), "ADS", str(library), use_library=True, store_map=False)
    assert store_library_item_map(payload, str(library / "project.json"))["path"] == "code/item_maps/ads.json"
