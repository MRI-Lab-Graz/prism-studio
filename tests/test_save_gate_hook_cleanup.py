"""Projects that ran the old `prism_tools publish --install-hook` carry a pre-push hook that calls the removed
`publish` command; it would block every push (also from Worldline Desktop). Installing the save gate removes it."""

import subprocess

import src.save_gate as sg

OLD_HOOK = "#!/bin/sh\n# prism-publish-hook\n# Blocks pushes to \"origin\" unless the dataset validates.\nexec prism_tools publish --check --project .\n"


def _repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def test_installing_the_save_gate_removes_the_old_publish_pre_push_hook(tmp_path):
    repo = _repo(tmp_path)
    old = repo / ".git" / "hooks" / "pre-push"
    old.write_text(OLD_HOOK, encoding="utf-8")

    sg.install_save_hook(repo)

    assert not old.exists()
    assert (repo / ".git" / "hooks" / "pre-commit").exists()


def test_a_foreign_pre_push_hook_is_left_alone(tmp_path):
    repo = _repo(tmp_path)
    foreign = repo / ".git" / "hooks" / "pre-push"
    foreign.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    sg.install_save_hook(repo)

    assert foreign.read_text(encoding="utf-8") == "#!/bin/sh\nexit 0\n"
