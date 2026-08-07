"""Guards against re-introducing a duplicate Neurobagel schema-merge copy.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P1-2) found that
app/src/web/blueprints/conversion_participants_blueprint.py defined a
private `_merge_neurobagel_schema_for_columns` that was byte-identical to
the canonical `src.participants_backend.merge_neurobagel_schema_for_columns`
— already imported into the same file for other symbols — but was an
independently-maintained copy rather than a reference to it, i.e. exactly
the `survey_base.py`-style drift class CLAUDE.md warns about. It has since
been replaced with an import alias; this test fails again if a future edit
reintroduces a local copy instead of importing the canonical function.
"""

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.participants_backend as participants_backend  # noqa: E402
from src.web.blueprints import conversion_participants_blueprint as bp  # noqa: E402


def test_blueprint_merge_function_is_the_canonical_one():
    assert (
        bp._merge_neurobagel_schema_for_columns
        is participants_backend.merge_neurobagel_schema_for_columns
    )
