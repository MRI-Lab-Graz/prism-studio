from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


class UndoLog:
    """Tracks the most recent undoable File Management operations for a project.

    Backed by a single JSON file so it survives across requests/processes
    without needing a database. Intentionally single-level in spirit (the
    UI only ever offers "Undo Last Operation") even though the file keeps a
    short capped history, so a later multi-level undo/redo UI has data to
    build on without a storage-format change.
    """

    def __init__(self, project_root: Path, max_entries: int = 20):
        self.project_root = Path(project_root)
        self.max_entries = max_entries
        self._log_path = self.project_root / ".prism" / "undo_log.json"

    def _read_entries(self) -> list[dict]:
        if not self._log_path.exists():
            return []
        try:
            data = json.loads(self._log_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return data if isinstance(data, list) else []

    def _write_entries(self, entries: list[dict]) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    def record(self, kind: str, description: str, payload: dict) -> str:
        entries = self._read_entries()
        entry_id = uuid.uuid4().hex
        entries.append(
            {
                "id": entry_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "kind": kind,
                "description": description,
                "payload": payload,
            }
        )
        entries = entries[-self.max_entries :]
        self._write_entries(entries)
        return entry_id

    def all_entries(self) -> list[dict]:
        return self._read_entries()

    def peek_last(self) -> dict | None:
        entries = self._read_entries()
        return entries[-1] if entries else None

    def pop_last(self) -> dict | None:
        entries = self._read_entries()
        if not entries:
            return None
        last = entries.pop()
        self._write_entries(entries)
        return last
