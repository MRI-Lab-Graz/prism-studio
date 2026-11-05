"""SSH login failures are told apart from ordinary file permission errors."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.datalad_doctor import classify_ssh_error  # noqa: E402


def test_local_file_permission_error_is_not_blamed_on_the_ssh_key():
    assert classify_ssh_error("[Errno 13] Permission denied: '/data/x'")[0] == "unknown"


def test_a_rejected_key_is_recognised():
    assert classify_ssh_error("kalle@h.at: Permission denied (publickey,password).")[0] == "key_rejected"
