"""install.sh must get uv onto a bare machine itself (after asking), not just
print a curl command and exit: users may have nothing relevant installed."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A stand-in for astral's installer: drops a working `uv` into ~/.local/bin.
FAKE_INSTALLER = 'mkdir -p "$HOME/.local/bin"; printf "#!/bin/sh\\n" > "$HOME/.local/bin/uv"; chmod +x "$HOME/.local/bin/uv"'


def _fake(path, body):
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(0o755)


def _run_ensure_uv(tmp_path, answer, downloader=None):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    if downloader:
        _fake(bin_dir / downloader, f"echo \"$@\" >> {tmp_path}/fetched\necho '{FAKE_INSTALLER}'\n")
    funcs = subprocess.run(
        ["sed", "-n", "/^fetch_url()/,/^}/p;/^ensure_uv()/,/^}/p", "install.sh"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout
    script = f"""
echo_info() {{ echo "$1"; }}; echo_success() {{ :; }}; echo_error() {{ echo "$1"; }}
{funcs}
ensure_uv && command -v uv
"""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    # /bin only: no real curl/wget/uv (those live in /usr/bin or elsewhere)
    return subprocess.run(
        ["bash", "-c", script], input=answer,
        env={"PATH": f"{bin_dir}:/bin", "HOME": str(home)},
        capture_output=True, text=True,
    )


def test_installs_uv_with_curl_when_user_agrees(tmp_path):
    out = _run_ensure_uv(tmp_path, "y\n", downloader="curl")
    assert out.returncode == 0, out.stdout + out.stderr
    assert out.stdout.strip().endswith("/home/.local/bin/uv")
    assert "astral.sh/uv/install.sh" in (tmp_path / "fetched").read_text()


def test_falls_back_to_wget_without_curl(tmp_path):
    out = _run_ensure_uv(tmp_path, "y\n", downloader="wget")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "astral.sh/uv/install.sh" in (tmp_path / "fetched").read_text()


def test_declining_explains_manual_install(tmp_path):
    out = _run_ensure_uv(tmp_path, "n\n", downloader="curl")
    assert out.returncode != 0
    assert not (tmp_path / "fetched").exists()
    assert "docs.astral.sh/uv" in out.stdout


def test_no_downloader_explains_manual_install(tmp_path):
    out = _run_ensure_uv(tmp_path, "y\n")
    assert out.returncode != 0
    assert "docs.astral.sh/uv" in out.stdout


def test_uv_in_local_bin_but_not_on_path_is_found_without_asking(tmp_path):
    home = tmp_path / "home"
    (home / ".local" / "bin").mkdir(parents=True)
    _fake(home / ".local" / "bin" / "uv", "")
    out = _run_ensure_uv(tmp_path, "")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "Install uv" not in out.stdout
