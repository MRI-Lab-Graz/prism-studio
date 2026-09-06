from __future__ import annotations

from src.undo_log import UndoLog


def test_undo_log_peek_last_returns_none_when_empty(tmp_path):
    log = UndoLog(tmp_path)
    assert log.peek_last() is None


def test_undo_log_record_and_peek_last_returns_most_recent(tmp_path):
    log = UndoLog(tmp_path)
    log.record(kind="subject_rewrite", description="first", payload={"a": 1})
    log.record(kind="subject_rewrite", description="second", payload={"a": 2})

    entry = log.peek_last()
    assert entry["description"] == "second"
    assert entry["kind"] == "subject_rewrite"
    assert entry["payload"] == {"a": 2}
    assert entry["id"]
    assert entry["timestamp"]


def test_undo_log_pop_last_removes_the_entry(tmp_path):
    log = UndoLog(tmp_path)
    log.record(kind="delete", description="first", payload={})
    log.record(kind="delete", description="second", payload={})

    popped = log.pop_last()
    assert popped["description"] == "second"

    remaining = log.peek_last()
    assert remaining["description"] == "first"


def test_undo_log_pop_last_returns_none_when_empty(tmp_path):
    log = UndoLog(tmp_path)
    assert log.pop_last() is None


def test_undo_log_persists_across_instances(tmp_path):
    UndoLog(tmp_path).record(kind="entity_rewrite", description="persisted", payload={"x": True})

    reloaded = UndoLog(tmp_path)
    entry = reloaded.peek_last()
    assert entry["description"] == "persisted"
    assert entry["payload"] == {"x": True}


def test_undo_log_caps_history_length(tmp_path):
    log = UndoLog(tmp_path, max_entries=3)
    for i in range(5):
        log.record(kind="delete", description=f"op-{i}", payload={})

    reloaded = UndoLog(tmp_path, max_entries=3)
    descriptions = [entry["description"] for entry in reloaded.all_entries()]
    assert descriptions == ["op-2", "op-3", "op-4"]
