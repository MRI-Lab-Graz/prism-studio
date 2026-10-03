import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
for p in (APP, APP / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.core.validation import determine_exit_code, validate_subject_only  # noqa: E402


def test_empty_session_folder_is_an_error(tmp_path):
    root = tmp_path / "proj"
    (root / "sub-001" / "ses-01").mkdir(parents=True)
    issues, _stats = validate_subject_only(str(root), "sub-001")
    assert any("Empty directory" in issue[1] for issue in issues)
    assert determine_exit_code(issues) == 1


def test_subject_without_problems_is_clean(tmp_path):
    root = tmp_path / "proj"
    (root / "sub-001").mkdir(parents=True)
    issues, _stats = validate_subject_only(str(root), "sub-001")
    assert issues == []


def test_only_the_named_subject_is_looked_at(tmp_path):
    root = tmp_path / "proj"
    (root / "sub-001").mkdir(parents=True)
    (root / "sub-002" / "ses-01").mkdir(parents=True)  # broken, but not ours
    issues, _stats = validate_subject_only(str(root), "sub-001")
    assert issues == []
