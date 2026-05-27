from __future__ import annotations

import runpy

from src._compat import load_canonical_module

_src_batch_convert = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="batch_convert.py",
    alias="prism_backend_batch_convert",
)
for _name in dir(_src_batch_convert):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_src_batch_convert, _name)

del _name
del _src_batch_convert


if __name__ == "__main__":
    runpy.run_module("src.batch_convert", run_name="__main__")