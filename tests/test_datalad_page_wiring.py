"""The DataLad page (/projects/datalad): one next step for the current project, everything else under "More".

The page only triggers: every button calls an existing route (the CLI's commands); `next_step` comes from the backend.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
APP = REPO_ROOT / "app"
TEMPLATES = APP / "templates"
JS = APP / "static" / "js"
PAGE_JS = JS / "modules" / "datalad" / "page.js"

_RENDER = f"""
import importlib.util, sys
sys.path[:0] = [{str(APP)!r}, {str(REPO_ROOT)!r}]
spec = importlib.util.spec_from_file_location("ps", {str(APP / "prism-studio.py")!r})
m = importlib.util.module_from_spec(spec); sys.modules["ps"] = m; spec.loader.exec_module(m)
r = m.app.test_client().get("/projects/datalad")
open(sys.argv[1], "w", encoding="utf-8").write(str(r.status_code) + "\\n" + r.get_data(as_text=True))
"""


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    out = tmp_path_factory.mktemp("datalad_page") / "page.html"
    subprocess.run([sys.executable, "-c", _RENDER, str(out)], capture_output=True, cwd=REPO_ROOT, check=True)
    status, _, html = out.read_text(encoding="utf-8").partition("\n")
    return int(status), html


def test_page_opens_without_a_project(rendered):
    status, html = rendered
    assert status == 200
    assert 'id="dataladRoot"' in html
    assert "js/main.js" in html


def test_page_has_the_step_card_more_and_the_shared_dialogs(rendered):
    _, html = rendered
    for element_id in (
        "dataladStepTitle", "dataladStepText", "dataladPrimary", "dataladSecondary", "dataladMore", "dataladNotice",
        "dataladJobProgress", "dataladJobProgressBar", "dataladJobCancelBtn", "dataladJobResult",
        "dataladLocation", "dataladTarget", "dataladDoctorResult",
        # shared parts, included once and reused
        "remoteFolderBrowserModal", "gitIdentityModal",
        # Get data uses the export's scope lists
        "dataladGetDataForm", "exportSubjectList", "exportSessionList", "exportModalityList", "exportDerivatives",
        "exportSourcedata",
    ):
        assert f'id="{element_id}"' in html, element_id
    # the scope lists are the export's own partial, not a copy
    assert "includes/projects/content_scope_filters.html" in _text(TEMPLATES / "datalad.html")
    assert "includes/projects/content_scope_filters.html" in _text(TEMPLATES / "includes/projects/export_section.html")


def test_get_data_scope_starts_at_the_cli_defaults(rendered):
    _, html = rendered
    checked = lambda element_id: bool(re.search(rf'id="{element_id}"[^>]*\bchecked\b', html))  # noqa: E731
    # src.datalad_get_data.filters_from_options({}): the same defaults as `prism_tools datalad get-data`
    assert checked("exportDerivatives") and checked("exportCode")
    assert not checked("exportSourcedata") and not checked("exportAnalysis")


def test_the_project_guard_lets_the_page_open_without_a_project():
    studio = _text(APP / "prism-studio.py")
    guard = studio[studio.index("def ensure_project_selected_first") :]
    assert 'path == "/projects/datalad"' in guard[: guard.index("\n\n\n")]


def test_navbar_datalad_item_is_always_visible_and_links_to_the_page():
    base = _text(TEMPLATES / "base.html")
    assert "navbarDataladStatusShell" not in base
    link = re.search(r'<a[^>]*id="navbarDataladToggle"[^>]*>', base, re.S).group(0)
    assert "url_for('projects.datalad_page')" in link
    # the count of unsaved changes stays, read from the one state endpoint
    assert 'id="navbarDataladPendingCount"' in base
    assert "/api/projects/datalad/state" in base
    # the navbar no longer saves on click; saving is on the page
    assert "saveNavbarDataladSnapshot" not in base
    assert "navbarDataladToggle?.addEventListener('click'" not in base


def test_main_initializes_the_datalad_page():
    main = _text(JS / "main.js")
    assert "getElementById('dataladRoot')" in main
    assert "modules/datalad/page.js" in main


def test_page_module_only_triggers_existing_routes():
    page = _text(PAGE_JS)
    job = _text(PAGE_JS.with_name("job.js"))  # the job runner; its behaviour is tested in job.test.js
    assert "from './render-state.js'" in page and "from './job.js'" in page
    assert "saveDataladSnapshot" in page and "getLatestFromServer" in page and "enableDatalad" in page
    assert "runDataladCheck" in page  # "Check this computer" is the existing doctor check
    assert "openRemoteFolderPicker" in page  # the existing server folder picker
    assert "readContentScope" in page and "renderScopeLists" in page  # Get data reads the export's lists
    for route in (
        "/api/projects/datalad/state",
        "/api/projects/datalad-server/sync/start",
        "/api/projects/datalad/put-on-server",
        "/api/projects/datalad/get-data",
    ):
        assert route in page, route
    for route in ("/api/projects/datalad/open-from-server", "/api/projects/datalad-server/sync", "/api/projects/current"):
        assert route in job, route
    assert "'prism-project-opened'" in page
    # the page's own state reads ask for the nested-dataset count; the navbar's does not
    assert "check_nested=1" in page and "check_nested" not in _text(TEMPLATES / "base.html")


def test_page_sends_no_default_snapshot_message_of_its_own():
    # An empty description goes to the backend, which applies DEFAULT_SNAPSHOT_MESSAGE as `datalad save` does.
    page = _text(PAGE_JS)
    assert "saveDataladSnapshot(fetchWithApiFallback, message.trim())" in page
    assert "PRISM project changes" not in page


def test_page_refreshes_the_navbar_count_after_an_action():
    assert "window.refreshNavbarDataladCount = (path) => fetchNavbarDataladCleanStatus(path, { force: true });" in _text(
        TEMPLATES / "base.html"
    )
    assert "window.refreshNavbarDataladCount?.(projectPath)" in _text(PAGE_JS)
