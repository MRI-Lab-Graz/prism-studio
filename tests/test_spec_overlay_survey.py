import json
import os

import pytest

from src.spec_overlay import OverlayError, load_local_survey, remove_local_survey, write_local_survey

H1, H2, H3 = "a" * 64, "b" * 64, "c" * 64


def fp(lang="en", wording=H1, task="phq", items=("Q1",)):
    return {"Version": 1, "Task": task,
            "Items": {k: {"Wording": {lang: wording}, "Scales": [H2]} for k in items}}


def _folder(root):
    d = root / "code" / "specification" / "survey"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_write_then_load_round_trip(tmp_path):
    path = write_local_survey(tmp_path, fp())
    assert path == tmp_path / "code" / "specification" / "survey" / "phq.json"
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert load_local_survey(tmp_path) == ({"phq": fp()}, [])


def test_load_without_a_folder_is_empty(tmp_path):
    assert load_local_survey(tmp_path) == ({}, [])


def test_load_skips_and_reports_invalid_files(tmp_path):
    d = _folder(tmp_path)
    (d / "list.json").write_text("[]", encoding="utf-8")
    (d / "ver.json").write_text(json.dumps({**fp(task="ver"), "Version": 2}), encoding="utf-8")
    (d / "hash.json").write_text(json.dumps(fp(task="hash", wording="xyz")), encoding="utf-8")
    (d / "stem.json").write_text(json.dumps(fp(task="other")), encoding="utf-8")
    (d / "broken.json").write_text("{nope", encoding="utf-8")
    (d / "deep.json").write_text("[" * 100000, encoding="utf-8")
    (d / "good.json").write_text(json.dumps(fp(task="good")), encoding="utf-8")
    found, problems = load_local_survey(tmp_path)
    assert list(found) == ["good"]
    assert len(problems) == 6
    assert all(name in " ".join(problems) for name in ("list", "ver", "hash", "stem", "broken", "deep"))


def test_second_language_merges_into_the_same_file(tmp_path):
    write_local_survey(tmp_path, fp("en", H1))
    write_local_survey(tmp_path, fp("de", H3, items=("Q1", "Q2")))
    data = load_local_survey(tmp_path)[0]["phq"]
    assert data["Items"]["Q1"]["Wording"] == {"en": H1, "de": H3}
    assert data["Items"]["Q2"]["Wording"] == {"de": H3}
    assert data["Items"]["Q1"]["Scales"] == [H2]


def test_same_language_twice_is_refused_and_nothing_changes(tmp_path):
    path = write_local_survey(tmp_path, fp("en", H1))
    before = path.read_text(encoding="utf-8")
    with pytest.raises(OverlayError, match="phq.json"):
        write_local_survey(tmp_path, fp("en", H3, items=("Q1", "Q2")))
    assert path.read_text(encoding="utf-8") == before


@pytest.mark.skipif(os.name == "nt", reason="symbolic links need extra rights on Windows")
def test_symlinked_specification_folder_is_refused(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "survey").mkdir(parents=True)
    (elsewhere / "survey" / "phq.json").write_text(json.dumps(fp()), encoding="utf-8")
    project = tmp_path / "p"
    (project / "code").mkdir(parents=True)
    (project / "code" / "specification").symlink_to(elsewhere)
    with pytest.raises(OverlayError, match="symbolic link"):
        write_local_survey(project, fp(task="new"))
    with pytest.raises(OverlayError, match="symbolic link"):
        remove_local_survey(project, "phq")
    assert [p.name for p in (elsewhere / "survey").iterdir()] == ["phq.json"]


def test_remove_deletes_only_that_task(tmp_path):
    write_local_survey(tmp_path, fp(task="phq"))
    write_local_survey(tmp_path, fp(task="gad"))
    remove_local_survey(tmp_path, "phq")
    assert list(load_local_survey(tmp_path)[0]) == ["gad"]
    with pytest.raises(OverlayError):
        remove_local_survey(tmp_path, "phq")


def test_task_names_with_a_segment_are_refused(tmp_path):
    with pytest.raises(OverlayError):
        write_local_survey(tmp_path, fp(task="ads.x"))
    with pytest.raises(OverlayError):
        remove_local_survey(tmp_path, "ads.x")
    d = _folder(tmp_path)
    (d / "ads.x.json").write_text(json.dumps(fp(task="ads.x")), encoding="utf-8")
    found, problems = load_local_survey(tmp_path)
    assert found == {} and "ads.x" in " ".join(problems)


@pytest.mark.parametrize("version", [True, 1.0])
def test_version_must_be_the_integer_one(tmp_path, version):
    (_folder(tmp_path) / "v.json").write_text(json.dumps({**fp(task="v"), "Version": version}), encoding="utf-8")
    found, problems = load_local_survey(tmp_path)
    assert found == {} and "v.json" in " ".join(problems)


def test_load_skips_symlinked_files(tmp_path):
    d = _folder(tmp_path)
    real = tmp_path / "real.json"
    real.write_text(json.dumps(fp(task="link")), encoding="utf-8")
    try:
        (d / "link.json").symlink_to(real)
    except OSError:
        pytest.skip("symlinks not available")
    found, problems = load_local_survey(tmp_path)
    assert found == {} and "link.json" in " ".join(problems) and "symbolic link" in " ".join(problems)
