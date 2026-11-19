"""Project links are untrusted data: a link in the project's spec folder must never lead outside the project."""

import json

import pytest

from src.mappings_check import check_links
from src.spec_overlay import OverlayError, write_local_links


def test_check_links_does_not_read_through_a_symlinked_specification_folder(tmp_path):
    outside = tmp_path / "outside" / "mappings" / "biosample"
    outside.mkdir(parents=True)
    (outside / "x.json").write_text(json.dumps({"prism:nothing": {"SameAs": {"loinc": "https://loinc.org/1-1"}}}))
    project = tmp_path / "study"
    (project / "code").mkdir(parents=True)
    (project / "code" / "specification").symlink_to(tmp_path / "outside")
    with pytest.raises(OverlayError, match="symbolic link"):
        check_links(project=project)


@pytest.mark.parametrize("bad", ["prism:a/b", "prism:../x", "prism:", "other:abc"])
def test_write_local_links_refuses_an_id_that_is_not_a_local_id(tmp_path, bad):
    with pytest.raises(OverlayError):
        write_local_links(tmp_path, "biosample", {bad: {"loinc": "https://loinc.org/1-1"}})
    assert not (tmp_path / "code").exists()
