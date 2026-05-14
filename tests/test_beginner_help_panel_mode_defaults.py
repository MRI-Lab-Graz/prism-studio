from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MACROS_TEMPLATE = REPO_ROOT / "app" / "templates" / "includes" / "ui" / "macros.html"
GLOBAL_HELP_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "global-help-mode.js"
HOME_TEMPLATE = REPO_ROOT / "app" / "templates" / "home.html"


def test_help_panel_macro_supports_mode_defaults() -> None:
    content = MACROS_TEMPLATE.read_text(encoding="utf-8")

    assert "default_mode=''" in content
    assert 'data-help-initial-expanded="{{ \'true\' if expanded else \'false\' }}"' in content
    assert '{% if default_mode %} data-help-default-mode="{{ default_mode }}"{% endif %}' in content


def test_global_help_mode_supports_beginner_linked_panels() -> None:
    content = GLOBAL_HELP_SCRIPT.read_text(encoding="utf-8")

    assert "panel.dataset.helpUserExpanded" in content
    assert "panel.dataset.helpDefaultMode" in content
    assert "const initialExpanded = panel.dataset.helpInitialExpanded;" in content
    assert "setPanelExpanded(panel, enabled);" in content
    assert "setPanelExpanded(panel, !isExpanded, true);" in content


def test_home_quick_start_panel_is_linked_to_beginner_mode() -> None:
    content = HOME_TEMPLATE.read_text(encoding="utf-8")

    assert "help_panel('Quick Start', 'info', true, 'fas fa-circle-info', 'py-2', 'mb-3', 'beginner')" in content