#!/usr/bin/env python3
"""Re-exec helper shared by the root launcher scripts.

On Windows ``os.execv`` hands argv to the C runtime, which joins the
arguments with plain spaces and does no quoting.  Any path containing a
space (e.g. ``C:\\Users\\x\\Downloads\\prism-studio-main (1)\\...``) is
therefore split apart and the child interpreter gets garbage.  Use
``subprocess`` there, which quotes properly, and keep ``execv`` on POSIX
where it is exact and cheaper.
"""

import os
import subprocess
import sys


def exec_python(executable, args):
    """Run ``executable`` with ``args`` (argv[1:]), replacing this process."""
    cmd = [str(executable)] + [str(a) for a in args]
    if sys.platform == "win32":
        sys.exit(subprocess.run(cmd).returncode)
    os.execv(cmd[0], cmd)
