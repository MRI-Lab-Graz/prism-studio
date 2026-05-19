import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = PROJECT_ROOT / "app"
if str(APP_PATH) not in sys.path:
    sys.path.insert(0, str(APP_PATH))

from src.project_session_logging import ProjectSessionLogger  # noqa: E402


def _read_event_lines(log_path: Path) -> list[str]:
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [
        line
        for line in lines
        if line and not line.startswith("#") and not line.startswith("date\ttime\tevent")
    ]


def test_activate_project_creates_session_log_in_code_logs(tmp_path):
    logger = ProjectSessionLogger()
    project_root = tmp_path / "demo_project"
    project_root.mkdir(parents=True, exist_ok=True)

    log_path = logger.activate_project(project_root)

    assert log_path is not None
    assert log_path.parent == project_root / "code" / "logs"
    assert log_path.name.startswith("prism_session_")

    events = _read_event_lines(log_path)
    assert any("\tSESSION_START\tproject=" in line for line in events)
    assert all(
        re.match(r"^\d{4}-\d{2}-\d{2}\t\d{2}:\d{2}:\d{2}\t", line)
        for line in events
    )


def test_record_command_appends_command_with_method_and_endpoint(tmp_path):
    logger = ProjectSessionLogger()
    project_root = tmp_path / "demo_project"
    project_root.mkdir(parents=True, exist_ok=True)

    log_path = logger.activate_project(project_root)
    assert log_path is not None

    logger.record_command(
        "python prism_tools.py survey convert --input demo.xlsx --output /tmp/out",
        method="POST",
        endpoint="conversion_survey.api_survey_convert",
    )

    events = _read_event_lines(log_path)
    command_events = [line for line in events if "\tCOMMAND\t" in line]
    assert len(command_events) == 1
    assert "method=POST" in command_events[0]
    assert "endpoint=conversion_survey.api_survey_convert" in command_events[0]
    assert "python prism_tools.py survey convert --input demo.xlsx --output /tmp/out" in command_events[0]


def test_switching_projects_closes_previous_session_and_starts_new_one(tmp_path):
    logger = ProjectSessionLogger()
    first_project = tmp_path / "project_one"
    second_project = tmp_path / "project_two"
    first_project.mkdir(parents=True, exist_ok=True)
    second_project.mkdir(parents=True, exist_ok=True)

    first_log = logger.activate_project(first_project)
    assert first_log is not None

    second_log = logger.activate_project(second_project)
    assert second_log is not None
    assert second_log != first_log

    first_events = _read_event_lines(first_log)
    second_events = _read_event_lines(second_log)

    assert any("\tSESSION_END\treason=project_switch" in line for line in first_events)
    assert any("\tSESSION_START\tproject=" in line for line in second_events)

    logger.close_active_session(reason="prism_closed")
    second_events_after_close = _read_event_lines(second_log)
    assert any("\tSESSION_END\treason=prism_closed" in line for line in second_events_after_close)


def test_get_active_project_root_tracks_current_session(tmp_path):
    logger = ProjectSessionLogger()
    project_root = tmp_path / "demo_project"
    project_root.mkdir(parents=True, exist_ok=True)

    assert logger.get_active_project_root() is None

    logger.activate_project(project_root)
    assert logger.get_active_project_root() == project_root

    logger.close_active_session(reason="prism_closed")
    assert logger.get_active_project_root() is None
