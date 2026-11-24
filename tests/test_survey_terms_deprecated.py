"""A survey ID can be deprecated (`deprecated.json` next to term-ids.txt): marked in the registry, allowed to leave the template."""

import json

from src.survey_terms import build_survey_registry, deprecated_ids, freeze_report
from test_survey_terms import TIPI, _lib


def _with(tmp_path, deprecated, released=("prism:tipi", "prism:tipi.tipi01", "prism:tipi.tipi02")):
    lib, rec = _lib(tmp_path, {"tipi": TIPI})
    (lib / "term-ids.txt").write_text("".join(f"{i}\n" for i in released), encoding="utf-8")
    if deprecated is not None:
        (lib / "deprecated.json").write_text(json.dumps(deprecated), encoding="utf-8")
    return lib, rec


def test_a_deprecated_item_is_marked_with_its_replacement(tmp_path):
    reg, problems = build_survey_registry(*_with(tmp_path, {"prism:tipi.tipi01": {"ReplacedBy": "prism:tipi.tipi02"}}))
    assert problems == []
    assert reg["tipi.tipi01"]["Status"] == "deprecated" and reg["tipi.tipi01"]["ReplacedBy"] == "prism:tipi.tipi02"
    assert reg["tipi.tipi02"]["Status"] == "official" and "ReplacedBy" not in reg["tipi.tipi02"]


def test_a_replacement_that_was_never_released_is_a_problem(tmp_path):
    reg, problems = build_survey_registry(*_with(tmp_path, {"prism:tipi.tipi01": {"ReplacedBy": "prism:tipi.nope"}}))
    assert problems == ["deprecated.json: prism:tipi.tipi01 is replaced by prism:tipi.nope, which is not a released ID"]


def test_an_entry_without_a_replacement_is_skipped_and_reported(tmp_path):
    reg, problems = build_survey_registry(*_with(tmp_path, {"prism:tipi.tipi01": {}, "prism:tipi.tipi02": "x"}))
    assert len(problems) == 2 and all("needs a ReplacedBy" in p for p in problems)
    assert reg["tipi.tipi01"]["Status"] == "official"


def test_without_the_file_nothing_is_deprecated(tmp_path):
    reg, problems = build_survey_registry(*_with(tmp_path, None))
    assert problems == [] and all(t["Status"] == "official" for t in reg.values())
    assert deprecated_ids(tmp_path / "library" / "deprecated.json") == ({}, [])


def test_a_broken_file_is_a_problem_not_a_crash(tmp_path):
    lib, rec = _with(tmp_path, None)
    (lib / "deprecated.json").write_text("[1]", encoding="utf-8")
    _, problems = build_survey_registry(lib, rec)
    assert problems == ["deprecated.json: must hold a JSON object"]


def test_a_deprecated_released_id_may_leave_the_registry(tmp_path):
    reg, _ = build_survey_registry(*_lib(tmp_path, {"tipi": TIPI}))
    released = {"prism:tipi", "prism:tipi.tipi01", "prism:tipi.old"}
    assert freeze_report(reg, released)[0]  # gone: a problem
    assert freeze_report(reg, released, deprecated={"prism:tipi.old"})[0] == []
