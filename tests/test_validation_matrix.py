"""The validator against injected defects: every defect is caught with its catalogue code, or is a known gap."""

import pytest

from src.validation_matrix import ANY, DEFECTS, NONE, KNOWN_GAPS, build_clean_project, classify, matrix_problems, run_matrix


def test_classify():
    assert classify("PRISM201", ["PRISM201", "PRISM708"]) == "detected"
    assert classify("PRISM201", ["PRISM301"]) == "wrong_code"
    assert classify("PRISM201", []) == "missed"
    assert classify(ANY, ["PRISM999"]) == "detected" and classify(ANY, []) == "missed"
    assert classify(NONE, []) == "detected" and classify(NONE, ["PRISM402"]) == "false_positive"


def test_defects_are_unique_and_expect_codes_of_the_catalogue():
    from src.issues import ERROR_CODES

    ids = [d.id for d in DEFECTS]
    assert len(ids) == len(set(ids))
    assert {d.expect for d in DEFECTS} - {ANY, NONE} <= set(ERROR_CODES)
    assert set(KNOWN_GAPS) <= set(ids)


@pytest.fixture(scope="module")
def matrix(tmp_path_factory):
    root = tmp_path_factory.mktemp("matrix") / "clean"
    build_clean_project(root)
    return run_matrix(root)


def test_control_is_clean_and_every_defect_is_detected_or_a_documented_gap(matrix):
    assert matrix_problems(matrix) == []


def test_data_problems_are_never_reported_as_internal_errors(matrix):
    assert not [r["id"] for r in matrix["rows"] if "PRISM901" in r["got"]]
