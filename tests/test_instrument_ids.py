"""A stub must map to a known PRISM ID: prism:<TaskName> and prism:<TaskName>.<item>, read from the official
library only (docs/specs/instrument-ids.md). A project-only template is a local: instrument, not a prism: one."""

from src.instrument_ids import stub_id_problems

FP = {"en": "sha256:" + "0" * 64}


def _stub(task, items, fingerprint=FP):
    return {"Study": {"TaskName": task, "ItemTextsIncluded": False},
            **{k: {"Description": None, "Fingerprint": fingerprint} for k in items}}


def test_stub_matching_official_library_has_no_problems():
    assert stub_id_problems(_stub("dass", ["dass01", "dass02"])) == []


def test_unknown_instrument_id():
    problems = stub_id_problems(_stub("nosuchtest", ["a01"]))
    assert len(problems) == 1 and "prism:nosuchtest" in problems[0]


def test_item_not_in_official_template():
    problems = stub_id_problems(_stub("dass", ["dass01", "dass999"]))
    assert len(problems) == 1 and "prism:dass.dass999" in problems[0]


def test_item_without_fingerprint():
    problems = stub_id_problems(_stub("dass", ["dass01"], fingerprint=None))
    assert len(problems) == 1 and "dass01" in problems[0] and "Fingerprint" in problems[0]


def test_task_name_and_item_case_do_not_matter():
    assert stub_id_problems(_stub("DASS", ["DASS01"])) == []
