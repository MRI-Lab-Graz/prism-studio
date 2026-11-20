"""A disabled button is gray in every variant: the theme's solid .btn-primary colours must not win over it."""

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "app/static/css/studio-theme.css").read_text(encoding="utf-8")


def test_the_theme_greys_out_disabled_buttons():
    rule = re.search(r"\.studio-theme[^{}]*\.btn:disabled[^{}]*\{([^}]*)\}", CSS)
    assert rule, "no `.studio-theme .btn:disabled` rule: a disabled Load Project button stays green"
    assert "background-color" in rule.group(1) and "box-shadow: none" in rule.group(1)
