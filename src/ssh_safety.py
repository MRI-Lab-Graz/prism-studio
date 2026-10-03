"""Guard for values that become the destination argument of ssh/rsync.

`ssh -oProxyCommand=<cmd> ...` runs <cmd> locally, so a host (or `user@host`)
that starts with '-' -- in a URL, a shared project's .prismrc.json or a query
string -- is a command-execution primitive. Every place that passes such a
value to ssh/rsync/datalad must check it here and put `--` before it.
"""

from __future__ import annotations

import re

_SAFE = re.compile(r"[^\s\x00-\x1f\x7f]+")


def ssh_target_ok(target: str) -> bool:
    """True if `[user@]host` is non-empty, has no whitespace/control chars and
    neither the whole value nor its host part starts with '-'."""
    target = str(target or "")
    if not _SAFE.fullmatch(target):
        return False
    return not any(part.startswith("-") for part in (target, target.rpartition("@")[2]))
