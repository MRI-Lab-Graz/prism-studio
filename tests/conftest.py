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


@pytest.fixture
def make_edf():
    """Factory building a minimal valid EDF by hand (no pyedflib needed).

    make_edf(path, {label: (physical_samples, rate_hz)}, pmin=-100, pmax=100,
    dmin=-32768, dmax=32767, duration=1.0) -> path. Samples are encoded to
    int16 with the EDF physical/digital mapping; length must be a whole number
    of records for every channel.
    """
    import numpy as np

    def _make(path, channels, *, pmin=-100.0, pmax=100.0, dmin=-32768, dmax=32767, duration=1.0):
        labels = list(channels)
        spr = [int(round(rate * duration)) for _, rate in channels.values()]
        n_rec = len(channels[labels[0]][0]) // spr[0]
        ns = len(labels)

        def f(v, n):
            return str(v).ljust(n)[:n].encode("ascii")

        head = (
            f("0", 8) + f("X X X X", 80) + f("Startdate X X X X", 80) + f("01.01.20", 8)
            + f("00.00.00", 8) + f(256 * (ns + 1), 8) + f("", 44) + f(n_rec, 8)
            + f(duration, 8) + f(ns, 4)
        )
        sig = b"".join(f(l, 16) for l in labels) + f("", 80 * ns) + f("uV", 8 * ns)
        sig += b"".join(f(pmin, 8) for _ in labels) + b"".join(f(pmax, 8) for _ in labels)
        sig += b"".join(f(dmin, 8) for _ in labels) + b"".join(f(dmax, 8) for _ in labels)
        sig += f("", 80 * ns) + b"".join(f(s, 8) for s in spr) + f("", 32 * ns)
        digital = [
            np.round((np.asarray(channels[l][0], float) - pmin) * (dmax - dmin) / (pmax - pmin) + dmin)
            .astype("<i2").reshape(n_rec, s)
            for l, s in zip(labels, spr)
        ]
        data = np.concatenate(digital, axis=1).tobytes()
        path.write_bytes(head + sig + data)
        return path

    return _make
