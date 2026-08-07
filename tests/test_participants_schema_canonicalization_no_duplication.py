"""Guards against re-introducing a duplicate participants-schema
canonicalization implementation in the Projects participants handler.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P2): the Neurobagel widget's
"Save Annotations" handler (projects_participants_handlers.py) had its own
private canonicalization/merge functions with no CLI equivalent. They were
extracted into src.participants_backend and are now shared with the new
`participants save-schema` CLI command.
"""

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.participants_backend as participants_backend  # noqa: E402
from src.web.blueprints import projects_participants_handlers as handlers  # noqa: E402


def test_blueprint_canonicalize_function_is_the_canonical_one():
    assert (
        handlers._canonicalize_participant_schema_keys
        is participants_backend.canonicalize_participants_schema_keys
    )
