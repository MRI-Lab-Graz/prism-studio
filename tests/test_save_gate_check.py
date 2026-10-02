import subprocess

import pytest

import src.save_gate as sg


def git(*args, cwd):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.t", *args],
                   cwd=cwd, check=True, capture_output=True)


def repo(path, commits):
    path.mkdir(parents=True, exist_ok=True)
    git("init", "-q", cwd=path)
    for i in range(commits):
        (path / f"f{i}").write_text(str(i))
        git("add", ".", cwd=path)
        git("commit", "-q", "-m", f"c{i}", cwd=path)
    return path


@pytest.fixture
def calls(monkeypatch):
    seen = {"full": 0, "subject": []}

    def full(root):
        seen["full"] += 1
        return seen.get("full_result", [])

    def subject(root, sid):
        seen["subject"].append((str(root), sid))
        return seen.get("subject_result", [])

    monkeypatch.setattr(sg, "validate_for_publish", full)
    monkeypatch.setattr(sg, "validate_subject_for_save", subject)
    return seen


def test_first_save_of_a_top_level_dataset_is_exempt(tmp_path, calls):
    result = sg.check_save(repo(tmp_path / "p", commits=1))
    assert result.allowed and result.reason == "exempt_initial" and calls["full"] == 0


def test_empty_repo_first_save_is_exempt(tmp_path, calls):
    result = sg.check_save(repo(tmp_path / "p", commits=0))
    assert result.allowed and result.reason == "exempt_initial"


def test_later_saves_are_gated_and_refused_on_errors(tmp_path, calls):
    calls["full_result"] = ["PRISM101 bad"]
    result = sg.check_save(repo(tmp_path / "p", commits=2))
    assert not result.allowed and result.reason == "validation_errors"
    assert result.errors == ["PRISM101 bad"]


def test_later_save_allowed_when_valid(tmp_path, calls):
    result = sg.check_save(repo(tmp_path / "p", commits=2))
    assert result.allowed and result.reason == "valid"


def test_validator_crash_is_refused(tmp_path, monkeypatch):
    def boom(root):
        raise RuntimeError("kaput")

    monkeypatch.setattr(sg, "validate_for_publish", boom)
    result = sg.check_save(repo(tmp_path / "p", commits=2))
    assert not result.allowed and result.reason == "validator_crash"
    assert "kaput" in result.errors[0]


def make_super_with_subject(tmp_path):
    sub_src = repo(tmp_path / "sub-src", commits=1)
    sup = repo(tmp_path / "proj", commits=1)
    subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "-c", "user.name=t", "-c", "user.email=t@t.t",
         "submodule", "add", "-q", str(sub_src), "sub-001"],
        cwd=sup, check=True, capture_output=True,
    )
    git("commit", "-q", "-m", "add sub", cwd=sup)
    return sup, sup / "sub-001"


def test_nested_subject_is_validated_alone_and_never_exempt(tmp_path, calls):
    sup, sub = make_super_with_subject(tmp_path)
    assert sg._commit_count(sub) == 1  # would be exempt if it were top-level
    calls["subject_result"] = ["PRISM201 empty dir"]
    result = sg.check_save(sub)
    assert not result.allowed and result.errors == ["PRISM201 empty dir"]
    assert calls["full"] == 0  # no full-project validation for a nested commit
    assert calls["subject"] == [(str(sup.resolve()), "sub-001")] or calls["subject"][0][1] == "sub-001"


def test_non_subject_submodule_is_validated_as_a_whole(tmp_path, calls):
    sub_src = repo(tmp_path / "x-src", commits=2)
    sup = repo(tmp_path / "proj", commits=1)
    subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "-c", "user.name=t", "-c", "user.email=t@t.t",
         "submodule", "add", "-q", str(sub_src), "derivatives"],
        cwd=sup, check=True, capture_output=True,
    )
    sg.check_save(sup / "derivatives")
    assert calls["full"] == 1 and calls["subject"] == []
