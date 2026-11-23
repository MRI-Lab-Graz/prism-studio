import subprocess

from src.share_publish import _audit, audit_path


def test_the_audit_log_is_save_jsonl_and_keeps_the_old_publish_jsonl_history(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    old = audit_path(tmp_path).with_name("publish.jsonl")
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_text('{"result": "old"}\n', encoding="utf-8")

    _audit(tmp_path, identity=None, sibling="", result="saved", error_count=0)

    log = audit_path(tmp_path)
    assert log.name == "save.jsonl" and not old.exists()
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[0] == '{"result": "old"}' and '"saved"' in lines[1]


def test_history_of_both_logs_is_kept_and_an_unwritable_legacy_never_raises(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    log = audit_path(tmp_path)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text('{"result": "new"}\n', encoding="utf-8")
    log.with_name("publish.jsonl").write_text('{"result": "old"}\n', encoding="utf-8")
    _audit(tmp_path, identity=None, sibling="", result="saved", error_count=0)
    assert log.read_text(encoding="utf-8").splitlines()[:2] == ['{"result": "old"}', '{"result": "new"}']

    from pathlib import Path

    log.with_name("publish.jsonl").write_text("x\n", encoding="utf-8")
    monkeypatch.setattr(Path, "unlink", lambda self, *a, **k: (_ for _ in ()).throw(PermissionError("locked")))
    _audit(tmp_path, identity=None, sibling="", result="saved", error_count=0)  # must not raise
