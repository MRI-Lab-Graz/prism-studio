"""prism datalad doctor: tool checks, SSH key check, server reachability."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.datalad_doctor import classify_ssh_error, parse_ssh_target, run_doctor  # noqa: E402


@pytest.mark.parametrize(
    "url, expected",
    [
        ("ria+ssh://kalle@server.uni.at/data/store", ("kalle", "server.uni.at", None)),
        ("ssh://kalle@server.uni.at:2222/data", ("kalle", "server.uni.at", 2222)),
        ("kalle@server.uni.at:/data/x", ("kalle", "server.uni.at", None)),
        ("ssh://server.uni.at/data", (None, "server.uni.at", None)),
        ("ria+file:///local/store", None),
        ("https://github.com/x/y", None),
        ("", None),
    ],
)
def test_parse_ssh_target(url, expected):
    assert parse_ssh_target(url) == expected


@pytest.mark.parametrize(
    "stderr, code",
    [
        ("kalle@h: Permission denied (publickey).", "key_rejected"),
        ("Host key verification failed.", "host_key"),
        ("ssh: Could not resolve hostname h: Name or service not known", "unreachable"),
        ("ssh: connect to host h port 22: Connection timed out", "unreachable"),
        ("ssh: connect to host h port 22: Connection refused", "unreachable"),
        ("something odd", "unknown"),
    ],
)
def test_classify_ssh_error(stderr, code):
    assert classify_ssh_error(stderr)[0] == code


def _by_name(results):
    return {r["name"]: r for r in results}


def _env(tmp_path, tools=("git", "git-annex", "datalad", "ssh"), key=True):
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    if key:
        (ssh_dir / "id_ed25519").write_text("PRIVATE")
        (ssh_dir / "id_ed25519.pub").write_text("ssh-ed25519 AAAA kalle@laptop")
    which = lambda name: f"/bin/{name}" if name in tools else None  # noqa: E731
    return which, ssh_dir


def _run_ok(cmd):
    return 0, "git version 2.45"


def test_all_ok_without_url_skips_server_check(tmp_path):
    which, ssh_dir = _env(tmp_path)
    res = _by_name(run_doctor(None, which=which, run=_run_ok, ssh_dir=ssh_dir))
    assert all(res[n]["ok"] for n in ("git", "git-annex", "datalad", "ssh", "ssh-key"))
    assert "server" not in res


def test_missing_tool_fails_with_fix(tmp_path):
    which, ssh_dir = _env(tmp_path, tools=("git", "ssh"))
    res = _by_name(run_doctor(None, which=which, run=_run_ok, ssh_dir=ssh_dir))
    assert res["git-annex"]["ok"] is False
    assert res["git-annex"]["fix"]
    assert res["datalad"]["ok"] is False


def test_no_key_fails_and_points_to_the_it_admin(tmp_path):
    which, ssh_dir = _env(tmp_path, key=False)
    res = _by_name(run_doctor(None, which=which, run=_run_ok, ssh_dir=ssh_dir))
    assert res["ssh-key"]["ok"] is False
    assert "IT" in res["ssh-key"]["fix"]
    assert "keygen" not in res["ssh-key"]["fix"]


def test_rejected_login_without_a_key_points_to_the_it_admin(tmp_path):
    which, ssh_dir = _env(tmp_path, key=False)

    def run(cmd):
        return (255, "Permission denied (publickey).") if "BatchMode=yes" in cmd else (0, "v1")

    res = _by_name(run_doctor("ssh://kalle@h/store", which=which, run=run, ssh_dir=ssh_dir))
    assert "IT" in res["server"]["fix"]
    assert "keygen" not in res["server"]["fix"]


def test_server_check_uses_batchmode_ssh_and_reports_ok(tmp_path):
    which, ssh_dir = _env(tmp_path)
    calls = []

    def run(cmd):
        calls.append(cmd)
        return 0, ""

    res = _by_name(
        run_doctor("ria+ssh://kalle@h.at:2222/store", which=which, run=run, ssh_dir=ssh_dir)
    )
    assert res["server"]["ok"] is True
    ssh_call = next(c for c in calls if "BatchMode=yes" in c)
    assert "kalle@h.at" in ssh_call
    assert ssh_call[ssh_call.index("-p") + 1] == "2222"


def test_server_rejecting_key_tells_user_to_send_public_key(tmp_path):
    which, ssh_dir = _env(tmp_path)

    def run(cmd):
        if cmd[0].endswith("ssh"):
            return 255, "kalle@h: Permission denied (publickey)."
        return 0, "v1"

    res = _by_name(run_doctor("ssh://kalle@h/store", which=which, run=run, ssh_dir=ssh_dir))
    assert res["server"]["ok"] is False
    assert "ssh-ed25519 AAAA kalle@laptop" in res["server"]["fix"]


def test_non_ssh_url_is_reported_not_crashed(tmp_path):
    which, ssh_dir = _env(tmp_path)
    res = _by_name(run_doctor("ria+file:///x", which=which, run=_run_ok, ssh_dir=ssh_dir))
    assert res["server"]["ok"] is True
    assert "local" in res["server"]["detail"].lower()
