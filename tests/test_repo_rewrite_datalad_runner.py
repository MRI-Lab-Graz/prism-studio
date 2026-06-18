from __future__ import annotations

import ast
import json
from types import SimpleNamespace

from src.repo_rewrite_datalad_runner import apply_entity_rewrite, apply_subject_rewrite


_JSON_LITERAL_NAMES = {"true", "false", "null"}


def _assert_run_command_script_is_valid_python(command: list[str]) -> None:
    """Fail loudly if the embedded `-c` script leaks JSON literals.

    Regression guard: the script used to be built with json.dumps(), which
    emits JSON literals (true/false/null) instead of Python ones
    (True/False/None). `true`/`false`/`null` are syntactically valid Python
    *names*, so ast.parse() alone won't catch this — it only blows up with a
    NameError once the subprocess actually runs. We walk the AST for any
    bare reference to those names instead.
    """
    if "-c" not in command:
        return
    script = command[command.index("-c") + 1]
    tree = ast.parse(script)
    leaked_names = sorted(
        {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id in _JSON_LITERAL_NAMES
        }
    )
    assert not leaked_names, (
        f"Script leaks JSON literal(s) {leaked_names} as Python names "
        f"(use repr(), not json.dumps(), to embed values): {script}"
    )


def test_apply_subject_rewrite_uses_datalad_run_when_project_is_tracked(
    tmp_path,
    monkeypatch,
):
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-1293167" / "ses-01" / "func"
    func_dir.mkdir(parents=True)
    (project_root / ".datalad").mkdir(parents=True)
    (func_dir / "sub-1293167_ses-01_task-rest_bold.nii.gz").write_bytes(b"nii")

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda command: "/usr/bin/datalad" if command == "datalad" else "",
    )

    seen_commands: list[list[str]] = []

    def _fake_subprocess_run(
        command,
        cwd=None,
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
        env=None,
    ):
        seen_commands.append([str(item) for item in command])
        if len(command) >= 2 and command[1] == "save":
            return SimpleNamespace(returncode=0, stdout="save ok", stderr="")
        if len(command) >= 2 and command[1] == "get":
            return SimpleNamespace(returncode=0, stdout="get ok", stderr="")
        if len(command) >= 2 and command[1] == "run":
            _assert_run_command_script_is_valid_python(command)
            payload = {
                "applied": True,
                "mapping_count": 1,
                "directory_rename_count": 1,
                "file_rename_count": 1,
                "text_update_count": 0,
                "conflicts": [],
            }
            return SimpleNamespace(
                returncode=0,
                stdout=f"datalad run log\n{json.dumps(payload)}\n",
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        _fake_subprocess_run,
    )

    result = apply_subject_rewrite(
        project_root,
        mode="last3",
        example_subject=None,
        keep_fragment=None,
        allow_many_to_one=False,
    )

    assert result.get("applied") is True
    assert result.get("datalad", {}).get("used_run") is True
    assert any(command[0:2] == ["/usr/bin/datalad", "get"] for command in seen_commands)
    assert any(command[0:2] == ["/usr/bin/datalad", "run"] for command in seen_commands)


