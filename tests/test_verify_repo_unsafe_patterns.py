import importlib.util
from pathlib import Path


def _load_verify_repo_module():
    module_path = Path(__file__).with_name("verify_repo.py")
    spec = importlib.util.spec_from_file_location("verify_repo", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_unsafe_patterns_allows_ci_local_http_probe_templates(
    tmp_path: Path, capsys
) -> None:
    verify_repo = _load_verify_repo_module()

    script_path = tmp_path / "scripts" / "ci" / "smoke_packaged_web_app.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(
        "\n".join(
            [
                'probe_url = f"http://{host}:{port}{probe_path}"',
                'msg = f"Timed out waiting for packaged app to answer on http://{host}:{port}."',
                'shutdown_url = f"http://{host}:{port}/shutdown"',
                'ok = f"[OK] Packaged app served HTTP probes successfully on http://{host}:{port}"',
            ]
        ),
        encoding="utf-8",
    )

    verify_repo.check_unsafe_patterns(str(tmp_path))
    output = capsys.readouterr().out

    assert "Potential unsafe pattern" not in output


def test_unsafe_patterns_still_flags_external_http(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    src_file = tmp_path / "src" / "insecure_url.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text('url = "http://example.com/api"\n', encoding="utf-8")

    verify_repo.check_unsafe_patterns(str(tmp_path))
    output = capsys.readouterr().out

    assert "Potential unsafe pattern" in output
    assert "src/insecure_url.py" in output
