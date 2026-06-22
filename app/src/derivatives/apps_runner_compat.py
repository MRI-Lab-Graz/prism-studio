from __future__ import annotations

from src._compat import load_canonical_module

_src_apps_runner_compat = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="derivatives/apps_runner_compat.py",
    alias="prism_backend_derivatives_apps_runner_compat",
)
for _name in dir(_src_apps_runner_compat):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_src_apps_runner_compat, _name)

del _name
del _src_apps_runner_compat
