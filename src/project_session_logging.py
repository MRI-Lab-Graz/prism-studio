"""Project-scoped session logging for backend command activity."""

from __future__ import annotations

import atexit
from datetime import datetime
from pathlib import Path
import threading


def _now_local() -> datetime:
    """Return the current local time with timezone information."""
    return datetime.now().astimezone()


def _normalize_project_root(project_path: str | Path | None) -> Path | None:
    """Normalize a project root path, accepting project.json inputs."""
    if project_path is None:
        return None

    project_text = str(project_path).strip()
    if not project_text:
        return None

    try:
        normalized = Path(project_text).expanduser().resolve(strict=False)
    except Exception:
        return None

    if normalized.name == "project.json":
        return normalized.parent

    if normalized.is_file():
        return normalized.parent

    return normalized


def _sanitize_details(value: str) -> str:
    """Sanitize event details to keep one physical line per event."""
    text = str(value or "")
    text = text.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")
    text = text.replace("\t", " ")
    return text.strip()


class ProjectSessionLogger:
    """Manage per-project command session logs."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active_project_root: Path | None = None
        self._active_log_path: Path | None = None

    def activate_project(self, project_path: str | Path | None) -> Path | None:
        """Start a session log for the given project.

        When another project session is already active, it is closed first with
        a switch reason and a new session log is opened for the new project.
        """
        project_root = _normalize_project_root(project_path)
        if project_root is None:
            return None

        with self._lock:
            if (
                self._active_project_root == project_root
                and self._active_log_path is not None
            ):
                return self._active_log_path

            if self._active_log_path is not None:
                self._close_active_locked(
                    reason=f"project_switch next_project={project_root}"
                )

            started_at = _now_local()
            log_path = self._build_log_path(project_root, started_at)
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with log_path.open("w", encoding="utf-8") as handle:
                    handle.write("# PRISM project session log\n")
                    handle.write("# format: date<TAB>time<TAB>event<TAB>details\n")
                    handle.write(f"# project_root: {project_root}\n")
                    handle.write(f"# session_started_at: {started_at.isoformat()}\n")
                    handle.write("date\ttime\tevent\tdetails\n")
            except Exception:
                self._active_project_root = None
                self._active_log_path = None
                return None

            self._active_project_root = project_root
            self._active_log_path = log_path
            self._append_event_locked("SESSION_START", f"project={project_root}")
            return log_path

    def close_active_session(self, reason: str = "session_closed") -> Path | None:
        """Close the currently active project session, if any."""
        with self._lock:
            return self._close_active_locked(reason=reason)

    def record_command(
        self,
        command: str,
        *,
        method: str = "",
        endpoint: str = "",
    ) -> None:
        """Append a command line to the active session log."""
        command_text = str(command or "").strip()
        if not command_text:
            return

        with self._lock:
            if self._active_log_path is None:
                return

            details_parts: list[str] = []
            method_text = str(method or "").strip().upper()
            endpoint_text = str(endpoint or "").strip()

            if method_text:
                details_parts.append(f"method={method_text}")
            if endpoint_text:
                details_parts.append(f"endpoint={endpoint_text}")
            details_parts.append(f"command={command_text}")

            self._append_event_locked("COMMAND", " ".join(details_parts))

    def get_active_log_path(self) -> Path | None:
        """Return current active session log path, if any."""
        with self._lock:
            return self._active_log_path

    def _build_log_path(self, project_root: Path, started_at: datetime) -> Path:
        log_dir = project_root / "code" / "logs"
        base_name = f"prism_session_{started_at.strftime('%Y%m%d_%H%M%S')}.log"
        log_path = log_dir / base_name

        suffix = 1
        while log_path.exists():
            suffix += 1
            log_path = (
                log_dir
                / f"prism_session_{started_at.strftime('%Y%m%d_%H%M%S')}_{suffix}.log"
            )

        return log_path

    def _append_event_locked(self, event: str, details: str) -> None:
        if self._active_log_path is None:
            return

        timestamp = _now_local()
        line = (
            f"{timestamp.strftime('%Y-%m-%d')}\t"
            f"{timestamp.strftime('%H:%M:%S')}\t"
            f"{event}\t"
            f"{_sanitize_details(details)}\n"
        )

        try:
            with self._active_log_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            # Logging should never break request handling.
            return

    def _close_active_locked(self, reason: str) -> Path | None:
        if self._active_log_path is None:
            self._active_project_root = None
            return None

        closed_log_path = self._active_log_path
        self._append_event_locked("SESSION_END", f"reason={reason}")
        self._active_project_root = None
        self._active_log_path = None
        return closed_log_path


_PROJECT_SESSION_LOGGER = ProjectSessionLogger()


def activate_project_session(project_path: str | Path | None) -> Path | None:
    """Start a new project session log or keep the current one."""
    return _PROJECT_SESSION_LOGGER.activate_project(project_path)


def close_project_session(reason: str = "session_closed") -> Path | None:
    """Close the active project session log."""
    return _PROJECT_SESSION_LOGGER.close_active_session(reason=reason)


def record_project_session_command(
    command: str,
    *,
    method: str = "",
    endpoint: str = "",
) -> None:
    """Record a command entry in the currently active project session log."""
    _PROJECT_SESSION_LOGGER.record_command(
        command,
        method=method,
        endpoint=endpoint,
    )


def get_active_project_session_log_path() -> Path | None:
    """Return currently active project session log file path, if any."""
    return _PROJECT_SESSION_LOGGER.get_active_log_path()


@atexit.register
def _close_project_session_on_exit() -> None:
    _PROJECT_SESSION_LOGGER.close_active_session(reason="prism_closed")


__all__ = [
    "ProjectSessionLogger",
    "activate_project_session",
    "close_project_session",
    "record_project_session_command",
    "get_active_project_session_log_path",
]
