"""Compatibility shim for survey recipes backend.

Delegates all runtime symbols to the canonical backend module:
`src/recipes_surveys.py`.

In development the canonical module is loaded directly from `src/`.
In a PyInstaller bundle it is loaded from `backend_bundle/src/` (see
PrismStudio.spec: `('src', 'backend_bundle/src')`).

``app/src/`` must remain a thin adapter — no business logic lives here.
"""

from __future__ import annotations

from src._compat import load_canonical_module

_src_recipes_surveys = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="recipes_surveys.py",
    alias="prism_backend_recipes_surveys",
)

for _name in dir(_src_recipes_surveys):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_src_recipes_surveys, _name)

del _name
del _src_recipes_surveys
