import os

from src.cross_platform import ensure_user_bin_on_path


def test_adds_local_bin_when_present(tmp_path, monkeypatch):
    (tmp_path / ".local" / "bin").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("PATH", "/usr/bin")
    ensure_user_bin_on_path()
    assert os.environ["PATH"].split(os.pathsep)[-1] == str(tmp_path / ".local" / "bin")


def test_noop_when_missing_or_already_on_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("PATH", "/usr/bin")
    ensure_user_bin_on_path()
    assert os.environ["PATH"] == "/usr/bin"
    (tmp_path / ".local" / "bin").mkdir(parents=True)
    p = str(tmp_path / ".local" / "bin")
    monkeypatch.setenv("PATH", p)
    ensure_user_bin_on_path()
    assert os.environ["PATH"] == p
