"""Sibling names and aliases become git remote names and folders in the store: plain labels only."""

import pytest

from src.datalad_execution import run_datalad_create_sibling_plain, sibling_label_problem


@pytest.mark.parametrize("label", ["server", "lab-server", "lab_server.2", "A1"])
def test_plain_labels_are_fine(label):
    assert sibling_label_problem(label, "sibling name") == ""


@pytest.mark.parametrize("label", ["-x", "--alias", "a b", "../../evil", "a/b", "a\\b", "a;b", "$(x)", "a\nb", "ünï", ".hidden", "x" * 65])
def test_other_labels_are_refused_with_a_reason(label):
    assert "sibling name" in sibling_label_problem(label, "sibling name")


def test_create_function_refuses_before_running_anything(tmp_path):
    for call in (
        lambda **kw: run_datalad_create_sibling_plain(tmp_path, remote_url="ssh://host/path", sibling_name="-x", **kw),
        lambda **kw: run_datalad_create_sibling_plain(tmp_path, remote_url="ssh://host/path", sibling_name="a;b", **kw),
    ):
        result = call(datalad_executable="/bin/echo")
        assert not result["attempted"] and not result["success"] and "plain" in result["message"]
