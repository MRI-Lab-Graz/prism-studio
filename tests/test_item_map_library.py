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
