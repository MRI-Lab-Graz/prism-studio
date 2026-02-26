from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class EnvironmentCache:
    def __init__(self, cache_path: str | Path):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Any] = {}
        if self.cache_path.exists():
            try:
                self._data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def get(self, key: str) -> Any:
        return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def flush(self) -> None:
        self.cache_path.write_text(
            json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8"
        )
