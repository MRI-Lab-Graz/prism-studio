"""Guards against re-introducing a duplicate Neurobagel schema-merge copy.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P1-2) found that
app/src/web/blueprints/conversion_participants_blueprint.py defined a
private `_merge_neurobagel_schema_for_columns` that was byte-identical to
the canonical `src.participants_backend.merge_neurobagel_schema_for_columns`
— already imported into the same file for other symbols — but was an
independently-maintained copy rather than a reference to it, i.e. exactly
the `survey_base.py`-style drift class CLAUDE.md warns about. It was fixed
by importing the canonical function under a private alias.

The participants blueprint has since been split (see
.superpowers/sdd/2026-08-10-participants-blueprint-split/) and the only
call sites for `_merge_neurobagel_schema_for_columns` now live in
`conversion_participants_merge.py` and `conversion_participants_convert.py`
— the blueprint module itself no longer calls it at all. This test asserts
identity against those two real call sites directly, so it keeps guarding
against the same drift class even if a future edit changes how (or whether)
the blueprint re-exports the name.
"""

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.participants_backend as participants_backend  # noqa: E402
from src.web.blueprints import (  # noqa: E402
    conversion_participants_convert as convert_module,
)
from src.web.blueprints import (  # noqa: E402
    conversion_participants_merge as merge_module,
)


def test_merge_module_uses_the_canonical_merge_function():
    assert (
        merge_module._merge_neurobagel_schema_for_columns
        is participants_backend.merge_neurobagel_schema_for_columns
    )


def test_convert_module_uses_the_canonical_merge_function():
    assert (
        convert_module._merge_neurobagel_schema_for_columns
        is participants_backend.merge_neurobagel_schema_for_columns
    )