def test_apply_subject_rewrite_unlocks_and_fetches_content_for_text_files(
    tmp_path,
    monkeypatch,
):
    """Files whose *content* gets rewritten (not renamed) must be fetched
    with full data and unlocked before the DataLad run — otherwise the
    in-place write inside the subprocess fails with PermissionError on a
    locked, read-only annexed symlink."""
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-1293167" / "ses-01" / "func"
    func_dir.mkdir(parents=True)
    (project_root / ".datalad").mkdir(parents=True)
    (func_dir / "sub-1293167_ses-01_task-rest_bold.nii.gz").write_bytes(b"nii")
    scans_path = project_root / "sub-1293167" / "ses-01" / "sub-1293167_ses-01_scans.tsv"
    scans_path.write_text("filename\nfunc/sub-1293167_ses-01_task-rest_bold.nii.gz\n")

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda command: "/usr/bin/datalad" if command == "datalad" else "",
    )

    seen_commands: list[list[str]] = []

    def _fake_subprocess_run(
        command,
        cwd=None,
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
        env=None,
    ):
        seen_commands.append([str(item) for item in command])
        if len(command) >= 2 and command[1] == "save":
            return SimpleNamespace(returncode=0, stdout="save ok", stderr="")
        if len(command) >= 2 and command[1] == "unlock":
            return SimpleNamespace(returncode=0, stdout="unlock ok", stderr="")
        if len(command) >= 2 and command[1] == "get":
            return SimpleNamespace(returncode=0, stdout="get ok", stderr="")
        if len(command) >= 2 and command[1] == "run":
            _assert_run_command_script_is_valid_python(command)
            payload = {
                "applied": True,
                "mapping_count": 1,
                "directory_rename_count": 1,
                "file_rename_count": 1,
                "text_update_count": 1,
                "conflicts": [],
            }
            return SimpleNamespace(
                returncode=0,
                stdout=f"datalad run log\n{json.dumps(payload)}\n",
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        _fake_subprocess_run,
    )

    result = apply_subject_rewrite(
        project_root,
        mode="last3",
        example_subject=None,
        keep_fragment=None,
        allow_many_to_one=False,
    )

    assert result.get("applied") is True
    scans_rel = scans_path.relative_to(project_root).as_posix()

    unlock_commands = [command for command in seen_commands if command[1] == "unlock"]
    assert unlock_commands, "Expected a `datalad unlock` call for the rewritten text file."
    assert any(scans_rel in command for command in unlock_commands)

    get_commands = [command for command in seen_commands if command[1] == "get"]
    full_content_get_commands = [command for command in get_commands if "-n" not in command]
    assert any(scans_rel in command for command in full_content_get_commands), (
        "Expected a full-content `datalad get` (no -n) for the rewritten text file."
    )


def test_apply_entity_rewrite_uses_datalad_run_when_project_is_tracked(
    tmp_path,
    monkeypatch,
):
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-006" / "ses-1" / "func"
    func_dir.mkdir(parents=True)
    (project_root / ".datalad").mkdir(parents=True)
    (func_dir / "sub-006_ses-1_task-A_run-01_bold.nii.gz").write_bytes(b"nii")

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda command: "/usr/bin/datalad" if command == "datalad" else "",
    )

    seen_commands: list[list[str]] = []

    def _fake_subprocess_run(
        command,
        cwd=None,
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
        env=None,
    ):
        seen_commands.append([str(item) for item in command])
        if len(command) >= 2 and command[1] == "save":
            return SimpleNamespace(returncode=0, stdout="save ok", stderr="")
        if len(command) >= 2 and command[1] == "get":
            return SimpleNamespace(returncode=0, stdout="get ok", stderr="")
        if len(command) >= 2 and command[1] == "run":
            _assert_run_command_script_is_valid_python(command)
            payload = {
                "applied": True,
                "rename_count": 1,
                "text_update_count": 0,
                "conflicts": [],
            }
            return SimpleNamespace(
                returncode=0,
                stdout=f"datalad run log\n{json.dumps(payload)}\n",
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        _fake_subprocess_run,
    )

    result = apply_entity_rewrite(
        project_root,
        modality="func",
        entity="_task",
        operation="rename",
        current_value=None,
        replacement="rest",
    )

    assert result.get("applied") is True
    assert result.get("datalad", {}).get("used_run") is True
    assert any(command[0:2] == ["/usr/bin/datalad", "get"] for command in seen_commands)
    assert any(command[0:2] == ["/usr/bin/datalad", "run"] for command in seen_commands)


