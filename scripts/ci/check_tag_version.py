"""Fail unless the given tag is `v<__version__>` of src/__init__.py.

Used by every tag-triggered workflow before it publishes anything.
"""

import re
import sys
from pathlib import Path

init = Path(__file__).resolve().parents[2] / "src" / "__init__.py"
version = re.search(r'__version__ = "([^"]+)"', init.read_text(encoding="utf-8")).group(1)
tag = sys.argv[1] if len(sys.argv) > 1 else ""
if tag != f"v{version}":
    sys.exit(f"Tag {tag!r} does not match the package version v{version}; nothing was published.")
