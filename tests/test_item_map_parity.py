"""`survey item-map` and Studio's /api/item-map write the same files and answer the same."""

import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src.cli.commands.survey import cmd_survey_item_map  # noqa: E402
from src.web.blueprints.item_map_blueprint import item_map_bp  # noqa: E402
from tests.template_fixtures import dump_complete  # noqa: E402

ITEMS = ["ADS01", "ADS02"]
TEMPLATE = {i: {"Description": {"en": i}, "Levels": {"1": "low", "2": "high"}} for i in ITEMS}


def _tree(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture
def setup(tmp_path):
    cli = tmp_path / "cli"
    library = cli / "code" / "library" / "survey"
    library.mkdir(parents=True)
    (library / "survey-ads.json").write_text(dump_complete(TEMPLATE, "ads"), encoding="utf-8")
    studio = tmp_path / "studio"
    shutil.copytree(cli, studio)
    data = tmp_path / "in.csv"
    data.write_text("participant_id,A01,A02\nsub-001,1,2\n", encoding="utf-8")
    app = Flask(__name__)
    app.register_blueprint(item_map_bp)
    return cli, studio, data, app.test_client()


def _post(http, url, data, studio, **form):
    with open(data, "rb") as fh:
        return http.post(url, data={"file": (fh, data.name), "project_path": str(studio), **form},
                         content_type="multipart/form-data")


def _cli(cli, data, **kw):
    args = dict(input=str(data), project=str(cli), task=None, accept=False, set=None)
    cmd_survey_item_map(SimpleNamespace(**{**args, **kw}))


def test_saving_a_map_writes_the_same_files(setup):
    cli, studio, data, http = setup
    _cli(cli, data, task="ads", accept=True, set=["ADS02=A01", "ADS01=A02"])
    resp = _post(http, "/api/item-map", data, studio, task="ads", accept="1",
                 choices=json.dumps({"ADS02": "A01", "ADS01": "A02"}))
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True, "path": "code/item_maps/ads.json"}
    assert _tree(cli) == _tree(studio)
    assert "code/item_maps/ads.json" in _tree(studio)


def test_suggest_returns_the_rows_the_cli_prints(setup, capsys):
    cli, studio, data, http = setup
    _cli(cli, data, task="ads")
    out = capsys.readouterr().out
    body = _post(http, "/api/item-map/suggest", data, studio, task="ads").get_json()
    for r in body["rows"]:
        assert f"{r['item']} <- {r['column']}  ({r['why']})" in out
    assert body["columns"] == ["participant_id", "A01", "A02"]
    assert _tree(cli) == _tree(studio)


def test_suggest_without_task_lists_the_tasks(setup):
    _, studio, data, http = setup
    assert _post(http, "/api/item-map/suggest", data, studio).get_json() == {"tasks": ["ads"]}


def test_an_invalid_task_is_400_and_writes_nothing(setup):
    cli, studio, data, http = setup
    before = _tree(studio)
    resp = _post(http, "/api/item-map", data, studio, task="nope", accept="1")
    assert resp.status_code == 400 and "error" in resp.get_json()
    assert _tree(studio) == before


def test_no_project_is_400(setup, tmp_path):
    _, _, data, http = setup
    resp = _post(http, "/api/item-map/suggest", data, tmp_path / "missing")
    assert resp.status_code == 400 and resp.get_json() == {"error": "No project selected"}


def test_a_corrupt_xlsx_is_an_error_in_both(setup, capsys):
    cli, studio, _, http = setup
    bad = cli.parent / "bad.xlsx"
    bad.write_text("not a zip", encoding="utf-8")
    with pytest.raises(SystemExit):
        _cli(cli, bad)
    assert "bad.xlsx" in capsys.readouterr().out
    resp = _post(http, "/api/item-map/suggest", bad, studio)
    assert resp.status_code == 400 and "bad.xlsx" in resp.get_json()["error"]


def test_an_unexpected_reader_error_becomes_an_item_map_error(tmp_path, monkeypatch):
    import zipfile

    from src import item_map
    import src.converters.survey as survey

    def boom(**_):
        raise zipfile.BadZipFile("File is not a zip file")

    monkeypatch.setattr(survey, "_read_table_as_dataframe", boom)
    with pytest.raises(item_map.ItemMapError, match="Cannot read x.xlsx"):
        item_map.read_survey_columns(tmp_path / "x.xlsx")
