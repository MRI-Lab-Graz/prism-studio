"""Git runs hooks with sh; a CRLF shebang/`exit 0\r` breaks them on Windows."""

import subprocess

import src.save_gate as sg
import src.share_publish as sp


def _init(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def test_save_gate_hook_is_written_with_lf_only(tmp_path):
    hook = sg.install_save_hook(_init(tmp_path))
    assert b"\r" not in hook.read_bytes()


def test_publish_hook_is_written_with_lf_only(tmp_path):
    hook = sp.install_hook(_init(tmp_path), "ria-store")
    assert b"\r" not in hook.read_bytes()
