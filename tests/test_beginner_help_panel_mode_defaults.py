from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MACROS_TEMPLATE = REPO_ROOT / "app" / "templates" / "includes" / "ui" / "macros.html"
BASE_TEMPLATE = REPO_ROOT / "app" / "templates" / "base.html"
GLOBAL_HELP_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "global-help-mode.js"
HOME_TEMPLATE = REPO_ROOT / "app" / "templates" / "home.html"


def test_help_panel_macro_supports_mode_defaults() -> None:
    content = MACROS_TEMPLATE.read_text(encoding="utf-8")

    assert "default_mode=''" in content
    assert 'data-help-initial-expanded="{{ \'true\' if expanded else \'false\' }}"' in content
    assert "normalized_title in ['quick guide', 'quick start']" in content
    assert '{% if resolved_default_mode %} data-help-default-mode="{{ resolved_default_mode }}"{% endif %}' in content


def test_base_template_hides_beginner_only_help_panels_before_bootstrap() -> None:
    content = BASE_TEMPLATE.read_text(encoding="utf-8")

    assert "const storageKey = 'prism_beginner_help_mode';" in content
    assert "document.documentElement.setAttribute('data-beginner-help-mode', enabled ? 'on' : 'off');" in content
    assert 'html[data-beginner-help-mode="off"] [data-help-panel][data-help-default-mode="beginner"]' in content


def test_global_help_mode_supports_beginner_linked_panels() -> None:
    content = GLOBAL_HELP_SCRIPT.read_text(encoding="utf-8")

    assert "panel.dataset.helpUserExpanded" in content
    assert "panel.dataset.helpDefaultMode" in content
    assert "panel.classList.toggle('d-none', beginnerOnly && !enabled);" in content
    assert "if (beginnerOnly && !enabled) {" in content
    assert "const initialExpanded = panel.dataset.helpInitialExpanded;" in content
    assert "setPanelExpanded(panel, enabled);" in content
    assert "setPanelExpanded(panel, !isExpanded, true);" in content


def test_home_quick_start_panel_is_linked_to_beginner_mode() -> None:
    content = HOME_TEMPLATE.read_text(encoding="utf-8")

    assert "help_panel('Quick Start', 'info', true, 'fas fa-circle-info', 'py-2', 'mb-3', 'beginner')" in content