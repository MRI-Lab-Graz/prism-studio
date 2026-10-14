"""Windows-only environment limits, reported as skips instead of failures.

* WinError 1314: creating symlinks needs Developer Mode or admin.
* WinError 4551: an Application Control policy blocks an executable (the sh /
  git-annex / datalad shims on some managed machines).
* WinError 193: a #! shell script run directly (Windows needs sh to start it).
* `git annex` installed but not runnable (same policy, seen as exit status 1).

With the limitation lifted the tests run normally. Done on the report (not
around the test body) so it also covers unittest.TestCase tests.
"""

import functools
import subprocess

import pytest

_REASONS = {
    "WinError 1314": "creating symlinks needs Windows Developer Mode or admin",
    "WinError 4551": "an executable is blocked by this machine's Application Control policy",
    "WinError 193": "a #!/bin/sh test fixture cannot be executed directly on Windows",
}


@functools.cache
def _annex_works() -> bool:
    try:
        return subprocess.run(["git", "annex", "version"], capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _environment_reason(exc: BaseException) -> str | None:
    text = str(exc)
    for marker, reason in _REASONS.items():
        if marker in text:
            return reason
    if isinstance(exc, subprocess.CalledProcessError) and "annex" in str(exc.cmd) and not _annex_works():
        return "git-annex is installed but not runnable here"
    return None


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    if report.failed and call.excinfo is not None:
        reason = _environment_reason(call.excinfo.value)
        if reason:
            report.outcome = "skipped"
            report.longrepr = (str(item.path), item.location[1] or 0, f"Skipped: {reason}")
    return report