def test_apply_subject_rewrite_runs_once_per_subject_group(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    (project_root / ".datalad").mkdir(parents=True)
    func_a = project_root / "sub-1293001" / "ses-01" / "func"
    func_b = project_root / "sub-1293002" / "ses-01" / "func"
    func_a.mkdir(parents=True)
    func_b.mkdir(parents=True)
    (func_a / "sub-1293001_ses-01_task-rest_bold.nii.gz").write_bytes(b"nii")
    (func_b / "sub-1293002_ses-01_task-rest_bold.nii.gz").write_bytes(b"nii")

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda command: "/usr/bin/datalad" if command == "datalad" else "",
    )

    seen_commands: list[list[str]] = []

    def _fake_subprocess_run(
        command,
        cwd=None,
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
        env=None,
    ):
        command_as_text = [str(item) for item in command]
        seen_commands.append(command_as_text)
        if len(command) >= 2 and command[1] == "save":
            return SimpleNamespace(returncode=0, stdout="save ok", stderr="")
        if len(command) >= 2 and command[1] == "get":
            return SimpleNamespace(returncode=0, stdout="get ok", stderr="")
        if len(command) >= 2 and command[1] == "run":
            _assert_run_command_script_is_valid_python(command)
            subject = "sub-1293001" if "sub-1293001" in " ".join(command_as_text) else "sub-1293002"
            payload = {
                "mode": "last3",
                "rule": None,
                "allow_many_to_one": False,
                "subjects": [subject],
                "applied": True,
                "mapping": {subject: f"sub-{subject[-3:]}"},
                "mapping_count": 1,
                "directory_rename_count": 1,
                "file_rename_count": 1,
                "text_update_count": 0,
                "directory_renames": [],
                "file_renames": [],
                "text_update_files": [],
                "conflicts": [],
            }
            return SimpleNamespace(
                returncode=0,
                stdout=f"datalad run log\n{json.dumps(payload)}\n",
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_subprocess_run)

    result = apply_subject_rewrite(
        project_root,
        mode="last3",
        example_subject=None,
        keep_fragment=None,
        allow_many_to_one=False,
    )

    assert result.get("applied") is True
    assert result.get("datalad", {}).get("run_per_subject") is True
    assert result.get("datalad", {}).get("run_count") == 2
    run_commands = [command for command in seen_commands if command[1] == "run"]
    assert len(run_commands) == 2


def test_apply_entity_rewrite_runs_once_per_subject_group(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    (project_root / ".datalad").mkdir(parents=True)
    func_a = project_root / "sub-006" / "ses-1" / "func"
    func_b = project_root / "sub-007" / "ses-1" / "func"
    func_a.mkdir(parents=True)
    func_b.mkdir(parents=True)
    (func_a / "sub-006_ses-1_task-A_run-01_bold.nii.gz").write_bytes(b"nii")
    (func_b / "sub-007_ses-1_task-A_run-01_bold.nii.gz").write_bytes(b"nii")

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda command: "/usr/bin/datalad" if command == "datalad" else "",
    )

    seen_commands: list[list[str]] = []

    def _fake_subprocess_run(
        command,
        cwd=None,
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
        env=None,
    ):
        command_as_text = [str(item) for item in command]
        seen_commands.append(command_as_text)
        if len(command) >= 2 and command[1] == "save":
            return SimpleNamespace(returncode=0, stdout="save ok", stderr="")
        if len(command) >= 2 and command[1] == "get":
            return SimpleNamespace(returncode=0, stdout="get ok", stderr="")
        if len(command) >= 2 and command[1] == "run":
            _assert_run_command_script_is_valid_python(command)
            subject = "sub-006" if "sub-006" in " ".join(command_as_text) else "sub-007"
            payload = {
                "modality": "func",
                "entity": "_task",
                "current_value": "A",
                "operation": "rename",
                "replacement": "rest",
                "available_modalities": ["func"],
                "available_entities": ["_task", "_run"],
                "subjects": [subject],
                "applied": True,
                "rename_count": 1,
                "text_update_count": 0,
                "renames": [
                    {
                        "from": f"{subject}/ses-1/func/{subject}_ses-1_task-A_run-01_bold.nii.gz",
                        "to": f"{subject}/ses-1/func/{subject}_ses-1_task-rest_run-01_bold.nii.gz",
                    }
                ],
                "text_update_files": [],
                "conflicts": [],
            }
            return SimpleNamespace(
                returncode=0,
                stdout=f"datalad run log\n{json.dumps(payload)}\n",
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_subprocess_run)

    result = apply_entity_rewrite(
        project_root,
        modality="func",
        entity="_task",
        operation="rename",
        current_value=None,
        replacement="rest",
    )

    assert result.get("applied") is True
    assert result.get("datalad", {}).get("run_per_subject") is True
    assert result.get("datalad", {}).get("run_count") == 2
    run_commands = [command for command in seen_commands if command[1] == "run"]
    assert len(run_commands) == 2
