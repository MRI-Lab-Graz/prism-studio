"""The guard that keeps a project with sourcedata/ off public hosts must not be bypassed by spelling tricks."""

import pytest

from src.share_publish import _is_public_target


@pytest.mark.parametrize("url", [
    "https://github.com/org/repo", "git@github.com:org/repo.git", "ssh://git@gitlab.com/x/y", "ria+ssh://git@github.com/x",
    "ssh://git@GITHUB.COM/x", "ssh://git@github.com:22/x",
    "ssh://git@github.com./x",       # trailing dot is the same host
    "git@github.com.:org/r",
    "git+ssh://git@github.com/x",    # scheme prefix used by pip/git tooling
    "  ssh://git@github.com/x  ",
])
def test_public_hosts_are_recognised_however_they_are_spelled(url):
    assert _is_public_target(url)


@pytest.mark.parametrize("url", ["ssh://user@10.0.0.5/data/ds", "/mnt/share/ds", "file:///mnt/share/ds", "ria+file:///x", "", "git@gitlab.uni-graz.at:lab/ds.git"])
def test_the_lab_server_and_local_paths_are_not_public(url):
    assert not _is_public_target(url)
