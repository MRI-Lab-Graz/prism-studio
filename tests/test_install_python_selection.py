"""install.sh must prefer an installed Python 3.10-3.12 over a uv-managed one.

uv-managed Python cannot build a copied venv on some macOS setups (ensurepip
aborts), so install.sh falls back to a symlinked venv.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _fake(path, body):
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(0o755)


def test_prefers_installed_python312_over_uv(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    too_new = tmp_path / "python3"
    _fake(too_new, "exit 1\n")  # stands in for an unsupported default python3
    _fake(bin_dir / "python3.12", 'echo 3.12.0\n')
    _fake(bin_dir / "uv", 'echo "/uv/python3.12"\n')

    script = f"""
echo_info() {{ :; }}; echo_success() {{ :; }}; echo_error() {{ :; }}
{subprocess.run(["sed", "-n", "/^ensure_min_python_version()/,/^}/p", "install.sh"],
                cwd=ROOT, capture_output=True, text=True).stdout}
VENV_CREATOR_PYTHON=""
ensure_min_python_version "{too_new}" >/dev/null
echo "$VENV_CREATOR_PYTHON"
"""
    out = subprocess.run(
        ["bash", "-c", script],
        env={"PATH": f"{bin_dir}:/usr/bin:/bin"},
        capture_output=True, text=True,
    )
    assert out.stdout.strip() == str(bin_dir / "python3.12"), out.stderr


def _run_reset_existing_venv(venv_dir):
    funcs = subprocess.run(
        ["sed", "-n", "/^is_python_executable_usable()/,/^}/p;/^reset_unusable_venv()/,/^}/p", "install.sh"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout
    script = f"""
echo_info() {{ :; }}
{funcs}
VENV_DIR="{venv_dir}"
VENV_PYTHON_UNIX="$VENV_DIR/bin/python"
reset_unusable_venv
"""
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True)


def test_working_symlinked_venv_is_reused(tmp_path):
    """The symlinked fallback venv is valid; rerunning install.sh must keep it."""
    venv = tmp_path / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "activate").write_text("")
    real = tmp_path / "real-python"
    _fake(real, "exit 0\n")
    (venv / "bin" / "python").symlink_to(real)

    out = _run_reset_existing_venv(venv)

    assert out.returncode == 0, out.stderr
    assert venv.is_dir()


def test_broken_symlinked_venv_is_removed(tmp_path):
    """A venv whose interpreter link points nowhere (e.g. uv removed that Python)."""
    venv = tmp_path / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "activate").write_text("")
    (venv / "bin" / "python").symlink_to(tmp_path / "gone")

    out = _run_reset_existing_venv(venv)

    assert out.returncode == 0, out.stderr
    assert not venv.exists()


def test_symlinked_python_is_resolved_to_its_real_path(tmp_path):
    """A venv made through a symlink (e.g. uv's ~/.local/bin/python3.12 shim)
    records the symlink's directory as `home` and cannot find its stdlib."""
    bin_dir = tmp_path / "bin"
    real_dir = tmp_path / "uv" / "bin"
    bin_dir.mkdir()
    real_dir.mkdir(parents=True)
    too_new = tmp_path / "python3"
    _fake(too_new, "exit 1\n")
    real = real_dir / "python3.12"
    _fake(real, 'echo 3.12.0\n')
    (bin_dir / "python3.12").symlink_to(real)

    script = f"""
echo_info() {{ :; }}; echo_success() {{ :; }}; echo_error() {{ :; }}
{subprocess.run(["sed", "-n", "/^ensure_min_python_version()/,/^}/p", "install.sh"],
                cwd=ROOT, capture_output=True, text=True).stdout}
VENV_CREATOR_PYTHON=""
ensure_min_python_version "{too_new}" >/dev/null
echo "$VENV_CREATOR_PYTHON"
"""
    out = subprocess.run(
        ["bash", "-c", script],
        env={"PATH": f"{bin_dir}:/usr/bin:/bin"},
        capture_output=True, text=True,
    )
    assert out.stdout.strip() == str(real), out.stderr
