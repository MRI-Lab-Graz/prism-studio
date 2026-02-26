"""Command dispatch utilities for prism_tools CLI.

This module provides a central dispatch function. Command registration is
introduced incrementally as handlers are extracted from app/prism_tools.py.
"""

from __future__ import annotations

from argparse import Namespace
from typing import Callable, Mapping


CommandHandler = Callable[[Namespace], None]


def dispatch_command(
    args: Namespace,
    handlers: Mapping[str, CommandHandler],
) -> bool:
    """Dispatch to a top-level command handler if present.

    Returns True when a handler was found and executed, otherwise False.
    """
    command = getattr(args, "command", None)
    if not command:
        return False

    handler = handlers.get(command)
    if not handler:
        return False

    handler(args)
    return True
