"""Regression test for DatasetFixer._rename_file: must overwrite an existing
destination rather than raise.

os.rename() raises FileExistsError on Windows when the destination already
exists (POSIX rename() overwrites atomically; Windows doesn't). Renaming to
an already-occupied path can happen for real, e.g. two independently broken
filenames both getting corrected to the same "fixed" name. os.replace() is
the cross-platform-safe equivalent and must be used instead.
"""

from app.src.fixer import DatasetFixer, FixAction


def test_rename_file_overwrites_existing_destination(tmp_path):
    source = tmp_path / "sub-01_bad-name.tsv"
    destination = tmp_path / "sub-01_task-rest_events.tsv"
    source.write_text("source content", encoding="utf-8")
    destination.write_text("stale content", encoding="utf-8")

    fixer = DatasetFixer(str(tmp_path))
    fix = FixAction(
        issue_code="TEST",
        description="rename",
        file_path=str(source),
        action_type="rename",
        details={"new_path": str(destination)},
    )

    assert fixer._rename_file(fix) is True
    assert not source.exists()
    assert destination.read_text(encoding="utf-8") == "source content"


def test_rename_file_returns_false_when_source_missing(tmp_path):
    fixer = DatasetFixer(str(tmp_path))
    fix = FixAction(
        issue_code="TEST",
        description="rename",
        file_path=str(tmp_path / "does-not-exist.tsv"),
        action_type="rename",
        details={"new_path": str(tmp_path / "target.tsv")},
    )

    assert fixer._rename_file(fix) is False
