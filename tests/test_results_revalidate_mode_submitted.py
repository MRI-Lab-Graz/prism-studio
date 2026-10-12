"""Re-validate must send the chosen mode.

Disabled form controls are omitted from FormData, and setActionsDisabled(true)
disables the mode <select>, so the form has to be read before that call.
"""
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "app/static/js/results.js"


def test_formdata_is_built_before_controls_are_disabled():
    src = JS.read_text(encoding="utf-8")
    body = src[src.index("async function startRevalidation") :]
    assert body.index("new FormData(revalidateForm)") < body.index("setActionsDisabled(true)")
