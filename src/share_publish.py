"""Validity-gated push from a department share to the DataLad server sibling.

One implementation: the CLI (`prism_tools publish`) and the Studio routes call
these functions. See docs/superpowers/specs/2026-10-02-share-publish-design.md.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Identity:
    name: str
    email: str


_IDENTITY_RE = re.compile(r"^\s*(?P<name>[^<>]+?)\s*<(?P<email>[^<>@\s]+@[^<>\s]+)>\s*$")


def parse_identity(text: str) -> Identity:
    match = _IDENTITY_RE.match(text or "")
    if not match:
        raise ValueError(f'Identity must look like "Name <email@host>", got {text!r}.')
    return Identity(match["name"], match["email"])


def _global_git(key: str) -> str:
    out = subprocess.run(
        ["git", "config", "--global", key], capture_output=True, text=True, check=False
    )
    return out.stdout.strip() if out.returncode == 0 else ""


def resolve_identity(as_text: str | None = None) -> Identity | None:
    """--as, then PRISM_USER_NAME/EMAIL, then global git config; None if nothing."""
    if as_text:
        return parse_identity(as_text)
    name, email = os.environ.get("PRISM_USER_NAME", "").strip(), os.environ.get("PRISM_USER_EMAIL", "").strip()
    if name and email:
        return Identity(name, email)
    name, email = _global_git("user.name"), _global_git("user.email")
    return Identity(name, email) if name and email else None


def identity_env(identity: Identity) -> dict[str, str]:
    return {
        "GIT_AUTHOR_NAME": identity.name,
        "GIT_AUTHOR_EMAIL": identity.email,
        "GIT_COMMITTER_NAME": identity.name,
        "GIT_COMMITTER_EMAIL": identity.email,
    }


def apply_identity(identity: Identity) -> None:
    """Export the identity into this process so child git/datalad inherit it.

    ponytail: process-global; fine because Studio/CLI is one local process per
    user. Switch to per-call env if Studio ever serves several users at once.
    """
    os.environ.update(identity_env(identity))
