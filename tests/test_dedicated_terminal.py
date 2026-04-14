from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_FILE = (
    Path(__file__).resolve().parents[1] / "app" / "src" / "dedicated_terminal.py"
)


def _load_module_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_relaunch_args_appends_guard_once():
    module = _load_module_from_path("dedicated_terminal_args", MODULE_FILE)

    assert module.build_dedicated_terminal_relaunch_args(["--public"]) == [
        "--public",
        "--no-dedicated-terminal",
    ]
    assert module.build_dedicated_terminal_relaunch_args(
        ["--public", "--no-dedicated-terminal"]
    ) == ["--public", "--no-dedicated-terminal"]


def test_should_relaunch_windows_uses_setting_and_respects_guards():
    module = _load_module_from_path("dedicated_terminal_gate", MODULE_FILE)

    env_names = {
        "attached_env_name": "PRISM_DEDICATED_TERMINAL_ATTACHED",
        "disabled_env_name": "PRISM_DISABLE_DEDICATED_TERMINAL",
        "force_env_name": "PRISM_FORCE_DEDICATED_TERMINAL",
    }

    base_kwargs = {
        "frozen": True,
        "platform": "win32",
        "no_dedicated_terminal": False,
        "env": {},
        "show_dedicated_terminal": True,
        **env_names,
    }

    assert module.should_relaunch_in_dedicated_terminal(**base_kwargs) is True
    assert (
        module.should_relaunch_in_dedicated_terminal(
            **{**base_kwargs, "env": {"PRISM_FORCE_DEDICATED_TERMINAL": "1"}}
        )
        is True
    )
    assert (
        module.should_relaunch_in_dedicated_terminal(
            **{**base_kwargs, "show_dedicated_terminal": False}
        )
        is False
    )
    assert (
        module.should_relaunch_in_dedicated_terminal(
            **{
                **base_kwargs,
                "show_dedicated_terminal": False,
                "env": {"PRISM_FORCE_DEDICATED_TERMINAL": "1"},
            }
        )
        is True
    )
    assert (
        module.should_relaunch_in_dedicated_terminal(
            **{**base_kwargs, "no_dedicated_terminal": True}
        )
        is False
    )
    assert (
        module.should_relaunch_in_dedicated_terminal(
            **{**base_kwargs, "env": {"PRISM_DISABLE_DEDICATED_TERMINAL": "1"}}
        )
        is False
    )
    assert (
        module.should_relaunch_in_dedicated_terminal(
            **{**base_kwargs, "env": {"PRISM_DEDICATED_TERMINAL_ATTACHED": "1"}}
        )
        is False
    )


def test_windows_command_builder_handles_spaces_parentheses_and_guard():
    module = _load_module_from_path("dedicated_terminal_windows_cmd", MODULE_FILE)

    command = module.build_windows_dedicated_terminal_command(
        executable=(
            r"C:\Users\karl\Downloads\prism-studio-Windows (1)\prism-studio-Windows"
            r"\PrismStudio\PrismStudio.exe"
        ),
        argv_tail=["--public"],
        attached_env_name="PRISM_DEDICATED_TERMINAL_ATTACHED",
    )

    assert command.startswith('set "PRISM_DEDICATED_TERMINAL_ATTACHED=1" && ')
    assert "--public" in command
    assert "--no-dedicated-terminal" in command
    assert "\"'" not in command


def test_stream_frozen_logs_only_when_terminal_attached():
    module = _load_module_from_path("dedicated_terminal_streaming", MODULE_FILE)

    assert (
        module.should_stream_frozen_logs_to_attached_terminal(
            frozen=True,
            env={"PRISM_DEDICATED_TERMINAL_ATTACHED": "1"},
            attached_env_name="PRISM_DEDICATED_TERMINAL_ATTACHED",
        )
        is True
    )
    assert (
        module.should_stream_frozen_logs_to_attached_terminal(
            frozen=True,
            env={},
            attached_env_name="PRISM_DEDICATED_TERMINAL_ATTACHED",
        )
        is False
    )
    assert (
        module.should_stream_frozen_logs_to_attached_terminal(
            frozen=False,
            env={"PRISM_DEDICATED_TERMINAL_ATTACHED": "1"},
            attached_env_name="PRISM_DEDICATED_TERMINAL_ATTACHED",
        )
        is False
    )
