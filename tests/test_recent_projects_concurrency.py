"""The page asks for the recent list while it records a project: neither may see a half-written file."""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src.web.blueprints import projects_helpers as helpers  # noqa: E402


def test_concurrent_reads_and_records_lose_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(helpers, "_recent_projects_file", lambda: tmp_path / "recent.json")
    folders = [tmp_path / f"study{i}" for i in range(8)]
    for folder in folders:
        folder.mkdir()
    helpers._record_recent_project({"path": str(folders[0]), "name": "first"})
    short_reads, stop = [], threading.Event()

    def read():
        while not stop.is_set():
            if not helpers._stored_recent_projects():
                short_reads.append(1)

    def record(folder):
        for _ in range(40):
            helpers._record_recent_project({"path": str(folder), "name": folder.name})

    reader = threading.Thread(target=read)
    reader.start()
    writers = [threading.Thread(target=record, args=(folder,)) for folder in folders[1:]]
    for thread in writers:
        thread.start()
    for thread in writers:
        thread.join()
    stop.set()
    reader.join()

    assert not short_reads, f"{len(short_reads)} reads saw an empty list"
    assert len(helpers._stored_recent_projects()) == len(folders)
